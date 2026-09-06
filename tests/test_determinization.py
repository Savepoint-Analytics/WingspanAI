from collections import Counter
from unittest import TestCase
from unittest.mock import patch

from wingspan_ai.agents import GreedyBaselineAgent, PotentialPointsAgent
from wingspan_ai.agents.determinization import determinization_seed_material, determinize_state
from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.rules.actions import ActionType
from wingspan_ai.rules.base_game import (
    apply_action,
    legal_actions_for_current_player,
    setup_base_game,
)
from wingspan_ai.simulation.replay import canonical_state_json


def _names(cards) -> Counter:
    return Counter(card.common_name for card in cards)


class DeterminizeStateTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def _state(self, seed: int = 7):
        state = setup_base_game(self.catalog, player_ids=["p1", "p2", "p3"], random_seed=seed)
        # Advance a few turns so opponents hold cards drawn in play, not only setup.
        for _ in range(4):
            state = apply_action(state, legal_actions_for_current_player(state)[0])
        return state

    def test_public_and_own_private_information_are_preserved(self) -> None:
        state = self._state()
        player_id = state.active_player.player_id
        sample = determinize_state(state, player_id, sample_index=0)

        own = next(p for p in state.players if p.player_id == player_id)
        own_sample = next(p for p in sample.players if p.player_id == player_id)
        self.assertEqual(own.model_dump(), own_sample.model_dump())
        self.assertEqual(state.bird_tray, sample.bird_tray)
        self.assertEqual(state.birdfeeder, sample.birdfeeder)
        self.assertEqual(state.round_goals, sample.round_goals)
        self.assertEqual(state.round_state, sample.round_state)
        self.assertEqual(state.decks.bird_discard, sample.decks.bird_discard)
        for before, after in zip(state.players, sample.players, strict=True):
            self.assertEqual(before.player_id, after.player_id)
            self.assertEqual(len(before.hand), len(after.hand))
            self.assertEqual(len(before.bonus_cards), len(after.bonus_cards))
            self.assertEqual(before.habitats, after.habitats)
            self.assertEqual(before.food_tokens, after.food_tokens)

    def test_hidden_cards_are_redealt_from_the_unseen_pool(self) -> None:
        state = self._state()
        player_id = state.active_player.player_id

        def unseen_birds(s):
            pool = _names(s.decks.bird_deck)
            for p in s.players:
                if p.player_id != player_id:
                    pool += _names(p.hand)
            return pool

        def unseen_bonus(s):
            pool = Counter(card.name for card in s.decks.bonus_deck)
            for p in s.players:
                if p.player_id != player_id:
                    pool += Counter(card.name for card in p.bonus_cards)
            return pool

        sample = determinize_state(state, player_id, sample_index=0)
        self.assertEqual(unseen_birds(state), unseen_birds(sample))
        self.assertEqual(unseen_bonus(state), unseen_bonus(sample))
        self.assertEqual(len(state.decks.bird_deck), len(sample.decks.bird_deck))

    def test_samples_are_reproducible_and_distinct(self) -> None:
        state = self._state()
        player_id = state.active_player.player_id
        first = determinize_state(state, player_id, sample_index=0)
        again = determinize_state(state, player_id, sample_index=0)
        other = determinize_state(state, player_id, sample_index=1)
        self.assertEqual(canonical_state_json(first), canonical_state_json(again))
        self.assertNotEqual(canonical_state_json(first), canonical_state_json(other))
        deck_names = [card.common_name for card in state.decks.bird_deck]
        self.assertNotEqual(deck_names, [card.common_name for card in first.decks.bird_deck])
        # Future feeder rolls derive from the seed, so it is resampled too.
        self.assertNotEqual(state.random_seed, first.random_seed)
        self.assertNotEqual(first.random_seed, other.random_seed)

    def test_seed_material_excludes_game_id(self) -> None:
        state = self._state()
        material = determinization_seed_material(state, "p1", 3)
        self.assertNotIn(state.game_id, material)
        self.assertIn(str(state.random_seed), material)
        self.assertIn(str(state.round_state.global_turn_number), material)

    def test_original_state_is_untouched(self) -> None:
        state = self._state()
        before = canonical_state_json(state)
        determinize_state(state, state.active_player.player_id, sample_index=0)
        self.assertEqual(before, canonical_state_json(state))

    def test_true_state_actions_are_legal_in_the_sample(self) -> None:
        state = self._state()
        player_id = state.active_player.player_id
        sample = determinize_state(state, player_id, sample_index=2)
        self.assertEqual(
            legal_actions_for_current_player(state),
            legal_actions_for_current_player(sample),
        )

    def test_true_state_actions_are_legal_with_an_empty_feeder(self) -> None:
        state = self._state()
        state.birdfeeder.dice = []
        player_id = state.active_player.player_id
        sample = determinize_state(state, player_id, sample_index=2)
        self.assertEqual(
            legal_actions_for_current_player(state),
            legal_actions_for_current_player(sample),
        )

    def test_reroll_outcomes_differ_across_samples(self) -> None:
        state = self._state()
        state.birdfeeder.dice = []
        player_id = state.active_player.player_id
        reroll = next(
            action
            for action in legal_actions_for_current_player(state)
            if action.action_type == ActionType.GAIN_FOOD and action.reroll_birdfeeder
        )
        rolls = {
            tuple(apply_action(determinize_state(state, player_id, index), reroll).birdfeeder.dice)
            for index in range(8)
        }
        self.assertGreater(len(rolls), 1)


class DeterminizedSelectionTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_zero_samples_scores_the_true_state(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=3)
        agent = PotentialPointsAgent(determinization_samples=0)
        legal_actions = legal_actions_for_current_player(state)
        with patch("wingspan_ai.agents.potential_points.determinize_state") as mocked:
            agent.select_action(state, legal_actions)
        mocked.assert_not_called()

    def test_samples_are_averaged_per_action(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=3)
        legal_actions = legal_actions_for_current_player(state)
        agent = PotentialPointsAgent(determinization_samples=3)
        n = len(legal_actions)
        # Action 0 wins on two samples narrowly; action 1 wins big on one.
        # Averaging must pick action 1; a per-sample vote would pick action 0.
        per_sample = [
            [(1.0, 0.0)] + [(0.0, 0.0)] * (n - 1),
            [(1.0, 0.0)] + [(0.0, 0.0)] * (n - 1),
            [(0.0, 0.0), (9.0, 0.0)] + [(0.0, 0.0)] * (n - 2),
        ]
        calls: list[int] = []

        def fake_scores(sample_state, actions):
            calls.append(sample_state.random_seed)
            return per_sample[len(calls) - 1]

        with (
            patch.object(agent, "_score_actions", side_effect=fake_scores),
            patch(
                "wingspan_ai.agents.potential_points.determinize_state",
                side_effect=lambda s, pid, i: s.model_copy(update={"random_seed": i}),
            ),
        ):
            chosen = agent.select_action(state, legal_actions)
        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(chosen, legal_actions[1])

    def test_determinized_agent_plays_a_full_game(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=11)
        agents = {
            "p1": PotentialPointsAgent(
                agent_id="det", search_depth=2, final_search_turns=2, determinization_samples=2
            ),
            "p2": GreedyBaselineAgent(agent_id="plain"),
        }
        turns = 0
        while not state.round_state.game_over and turns < 200:
            legal_actions = legal_actions_for_current_player(state)
            agent = agents[state.active_player.player_id]
            state = apply_action(state, agent.select_action(state, legal_actions))
            turns += 1
        self.assertTrue(state.round_state.game_over)

    def test_config_round_trip(self) -> None:
        config = PotentialPointsSearchConfig(determinization_samples=4)
        self.assertEqual(config.as_manifest_payload()["determinization_samples"], 4)
        default = PotentialPointsSearchConfig()
        self.assertEqual(
            (default.search_depth, default.final_search_turns, default.determinization_samples),
            (3, 8, 4),
        )
