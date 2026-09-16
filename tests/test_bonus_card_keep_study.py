"""Forced-keep bonus-card study: the setup policy, the flow plumbing, and the contrast."""

import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig
from wingspan_ai.agents.setup import (
    DefaultSetupPolicy,
    ForcedBonusCardSetupPolicy,
    InitialSelectionContext,
    PotentialPointsSetupPolicy,
)
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.rules.base_game import setup_base_game

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

FLOW_SPEC = importlib.util.spec_from_file_location(
    "simulation_batch_for_keep_study", REPO / "flows" / "simulation_batch.py"
)
assert FLOW_SPEC is not None and FLOW_SPEC.loader is not None
simulation_batch = importlib.util.module_from_spec(FLOW_SPEC)
FLOW_SPEC.loader.exec_module(simulation_batch)

CHEAP_SEARCH = PotentialPointsSearchConfig(
    search_depth=1, final_search_turns=0, determinization_samples=0
)


def _dealt_player(seed: int = 4):
    catalog = make_sample_catalog()
    state = setup_base_game(
        catalog, player_ids=["p1", "p2"], random_seed=seed, apply_initial_selection=False
    )
    return state, state.players[0]


class ForcedBonusCardSetupPolicyTests(TestCase):
    def test_keeps_the_dealt_card_at_the_index_and_nothing_else_changes(self) -> None:
        state, player = _dealt_player()
        self.assertEqual(len(player.bonus_cards), 2)
        dealt = [card.name for card in player.bonus_cards]
        for index in (0, 1):
            policy = ForcedBonusCardSetupPolicy(PotentialPointsSetupPolicy(), index)
            selection = policy.choose_initial_selection(player, InitialSelectionContext())
            self.assertEqual(selection.kept_bonus_card_names, [dealt[index]])
            self.assertEqual(selection.player_id, player.player_id)
            self.assertTrue(selection.kept_bird_names)
        # The forced policy must not mutate the dealt hand it was shown.
        self.assertEqual([card.name for card in player.bonus_cards], dealt)

    def test_birds_and_food_come_from_the_base_policy_given_the_card(self) -> None:
        _state, player = _dealt_player()
        forced = player.bonus_cards[1]
        restricted = player.model_copy(update={"bonus_cards": [forced]})
        expected = PotentialPointsSetupPolicy().choose_initial_selection(
            restricted, InitialSelectionContext()
        )
        actual = ForcedBonusCardSetupPolicy(
            PotentialPointsSetupPolicy(), 1
        ).choose_initial_selection(player, InitialSelectionContext())
        self.assertEqual(actual.kept_bird_names, expected.kept_bird_names)
        self.assertEqual(actual.starting_food, expected.starting_food)

    def test_policy_id_names_the_index_and_base(self) -> None:
        policy = ForcedBonusCardSetupPolicy(DefaultSetupPolicy(), 0)
        self.assertEqual(policy.policy_id, "forced_bonus_0:default_setup_v1")

    def test_out_of_range_index_is_an_error(self) -> None:
        _state, player = _dealt_player()
        with self.assertRaises(ValueError):
            ForcedBonusCardSetupPolicy(DefaultSetupPolicy(), 2).choose_initial_selection(
                player, InitialSelectionContext()
            )
        with self.assertRaises(ValueError):
            ForcedBonusCardSetupPolicy(DefaultSetupPolicy(), -1)


class ForcedKeepFlowTests(TestCase):
    def _run_arm(self, tmp_dir: str, index: int) -> list[dict]:
        return simulation_batch.run_simulation_batch(
            workbook_path="missing-workbook.xlsx",
            seeds=[4, 5],
            artifact_root=tmp_dir,
            persist_postgres=False,
            upload_artifacts=False,
            batch_kind="smoke",
            batch_label=f"force{index}",
            batch_id=f"force{index}_batch",
            player_agent_kinds=["potential_points", "greedy_immediate"],
            potential_points_search=CHEAP_SEARCH,
            forced_bonus_choice={"potential_points": index},
        )

    def test_forced_choice_applies_to_the_study_agent_only_and_is_recorded(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            results = self._run_arm(tmp_dir, 1)
            manifest = json.loads(
                Path(results[0]["batch_manifest"]["path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["games"][0]["forced_bonus_choice"], {"potential_points": 1})
            events_path = Path(manifest["games"][0]["artifact_dir"]) / "events.jsonl"
            setups = [
                json.loads(line)["payload"]
                for line in events_path.read_text().splitlines()
                if '"setup_selection_applied"' in line
            ]
            by_player = {payload["player_id"]: payload for payload in setups}
            self.assertTrue(by_player["player_1"]["setup_policy_id"].startswith("forced_bonus_1:"))
            self.assertFalse(by_player["player_2"]["setup_policy_id"].startswith("forced_bonus"))
            # Recorded discards make the counterfactual identifiable.
            self.assertEqual(len(by_player["player_1"]["discarded_bonus_card_names"]), 1)

    def test_contrast_pairs_the_two_arms_per_seed(self) -> None:
        from analysis.bonus_card_keep_contrast import load_arm, pair_arms, report

        with TemporaryDirectory() as tmp_dir:
            self._run_arm(tmp_dir, 0)
            self._run_arm(tmp_dir, 1)
            root = Path(tmp_dir)
            arm_a = load_arm(root / "smoke" / "force0")
            arm_b = load_arm(root / "smoke" / "force1")
            pairs = pair_arms(arm_a, arm_b, "potential_points")
            self.assertEqual(len(pairs), 2)
            for a, b in pairs:
                self.assertNotEqual(a.kept, b.kept)
                self.assertEqual({a.kept, a.discarded}, {b.kept, b.discarded})
            text = report(pairs)
            self.assertIn("Paired deals: 2", text)
            self.assertIn("| Card | n |", text)
