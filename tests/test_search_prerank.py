"""Beam pre-ranking: cheap scores cut candidates before expansion."""

from unittest import TestCase

from wingspan_ai.agents import PotentialPointsAgent, profiling
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.rules.base_game import legal_actions_for_current_player, setup_base_game


class SearchPrerankTests(TestCase):
    def setUp(self) -> None:
        self.catalog = make_sample_catalog()
        self.state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=9)
        self.legal = legal_actions_for_current_player(self.state)
        self.kwargs = dict(search_depth=3, final_search_turns=8, determinization_samples=1)

    def _counts(self, **agent_kwargs) -> dict:
        agent = PotentialPointsAgent(**self.kwargs, **agent_kwargs)
        with profiling.activate("select_action") as profiler:
            action = agent.select_action(self.state, self.legal)
        nodes = profiler.finish().summary_payload()["nodes"]
        return {
            "action": action,
            "leaves": nodes.get("terminal_value", {}).get("count", 0),
            "prerank": nodes.get("prerank_children", {}).get("count", 0),
        }

    def test_leaf_mode_evaluates_fewer_leaves_and_records_the_cut(self) -> None:
        none = self._counts(search_prerank="none")
        beam = self._counts(search_prerank="beam")
        leaf = self._counts(search_prerank="beam_leaf", search_leaf_candidates=3)
        self.assertEqual(none["prerank"], 0)
        self.assertGreater(beam["prerank"], 0)
        self.assertLess(beam["leaves"], none["leaves"])
        self.assertLess(leaf["leaves"], beam["leaves"])
        self.assertIn(leaf["action"], self.legal)

    def test_switch_is_validated_and_recorded(self) -> None:
        with self.assertRaises(ValueError):
            PotentialPointsAgent(search_prerank="psychic")
        with self.assertRaises(ValueError):
            PotentialPointsAgent(search_leaf_candidates=0)
        agent = PotentialPointsAgent(search_prerank="beam_leaf", **self.kwargs)
        summary = agent.summarize_decision(self.state, self.legal, self.legal[0])
        self.assertEqual(summary["search_prerank"], "beam_leaf")
        self.assertEqual(summary["search_leaf_candidates"], 6)
