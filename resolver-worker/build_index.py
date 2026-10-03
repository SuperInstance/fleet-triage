#!/usr/bin/env python3
"""Regenerate the edge index asset for resolver-worker.

Source of truth : /workspace/.resolver-state/repo_index.json
                   /workspace/.resolver-state/fleet_census.json
Output          : index.asset.b64   (gzip -> base64, embedded in index_asset.js)

The Worker holds PATHS ONLY, deliberately: 85,990 paths across 477 repos compress
to 0.91 MB gzip (944 KiB on the wire). It cannot adjudicate LINE_OOR or
SYMBOL_MISMATCH because it has no file contents, and it says so in every response
rather than guessing. That trade is the reason stage 1 is the only stage shipped
at full strength.
"""
import json, gzip, base64, os

SRC_IDX = "/workspace/.resolver-state/repo_index.json"
SRC_CEN = "/workspace/.resolver-state/fleet_census.json"
OUT_B64 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.asset.b64")
OUT_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker", "index_asset.js")

idx = json.load(open(SRC_IDX))
cens = json.load(open(SRC_CEN))

repos, basenames, dirs = {}, {}, {}
nfiles = 0
for name, inf in sorted(idx.items()):
    key = name.lower()
    files = sorted(p for p in inf.get("files", []) if p)
    if not files:
        continue
    repos[key] = files
    nfiles += len(files)
    ds = set()
    for f in files:
        basenames.setdefault(f.rsplit("/", 1)[-1], []).append(key)
        d = f.rsplit("/", 1)[0] if "/" in f else ""
        if d:
            ds.add(d)
    dirs[key] = sorted(ds)

for b in basenames.values():
    b[:] = sorted(set(b))

blob = {
    "v": 1,
    "repos": repos,
    "basenames": basenames,
    "dirs": dirs,
    "census": sorted(cens.keys()),
}
raw = json.dumps(blob, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
gz = gzip.compress(raw, 9)
b64 = base64.b64encode(gz).decode("ascii")
open(OUT_B64, "w").write(b64)

if os.path.isdir(os.path.dirname(OUT_JS)):
    with open(OUT_JS, "w") as fh:
        fh.write("// Generated from %s — %d repos / %d files.\n" % (SRC_IDX, len(repos), nfiles))
        fh.write("// Deploy-time artifact only. Not a secret.\n")
        fh.write('export const INDEX_B64 = "%s";\n' % b64)

print(f"repos={len(repos)} files={nfiles} basenames={len(basenames)} census={len(cens)}")
print(f"raw={len(raw)/1048576:.2f}MB gzip={len(gz)/1048576:.2f}MB base64={len(b64)/1048576:.2f}MB")
print(f"wrote {OUT_B64}")
if os.path.isdir(os.path.dirname(OUT_JS)):
    print(f"wrote {OUT_JS}")
