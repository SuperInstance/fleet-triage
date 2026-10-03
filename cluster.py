#!/usr/bin/env python3
"""Cluster the SuperInstance fleet by WHAT IT DOES (description + topics), not by name.
Names in this fleet are unreliable and often poetic; descriptions are the signal.
"""
import json, re, collections, itertools, math, sys

D = json.load(open('/workspace/projects/fleet-triage/fleet_meta.json'))
by = {x['name']: x for x in D}

# ---- hygiene: drop forks + the known recovered-copy pollution ----
def is_pollution(n):
    if n.startswith('recovered-copy-'): return True
    if by[n].get('fork'): return True
    return False

live = [x for x in D if not is_pollution(x['name'])]
print(f"total={len(D)} live_nonfork={len(live)}", file=sys.stderr)

STOP = set("""a an the and or of for to in on with by is are be it its this that from as at
into using use used build builds building built new not no via more than then also can will
project repo repository code source simple small fast high low real time first second
""".split())

def toks(x):
    s = (x.get('description') or '') + ' ' + ' '.join(x.get('topics') or [])
    s = s.lower()
    s = re.sub(r'[^a-z0-9+#.\- ]', ' ', s)
    out = []
    for t in s.split():
        t = t.strip('-.')
        for p in t.split('-'):
            if len(p) > 2 and p not in STOP and not p.isdigit():
                out.append(p)
    return out

docs = {x['name']: toks(x) for x in live}
df = collections.Counter()
for n, t in docs.items():
    df.update(set(t))
N = len(docs)
idf = {w: math.log(N / (1 + c)) for w, c in df.items()}
vec = {n: collections.Counter({w: (1 + math.log(tf)) * idf[w] for w, tf in collections.Counter(t).items()}) for n, t in docs.items()}
norm = {n: math.sqrt(sum(v * v for v in vv.values())) or 1 for n, vv in vec.items()}

# inverted index
inv = collections.defaultdict(list)
for n, vv in vec.items():
    for w in vv:
        inv[w].append(n)

def sim(a, b):
    va, vb = vec[a], vec[b]
    if len(va) > len(vb): va, vb = vb, va
    return sum(v * vb.get(w, 0) for w, v in va.items()) / (norm[a] * norm[b])

# ---- connected components over description-similarity, strong threshold only ----
THRESH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.42
parent = {n: n for n in docs}
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb

edges = []
for w, ns in inv.items():
    if len(ns) > 400: continue
    if len(ns) < 2: continue
    for a, b in itertools.combinations(ns, 2):
        s = sim(a, b)
        if s >= THRESH:
            union(a, b)
            edges.append((s, a, b))

comps = collections.defaultdict(list)
for n in docs: comps[find(n)].append(n)
clusters = [c for c in comps.values() if len(c) >= 3]
clusters.sort(key=len, reverse=True)
print(f"threshold={THRESH} components>=3: {len(clusters)}  covered={sum(len(c) for c in clusters)}", file=sys.stderr)

out = []
for c in clusters[:80]:
    c = sorted(c)
    wc = collections.Counter(w for n in c for w in docs[n])
    out.append({'size': len(c), 'members': c,
                'key_tops': [w for w, _ in wc.most_common(14)],
                'langs': collections.Counter(by[n]['language'] for n in c).most_common(4),
                'date_range': (min(by[n]['pushed_at'] for n in c)[:10], max(by[n]['pushed_at'] for n in c)[:10])})
json.dump(out, open('/workspace/projects/fleet-triage/clusters.json', 'w'), indent=1)
for c in out:
    print(f"[{c['size']:4d}] {','.join(c['key_tops'][:9])}")
    print(f"        {' '.join(c['members'][:14])}{' …' if c['size']>14 else ''}")
