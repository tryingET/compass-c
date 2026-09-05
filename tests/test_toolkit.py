from __future__ import annotations

import contextlib
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from compass_c import CompassError, Notebook, calculate
from compass_c.cli import main, parse_json
from install_skill import install

ROOT = Path(__file__).resolve().parents[1]


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "notebook.sqlite3"
        self.book = Notebook(self.path)
        started = self.book.start(
            "Choose an integration architecture", "medium", ["No remote writes"]
        )
        self.did, self.rev = started["decision_id"], started["revision"]

    def add(
        self,
        kind="assumption",
        content="A declared assumption",
        status="assumed",
        source="",
        depends_on=None,
    ):
        result = self.book.record(self.did, self.rev, kind, content, status, source, depends_on)
        self.rev = result["revision"]
        return result["note_id"]

    def test_start_has_no_authority(self):
        d = self.book.get(self.did)
        self.assertEqual(d["scope"], "analysis_only")
        self.assertEqual(d["action_permission"], "not_granted")

    def test_storage_survives_new_instance(self):
        self.add()
        self.assertEqual(len(Notebook(self.path).get(self.did)["notes"]), 1)

    def test_stale_revision_rejected(self):
        self.add()
        with self.assertRaises(CompassError) as ctx:
            self.book.record(self.did, 1, "test", "Check something")
        self.assertEqual(ctx.exception.code, "REVISION_CONFLICT")
        self.assertEqual(len(self.book.get(self.did)["notes"]), 1)

    def test_observed_needs_source(self):
        with self.assertRaises(CompassError):
            self.add("evidence", status="observed")
        self.assertEqual(self.book.get(self.did)["revision"], 1)

    def test_computed_source_not_treated_as_verified(self):
        nid = self.add("evidence", "A numerical result", "computed", "local-test-log")
        self.assertEqual(self.book.get(self.did)["notes"][0]["id"], nid)
        self.assertFalse(self.book.review(self.did)["source_verified"])

    def test_cross_decision_dependency_rejected(self):
        other = self.book.start("Other")
        note = self.book.record(other["decision_id"], 1, "assumption", "Other note")["note_id"]
        with self.assertRaises(CompassError):
            self.add(depends_on=[note])

    def test_missing_dependency_rejected(self):
        with self.assertRaises(CompassError):
            self.add(depends_on=["a" * 32])

    def test_transitive_invalidation(self):
        a = self.add()
        b = self.add("evidence", "Derived", "inferred", depends_on=[a])
        c = self.add("decision", "Select", "inferred", depends_on=[b])
        out = self.book.invalidate(self.did, self.rev, a, "Assumption changed")
        self.assertEqual(set(out["invalidated"]), {a, b, c})

    def test_invalidation_catches_unlinked_conclusion(self):
        a = self.add()
        c = self.add("decision", "Unlinked conclusion")
        out = self.book.invalidate(self.did, self.rev, a, "Unknown omitted dependency")
        self.assertIn(c, out["invalidated"])

    def test_stale_dependency_cannot_be_reused(self):
        a = self.add()
        self.rev = self.book.invalidate(self.did, self.rev, a, "Changed")["revision"]
        with self.assertRaises(CompassError) as ctx:
            self.add(depends_on=[a])
        self.assertEqual(ctx.exception.code, "STALE_DEPENDENCY")

    def test_invalidation_history_persisted(self):
        a = self.add()
        self.book.invalidate(self.did, self.rev, a, "Changed source")
        self.assertEqual(self.book.get(self.did)["invalidations"][0]["reason"], "Changed source")

    def test_concurrent_writes_do_not_lose_updates(self):
        def attempt(_):
            try:
                return self.book.record(self.did, 1, "test", "One competing update")["revision"]
            except CompassError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(attempt, range(8)))
        self.assertEqual(outcomes.count(2), 1)
        self.assertEqual(outcomes.count("REVISION_CONFLICT"), 7)
        self.assertEqual(len(self.book.get(self.did)["notes"]), 1)

    def test_bool_revision_is_not_integer(self):
        with self.assertRaises(CompassError):
            self.book.record(self.did, True, "test", "No coercion")

    def test_hostile_objects_rejected_without_equality(self):
        class Hostile:
            def __eq__(self, other):
                raise AssertionError("Untrusted equality invoked")

        with self.assertRaises(CompassError):
            self.book.start("Objective", Hostile())
        with self.assertRaises(CompassError):
            self.book.record(self.did, 1, Hostile(), "Bad kind")

    def test_duplicate_dependencies_rejected(self):
        a = self.add()
        with self.assertRaises(CompassError):
            self.add(depends_on=[a, a])

    def test_identifiers_cannot_be_paths(self):
        for value in ["../../etc/passwd", "' OR 1=1 --", "x" * 500, None]:
            with self.subTest(value=value), self.assertRaises(CompassError):
                self.book.get(value)

    def test_large_text_rejected(self):
        with self.assertRaises(CompassError):
            self.add(content="x" * 12001)

    def test_structural_review_is_not_verification(self):
        self.add("evidence", "Observed result", "observed", "example-source")
        self.add("alternative", "A")
        self.add("alternative", "B")
        self.add("test", "Discriminating check")
        self.add("limitation", "Toy environment only")
        self.add("decision", "Conditional choice")
        out = self.book.review(self.did)
        self.assertEqual(out["status"], "record_complete_not_verified")
        self.assertEqual(out["action_permission"], "not_granted")

    def test_assumption_not_promoted_to_evidence(self):
        self.add("evidence", "Unverified assertion", "assumed")
        out = self.book.review(self.did)
        self.assertTrue(any("only assumptions" in s for s in out["next_checks"]))

    def test_invalid_inputs_leave_state_unchanged(self):
        invalid = [None, [], {}, True, 3.0, 3, "", "x" * 12001]
        for value in invalid:
            with self.subTest(value=str(type(value))), self.assertRaises(CompassError):
                self.book.record(self.did, 1, "test", value)
        self.assertEqual(self.book.get(self.did)["revision"], 1)
        self.assertEqual(self.book.get(self.did)["notes"], [])


class CalculationTests(unittest.TestCase):
    def test_nominal_robust_matrix(self):
        out = calculate(
            "compare",
            {
                "actions": ["nominal", "robust", "abstain"],
                "scenarios": ["normal", "cheap_shift", "common_shift"],
                "payoffs": [[4.5, -1.2, -1.2], [2.95, 2.95, -1.8], [0, 0, 0]],
                "probabilities": [1, 0, 0],
            },
        )["result"]
        self.assertEqual(out["criterion_winners"]["expected_value"], ["nominal"])
        self.assertEqual(out["criterion_winners"]["maximin"], ["abstain"])
        self.assertFalse(out["criterion_chosen_by_tool"])

    def test_compare_does_not_invent_probabilities(self):
        out = calculate(
            "compare", {"actions": ["A", "B"], "scenarios": ["X"], "payoffs": [[2], [1]]}
        )["result"]
        self.assertNotIn("expected_value", out["criterion_winners"])
        self.assertIsNone(out["rows"][0]["expected"])

    def test_committee_independent(self):
        r = calculate("committee", {"members": 9, "accuracy": 0.8, "correlation": 0})["result"]
        self.assertAlmostEqual(r["majority_accuracy"], 0.98041856)

    def test_committee_correlated(self):
        r = calculate("committee", {"members": 9, "accuracy": 0.8, "correlation": 0.6})["result"]
        self.assertAlmostEqual(r["majority_accuracy"], 0.872167424)
        self.assertAlmostEqual(r["accuracy_given_unanimity"], 0.8164256739662874)

    def test_bundle_complementarity(self):
        r = calculate("bundle", {"test_accuracy": 0.95, "test_cost": 3, "gain": 100, "loss": 400})[
            "result"
        ]
        self.assertAlmostEqual(r["pair_value"], 20.25)
        self.assertEqual(r["single_test_value"], -3)

    def test_bundle_can_be_not_worthwhile(self):
        r = calculate("bundle", {"test_accuracy": 0.9, "test_cost": 3, "gain": 100, "loss": 400})[
            "result"
        ]
        self.assertAlmostEqual(r["pair_value"], -1)
        self.assertEqual(r["best_value_including_abstention"], 0)

    def test_delayed_aggressive_feedback_unstable(self):
        r = calculate("feedback", {"a": 1.2, "gain": 1.2, "delay": 1})["result"]
        self.assertAlmostEqual(r["spectral_radius"], math.sqrt(1.2))
        self.assertEqual(r["linear_asymptotic_stability"], "unstable")

    def test_delayed_moderate_feedback_stable(self):
        r = calculate("feedback", {"a": 1.2, "gain": 0.5, "delay": 1})["result"]
        self.assertAlmostEqual(r["spectral_radius"], math.sqrt(0.5))

    def test_feedback_boundary_not_declared_stable(self):
        r = calculate("feedback", {"a": 1, "gain": 0, "delay": 0})["result"]
        self.assertEqual(r["linear_asymptotic_stability"], "boundary_requires_analysis")

    def test_recovery_capacity_not_authority(self):
        r = calculate("recovery", {"capacity": 10, "committed": 0, "proposed": 9, "reserve": 2})
        self.assertFalse(r["result"]["capacity_condition_met"])
        self.assertFalse(r["result"]["reservation_enforced"])
        self.assertEqual(r["action_permission"], "not_granted")

    def test_infinite_tail(self):
        r = calculate(
            "tail", {"immediate": 12, "recurring": -1.5, "starts_at": 5, "discount": 0.95}
        )["result"]
        self.assertAlmostEqual(r["present_value"], -11.213428125)

    def test_tail_before_start(self):
        r = calculate(
            "tail",
            {"immediate": 12, "recurring": -1.5, "starts_at": 5, "discount": 0.95, "horizon": 4},
        )["result"]
        self.assertEqual(r["present_value"], 12)

    def test_tail_undiscounted_finite(self):
        r = calculate(
            "tail",
            {"immediate": 12, "recurring": -1.5, "starts_at": 5, "discount": 1, "horizon": 6},
        )["result"]
        self.assertEqual(r["present_value"], 9)

    def test_brier(self):
        self.assertAlmostEqual(
            calculate("brier", {"probabilities": [0.8, 0.2], "outcomes": [1, 0]})["result"][
                "brier_score"
            ],
            0.04,
        )

    def test_reject_nonfinite_and_bool(self):
        for x in [float("nan"), float("inf"), True]:
            with self.subTest(x=x), self.assertRaises(CompassError):
                calculate("feedback", {"a": x, "gain": 0.5, "delay": 1})

    def test_huge_integer_rejected_as_input_not_overflow(self):
        with self.assertRaises(CompassError):
            calculate("feedback", {"a": 10**1000, "gain": 0.5, "delay": 1})

    def test_tail_near_unit_discount_matches_direct_sum(self):
        d = 0.999999999999
        r = calculate(
            "tail",
            {"immediate": 12, "recurring": -1.5, "starts_at": 5, "discount": d, "horizon": 100},
        )["result"]
        self.assertAlmostEqual(
            r["present_value"], 12 + sum(-1.5 * d**t for t in range(5, 101)), places=9
        )

    def test_reject_unknown_and_missing_fields(self):
        for p in [{"a": 1}, {"a": 1, "gain": 0.5, "delay": 1, "override": True}]:
            with self.subTest(p=p), self.assertRaises(CompassError):
                calculate("feedback", p)

    def test_reject_unsupported_dynamics(self):
        with self.assertRaises(CompassError):
            calculate("feedback", {"a": 1.2, "gain": 0.5, "delay": 3})

    def test_reject_bad_probabilities(self):
        with self.assertRaises(CompassError):
            calculate(
                "compare",
                {"actions": ["a"], "scenarios": ["s"], "payoffs": [[1]], "probabilities": [0.5]},
            )

    def test_reject_even_committee(self):
        with self.assertRaises(CompassError):
            calculate("committee", {"members": 8, "accuracy": 0.8, "correlation": 0.6})

    def test_reject_unbounded_infinite_tail(self):
        with self.assertRaises(CompassError):
            calculate("tail", {"immediate": 12, "recurring": -1.5, "starts_at": 5, "discount": 1})


class InterfaceTests(unittest.TestCase):
    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(CompassError):
            parse_json('{"a":1,"a":2}')

    def test_json_nan_rejected(self):
        with self.assertRaises(CompassError):
            parse_json('{"a":NaN}')

    def test_cli_real_subprocess(self):
        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "compass_c",
                "calculate",
                "recovery",
                "--parameters",
                '{"capacity":10,"committed":0,"proposed":8,"reserve":2}',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(out["data"]["result"]["reserve_margin"], 0)

    def test_cli_error_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(
                ["calculate", "feedback", "--parameters", '{"a":true,"gain":0.5,"delay":1}']
            )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(buf.getvalue())["error"]["code"], "INVALID_INPUT")

    def test_install_is_self_contained(self):
        with tempfile.TemporaryDirectory() as t:
            path = install(Path(t))
            self.assertTrue((path / "SKILL.md").is_file())
            p = subprocess.run(
                [sys.executable, str(path / "scripts" / "compass.py"), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout.strip(), "0.3.0")

    def test_install_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            install(Path(t))
            with self.assertRaises(FileExistsError):
                install(Path(t))

    def test_install_dry_run_has_no_side_effect(self):
        with tempfile.TemporaryDirectory() as t:
            destination = install(Path(t) / "new", dry_run=True)
            self.assertFalse(destination.exists())
            self.assertFalse(destination.parent.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
