"""The joint opener, adopted 2026-10-06 on mechanism rather than a significance test.

The defect it fixes: ``expected_bonus_points`` -- which prices every bonus card
from its parsed scoring rule and printed prevalence -- chose the card against
the **dealt five**, including birds about to be discarded, while the tradeoff
inside the keep loop was priced by ``_bonus_alignment_score``, a hand-written
if-chain covering about a dozen named cards and returning 0 for everything else.
The good scorer saw the wrong card set and the crude one made the decision, so
both bonus cards tied at the optimum in 37% of 240 openings.

These tests pin the three things that make the fix work, each of which would
silently undo it: both bonus cards are considered, the bonus is priced against
the kept cards, and the frequent ties are broken by the richer scorer rather
than by iteration order.
"""

from __future__ import annotations

from unittest import TestCase

from wingspan_ai.agents.potential_points import DEFAULT_HOLDOUTS, PotentialPointsAgent
from wingspan_ai.agents.setup import (
    BONUS_SCORING_KINDS,
    DEFAULT_BONUS_SCORING,
    InitialSelectionContext,
    expected_bonus_points,
    potential_points_setup_policy,
)
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.rules.base_game import setup_base_game

CATALOG = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)


DEFAULT_SEEDS = tuple(range(1, 41))


def openings(policy, seeds=DEFAULT_SEEDS, players=("p1", "p2")):
    """``(player, context, selection)`` per seat over several deals."""

    out = []
    for seed in seeds:
        state = setup_base_game(
            CATALOG, player_ids=list(players), random_seed=seed, apply_initial_selection=False
        )
        context = InitialSelectionContext(
            round_goal_names=tuple(goal.name for goal in state.round_goals)
        )
        for player in state.players:
            out.append((player, context, policy.choose_initial_selection(player, context)))
    return out


class AdoptionTests(TestCase):
    def test_joint_is_the_default(self) -> None:
        self.assertEqual(DEFAULT_BONUS_SCORING, "joint")
        self.assertIn("joint", BONUS_SCORING_KINDS)

    def test_the_default_agent_uses_the_v4_opener(self) -> None:
        agent = PotentialPointsAgent(agent_id="test")
        self.assertEqual(agent.setup_policy.policy_id, "potential_points_setup_v4")

    def test_the_previous_opener_is_held_out(self) -> None:
        """Every adopted switch keeps its losing side in 5% of games."""

        setup_holdouts = [h for h in DEFAULT_HOLDOUTS if h.field == "setup_policy"]
        self.assertEqual(len(setup_holdouts), 1, "two holdouts cannot share a field")
        self.assertEqual(setup_holdouts[0].value, "potential_points_setup_v2")


class JointEnumerationTests(TestCase):
    def test_both_bonus_cards_are_reachable(self) -> None:
        """If only one were ever considered, the fix would be inert.

        The old opener picked the bonus first, so the keep loop could never
        choose the other one however well it fitted the kept birds.
        """

        joint = potential_points_setup_policy("potential_points_setup_v4")
        previous = potential_points_setup_policy("potential_points_setup_v2")
        changed = sum(
            1
            for (player, context, selection) in openings(joint)
            if selection.kept_bonus_card_names
            != previous.choose_initial_selection(player, context).kept_bonus_card_names
        )
        self.assertGreater(changed, 0, "the joint opener never picks the other bonus card")

    def test_the_bonus_price_never_credits_discarded_birds(self) -> None:
        """The scorer contract: a keep set can only have fewer qualifiers.

        Measured, this bites rarely -- the opener keeps all five birds in 570
        of 600 openings, so the kept set usually *is* the dealt hand and subset
        pricing changes the figure in 0.3% of openings. The contract is pinned
        anyway because the keep-count behaviour is itself suspect and may
        change, at which point this becomes load-bearing.
        """

        joint = potential_points_setup_policy("potential_points_setup_v4")
        checked = 0
        for player, _context, selection in openings(joint, seeds=tuple(range(1, 151))):
            kept_names = set(selection.kept_bird_names)
            if len(kept_names) == len(player.hand):
                continue  # kept is the dealt hand; nothing to distinguish
            kept = [card for card in player.hand if card.common_name in kept_names]
            for bonus in player.bonus_cards:
                self.assertLessEqual(
                    expected_bonus_points(bonus, kept),
                    expected_bonus_points(bonus, player.hand) + 1e-9,
                    f"{bonus.name} scores higher on the keep set than on the dealt hand",
                )
            checked += 1
        self.assertGreater(checked, 0, "no opening kept a strict subset; the test is vacuous")

    def test_the_bonus_choice_responds_to_the_whole_opening_score(self) -> None:
        """The mechanism that actually drives the change.

        v2 chose the bonus by ``expected_bonus_points`` alone and then used a
        crude alignment term inside the keep loop. v4 chooses it by the whole
        opening score including its expected points, so a card can win on fit
        with the kept birds even when its standalone expectation is lower.
        """

        joint = potential_points_setup_policy("potential_points_setup_v4")
        overridden = 0
        for player, _context, selection in openings(joint, seeds=tuple(range(1, 151))):
            standalone = max(
                player.bonus_cards,
                key=lambda bonus: (expected_bonus_points(bonus, player.hand), bonus.name),
            )
            if standalone.name not in selection.kept_bonus_card_names:
                overridden += 1
        self.assertGreater(
            overridden,
            0,
            "the joint opener never overrode the standalone bonus expectation, "
            "so it is equivalent to the opener it replaced",
        )

    def test_every_opening_is_valid(self) -> None:
        for player, _context, selection in openings(
            potential_points_setup_policy("potential_points_setup_v4")
        ):
            hand = {card.common_name for card in player.hand}
            bonuses = {card.name for card in player.bonus_cards}
            self.assertTrue(set(selection.kept_bird_names) <= hand)
            self.assertEqual(len(selection.kept_bonus_card_names), 1)
            self.assertTrue(set(selection.kept_bonus_card_names) <= bonuses)
            # Keep N birds and 5 - N food, per the rulebook's setup trade.
            self.assertEqual(
                len(selection.kept_bird_names) + len(selection.starting_food), 5
            )

    def test_openings_are_deterministic(self) -> None:
        policy = potential_points_setup_policy("potential_points_setup_v4")
        first = [s.kept_bird_names + s.kept_bonus_card_names for _p, _c, s in openings(policy)]
        second = [s.kept_bird_names + s.kept_bonus_card_names for _p, _c, s in openings(policy)]
        self.assertEqual(first, second)

    def test_three_players_are_supported(self) -> None:
        rows = openings(
            potential_points_setup_policy("potential_points_setup_v4"),
            seeds=range(1, 6),
            players=("p1", "p2", "p3"),
        )
        self.assertEqual(len(rows), 15)


class PolicyIdTests(TestCase):
    def test_the_joint_ids_round_trip(self) -> None:
        for policy_id in (
            "potential_points_setup_v4",
            "potential_points_setup_v4_measured",
            "potential_points_setup_v4_allgoals",
        ):
            self.assertEqual(
                potential_points_setup_policy(policy_id).policy_id, policy_id
            )

    def test_the_previous_ids_still_resolve(self) -> None:
        """Archived manifests name them, and the holdout selects one."""

        for policy_id in (
            "potential_points_setup_v1",
            "potential_points_setup_v2",
            "potential_points_setup_v3",
            "potential_points_setup_v3_keep3",
        ):
            self.assertEqual(
                potential_points_setup_policy(policy_id).policy_id, policy_id
            )
