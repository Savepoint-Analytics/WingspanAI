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
    build_search_opponent_model,
)
from wingspan_ai.belief import OpponentProfile
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

    def test_agent_default_is_greedy_and_observation_is_a_no_op(self) -> None:
        agent = PotentialPointsAgent()
        self.assertEqual(agent.search_opponent_model, "greedy")
        self.assertIsInstance(agent.opponent_model, GreedySearchOpponentModel)
        branch = _opponent_turn_state(self.catalog)
        agent.observe_action(branch, legal_actions_for_current_player(branch)[0], "p2")
        self.assertEqual(agent.opponent_model.telemetry_payload(), {"model_id": "greedy"})


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
        self.assertEqual(set(posterior), set(OpponentProfile))

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


class SearchOpponentConfigTests(TestCase):
    def test_config_and_manifest_carry_the_switch(self) -> None:
        self.assertEqual(
            PotentialPointsSearchConfig().as_manifest_payload()["search_opponent_model"], "greedy"
        )
        self.assertEqual(
            PotentialPointsSearchConfig(search_opponent_model="belief").as_manifest_payload()[
                "search_opponent_model"
            ],
            "belief",
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
            PotentialPointsAgent(search_opponent_model="oracle")
        with self.assertRaises(ValueError):
            build_search_opponent_model("oracle", owner_agent_id="pp")
