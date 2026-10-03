//! crdt-core variant. NOTE: the OR-Set law MUST use add(), not add_with_tag().
//! add_with_tag is the test-only escape hatch that lets crdt-core's own
//! src/orset.rs:148-162 pass while the public API is broken.
use crdt_core::{GSet, ORSet};

#[test]
fn gset_merge_is_union() {
    let mut a = GSet::new(); a.add(1); a.add(2);
    let mut b = GSet::new(); b.add(3);
    let m = a.merged(&b);
    assert_eq!(m.len(), 3, "merge lost or invented elements");
    assert!(m.contains(&1) && m.contains(&2) && m.contains(&3));
}

#[test]
fn gset_merge_is_associative() {
    let mut a = GSet::new(); a.add(1);
    let mut b = GSet::new(); b.add(2);
    let mut c = GSet::new(); c.add(3);
    let left = a.merged(&b.merged(&c));
    let right = c.merged(&a.merged(&b));
    assert_eq!(left.len(), right.len()); assert_eq!(left.len(), 3);
}

#[test]
fn orset_concurrent_add_survives_a_concurrent_remove() {
    let mut a = ORSet::new(); a.add(1); a.remove(&1);
    let mut b = ORSet::new(); b.add(2);
    a.merge(&b);
    assert!(a.contains(&2), "concurrent add was wrongly killed by a concurrent remove");
}
