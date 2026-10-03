//! MERGE-LAW CANARY for crdt-map -- the crate the consolidation plan has NO target for.
//! If it is the best-implemented crate in the family, its laws must hold too.

use crdt_map::{ORSet, LWWRegister, GCounter};

#[test]
fn orset_remove_tombstones_only_observed_tags_across_replicas() {
    let mut a: ORSet<u32> = ORSet::new("replica-a");
    a.add(100); // tag 1
    a.add(200); // tag 2

    let mut b: ORSet<u32> = ORSet::new("replica-b");
    b.add(300); // tag 1 -- same integer as a's first tag, different element

    assert!(a.remove(&100), "remove(100) must report success");
    let merged = a.merge(&b);

    assert!(!merged.contains(&100), "removed element 100 must stay removed");
    assert!(merged.contains(&200), "LAW VIOLATED: element 200 destroyed");
    assert!(
        merged.contains(&300),
        "LAW VIOLATED (tag aliasing): remove(100) tombstoned tag 1, which on replica-b belonged \
         to element 300. 300 was never removed."
    );
}

#[test]
fn gcounter_is_replica_scoped() {
    let c1 = GCounter::new("replica-1");
    let c2 = GCounter::new("replica-2");
    let mut a = c1.clone(); a.increment(5);
    let mut b = c2.clone(); b.increment(3);
    assert_eq!(a.merge(&b).value(), 8, "LAW VIOLATED: disjoint replicas must sum");
}

#[test]
fn lww_breaks_ties_deterministically() {
    let a = LWWRegister::new("A", 1000, "replica-a");
    let b = LWWRegister::new("B", 1000, "replica-b");
    let x = a.merge(&b);
    let y = b.merge(&a);
    assert_eq!(x.value(), y.value(), "LAW VIOLATED: LWW diverged on a timestamp tie");
}
