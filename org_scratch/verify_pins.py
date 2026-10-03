import json,os,subprocess
from concurrent.futures import ThreadPoolExecutor,as_completed
heads=json.load(open("all_heads.json"))
pairs=json.load(open("open_target_pairs.json"))
def anc(t,sha):
    d="pinverify/"+t
    if not os.path.isdir(d):
        os.makedirs(d,exist_ok=True)
        subprocess.run(["git","init","-q",d],capture_output=True)
        subprocess.run(["git","-C",d,"remote","add","origin","https://github.com/SuperInstance/%s.git"%t],capture_output=True)
    r=subprocess.run(["git","-C",d,"fetch","-q","--depth=400","origin",
        "refs/heads/%s:refs/remotes/origin/HEADREF"%("main" if "refs/heads/main" in open("lsremote/%s.txt"%t).read() else "master")],capture_output=True,timeout=180)
    if r.returncode!=0: return "FETCHFAIL"
    r=subprocess.run(["git","-C",d,"cat-file","-t",sha],capture_output=True)
    if r.returncode!=0: return "SHA_UNKNOWN"
    r=subprocess.run(["git","-C",d,"merge-base","--is-ancestor",sha,"refs/remotes/origin/HEADREF"],capture_output=True)
    return "ANCESTOR" if r.returncode==0 else "NOT_ANCESTOR"
os.makedirs("pinverify",exist_ok=True)
out={}
with ThreadPoolExecutor(max_workers=6) as ex:
    fs={ex.submit(anc,t,s):(t,s,f) for t,s,f in pairs}
    for fut in as_completed(fs):
        t,s,f=fs[fut]
        try: v=fut.result()
        except Exception as e: v="ERR"
        out["%s|%s|%s"%(t,s,f)]=v
        print(f"  {t:22s} {s[:7]} {v:14s} {f[-50:]}",flush=True)
json.dump(out,open("pin_verification.json","w"),indent=1)
