"""Per-handler regression tests for the expanded bird power slice.

Each test drives one registry handler key through `resolve_habitat_powers` or
`resolve_played_bird_power` so that classification and resolution are checked
together. Handler metadata in `power_registry.py` points here.
"""

from pathlib import Path
from unittest import TestCase, skipIf

from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
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
from wingspan_ai.rules.base_game import (
    resolve_habitat_powers,
    resolve_played_bird_power,
    setup_base_game,
)
from wingspan_ai.rules.power_registry import (
    POWER_HANDLER_REGISTRY,
    audit_power_coverage,
    classify_power_handler_key,
)
from wingspan_ai.state.models import BirdfeederState, BirdSlot


def make_bird(
    common_name: str,
    power_text: str | None,
    power_color: PowerColor,
    *,
    habitats: set[Habitat] | None = None,
    food_cost: FoodCost | None = None,
    victory_points: int = 3,
    egg_limit: int = 3,
    nest_type: NestType = NestType.BOWL,
    wingspan_cm: int = 40,
) -> BirdCard:
    """Build a bird whose power is classified through the live registry."""

    handler_key = classify_power_handler_key(power_text, power_color)
    metadata = POWER_HANDLER_REGISTRY.get(handler_key or "")
    return BirdCard(
        common_name=common_name,
        scientific_name=f"Testus {common_name.lower().replace(' ', '')}",
        content_pack=ContentPack.CORE,
        habitats=habitats or {Habitat.FOREST},
        food_cost=food_cost or FoodCost(),
        victory_points=victory_points,
        nest_type=nest_type,
        egg_limit=egg_limit,
        wingspan_cm=wingspan_cm,
        power=Power(
            color=power_color,
            text=power_text,
            handler_key=handler_key,
            implementation_status=(
                metadata.implementation_status
                if metadata is not None
                else PowerImplementationStatus.NOT_IMPLEMENTED
            ),
        ),
    )


class PowerHandlerTestCase(TestCase):
    """Shared two-player fixture with a deterministic birdfeeder."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def setUp(self) -> None:
        self.state = setup_base_game(
            self.catalog,
            player_ids=["p1", "p2"],
            random_seed=7,
        )
        self.player = self.state.players[0]
        self.opponent = self.state.players[1]
        self.state.birdfeeder = BirdfeederState(
            dice=[FoodType.SEED, FoodType.FISH, FoodType.FRUIT, FoodType.RODENT, FoodType.SEED]
        )

    def place(self, bird: BirdCard, habitat: Habitat = Habitat.FOREST, **slot_kwargs) -> BirdSlot:
        slot = BirdSlot(card=bird, **slot_kwargs)
        self.player.habitats[habitat].append(slot)
        return slot


class DiscardEggDrawCardsTests(PowerHandlerTestCase):
    def test_spends_one_egg_and_draws_stated_count(self) -> None:
        host = self.place(make_bird("Egg Host", None, PowerColor.NONE))
        host.eggs = 2
        self.place(
            make_bird("Franklin Test", "Discard 1 [egg] to draw 2 [card].", PowerColor.BROWN)
        )
        hand_before = len(self.player.hand)

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(self.player.total_eggs, 1)
        self.assertEqual(len(self.player.hand), hand_before + 2)

    def test_is_skipped_without_an_egg_to_spend(self) -> None:
        self.place(
            make_bird("Franklin Test", "Discard 1 [egg] to draw 2 [card].", PowerColor.BROWN)
        )
        hand_before = len(self.player.hand)

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(self.player.total_eggs, 0)
        self.assertEqual(len(self.player.hand), hand_before)


class DrawCardsThenDiscardTests(PowerHandlerTestCase):
    def test_draws_two_and_discards_one_for_net_gain(self) -> None:
        self.place(
            make_bird(
                "Wood Duck Test",
                "Draw 2 [card]. If you do, discard 1 [card] from your hand "
                "at the end of your turn.",
                PowerColor.BROWN,
            )
        )
        hand_before = len(self.player.hand)

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(len(self.player.hand), hand_before + 1)

    def test_single_draw_variant_is_net_neutral(self) -> None:
        self.place(
            make_bird(
                "Black Tern Test",
                "Draw 1 [card]. If you do, discard 1 [card] from your hand "
                "at the end of your turn.",
                PowerColor.BROWN,
            )
        )
        hand_before = len(self.player.hand)

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(len(self.player.hand), hand_before)


class MoveBirdHabitatTests(PowerHandlerTestCase):
    def test_moves_rightmost_bird_to_emptiest_habitat(self) -> None:
        self.place(make_bird("Anchor", None, PowerColor.NONE))
        mover = self.place(
            make_bird(
                "Song Sparrow Test",
                "If this bird is to the right of all other birds in its habitat, "
                "move it to another habitat.",
                PowerColor.BROWN,
            )
        )
        self.player.habitats[Habitat.GRASSLAND].append(
            BirdSlot(card=make_bird("Grass Anchor", None, PowerColor.NONE))
        )

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(len(self.player.habitats[Habitat.FOREST]), 1)
        self.assertIn(mover, self.player.habitats[Habitat.WETLAND])

    def test_does_not_move_when_another_bird_is_to_the_right(self) -> None:
        mover = self.place(
            make_bird(
                "Song Sparrow Test",
                "If this bird is to the right of all other birds in its habitat, "
                "move it to another habitat.",
                PowerColor.BROWN,
            )
        )
        self.place(make_bird("Rightmost", None, PowerColor.NONE))

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertIn(mover, self.player.habitats[Habitat.FOREST])
        self.assertEqual(len(self.player.habitats[Habitat.FOREST]), 2)


class RepeatBrownPowerTests(PowerHandlerTestCase):
    def test_repeats_the_nearest_other_brown_power(self) -> None:
        self.place(
            make_bird("Supply Bird", "Gain 1 [fruit] from the supply.", PowerColor.BROWN)
        )
        self.place(
            make_bird(
                "Mockingbird Test",
                "Repeat a brown power on another bird in this habitat.",
                PowerColor.BROWN,
            )
        )
        fruit_before = self.player.food_tokens[FoodType.FRUIT]

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        # Once for the supply bird's own activation, once for the repeat.
        self.assertEqual(self.player.food_tokens[FoodType.FRUIT], fruit_before + 2)

    def test_repeat_powers_do_not_target_other_repeat_powers(self) -> None:
        self.player.food_tokens = {food: 0 for food in self.player.food_tokens}
        self.place(
            make_bird(
                "Catbird Test",
                "Repeat a brown power on another bird in this habitat.",
                PowerColor.BROWN,
            )
        )
        self.place(
            make_bird(
                "Mockingbird Test",
                "Repeat a brown power on another bird in this habitat.",
                PowerColor.BROWN,
            )
        )

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(sum(self.player.food_tokens.values()), 0)


class TradeFoodWithSupplyTests(PowerHandlerTestCase):
    def test_trades_surplus_food_for_the_most_needed_type(self) -> None:
        self.player.food_tokens[FoodType.SEED] = 4
        self.player.hand = [
            make_bird(
                "Fish Eater",
                None,
                PowerColor.NONE,
                food_cost=FoodCost(fixed={FoodType.FISH: 2}),
            )
        ]
        self.place(
            make_bird(
                "Green Heron Test",
                "Trade 1 [wild] for any other type from the supply.",
                PowerColor.BROWN,
            )
        )

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(self.player.food_tokens[FoodType.SEED], 3)
        self.assertEqual(self.player.food_tokens[FoodType.FISH], 1)

    def test_is_skipped_without_any_food(self) -> None:
        self.player.food_tokens = {food: 0 for food in self.player.food_tokens}
        self.place(
            make_bird(
                "Green Heron Test",
                "Trade 1 [wild] for any other type from the supply.",
                PowerColor.BROWN,
            )
        )

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(sum(self.player.food_tokens.values()), 0)


class DrawBonusCardsKeepOneTests(PowerHandlerTestCase):
    def test_keeps_the_highest_scoring_bonus_card(self) -> None:
        self.player.bonus_cards = []
        # Bonus scoring counts birds carrying the card's tag, mirroring the
        # workbook, so the board must be tagged rather than merely flocking.
        for index in range(2):
            bird = make_bird(f"Flocker {index}", None, PowerColor.NONE)
            bird = bird.model_copy(
                update={"flocking": True, "bonus_card_tags": {"Bird Counter"}}
            )
            self.place(bird)
        self.state.decks.bonus_deck = [
            BonusCard(
                name="Bird Counter",
                content_packs={ContentPack.CORE},
                condition="Birds with flocking powers",
                # Real printed text; the parser deliberately rejects invented forms.
                victory_point_text="2 per bird",
            ),
            BonusCard(
                name="Visionary Leader",
                content_packs={ContentPack.CORE},
                condition="Cards in hand",
                victory_point_text="5 to 7 cards: 4; 8+ cards: 7",
            ),
        ]
        self.player.hand = []

        played = BirdSlot(
            card=make_bird("Puffin Test", "Draw 2 new bonus cards and keep 1.", PowerColor.WHITE)
        )
        self.player.habitats[Habitat.FOREST].append(played)
        resolve_played_bird_power(self.player, played, self.state, habitat=Habitat.FOREST)

        self.assertEqual([card.name for card in self.player.bonus_cards], ["Bird Counter"])
        self.assertEqual([card.name for card in self.state.decks.bonus_discard[-1:]],
                         ["Visionary Leader"])


class DrawTrayCardsTests(PowerHandlerTestCase):
    def test_takes_the_whole_tray_and_refills_it(self) -> None:
        hand_before = len(self.player.hand)
        tray_names = [card.common_name for card in self.state.bird_tray]

        played = BirdSlot(
            card=make_bird(
                "Brant Test",
                "Draw the 3 face-up [card] in the bird tray.",
                PowerColor.WHITE,
            )
        )
        self.player.habitats[Habitat.FOREST].append(played)
        resolve_played_bird_power(self.player, played, self.state, habitat=Habitat.FOREST)

        self.assertEqual(len(self.player.hand), hand_before + len(tray_names))
        self.assertEqual(len(self.state.bird_tray), 3)
        for name in tray_names:
            self.assertIn(name, [card.common_name for card in self.player.hand])


class DrawCardsPlayerSelectTests(PowerHandlerTestCase):
    def test_deals_one_card_to_each_opponent_and_the_rest_to_the_actor(self) -> None:
        actor_hand_before = len(self.player.hand)
        opponent_hand_before = len(self.opponent.hand)

        played = BirdSlot(
            card=make_bird(
                "Oystercatcher Test",
                "Draw [card] equal to the number of players +1. Starting with you and "
                "proceeding clockwise, each player selects 1 of those cards and places "
                "it in their hand. You keep the extra card.",
                PowerColor.WHITE,
            )
        )
        self.player.habitats[Habitat.FOREST].append(played)
        resolve_played_bird_power(self.player, played, self.state, habitat=Habitat.FOREST)

        # Three cards drawn for two players: actor keeps two, opponent takes one.
        self.assertEqual(len(self.player.hand), actor_hand_before + 2)
        self.assertEqual(len(self.opponent.hand), opponent_hand_before + 1)


class PlayAdditionalBirdTests(PowerHandlerTestCase):
    def test_plays_the_best_affordable_bird_into_the_named_habitat(self) -> None:
        self.player.food_tokens[FoodType.SEED] = 2
        # The second forest slot costs an egg, so the player needs one available.
        egg_host = self.place(
            make_bird("Egg Host", None, PowerColor.NONE), habitat=Habitat.GRASSLAND
        )
        egg_host.eggs = 1
        cheap = make_bird(
            "Cheap Extra",
            None,
            PowerColor.NONE,
            habitats={Habitat.FOREST},
            food_cost=FoodCost(fixed={FoodType.SEED: 1}),
            victory_points=2,
        )
        valuable = make_bird(
            "Valuable Extra",
            None,
            PowerColor.NONE,
            habitats={Habitat.FOREST},
            food_cost=FoodCost(fixed={FoodType.SEED: 1}),
            victory_points=6,
        )
        self.player.hand = [cheap, valuable]

        played = BirdSlot(
            card=make_bird(
                "Downy Test",
                "Play an additional bird in your [forest]. Pay its normal cost.",
                PowerColor.WHITE,
            )
        )
        self.player.habitats[Habitat.FOREST].append(played)
        resolve_played_bird_power(self.player, played, self.state, habitat=Habitat.FOREST)

        forest_names = [slot.card.common_name for slot in self.player.habitats[Habitat.FOREST]]
        self.assertIn("Valuable Extra", forest_names)
        self.assertEqual([card.common_name for card in self.player.hand], ["Cheap Extra"])
        self.assertEqual(self.player.food_tokens[FoodType.SEED], 1)
        self.assertEqual(self.player.total_eggs, 0)

    def test_is_skipped_when_no_hand_bird_is_affordable(self) -> None:
        self.player.food_tokens = {food: 0 for food in self.player.food_tokens}
        self.player.hand = [
            make_bird(
                "Too Expensive",
                None,
                PowerColor.NONE,
                habitats={Habitat.FOREST},
                food_cost=FoodCost(fixed={FoodType.SEED: 3}),
            )
        ]

        played = BirdSlot(
            card=make_bird(
                "Downy Test",
                "Play an additional bird in your [forest]. Pay its normal cost.",
                PowerColor.WHITE,
            )
        )
        self.player.habitats[Habitat.FOREST].append(played)
        resolve_played_bird_power(self.player, played, self.state, habitat=Habitat.FOREST)

        self.assertEqual(len(self.player.habitats[Habitat.FOREST]), 1)
        self.assertEqual(len(self.player.hand), 1)


class MultiPlayerPowerTests(PowerHandlerTestCase):
    """Powers that previously resolved as pure self-benefit."""

    def test_all_players_draw_cards_gives_opponents_cards_too(self) -> None:
        actor_before = len(self.player.hand)
        opponent_before = len(self.opponent.hand)
        self.place(
            make_bird("Mallard Test", "All players draw 1 [card] from the deck.", PowerColor.BROWN)
        )

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(len(self.player.hand), actor_before + 1)
        self.assertEqual(len(self.opponent.hand), opponent_before + 1)

    def test_each_player_gains_birdfeeder_food(self) -> None:
        actor_before = sum(self.player.food_tokens.values())
        opponent_before = sum(self.opponent.food_tokens.values())
        self.place(
            make_bird(
                "Hummingbird Test",
                "Each player gains 1 [die] from the birdfeeder, starting with the "
                "player of your choice.",
                PowerColor.BROWN,
            )
        )

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(sum(self.player.food_tokens.values()), actor_before + 1)
        self.assertEqual(sum(self.opponent.food_tokens.values()), opponent_before + 1)

    def test_all_players_lay_eggs_respects_nest_type_and_actor_bonus(self) -> None:
        bowl = self.place(make_bird("Bowl Bird", None, PowerColor.NONE))
        actor_extra = self.place(make_bird("Bowl Bird Two", None, PowerColor.NONE))
        opponent_bowl = BirdSlot(card=make_bird("Opp Bowl", None, PowerColor.NONE))
        self.opponent.habitats[Habitat.FOREST].append(opponent_bowl)
        ground_only = BirdSlot(
            card=make_bird("Opp Ground", None, PowerColor.NONE, nest_type=NestType.GROUND)
        )
        self.opponent.habitats[Habitat.GRASSLAND].append(ground_only)

        self.place(
            make_bird(
                "Lazuli Test",
                "All players lay 1 [egg] on any 1 [bowl] bird. You may lay 1 [egg] on "
                "1 additional [bowl] bird.",
                PowerColor.BROWN,
            )
        )

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        # Actor lays one plus the additional egg; opponent lays only on its bowl bird.
        self.assertEqual(bowl.eggs + actor_extra.eggs, 2)
        self.assertEqual(opponent_bowl.eggs, 1)
        self.assertEqual(ground_only.eggs, 0)

    def test_fewest_birds_draw_cards_only_rewards_the_trailing_player(self) -> None:
        self.place(make_bird("Filler One", None, PowerColor.NONE), habitat=Habitat.WETLAND)
        self.place(make_bird("Filler Two", None, PowerColor.NONE), habitat=Habitat.WETLAND)
        actor_before = len(self.player.hand)
        opponent_before = len(self.opponent.hand)

        self.place(
            make_bird(
                "Bittern Test",
                "Player(s) with the fewest birds in their [wetland] draw 1 [card].",
                PowerColor.BROWN,
            )
        )

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(len(self.player.hand), actor_before)
        self.assertEqual(len(self.opponent.hand), opponent_before + 1)

    def test_fewest_birds_gain_food_only_rewards_the_trailing_player(self) -> None:
        self.place(make_bird("Forest Filler", None, PowerColor.NONE))
        actor_before = sum(self.player.food_tokens.values())
        opponent_before = sum(self.opponent.food_tokens.values())

        self.place(
            make_bird(
                "Hermit Thrush Test",
                "Player(s) with the fewest birds in their [forest] gain 1 [die] "
                "from birdfeeder.",
                PowerColor.BROWN,
            )
        )

        resolve_habitat_powers(self.player, Habitat.FOREST, self.state)

        self.assertEqual(sum(self.player.food_tokens.values()), actor_before)
        self.assertEqual(sum(self.opponent.food_tokens.values()), opponent_before + 1)


class CountedTemplateTests(PowerHandlerTestCase):
    def test_gain_food_from_supply_honours_multi_token_counts(self) -> None:
        played = BirdSlot(
            card=make_bird("Pelican Test", "Gain 3 [fish] from the supply.", PowerColor.WHITE)
        )
        self.player.habitats[Habitat.FOREST].append(played)
        fish_before = self.player.food_tokens[FoodType.FISH]

        resolve_played_bird_power(self.player, played, self.state, habitat=Habitat.FOREST)

        self.assertEqual(self.player.food_tokens[FoodType.FISH], fish_before + 3)

    def test_draw_card_honours_multi_card_counts(self) -> None:
        played = BirdSlot(
            card=make_bird("Carolina Test", "Draw 2 [card].", PowerColor.WHITE)
        )
        self.player.habitats[Habitat.FOREST].append(played)
        hand_before = len(self.player.hand)

        resolve_played_bird_power(self.player, played, self.state, habitat=Habitat.FOREST)

        self.assertEqual(len(self.player.hand), hand_before + 2)


class WorkbookClassificationTests(TestCase):
    """Coverage guard against the real workbook, not the synthetic catalog."""

    @skipIf(
        not DEFAULT_WORKBOOK_PATH.exists(),
        f"{DEFAULT_WORKBOOK_PATH} is not present",
    )
    def test_every_workbook_power_is_classified_and_implemented(self) -> None:
        catalog = load_base_game_content_catalog(Path(DEFAULT_WORKBOOK_PATH))
        audit = audit_power_coverage(catalog)

        self.assertEqual(audit.unclassified_power_count, 0)
        self.assertEqual(audit.unsupported_power_count, 0)
        self.assertEqual(audit.handler_coverage, 1.0)
        self.assertEqual(audit.implementation_coverage, 1.0)

    @skipIf(
        not DEFAULT_WORKBOOK_PATH.exists(),
        f"{DEFAULT_WORKBOOK_PATH} is not present",
    )
    def test_every_classified_handler_key_has_registry_metadata(self) -> None:
        catalog = load_base_game_content_catalog(Path(DEFAULT_WORKBOOK_PATH))

        for bird in catalog.birds:
            handler_key = bird.power.handler_key or classify_power_handler_key(
                bird.power.text,
                bird.power.color,
            )
            self.assertIsNotNone(handler_key, bird.common_name)
            self.assertIn(handler_key, POWER_HANDLER_REGISTRY, bird.common_name)
