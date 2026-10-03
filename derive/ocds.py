import math
nodes=[10,100,1000,10000]; deg=[3,5,7,10]; t=[12,47,89,156]; msgs=[45,523,6247,78431]
print("=== OCDS 'Empirical Evaluation' 07-Origin-Centric-Data-Systems.md:216-220 ===")
print("Claim: 'Results show O(log n) scaling as predicted.'\n")
print(f"{'n':>7} {'time ms':>8} {'time/ln n':>10} {'time/log2 n':>12} {'msgs':>8} {'msgs/n':>9}")
for n,d,tt,m in zip(nodes,deg,t,msgs):
    print(f"{n:>7} {tt:>8} {tt/math.log(n):>10.3f} {tt/math.log2(n):>12.3f} {m:>8} {m/n:>9.3f}")
print()
print("If T = c*log n then time/log n must be CONSTANT. It is:")
vals=[tt/math.log(n) for n,tt in zip(nodes,t)]
print("  ", [round(v,2) for v in vals], " ratio max/min = %.2fx" % (max(vals)/min(vals)))
print("  -> NOT log. The growth 12->47->89->156 is much closer to SUBLINEAR-but-not-log,")
print("     i.e. n^alpha. Fit alpha:")
for (n1,t1),(n2,t2) in [((10,12),(10000,156))]:
    a=math.log(t2/t1)/math.log(n2/n1)
    print(f"     alpha = log(156/12)/log(10000/10) = {a:.4f}  -> T ~ n^{a:.3f}")
print()
print("=== README 08: 'Message Complexity O(n^3) -> O(k), 1000x reduction' ===")
print("Paper 07:118 says message complexity is O(d) per update 'vs O(n^2) for consensus'.")
print("README upgrades the baseline from O(n^2) to O(n^3):")
print("  paper  07-Origin-Centric-Data-Systems.md:118 -> 'O(n^2) for consensus'")
print("  README 08-Origin-Centric-Data-Systems-README.md -> table 'Traditional ... O(n^3)'")
print("  n^3 vs n^2 is a factor of n -- the '1000x' is manufactured by inflating the baseline.")
print()
print("And the paper's OWN table (line 239) says Raft=2n, PBFT=O(n^2) -- never O(n^3).")
print()
print("=== 1000x check at the paper's own largest measured n ===")
for n,d,m in zip(nodes,deg,msgs):
    print(f"  n={n:>6}: OCDS msgs={m:>6}  vs O(n^3)={n**3:>14}  ratio={n**3/m:>12.1f}x   vs O(n^2)={n*n:>10} ratio={n*n/m:>8.1f}x")
