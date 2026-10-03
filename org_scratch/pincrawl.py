import os,json,re,subprocess,tarfile,io,sys
from concurrent.futures import ThreadPoolExecutor
targets=json.load(open("targets.json"))
OUT="pins"; os.makedirs(OUT,exist_ok=True)
CITE=re.compile(rb'SuperInstance/([A-Za-z0-9._-]+)')
SHA=re.compile(rb'\b([0-9a-f]{7,40})\b')
SKIP=re.compile(rb'(node_modules/|\.git/|package-lock\.json|dist/|\.venv/)')
def scan(repo):
    p=os.path.join(OUT,repo+".json")
    if os.path.exists(p): return repo,"cached"
    url="https://codeload.github.com/SuperInstance/%s/tar.gz/refs/heads/main"%repo
    try:
        r=subprocess.run(["curl","-sL","-m","60",url],capture_output=True)
        if r.returncode!=0 or len(r.stdout)<50: return repo,"empty"
        tf=tarfile.open(fileobj=io.BytesIO(r.stdout),mode="r:gz")
        cites={}; nfile=0; nbytes=0
        for m in tf.getmembers():
            if not m.isfile() or m.size>3_000_000: continue
            if SKIP.search(m.name.encode()): continue
            try: data=tf.extractfile(m).read()
            except Exception: continue
            nfile+=1; nbytes+=len(data)
            for c in set(CITE.findall(data)):
                cs=c.decode()
                if cs!=repo: cites.setdefault(cs,set()).add(m.name)
        json.dump({"repo":repo,"files":nfile,"bytes":nbytes,"cites":{k:sorted(v)[:3] for k,v in cites.items()}},open(p,"w"))
        return repo,"ok"
    except Exception as e:
        return repo,"ERR:%s"%type(e).__name__
d=0;e=[]
with ThreadPoolExecutor(max_workers=12) as ex:
    for repo,st in ex.map(scan,targets):
        d+=1
        if st.startswith("ERR") or st=="empty": e.append((repo,st))
        if d%50==0: print(d,"issues",len(e),flush=True)
print("DONE",d,"issues",len(e),e[:15],flush=True)
