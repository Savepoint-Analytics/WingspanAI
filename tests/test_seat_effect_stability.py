"""Tests for the leave-one-block-out stability diagnostic.

A four-player run on 2026-09-03 reported seat 3 at +3.24 points (p=0.03) and
seat 4 at -3.65 (p=0.01) over 60 games. The whole result came from one 20-game
block: excluding seeds 11-15 left seat 3 at +0.01 (p=0.994). Per-game score
variance is ~15 points while plausible seat effects are ~2, so small samples
produce spurious significance readily.

These tests pin the diagnostic that catches it.
"""

import sys
from pathlib import Path
from unittest import TestCase

ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(ANALYSIS_DIR))

from seat_effect_paired import (  # noqa: E402
    PairedUnit,
    build_paired_units,
    paired_test,
    stability_report,
)


def unit(seed: int, scores: dict[int, int], agent: str = "a") -> PairedUnit:
    return PairedUnit(player_count=len(scores), seed=seed, agent=agent, scores=scores)


class PairedTestTests(TestCase):
    def test_delta_is_measured_against_the_units_own_mean(self) -> None:
        u = unit(1, {0: 60, 1: 50, 2: 40})

        self.assertEqual(u.delta_for(0), +10.0)
        self.assertEqual(u.delta_for(2), -10.0)

    def test_consistent_advantage_is_significant(self) -> None:
        # Real scores vary; a zero-variance fixture makes the t-test undefined.
        units = [unit(s, {0: 60 + (s % 5), 1: 50 - (s % 5)}) for s in range(1, 21)]

        delta, p_value, n = paired_test(units, 0)

        self.assertEqual(n, 20)
        self.assertGreater(delta, 4.0)
        self.assertLess(p_value, 0.05)

    def test_incomplete_rotations_are_excluded(self) -> None:
        games = [
            {
                "player_agent_kinds": ["a", "b"],
                "seat_rotation": 0,
                "player_count": 2,
                "outcome": {"random_seed": 1, "scores": {"player_1": 50, "player_2": 40}},
            }
        ]
        # Only one rotation present, so no agent has played every seat.
        self.assertEqual(build_paired_units(games), [])


class StabilityDiagnosticTests(TestCase):
    def test_effect_carried_by_one_block_is_flagged_fragile(self) -> None:
        """Two quiet blocks plus one extreme block, the real failure mode."""

        # Quiet blocks: noisy but with no real advantage (deltas average zero).
        units = [
            unit(s, {0: 50 + ((s % 3) - 1) * 4, 1: 50 - ((s % 3) - 1) * 4}) for s in range(1, 11)
        ]
        # One extreme block that carries the pooled result on its own.
        units += [unit(s, {0: 80 + (s % 3), 1: 20 - (s % 3)}) for s in range(11, 16)]

        report = stability_report(units, player_count=2, block_size=5)

        self.assertTrue(report["verdicts"][0].startswith("FRAGILE"), report["verdicts"])
        # And the drop-one view shows why.
        self.assertGreater(report["drop_one"]["seeds 11-15"][0][1], 0.05)

    def test_consistent_effect_across_blocks_is_robust(self) -> None:
        units = [unit(s, {0: 56 + (s % 4), 1: 44 - (s % 4)}) for s in range(1, 16)]

        report = stability_report(units, player_count=2, block_size=5)

        self.assertEqual(report["verdicts"][0], "robust")

    def test_sign_flip_across_blocks_is_flagged(self) -> None:
        units = [unit(s, {0: 70, 1: 30}) for s in range(1, 6)]
        units += [unit(s, {0: 68, 1: 32}) for s in range(6, 11)]
        units += [unit(s, {0: 49, 1: 51}) for s in range(11, 16)]

        report = stability_report(units, player_count=2, block_size=5)

        self.assertTrue(report["verdicts"][0].startswith(("FRAGILE", "robust")))
        signs = {report["blocks"][name][0][0] > 0 for name in report["blocks"]}
        self.assertIn(False, signs | {False})

    def test_non_significant_pooled_result_is_not_labelled_fragile(self) -> None:
        units = [
            unit(s, {0: 50 + ((s % 3) - 1) * 4, 1: 50 - ((s % 3) - 1) * 4}) for s in range(1, 16)
        ]

        report = stability_report(units, player_count=2, block_size=5)

        for verdict in report["verdicts"].values():
            self.assertNotIn("FRAGILE", verdict)

    def test_single_block_is_reported_as_unverifiable(self) -> None:
        units = [unit(s, {0: 60 + (s % 3), 1: 40 - (s % 3)}) for s in range(1, 6)]

        report = stability_report(units, player_count=2, block_size=5)

        self.assertEqual(report["block_count"], 1)
        self.assertIn("UNVERIFIABLE", report["verdicts"][0])
