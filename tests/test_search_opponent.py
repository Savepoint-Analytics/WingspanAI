"""Opponent models inside the potential-points search."""

from unittest import TestCase

from wingspan_ai.agents import GreedyBaselineAgent, PotentialPointsAgent
from wingspan_ai.agents.potential_points import (
    PotentialPointsSearchConfig,
    _play_opponent_turns_in_place,
    _search_action_value,
)
from wingspan_ai.agents.search_opponent import (
    BeliefSearchOpponentModel,
    GreedySearchOpponentModel,
    OracleTypeSearchOpponentModel,
    build_search_opponent_model,
)
from wingspan_ai.belief import DEFAULT_PROFILE_MODELS, OpponentProfile
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.rules.actions import ActionType
from wingspan_ai.rules.base_game import (
    apply_action,
    legal_actions_for_current_player,
    setup_base_game,
)
from wingspan_ai.simulation.runner import run_single_game


def _opponent_turn_state(catalog, random_seed: int = 7):
    """A state where the opponent of ``player_1`` is about to act."""

    state = setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=random_seed)
    branch = apply_action(state, legal_actions_for_current_player(state)[0])
    assert branch.active_player.player_id == "p2"
    return branch


class GreedySearchOpponentModelTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_greedy_model_is_the_historic_greedy_baseline(self) -> None:
        """The default must reproduce every archived search decision bit for bit."""

        model = GreedySearchOpponentModel()
        baseline = GreedyBaselineAgent(agent_id="search_opponent_model")
        for seed in range(1, 6):
            branch = _opponent_turn_state(self.catalog, seed)
            legal_actions = legal_actions_for_current_player(branch)
            self.assertEqual(
                model.select_action(branch, legal_actions),
                baseline.select_action(branch, legal_actions),
            )

    def test_search_without_a_model_uses_greedy(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=7)
        action = legal_actions_for_current_player(state)[0]
        implicit = _search_action_value(state, action, "p1", depth=2, beam_width=None)
        explicit = _search_action_value(
            state,
            action,
            "p1",
            depth=2,
            beam_width=None,
            opponent_model=GreedySearchOpponentModel(),
        )
        self.assertEqual(implicit, explicit)

    def test_greedy_observation_is_a_no_op(self) -> None:
        agent = PotentialPointsAgent(search_opponent_model="greedy")
        self.assertIsInstance(agent.opponent_model, GreedySearchOpponentModel)
        branch = _opponent_turn_state(self.catalog)
        agent.observe_action(branch, legal_actions_for_current_player(branch)[0], "p2")
        self.assertEqual(agent.opponent_model.telemetry_payload(), {"model_id": "greedy"})

    def test_agent_default_is_belief(self) -> None:
        """Default flipped 2026-09-16 after the arm in search_opponent_model_test.md."""

        agent = PotentialPointsAgent()
        self.assertEqual(agent.search_opponent_model, "belief")
        self.assertIsInstance(agent.opponent_model, BeliefSearchOpponentModel)


class BeliefSearchOpponentModelTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_picks_inside_the_most_likely_available_family(self) -> None:
        model = BeliefSearchOpponentModel(owner_agent_id="pp")
        for seed in range(1, 8):
            branch = _opponent_turn_state(self.catalog, seed)
            legal_actions = legal_actions_for_current_player(branch)
            chosen = model.select_action(branch, legal_actions)
            available = {action.action_type for action in legal_actions}
            ranked = model.predict_family(branch, "p2").ranked_families()
            expected_family = next(family for family, _probability in ranked if family in available)
            self.assertEqual(chosen.action_type, expected_family, f"seed {seed}")

    def test_falls_back_when_the_predicted_family_has_no_legal_action(self) -> None:
        model = BeliefSearchOpponentModel(owner_agent_id="pp")
        branch = _opponent_turn_state(self.catalog)
        legal_actions = legal_actions_for_current_player(branch)
        predicted = model.predict_family(branch, "p2").most_likely_family
        remaining = [a for a in legal_actions if a.action_type != predicted]
        self.assertTrue(remaining)
        chosen = model.select_action(branch, remaining)
        self.assertIn(chosen, remaining)

    def test_selection_is_deterministic(self) -> None:
        model = BeliefSearchOpponentModel(owner_agent_id="pp")
        branch = _opponent_turn_state(self.catalog)
        legal_actions = legal_actions_for_current_player(branch)
        first = model.select_action(branch, legal_actions)
        for _ in range(3):
            self.assertEqual(model.select_action(branch, legal_actions), first)

    def test_within_family_pick_prefers_points_then_greedy_tiebreak(self) -> None:
        """Inside play-bird the proxy must agree with greedy's immediate score."""

        model = BeliefSearchOpponentModel(owner_agent_id="pp")
        greedy = GreedyBaselineAgent()
        checked = 0
        for seed in range(1, 12):
            branch = _opponent_turn_state(self.catalog, seed)
            plays = [
                a
                for a in legal_actions_for_current_player(branch)
                if a.action_type == ActionType.PLAY_BIRD
            ]
            if len(plays) < 2:
                continue
            checked += 1
            self.assertEqual(
                model.select_action(branch, plays), greedy.select_action(branch, plays)
            )
        self.assertGreater(checked, 0)

    def test_family_prediction_reads_only_public_information(self) -> None:
        """Changing the opponent's hidden hand at fixed hand size changes nothing."""

        model = BeliefSearchOpponentModel(owner_agent_id="pp")
        branch = _opponent_turn_state(self.catalog)
        before = model.predict_family(branch, "p2").probabilities

        altered = branch.model_copy(deep=True)
        opponent = next(p for p in altered.players if p.player_id == "p2")
        hand_size = len(opponent.hand)
        self.assertGreater(hand_size, 0)
        opponent.hand = list(altered.decks.bird_deck[:hand_size])
        after = model.predict_family(altered, "p2").probabilities

        self.assertEqual(before, after)

    def test_observe_updates_opponents_and_skips_own_seat(self) -> None:
        model = BeliefSearchOpponentModel(owner_agent_id="pp")
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=7)
        for player in state.players:
            player.agent_id = "pp" if player.player_id == "p1" else "other"

        own_action = legal_actions_for_current_player(state)[0]
        model.observe_action(state, own_action, "p1")
        self.assertEqual(model.belief_states, {})

        branch = apply_action(state, own_action)
        opponent_action = legal_actions_for_current_player(branch)[0]
        model.observe_action(branch, opponent_action, "p2")
        self.assertEqual(model.belief_state_for("p2").observation_count, 1)
        posterior = model.belief_state_for("p2").profile_posterior
        self.assertAlmostEqual(sum(posterior.values()), 1.0)
        self.assertEqual(set(posterior), set(DEFAULT_PROFILE_MODELS))

    def test_search_branches_do_not_write_the_posterior(self) -> None:
        model = BeliefSearchOpponentModel(owner_agent_id="pp")
        branch = _opponent_turn_state(self.catalog)
        _play_opponent_turns_in_place(branch, "p1", model)
        self.assertEqual(branch.active_player.player_id, "p1")
        self.assertEqual(model.belief_state_for("p2").observation_count, 0)

    def test_search_runs_end_to_end_with_the_belief_model(self) -> None:
        agent = PotentialPointsAgent(
            search_depth=2,
            final_search_turns=8,
            determinization_samples=0,
            search_opponent_model="belief",
        )
        self.assertIsInstance(agent.opponent_model, BeliefSearchOpponentModel)
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=7)
        legal_actions = legal_actions_for_current_player(state)
        scores = agent._score_actions(state, legal_actions)
        self.assertEqual(len(scores), len(legal_actions))
        self.assertTrue(all(score[0] > float("-inf") for score in scores))
        self.assertIn(agent.select_action(state, legal_actions), legal_actions)

    def test_runner_feeds_the_posterior_and_telemetry_records_it(self) -> None:
        agent = PotentialPointsAgent(
            agent_id="pp_belief",
            search_depth=1,
            final_search_turns=0,
            determinization_samples=0,
            search_opponent_model="belief",
        )
        result = run_single_game(
            self.catalog,
            [agent, GreedyBaselineAgent(agent_id="greedy")],
            random_seed=3,
        )
        self.assertTrue(result.state.round_state.game_over)
        model = agent.opponent_model
        self.assertIsInstance(model, BeliefSearchOpponentModel)
        self.assertEqual(set(model.belief_states), {"player_2"})
        self.assertGreater(model.belief_state_for("player_2").observation_count, 10)

        payload = model.telemetry_payload()
        self.assertEqual(payload["model_id"], "belief")
        self.assertIn("player_2", payload["opponent_belief_states"])
        self.assertIn(
            payload["opponent_belief_states"]["player_2"]["most_likely_profile"],
            {profile.value for profile in OpponentProfile},
        )


class OracleTypeSearchOpponentModelTests(TestCase):
    def setUp(self) -> None:
        self.catalog = make_sample_catalog()

    def test_known_kinds_start_at_the_converged_posterior_and_never_update(self) -> None:
        model = build_search_opponent_model("oracle", owner_agent_id="pp")
        self.assertIsInstance(model, OracleTypeSearchOpponentModel)
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=7)
        for player in state.players:
            player.agent_id = "pp" if player.player_id == "p1" else "engine_builder_p2"
        distribution = model.predict_family(state, "p2")
        posterior = distribution.profile_posterior
        self.assertAlmostEqual(sum(posterior.values()), 1.0, places=3)
        self.assertGreater(posterior[OpponentProfile.FOOD_ACCELERATION], 0.4)
        self.assertNotAlmostEqual(posterior[OpponentProfile.EGG_FOCUS], 1 / 6, places=2)
        branch = apply_action(state, legal_actions_for_current_player(state)[0])
        model.observe_action(branch, legal_actions_for_current_player(branch)[0], "p2")
        self.assertEqual(model.belief_state_for("p2").observation_count, 0)
        self.assertEqual(model.belief_state_for("p2").profile_posterior, posterior)
        self.assertEqual(model.telemetry_payload()["oracle_fixed_players"], ["p2"])

    def test_unknown_kinds_fall_back_to_ordinary_updating(self) -> None:
        model = OracleTypeSearchOpponentModel(owner_agent_id="pp")
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=7)
        for player in state.players:
            player.agent_id = "pp" if player.player_id == "p1" else "mystery_p2"
        branch = apply_action(state, legal_actions_for_current_player(state)[0])
        model.observe_action(branch, legal_actions_for_current_player(branch)[0], "p2")
        self.assertEqual(model.belief_state_for("p2").observation_count, 1)
        self.assertEqual(model.telemetry_payload()["oracle_fixed_players"], [])

    def test_agent_accepts_the_oracle_switch(self) -> None:
        agent = PotentialPointsAgent(
            search_depth=1,
            final_search_turns=0,
            determinization_samples=0,
            search_opponent_model="oracle",
        )
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=7)
        for player in state.players:
            player.agent_id = agent.agent_id if player.player_id == "p1" else "greedy_immediate_p2"
        legal_actions = legal_actions_for_current_player(state)
        self.assertIn(agent.select_action(state, legal_actions), legal_actions)


class BeliefApplySearchOpponentModelTests(TestCase):
    def test_picks_greedily_inside_the_predicted_family(self) -> None:
        from wingspan_ai.agents.search_opponent import BeliefApplySearchOpponentModel

        catalog = make_sample_catalog()
        model = build_search_opponent_model("belief_apply", owner_agent_id="pp")
        self.assertIsInstance(model, BeliefApplySearchOpponentModel)
        branch = _opponent_turn_state(catalog)
        legal = legal_actions_for_current_player(branch)
        chosen = model.select_action(branch, legal)
        family = model.predict_family(branch, branch.active_player.player_id)
        ranked = [f for f, _ in family.ranked_families() if f in {a.action_type for a in legal}]
        self.assertEqual(chosen.action_type, ranked[0])
        pool = [a for a in legal if a.action_type == ranked[0]]
        self.assertEqual(chosen, GreedyBaselineAgent(agent_id="g").select_action(branch, pool))
        agent = PotentialPointsAgent(
            search_depth=2,
            final_search_turns=8,
            determinization_samples=0,
            search_opponent_model="belief_apply",
        )
        state = setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=7)
        actions = legal_actions_for_current_player(state)
        self.assertIn(agent.select_action(state, actions), actions)


class SearchOpponentConfigTests(TestCase):
    def test_config_and_manifest_carry_the_switch(self) -> None:
        payload = PotentialPointsSearchConfig().as_manifest_payload()
        self.assertEqual(payload["search_opponent_model"], "belief")
        self.assertEqual(payload["search_opponent_holdout_share"], 0.05)
        self.assertEqual(payload["search_opponent_holdout_model"], "greedy")
        self.assertEqual(
            PotentialPointsSearchConfig(search_opponent_model="greedy").as_manifest_payload()[
                "search_opponent_model"
            ],
            "greedy",
        )

    def test_decision_summary_records_the_model(self) -> None:
        catalog = make_sample_catalog()
        agent = PotentialPointsAgent(
            search_depth=1, final_search_turns=0, search_opponent_model="belief"
        )
        state = setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=7)
        legal_actions = legal_actions_for_current_player(state)
        summary = agent.summarize_decision(state, legal_actions, legal_actions[0])
        self.assertEqual(summary["search_opponent_model"], "belief")
        self.assertEqual(summary["opponent_model"]["model_id"], "belief")

    def test_unknown_model_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PotentialPointsAgent(search_opponent_model="psychic")
        with self.assertRaises(ValueError):
            build_search_opponent_model("psychic", owner_agent_id="pp")


class HoldoutTests(TestCase):
    """A deterministic minority of games keeps the previous model as a control."""

    def test_draw_is_stable_and_uniform_enough(self) -> None:
        from wingspan_ai.agents.search_opponent import holdout_draw

        self.assertEqual(holdout_draw("a"), holdout_draw("a"))
        self.assertNotEqual(holdout_draw("a"), holdout_draw("b"))
        draws = [holdout_draw(str(i)) for i in range(5000)]
        self.assertTrue(all(0.0 <= d < 1.0 for d in draws))
        self.assertAlmostEqual(sum(draws) / len(draws), 0.5, delta=0.03)

    def test_share_is_honoured_over_many_games(self) -> None:
        from wingspan_ai.agents.search_opponent import resolve_search_opponent_model

        lineup = ("potential_points", "greedy_immediate")
        held = sum(
            resolve_search_opponent_model(
                "belief",
                holdout_share=0.05,
                holdout_model="greedy",
                random_seed=seed,
                lineup=lineup,
                lineup_position=0,
            )[1]
            for seed in range(1, 4001)
        )
        self.assertGreater(held / 4000, 0.03)
        self.assertLess(held / 4000, 0.07)

    def test_zero_share_and_same_model_never_hold_out(self) -> None:
        from wingspan_ai.agents.search_opponent import resolve_search_opponent_model

        for seed in range(1, 200):
            self.assertEqual(
                resolve_search_opponent_model(
                    "belief",
                    holdout_share=0.0,
                    holdout_model="greedy",
                    random_seed=seed,
                    lineup=("a", "b"),
                    lineup_position=0,
                ),
                ("belief", False),
            )
            self.assertEqual(
                resolve_search_opponent_model(
                    "belief",
                    holdout_share=1.0,
                    holdout_model="belief",
                    random_seed=seed,
                    lineup=("a", "b"),
                    lineup_position=0,
                ),
                ("belief", False),
            )

    def test_holdout_is_keyed_on_seed_lineup_and_position_not_seat(self) -> None:
        """The same game must hold out in every seat rotation, so pairing survives."""

        config = PotentialPointsSearchConfig(search_opponent_holdout_share=0.5)
        lineup = ("potential_points", "greedy_immediate")
        for seed in range(1, 60):
            first = config.resolve_opponent_model(
                random_seed=seed, lineup=lineup, lineup_position=0
            )
            again = config.resolve_opponent_model(
                random_seed=seed, lineup=lineup, lineup_position=0
            )
            self.assertEqual(first, again)
        outcomes = {
            config.resolve_opponent_model(random_seed=seed, lineup=lineup, lineup_position=0)
            for seed in range(1, 60)
        }
        self.assertEqual(outcomes, {("belief", False), ("greedy", True)})

    def test_flow_records_the_effective_model_per_seat(self) -> None:
        from flows.simulation_batch import _make_agent

        config = PotentialPointsSearchConfig(
            search_depth=1, final_search_turns=0, search_opponent_holdout_share=1.0
        )
        agent = _make_agent(
            "potential_points",
            seat="p1",
            random_seed=3,
            potential_points_search=config,
            lineup=("potential_points", "greedy_immediate"),
        )
        self.assertEqual(agent.search_opponent_model, "greedy")
        agent = _make_agent(
            "potential_points",
            seat="p1",
            random_seed=3,
            potential_points_search=PotentialPointsSearchConfig(
                search_depth=1, final_search_turns=0, search_opponent_holdout_share=0.0
            ),
            lineup=("potential_points", "greedy_immediate"),
        )
        self.assertEqual(agent.search_opponent_model, "belief")

    def test_invalid_holdout_settings_are_rejected(self) -> None:
        from wingspan_ai.agents.search_opponent import resolve_search_opponent_model

        with self.assertRaises(ValueError):
            resolve_search_opponent_model(
                "belief",
                holdout_share=1.5,
                holdout_model="greedy",
                random_seed=1,
                lineup=("a",),
                lineup_position=0,
            )
        with self.assertRaises(ValueError):
            resolve_search_opponent_model(
                "belief",
                holdout_share=0.1,
                holdout_model="psychic",
                random_seed=1,
                lineup=("a",),
                lineup_position=0,
            )

    def test_guardrail_report_splits_games_by_effective_model(self) -> None:
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from analysis.holdout_guardrail import report, split_by_model

        def game(seed: int, model: str, own: int, other: int) -> dict:
            return {
                "player_agent_kinds": ["potential_points", "greedy_immediate"],
                "seat_rotation": 0,
                "player_count": 2,
                "outcome": {
                    "random_seed": seed,
                    "scores": {"player_1": own, "player_2": other},
                },
                "search_opponent_models": {
                    "potential_points_p1": {"model": model, "holdout": model != "belief"}
                },
            }

        games = [game(1, "belief", 80, 50), game(2, "belief", 70, 75), game(3, "greedy", 60, 40)]
        rows = split_by_model(games)
        self.assertEqual({m: len(r) for m, r in rows.items()}, {"belief": 2, "greedy": 1})
        self.assertEqual([r[1] for r in rows["belief"]], [1.0, 0.0])
        text = report(rows)
        self.assertIn("| `belief` | 2 | 75.00 | 0.500 |", text)
        self.assertIn("too few to read", text)
