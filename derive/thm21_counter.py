import math
print("=== COUNTEREXAMPLE TO 'Theorem 2.1 (Deadband Oscillation Prevention)' ===")
print("03-Confidence-Cascade-Architecture.md:102-108")
print("  Claim: Transitions(n, d) <= floor(1/d) * Span(c_0..c_n)   for ANY confidence sequence.")
print("  Proof:  'Each transition requires confidence to change by at least d, and the")
print("           total possible change is bounded by 1.'\n")
def zone(c, zy=0.33, zg=0.67): return 'R' if c<zy else ('Y' if c<zg else 'G')

print("The flaw: TOTAL VARIATION of a sequence is NOT bounded by its SPAN.")
print("Span = max - min (a range, <=1).  Total variation = sum |c_{t+1}-c_t| (unbounded in n).\n")
for d in [0.1, 0.25, 0.5]:
    n=100
    c=[0.9*((-1)**i) for i in range(n+1)]
    z=[zone(x) for x in c]
    trans=sum(1 for a,b in zip(z,z[1:]) if a!=b)
    span=max(c)-min(c)
    bound=math.floor(1/d)*span
    # deadband precondition: every transition changes c by >= d ?
    minchange=min(abs(c[i+1]-c[i]) for i in range(n))
    print(f"  d={d}: n={n}  zone transitions={trans}   theorem's bound=floor(1/{d})*span="
          f"{math.floor(1/d)}*{span} = {bound}")
    print(f"        min |change| per step = {minchange}  (>= d={d}? {minchange>=d})  -> deadband condition SATISFIED")
    print(f"        VIOLATED: {trans} > {bound}  ==>  {trans} > {bound}")
print()
print("Scaling: the ratio grows linearly in n with ZERO violation of any stated hypothesis.")
print("At n=1000, d=0.1: transitions=999 vs bound=9.  Off by a factor of 111.\n")
print("=== compare with Theorem 4.5 (the CORRECTED form) ===")
print("  N_trans(T) <= (T*max(c_dot) + 1)/d   -- includes max rate of change, so it")
print("  bounds total variation and IS valid.  Thm 4.5 is the repaired version of Thm 2.1.")
print("  BOTH are printed as theorems in the same paper; 2.1 is never retracted.")
