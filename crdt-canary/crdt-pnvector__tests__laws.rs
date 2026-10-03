//! MERGE-LAW CANARY for crdt-pnvector. Constructs the type; asserts the PN-Counter algebra.

use crdt_pnvector::PNVector;

#[test]
fn law1_merge_unions_disjoint_replicas() {
    let mut a = PNVector::new();
    a.increment("a"); a.increment("a");
    let mut b = PNVector::new();
    b.increment("b"); b.decrement("b");
    a.merge(&b);
    assert_eq!(a.value(), 2, "LAW VIOLATED: 2 increments + 1 - 1 must be 2");
}

#[test]
fn law2_merge_is_commutative() {
    let mut a = PNVector::new(); a.increment("a"); a.increment("a"); a.decrement("a");
    let mut b = PNVector::new(); b.increment("b"); b.decrement("b"); b.decrement("b");
    a.merge(&b);
    let mut x = PNVector::new(); x.increment("a"); x.increment("a"); x.decrement("a");
    let mut y = PNVector::new(); y.increment("b"); y.decrement("b"); y.decrement("b");
    y.merge(&x);
    assert_eq!(a.value(), y.value(), "LAW VIOLATED: merge is not commutative");
}

#[test]
fn law3_merge_is_idempotent() {
    let mut a = PNVector::new(); a.increment("a"); a.increment("a");
    let mut b = PNVector::new(); b.increment("b"); b.decrement("b");
    a.merge(&b);
    let v = a.value();
    a.merge(&b); a.merge(&b);
    assert_eq!(a.value(), v, "LAW VIOLATED: re-merge changed the value");
}

#[test]
fn law4_merge_is_associative() {
    let mut a = PNVector::new(); a.increment("a");
    let mut b = PNVector::new(); b.increment("a"); b.decrement("a");
    let mut c = PNVector::new(); c.decrement("a"); c.decrement("a");
    let mut l = a.clone(); let bb = b.clone(); l.merge(&bb); let cc = c.clone(); l.merge(&cc);
    let mut bc = b.clone(); let cc2 = c.clone(); bc.merge(&cc2);
    let mut r = a.clone(); r.merge(&bc);
    assert_eq!(l.value(), r.value(), "LAW VIOLATED: merge is not associative");
    assert_eq!(l.value(), -1, "LAW VIOLATED: p=max(1,1,0)=1, n=max(0,1,2)=2, 1-2=-1");
}
