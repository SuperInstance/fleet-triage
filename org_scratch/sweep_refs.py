import json, subprocess, os, sys
from concurrent.futures import ThreadPoolExecutor
BASE="/workspace/projects/fleet-triage"
OUT=BASE+"/org_scratch/lsremote"
repos=[r["name"] for r in json.load(open(BASE+"/fleet_meta.json"))]
repos=sorted(set(repos))
print("repos:",len(repos),flush=True)
def probe(name):
    p=os.path.join(OUT,name+".txt")
    if os.path.exists(p) and os.path.getsize(p)>0: return name,"cached"
    url="https://github.com/SuperInstance/%s.git"%name
    try:
        r=subprocess.run(["git","ls-remote","--refs",url,"refs/pull/*/merge","refs/heads/main"],
                         capture_output=True,timeout=45)
        open(p,"w").write(r.stdout.decode("utf-8","replace"))
        if r.returncode!=0: return name,"ERR"
        return name,"ok"
    except Exception as e:
        open(p,"w").write("")
        return name,"TIMEOUT"
done=0; errs=[]
with ThreadPoolExecutor(max_workers=24) as ex:
    for name,st in ex.map(probe,repos):
        done+=1
        if st!="ok": errs.append((name,st))
        if done%500==0: print(done,"errs",len(errs),flush=True)
print("DONE",done,"errs",len(errs),flush=True)
json.dump(errs,open(BASE+"/org_scratch/lsremote_errors.json","w"),indent=1)
