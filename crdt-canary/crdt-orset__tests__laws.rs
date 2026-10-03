//! MERGE-LAW CANARY for crdt-orset. Constructs the type; asserts the OR-Set algebra.
//! Law sources: OR-Set is a state-based add-wins set. A remove tombstones exactly the
//! tags it OBSERVED. Therefore:
//!   L1 remove is precise      -- removing x must not affect any y != x
//!   L2 add-wins              -- re-adding a removed element resurrects it
//!   L3 merge is commutative   -- a.merge(b) == b.merge(a) under concurrent add/remove
//!   L4 merge is idempotent
//!   L5 merge is associative

use crdt_orset::ORSet;

#[test]
fn law1_remove_is_precise_only_affects_named_element() {
    // Two DISTINCT elements. A removes only the first.
    let mut s = ORSet::new();
    s.add(1);
    s.add(2);
    assert!(s.remove(&1), "remove of a present element must return true");
    assert!(!s.contains(&1), "removed element must be absent");
    assert!(s.contains(&2), "LAW VIOLATED: remove(1) also destroyed 2, which was never removed");
}

#[test]
fn law1b_remove_tombstones_observed_tags_across_replicas() {
    // The core OR-Set guarantee: a remove on replica A must delete the element at
    // replica B -- and only that element, even when both replicas numbered their
    // tags independently. This is where a locally-generated tag counter aliases.
    let mut a = ORSet::new();
    a.add(100); // A's tag 0
    a.add(200); // A's tag 1

    let mut b = ORSet::new();
    b.add(300); // B's tag 0  <-- same integer as A's tag 0, different element

    assert!(a.remove(&100), "remove(100) must report success");
    a.merge(&b);

    let mut b2 = b.clone();
    b2.merge(&a);

    assert!(!a.contains(&100), "removed element 100 must stay removed");
    assert!(a.contains(&200), "LAW VIOLATED: element 200 destroyed on A");
    assert!(
        a.contains(&300),
        "LAW VIOLATED (tag aliasing): remove(100) on A tombstoned tag 0, which on B belonged \
         to element 300. 300 was never removed and must survive the merge."
    );
    assert!(b2.contains(&300), "LAW VIOLATED: 300 destroyed on B by an unrelated remove");
    // Convergence: both replicas must agree.
    assert_eq!(a.contains(&300), b2.contains(&300), "LAW VIOLATED: replicas diverged on 300");
}

#[test]
fn law2_add_wins_over_concurrent_remove() {
    let mut a = ORSet::new();
    a.add(7);
    let mut b = a.clone();
    b.add(7); // concurrent re-add, fresh tag
    a.remove(&7);
    a.merge(&b);
    assert!(a.contains(&7), "LAW VIOLATED: add-wins semantics say the re-add must survive");
}

#[test]
fn law3_merge_is_commutative_under_concurrent_add_remove() {
    let mut a = ORSet::new();
    a.add(1); a.add(2);
    let mut b = ORSet::new();
    b.add(3);
    a.remove(&2); // concurrent remove on A

    let mut ab = a.clone(); ab.merge(&b);
    let mut ba = b.clone(); ba.merge(&a);
    for e in [1u32, 2, 3] {
        assert_eq!(ab.contains(&e), ba.contains(&e), "LAW VIOLATED: diverged on element {}", e);
    }
    assert!(!ab.contains(&2), "LAW VIOLATED: the observed remove of 2 was lost");
}

#[test]
fn law4_merge_is_idempotent() {
    let mut a = ORSet::new();
    a.add(1);
    let mut b = ORSet::new();
    b.add(2);
    a.merge(&b);
    let snap: Vec<bool> = (0..4).map(|i| a.contains(&i)).collect();
    a.merge(&b);
    a.merge(&b);
    let after: Vec<bool> = (0..4).map(|i| a.contains(&i)).collect();
    assert_eq!(snap, after, "LAW VIOLATED: re-merging changed state");
}

#[test]
fn law5_merge_is_associative() {
    let mut a = ORSet::new();
    a.add(1);
    let mut b = ORSet::new();
    b.add(2);
    let mut c = ORSet::new();
    c.add(3);

    let mut l = a.clone(); let bb = b.clone(); l.merge(&bb); let cc = c.clone(); l.merge(&cc);
    let mut bc = b.clone(); let cc2 = c.clone(); bc.merge(&cc2);
    let mut r = a.clone(); r.merge(&bc);

    for e in [1u32, 2, 3] {
        assert_eq!(l.contains(&e), r.contains(&e), "LAW VIOLATED: diverged on element {}", e);
    }
}
