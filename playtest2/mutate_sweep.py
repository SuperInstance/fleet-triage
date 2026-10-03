import sys, json, io, contextlib
from pathlib import Path
sys.path.insert(0,'.')
import exectest
rows=json.load(open('sweep.json'))
cands=[r for r in rows if r['verdict'] in ('EXECUTES-PRODUCT',)]
base=Path('/workspace/projects/fleet-triage/repos')
out=[]
for i,r in enumerate(cands,1):
    p=base/r['repo']
    try:
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            rep=exectest.analyse(p, do_mutate=True, quiet=True)
        m=rep.mutation
        out.append({'repo':r['repo'],'verdict':rep.verdict,
                    'baseline':rep.baseline,
                    'n_mut':len(m.get('mutations',[])),
                    'caught':sum(1 for x in m.get('mutations',[]) if x['caught']),
                    'muts':m.get('mutations',[]),'skipped':m.get('skipped')})
        print(f"  {i}/{len(cands)} {r['repo']}: {sum(1 for x in m.get('mutations',[]) if x['caught'])}/{len(m.get('mutations',[]))} caught",file=sys.stderr)
    except Exception as e:
        out.append({'repo':r['repo'],'verdict':'TOOL-ERROR','err':str(e)[:200]})
json.dump(out,open('mutate_sweep.json','w'),indent=1)
print("done",len(out))
