from wingspan_ai.content.schemas import (
    BirdCard,
    BonusCard,
    ContentCatalog,
    ContentPack,
    FoodCost,
    FoodType,
    Habitat,
    NestType,
    Power,
    PowerColor,
    PowerImplementationStatus,
    RoundGoal,
    RulesModule,
    RulesetMetadata,
)


def make_test_catalog(card_count: int = 80) -> ContentCatalog:
    birds = []
    for index in range(card_count):
        birds.append(
            BirdCard(
                common_name=f"Seed Bird {index}",
                scientific_name=f"Testus seedus {index}",
                content_pack=ContentPack.CORE,
                habitats={Habitat.FOREST, Habitat.GRASSLAND, Habitat.WETLAND},
                food_cost=FoodCost(fixed={FoodType.SEED: 1 if index % 2 == 0 else 0}),
                victory_points=1 + (index % 5),
                nest_type=NestType.BOWL,
                egg_limit=3,
                wingspan_cm=30 + index,
                power=Power(
                    color=PowerColor.NONE,
                    implementation_status=PowerImplementationStatus.NO_OP_FOR_V1,
                ),
            )
        )

    return ContentCatalog(
        birds=birds,
        bonus_cards=[
            BonusCard(
                name=f"Bird Feeder" if index == 0 else f"Test Bonus {index}",
                content_packs={ContentPack.CORE},
                condition="Birds that eat [seed]",
                victory_point_text="5 to 7 birds: 3; 8+ birds: 7",
            )
            for index in range(8)
        ],
        round_goals=[
            RoundGoal(
                name=goal_name,
                content_pack=ContentPack.CORE,
                scoring_values={1: 0, 2: 1, 3: 2, 4: 3},
                rules_module=RulesModule.BASE_GAME,
            )
            for goal_name in (
                "[bird] in [forest]",
                "[bird] in [grassland]",
                "[bird] in [wetland]",
                "[egg] in grassland",
            )
        ],
        rulesets=[
            RulesetMetadata(
                ruleset_id="test_core",
                content_packs=[ContentPack.CORE],
                rules_modules=[RulesModule.BASE_GAME],
                player_count=2,
            )
        ],
    )
