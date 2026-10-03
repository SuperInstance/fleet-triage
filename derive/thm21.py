import math
def TdotT(alpha,beta):
    d=alpha-beta
    return math.cos(d)**2 - math.sin(d)**2   # = cos(2d)
def ang(t): return math.atan2(t[0],t[1])
tris=[(3,4,5),(5,12,13),(8,15,17),(7,24,25)]
print("Definition 2.1:  T_ij = (a_i a_j + b_i b_j)/c ,  a,b = ORTHOGONAL UNIT vectors")
print("=> T : T = (a.a)^2 + (b.b)^2 = 1 + 1 = 2   for EVERY triple.  (c cancels; c never appears)")
print("Theorem 2.1 asserts  T:T = c^2.  For c=5 that is 25, for c=13 it is 169. Prediction: 2.")
print()
print("Cross-term  T_(3,4,5) : T_(5,12,13)  -- theorem says 0")
a,b,c=tris[0]; aa,bb,cc=tris[1]
al=math.atan2(a,b); be=math.atan2(aa,bb)
print(f"  alpha={math.degrees(al):.4f} deg  beta={math.degrees(be):.4f} deg  delta={math.degrees(al-be):.4f} deg")
print(f"  predicted T1:T2 = cos(2*delta) = {TdotT(al,be):.10f}   (theorem claims 0)")
print(f"  also raw unit-vector dot a.a' = {math.cos(al-be):.10f}")
print()
print("=== brute force: does ANY weighting make the basis orthogonal? ===")
print("Gram matrix of raw unit vectors (cos,sin) for the 4 triples:")
G=[[round(math.cos(ang(x)-ang(y)),6) for y in tris] for x in tris]
for r in G: print("   ",r)
import numpy as np
A=np.array(G); print("  det(G) =", round(np.linalg.det(A),6), " rank:", np.linalg.matrix_rank(A), "of", len(tris))
print("  -> G is full rank and NOT diagonal: 4 vectors in 2-D cannot be mutually orthogonal anyway.")
