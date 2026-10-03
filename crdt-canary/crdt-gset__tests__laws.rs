//! MERGE-LAW CANARY for crdt-gset. Constructs the type; asserts the CRDT algebra.
//! Law sources: G-Set is a join-semilattice: merge = set union. Therefore
//! union is commutative, associative, idempotent.

use crdt_gset::GSet;

fn mk() -> GSet<u32> { GSet::new() }

#[test]
fn law1_merge_is_set_union() {
    let mut a = mk();
    a.add(1); a.add(2);
    let mut b = mk();
    b.add(3); b.add(4);
    a.merge(&b);
    for e in [1u32, 2, 3, 4] {
        assert!(a.contains(&e), "after merge, element {} must be present", e);
    }
    assert_eq!(a.len(), 4, "union of disjoint {{1,2}} and {{3,4}} has cardinality 4");
}

#[test]
fn law2_merge_is_commutative() {
    let mut a = mk(); a.add(1); a.add(2);
    let mut b = mk(); b.add(3);
    a.merge(&b);
    let mut x = mk(); x.add(1); x.add(2);
    let mut y = mk(); y.add(3);
    y.merge(&x);
    for e in [1u32, 2, 3] {
        assert_eq!(a.contains(&e), y.contains(&e), "divergence on element {}", e);
    }
    assert_eq!(a.len(), y.len(), "commutative merge: equal cardinality");
}

#[test]
fn law3_merge_is_idempotent() {
    let mut a = mk(); a.add(1);
    let mut b = mk(); b.add(2);
    a.merge(&b);
    let after_first = a.len();
    a.merge(&b);
    a.merge(&b);
    assert_eq!(a.len(), after_first, "re-merging the same replica must not grow the set");
}

#[test]
fn law4_merge_is_associative() {
    let mut a = mk(); a.add(1);
    let mut b = mk(); b.add(2);
    let mut c = mk(); b.add(0); c.add(3);
    // (a|b)|c
    let mut l = a.clone(); let bb = b.clone(); l.merge(&bb); l.merge(&c);
    // a|(b|c)
    let mut r = a.clone(); let mut bc = b.clone(); bc.merge(&c); r.merge(&bc);
    for e in [0u32, 1, 2, 3] {
        assert_eq!(l.contains(&e), r.contains(&e), "divergence on element {}", e);
    }
    assert_eq!(l.len(), r.len(), "associative merge: equal cardinality");
}
