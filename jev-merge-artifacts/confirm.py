import json,statistics
from concurrent.futures import ThreadPoolExecutor
exec(open('jevmerge2.py').read().split('def main()')[0].split('pr32 =')[0])  # imports, KEY, call, parse
KEY="apikey_2217d2c797da8a2d48d887bd713a67e1f235_e376d8a7b61fe16caf5645c0e53de638c87580d1bec9695f5edd0b1098728599"
URL="https://api.typesafe.ai/v1/systemone"
import urllib.request,urllib.error,time,random
CRIT={"correct":"The claim below is factually correct: it matches the evidence.",
 "incorrect":"The claim below is factually wrong: the evidence contradicts it.",
 "insufficient":"The evidence provided does not settle the claim either way."}
MEAN={"correct":"correct","incorrect":"incorrect","insufficient":"insufficient"}
INSTR=("Adjudicate the claim against the evidence. Answer 'correct' if the evidence supports it, "
 "'incorrect' if the evidence contradicts it, and 'insufficient' if the evidence does not settle it.")
def call(state,qspec,tries=4):
    body={"model":"jev-1.13.0","state":state,"questions":{"q":qspec}}
    req=urllib.request.Request(URL,data=json.dumps(body).encode(),method="POST",
      headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"})
    for a in range(tries):
        try:
            with urllib.request.urlopen(req,timeout=50) as r: return json.loads(r.read() or b"{}")
        except Exception:
            if a<tries-1: time.sleep(.4); continue
            return {"error":"t"}
def run(t):
    cid,tag,state,instr,kind=t
    if kind=="noul":
        r=call(state,{"type":"noul","instructions":instr});a=(r.get("answers") or {}).get("q")
        p=a.get("noul") if a else None
        if not isinstance(p,(int,float)):
            pr=(a or {}).get("probabilities") or {}; p=max(pr.values()) if pr else None
        return (cid,tag,p)
    r=call(state,{"type":"choice","instructions":instr,"criteria":CRIT});a=(r.get("answers") or {}).get("q")
    pr=(a or {}).get("probabilities") or {}
    if not pr: return (cid,tag,None)
    k=max(pr,key=pr.get); return (cid,tag,MEAN[k])
pr32=json.load(open("pr32.json"))["body"]; pr33=json.load(open("pr33.json"))["body"]
AUTH32=f"GitHub pull request SuperInstance/quilt-tools #32\nTitle: referral-graph: edge #14 VERIFIED\nState: closed, merged=true, merged 2026-10-01T20:08:03Z, merge fb2e041\n\n{pr32}"
AUTH33=f"GitHub pull request SuperInstance/quilt-tools #33\nTitle: referral-graph: book edge #15 VERIFIED (fleet-murmur#8)\nState: closed, merged=true, merged 2026-10-01T20:29:03Z, merge 0101409\nBase: fb2e041 (PR #32's merge commit)\n\n{pr33}"
SEED=open("seedview.txt").read()
T=[]
for i in range(5):
  # inverse framing: is the count WRONG?
  T.append(("INV32","inverse",f"EVIDENCE:\n{AUTH32}\n\nCLAIM: PR #32's stated count of 18 edges / 14 VERIFIED / 4 PENDING is WRONG — the real graph has more than 18 edges.",INSTR,"choice"))
  T.append(("INV33","inverse",f"EVIDENCE:\n{AUTH33}\n\nCLAIM: PR #33's stated count of 18 edges / 14 VERIFIED is WRONG — the real graph has more than 18 edges.",INSTR,"choice"))
  T.append(("BOTH","both",f"EVIDENCE:\n{AUTH32}\n\n=====\n\n{AUTH33}\n\nCLAIM: Counting every edge in seed.mjs on main gives 19 total edges and 15 VERIFIED, not 18/14.",INSTR,"choice"))
  T.append(("NEEDX","needx",f"EVIDENCE:\n{AUTH32}\n\n=====\n\n{AUTH33}\n\nCLAIM: These two PRs were both counted against a base that excluded the other, so their counters undercount by one.",INSTR,"choice"))
  T.append(("N32","noul",f"EVIDENCE:\n{AUTH32}\n\nCLAIM: PR #32's own count (18 edges / 14 VERIFIED / 4 PENDING) is factually true.",f"Is the following claim factually true?\n\nCLAIM: PR #32's own count (18 edges / 14 VERIFIED / 4 PENDING) is factually true.",'noul'))
  T.append(("NX","noulX",f"EVIDENCE:\n{AUTH32}\n\n=====\n\n{AUTH33}\n\nCLAIM: Counting every edge in seed.mjs on main gives 19 total edges and 15 VERIFIED, not 18/14.",f"Is the following claim factually true?\n\nCLAIM: Counting every edge in seed.mjs on main gives 19 total edges and 15 VERIFIED, not 18/14.",'noul'))
  T.append(("SEED19","seed19",f"EVIDENCE:\n{SEED}\n\nCLAIM: seed.mjs on main contains 19 total edges, 15 VERIFIED, 4 PENDING.",INSTR,"choice"))
with ThreadPoolExecutor(max_workers=7) as ex: res=list(ex.map(run,T))
agg={}
for cid,tag,p in res: agg.setdefault((cid,tag),[]).append(p)
print(f"{'probe':<10}{'tag':<8}{'answers (5 reps)':<34}{'verdict'}")
TRUTH={"INV32":"incorrect","INV33":"incorrect","BOTH":"correct","NEEDX":"correct","SEED19":"correct"}
for (cid,tag),v in agg.items():
    if tag=='noul':
        ps=[x for x in v if isinstance(x,(int,float))]
        print(f"{cid:<10}{tag:<8}P(true)={[round(x,3) for x in ps]}")
    else:
        vv=[x for x in v if x]
        from collections import Counter
        m=Counter(vv).most_common(1)[0][0]
        ok='' if tag not in TRUTH else ('  OK' if m==TRUTH[tag] else '  *** WRONG ***')
        print(f"{cid:<10}{tag:<8}{str(vv):<34}{m}{ok}")
