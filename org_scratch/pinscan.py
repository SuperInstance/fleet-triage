import os,re,json,subprocess
from concurrent.futures import ThreadPoolExecutor
D="lsremote"
PIN=re.compile(r'SuperInstance/([A-Za-z0-9._-]+)')
SHA=re.compile(r'\b([0-9a-f]{7,40})\b')
active=[]
for fn in os.listdir(D):
    repo=fn[:-4]
    t=open(os.path.join(D,fn)).read()
    if 'refs/heads/main' in t or 'refs/heads/master' in t:
        active.append(repo)
print("scanning",len(active),"repos for cross-repo citations",flush=True)
# Only scan the repos that participate in the quilt lineage + recently pushed.
meta={r["name"]:r for r in json.load(open("/workspace/projects/fleet-triage/fleet_meta.json"))}
targets=[r for r in active if meta.get(r,{}).get("pushed_at","") >= "2026-09-25"]
print("recently pushed (<=2026-09-25):",len(targets),flush=True)
json.dump(sorted(targets),open("targets.json","w"))
