//! MERGE-LAW CANARY for crdt-core (the proposed consolidation target).
//! If the fleet consolidates onto crdt-core, these laws must hold THERE too --
//! otherwise consolidation moves the ports onto a broken target.

use crdt_core::orset::ORSet;

#[test]
fn orset_law1b_remove_tombstones_only_observed_tags_across_replicas() {
    let mut a: ORSet<u32> = ORSet::new();
    a.add(100); // A's tag 0
    a.add(200); // A's tag 1

    let mut b: ORSet<u32> = ORSet::new();
    b.add(300); // B's tag 0 -- same integer, different element

    assert!(a.remove(&100), "remove(100) must report success");
    a.merge(&b);
    let mut b2 = b.clone();
    b2.merge(&a);

    assert!(!a.contains(&100), "removed element 100 must stay removed");
    assert!(a.contains(&200), "LAW VIOLATED: element 200 destroyed on A");
    assert!(
        a.contains(&300),
        "LAW VIOLATED (tag aliasing): remove(100) tombstoned tag 0, which on B belonged to 300. \
         300 was never removed and must survive."
    );
    assert!(b2.contains(&300), "LAW VIOLATED: 300 destroyed on B by an unrelated remove");
    assert_eq!(a.contains(&300), b2.contains(&300), "LAW VIOLATED: replicas diverged on 300");
}

#[test]
fn orset_law2_add_wins() {
    let mut a: ORSet<u32> = ORSet::new();
    a.add(7);
    let mut b = a.clone();
    b.add(7);
    a.remove(&7);
    a.merge(&b);
    assert!(a.contains(&7), "LAW VIOLATED: add-wins semantics violated");
}

#[test]
fn orset_law3_merge_commutative_under_concurrent_add_remove() {
    let mut a: ORSet<u32> = ORSet::new();
    a.add(1); a.add(2);
    let mut b: ORSet<u32> = ORSet::new();
    b.add(3);
    a.remove(&2);
    let mut ab = a.clone(); ab.merge(&b);
    let mut ba = b.clone(); ba.merge(&a);
    for e in [1u32, 2, 3] {
        assert_eq!(ab.contains(&e), ba.contains(&e), "LAW VIOLATED: diverged on {}", e);
    }
    assert!(!ab.contains(&2), "LAW VIOLATED: observed remove of 2 was lost");
}

#[test]
fn lww_law_deterministic_tiebreak() {
    // crdt-core's LWW takes an explicit (timestamp, node_id) key.
    let a = crdt_core::lww::LWWRegister::new("A", 1000, 1);
    let b = crdt_core::lww::LWWRegister::new("B", 1000, 2);
    let mut x = a.clone(); x.merge(&b);
    let mut y = b.clone(); y.merge(&a);
    assert_eq!(x.value(), y.value(), "LAW VIOLATED: crdt-core LWW diverged on a timestamp tie");
}
