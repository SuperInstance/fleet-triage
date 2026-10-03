#!/usr/bin/env python3
"""Cross-repo CODE duplication over the cloned working trees.
Reports exact-duplicate and near-duplicate FILES with concrete repo:path evidence."""
import os, re, sys, json, hashlib, collections, itertools

REPOS = '/workspace/projects/fleet-triage/repos'
SKIP_DIR = re.compile(r'(^|/)(\.git|node_modules|target|vendor|third_party|\.venv|venv|site-packages|dist|build|__pycache__|\.wrangler|coverage)(/|$)')
SKIP_EXT = re.compile(r'\.(min\.js|min\.css|map|d\.ts|lock|png|jpg|jpeg|gif|svg|ico|woff2?|pdf|zip|gz|tar|mp4|mp3|wasm|so|dylib|dll|exe|class|jar|bin|db|sqlite|parquet|arrow|ipynb|lock|sum)$', re.I)
CODE_EXT = {'.py','.rs','.js','.ts','.tsx','.jsx','.go','.c','.h','.cpp','.hpp','.cc','.java','.cs',
            '.sh','.rb','.jl','.f90','.mojo','.chpl','.cob','.m','.scala','.swift','.kt','.lua','.html'}

def files(repo):
    base = os.path.join(REPOS, repo)
    for dp, dn, fn in os.walk(base):
        rel = os.path.relpath(dp, base)
        if SKIP_DIR.search('/' + rel.replace(os.sep, '/')): continue
        for f in fn:
            if SKIP_EXT.search(f): continue
            yield os.path.join(rel, f) if rel != '.' else f

def strip_py(src):
    """Remove comments + docstrings + blank lines so that 'same code, different prose' is caught."""
    out, in_s, q = [], False, None
    for line in src.split('\n'):
        s = line.strip()
        if in_s:
            if q in s: in_s = False
            continue
        if s.startswith(('"""', "'''")):
            q = s[:3]
            if not (len(s) > 3 and s[3:].endswith(q)): in_s = True
            continue
        # strip trailing comments outside strings (crude but adequate)
        t = re.sub(r'(?<![:\w])#.*$', '', line)
        t = re.sub(r'//.*$', '', t)
        t = t.strip()
        if t: out.append(t)
    return '\n'.join(out)

def strip_gen(src):
    t = re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)
    t = re.sub(r'(?m)//.*$', ' ', t)
    return '\n'.join(l.strip() for l in t.split('\n') if l.strip())

def norm(path, src):
    if path.endswith(('.py','.sh','.rb','.jl')): return strip_py(src)
    if path.endswith(('.rs','.js','.ts','.tsx','.go','.c','.h','.cpp','.java','.cs','.m','.f90','.mojo','.chpl')):
        return strip_gen(src)
    return '\n'.join(l.strip() for l in src.split('\n') if l.strip())

store = {}   # (repo, path) -> (norm_text, nlines, lang)
exact = collections.defaultdict(list)   # hash -> [(repo,path)]
bysize = collections.defaultdict(list)
for repo in sorted(os.listdir(REPOS)):
    for rel in files(repo):
        if not os.path.splitext(rel)[1] in CODE_EXT: continue
        p = os.path.join(REPOS, repo, rel)
        try: src = open(p, encoding='utf8', errors='replace').read()
        except Exception: continue
        if len(src) < 200: continue
        n = norm(rel, src)
        if len(n) < 150: continue
        key = (repo, rel)
        store[key] = (n, n.count('\n') + 1)
        h = hashlib.sha1(re.sub(r'\s+', '', n).encode()).hexdigest()
        exact[h].append(key)
        bysize[len(n)].append(key)

print('code files indexed:', len(store), file=sys.stderr)

# ---- exact cross-repo duplicate files ----
dups = [g for g in exact.values() if len({r for r, _ in g}) > 1]
dups.sort(key=len, reverse=True)
print(f'\n=== EXACT cross-repo duplicate files (>=2 different repos): {len(dups)} groups, '
      f'{sum(len(g) for g in dups)} files ===')
for g in dups[:40]:
    rl = store[g[0]][1]
    print(f'  [{len({r for r,_ in g})} repos x {len(g)} files, ~{rl} lines] {g[0][1][:52]}')
    for r, p in g[:8]: print(f'        {r}/{p}')

# ---- near-duplicate: same line-count bucket, cheap shingle containment ----
inv = collections.defaultdict(list)
for key, (n, nl) in store.items():
    if nl < 12: continue
    w = n.split('\n')
    for i in range(0, max(1, len(w) - 7), 8):
        inv[hash('\n'.join(w[i:i+8]))].append(key)
co = collections.Counter()
for s, ks in inv.items():
    if 1 < len(ks) <= 12:
        for a, b in itertools.combinations(ks, 2):
            if a[0] != b[0]: co[(a, b)] += 1
print('\nnear-dup candidate pairs:', len(co), file=sys.stderr)

def jac(a, b):
    A = set(store[a][0].split('\n')); B = set(store[b][0].split('\n'))
    return len(A & B) / max(1, len(A | B))

scored = []
for (a, b), c in co.items():
    if c < 12: continue
    j = jac(a, b)
    if j >= 0.70: scored.append((round(j, 3), c, a, b))
scored.sort(reverse=True)
print(f'\n=== NEAR-DUPLICATE cross-repo file pairs (jaccard>=0.70): {len(scored)} ===')
for j, c, a, b in scored[:60]:
    print(f'  j={j:.2f} shared_blocks={c:3d}  {a[0]}/{a[1][:46]}  <->  {b[0]}/{b[1][:46]}  ({store[a][1]}/{store[b][1]} lines)')

json.dump({'exact': [[list(x) for x in g] for g in dups],
           'near': [[s[0], s[1], list(s[2]), list(s[3])] for s in scored[:4000]]},
          open('/workspace/projects/fleet-triage/code_dups.json', 'w'), indent=1)
