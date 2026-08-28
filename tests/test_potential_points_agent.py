from unittest import TestCase

from wingspan_ai.agents import GreedyBaselineAgent, PotentialPointsAgent, evaluate_state_potential
from wingspan_ai.content import make_sample_catalog
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
from wingspan_ai.state.models import BirdSlot


class PotentialPointsAgentTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_agent_prefers_resource_that_unlocks_high_value_future_bird(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=31)
        player = state.active_player
        cheap_bird = _bird(
            "Cheap Bird",
            points=1,
            food_cost={},
            habitats={Habitat.GRASSLAND},
        )
        expensive_bird = _bird(
            "Expensive Bird",
            points=9,
            food_cost={FoodType.INVERTEBRATE: 1},
            habitats={Habitat.FOREST},
        )
        player.hand = [cheap_bird, expensive_bird]
        player.food_tokens = {food_type: 0 for food_type in FoodType}
        state.birdfeeder.dice = [FoodType.INVERTEBRATE]
        state.bird_tray = []
        state.decks.bird_deck = []

        action = PotentialPointsAgent(final_search_turns=0).select_action(
            state,
            legal_actions_for_current_player(state),
        )

        self.assertEqual(action.action_type, ActionType.GAIN_FOOD)
        self.assertIn(FoodType.INVERTEBRATE, action.food_types)

    def test_final_turn_search_prefers_realized_points_over_dead_resources(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=32)
        player = state.active_player
        grassland_bird = _bird("Egg Bird", points=1, food_cost={}, habitats={Habitat.GRASSLAND})
        player.habitats[Habitat.GRASSLAND].append(BirdSlot(card=grassland_bird))
        player.hand = []
        player.action_cubes_available = 1
        state.round_state.round_number = 4
        state.birdfeeder.dice = [FoodType.SEED]

        action = PotentialPointsAgent().select_action(
            state,
            legal_actions_for_current_player(state),
        )

        self.assertEqual(action.action_type, ActionType.LAY_EGGS)

    def test_played_power_colors_contribute_to_engine_potential(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=33)
        player = state.active_player
        brown_food = _bird(
            "Brown Food Bird",
            points=1,
            food_cost={},
            power=Power(
                color=PowerColor.BROWN,
                text="Gain 1 [invertebrate] from the birdfeeder.",
                implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
            ),
        )
        teal_tuck = _bird(
            "Teal Tuck Bird",
            points=1,
            food_cost={},
            power=Power(
                color=PowerColor.TEAL,
                text="At end of round, tuck 1 [card] from your hand behind this bird.",
                implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
            ),
        )
        yellow_cache = _bird(
            "Yellow Cache Bird",
            points=1,
            food_cost={},
            power=Power(
                color=PowerColor.YELLOW,
                text="At the end of the game, cache 1 [seed] from your supply on this bird.",
                implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
            ),
        )
        player.habitats[Habitat.FOREST].append(BirdSlot(card=brown_food))
        player.habitats[Habitat.WETLAND].append(BirdSlot(card=teal_tuck))
        player.habitats[Habitat.GRASSLAND].append(BirdSlot(card=yellow_cache))
        player.hand = [
            _bird(
                "Needs Invertebrate",
                points=5,
                food_cost={FoodType.INVERTEBRATE: 1},
            )
        ]

        breakdown = evaluate_state_potential(state, player.player_id)

        self.assertGreater(breakdown.engine_power_potential, 0)

    def test_white_power_on_unplayed_bird_adds_future_one_shot_value(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=34)
        player = state.active_player
        player.hand = [
            _bird(
                "Plain Bird",
                points=2,
                food_cost={},
            )
        ]
        plain_breakdown = evaluate_state_potential(state, player.player_id)
        player.hand = [
            _bird(
                "White Draw Bird",
                points=2,
                food_cost={},
                power=Power(
                    color=PowerColor.WHITE,
                    text="When played: draw 1 [card].",
                    implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
                ),
            )
        ]

        white_breakdown = evaluate_state_potential(state, player.player_id)

        self.assertGreater(
            white_breakdown.playable_bird_potential,
            plain_breakdown.playable_bird_potential,
        )

    def test_handler_key_can_value_power_without_text_token_match(self) -> None:
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=35)
        player = state.active_player
        player.habitats[Habitat.WETLAND].append(
            BirdSlot(
                card=_bird(
                    "Registered Tuck Bird",
                    points=1,
                    food_cost={},
                    power=Power(
                        color=PowerColor.BROWN,
                        text="Custom registry-backed wording.",
                        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
                        handler_key="tuck_card",
                    ),
                )
            )
        )

        breakdown = evaluate_state_potential(state, player.player_id)

        self.assertGreater(breakdown.engine_power_potential, 0)

    def test_immediate_greedy_baseline_still_available(self) -> None:
        self.assertEqual(GreedyBaselineAgent().agent_id, "greedy_immediate_score")


def _bird(
    name: str,
    *,
    points: int,
    food_cost: dict[FoodType, int],
    habitats: set[Habitat] | None = None,
    power: Power | None = None,
) -> BirdCard:
    return BirdCard(
        common_name=name,
        scientific_name=f"{name} scientific",
        content_pack=ContentPack.CORE,
        habitats=habitats or {Habitat.FOREST, Habitat.GRASSLAND, Habitat.WETLAND},
        food_cost=FoodCost(fixed=food_cost),
        victory_points=points,
        nest_type=NestType.BOWL,
        egg_limit=4,
        wingspan_cm=40,
        power=power
        or Power(
            color=PowerColor.NONE,
            implementation_status=PowerImplementationStatus.NO_OP_FOR_V1,
        ),
    )
