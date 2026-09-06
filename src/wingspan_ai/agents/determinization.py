"""Determinized state sampling for search under hidden information.

A search that applies real actions to the full ``GameState`` reads information
the acting player cannot have: the order of the bird deck and opponents' hands
and bonus cards. ``determinize_state`` replaces those with a sample consistent
with what the player can see, so a search over several samples estimates value
under the player's real uncertainty instead of under perfect information.

What the player is assumed to know:

- Own hand and bonus cards, every board, food, eggs, the tray, the feeder, the
  round goals, and hand/bonus-card counts for every opponent.
- The discard piles, which are treated as out of play.

What is resampled:

- The bird deck order, pooled with opponents' hands and redealt.
- The bonus deck order, pooled with opponents' bonus cards and redealt.

- ``random_seed``, from which every future birdfeeder roll (rerolls, refills,
  predator hunts, pink reactions) is derived. Legal actions do not depend on
  it — a gain-food action names preferred foods and the engine resolves the
  roll when the action is applied — so the true state's actions remain legal
  on every sample while the rolls they lead to differ.

Cards an opponent took from the tray in public are not remembered: the sample
draws every opponent hand card from the unseen pool. That discards some
legitimate public information, so the sample is slightly *less* informed than a
perfect-memory player would be.
"""

from __future__ import annotations

import random

from wingspan_ai.state.models import GameState


def determinization_seed_material(state: GameState, player_id: str, sample_index: int) -> str:
    """Seed material for one sample; excludes ``game_id`` so seed-matched batches agree."""

    return (
        f"{state.random_seed}:{state.round_state.global_turn_number}"
        f":{player_id}:determinize:{sample_index}"
    )


def determinize_state(state: GameState, player_id: str, sample_index: int) -> GameState:
    """Return a copy of ``state`` with hidden information resampled for ``player_id``.

    The copy is a deep copy the caller owns; content cards are shared, not
    cloned. Every public element and the acting player's private information
    are unchanged, so any action legal in ``state`` is legal in the sample.
    """

    rng = random.Random(determinization_seed_material(state, player_id, sample_index))
    sample = state.model_copy(deep=True)
    opponents = [player for player in sample.players if player.player_id != player_id]

    bird_pool = list(sample.decks.bird_deck)
    for opponent in opponents:
        bird_pool.extend(opponent.hand)
    rng.shuffle(bird_pool)
    for opponent in opponents:
        hand_size = len(opponent.hand)
        opponent.hand = bird_pool[:hand_size]
        del bird_pool[:hand_size]
    sample.decks.bird_deck = bird_pool

    bonus_pool = list(sample.decks.bonus_deck)
    for opponent in opponents:
        bonus_pool.extend(opponent.bonus_cards)
    rng.shuffle(bonus_pool)
    for opponent in opponents:
        bonus_count = len(opponent.bonus_cards)
        opponent.bonus_cards = bonus_pool[:bonus_count]
        del bonus_pool[:bonus_count]
    sample.decks.bonus_deck = bonus_pool

    sample.random_seed = rng.getrandbits(63)
    return sample
