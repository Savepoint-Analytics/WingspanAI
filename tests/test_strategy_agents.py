from unittest import TestCase

from wingspan_ai.agents import (
    MonteCarloRolloutAgent,
    StrategyArchetype,
    StrategyArchetypeAgent,
)
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.schemas import FoodType
from wingspan_ai.rules.actions import ActionType
from wingspan_ai.rules.base_game import legal_actions_for_current_player, setup_base_game
from wingspan_ai.state.models import BirdSlot


class StrategyAgentTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_egg_focus_agent_prefers_laying_eggs_when_available(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=5)
        player = state.active_player
        card = next(card for card in self.catalog.birds if card.egg_limit >= 2)
        player.habitats[next(iter(card.habitats))].append(BirdSlot(card=card))

        action = StrategyArchetypeAgent(StrategyArchetype.EGG_FOCUS).choose_action(state)

        self.assertEqual(action.action_type, ActionType.LAY_EGGS)

    def test_monte_carlo_agent_selects_legal_action(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=6)
        agent = MonteCarloRolloutAgent(rollout_count=2, rollout_depth=2, random_seed=6)

        action = agent.choose_action(state)

        self.assertIn(action, legal_actions_for_current_player(state))

    def test_monte_carlo_agent_reports_budget_usage(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=8)
        legal_actions = legal_actions_for_current_player(state)
        agent = MonteCarloRolloutAgent(
            rollout_count=3,
            rollout_depth=2,
            max_decision_time_ms=0.001,
            random_seed=8,
        )

        action = agent.select_action(state, legal_actions)
        summary = agent.summarize_decision(state, legal_actions, action)

        self.assertIn(action, legal_actions)
        self.assertEqual(summary["policy"], "monte_carlo_rollout")
        self.assertTrue(summary["budget_exhausted"])
        self.assertLessEqual(summary["evaluated_action_count"], 12)
        self.assertEqual(summary["total_completed_rollouts"], 0)
        self.assertTrue(summary["selected_used_static_fallback"])
        self.assertEqual(summary["configured_max_decision_time_ms"], 0.001)

    def test_monte_carlo_agent_respects_candidate_cap(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=9)
        legal_actions = legal_actions_for_current_player(state)
        agent = MonteCarloRolloutAgent(
            rollout_count=1,
            rollout_depth=1,
            max_candidate_actions=3,
            random_seed=9,
        )

        action = agent.select_action(state, legal_actions)
        summary = agent.summarize_decision(state, legal_actions, action)

        self.assertIn(action, legal_actions)
        self.assertEqual(summary["evaluated_action_count"], 3)
        self.assertEqual(summary["configured_max_candidate_actions"], 3)

    def test_archetype_agent_rejects_empty_action_list(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1"], random_seed=7)
        state.round_state.game_over = True

        with self.assertRaises(ValueError):
            StrategyArchetypeAgent(StrategyArchetype.CARD_DRAW).choose_action(state)


class ArchetypeDistinctnessTests(TestCase):
    """Archetypes must be behaviourally distinguishable, not variations on greedy.

    The 2026-08-31 round robin found `engine_builder` and `bonus_card_focus`
    posting identical win rates in every matchup with near-identical action
    mixes. The cause was that several archetypes scored only PLAY_BIRD actions
    and returned 0 for everything else, so whenever a bird was unaffordable they
    collapsed into the same greedy fallback. These tests guard against that
    regressing.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def _state(self):
        return setup_base_game(
            self.catalog,
            player_ids=["player_1", "player_2"],
            random_seed=4,
        )

    def test_every_archetype_has_an_opinion_on_every_legal_action(self) -> None:
        from wingspan_ai.agents.archetypes import _score_action_for_archetype
        from wingspan_ai.rules.base_game import legal_actions_for_current_player, score_player

        state = self._state()
        actions = legal_actions_for_current_player(state)
        before = score_player(state, state.active_player.player_id).total
        self.assertGreater(len(actions), 3, "need a varied action set for this test")

        for archetype in StrategyArchetype:
            scored = [
                _score_action_for_archetype(state, action, archetype, before)
                for action in actions
            ]
            # A zero for every non-play-bird action is the exact degeneracy that
            # made two archetypes indistinguishable.
            self.assertTrue(
                all(value != 0 for value in scored),
                f"{archetype.value} scored some actions 0, leaving it opinionless",
            )

    def test_archetypes_weight_their_signature_action_family_highest(self) -> None:
        """The archetype bonus, not the composite score, carries the identity.

        The composite score also contains immediate points, so a free
        high-value bird can and should outrank the signature action. What must
        hold is that the archetype's own weighting favours its family.
        """

        from wingspan_ai.agents.archetypes import (
            _card_draw_bonus,
            _egg_focus_bonus,
            _food_acceleration_bonus,
        )
        from wingspan_ai.rules.base_game import legal_actions_for_current_player

        state = self._state()
        actions = legal_actions_for_current_player(state)
        by_family = {}
        for action in actions:
            by_family.setdefault(action.action_type, action)

        cases = [
            (_food_acceleration_bonus, ActionType.GAIN_FOOD, "food_acceleration"),
            (_card_draw_bonus, ActionType.DRAW_CARDS, "card_draw"),
            (_egg_focus_bonus, ActionType.LAY_EGGS, "egg_focus"),
        ]
        for bonus_fn, signature_family, label in cases:
            if signature_family not in by_family:
                continue
            signature_value = bonus_fn(state, by_family[signature_family])
            for family, action in by_family.items():
                if family is signature_family:
                    continue
                self.assertGreater(
                    signature_value,
                    bonus_fn(state, action),
                    f"{label} should weight {signature_family.value} above {family.value}",
                )

    def test_accumulator_archetypes_have_diminishing_returns(self) -> None:
        """A saturated hand or food store must stop dominating the score."""

        from wingspan_ai.agents.archetypes import _card_draw_bonus, _food_acceleration_bonus
        from wingspan_ai.rules.actions import LegalAction

        state = self._state()
        player = state.active_player
        draw_action = LegalAction(
            action_type=ActionType.DRAW_CARDS,
            player_id=player.player_id,
            draw_from_deck=True,
            draw_from_deck_count=1,
        )
        food_action = LegalAction(
            action_type=ActionType.GAIN_FOOD,
            player_id=player.player_id,
            food_type=FoodType.SEED,
            food_types=(FoodType.SEED,),
        )

        player.hand = []
        player.food_tokens = {food: 0 for food in player.food_tokens}
        hungry_draw = _card_draw_bonus(state, draw_action)
        hungry_food = _food_acceleration_bonus(state, food_action)

        player.hand = list(state.decks.bird_deck[:12])
        player.food_tokens = {food: 6 for food in player.food_tokens}
        sated_draw = _card_draw_bonus(state, draw_action)
        sated_food = _food_acceleration_bonus(state, food_action)

        self.assertLess(sated_draw, hungry_draw)
        self.assertLess(sated_food, hungry_food)

    def test_round_goal_chase_lays_eggs_for_an_egg_goal(self) -> None:
        """Egg-based round goals were previously unchaseable: LAY_EGGS scored 0."""

        from wingspan_ai.agents.archetypes import _round_goal_chase_bonus
        from wingspan_ai.content.schemas import ContentPack, RoundGoal
        from wingspan_ai.rules.actions import LegalAction

        state = self._state()
        state.round_goals = [
            RoundGoal(name="[egg] in [bowl]", content_pack=ContentPack.CORE)
            for _ in range(4)
        ]
        lay_action = LegalAction(
            action_type=ActionType.LAY_EGGS,
            player_id=state.active_player.player_id,
            egg_count=2,
        )

        self.assertGreater(_round_goal_chase_bonus(state, lay_action), 5.0)
