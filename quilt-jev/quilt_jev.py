#!/usr/bin/env python3
"""quilt-jev — render a JEV probability tensor to a terminal.

The canonical artifact is the TENSOR. Every picture, ramp, or table this tool
prints is a PROJECTION of that tensor, and every projection names itself.

Derived from achimala/jev-paint (MIT) — web/jev.mjs, web/art.mjs.
Standard library only. No framework. The API key is never printed or stored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ENDPOINT = os.environ.get("JEV_BASE_URL", "https://api.typesafe.ai") .rstrip("/") + "/v1/systemone"
MODEL = "jev-latest"            # request alias. jev-1.13.0 is the RESPONSE id.
SIZES = (8, 12, 16, 24, 32)     # from web/jev.mjs `sizes`
BATCH_PIXELS = 144              # from web/jev.mjs `batchPixels.palette`
CONCURRENCY = 4                 # from web/jev.mjs `Array.from({length: Math.min(4, ...)})`

# web/jev.mjs `palette`, in insertion order. The index IS the wire position.
PALETTE = {
    "black": (0, 0, 0), "white": (255, 255, 255), "gray": (128, 128, 128),
    "red": (220, 40, 40), "orange": (255, 150, 40), "pink": (255, 170, 190),
    "brown": (125, 70, 35), "tan": (205, 160, 105), "green": (65, 165, 65),
    "dark_green": (25, 90, 35), "blue": (45, 90, 210), "sky_blue": (170, 220, 255),
    "yellow": (255, 215, 40), "purple": (110, 45, 160), "navy": (15, 20, 50),
    "cream": (255, 240, 205),
}
LABELS = list(PALETTE)


class TransportFailure(Exception):
    """The endpoint failed at the wire level. NEVER rendered as an empty grid."""


class SchemaFailure(Exception):
    """The endpoint answered with valid JSON that is not a valid tensor."""


# ---------------------------------------------------------------- probability
# Ports of web/art.mjs `normalized` / `argmax` / `probability`.

def normalized(p):
    total = sum(p)
    if not total or any(not math.isfinite(x) or x < 0 for x in p):
        raise SchemaFailure("Invalid distribution")
    return [x / total for x in p]


def argmax(p):
    return p.index(max(p))


def probability(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) \
            or not math.isfinite(value) or value < 0 or value > 1:
        raise SchemaFailure("Jev returned an invalid probability.")
    return float(value)


def distribution(answer):
    """Per-pixel label->probability map for a `choice` answer, in palette order."""
    probs = (answer or {}).get("probabilities")
    if not probs:
        raise SchemaFailure("Jev returned an incomplete distribution.")
    return normalized([probability(probs.get(label, 0.0)) for label in LABELS])


def entropy(dist):
    """Shannon entropy (nats), matching the source's formulation."""
    h = 0.0
    for p in dist:
        if p > 0:
            h -= p * math.log(p)
    return h


def uncertainty(dist):
    """Source's compression: 1 - exp(-H). Independent of unused labels."""
    return 1.0 - math.exp(-entropy(dist))


def margin(dist):
    """Top-1 minus top-2. How much the argmax is worth believing."""
    s = sorted(dist, reverse=True)
    return s[0] - s[1] if len(s) > 1 else s[0]


def mean_color(dist):
    """Weighted mean RGB under the full distribution — the underpainting."""
    out = [0.0, 0.0, 0.0]
    for w, label in zip(dist, LABELS):
        r, g, b = PALETTE[label]
        out[0] += w * r
        out[1] += w * g
        out[2] += w * b
    return [min(255, max(0, int(round(c)))) for c in out]


# ------------------------------------------------------------------- requests
# Port of web/jev.mjs `buildRequests`, palette method.

def build_batches(prompt, size):
    if size not in SIZES:
        raise ValueError(f"Grid size must be one of {list(SIZES)}.")
    if not prompt.strip() or len(prompt) > 2000:
        raise ValueError("Enter a prompt of up to 2,000 characters.")
    state = {
        "image_description": prompt.strip(),
        "width": size,
        "height": size,
        "coordinates": "Origin (0,0) top-left, x increases right, y increases down.",
        "task": ("Compose one coherent recognizable pixel-art image. "
                 "Fill the canvas including background. No text or border."),
    }
    criteria = {label: None for label in LABELS}   # values are null, not prose
    questions = {}
    for y in range(size):
        for x in range(size):
            questions[f"x{x}_y{y}"] = {
                "type": "choice",
                "instructions": f"What color is pixel (x={x}, y={y}) in the described image?",
                "criteria": criteria,
            }
    entries = list(questions.items())
    return [{"model": MODEL, "state": state,
             "questions": dict(entries[i:i + BATCH_PIXELS])}
            for i in range(0, len(entries), BATCH_PIXELS)]


def call(batch, key, tries=5):
    """One POST. Transport failure is RAISED, never swallowed into empty answers."""
    body = json.dumps(batch).encode()
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(
            ENDPOINT, data=body, method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                payload = json.loads(r.read() or b"{}")
            if not payload.get("answers"):
                raise SchemaFailure("Jev returned no answers.")
            return payload
        except SchemaFailure:
            raise
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 413, 422):
                raise SchemaFailure(f"HTTP {e.code}: request rejected by the endpoint.")
            last = e
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            # TLS EOF lands here. It is evidence about the wire, never about the grid.
            last = e
        if attempt < tries - 1:
            time.sleep(min(8.0, 0.4 * (2 ** attempt)) * (0.5 + random.random()))
    raise TransportFailure(f"{type(last).__name__}: {last}")


def generate(prompt, size, key, progress=True):
    batches = build_batches(prompt, size)
    answers, done = {}, 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for payload in pool.map(lambda b: call(b, key), batches):
            answers.update(payload["answers"])
            done += 1
            if progress:
                print(f"  batch {done}/{len(batches)}", file=sys.stderr)
    return pack(answers, size, prompt)


def pack(answers, size, prompt):
    """The tensor. This dict IS the canonical artifact; nothing below adds to it."""
    pixels = []
    for y in range(size):
        for x in range(size):
            pixels.append({
                "x": x, "y": y,
                "probabilities": distribution(answers.get(f"x{x}_y{y}")),
            })
    return {
        "method": "palette", "size": size, "prompt": prompt.strip(),
        "labels": LABELS,
        "palette": [list(PALETTE[l]) for l in LABELS],
        "pixels": pixels,
    }


# --------------------------------------------------------------------- tensor
def canonical(obj):
    """Byte-stable JSON. Two equal tensors must produce two equal files."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def write_tensor(tensor, path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(tensor, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def write_tensor_new(tensor, path):
    """Never clobber an existing tensor unless it is byte-identical.

    The tensor is the artifact. Re-running the same prompt must not silently
    destroy the previous run's evidence -- that is how a receipt gets lost.
    An explicit --out is taken as consent to overwrite; the derived default
    name is not.
    """
    blob = json.dumps(tensor, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(blob)
        return path
    with open(path, encoding="utf-8") as fh:
        if fh.read() == blob:
            return path                      # same tensor, same name: a no-op
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem}-{n}{ext}"):
        n += 1
    path = f"{stem}-{n}{ext}"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(blob)
    return path


def load_tensor(path):
    with open(path, encoding="utf-8") as fh:
        t = json.load(fh)
    return upgrade(t, path)


def upgrade(t, path="<tensor>"):
    """Accept a raw achimala/jev-paint payload and lift it to a labelled tensor.

    That repo's recorded fixtures carry `palette` as bare RGB triples and pixel
    entries with no coordinates. Coordinates are positional by construction
    (web/jev.mjs packs y-major, x-minor), so they are recovered, not guessed.
    """
    if "palette" in t and "labels" not in t:
        rgb = [tuple(c) for c in t["palette"]]
        if rgb == [PALETTE[l] for l in LABELS]:
            t["labels"] = list(LABELS)
        else:
            t["labels"] = ["c%02d%s" % (i, "".join(hex(v)[2:] for v in c))
                           for i, c in enumerate(rgb)]
    if "labels" not in t and "palette" not in t:
        raise SchemaFailure(f"{path}: no palette; it is not a jev tensor")
    size = t.get("size")
    if not isinstance(size, int) or size <= 0:
        raise SchemaFailure(f"{path}: missing or bad 'size'")
    px = t.get("pixels")
    if not isinstance(px, list) or len(px) != size * size:
        raise SchemaFailure(f"{path}: 'pixels' is not a {size}x{size} grid")
    n = len(t["labels"])
    for i, p in enumerate(px):
        if not isinstance(p, dict) or "probabilities" not in p:
            raise SchemaFailure(f"{path}: cell {i} has no probabilities")
        if "x" not in p or "y" not in p:
            p["x"], p["y"] = i % size, i // size
    for field in ("size", "pixels", "labels", "palette"):
        if field not in t:
            raise SchemaFailure(f"{path}: tensor is missing '{field}'")
    return t


# --------------------------------------------------------------------- verify
def verify(tensor):
    """The invariant, executable. Returns (ok, list of findings)."""
    findings, ok = [], True
    size, pixels = tensor["size"], tensor["pixels"]
    labels = tensor["labels"]

    if len(pixels) != size * size:
        ok = False
        findings.append(f"pixel count {len(pixels)} != size*size ({size * size})")

    coords = [(p.get("x"), p.get("y")) for p in pixels]
    if len(set(coords)) != len(coords):
        ok = False
        findings.append("duplicate coordinates; a grid is a set of distinct cells")
    if set(coords) != {(x, y) for y in range(size) for x in range(size)}:
        ok = False
        findings.append("coordinate set is not the full size x size lattice")

    for p in pixels:
        d = p.get("probabilities")
        if not isinstance(d, list) or len(d) != len(labels):
            ok = False
            findings.append(f"x{p.get('x')}_y{p.get('y')}: wrong arity")
            continue
        if any(not isinstance(v, (int, float)) or isinstance(v, bool)
               or not math.isfinite(v) or v < 0 or v > 1 for v in d):
            ok = False
            findings.append(f"x{p.get('x')}_y{p.get('y')}: non-finite or out of [0,1]")
            continue
        if abs(sum(d) - 1.0) > 1e-9:
            ok = False
            findings.append(
                f"x{p.get('x')}_y{p.get('y')}: sums to {sum(d):.12f}, not 1")

    # Projection 3: any two renderings of the same tensor are diffable.
    if digest(tensor) != digest(json.loads(canonical(tensor))):
        ok = False
        findings.append("tensor is not canonical; it does not round-trip")
    return ok, findings


# -------------------------------------------------------------------- renders
ASCII_RAMP = " .:-=+*#%@"
COLOR_RAMP = ("#10233f", "#153a5b", "#1c5470", "#2a6f7a", "#3f8a72", "#5fa35c",
              "#8ab545", "#b7c02c", "#dedc1a", "#f2c40c", "#f39c12", "#f06013",
              "#e33d3d", "#c92a5b", "#9b2f7f", "#5b2a8f", "#2f2a8f", "#1b1b4d")
ENTROPY_RAMP = " .:-=+*#%@"


def header(view, tensor, extra=""):
    """Every render states which view it is. Unlabeled is the whole problem."""
    n = len(tensor["pixels"])
    mean_h = sum(entropy(p["probabilities"]) for p in tensor["pixels"]) / n if n else 0.0
    lines = [
        "=" * 72,
        f"quilt-jev  view: {view.upper()}",
        f"  projection of tensor  sha256:{digest(tensor)[:16]}",
        f"  prompt  {tensor['prompt'][:60]!r}",
        f"  grid    {tensor['size']}x{tensor['size']} = {n} cells x {len(tensor['labels'])} labels",
        f"  mean entropy {mean_h:.4f} nats   (mean of per-cell Shannon H)",
    ]
    if extra:
        lines.append(f"  {extra}")
    lines.append("=" * 72)
    return "\n".join(lines)


def relief(u, lo=0.48, hi=0.80):
    """The source's contrast stretch on entropy (renderer.mjs: `(spread-0.48)/0.32`).

    JEV over a 16-way palette sits near u ~= 0.75 almost everywhere, so an
    unstretched glyph index saturates to one character. This is a DISCLOSED
    display remap only: it touches rendering, never the tensor, and both ends
    are printed in every header.
    """
    return max(0.0, min(1.0, (u - lo) / (hi - lo)))


def render_paint(tensor, cell_w=2):
    """Background = distribution mean. Glyph = argmax, density = uncertainty.

    This is the source's thesis in a terminal: the full probabilities map is
    used, and entropy becomes physical texture. A confident cell is a solid
    block of its argmax colour; an uncertain one dissolves toward the mean.
    """
    size = tensor["size"]
    out = [header("paint", tensor,
                  "background=mean colour, glyph=argmax colour, "
                  "density=relief(uncertainty) stretched over 0.48..0.80")]
    for y in range(size):
        row = [f"{y:>3} "]
        for x in range(size):
            d = tensor["pixels"][y * size + x]["probabilities"]
            r = relief(uncertainty(d))
            mr, mg, mb = mean_color(d)
            ar, ag, ab = PALETTE[LABELS[argmax(d)]]
            idx = min(len(ENTROPY_RAMP) - 1, int(r * len(ENTROPY_RAMP)))
            glyph = ENTROPY_RAMP[idx]
            # Contrast rises as certainty rises: confident cells are crisp
            # blocks of their argmax colour, contested cells dissolve.
            blend = 1.0 - 0.9 * r
            fr = int(ar * blend + mr * (1 - blend))
            fg = int(ag * blend + mg * (1 - blend))
            fb = int(ab * blend + mb * (1 - blend))
            row.append(f"\x1b[38;2;{fr};{fg};{fb}m\x1b[48;2;{mr};{mg};{mb}m{glyph * cell_w}\x1b[0m")
        out.append("".join(row))
    out.append("    " + "".join(str(x // 10 % 10) if x % 10 == 0 else " " for x in range(size * cell_w)))
    return "\n".join(out) + "\n"


ABBREV = {"black": "Bk", "white": "Wh", "gray": "Gy", "red": "Rd", "orange": "Or",
          "pink": "Pk", "brown": "Br", "tan": "Tn", "green": "Gn", "dark_green": "Dg",
          "blue": "Bu", "sky_blue": "Sb", "yellow": "Ye", "purple": "Pu", "navy": "Nv",
          "cream": "Cr"}


def render_argmax(tensor):
    """The collapse. What every other system in the fleet would ship.

    Each cell is a colour block carrying its label's two-letter abbreviation, so
    the view still says WHAT it decided after the colour is stripped from a pipe.
    """
    size = tensor["size"]
    out = [header("argmax", tensor, "hard argmax per cell; the discarded evidence, shown alone")]
    for y in range(size):
        row = [f"{y:>3} "]
        for x in range(size):
            d = tensor["pixels"][y * size + x]["probabilities"]
            label = LABELS[argmax(d)]
            r, g, b = PALETTE[label]
            row.append(f"\x1b[38;2;0;0;0m\x1b[48;2;{r};{g};{b}m{ABBREV.get(label, '??')}\x1b[0m")
        out.append("".join(row))
    return "\n".join(out) + "\n"


def _ramp_view(tensor, name, value, ramp, note):
    size = tensor["size"]
    vals = [value(p["probabilities"]) for p in tensor["pixels"]]
    lo, hi = min(vals), max(vals)
    out = [header(name, tensor, note + f"  range {lo:.4f}..{hi:.4f}")]
    for y in range(size):
        row = [f"{y:>3} "]
        for x in range(size):
            v = vals[y * size + x]
            t = 0.0 if hi == lo else (v - lo) / (hi - lo)
            row.append(ramp[min(len(ramp) - 1, int(t * len(ramp)))])
        out.append("".join(row))
    return "\n".join(out) + "\n", vals


def render_entropy(tensor):
    text, vals = _ramp_view(tensor, "entropy", uncertainty, ENTROPY_RAMP,
                            "per-cell 1-exp(-H); blank=confident, dense=uncertain")
    return text, vals


def render_margin(tensor):
    text, vals = _ramp_view(tensor, "margin", margin, ENTROPY_RAMP,
                            "per-cell p1-p2; blank=contested, dense=decisive")
    return text, vals


def render_tensor(tensor):
    return header("tensor", tensor, "the canonical artifact, verbatim") + "\n" + \
        json.dumps(tensor, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


RENDERERS = {
    "paint": lambda t: (render_paint(t), None),
    "argmax": lambda t: (render_argmax(t), None),
    "entropy": lambda t: render_entropy(t),
    "margin": lambda t: render_margin(t),
    "tensor": lambda t: (render_tensor(t), None),
}


def jsonl_rows(tensor):
    """The composable output. Another quilt consumes THIS, not the picture."""
    for y in range(tensor["size"]):
        for x in range(tensor["size"]):
            d = tensor["pixels"][y * tensor["size"] + x]["probabilities"]
            i = argmax(d)
            yield {
                "x": x, "y": y,
                "choice": tensor["labels"][i],
                "confidence": d[i],
                "entropy": uncertainty(d),
                "margin": margin(d),
                "probabilities": {lab: d[j] for j, lab in enumerate(tensor["labels"])},
            }


# ----------------------------------------------------------------------- main
def cmd_render(a):
    if a.from_tensor:
        tensor = load_tensor(a.from_tensor)
    else:
        if not a.prompt:
            raise SystemExit("error: a prompt is required unless --from is given")
        key = (os.environ.get("TYPESAFEAI_KEY") or os.environ.get("TYPESAFE_API_KEY")
               or os.environ.get("JEV_API_KEY"))
        if not key:
            raise SystemExit("error: set TYPESAFEAI_KEY (key is never read from a file)")
        print(f"quilt-jev  generating {a.size}x{a.size} tensor "
              f"({(a.size * a.size + BATCH_PIXELS - 1) // BATCH_PIXELS} batch(es))...",
              file=sys.stderr)
        try:
            tensor = generate(a.prompt, a.size, key, progress=not a.quiet)
        except TransportFailure as e:
            # The fleet's signature failure: a failed call must never look like
            # an all-zero grid. No artifact is written. Exit code says transport.
            print(f"TRANSPORT_FAILURE: {e}", file=sys.stderr)
            print("No tensor written. An unreachable endpoint is not an empty picture.",
                  file=sys.stderr)
            return 75          # EX_TEMPFAIL
        except SchemaFailure as e:
            print(f"SCHEMA_FAILURE: {e}", file=sys.stderr)
            print("No tensor written.", file=sys.stderr)
            return 65          # EX_DATAERR

    ok, findings = verify(tensor)
    if not ok:
        for f in findings[:20]:
            print(f"INVARIANT VIOLATION: {f}", file=sys.stderr)
        return 65

    # A projection of an existing tensor must not rewrite it. The tensor is
    # written exactly once, at generation time, and then only read.
    if not a.from_tensor:
        path = a.out or default_path(tensor)
        path = write_tensor_new(tensor, path)
        # Always announced. A tool whose artifact is the whole point must never
        # write a file without saying which file and with what hash.
        print(f"tensor written: {path}  sha256:{digest(tensor)}", file=sys.stderr)

    if a.view == "jsonl":
        for row in jsonl_rows(tensor):
            print(json.dumps(row, sort_keys=True))
    elif a.view == "diff":
        # Two renderings of one tensor, side by side, byte-for-byte labelled.
        ent_text, _ = render_entropy(tensor)
        mar_text, _ = render_margin(tensor)
        left = [l for l in ent_text.splitlines() if not l.startswith("=")]
        right = [l for l in mar_text.splitlines() if not l.startswith("=")]
        out = ["=" * 72,
               f"quilt-jev  view: DIFF  (entropy | margin)",
               f"  same tensor, two projections  sha256:{digest(tensor)[:16]}",
               "=" * 72]
        for l, r in zip(left, right):
            out.append(f"{l[:40]:<40} | {r[:40]}")
        print("\n".join(out))
    else:
        text, _ = RENDERERS[a.view](tensor)
        print(text, end="")
    return 0


def default_path(tensor):
    slug = "".join(c if c.isalnum() else "-" for c in tensor["prompt"].lower())[:32].strip("-")
    return f"jev-{slug or 'grid'}-{tensor['size']}.tensor.json"


def cmd_verify(a):
    tensor = load_tensor(a.tensor)
    ok, findings = verify(tensor)
    print(f"tensor  {a.tensor}\nsha256  {digest(tensor)}")
    print(f"grid    {tensor['size']}x{tensor['size']}  cells={len(tensor['pixels'])}  "
          f"labels={len(tensor['labels'])}")
    for f in findings:
        print(f"  VIOLATION  {f}")
    if not ok:
        print("FAIL")
        return 65
    print("PASS  structural invariant holds")

    # Invariant 3, executed: same tensor -> byte-identical render.
    if not a.no_determinism:
        for view in ("paint", "argmax", "entropy", "margin"):
            first, _ = RENDERERS[view](tensor)
            second, _ = RENDERERS[view](tensor)
            state = "deterministic" if first == second else "NON-DETERMINISTIC"
            print(f"  {state:>15}  view={view}")
            if first != second:
                return 70
        # And a labelled render must name its view.
        text, _ = RENDERERS[a.view](tensor)
        if f"view: {a.view.upper()}" not in text:
            print(f"  UNLABELLED  view={a.view} does not name itself")
            return 70
        print(f"  {'labelled':>15}  view={a.view} names itself in its header")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="quilt-jev",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Render a JEV probability tensor to a terminal.\n\n"
            "THE TENSOR IS THE ARTIFACT. A grid is fetched once, written to disk\n"
            "as canonical JSON, and every view below is a PROJECTION of that file.\n"
            "Views are not pictures of each other; they are readings of one tensor,\n"
            "and each one prints which view it is."),
        epilog=(
            "VIEWS (all projections of the same tensor):\n"
            "  paint    background = distribution mean, glyph = argmax colour,\n"
            "           glyph density = per-cell uncertainty (contrast-stretched\n"
            "           over 0.48..0.80, and every header says so). Uncertainty\n"
            "           becomes texture; it is never averaged away.\n"
            "  argmax   the hard collapse. What a vote-based system would ship.\n"
            "  entropy  per-cell 1-exp(-H). Blank = confident, dense = uncertain.\n"
            "  margin   per-cell p1 - p2. Blank = contested, dense = decisive.\n"
            "  diff     entropy beside margin, one tensor, two projections.\n"
            "  tensor   the canonical artifact, verbatim.\n"
            "  jsonl    one row per cell: {x,y,choice,confidence,entropy,margin,\n"
            "           probabilities}. THE COMPOSABLE OUTPUT -- this is what\n"
            "           another quilt consumes.\n"
            "\n"
            "GRID SIZE is the abstraction dial: " + ", ".join(map(str, SIZES)) +
            " cells per side.\n"
            "  8  =  64 cells,  1 batch   fastest, coarse\n"
            "  12 = 144 cells,  1 batch   default\n"
            "  16 = 256 cells,  2 batches\n"
            "  24 = 576 cells,  4 batches\n"
            "  32 = 1024 cells, 8 batches  finest, most expensive\n"
            "Each batch is 144 questions. Cost scales with the square.\n"
            "\n"
            "EXAMPLES\n"
            "  quilt-jev render 'a red barn on a hill' --size 12\n"
            "  quilt-jev render 'a red barn on a hill' --size 12 --view entropy\n"
            "  quilt-jev render --from barn.tensor.json --view diff\n"
            "  quilt-jev render --from barn.tensor.json --view jsonl | head -2\n"
            "  quilt-jev verify barn.tensor.json\n"))
    p.add_argument("--version", action="version", version="quilt-jev 0.1.0")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="fetch a tensor (or load one) and project it")
    r.add_argument("prompt", nargs="?", help="the image description (max 2000 chars)")
    r.add_argument("--view", default="paint",
                   choices=list(RENDERERS) + ["jsonl", "diff"],
                   help="which projection to print (default: paint)")
    r.add_argument("--size", type=int, default=12, choices=list(SIZES),
                   help="grid size, the abstraction dial: 8|12|16|24|32 (default: 12)")
    r.add_argument("--out", help="tensor path (default: derived from the prompt)")
    r.add_argument("--from", dest="from_tensor",
                   help="project an existing tensor; makes no network call")
    r.add_argument("--quiet", action="store_true", help="suppress per-batch progress")
    r.add_argument("--verbose", action="store_true", help="always print the tensor path")
    r.set_defaults(func=cmd_render)

    v = sub.add_parser("verify", help="run the invariant against a tensor on disk")
    v.add_argument("tensor")
    v.add_argument("--view", default="paint", choices=list(RENDERERS),
                   help="view to check for determinism and self-labelling")
    v.add_argument("--no-determinism", action="store_true",
                   help="structural checks only")
    v.set_defaults(func=cmd_verify)
    return p.parse_args(argv)


if __name__ == "__main__":
    try:
        _args = main()
        sys.exit(_args.func(_args))
    except KeyboardInterrupt:
        sys.exit(130)
    except (TransportFailure, SchemaFailure, ValueError) as exc:
        # A bad input is a refusal with a name, never a traceback and never a
        # blank grid. The kind names the failure class.
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(65)
