from unittest import TestCase

from pydantic import ValidationError

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
    RulesModule,
    RulesetMetadata,
)


class ContentSchemaTests(TestCase):
    def test_bird_card_accepts_core_economy_fields(self) -> None:
        bird = BirdCard(
            common_name="American Robin",
            scientific_name="Turdus migratorius",
            content_pack=ContentPack.CORE,
            habitats={Habitat.FOREST, Habitat.GRASSLAND, Habitat.WETLAND},
            food_cost=FoodCost(fixed={FoodType.INVERTEBRATE: 1, FoodType.FRUIT: 1}),
            victory_points=1,
            nest_type=NestType.BOWL,
            egg_limit=4,
            wingspan_cm=31,
            power=Power(
                color=PowerColor.BROWN,
                text="Example brown power.",
                implementation_status=PowerImplementationStatus.NOT_IMPLEMENTED,
            ),
        )

        self.assertEqual(bird.food_cost.minimum_total, 2)
        self.assertIn(Habitat.WETLAND, bird.habitats)

    def test_ready_power_requires_handler_key(self) -> None:
        with self.assertRaises(ValidationError):
            Power(
                color=PowerColor.WHITE,
                text="Gain 1 food.",
                implementation_status=PowerImplementationStatus.READY,
            )

    def test_automa_ruleset_requires_automa_module(self) -> None:
        with self.assertRaises(ValidationError):
            RulesetMetadata(
                ruleset_id="core_automa_v1",
                content_packs=[ContentPack.CORE],
                rules_modules=[RulesModule.BASE_GAME],
                player_count=1,
                automa_enabled=True,
            )

