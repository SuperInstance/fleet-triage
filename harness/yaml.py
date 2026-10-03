#!/usr/bin/env python3
"""
yaml.py — a drop-in `yaml` module backed by node's real YAML parser.

WHY THIS FILE EXISTS
--------------------
`canfail.py` (the `can-fail-ci` rule) starts with:

    try:
        import yaml
    except ImportError:
        sys.exit("canfail.py needs PyYAML:  python3 -m pip install pyyaml")

There is no pip in this environment and no PyYAML. So `canfail.py --selftest` -- the
sibling lane's own negative control -- had NEVER BEEN EXECUTED. It exited 1, which is
loud, so it was not fail-open. But an unrunnable control is not a control.

The obvious shortcuts were both rejected:

  1. A hand-rolled subset parser for the GitHub Actions YAML dialect. Rejected: a
     parser that is wrong in the *lenient* direction invents structure the workflow
     does not have, and a rule that reads invented structure is exactly the failure
     this lane exists to catch. A parser that is wrong in the *strict* direction
     silently reports "no findings" on a file it did not understand -- which is a
     FAIL-OPEN parser, i.e. the disease, wearing the costume of the cure.

  2. Pretending to parse and returning {} on error. Same failure. Never do this.

So: delegate to `/app/node_modules/yaml`, which is a real, spec-following YAML 1.2
implementation. Real parser, no weakened rule.

FAIL-CLOSED CONTRACT
--------------------
If node is missing, or the parser is missing, or a document does not parse, this
module raises. It NEVER returns an empty structure on error. An empty dict is a
legitimate YAML document (`{}`), so returning it for an error would be a lie that
`canfail.py` cannot detect -- it would read "this workflow has no steps" and conclude
the workflow cannot fail, which is the correct verdict by accident, for the wrong
reason, on a file that was never read.

There is a second, quieter failure mode this also guards: the *wrong repo* being read.
`safe_load` returns the parsed document; `canfail.py` is responsible for choosing the
file. See `negctl/test_yaml_shim.py` control Y-4.

CALIBRATION HISTORY
-------------------
  v1  `require(process.argv[2])`. With `node -e SCRIPT ARG`, argv is
      [execPath, ARG] -- there is no argv[0] for the script. So argv[2] was always
      undefined, `require` threw on EVERY document, and canfail.py --selftest
      reported 5 of 5 constructed failures as "got=False" and then crashed on
      IndexError. Read at face value that is "the rule detects nothing", and it was
      very nearly written up as a fatal defect in the sibling lane's rule.
      It was not. It was one index off, in this file.
      The lesson is the one this whole lane is about, caught in the act: a
      BROKEN PARSER IS INDISTINGUISHABLE FROM A WORKFLOW THAT CANNOT FAIL, and the
      cheapest way to tell them apart is to check the tool's own plumbing before
      believing its verdict about someone else's code. canfail.py handled this
      correctly by design -- it returned `unverifiable: True` rather than inventing
      a clean verdict -- which is why the bug was visible instead of silent.
      Fixed: argv[1]. Control Y-5 in negctl/ pins it.
"""
from __future__ import annotations

import json
import os
import subprocess

NODE = os.environ.get("HARNESS_NODE", "node")
_CANDIDATES = (
    "/app/node_modules/yaml",
    "/app/packages/ui/node_modules/yaml",
)


class YamlError(RuntimeError):
    """Raised when a document cannot be parsed. Never swallowed."""


def _pkg() -> str:
    for c in _CANDIDATES:
        if os.path.isdir(c):
            return c
    raise YamlError(
        "no YAML implementation found; looked in %r" % (_CANDIDATES,)
    )


_JS = r"""
const Y = require(process.argv[1]);
let s = '';
process.stdin.on('data', d => s += d);
process.stdin.on('end', () => {
  try {
    const v = Y.parse(s);
    process.stdout.write(JSON.stringify({ok: true, v: v === undefined ? null : v}));
  } catch (e) {
    process.stdout.write(JSON.stringify({ok: false, err: String(e && e.message || e)}));
  }
});
"""


def safe_load(stream):
    """Parse one YAML document. Raises YamlError on anything it cannot read."""
    text = stream if isinstance(stream, str) else stream.read()
    try:
        r = subprocess.run(
            [NODE, "-e", _JS, _pkg()],
            input=text, capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError as e:
        raise YamlError("node not found on PATH (%s)" % NODE) from e
    except subprocess.TimeoutExpired as e:
        raise YamlError("YAML parse timed out after 60s") from e
    if r.returncode != 0:
        raise YamlError("YAML parser crashed rc=%d: %s" % (r.returncode, r.stderr[:400]))
    try:
        out = json.loads(r.stdout)
    except Exception as e:
        raise YamlError("unparseable parser output %r: %s" % (r.stdout[:200], e)) from e
    if not out.get("ok"):
        raise YamlError("YAML syntax error: %s" % out.get("err"))
    return out["v"]


load = safe_load


def load_all(stream):
    """Multi-document parse. canfail.py reads one file at a time; provided for parity."""
    text = stream if isinstance(stream, str) else stream.read()
    return [safe_load(text)]
