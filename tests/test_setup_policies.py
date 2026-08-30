from unittest import TestCase

from wingspan_ai.agents import (
    InitialSelectionContext,
    NetValueSetupPolicy,
    PotentialPointsAgent,
    PotentialPointsSetupPolicy,
    RandomLegalAgent,
    StrategyArchetype,
    StrategyArchetypeAgent,
)
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.schemas import (
    BirdCard,
    BonusCard,
    ContentPack,
    FoodCost,
    FoodType,
    Habitat,
    NestType,
    Power,
    PowerColor,
    PowerImplementationStatus,
)
from wingspan_ai.rules.base_game import BIRD_FOOD_SELECTION_TOTAL
from wingspan_ai.simulation import run_single_game
from wingspan_ai.state.models import PlayerState
from wingspan_ai.telemetry.events import EventName


class SetupPolicyTests(TestCase):
    def test_potential_points_setup_policy_returns_valid_selection(self) -> None:
        player = _player_with_opening_hand()

        selection = PotentialPointsSetupPolicy().choose_initial_selection(player)

        self.assertEqual(selection.player_id, "p1")
        self.assertEqual(len(selection.kept_bonus_card_names), 1)
        self.assertEqual(
            len(selection.kept_bird_names) + len(selection.starting_food),
            BIRD_FOOD_SELECTION_TOTAL,
        )
        self.assertTrue(set(selection.kept_bird_names).issubset(_hand_names(player)))

    def test_archetype_setup_policy_biases_card_draw_opening(self) -> None:
        player = _player_with_opening_hand()
        agent = StrategyArchetypeAgent(StrategyArchetype.CARD_DRAW)

        selection = agent.choose_initial_selection(player)

        self.assertIn("Wetland Draw Engine", selection.kept_bird_names)

    def test_archetype_setup_policy_biases_egg_opening(self) -> None:
        player = _player_with_opening_hand()
        agent = StrategyArchetypeAgent(StrategyArchetype.EGG_FOCUS)

        selection = agent.choose_initial_selection(player)

        self.assertIn("Grassland Egg Engine", selection.kept_bird_names)

    def test_net_value_setup_policy_uses_public_context_denial_prior(self) -> None:
        player = _player_with_opening_hand()
        context = InitialSelectionContext(
            bird_tray=(
                _bird(
                    "Public Wetland Tuck Threat",
                    habitats={Habitat.WETLAND},
                    food={FoodType.FISH: 1},
                    points=4,
                    power_text="Tuck 1 [card] from your hand behind this bird.",
                ),
            ),
            round_goal_names=("Birds in [wetland]",),
            player_count=2,
        )

        selection = NetValueSetupPolicy(denial_weight=2.0).choose_initial_selection(
            player,
            context,
        )

        self.assertIn("Wetland Draw Engine", selection.kept_bird_names)

    def test_runner_records_agent_setup_policy_id(self) -> None:
        result = run_single_game(
            make_sample_catalog(),
            [
                RandomLegalAgent(agent_id="random_p1", random_seed=1),
                PotentialPointsAgent(agent_id="potential_p2"),
            ],
            random_seed=1,
            max_turns=1,
        )

        setup_events = [
            event
            for event in result.events
            if event.event_name == EventName.SETUP_SELECTION_APPLIED
        ]
        p2_setup = next(event for event in setup_events if event.player_id == "player_2")

        self.assertEqual(p2_setup.payload["selection_source"], "agent")
        self.assertEqual(p2_setup.payload["setup_policy_id"], "potential_points_setup_v1")


def _player_with_opening_hand() -> PlayerState:
    return PlayerState(
        player_id="p1",
        hand=[
            _bird(
                "Wetland Draw Engine",
                habitats={Habitat.WETLAND},
                food={FoodType.FISH: 1},
                points=3,
                power_text="Draw 1 [card].",
            ),
            _bird(
                "Grassland Egg Engine",
                habitats={Habitat.GRASSLAND},
                food={FoodType.SEED: 1},
                points=3,
                egg_limit=5,
                power_text="Lay 1 [egg] on this bird.",
            ),
            _bird(
                "Forest Food Engine",
                habitats={Habitat.FOREST},
                food={FoodType.INVERTEBRATE: 1},
                points=2,
                power_text="Gain 1 [seed] from the supply.",
            ),
            _bird(
                "Plain High Point Bird",
                habitats={Habitat.FOREST},
                food={FoodType.RODENT: 2},
                points=7,
                power_text=None,
            ),
            _bird(
                "Flexible Low Cost Bird",
                habitats={Habitat.FOREST, Habitat.GRASSLAND},
                food={FoodType.FRUIT: 1},
                points=1,
                power_text=None,
            ),
        ],
        bonus_cards=[
            BonusCard(
                name="Fishery Manager",
                content_packs={ContentPack.CORE},
                condition="Birds that eat fish.",
            ),
            BonusCard(
                name="Backyard Birder",
                content_packs={ContentPack.CORE},
                condition="Birds worth fewer than 4 points.",
            ),
        ],
    )


def _bird(
    name: str,
    *,
    habitats: set[Habitat],
    food: dict[FoodType, int],
    points: int,
    egg_limit: int = 3,
    power_text: str | None,
) -> BirdCard:
    return BirdCard(
        common_name=name,
        scientific_name=f"{name} scientific",
        content_pack=ContentPack.CORE,
        habitats=habitats,
        food_cost=FoodCost(fixed=food),
        victory_points=points,
        nest_type=NestType.BOWL,
        egg_limit=egg_limit,
        wingspan_cm=35,
        power=Power(
            color=PowerColor.BROWN if power_text else PowerColor.NONE,
            text=power_text,
            implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        ),
    )


def _hand_names(player: PlayerState) -> set[str]:
    return {card.common_name for card in player.hand}
