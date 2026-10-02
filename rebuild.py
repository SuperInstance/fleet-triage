W,H=7,6
def four(m):
    for r in range(H):
        for c in range(W-3):
            if all((m>>(7*(c+k)+r))&1 for k in range(4)): return True
    for c in range(W):
        for r in range(H-3):
            if all((m>>(7*c+(r+k)))&1 for k in range(4)): return True
    for c in range(W-3):
        for r in range(H-3):
            if all((m>>(7*(c+k)+(r+k)))&1 for k in range(4)): return True
            if all((m>>(7*(c+k)+(r+3-k)))&1 for k in range(4)): return True
    return False
def haswin(m):
    for c in range(W):
        h=sum(1 for r in range(H) if (m>>(7*c+r))&1)
        if h<H and four(m|(1<<(7*c+h))): return True
    return False
ok=0
out=open('/tmp/c4/verified_subset.txt','w')
for line in open('/tmp/c4/c4_ground_truth.txt'):
    m,p,v=map(int,line.split())
    if p>>42 or (p&~m): continue
    good=True
    for c in range(W):
        for who in (p, m&~p):
            col=''.join('1' if (who>>(7*c+r))&1 else '0' for r in range(H))
            if '01' in col: good=False; break
        if not good: break
    if not good: continue
    n0=bin(p).count('1'); nt=bin(m).count('1')
    if abs(n0-(nt-n0))>1: continue
    w=haswin(m)
    if (w and v>0) or (not w and v<0):
        ok+=1; out.write(f"{m} {p} {v} {1 if w else 0}\n")
out.close()
print(f"  rebuilt verified subset: {ok} rows")
