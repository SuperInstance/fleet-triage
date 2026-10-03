#!/usr/bin/env python3
"""Aggregate code duplication by REPO PAIR and by FAMILY, to size each case."""
import json, collections, os

CD = json.load(open('/workspace/projects/fleet-triage/code_dups.json'))
NE = json.load(open('/workspace/projects/fleet-triage/neardups.json'))
D = json.load(open('/workspace/projects/fleet-triage/fleet_meta.json'))
by = {x['name']: x for x in D}

pairs = collections.defaultdict(lambda: {'files': 0, 'lines': 0, 'exact': 0, 'near': 0, 'ex': []})
for g in CD['exact']:
    rs = {r for r, _ in g}
    if len(rs) < 2: continue
    rl = sorted(rs)
    for i in range(len(rl)):
        for j in range(i + 1, len(rl)):
            k = tuple(sorted([rl[i], rl[j]]))
            pairs[k]['files'] += 1
            pairs[k]['exact'] += 1
            if len(pairs[k]['ex']) < 4:
                pairs[k]['ex'].append([f'{g[0][0]}/{g[0][1]}', f'{g[1][0]}/{g[1][1]}'])
for j, c, a, b in CD['near']:
    if a[0] == b[0]: continue
    k = tuple(sorted([a[0], b[0]]))
    pairs[k]['files'] += 1
    pairs[k]['near'] += 1

# line counts from cloned trees
def nlines(repo, path):
    p = os.path.join('/workspace/projects/fleet-triage/repos', repo, path)
    try: return sum(1 for _ in open(p, encoding='utf8', errors='replace'))
    except Exception: return 0

ranked = sorted(pairs.items(), key=lambda kv: -kv[1]['files'])
print('=== REPO PAIRS ranked by number of duplicated files ===')
for (a, b), v in ranked[:30]:
    d1 = (by[a]['pushed_at'][:10] if a in by else '?')
    d2 = (by[b]['pushed_at'][:10] if b in by else '?')
    gap = ''
    print(f"\n{a}  <->  {b}")
    print(f"   dup files={v['files']} (exact={v['exact']} near={v['near']})  "
          f"pushed {d1} vs {d2}   lang {by[a]['language']}/{by[b]['language']}")
    for x in v['ex'][:3]: print(f"      e.g. {x[0]}  <->  {x[1]}")

# ---- family-level: group repos by prefix, count intra-family dup files ----
print('\n\n=== INTRA-FAMILY duplication (prefix >=4 chars shared) ===')
fam = collections.defaultdict(lambda: {'repos': set(), 'files': 0, 'pairs': 0})
for (a, b), v in pairs.items():
    ta = a.split('-')[0][:6]; tb = b.split('-')[0][:6]
    pre = ta if ta == tb else None
    if pre and len(pre) >= 4:
        fam[pre]['repos'].update([a, b])
        fam[pre]['files'] += v['files']
        fam[pre]['pairs'] += 1
for p, v in sorted(fam.items(), key=lambda kv: -kv[1]['files'])[:22]:
    print(f"  {p:10s} repos={len(v['repos']):3d} duplicated_files={v['files']:4d} pairs={v['pairs']:3d} "
          f"eg {' '.join(sorted(v['repos'])[:6])}")
json.dump({f'{a}|{b}': v for (a, b), v in ranked}, open('/workspace/projects/fleet-triage/pairs.json', 'w'), indent=1)
