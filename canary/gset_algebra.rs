//! The smallest canary that can fail: G-Set merge IS set union.
//! Construct two disjoint replicas, merge, assert the union.

#[test]
fn gset_merge_is_union() {
    let mut a = crdt_gset::GSet::new();
    a.add(1);
    a.add(2);

    let mut b = crdt_gset::GSet::new();
    b.add(3);

    a.merge(&b);

    assert_eq!(a.len(), 3, "merge lost or invented elements");
    assert!(a.contains(&1) && a.contains(&2) && a.contains(&3),
            "merge did not produce the union");
}

#[test]
fn gset_merge_is_commutative() {
    let mut a = crdt_gset::GSet::new();
    a.add(1);
    let mut b = crdt_gset::GSet::new();
    b.add(2);

    let mut ab = a.clone(); ab.merge(&b);
    let mut ba = b.clone(); ba.merge(&a);

    assert_eq!(ab.len(), ba.len(), "merge is not commutative");
    assert_eq!(ab.contains(&2), ba.contains(&2));
}

#[test]
fn gset_merge_is_idempotent() {
    let mut a = crdt_gset::GSet::new();
    a.add(1);
    a.merge(&a.clone());
    assert_eq!(a.len(), 1, "merge is not idempotent");
}

#[test]
fn gset_merge_is_associative() {
    let mut a = crdt_gset::GSet::new(); a.add(1);
    let mut b = crdt_gset::GSet::new(); b.add(2);
    let mut c = crdt_gset::GSet::new(); c.add(3);

    let mut left = a.clone(); let mut bc = b.clone(); bc.merge(&c); left.merge(&bc);
    let mut right = c.clone(); let mut ab = a.clone(); ab.merge(&b); right.merge(&ab);

    assert_eq!(left.len(), right.len(), "merge is not associative");
    assert_eq!(left.len(), 3);
}
