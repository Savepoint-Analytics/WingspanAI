"""Posterior over which bonus cards an opponent is holding.

Why this exists
---------------
Denial value needs to answer "is this card exactly what my opponent needs?" The
strongest form of that is bonus-card fit: a niche bird that completes an
opponent's bonus card is worth far more to them than its printed victory points
suggest, and is therefore worth denying.

Bonus cards are hidden. What is public is the opponent's **board** and how many
bonus cards they hold. A player pursuing a bonus card plays birds satisfying it
at an above-chance rate, so the tags on their played birds are evidence.

Information boundary
--------------------
Uses only `PublicPlayerState`: played birds and `bonus_card_count`. Never reads
an opponent's hand or their actual bonus cards.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable

#: Sharpness of the posterior. Lower concentrates probability on the strongest
#: alignment; higher spreads it. Hand-set, not fitted.
BONUS_POSTERIOR_TEMPERATURE = 0.45
#: Guard against a single played bird dominating the estimate.
MIN_BIRDS_FOR_INFERENCE = 2


def normalize_bonus_name(name: str) -> str:
    """Strip expansion suffixes so tags and card names compare equal."""

    return name.split("[", maxsplit=1)[0].strip()


def estimate_bonus_card_posterior(
    played_birds: Iterable,
    bonus_card_count: int,
) -> dict[str, float]:
    """Return P(opponent holds bonus card) keyed by normalized card name.

    Probabilities are scaled so they sum to the number of bonus cards the
    opponent actually holds, which is public. An empty result means the board
    carries no usable evidence yet.
    """

    slots = list(played_birds)
    if bonus_card_count <= 0 or len(slots) < MIN_BIRDS_FOR_INFERENCE:
        return {}

    counts: Counter[str] = Counter()
    for slot in slots:
        for tag in slot.card.bonus_card_tags:
            counts[normalize_bonus_name(tag)] += 1
    if not counts:
        return {}

    # Every bird satisfies many bonus cards, so raw counts are dominated by
    # common tags. Compare each tag against the average tag count on this
    # opponent's own board: a tag well above their own average is the signal
    # that they are steering toward it.
    mean_count = sum(counts.values()) / len(counts)
    if mean_count <= 0:
        return {}

    weights = {
        name: math.exp((count / mean_count - 1.0) / BONUS_POSTERIOR_TEMPERATURE)
        for name, count in counts.items()
    }
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return {}

    # Expected number of held cards is known, so distribute that mass.
    scale = min(bonus_card_count, len(weights))
    return {
        name: min(1.0, scale * weight / total_weight) for name, weight in weights.items()
    }


def bonus_fit_value(
    card,
    posterior: dict[str, float],
) -> float:
    """Expected bonus-card value a card would deliver to the opponent.

    Sums the probability that the opponent holds each bonus card the card
    satisfies. A niche bird matching one likely-held card scores well even when
    its printed victory points are low, which is exactly the case intrinsic
    card-strength scoring misses.
    """

    if not posterior:
        return 0.0
    return sum(
        posterior.get(normalize_bonus_name(tag), 0.0) for tag in card.bonus_card_tags
    )
