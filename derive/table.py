from fractions import Fraction as F
import math
tbl = [("3/5",3/5),("4/5",4/5),("5/13",5/13),("12/13",12/13),("8/17",8/17),("15/17",15/17),
       ("7/25",7/25),("24/25",24/25),("20/29",20/29),("21/29",21/29),("9/41",9/41),("40/41",40/41),
       ("12/37",12/37),("35/37",35/37),("11/61",11/61),("60/61",60/61),("28/53",28/53),("45/53",45/53),
       ("33/65",33/65),("56/65",56/65),("16/65",16/65),("63/65",63/65),
       ("1/2",0.5),("sqrt2/2",0.7071067811865476)]
print(f"{'entry':>10} {'label':>10} {'f64 -> Fraction':>42} {'round-trips to stated rational?':>36}")
bad=0
for lab,v in tbl:
    fr=F(v)
    stated = lab if '/' in lab else None
    ok = (fr==F(stated)) if stated else None
    if ok is False: bad+=1
    print(f"{lab:>10} {repr(v):>22} {str(fr):>42} {str(ok):>36}")
print(f"\n=> {bad}/{len([t for t in tbl if '/' in t[0]])} rational-labelled entries are NOT exactly representable in f64.")
irr=[t for t in tbl if t[0]=='sqrt2/2']
print(f"\n=> sqrt(2)/2 entry: is it a rational point on the unit circle?  2*(sqrt2/2)^2 = {2*(math.sqrt(2)/2)**2}")
print("   It IS on the unit circle, but it is NOT in Q. No integer triple generates it.")
print("   -> the table is advertised as 'exact Pythagorean coordinates' yet contains a non-rational.")
print()
print("=== is_valid() tolerance 1e-6 vs f32 storage: does (3,4,5) survive? ===")
import struct
def f32(x): return struct.unpack('f',struct.pack('f',x))[0]
a,b,c=f32(3),f32(4),f32(5)
print(f"  f32(3)^2+f32(4)^2-f32(5)^2 = {a*a+b*b-c*c}  (abs {abs(a*a+b*b-c*c):.3e} < 1e-6 ? {abs(a*a+b*b-c*c)<1e-6})")
# a genuinely invalid triple that PASSES
print("  PythagoreanTriple::new(1.0,1.0,1.0).is_valid():", abs(1+1-1)<1e-6, "<- 1^2+1^2 != 1^2 but passes? ", abs(1.0+1.0-1.0)<1e-6)
print("  -> is_valid() only checks the triple, never that coordinates are integers.")
