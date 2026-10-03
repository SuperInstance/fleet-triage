import os,json,re,subprocess,tarfile,io,resource
from concurrent.futures import ThreadPoolExecutor, as_completed
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
todo=json.load(open("still_missing.json"))
CITE=re.compile(rb'SuperInstance/([A-Za-z0-9._-]+)')
SKIP=re.compile(rb'(node_modules/|\.git/|package-lock\.json|/dist/|\.venv/|/data/|\.png$|\.jpg$|\.mp4$|\.jsonl$)')
MAXU=80_000_000
def scan(repo):
    ref = "main" if "refs/heads/main" in open("lsremote/%s.txt"%repo).read() else "master"
    try:
        # stream with a hard byte cap; large repos are recorded as skipped, not failed
        p=subprocess.Popen(["curl","-sL","-m","90","https://codeload.github.com/SuperInstance/%s/tar.gz/refs/heads/%s"%(repo,ref)],
                           stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        buf=io.BytesIO(); tot=0
        while True:
            c=p.stdout.read(1<<20)
            if not c: break
            tot+=len(c)
            if tot>MAXU: p.kill(); break
            buf.write(c)
        p.wait()
        data=buf.getvalue()
        if len(data)<50:
            json.dump({"repo":repo,"skipped":"too_large" if tot>MAXU else "empty"},open("pins/"+repo+".json","w")); return repo,"skip"
        tf=tarfile.open(fileobj=io.BytesIO(data),mode="r:gz")
        cites={};nfile=0;nbytes=0;acc=0
        for m in tf:
            if not m.isfile() or m.size>2_000_000: continue
            acc+=m.size
            if acc>MAXU: break
            if SKIP.search(m.name.encode()): continue
            try: d=tf.extractfile(m).read()
            except Exception: continue
            nfile+=1;nbytes+=len(d)
            for c in set(CITE.findall(d)):
                cs=c.decode()
                if cs!=repo: cites.setdefault(cs,set()).add(m.name)
        json.dump({"repo":repo,"files":nfile,"bytes":nbytes,"cites":{k:sorted(v)[:3] for k,v in cites.items()}},open("pins/"+repo+".json","w"))
        return repo,"ok"
    except Exception as e: return repo,"ERR:%s"%type(e).__name__
d=0;e=[]
with ThreadPoolExecutor(max_workers=8) as ex:
    fs={ex.submit(scan,r):r for r in todo}
    for f in as_completed(fs):
        repo,st=f.result(); d+=1
        if st.startswith("ERR"): e.append((repo,st))
        if d%40==0: print(d,"errs",len(e),flush=True)
print("DONE",d,"errs",len(e),e[:20],flush=True)
