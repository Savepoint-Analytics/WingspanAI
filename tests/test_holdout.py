"""Standing holdouts across config fields, and the fast/copy child expansion."""

from unittest import TestCase, skipIf

from wingspan_ai.agents import PotentialPointsAgent
from wingspan_ai.agents.holdout import Holdout, holdout_draw, resolve_holdouts
from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.rules.base_game import (
    apply_action,
    legal_actions_for_current_player,
    setup_base_game,
)
from wingspan_ai.simulation.replay import state_hash


class HoldoutResolutionTests(TestCase):
    def test_each_field_draws_independently_and_records_what_it_changed(self) -> None:
        holdouts = (Holdout("a", "old_a", 0.5), Holdout("b", True, 0.5), Holdout("c", 1, 0.0))
        seen_a = seen_b = seen_c = 0
        for seed in range(1, 201):
            effective, applied = resolve_holdouts(
                {"a": "new_a", "b": False, "c": 2},
                holdouts,
                random_seed=seed,
                lineup=("x", "y"),
                lineup_position=0,
            )
            seen_a += "a" in applied
            seen_b += "b" in applied
            seen_c += "c" in applied
            for field in applied:
                self.assertEqual(
                    effective[field], next(h.value for h in holdouts if h.field == field)
                )
        self.assertTrue(60 < seen_a < 140)
        self.assertTrue(60 < seen_b < 140)
        self.assertEqual(seen_c, 0)

    def test_a_field_already_at_the_holdout_value_is_never_counted(self) -> None:
        effective, applied = resolve_holdouts(
            {"a": "old"},
            (Holdout("a", "old", 1.0),),
            random_seed=1,
            lineup=("x",),
            lineup_position=0,
        )
        self.assertEqual((effective, applied), ({"a": "old"}, []))

    def test_share_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            Holdout("a", 1, 1.5)

    def test_draw_is_stable(self) -> None:
        self.assertEqual(holdout_draw("k"), holdout_draw("k"))

    def test_config_resolves_legacy_and_generic_holdouts_together(self) -> None:
        config = PotentialPointsSearchConfig(
            search_opponent_holdout_share=1.0,
            holdouts=(Holdout("mechanic_synergy", True, 1.0),),
        )
        effective, applied = config.resolve_effective(
            random_seed=3, lineup=("potential_points", "greedy_immediate"), lineup_position=0
        )
        self.assertEqual(applied, ["search_opponent_model", "mechanic_synergy"])
        self.assertEqual(effective["search_opponent_model"], "greedy")
        self.assertTrue(effective["mechanic_synergy"])
        self.assertEqual(set(effective), set(config.AGENT_FIELDS))
        # The agent accepts exactly the effective fields.
        agent = PotentialPointsAgent(agent_id="pp", **effective)
        self.assertTrue(agent.mechanic_synergy)

    def test_legacy_opponent_holdout_keeps_its_key(self) -> None:
        """Games held out since 2026-09-16 must stay the same games."""

        config = PotentialPointsSearchConfig()
        lineup = ("potential_points", "archetype_engine_builder")
        held = [
            seed
            for seed in range(1, 11)
            if "search_opponent_model"
            in config.resolve_effective(random_seed=seed, lineup=lineup, lineup_position=0)[1]
        ]
        self.assertEqual(held, [10])


class SetupPolicyHoldoutTests(TestCase):
    def test_flow_reverts_a_minority_of_games_to_the_held_out_opener(self) -> None:
        from flows import simulation_batch
        from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig

        config = PotentialPointsSearchConfig(
            holdouts=(Holdout("setup_policy", "potential_points_setup_v3_keep3", 1.0),)
        )
        agent = simulation_batch._make_agent(
            "potential_points",
            seat="p1",
            setup_policy_kind="control",
            random_seed=4,
            potential_points_search=config,
            lineup=("potential_points", "greedy_immediate"),
        )
        self.assertEqual(agent.setup_policy.policy_id, "potential_points_setup_v3_keep3")
        self.assertEqual(agent.holdouts_applied, ["setup_policy"])
        recorded = simulation_batch._search_holdouts([agent], {agent.agent_id: config})
        self.assertEqual(
            recorded[agent.agent_id]["effective"]["setup_policy"],
            "potential_points_setup_v3_keep3",
        )
        # Share 0 never reverts; the effective opener is still recorded.
        config = PotentialPointsSearchConfig(
            holdouts=(Holdout("setup_policy", "potential_points_setup_v3_keep3", 0.0),)
        )
        agent = simulation_batch._make_agent(
            "potential_points",
            seat="p1",
            setup_policy_kind="control",
            random_seed=4,
            potential_points_search=config,
            lineup=("potential_points", "greedy_immediate"),
        )
        self.assertEqual(agent.setup_policy.policy_id, "default_setup_v1")
        self.assertEqual(agent.holdouts_applied, [])
        self.assertEqual(
            simulation_batch._search_holdouts([agent], {agent.agent_id: config})[agent.agent_id][
                "effective"
            ]["setup_policy"],
            "default_setup_v1",
        )


@skipIf(not DEFAULT_WORKBOOK_PATH.exists(), "workbook required")
class FastExpansionTests(TestCase):
    def test_fast_and_copy_paths_agree_on_every_child(self) -> None:
        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        state = setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=7)
        for action in legal_actions_for_current_player(state):
            full = apply_action(state, action)
            fast = apply_action(state, action, trusted=True, lean=True)
            # The lean copy drops the audit trail; only this transition's draws survive.
            self.assertEqual(
                fast.rng_draw_records, full.rng_draw_records[len(state.rng_draw_records) :]
            )
            fast.rng_draw_records = list(full.rng_draw_records)
            self.assertEqual(state_hash(full), state_hash(fast))

    def test_agent_decisions_are_identical_under_both_expansions(self) -> None:
        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        state = setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=7)
        legal = legal_actions_for_current_player(state)
        kwargs = dict(search_depth=2, final_search_turns=8, determinization_samples=1)
        fast = PotentialPointsAgent(search_child_expansion="fast", **kwargs)
        copy = PotentialPointsAgent(search_child_expansion="copy", **kwargs)
        self.assertEqual(fast.select_action(state, legal), copy.select_action(state, legal))
        self.assertEqual(fast._score_actions(state, legal), copy._score_actions(state, legal))
        with self.assertRaises(ValueError):
            PotentialPointsAgent(search_child_expansion="teleport")
