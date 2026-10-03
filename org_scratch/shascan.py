import os,json,re,subprocess,tarfile,io,resource
from concurrent.futures import ThreadPoolExecutor,as_completed
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
todo=json.load(open("targets.json"))
# A PIN = citation + a commit sha within 400 chars. Mentions have no sha.
CITE=re.compile(rb'SuperInstance/([A-Za-z0-9._-]+)')
SHA=re.compile(rb'\b([0-9a-f]{7,40})\b')
SKIP=re.compile(rb'(node_modules/|\.git/|package-lock\.json|/dist/|\.venv/|/data/|\.png$|\.jpg$|\.mp4$|\.jsonl$)')
MAXU=80_000_000
def scan(repo):
    ref="main" if "refs/heads/main" in open("lsremote/%s.txt"%repo).read() else "master"
    try:
        p=subprocess.Popen(["curl","-sL","-m","90","https://codeload.github.com/SuperInstance/%s/tar.gz/refs/heads/%s"%(repo,ref)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        buf=io.BytesIO();tot=0
        while True:
            c=p.stdout.read(1<<20)
            if not c: break
            tot+=len(c)
            if tot>MAXU: p.kill();break
            buf.write(c)
        p.wait()
        if len(buf.getvalue())<50: return repo,"skip"
        tf=tarfile.open(fileobj=io.BytesIO(buf.getvalue()),mode="r:gz")
        pins=[]
        for m in tf:
            if not m.isfile() or m.size>2_000_000: continue
            if SKIP.search(m.name.encode()): continue
            try: d=tf.extractfile(m).read()
            except Exception: continue
            for cm in CITE.finditer(d):
                tgt=cm.group(1).decode()
                if tgt==repo: continue
                w=d[max(0,cm.start()-400):cm.start()+400]
                for s in set(x.decode() for x in SHA.findall(w)):
                    pins.append({"target":tgt,"sha":s,"file":m.name})
        json.dump(pins,open("shapins/%s.json"%repo,"w")); return repo,"ok"
    except Exception as e: return repo,"ERR:%s"%type(e).__name__
os.makedirs("shapins",exist_ok=True)
d=0;e=[]
with ThreadPoolExecutor(max_workers=8) as ex:
    fs={ex.submit(scan,r):r for r in todo if not os.path.exists("shapins/%s.json"%r)}
    for f in as_completed(fs):
        r,st=f.result();d+=1
        if st.startswith("ERR"): e.append((r,st))
        if d%50==0: print(d,"errs",len(e),flush=True)
print("DONE",d,"errs",len(e),e[:10],flush=True)
