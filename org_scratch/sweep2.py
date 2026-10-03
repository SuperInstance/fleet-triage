import os,subprocess,json
from concurrent.futures import ThreadPoolExecutor
D="lsremote"
empty=[fn[:-4] for fn in os.listdir(D) if not open(os.path.join(D,fn)).read().strip()]
print("re-probing",len(empty),"master-branch candidates",flush=True)
def probe(repo):
    url="https://github.com/SuperInstance/%s.git"%repo
    try:
        r=subprocess.run(["git","ls-remote","--refs",url,"refs/pull/*/merge","refs/heads/master","refs/heads/main"],capture_output=True,timeout=45)
        open(os.path.join(D,repo+".txt"),"w").write(r.stdout.decode("utf-8","replace"))
        return repo,"ok" if r.returncode==0 else "ERR"
    except Exception: return repo,"TIMEOUT"
d=0;e=[]
with ThreadPoolExecutor(max_workers=24) as ex:
    for repo,st in ex.map(probe,empty):
        d+=1
        if st!="ok": e.append((repo,st))
        if d%500==0: print(d,"errs",len(e),flush=True)
print("DONE",d,"errs",len(e),e[:20],flush=True)
