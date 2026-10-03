#!/usr/bin/env python3
"""Proper near-dup: candidate pairs from a RARE-shingle inverted index, then exact Jaccard."""
import os, re, json, hashlib, collections, itertools, sys

RD = '/workspace/projects/fleet-triage/readmes'
D = json.load(open('/workspace/projects/fleet-triage/fleet_meta.json'))
by = {x['name']: x for x in D}
BADGE = re.compile(r'\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)|!\[[^\]]*\]\([^)]*\)')
LINKTXT = re.compile(r'\[([^\]]*)\]\([^)]*\)')
URL = re.compile(r'https?://\S+')
FENCE = re.compile(r'```.*?```', re.S)
HTML = re.compile(r'<[^>]+>')

def norm(b):
    t = b.decode('utf8', 'replace')
    for rx, rep in ((FENCE, ' '), (BADGE, ' '), (LINKTXT, r'\1'), (URL, ' '), (HTML, ' ')):
        t = rx.sub(rep, t)
    t = re.sub(r'^\s*[|#>*-]{1,6}\s*', ' ', t, flags=re.M)
    return re.sub(r'\s+', ' ', t).strip().lower()

docs = {}
for fn in os.listdir(RD):
    n = fn[:-7]
    if n in by:
        t = norm(open(os.path.join(RD, fn), 'rb').read())
        if len(t) >= 120: docs[n] = t

def shingles(t, k=4):
    w = t.split()
    return {hash(' '.join(w[i:i+k])) for i in range(max(1, len(w)-k+1))}

sh = {n: shingles(t) for n, t in docs.items()}
inv = collections.defaultdict(list)
for n, s in sh.items():
    for x in s: inv[x].append(n)
print('docs', len(docs), 'shingles', len(inv))

# candidate pairs via shared RARE shingles (df<=25)
co = collections.Counter()
for x, ns in inv.items():
    if 1 < len(ns) <= 25:
        for a, b in itertools.combinations(ns, 2): co[(a, b)] += 1
print('candidate pairs', len(co))

def jac(a, b):
    A, B = sh[a], sh[b]
    return len(A & B) / max(1, len(A | B))

THR = float(sys.argv[1]) if len(sys.argv) > 1 else 0.40
pairs = sorted(((jac(a, b), a, b) for (a, b), c in co.items() if c >= 8), reverse=True)
pairs = [p for p in pairs if p[0] >= THR]
print('pairs >=', THR, len(pairs))

par = {n: n for n in docs}
def f(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
for j, a, b in pairs:
    ra, rb = f(a), f(b)
    if ra != rb: par[ra] = rb
comp = collections.defaultdict(list)
for n in docs: comp[f(n)].append(n)
dd = sorted([c for c in comp.values() if len(c) > 1], key=len, reverse=True)
print(f'\n=== NEAR-DUP clusters (j>={THR}): {len(dd)} covering {sum(len(c) for c in dd)} ===')
out = []
for c in dd:
    c = sorted(c)
    best = max((p for p in pairs if p[1] in c and p[2] in c), default=(0,'',''))
    langs = collections.Counter(by[x]['language'] for x in c)
    dates = sorted(by[x]['pushed_at'][:10] for x in c)
    nonfork = sum(1 for x in c if not by[x]['fork'])
    print(f'\n[{len(c):3d}] nonfork={nonfork} langs={dict(langs)} dates={dates[0]}..{dates[-1]} maxjac={best[0]:.2f}')
    print('   ', ' '.join(c[:26]) + (' …' if len(c) > 26 else ''))
    out.append({'members': c, 'langs': dict(langs), 'dates': [dates[0], dates[-1]],
                'max_jaccard': round(best[0], 3), 'nonfork': nonfork})
json.dump(out, open('/workspace/projects/fleet-triage/neardups.json', 'w'), indent=1)
