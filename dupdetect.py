#!/usr/bin/env python3
"""Near-duplicate detection over 4,835 READMEs. Strips badges/URLs/code-fences so that
'one project with fifty names' surfaces as identical fingerprints, not as diffs."""
import os, re, json, hashlib, collections, itertools

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
    t = FENCE.sub(' ', t)
    t = BADGE.sub(' ', t)
    t = LINKTXT.sub(r'\1', t)
    t = URL.sub(' ', t)
    t = HTML.sub(' ', t)
    t = re.sub(r'^\s*[|#>*-]{1,6}\s*', ' ', t, flags=re.M)
    t = re.sub(r'\s+', ' ', t).strip().lower()
    return t

docs = {}
for fn in os.listdir(RD):
    n = fn[:-7]
    if n not in by: continue
    raw = open(os.path.join(RD, fn), 'rb').read()
    t = norm(raw)
    if len(t) < 120: continue
    docs[n] = t
print('docs', len(docs))

# --- 1. exact fingerprint (normalized) -> strongest possible signal ---
fp = collections.defaultdict(list)
for n, t in docs.items():
    fp[hashlib.sha1(t.encode()).hexdigest()].append(n)
exact = [g for g in fp.values() if len(g) > 1]
exact.sort(key=len, reverse=True)
print('\n=== EXACT normalized-README duplicate groups:', len(exact),
      'covering', sum(len(g) for g in exact), 'repos ===')
for g in exact[:45]:
    print(f'  [{len(g):3d}] {" ".join(sorted(g)[:9])}{" …" if len(g) > 9 else ""}')

# --- 2. shingle Jaccard via LSH on 5-gram hashes ---
def shingles(t, k=5):
    w = t.split()
    return {hash(' '.join(w[i:i+k])) for i in range(max(1, len(w) - k + 1))}

sh = {n: shingles(t) for n, t in docs.items()}
M = 24
sig = {}
for n, s in sh.items():
    h = [0] * M
    for x in s:
        for b in range(M):
            h[b] |= hash((x, b))
    sig[n] = h

buckets = collections.defaultdict(list)
for n, h in sig.items():
    for b in range(0, M, 6):
        buckets[(b, h[b] >> 20)].append(n)

cand = set()
for bk, ns in buckets.items():
    if 1 < len(ns) <= 60:
        for a, b in itertools.combinations(ns, 2): cand.add((a, b))
print('\ncandidate pairs from LSH:', len(cand))

def jac(a, b):
    A, B = sh[a], sh[b]
    return len(A & B) / max(1, len(A | B))

pairs = []
for a, b in cand:
    j = jac(a, b)
    if j >= 0.55: pairs.append((j, a, b))
pairs.sort(reverse=True)
print('pairs with jaccard>=0.55:', len(pairs))

# group into clusters
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
print('\n=== NEAR-DUPLICATE clusters (jaccard>=0.55):', len(dd), 'covering', sum(len(c) for c in dd), '===')
out = []
for c in dd:
    c = sorted(c)
    best = max((p for p in pairs if p[1] in c and p[2] in c), default=(0, '', ''))
    langs = collections.Counter(by[x]['language'] for x in c)
    dates = sorted(by[x]['pushed_at'][:10] for x in c)
    print(f'\n[{len(c):3d}] langs={dict(langs)} dates={dates[0]}..{dates[-1]} maxjac={best[0]:.2f}')
    print('   ', ' '.join(c[:20]) + (' …' if len(c) > 20 else ''))
    out.append({'members': c, 'langs': dict(langs), 'dates': [dates[0], dates[-1]],
                'max_jaccard': best[0]})
json.dump({'exact_groups': exact, 'near_dup_clusters': out},
          open('/workspace/projects/fleet-triage/dups.json', 'w'), indent=1)
