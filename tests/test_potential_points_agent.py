from collections import Counter
from unittest import TestCase, skipIf

from wingspan_ai.agents import GreedyBaselineAgent, PotentialPointsAgent, evaluate_state_potential
from wingspan_ai.agents.potential_points import (
    _pink_trigger_rate,
    _played_power_value,
    _remaining_teal_triggers,
)
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
from wingspan_ai.rules import habitat_action_yield
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


@skipIf(
    not DEFAULT_WORKBOOK_PATH.exists(),
    f"{DEFAULT_WORKBOOK_PATH} is not present",
)
class PinkPowerValuationTests(TestCase):
    """Pink powers fire on opponents' turns, so their value depends on opponents.

    Previously every pink power was valued at a flat `turns_remaining * 0.35`,
    so a vulture paying out only when an opponent's predator succeeds scored
    identically whether opponents held zero predators or five.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        cls.by_name = {bird.common_name: bird for bird in cls.catalog.birds}
        cls.predator = next(bird for bird in cls.catalog.birds if bird.predator)

    def _state_with(self, pink_card_name: str, opponent_predators: int = 0):
        state = setup_base_game(self.catalog, player_ids=["player_1", "player_2"], random_seed=1)
        me, opponent = state.players
        opponent.action_cubes_available = 8
        opponent.habitats[Habitat.FOREST] = [
            BirdSlot(card=self.predator) for _ in range(opponent_predators)
        ]
        slot = BirdSlot(card=self.by_name[pink_card_name])
        me.habitats[Habitat.FOREST] = [slot]
        return state, me, slot

    def test_predator_pink_is_worthless_without_opponent_predators(self) -> None:
        state, me, slot = self._state_with("Black Vulture", opponent_predators=0)

        self.assertEqual(_pink_trigger_rate(state, me, slot, 8), 0.0)

    def test_predator_pink_scales_with_opponent_predator_count(self) -> None:
        rates = []
        for count in (1, 2, 3):
            state, me, slot = self._state_with("Black Vulture", opponent_predators=count)
            rates.append(_pink_trigger_rate(state, me, slot, 8))

        self.assertEqual(rates, sorted(rates))
        self.assertGreater(rates[-1], rates[0])

    def test_habitat_gated_pink_is_worthless_when_that_habitat_is_full(self) -> None:
        """Eastern Kingbird fires when an opponent plays into their forest."""

        state, me, slot = self._state_with("Eastern Kingbird", opponent_predators=0)
        with_room = _pink_trigger_rate(state, me, slot, 8)

        state.players[1].habitats[Habitat.FOREST] = [BirdSlot(card=self.predator) for _ in range(5)]
        when_full = _pink_trigger_rate(state, me, slot, 8)

        self.assertGreater(with_room, 0.0)
        self.assertEqual(when_full, 0.0)

    def test_brood_parasite_is_valued_by_board_capacity_not_its_own(self) -> None:
        """Both cowbirds have `egg_limit` 0 and lay on *other* birds.

        Checking the power card's own capacity valued these 5 VP and 3 VP cards
        at exactly zero.
        """

        bowl_bird = next(
            bird
            for bird in self.catalog.birds
            if bird.nest_type is not None and bird.nest_type.value == "bowl" and bird.egg_limit > 0
        )
        state, me, slot = self._state_with("Bronzed Cowbird")
        state.players[1].habitats[Habitat.FOREST] = [BirdSlot(card=bowl_bird)]
        self.assertEqual(slot.card.egg_limit, 0)

        triggers = _pink_trigger_rate(state, me, slot, 8)
        demand = Counter({FoodType.INVERTEBRATE: 1})
        without_targets = _played_power_value(
            slot, demand, 3.0, 8, state.round_state.round_number, pink_triggers=triggers, player=me
        )
        me.habitats[Habitat.GRASSLAND] = [BirdSlot(card=bowl_bird) for _ in range(2)]
        with_targets = _played_power_value(
            slot, demand, 3.0, 8, state.round_state.round_number, pink_triggers=triggers, player=me
        )

        self.assertEqual(without_targets, 0.0)
        self.assertGreater(with_targets, 0.0)


@skipIf(
    not DEFAULT_WORKBOOK_PATH.exists(),
    f"{DEFAULT_WORKBOOK_PATH} is not present",
)
class HabitatYieldValuationTests(TestCase):
    """The player-mat yield curve is Wingspan's core engine and was unvalued.

    Forest produces 1/2/3 food at 0-1, 2-3 and 4-5 birds, so the 2nd and 4th
    birds in a row are worth more than the 3rd and 5th. Before this, adding a
    powerless bird moved the estimate by a flat +10.70 either way.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)
        cls.plain = next(
            bird
            for bird in cls.catalog.birds
            if bird.power.color == PowerColor.NONE and Habitat.FOREST in bird.habitats
        )

    def _total_with_forest_birds(self, count: int) -> float:
        state = setup_base_game(self.catalog, player_ids=["player_1", "player_2"], random_seed=1)
        state.players[0].habitats[Habitat.FOREST] = [
            BirdSlot(card=self.plain) for _ in range(count)
        ]
        return evaluate_state_potential(state, "player_1").total

    def test_crossing_a_yield_threshold_is_worth_more_than_not_crossing(self) -> None:
        totals = [self._total_with_forest_birds(n) for n in range(5)]
        crossing = totals[2] - totals[1]  # 1 -> 2 birds unlocks 2 food per action
        not_crossing = totals[3] - totals[2]  # 2 -> 3 unlocks nothing

        self.assertGreater(crossing, not_crossing)

    def test_agent_valuation_tracks_the_rules_curve(self) -> None:
        """The agent must read the rule, not keep its own copy of the curve."""

        from wingspan_ai.agents.potential_points import _egg_rate

        for count in range(6):
            state = setup_base_game(
                self.catalog, player_ids=["player_1", "player_2"], random_seed=1
            )
            player = state.players[0]
            player.habitats[Habitat.GRASSLAND] = [BirdSlot(card=self.plain) for _ in range(count)]
            self.assertEqual(_egg_rate(player), habitat_action_yield(Habitat.GRASSLAND, count))

    def test_ablation_switch_removes_the_component(self) -> None:
        from wingspan_ai.agents import potential_points as module

        state = setup_base_game(self.catalog, player_ids=["player_1", "player_2"], random_seed=1)
        state.players[0].habitats[Habitat.FOREST] = [BirdSlot(card=self.plain) for _ in range(4)]
        with_feature = evaluate_state_potential(state, "player_1").habitat_yield_potential
        module.VALUE_HABITAT_YIELD = False
        try:
            without = evaluate_state_potential(state, "player_1").habitat_yield_potential
        finally:
            module.VALUE_HABITAT_YIELD = True

        self.assertGreater(with_feature, 0.0)
        self.assertEqual(without, 0.0)


class TealTriggerCountTests(TestCase):
    """Teal powers fire once per remaining round.

    This was inferred from turns remaining via ceil(turns / 6), but turns per
    round are 8/7/6/5. It returned 2 in round 1 where the answer is 4, halving
    the value of teal birds exactly when playing them is most valuable.
    """

    def test_triggers_count_remaining_rounds(self) -> None:
        self.assertEqual([_remaining_teal_triggers(r) for r in (1, 2, 3, 4)], [4, 3, 2, 1])

    def test_a_teal_bird_is_worth_more_early_than_late(self) -> None:
        self.assertGreater(_remaining_teal_triggers(1), _remaining_teal_triggers(4))

    def test_no_triggers_past_the_final_round(self) -> None:
        self.assertEqual(_remaining_teal_triggers(5), 0)


class EndgameSearchDepthTests(TestCase):
    """The endgame search must actually descend through opponent turns.

    Until 2026-09-04 the recursion stopped whenever the active player changed,
    which is after every action in a multiplayer game, so `search_depth` was a
    dead parameter. These tests pin the repaired behaviour.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def _two_player_state(self):
        state = setup_base_game(self.catalog, player_ids=["p1", "p2"], random_seed=7)
        return state, state.active_player.player_id

    def test_depth_two_descends_into_a_second_own_turn(self) -> None:
        from unittest.mock import patch

        import wingspan_ai.agents.potential_points as module

        state, player_id = self._two_player_state()
        action = legal_actions_for_current_player(state)[0]
        depths_seen: list[int] = []
        original = module._search_value_from_branch

        def recording(branch, pid, depth, beam_width):
            depths_seen.append(depth)
            return original(branch, pid, depth, beam_width)

        with patch.object(module, "_search_value_from_branch", recording):
            module._search_action_value(state, action, player_id, depth=3, beam_width=2)

        self.assertIn(2, depths_seen, "search never reached a second own turn")

    def test_opponent_turns_are_played_before_the_next_own_turn(self) -> None:
        from wingspan_ai.agents.potential_points import _play_opponent_turns_in_place
        from wingspan_ai.rules.base_game import apply_action

        state, player_id = self._two_player_state()
        branch = apply_action(state, legal_actions_for_current_player(state)[0])
        self.assertNotEqual(branch.active_player.player_id, player_id)
        opponent_cubes_before = branch.active_player.action_cubes_available

        _play_opponent_turns_in_place(branch, player_id)

        self.assertEqual(branch.active_player.player_id, player_id)
        opponent = next(p for p in branch.players if p.player_id != player_id)
        self.assertEqual(opponent.action_cubes_available, opponent_cubes_before - 1)

    def test_depth_one_matches_the_one_ply_evaluator(self) -> None:
        from wingspan_ai.agents.potential_points import (
            _search_action_value,
            _terminal_planning_value,
        )
        from wingspan_ai.rules.base_game import apply_action

        state, player_id = self._two_player_state()
        for action in legal_actions_for_current_player(state)[:5]:
            expected = _terminal_planning_value(apply_action(state, action), player_id)
            self.assertEqual(_search_action_value(state, action, player_id, depth=1), expected)

    def test_deeper_search_is_never_worse_than_its_own_beam_leaf_bound(self) -> None:
        """A depth-2 value is a max over real continuations, so it cannot fall
        below the leaf value of any own-turn continuation kept in the beam."""

        from wingspan_ai.agents.potential_points import (
            _play_opponent_turns_in_place,
            _search_action_value,
            _terminal_planning_value,
        )
        from wingspan_ai.rules.base_game import apply_action

        state, player_id = self._two_player_state()
        action = legal_actions_for_current_player(state)[0]
        deep_value = _search_action_value(state, action, player_id, depth=2, beam_width=None)

        branch = apply_action(state, action)
        _play_opponent_turns_in_place(branch, player_id)
        leaf_values = [
            _terminal_planning_value(apply_action(branch, follow_up), player_id)
            for follow_up in legal_actions_for_current_player(branch)
        ]
        self.assertEqual(deep_value, max(leaf_values))

    def test_search_config_round_trips_through_the_agent(self) -> None:
        from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig

        config = PotentialPointsSearchConfig(
            search_depth=2, final_search_turns=8, search_beam_width=3
        )
        agent = PotentialPointsAgent(
            search_depth=config.search_depth,
            final_search_turns=config.final_search_turns,
            search_beam_width=config.search_beam_width,
        )
        self.assertEqual(agent.search_depth, 2)
        self.assertEqual(agent.search_beam_width, 3)
        self.assertEqual(
            config.as_manifest_payload(),
            {"search_depth": 2, "final_search_turns": 8, "search_beam_width": 3},
        )
