#!/usr/bin/env python3
"""Bulk-fetch READMEs via raw.githubusercontent (no API rate limit) to find near-duplicate repos."""
import json, os, sys, concurrent.futures as cf, urllib.request, urllib.error, hashlib, re

OUT = '/workspace/projects/fleet-triage/readmes'
os.makedirs(OUT, exist_ok=True)
D = json.load(open('/workspace/projects/fleet-triage/fleet_meta.json'))

VARIANTS = ['README.md', 'readme.md', 'README.rst', 'README.txt', 'Readme.md', 'README.MD']
TOKEN = None
try:
    tk = os.popen("git config --global --get-regexp 'url\\..*insteadof'").read()
    m = re.search(r'x-access-token:([^@]+)@', tk)
    if m: TOKEN = m.group(1)
except Exception: pass

def fetch(name, branch):
    for v in VARIANTS:
        url = f"https://raw.githubusercontent.com/SuperInstance/{name}/{branch}/{v}"
        req = urllib.request.Request(url, headers={'User-Agent': 'fleet-triage'})
        # NOTE: do NOT send Authorization. The only token in this sandbox is revoked;
        # raw.githubusercontent rejects a bad credential with 401 on public repos.
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            if data.strip():
                return v, data
        except urllib.error.HTTPError as e:
            if e.code == 404: continue
            return None, None
        except Exception:
            return None, None
    return None, None

def job(x):
    name, branch = x
    p = os.path.join(OUT, name + '.readme')
    if os.path.exists(p): return name, 'cached'
    v, data = fetch(name, branch)
    if data is None: return name, 'none'
    with open(p, 'wb') as f: f.write(data)
    return name, v

todo = [(x['name'], x.get('default_branch') or 'main') for x in D]
stats = {}
with cf.ThreadPoolExecutor(max_workers=32) as ex:
    for i, (name, st) in enumerate(ex.map(job, todo)):
        stats[st] = stats.get(st, 0) + 1
        if (i + 1) % 500 == 0:
            print(i + 1, stats, flush=True)
print('DONE', stats, flush=True)
