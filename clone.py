#!/usr/bin/env python3
"""Parallel shallow clone of SuperInstance repos. Public repos, no auth needed."""
import os, sys, subprocess, concurrent.futures as cf, json

DEST = '/workspace/projects/fleet-triage/repos'
os.makedirs(DEST, exist_ok=True)

def clone(name):
    p = os.path.join(DEST, name)
    if os.path.isdir(os.path.join(p, '.git')): return name, 'cached'
    env = dict(os.environ, GIT_SSL_NO_VERIFY='1', GIT_TERMINAL_PROMPT='0')
    try:
        r = subprocess.run(['git', 'clone', '--depth', '1', '--quiet',
                            f'https://github.com/SuperInstance/{name}.git', p],
                           capture_output=True, timeout=90, env=env)
    except subprocess.TimeoutExpired:
        subprocess.run(['rm', '-rf', p], capture_output=True)
        return name, 'TIMEOUT'
    if r.returncode != 0:
        return name, 'FAIL:' + r.stderr.decode()[:120].strip()
    return name, 'ok'

names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
st = {}
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    for i, (n, s) in enumerate(ex.map(clone, names)):
        k = 'ok' if s in ('ok', 'cached') else 'FAIL'
        st[k] = st.get(k, 0) + 1
        if s.startswith('FAIL'): print('  FAIL', n, s, flush=True)
        if (i + 1) % 10 == 0: print(i + 1, st, flush=True)
print('DONE', st, flush=True)
