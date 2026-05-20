from unittest import TestCase

from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.schemas import (
    BonusCard,
    ContentPack,
    FoodType,
    Habitat,
    NestType,
    Power,
    PowerColor,
    PowerImplementationStatus,
)
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import (
    InitialSelection,
    apply_action,
    apply_initial_selection_choice,
    legal_actions_for_current_player,
    score_player,
    score_round_goal_competitive,
    setup_base_game,
)
from wingspan_ai.state.models import BirdfeederState, BirdSlot


class BaseGameRulesTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def setUp(self) -> None:
        self.state = setup_base_game(
            self.catalog,
            player_ids=["p1", "p2"],
            random_seed=11,
        )

    def test_setup_deals_private_cards_and_public_markets(self) -> None:
        self.assertEqual([len(player.hand) for player in self.state.players], [3, 3])
        self.assertEqual([len(player.bonus_cards) for player in self.state.players], [1, 1])
        self.assertEqual(
            [sum(player.food_tokens.values()) for player in self.state.players],
            [2, 2],
        )
        self.assertEqual(len(self.state.bird_tray), 3)
        self.assertEqual(len(self.state.birdfeeder.dice), 5)
        self.assertEqual(len(self.state.round_goals), 4)
        self.assertEqual(len(self.state.decks.bird_discard), 4)
        self.assertEqual(len(self.state.decks.bonus_discard), 2)

    def test_initial_selection_can_be_applied_explicitly(self) -> None:
        state = setup_base_game(
            self.catalog,
            player_ids=["p1"],
            random_seed=12,
            apply_initial_selection=False,
        )
        player = state.players[0]
        selection = InitialSelection(
            player_id="p1",
            kept_bird_names=[card.common_name for card in player.hand[:2]],
            kept_bonus_card_names=[player.bonus_cards[0].name],
            starting_food=[FoodType.SEED, FoodType.FISH, FoodType.FRUIT],
        )

        discarded_birds, discarded_bonus = apply_initial_selection_choice(player, selection)

        self.assertEqual(len(player.hand), 2)
        self.assertEqual(len(player.bonus_cards), 1)
        self.assertEqual(sum(player.food_tokens.values()), 3)
        self.assertEqual(len(discarded_birds), 3)
        self.assertEqual(len(discarded_bonus), 1)

    def test_playing_a_bird_spends_food_and_moves_card_to_habitat(self) -> None:
        card = self.catalog.birds[0]
        player = self.state.players[0]
        player.hand = [card]
        player.food_tokens = {food_type: 0 for food_type in FoodType}
        for food_type, count in card.food_cost.fixed.items():
            player.food_tokens[food_type] = count

        next_state = apply_action(
            self.state,
            LegalAction(
                action_type=ActionType.PLAY_BIRD,
                player_id="p1",
                bird_common_name=card.common_name,
                habitat=Habitat.FOREST,
            ),
        )

        next_player = next_state.players[0]
        self.assertTrue(
            all(next_player.food_tokens[food_type] == 0 for food_type in card.food_cost.fixed)
        )
        self.assertEqual(next_player.hand, [])
        self.assertEqual(
            next_player.habitats[Habitat.FOREST][0].card.common_name,
            card.common_name,
        )

    def test_gaining_food_removes_die_and_adds_token(self) -> None:
        self.state.birdfeeder = BirdfeederState(dice=[FoodType.SEED])
        starting_seed = self.state.players[0].food_tokens[FoodType.SEED]

        action = next(
            action
            for action in legal_actions_for_current_player(self.state)
            if action.action_type == ActionType.GAIN_FOOD and FoodType.SEED in action.food_types
        )
        next_state = apply_action(self.state, action)

        self.assertEqual(next_state.players[0].food_tokens[FoodType.SEED], starting_seed + 1)
        self.assertEqual(next_state.birdfeeder.dice, [])

    def test_laying_eggs_places_eggs_on_played_birds(self) -> None:
        card = next(card for card in self.catalog.birds if card.egg_limit >= 2)
        self.state.players[0].habitats[Habitat.GRASSLAND].append(BirdSlot(card=card))

        next_state = apply_action(
            self.state,
            LegalAction(action_type=ActionType.LAY_EGGS, player_id="p1", egg_count=2),
        )

        self.assertEqual(next_state.players[0].habitats[Habitat.GRASSLAND][0].eggs, 2)

    def test_drawing_cards_from_tray_adds_card_and_replenishes_tray(self) -> None:
        drawn_card = self.state.bird_tray[0]
        replacement_card = self.state.decks.bird_deck[0]

        next_state = apply_action(
            self.state,
            LegalAction(action_type=ActionType.DRAW_CARDS, player_id="p1", tray_index=0),
        )

        self.assertIn(drawn_card, next_state.players[0].hand)
        self.assertEqual(next_state.bird_tray[0], replacement_card)
        self.assertEqual(len(next_state.bird_tray), 3)

    def test_round_transition_resets_action_cubes_for_next_round(self) -> None:
        for player in self.state.players:
            player.action_cubes_available = 1

        state_after_p1 = apply_action(
            self.state,
            LegalAction(action_type=ActionType.DRAW_CARDS, player_id="p1", draw_from_deck=True),
        )
        state_after_p2 = apply_action(
            state_after_p1,
            LegalAction(action_type=ActionType.DRAW_CARDS, player_id="p2", draw_from_deck=True),
        )

        self.assertEqual(state_after_p2.round_state.round_number, 2)
        self.assertEqual(
            [player.action_cubes_available for player in state_after_p2.players],
            [7, 7],
        )
        self.assertEqual(state_after_p2.round_state.active_player_index, 1)
        self.assertEqual(state_after_p2.round_state.turn_number, 1)
        self.assertEqual(state_after_p2.round_state.round_action_number, 1)

    def test_turn_number_tracks_active_players_turn_within_round(self) -> None:
        state_after_p1 = apply_action(
            self.state,
            LegalAction(action_type=ActionType.DRAW_CARDS, player_id="p1", draw_from_deck=True),
        )
        state_after_p2 = apply_action(
            state_after_p1,
            LegalAction(action_type=ActionType.DRAW_CARDS, player_id="p2", draw_from_deck=True),
        )

        self.assertEqual(state_after_p1.round_state.turn_number, 1)
        self.assertEqual(state_after_p1.round_state.round_action_number, 2)
        self.assertEqual(state_after_p1.round_state.global_turn_number, 2)
        self.assertEqual(state_after_p2.round_state.turn_number, 2)
        self.assertEqual(state_after_p2.round_state.round_action_number, 3)
        self.assertEqual(state_after_p2.round_state.global_turn_number, 3)

    def test_final_score_skeleton_counts_implemented_categories(self) -> None:
        card = next(card for card in self.catalog.birds if card.victory_points > 0)
        self.state.round_goals = []
        self.state.players[0].bonus_cards = []
        self.state.players[0].habitats[Habitat.WETLAND].append(
            BirdSlot(card=card, eggs=2, cached_food=1, tucked_cards=3)
        )

        score = score_player(self.state, "p1")

        self.assertEqual(score.bird_points, card.victory_points)
        self.assertEqual(score.egg_points, 2)
        self.assertEqual(score.cached_food_points, 1)
        self.assertEqual(score.tucked_card_points, 3)
        self.assertEqual(score.bonus_points, 0)
        self.assertEqual(score.round_goal_points, 0)

    def test_first_bonus_card_scoring_handler_scores_bird_feeder(self) -> None:
        seed_birds = [
            card for card in self.catalog.birds if FoodType.SEED in card.food_cost.fixed
        ][:5]
        bird_feeder = next(card for card in self.catalog.bonus_cards if card.name == "Bird Feeder")
        self.state.players[0].bonus_cards = [bird_feeder]
        self.state.round_goals = []
        for card in seed_birds:
            self.state.players[0].habitats[next(iter(card.habitats))].append(BirdSlot(card=card))

        score = score_player(self.state, "p1")

        self.assertEqual(score.bonus_points, 3)

    def test_first_round_goal_scoring_handler_counts_birds_in_habitat(self) -> None:
        forest_goal = next(
            goal for goal in self.catalog.round_goals if goal.name == "[bird] in [forest]"
        )
        forest_bird = next(card for card in self.catalog.birds if Habitat.FOREST in card.habitats)
        self.state.round_goals = [forest_goal]
        self.state.players[0].bonus_cards = []
        self.state.players[0].habitats[Habitat.FOREST].append(BirdSlot(card=forest_bird))

        score = score_player(self.state, "p1")

        self.assertEqual(score.round_goal_points, forest_goal.scoring_values[1])

    def test_simple_brown_food_power_resolves_on_habitat_activation(self) -> None:
        power_card = self.catalog.birds[0].model_copy(
            update={
                "common_name": "Brown Seed Gainer",
                "power": Power(
                    color=PowerColor.BROWN,
                    text="Gain 1 [seed] from the supply.",
                    implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
                ),
            }
        )
        player = self.state.players[0]
        player.habitats[Habitat.FOREST].append(BirdSlot(card=power_card))
        self.state.birdfeeder = BirdfeederState(dice=[FoodType.FISH])
        starting_seed = player.food_tokens[FoodType.SEED]

        next_state = apply_action(
            self.state,
            LegalAction(action_type=ActionType.GAIN_FOOD, player_id="p1", food_type=FoodType.FISH),
        )

        self.assertEqual(next_state.players[0].food_tokens[FoodType.SEED], starting_seed + 1)

    def test_forest_action_scales_food_choices_with_birds_in_habitat(self) -> None:
        player = self.state.players[0]
        forest_birds = [
            card for card in self.catalog.birds if Habitat.FOREST in card.habitats
        ][:2]
        for card in forest_birds:
            player.habitats[Habitat.FOREST].append(BirdSlot(card=card))
        self.state.birdfeeder = BirdfeederState(dice=[FoodType.SEED, FoodType.FISH])

        legal_actions = legal_actions_for_current_player(self.state)
        gain_food_actions = [
            action for action in legal_actions if action.action_type == ActionType.GAIN_FOOD
        ]

        self.assertIn(
            (FoodType.SEED, FoodType.FISH),
            [action.food_types for action in gain_food_actions],
        )

    def test_birdfeeder_reroll_is_available_when_all_remaining_dice_match(self) -> None:
        self.state.birdfeeder = BirdfeederState(dice=[FoodType.SEED])

        legal_actions = legal_actions_for_current_player(self.state)

        self.assertTrue(
            any(
                action.action_type == ActionType.GAIN_FOOD and action.reroll_birdfeeder
                for action in legal_actions
            )
        )

    def test_brown_powers_resolve_right_to_left_after_habitat_action(self) -> None:
        first_card = self.catalog.birds[0].model_copy(
            update={
                "common_name": "Left Tucking Bird",
                "power": Power(
                    color=PowerColor.BROWN,
                    text="Tuck 1 [card] from your hand behind this bird.",
                    implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
                ),
            }
        )
        second_card = self.catalog.birds[1].model_copy(
            update={
                "common_name": "Right Drawing Bird",
                "power": Power(
                    color=PowerColor.BROWN,
                    text="Draw 1 [card].",
                    implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
                ),
            }
        )
        player = self.state.players[0]
        player.hand = []
        player.habitats[Habitat.WETLAND].extend(
            [BirdSlot(card=first_card), BirdSlot(card=second_card)]
        )

        action = next(
            action
            for action in legal_actions_for_current_player(self.state)
            if action.action_type == ActionType.DRAW_CARDS and action.draw_from_deck_count == 2
        )
        next_state = apply_action(self.state, action)

        next_player = next_state.players[0]
        self.assertEqual(next_player.habitats[Habitat.WETLAND][0].tucked_cards, 1)

    def test_pink_birdfeeder_reaction_prioritizes_food_needed_for_hand(self) -> None:
        pink_card = self.catalog.birds[0].model_copy(
            update={
                "common_name": "Helpful Pink Bird",
                "power": Power(
                    color=PowerColor.PINK,
                    text=(
                        "When another player's [predator] succeeds, "
                        "gain 1 [die] from the birdfeeder."
                    ),
                    implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
                ),
            }
        )
        fish_card = self.catalog.birds[1].model_copy(
            update={
                "common_name": "Fish Hungry Bird",
                "food_cost": self.catalog.birds[1].food_cost.model_copy(
                    update={"fixed": {FoodType.FISH: 1}}
                ),
            }
        )
        self.state.players[1].habitats[Habitat.FOREST].append(BirdSlot(card=pink_card))
        self.state.players[1].hand = [fish_card]
        self.state.birdfeeder = BirdfeederState(
            dice=[FoodType.SEED, FoodType.FISH, FoodType.FRUIT]
        )

        action = next(
            action
            for action in legal_actions_for_current_player(self.state)
            if action.action_type == ActionType.GAIN_FOOD and FoodType.SEED in action.food_types
        )
        next_state = apply_action(self.state, action)

        self.assertEqual(next_state.players[1].food_tokens[FoodType.FISH], 1)

    def test_competitive_round_goal_scores_by_rank(self) -> None:
        forest_goal = next(
            goal for goal in self.catalog.round_goals if goal.name == "[bird] in [forest]"
        )
        self.state.round_goals = [forest_goal]
        forest_birds = [
            card for card in self.catalog.birds if Habitat.FOREST in card.habitats
        ][:3]
        self.state.players[0].habitats[Habitat.FOREST].extend(
            [BirdSlot(card=forest_birds[0]), BirdSlot(card=forest_birds[1])]
        )
        self.state.players[1].habitats[Habitat.FOREST].append(BirdSlot(card=forest_birds[2]))

        scores = score_round_goal_competitive(self.state, 0)

        self.assertEqual(scores, {"p1": 4, "p2": 1})

    def test_expanded_bonus_card_scoring_counts_common_nest_bonus(self) -> None:
        wildlife_gardener = BonusCard(
            name="Wildlife Gardener",
            content_packs={ContentPack.CORE},
            condition="Birds with [bowl] nests",
            victory_point_text="4 to 5 birds: 4; 6+ birds: 7",
        )
        player = self.state.players[0]
        player.bonus_cards = [wildlife_gardener]
        player.round_goal_points = 0
        self.state.round_goals = []
        bowl_birds = [
            card.model_copy(update={"nest_type": NestType.BOWL})
            for card in self.catalog.birds[:4]
        ]
        for card in bowl_birds:
            player.habitats[Habitat.GRASSLAND].append(BirdSlot(card=card))

        score = score_player(self.state, "p1")

        self.assertEqual(score.bonus_points, 4)

    def test_discard_egg_gain_wild_food_power_uses_needed_hand_food(self) -> None:
        raven_card = self.catalog.birds[0].model_copy(
            update={
                "common_name": "Egg Discard Food Bird",
                "power": Power(
                    color=PowerColor.BROWN,
                    text=(
                        "Discard 1 [egg] from any of your other birds to gain "
                        "1 [wild] from the supply."
                    ),
                    implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
                    handler_key="discard_egg_gain_wild_food",
                ),
            }
        )
        egg_source = self.catalog.birds[1]
        fish_card = self.catalog.birds[2].model_copy(
            update={
                "food_cost": self.catalog.birds[2].food_cost.model_copy(
                    update={"fixed": {FoodType.FISH: 1}}
                )
            }
        )
        player = self.state.players[0]
        player.hand = [fish_card]
        player.habitats[Habitat.GRASSLAND].append(BirdSlot(card=egg_source, eggs=1))
        player.habitats[Habitat.FOREST].append(BirdSlot(card=raven_card))
        self.state.birdfeeder = BirdfeederState(dice=[FoodType.SEED])

        action = next(
            action
            for action in legal_actions_for_current_player(self.state)
            if action.action_type == ActionType.GAIN_FOOD and FoodType.SEED in action.food_types
        )
        next_state = apply_action(self.state, action)

        self.assertEqual(next_state.players[0].food_tokens[FoodType.FISH], 1)

    def test_predator_power_records_rng_and_caches_on_success(self) -> None:
        predator_card = self.catalog.birds[0].model_copy(
            update={
                "common_name": "Predator Bird",
                "predator": True,
                "power": Power(
                    color=PowerColor.BROWN,
                    text="Roll all dice not in birdfeeder. If any are [rodent], cache 1 [rodent].",
                    implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
                    handler_key="predator_hunt",
                ),
            }
        )
        player = self.state.players[0]
        player.habitats[Habitat.FOREST].append(BirdSlot(card=predator_card))
        self.state.birdfeeder = BirdfeederState(dice=[FoodType.SEED])

        next_state = apply_action(
            self.state,
            LegalAction(action_type=ActionType.GAIN_FOOD, player_id="p1", food_type=FoodType.SEED),
        )

        self.assertTrue(next_state.rng_draw_records)
        self.assertEqual(next_state.rng_draw_records[-1].draw_type, "predator_hunt")

    def test_deck_search_power_records_revealed_card(self) -> None:
        search_card = self.catalog.birds[0].model_copy(
            update={
                "common_name": "Deck Search Bird",
                "power": Power(
                    color=PowerColor.BROWN,
                    text=(
                        "Look at a [card] from the deck. If less than 75cm, "
                        "tuck it behind this bird. If not, discard it."
                    ),
                    implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
                    handler_key="deck_search_tuck_by_wingspan",
                ),
            }
        )
        player = self.state.players[0]
        player.habitats[Habitat.WETLAND].append(BirdSlot(card=search_card))

        action = next(
            action
            for action in legal_actions_for_current_player(self.state)
            if action.action_type == ActionType.DRAW_CARDS
        )
        next_state = apply_action(self.state, action)

        self.assertTrue(
            any(
                record.draw_type == "bird_power_deck_search"
                for record in next_state.rng_draw_records
            )
        )
