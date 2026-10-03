import math
from fractions import Fraction as F
tbl=[0.0,1.0,3/5,4/5,5/13,12/13,8/17,15/17,7/25,24/25,20/29,21/29,9/41,40/41,
     12/37,35/37,11/61,60/61,28/53,45/53,33/65,56/65,16/65,63/65,0.5,0.7071067811865476]
def snap_rational(v):
    best=v; md=float('inf')
    for r in tbl:
        d=abs(v-r)
        if d<md: md=d; best=r
    return best
def snap_to_lattice(p):
    n=math.sqrt(sum(x*x for x in p))
    if n<1e-10: return list(p)
    return [snap_rational(x/n)*n for x in p]
print("=== snap_to_lattice(): does it preserve the Pythagorean (unit-norm) constraint? ===")
print("hidden_dimensions.rs:264-270 snaps each component INDEPENDENTLY to a scalar, then rescales by norm.\n")
tests=[(0.3,0.4),(0.7071,0.7071),(1.0,2.0),(0.1,0.9),(0.6,0.8),(2.0,5.0)]
print(f"{'input':>14} {'snapped':>34} {'norm before':>12} {'norm after':>12} {'ON unit circle?':>17}")
for p in tests:
    s=snap_to_lattice(p)
    nb=math.hypot(*p); na=math.hypot(*s)
    print(f"{str(p):>14} {str([round(x,4) for x in s]):>34} {nb:12.6f} {na:12.6f} {str(abs(na-1)<1e-9):>17}")
print()
print("KEY: a 'Pythagorean point' (x,y) with x^2+y^2=r^2 becomes (r*a, r*b) with a,b INDEPENDENTLY")
print("snapped. Unless the two snapped ratios happen to form a triple, the result is NOT Pythagorean.")
print()
# find a concrete counterexample
print("=== counterexample search: input whose snap leaves the unit circle ===")
cnt=0
import itertools
for i in range(1,200):
    for j in range(1,200):
        x,y=i/200,j/200
        if x*x+y*y>1: continue
        n=math.hypot(x,y)
        if n<1e-9: continue
        s=snap_to_lattice([x,y]); na=math.hypot(*s)
        if abs(na-1)>1e-6:
            cnt+=1
            if cnt<=4: print(f"  ({x:.4f},{y:.4f}) -> ({s[0]:.6f},{s[1]:.6f})  norm={na:.9f}  OFF by {abs(na-1):.2e}")
print(f"  ... {cnt} of ~15700 unit-circle grid points snapped OFF the unit circle.")
