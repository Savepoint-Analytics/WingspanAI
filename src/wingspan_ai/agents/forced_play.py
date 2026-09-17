"""Forced keep-and-play: the layer C instrument of the synergy programme.

A card combination is confirmed by making it happen. ``inject_opening_cards``
swaps named birds into a player's dealt opening hand (from the deck, so the
deck loses exactly those cards and gains the ones displaced — everything else
about the seed is untouched). ``KeepBirdsSetupPolicy`` keeps them through the
opening choice. ``ForcedPlayAgent`` plays them as soon as they are legal,
preferring a habitat the pair can share, and otherwise defers to the wrapped
agent.

The design is a 2×2 per seed — {A, B}, {A, B'}, {A', B}, {A', B'} with A', B'
matched non-interacting controls — so the interaction contrast
``(AB − AB') − (A'B − A'B')`` isolates what the *combination* is worth over
and above each card's own value. Because every arm forces its two cards the
same way, forcing itself cancels.

Injections are recorded in the ``game_started`` event and re-applied by the
replay validator, so replay hashes still verify.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from wingspan_ai.agents.setup import InitialSelectionContext, InitialSetupPolicy
from wingspan_ai.content.schemas import FoodType, Habitat
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import (
    InitialSelection,
    apply_action,
    expected_gain_food,
    legal_actions_for_current_player,
)
from wingspan_ai.state.models import GameState, PlayerState


def inject_opening_cards(state: GameState, player_id: str, bird_names: list[str]) -> list[str]:
    """Swap the named birds from the deck into the player's dealt hand, in place.

    The i-th injected bird replaces the i-th hand card that is not itself
    being injected; the displaced card takes the injected bird's deck
    position, so deck order and length are otherwise preserved. Birds that
    are already in hand are kept where they are. Returns the names that could
    not be injected (not in the deck — dealt to another player, in the tray,
    or already discarded); the caller decides whether such a game counts.
    """

    player = next(p for p in state.players if p.player_id == player_id)
    deck = state.decks.bird_deck
    wanted = set(bird_names)
    missing: list[str] = []
    replaceable = [i for i, card in enumerate(player.hand) if card.common_name not in wanted]
    for name in bird_names:
        if any(card.common_name == name for card in player.hand):
            continue
        deck_index = next((i for i, card in enumerate(deck) if card.common_name == name), None)
        if deck_index is None or not replaceable:
            missing.append(name)
            continue
        hand_index = replaceable.pop(0)
        deck[deck_index], player.hand[hand_index] = player.hand[hand_index], deck[deck_index]
    return missing


def grant_opening_food(state: GameState, player_id: str, count: int) -> None:
    """Give a player ``count`` of every base food before the opening choice."""

    from wingspan_ai.content.loader import BASE_FOOD_TYPES

    player = next(p for p in state.players if p.player_id == player_id)
    for food_type in BASE_FOOD_TYPES:
        player.food_tokens[food_type] = player.food_tokens.get(food_type, 0) + count


@dataclass(frozen=True)
class KeepBirdsSetupPolicy:
    """Keep the named birds at setup; let ``base_policy`` choose the rest."""

    base_policy: InitialSetupPolicy
    bird_names: tuple[str, ...]
    policy_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", f"keep_birds:{self.base_policy.policy_id}")

    def choose_initial_selection(
        self,
        player: PlayerState,
        context: InitialSelectionContext | None = None,
    ) -> InitialSelection:
        forced = [card for card in player.hand if card.common_name in self.bird_names]
        rest = player.model_copy(
            update={
                "hand": [card for card in player.hand if card.common_name not in self.bird_names]
            }
        )
        base = self.base_policy.choose_initial_selection(rest, context)
        # Opening keeps birds + food = 5. The forced birds displace the base
        # policy's birds, not its food, so the opening economy is unchanged.
        room = max(len(base.kept_bird_names), len(forced))
        kept = [card.common_name for card in forced] + list(base.kept_bird_names)
        kept = kept[:room]
        food = list(base.starting_food)[: max(0, 5 - len(kept))]
        return InitialSelection(
            player_id=player.player_id,
            kept_bird_names=kept,
            kept_bonus_card_names=list(base.kept_bonus_card_names),
            starting_food=food,
        )


@dataclass
class ForcedPlayAgent:
    """Play the named birds as soon as legal; otherwise defer to the wrapped agent."""

    base_agent: object
    bird_names: tuple[str, ...]
    agent_id: str | None = None
    #: When the forced pair can share a habitat, play into it so same-row
    #: powers can interact; the wrapped agent ranks the remaining choice.
    prefer_shared_habitat: bool = True

    def __post_init__(self) -> None:
        # Keep the wrapped agent's id: telemetry and manifests already record
        # the forcing explicitly, and downstream analysis keys on agent ids.
        if self.agent_id is None:
            self.agent_id = self.base_agent.agent_id
        base_setup = getattr(self.base_agent, "setup_policy", None)
        if base_setup is not None:
            self.base_agent.setup_policy = KeepBirdsSetupPolicy(base_setup, self.bird_names)

    @property
    def setup_policy(self):
        return getattr(self.base_agent, "setup_policy", None)

    def choose_initial_selection(self, player: PlayerState, context=None) -> InitialSelection:
        return self.base_agent.choose_initial_selection(player, context)

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        forced = [
            action
            for action in legal_actions
            if action.action_type == ActionType.PLAY_BIRD
            and action.bird_common_name in self.bird_names
        ]
        player = state.active_player
        # Anything that would strip a waiting forced bird out of the hand
        # (a tuck-from-hand power on the row being activated, a discard) is
        # off the table while the pair is incomplete.
        legal_actions = self._keeps_forced_birds(state, legal_actions)
        if not forced:
            return self.base_agent.select_action(state, self._steer_food(state, legal_actions))
        # When the wrapper decides to wait, the base agent must not be able to
        # play a forced bird into the wrong row on its own.
        deferred = self._steer_food(state, [a for a in legal_actions if a not in forced])
        if self.prefer_shared_habitat:
            shared = self._shared_habitats(state)
            in_shared = [a for a in forced if a.habitat in shared]
            row_open = any(len(player.habitats[h]) < 5 for h in shared)
            if in_shared:
                forced = in_shared
            elif row_open:
                # The shared row exists but is not enterable yet (an egg it
                # cannot pay, usually): wait rather than split the pair, and
                # if eggs are what is missing, go and lay some.
                if player.total_eggs == 0:
                    lay = [a for a in deferred if a.action_type == ActionType.LAY_EGGS]
                    if lay:
                        return self.base_agent.select_action(state, lay)
                return self.base_agent.select_action(state, deferred or legal_actions)
        # A forced play must not consume food a waiting partner still needs.
        waiting = [card for card in player.hand if card.common_name in self.bird_names]
        safe = []
        for action in forced:
            others = [card for card in waiting if card.common_name != action.bird_common_name]
            if not others:
                safe.append(action)
                continue
            after = apply_action(state, action)
            after_player = next(p for p in after.players if p.player_id == player.player_id)
            before_short = sum(
                max(count - player.food_tokens.get(food_type, 0), 0)
                for card in others
                for food_type, count in card.food_cost.fixed.items()
            )
            after_short = sum(
                max(count - after_player.food_tokens.get(food_type, 0), 0)
                for card in others
                for food_type, count in card.food_cost.fixed.items()
            )
            if after_short <= before_short:
                safe.append(action)
        if not safe:
            return self.base_agent.select_action(state, deferred or legal_actions)
        return self.base_agent.select_action(state, safe)

    def _keeps_forced_birds(
        self, state: GameState, legal_actions: list[LegalAction]
    ) -> list[LegalAction]:
        player = state.active_player
        waiting = {card.common_name for card in player.hand if card.common_name in self.bird_names}
        if not waiting:
            return legal_actions
        kept = []
        for action in legal_actions:
            played = action.bird_common_name if action.action_type == ActionType.PLAY_BIRD else None
            after = apply_action(state, action)
            after_player = next(p for p in after.players if p.player_id == player.player_id)
            still = {card.common_name for card in after_player.hand}
            lost = {name for name in waiting if name not in still and name != played}
            if not lost:
                kept.append(action)
        return kept or legal_actions

    def _steer_food(self, state: GameState, legal_actions: list[LegalAction]) -> list[LegalAction]:
        """When a forced bird waits on food, keep only the gain-food actions that supply it.

        "Keep and play" has to include getting the bird onto the board: a
        two-rodent hawk is never played by an agent that never takes rodents.
        Only fixed costs are steered; wild costs any food can pay.
        """

        player = state.active_player
        waiting = [card for card in player.hand if card.common_name in self.bird_names]
        if not waiting:
            return legal_actions
        needed: Counter[FoodType] = Counter()
        for card in waiting:
            for food_type, count in card.food_cost.fixed.items():
                needed[food_type] += max(count - player.food_tokens.get(food_type, 0), 0)
        if not needed:
            return legal_actions
        supplying = [
            action
            for action in legal_actions
            if action.action_type == ActionType.GAIN_FOOD
            and any(needed.get(food_type, 0) > 0 for food_type in expected_gain_food(state, action))
        ]
        if supplying:
            return supplying
        # No way to gain what is needed this turn: at least do not spend it.
        # Other bird plays are kept only if the forced birds' shortfall does
        # not grow after paying for them.
        shortfall_now = sum(needed.values())
        kept = []
        for action in legal_actions:
            if action.action_type != ActionType.PLAY_BIRD:
                kept.append(action)
                continue
            after = apply_action(state, action)
            after_player = next(p for p in after.players if p.player_id == player.player_id)
            shortfall_after = sum(
                max(count - after_player.food_tokens.get(food_type, 0), 0)
                for card in waiting
                for food_type, count in card.food_cost.fixed.items()
            )
            if shortfall_after <= shortfall_now:
                kept.append(action)
        return kept or legal_actions

    def _shared_habitats(self, state: GameState) -> set[Habitat]:
        """Habitats every forced bird (in hand or on board) can live in."""

        player = state.active_player
        cards = [card for card in player.hand if card.common_name in self.bird_names]
        for habitat in Habitat:
            for slot in player.habitats[habitat]:
                if slot.card.common_name in self.bird_names:
                    cards.append(slot.card)
        if not cards:
            return set(Habitat)
        shared = set(cards[0].habitats)
        for card in cards[1:]:
            shared &= set(card.habitats)
        # A forced bird already on the board pins the row.
        for habitat in Habitat:
            if any(slot.card.common_name in self.bird_names for slot in player.habitats[habitat]):
                return {habitat} if habitat in shared or not shared else shared
        return shared or set(Habitat)

    def choose_action(self, state: GameState) -> LegalAction:
        return self.select_action(state, legal_actions_for_current_player(state))

    def observe_action(
        self, state_before: GameState, action: LegalAction, acting_player_id: str
    ) -> None:
        observer = getattr(self.base_agent, "observe_action", None)
        if observer is not None:
            observer(state_before, action, acting_player_id)

    def summarize_decision(
        self, state: GameState, legal_actions: list[LegalAction], selected_action: LegalAction
    ) -> dict:
        summarizer = getattr(self.base_agent, "summarize_decision", None)
        payload = summarizer(state, legal_actions, selected_action) if callable(summarizer) else {}
        return {
            **payload,
            "forced_play_birds": list(self.bird_names),
            "forced_play_applied": (
                selected_action.action_type == ActionType.PLAY_BIRD
                and selected_action.bird_common_name in self.bird_names
            ),
        }
