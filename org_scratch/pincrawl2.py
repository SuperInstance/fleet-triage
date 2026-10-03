import os,json,re,subprocess,tarfile,io,sys,resource
from concurrent.futures import ThreadPoolExecutor, as_completed
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
targets=[t for t in json.load(open("targets.json")) if not os.path.exists("pins/"+t+".json")]
print("resuming",len(targets),flush=True)
CITE=re.compile(rb'SuperInstance/([A-Za-z0-9._-]+)')
SKIP=re.compile(rb'(node_modules/|\.git/|package-lock\.json|/dist/|\.venv/|/data/|\.png$|\.jpg$|\.mp4$)')
MAXTOT=60_000_000
def scan(repo):
    try:
        r=subprocess.run(["curl","-sL","-m","45","--max-filesize","%d"%MAXTOT,
            "https://codeload.github.com/SuperInstance/%s/tar.gz/refs/heads/main"%repo],capture_output=True)
        if len(r.stdout)<50: return repo,"empty"
        tf=tarfile.open(fileobj=io.BytesIO(r.stdout),mode="r:gz")
        cites={};nfile=0;nbytes=0;tot=0
        for m in tf:
            if not m.isfile() or m.size>2_000_000: continue
            tot+=m.size
            if tot>MAXTOT: break
            if SKIP.search(m.name.encode()): continue
            try: data=tf.extractfile(m).read()
            except Exception: continue
            nfile+=1;nbytes+=len(data)
            for c in set(CITE.findall(data)):
                cs=c.decode()
                if cs!=repo: cites.setdefault(cs,set()).add(m.name)
        json.dump({"repo":repo,"files":nfile,"bytes":nbytes,"truncated":tot>MAXTOT,
                   "cites":{k:sorted(v)[:3] for k,v in cites.items()}},open("pins/"+repo+".json","w"))
        return repo,"ok"
    except Exception as e: return repo,"ERR:%s"%type(e).__name__
d=0;e=[]
with ThreadPoolExecutor(max_workers=8) as ex:
    futs={ex.submit(scan,r):r for r in targets}
    for f in as_completed(futs):
        repo,st=f.result(); d+=1
        if st!="ok": e.append((repo,st))
        if d%40==0: print(d,"issues",len(e),flush=True)
print("DONE",d,"issues",len(e),e[:20],flush=True)
