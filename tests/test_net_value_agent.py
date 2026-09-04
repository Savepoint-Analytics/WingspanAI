from unittest import TestCase, skipIf

from wingspan_ai.agents import (
    NetValueOpponentResponseAgent,
    PublicOpponentBeliefModel,
)
from wingspan_ai.agents.net_value import _opponent_card_value
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.schemas import (
    BirdCard,
    ContentPack,
    FoodCost,
    FoodType,
    Habitat,
    NestType,
    Power,
    PowerColor,
    PowerImplementationStatus,
)
from wingspan_ai.rules.actions import ActionType
from wingspan_ai.rules.base_game import legal_actions_for_current_player, setup_base_game
from wingspan_ai.state.models import BirdSlot, to_public_state


class NetValueOpponentResponseAgentTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_agent_selects_legal_action_and_reports_net_value(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=41)
        agent = NetValueOpponentResponseAgent(
            max_candidate_actions=4,
            max_opponent_response_actions=3,
        )
        legal_actions = legal_actions_for_current_player(state)

        action = agent.select_action(state, legal_actions)
        summary = agent.summarize_decision(state, legal_actions, action)

        self.assertIn(action, legal_actions)
        self.assertEqual(summary["policy"], "net_value_opponent_response")
        self.assertEqual(summary["opponent_model"], "public_observation_belief_v0")
        self.assertIn("public observations", summary["information_boundary"])
        self.assertLessEqual(summary["evaluated_action_count"], 4)
        self.assertEqual(summary["max_opponent_response_actions"], 3)
        self.assertIn("net_margin_delta", summary["selected_breakdown"])
        self.assertIn("selected_opponent_response", summary)

    def test_public_belief_model_does_not_use_opponent_hidden_hand(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=43)
        model = PublicOpponentBeliefModel()
        first_estimate = model.potential_total(
            state,
            observer_player_id="p1",
            opponent_id="p2",
        )

        state.players[1].hand = list(reversed(self.catalog.birds[: len(state.players[1].hand)]))
        second_estimate = model.potential_total(
            state,
            observer_player_id="p1",
            opponent_id="p2",
        )

        self.assertEqual(first_estimate, second_estimate)

    def test_tray_card_draw_carries_shared_denial_value(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=42)
        state.bird_tray = [
            _bird("High Threat Wetland Engine", points=8),
            _bird("Plain Low Bird", points=1),
        ]
        legal_actions = [
            action
            for action in legal_actions_for_current_player(state)
            if action.action_type == ActionType.DRAW_CARDS and action.tray_index == 0
        ]

        evaluation = NetValueOpponentResponseAgent().evaluate_actions(state, legal_actions)[0]

        self.assertGreater(evaluation.breakdown.shared_denial_value, 0)


def _bird(name: str, *, points: int) -> BirdCard:
    return BirdCard(
        common_name=name,
        scientific_name=f"{name} scientific",
        content_pack=ContentPack.CORE,
        habitats={Habitat.WETLAND},
        food_cost=FoodCost(fixed={FoodType.FISH: 1}),
        victory_points=points,
        nest_type=NestType.BOWL,
        egg_limit=4,
        wingspan_cm=40,
        power=Power(
            color=PowerColor.BROWN,
            text="Tuck 1 [card] from your hand behind this bird.",
            implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
            handler_key="tuck_card",
        ),
    )


@skipIf(
    not DEFAULT_WORKBOOK_PATH.exists(),
    f"{DEFAULT_WORKBOOK_PATH} is not present",
)
class OpponentAwareDenialTests(TestCase):
    """Denial must reflect what a card is worth to the opponent, not in the abstract.

    The previous `_public_card_threat_value` read only the card, so it could not
    tell a repeatable brown engine from a one-shot white power, had no notion of
    tempo, and could not express "this is exactly what my opponent needs".
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        cls.by_name = {bird.common_name: bird for bird in cls.catalog.birds}

    def setUp(self) -> None:
        self.state = setup_base_game(
            self.catalog, player_ids=["player_1", "player_2"], random_seed=1
        )
        self.opponent = self.state.players[1]
        self.opponent.food_tokens = {food: 3 for food in self.opponent.food_tokens}
        self.opponent.habitats[Habitat.FOREST] = []

    def _denial(self, card_name: str, turns: int) -> float:
        self.opponent.action_cubes_available = turns
        public_state = to_public_state(self.state)
        public_opponent = next(
            p for p in public_state.players if p.player_id == "player_2"
        )
        return _opponent_card_value(self.by_name[card_name], public_state, public_opponent)

    def test_repeatable_brown_engine_outvalues_a_one_shot_white_power(self) -> None:
        # Blue-Gray Gnatcatcher is brown "Gain 1 [invertebrate]" - it fires on
        # every habitat activation. American Goldfinch is white "Gain 3 [seed]" -
        # it fires once. The old model scored the one-shot HIGHER.
        gnatcatcher = self.by_name["Blue-Gray Gnatcatcher"]
        goldfinch = self.by_name["American Goldfinch"]
        self.assertEqual(gnatcatcher.power.color, PowerColor.BROWN)
        self.assertEqual(goldfinch.power.color, PowerColor.WHITE)

        self.assertGreater(
            self._denial("Blue-Gray Gnatcatcher", 8),
            self._denial("American Goldfinch", 8),
        )

    def test_denial_scales_with_opponent_turns_remaining(self) -> None:
        """Denying an engine early is worth more than denying it at game end."""

        early = self._denial("Blue-Gray Gnatcatcher", 16)
        late = self._denial("Blue-Gray Gnatcatcher", 1)

        self.assertGreater(early, late)
        self.assertGreater(early / max(late, 0.01), 2.0)

    def test_card_the_opponent_cannot_play_is_not_worth_denying(self) -> None:
        """Blue-Gray Gnatcatcher is forest-only; a full forest makes it useless."""

        with_room = self._denial("Blue-Gray Gnatcatcher", 8)
        self.opponent.habitats[Habitat.FOREST] = [
            BirdSlot(card=self.by_name["Mallard"]) for _ in range(5)
        ]
        without_room = self._denial("Blue-Gray Gnatcatcher", 8)

        self.assertGreater(with_room, 0.0)
        self.assertEqual(without_room, 0.0)

    def test_unaffordable_cards_are_discounted(self) -> None:
        """Food tokens are public, so a card they cannot pay for is worth less."""

        rich = self._denial("Blue-Gray Gnatcatcher", 8)
        self.opponent.food_tokens = {food: 0 for food in self.opponent.food_tokens}
        poor = self._denial("Blue-Gray Gnatcatcher", 8)

        self.assertLess(poor, rich)

    def test_denial_ignores_hidden_hand_contents(self) -> None:
        """Hand size is public; hand contents are not.

        Swapping which cards the opponent holds, while keeping the count fixed,
        must not change the denial estimate — otherwise the agent is reading
        information it is not entitled to.
        """

        self.opponent.hand = list(self.state.decks.bird_deck[:5])
        with_first_hand = self._denial("Blue-Gray Gnatcatcher", 8)

        self.opponent.hand = list(self.state.decks.bird_deck[5:10])
        with_second_hand = self._denial("Blue-Gray Gnatcatcher", 8)

        self.assertEqual(len(self.opponent.hand), 5)
        self.assertEqual(with_first_hand, with_second_hand)
