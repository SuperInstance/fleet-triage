//! MERGE-LAW CANARY for crdt-gcounter. Constructs the type; asserts the G-Counter algebra.
//! Law: merge is per-slot max, so merge is commutative, associative, idempotent, and
//! the value is the SUM of independent per-node slots.

use crdt_gcounter::GCounter;

#[test]
fn law1_merge_unions_disjoint_replicas() {
    let mut a = GCounter::new();
    a.increment("a", 3);
    let mut b = GCounter::new();
    b.increment("b", 5);
    a.merge(&b);
    assert_eq!(a.value(), 8, "LAW VIOLATED: 3 + 5 must be 8 after merging disjoint nodes");
}

#[test]
fn law2_merge_is_commutative() {
    let mut a = GCounter::new(); a.increment("a", 3);
    let mut b = GCounter::new(); b.increment("b", 5); b.increment("c", 2);
    a.merge(&b);
    let mut x = GCounter::new(); x.increment("a", 3);
    let mut y = GCounter::new(); y.increment("b", 5); y.increment("c", 2);
    y.merge(&x);
    assert_eq!(a.value(), y.value(), "LAW VIOLATED: merge is not commutative");
}

#[test]
fn law3_merge_is_idempotent() {
    let mut a = GCounter::new(); a.increment("a", 3);
    let mut b = GCounter::new(); b.increment("b", 5);
    a.merge(&b);
    let v = a.value();
    a.merge(&b); a.merge(&b); a.merge(&b);
    assert_eq!(a.value(), v, "LAW VIOLATED: re-merge changed the value (max must be idempotent)");
}

#[test]
fn law4_merge_is_associative() {
    let mut a = GCounter::new(); a.increment("a", 1);
    let mut b = GCounter::new(); b.increment("a", 4);
    let mut c = GCounter::new(); c.increment("a", 9);
    let mut l = a.clone(); let bb = b.clone(); l.merge(&bb); let cc = c.clone(); l.merge(&cc);
    let mut bc = b.clone(); let cc2 = c.clone(); bc.merge(&cc2);
    let mut r = a.clone(); r.merge(&bc);
    assert_eq!(l.value(), r.value(), "LAW VIOLATED: merge is not associative");
    assert_eq!(l.value(), 9, "LAW VIOLATED: max(1,4,9) must be 9");
}
