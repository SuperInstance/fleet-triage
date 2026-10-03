from fractions import Fraction as F
import math, itertools

tris = [(3,4,5),(5,12,13),(8,15,17),(7,24,25),(20,21,29)]
def dot(u,v): return u[0]*v[0] + u[1]*v[1]

print("=== D1: PGT basis from integer triples -- orthonormal? orthogonal? ===")
vecs=[(F(b,c),F(a,c)) for a,b,c in tris]   # (cos,sin) as exact rationals
for i,j in itertools.combinations(range(len(vecs)),2):
    print(f"  v{i}={tuple(map(str,vecs[i]))} . v{j}={tuple(map(str,vecs[j]))} = {dot(vecs[i],vecs[j])}")
print("  -> dot products are NOT 0. Claim 'orthogonal with respect to Frobenius' needs a weighting to be true;")
print("     raw dot of any two rational unit vectors is generally nonzero.")

print()
print("=== D2: density of Pythagorean angles (rational points on unit circle) ===")
for N in [10,50,100,500]:
    pts=set()
    for q in range(1,N+1):
        for p in range(0,q+1):
            if math.gcd(p,q)>1: continue
            t=F(p,q); x=(1-t*t)/(1+t*t); y=2*t/(1+t*t)
            pts.add(round(math.atan2(float(y),float(x)),12))
    pts=sorted(p for p in pts if -1e-9<=p<=math.pi/2+1e-9)
    gaps=[b-a for a,b in zip(pts,pts[1:])]+[math.pi/2-pts[-1]]
    print(f"    q<= {N:4d}: #angles={len(pts):4d}  max angular gap={max(gaps):.3e} rad  ~1/len={1/len(pts):.3e}  1/sqrt(N)={1/math.sqrt(N):.3e}")
print("  -> gap scales like 1/sqrt(N) in denominator, i.e. 1/number_of_points. NOT 1/N.")

print()
print("=== D3: angle addition -- is tan(a)+tan(c) = (a+c)/(b+d)? ===")
print("  tangent ADDITION: tan(alpha+beta) = (ad+bc)/(bd-ac).")
print("  componentwise 'vector' addition of the integer legs: (a+c, b+d).")
for (a,b,cc) in [(3,4,5),(5,12,13)]:
    pass
ex=[(3,4,5),(5,12,13),(8,15,17),(7,24,25)]
for (a,b,c0),(cc,d,e) in itertools.combinations(ex,2):
    naive_num, naive_den = a+cc, b+d
    true_num, true_den = a*d+b*cc, b*d-a*cc
    print(f"  ({a},{b}) + ({cc},{d}): naive (a+c)/(b+d)=({naive_num},{naive_den}) tan={float(F(naive_num,naive_den)):.9f}")
    print(f"      true tan-sum  =({true_num},{true_den}) tan={float(F(true_num,true_den)):.9f}")
    print(f"      tan(alpha)+tan(beta) = {a/b + cc/d:.9f}   (a third different number!)")
    # is the true tan-sum a Pythagorean slope? need num^2+den^2 perfect square
    s=true_num**2+true_den**2
    print(f"      true sum: {true_num}^2+{true_den}^2 = {s}, isqrt={math.isqrt(s)} -> {'PYTHAGOREAN' if math.isqrt(s)**2==s else 'NOT pythagorean'}")
    break

print()
print("=== D4: exact-rational coordinate check (mimics the 15-entry table claim) ===")
rows=[(3,4,5),(5,12,13),(8,15,17),(7,24,25),(20,21,29),(9,40,41),(12,35,37),(11,60,61),(28,45,53),(33,56,65),(16,63,65),(48,55,73),(13,84,85),(36,77,85),(39,80,89)]
for a,b,c in rows:
    x=1.0*a/c; y=1.0*b/c
    ex_ = math.gcd(math.gcd(a,c),b)
    exact = (a/c==F(a,c) and b/c==F(b,c))
    # check whether f64 division of a by c is EXACTLY representable
    print(f"  ({a},{b},{c}): a/c={x!r} b/c={y!r}  both f64-exact? {a/c==float(F(a,c)) and b/c==float(F(b,c))}  gcd={ex_}")
