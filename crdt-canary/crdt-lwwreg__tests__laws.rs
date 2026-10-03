//! MERGE-LAW CANARY for crdt-lwwreg. Constructs the type; asserts LWW convergence.
//! Law: merge must be commutative, associative, idempotent, and a tie on timestamp
//! must be broken deterministically -- otherwise two replicas that receive the same
//! two writes in opposite orders end up with different values.

use crdt_lwwreg::LWWReg;

#[test]
fn law3_merge_is_idempotent() {
    let mut a: LWWReg<&str> = LWWReg::new("a");
    let mut b: LWWReg<&str> = LWWReg::new("b");
    a.merge(&b);
    let v = a.get().clone();
    a.merge(&b); a.merge(&b);
    assert_eq!(a.get().clone(), v, "LAW VIOLATED: re-merge changed the value");
}

#[test]
fn law_converges_when_timestamps_tie() {
    // Two registers written in the same millisecond. LWW requires a deterministic
    // tiebreak on (timestamp, node). Without one, merge order decides the winner --
    // and the replicas diverge.
    let mut r1: LWWReg<&str> = LWWReg::new("a");
    let mut r2: LWWReg<&str> = LWWReg::new("b");
    r1.set("A");
    r2.set("B");

    let mut x = r1.clone(); x.merge(&r2);
    let mut y = r2.clone(); y.merge(&r1);

    assert_eq!(
        x.get(), y.get(),
        "LAW VIOLATED: LWW registers diverged under a timestamp tie. \
         r1|r2 = {:?} but r2|r1 = {:?}. LWW must break ties deterministically.",
        x.get(), y.get()
    );
}

#[test]
fn law_converges_over_many_ties() {
    // The same-millisecond case is the COMMON case, not an edge case: SystemTime
    // has millisecond resolution, so any two writes in the same tick tie.
    let mut diverged = 0;
    for _ in 0..200 {
        let mut r1: LWWReg<u32> = LWWReg::new(1);
        let mut r2: LWWReg<u32> = LWWReg::new(2);
        r1.set(11);
        r2.set(22);
        let mut x = r1.clone(); x.merge(&r2);
        let mut y = r2.clone(); y.merge(&r1);
        if x.get() != y.get() {
            diverged += 1;
        }
    }
    assert_eq!(
        diverged, 0,
        "LAW VIOLATED: {} of 200 same-millisecond register pairs diverged under opposite merge order",
        diverged
    );
}
