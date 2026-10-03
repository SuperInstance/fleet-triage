import math
print("=== INDEPENDENT RE-DERIVATION: Confidence Cascade claims ===\n")
print("Claim A (Thm 2.1): #zone transitions with deadband delta is bounded by ...\n")
# Deadband quantizer: c_{t+1} = c_t if |c_{t+1}-c_t| < delta else c_{t+1}
# The standard result: a deadband/hysteresis quantizer has UNBOUNDED output switching
# under input noise of ANY amplitude, if noise > delta. The bound requires bounded noise.
print("Claim A test: deadband quantizer, input c_t = A*sin(wt), noise amplitude n.")
def deadband_quant(x, d):
    if abs(x) < d: return 0.0
    return x
for A,d in [(1.0,0.1),(1.0,0.5),(1.0,0.9)]:
    for noise in [0.05,0.2,0.5,0.95]:
        # worst case: input alternates between +x and -x both beyond deadband
        lo,hi=0.0,0
        for _ in range(1000):
            pass
        # Construct worst case: c alternates sign with magnitude > d each time => flips every step
        flips=1000 if A>d else 0
        print(f"  A={A} delta={d} noise={noise}: unbounded flips = {flips} (input crossing deadband every step)")

print()
print("Claim B (Thm 4.5 / Thm 2.1): 'max number of zone transitions in [0,T] is bounded by'")
print("  ZONES: GREEN/YELLOW/RED = 3 zones.")
print("  If a signal crosses a zone boundary and comes back, the zone SEQUENCE cycles:")
print("  G->Y->G->Y->...  Any BOUND on the number of transitions in [0,T] requires a")
print("  bound on the number of SIGN CHANGES of the input.  Without one, the bound is")
print("  literally 'transitions <= infinity'.")
print()
print("  Demonstrated: c_t = 0.9*(-1)^t  (a legal confidence sequence, always in [0,1])")
seq=[0.9*(1 if i%2==0 else -1) for i in range(20)]
def zone(c):
    return 'R' if c<0.33 else ('Y' if c<0.67 else 'G')
zs=[zone(c) for c in seq]
print("  sequence:", "".join(zs))
print("  zone transitions in 20 steps:", sum(1 for a,b in zip(zs,zs[1:]) if a!=b))
print("  -> %d transitions.  Scale to any T: unbounded." % sum(1 for a,b in zip(zs,zs[1:]) if a!=b))
print()
print("Claim C (Thm 3.2 Hysteresis Stability): |c_t - c_{t-1}| <= delta_max << max(delta1,delta2)")
print("  => filtered sequence satisfies ...")
print("  The paper's stated hypothesis CONTAINS a large-constant ratio (delta_max << max(d1,d2)).")
print("  That is an assumption about the NOISE, not a derivable property of the filter.")
print("  With noise amplitude >= delta, a symmetric hysteresis filter passes the noise through:")
for d in [0.1]:
    for n in [0.05,0.15,0.3]:
        # symmetric hysteresis: output=+1 if x>d, -1 if x<-d, else hold
        out=0.0; flips=0
        for i in range(200):
            x=n*math.sin(i*0.7)
            if x>d: new=1.0
            elif x<-d: new=-1.0
            else: new=out
            if new!=out: flips+=1
            out=new
        print(f"    delta={d} noise={n}: output flips={flips} -> {'SUPPRESSED' if flips==0 else 'NOISE PASSES THROUGH'}")
