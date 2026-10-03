//! The smallest canary that can fail: OR-Set remove cancels only OBSERVED adds.
//!
//! OR-Set semantics: remove(x) tombstones the adds it has *seen*. An add that was
//! concurrent with the remove (the remover never observed it) MUST survive the merge.
//! Formally: A.add(x); A.remove(x);  B.add(x) concurrently;  A.merge(B) => contains(x).

#[test]
fn orset_concurrent_add_survives_a_concurrent_remove() {
    // Replica A: add then remove. It has observed tag 0 and tombstoned it.
    let mut a = crdt_orset::ORSet::new();
    a.add(1);
    a.remove(&1);
    assert!(!a.contains(&1), "remove should be visible locally");

    // Replica B: concurrent add. A never saw this tag.
    let mut b = crdt_orset::ORSet::new();
    b.add(2);

    // A merges B. B's add was never observed by A's remove, so it must survive.
    a.merge(&b);
    assert!(a.contains(&2), "concurrent add was wrongly killed by a concurrent remove");
}

#[test]
fn orset_merge_is_commutative_under_concurrency() {
    // Same interleaving, merged in both orders. A CRDT must agree with itself.
    let mut a1 = crdt_orset::ORSet::new();
    a1.add(1); a1.remove(&1);
    let mut b1 = crdt_orset::ORSet::new();
    b1.add(2);

    let mut a2 = crdt_orset::ORSet::new();
    a2.add(1); a2.remove(&1);
    let mut b2 = crdt_orset::ORSet::new();
    b2.add(2);

    a1.merge(&b1);   // A <- B
    b2.merge(&a2);   // B <- A

    assert_eq!(a1.contains(&2), b2.contains(&2),
               "merge is not commutative: A<-B and B<-A disagree");
}

#[test]
fn orset_add_remove_add_is_observable() {
    // The classic OR-Set law: after remove-then-readd the element is present,
    // and that presence must survive a round trip through another replica.
    let mut a = crdt_orset::ORSet::new();
    a.add(7);
    a.remove(&7);
    a.add(7);
    assert!(a.contains(&7), "re-add after remove must be observable");

    let mut b = crdt_orset::ORSet::new();
    b.merge(&a);
    assert!(b.contains(&7), "re-add did not survive merge onto a fresh replica");
}

#[test]
fn orset_remove_reports_whether_it_removed() {
    let mut a = crdt_orset::ORSet::new();
    a.add(1);
    assert!(a.remove(&1), "remove of a present element must return true");
    assert!(!a.remove(&1), "remove of an absent element must return false");
}
