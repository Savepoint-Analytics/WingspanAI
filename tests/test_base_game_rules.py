from unittest import TestCase

from wingspan_ai.content.schemas import FoodType, Habitat
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import apply_action, score_player, setup_base_game
from wingspan_ai.state.models import BirdSlot, BirdfeederState
from fixtures import make_test_catalog


class BaseGameRulesTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_test_catalog()

    def setUp(self) -> None:
        self.state = setup_base_game(
            self.catalog,
            player_ids=["p1", "p2"],
            random_seed=11,
        )

    def test_setup_deals_private_cards_and_public_markets(self) -> None:
        self.assertEqual([len(player.hand) for player in self.state.players], [3, 3])
        self.assertEqual([len(player.bonus_cards) for player in self.state.players], [1, 1])
        self.assertEqual([sum(player.food_tokens.values()) for player in self.state.players], [2, 2])
        self.assertEqual(len(self.state.bird_tray), 3)
        self.assertEqual(len(self.state.birdfeeder.dice), 5)
        self.assertEqual(len(self.state.round_goals), 4)
        self.assertEqual(len(self.state.decks.bird_discard), 4)
        self.assertEqual(len(self.state.decks.bonus_discard), 2)

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

        next_state = apply_action(
            self.state,
            LegalAction(action_type=ActionType.GAIN_FOOD, player_id="p1", food_type=FoodType.SEED),
        )

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
        self.assertEqual(state_after_p2.round_state.active_player_index, 0)

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
        forest_goal = next(goal for goal in self.catalog.round_goals if goal.name == "[bird] in [forest]")
        forest_bird = next(card for card in self.catalog.birds if Habitat.FOREST in card.habitats)
        self.state.round_goals = [forest_goal]
        self.state.players[0].bonus_cards = []
        self.state.players[0].habitats[Habitat.FOREST].append(BirdSlot(card=forest_bird))

        score = score_player(self.state, "p1")

        self.assertEqual(score.round_goal_points, forest_goal.scoring_values[1])
