#!/usr/bin/env python3
"""quilt-jev invariant suite. Standard library only, no network.

The invariant under test is not "the picture looks right". It is:

    a grid's canonical artifact is the probability tensor.
    every rendering is a projection of it and says which one.
    any two renderings of the same tensor are diffable.

Run:  python3 -m unittest discover -s tests -v      (offline, no API key)
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import quilt_jev as q  # noqa: E402


def synth(size=8, seed=0):
    """A valid tensor built without touching the network."""
    import random
    rnd = random.Random(seed)
    pixels = []
    for y in range(size):
        for x in range(size):
            d = q.normalized([rnd.random() for _ in q.LABELS])
            pixels.append({"x": x, "y": y, "probabilities": d})
    return {"method": "palette", "size": size, "prompt": f"synthetic seed={seed}",
            "labels": list(q.LABELS), "palette": [list(q.PALETTE[l]) for l in q.LABELS],
            "pixels": pixels}


class TestTensorIsTheArtifact(unittest.TestCase):
    def test_valid_tensor_passes(self):
        ok, f = q.verify(synth())
        self.assertTrue(ok, f)

    def test_unnormalized_is_rejected(self):
        t = synth()
        t["pixels"][3]["probabilities"][0] += 0.5
        ok, f = q.verify(t)
        self.assertFalse(ok)
        self.assertTrue(any("not 1" in x for x in f), f)

    def test_out_of_range_probability_is_rejected(self):
        t = synth()
        t["pixels"][0]["probabilities"][2] = 1.4
        ok, f = q.verify(t)
        self.assertFalse(ok)

    def test_nan_probability_is_rejected(self):
        t = synth()
        t["pixels"][0]["probabilities"][2] = float("nan")
        ok, f = q.verify(t)
        self.assertFalse(ok)

    def test_wrong_cell_count_is_rejected(self):
        t = synth()
        t["pixels"].pop()
        ok, f = q.verify(t)
        self.assertFalse(ok)
        self.assertTrue(any("size*size" in x for x in f), f)

    def test_duplicate_coordinate_is_rejected(self):
        t = synth()
        t["pixels"][5]["x"] = t["pixels"][4]["x"]
        t["pixels"][5]["y"] = t["pixels"][4]["y"]
        ok, f = q.verify(t)
        self.assertFalse(ok)
        self.assertTrue(any("duplicate" in x for x in f), f)

    def test_arity_must_match_label_count(self):
        t = synth()
        t["pixels"][0]["probabilities"].pop()
        ok, f = q.verify(t)
        self.assertFalse(ok)

    def test_canonical_json_round_trips(self):
        t = synth()
        self.assertEqual(q.digest(t), q.digest(json.loads(q.canonical(t))))

    def test_two_equal_tensors_share_a_digest(self):
        self.assertEqual(q.digest(synth(seed=1)), q.digest(synth(seed=1)))
        self.assertNotEqual(q.digest(synth(seed=1)), q.digest(synth(seed=2)))


class TestEveryRenderIsLabelled(unittest.TestCase):
    def test_each_view_names_itself(self):
        t = synth()
        for view in ("paint", "argmax", "entropy", "margin", "tensor"):
            text, _ = q.RENDERERS[view](t)
            self.assertIn(f"view: {view.upper()}", text, view)

    def test_each_view_carries_the_tensor_digest(self):
        t = synth()
        want = q.digest(t)[:16]
        for view in ("paint", "argmax", "entropy", "margin", "tensor"):
            text, _ = q.RENDERERS[view](t)
            self.assertIn(want, text, view)


class TestRendersAreDiffable(unittest.TestCase):
    def test_renders_are_deterministic_in_process(self):
        t = synth()
        for view in ("paint", "argmax", "entropy", "margin", "tensor"):
            a, _ = q.RENDERERS[view](t)
            b, _ = q.RENDERERS[view](t)
            self.assertEqual(a, b, view)

    def test_renders_are_byte_identical_across_processes(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.tensor.json")
            q.write_tensor(synth(), path)
            for view in ("paint", "argmax", "entropy", "margin"):
                cmd = [sys.executable, os.path.join(ROOT, "quilt_jev.py"),
                       "render", "--from", path, "--view", view]
                a = subprocess.run(cmd, capture_output=True).stdout
                b = subprocess.run(cmd, capture_output=True).stdout
                self.assertEqual(a, b, f"{view} is not reproducible across processes")
                self.assertTrue(a, f"{view} produced no output")

    def test_a_changed_tensor_changes_the_digest(self):
        t = synth()
        before = q.digest(t)
        t["pixels"][10]["probabilities"] = q.normalized([0.99] + [0.01] * 15)
        self.assertNotEqual(before, q.digest(t))


class TestProjectionsUseTheFullDistribution(unittest.TestCase):
    """The thesis: the probabilities map is USED, not collapsed before drawing."""

    def test_entropy_and_margin_agree_on_a_one_hot_cell(self):
        self.assertAlmostEqual(q.uncertainty([1.0] + [0.0] * 15), 0.0, places=12)
        self.assertAlmostEqual(q.margin([1.0] + [0.0] * 15), 1.0, places=12)

    def test_entropy_is_maximal_on_a_uniform_cell(self):
        # Uniform over n labels: H = ln n, so 1-exp(-H) = 1 - 1/n.
        # For the 16-label palette that ceiling is 0.9375, never 1.0.
        u = q.uncertainty([1 / 16] * 16)
        self.assertAlmostEqual(u, 1 - 1 / 16, places=12)
        self.assertAlmostEqual(q.margin([1 / 16] * 16), 0.0, places=12)

    def test_uncertainty_ceiling_depends_on_label_count(self):
        self.assertAlmostEqual(q.uncertainty([0.5] * 2), 1 - 1 / 2, places=12)
        self.assertAlmostEqual(q.uncertainty([1 / 3] * 3), 1 - 1 / 3, places=12)
        self.assertLess(q.uncertainty([1 / 16] * 16), 1.0)

    def test_mean_colour_is_a_distribution_weighted_mix(self):
        # half black, half white -> grey, not either endpoint.
        self.assertEqual(q.mean_color([0.5, 0.5] + [0.0] * 14), [128, 128, 128])

    def test_entropy_ranks_cells(self):
        sharp = q.uncertainty([0.97, 0.01, 0.01, 0.01])
        dull = q.uncertainty([0.25, 0.25, 0.25, 0.25])
        self.assertLess(sharp, dull)

    def test_argmax_picks_the_top_label(self):
        d = [0.1, 0.7, 0.2]
        self.assertEqual(q.LABELS[q.argmax(d)], q.LABELS[1])

    def test_jsonl_row_is_self_contained(self):
        t = synth(4)
        rows = list(q.jsonl_rows(t))
        self.assertEqual(len(rows), 16)
        r = rows[0]
        for field in ("x", "y", "choice", "confidence", "probabilities"):
            self.assertIn(field, r)
        self.assertAlmostEqual(sum(r["probabilities"].values()), 1.0, places=9)
        self.assertEqual(r["choice"], max(r["probabilities"], key=r["probabilities"].get))


class TestTransportIsNotAnEmptyGrid(unittest.TestCase):
    """The fleet's signature failure: a dead call must never look like a result."""

    def test_dead_endpoint_raises_rather_than_returning_pixels(self):
        batch = q.build_batches("a barn", 8)
        old = q.ENDPOINT
        q.ENDPOINT = "http://127.0.0.1:9/v1/systemone"   # nothing listens here
        try:
            with self.assertRaises(q.TransportFailure):
                q.call(batch[0], "dummy", tries=2)
        finally:
            q.ENDPOINT = old

    def test_cli_exits_75_and_writes_no_tensor_on_transport_failure(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "should-not-exist.tensor.json")
            env = dict(os.environ, TYPESAFEAI_KEY="dummy",
                       JEV_BASE_URL="http://127.0.0.1:9")
            r = subprocess.run(
                [sys.executable, os.path.join(ROOT, "quilt_jev.py"),
                 "render", "a barn", "--size", "8", "--quiet", "--out", out],
                capture_output=True, env=env, cwd=d)
            self.assertEqual(r.returncode, 75, r.stderr.decode())
            self.assertIn(b"TRANSPORT_FAILURE", r.stderr)
            self.assertFalse(os.path.exists(out), "a failed call wrote a tensor")

    def test_rejected_key_is_named_as_schema_not_transport(self):
        env = dict(os.environ, TYPESAFEAI_KEY="apikey_not_a_real_key")
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "quilt_jev.py"),
             "render", "a barn", "--size", "8", "--quiet"],
            capture_output=True, env=env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(b"SCHEMA_FAILURE", r.stderr)


class TestUpstreamFixture(unittest.TestCase):
    """achimala/jev-paint's own recorded fixture must load and verify."""

    FIX = "/tmp/jev-paint/tests/fixtures/palette.json"

    @unittest.skipUnless(os.path.exists(FIX), "upstream fixture not present")
    def test_upstream_fixture_loads_and_verifies(self):
        with open(self.FIX, encoding="utf-8") as fh:
            t = q.upgrade(json.load(fh), self.FIX)
        ok, f = q.verify(t)
        self.assertTrue(ok, f)
        self.assertEqual(t["size"], 12)
        self.assertEqual(len(t["pixels"]), 144)


class TestTheArtifactIsNotDestroyed(unittest.TestCase):
    """Re-running a prompt must not silently destroy the previous evidence."""

    def test_second_distinct_tensor_gets_its_own_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.tensor.json")
            a = q.write_tensor_new(synth(seed=1), p)
            b = q.write_tensor_new(synth(seed=2), p)
            self.assertEqual(a, p)
            self.assertNotEqual(a, b)
            self.assertTrue(os.path.exists(p), "the first tensor was clobbered")
            self.assertTrue(os.path.exists(b))

    def test_identical_tensor_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.tensor.json")
            t = synth(seed=3)
            a = q.write_tensor_new(t, p)
            b = q.write_tensor_new(t, p)
            self.assertEqual(a, b, "an identical re-run created a spurious duplicate")
            self.assertFalse(os.path.exists(os.path.join(d, "t-2.tensor.json")))


class TestGridSizeIsTheAbstractionDial(unittest.TestCase):
    def test_batch_count_grows_with_the_square(self):
        self.assertEqual(len(q.build_batches("x", 8)), 1)
        self.assertEqual(len(q.build_batches("x", 12)), 1)
        self.assertEqual(len(q.build_batches("x", 16)), 2)
        self.assertEqual(len(q.build_batches("x", 24)), 4)
        self.assertEqual(len(q.build_batches("x", 32)), 8)

    def test_every_size_yields_exactly_size_squared_questions(self):
        for size in q.SIZES:
            n = sum(len(b["questions"]) for b in q.build_batches("x", size))
            self.assertEqual(n, size * size, size)
            keys = [k for b in q.build_batches("x", size) for k in b["questions"]]
            self.assertEqual(len(set(keys)), len(keys), f"{size}: duplicate keys")

    def test_unsupported_size_is_refused(self):
        with self.assertRaises(ValueError):
            q.build_batches("x", 13)
        with self.assertRaises(ValueError):
            q.build_batches("   ", 8)
        with self.assertRaises(ValueError):
            q.build_batches("x" * 2001, 8)

    def test_criteria_values_are_null_and_type_is_choice(self):
        b = q.build_batches("x", 8)[0]
        self.assertEqual(b["model"], "jev-latest")
        for spec in b["questions"].values():
            self.assertEqual(spec["type"], "choice")
            self.assertEqual(set(spec["criteria"].values()), {None})
            self.assertEqual(len(spec["criteria"]), 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
