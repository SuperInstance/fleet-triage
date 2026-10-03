import sys, json, io, contextlib
from pathlib import Path
sys.path.insert(0,'.')
import exectest
rows=[]
base=Path('/workspace/projects/fleet-triage/repos')
repos=sorted([p for p in base.iterdir() if p.is_dir() and (p/'.git').exists()])
for i,p in enumerate(repos,1):
    try:
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            rep=exectest.analyse(p, do_mutate=False, quiet=True)
        rows.append({'repo':p.name,'verdict':rep.verdict,
                     'ntests':len(rep.test_files),
                     'vac':[f['subject'] for f in rep.findings if f['severity']=='VACUOUS'],
                     'sus':len([f for f in rep.findings if f['severity']=='SUSPECT'])})
    except Exception as e:
        rows.append({'repo':p.name,'verdict':'TOOL-ERROR','ntests':0,'vac':[],'sus':0,'err':str(e)[:100]})
    if i%25==0: print(f"  ...{i}/{len(repos)}",file=sys.stderr)
json.dump(rows,open('sweep.json','w'),indent=1)
print("done",len(rows))
