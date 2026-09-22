"""Placement model for end-of-round goals: what is my share of the goal worth?

Why this module exists
----------------------
``potential_points`` valued the current round's goal with a reachability
heuristic — a gap in items, a flat 0.6 a turn, zero if unreachable. It could
not express three things the 2026-09-22 mirror measurement showed decide
goals (``docs/experiments/strategy_findings.md`` §4):

* **What the round pays.** The green scale is 4/1 in round 1 and 7/4/3 in
  round 4. The heuristic scored them identically, so it undervalued late
  goals by nearly half.
* **The opponent's remaining turns.** A one-item lead with the opponent
  holding four turns is not a lead.
* **Ties.** 13–16% of rounds tie for first, and a tie splits the top two
  slots rounded down — worth two points less to the leader than winning.

This module answers "what is the goal worth to me from here?" as an
expectation in points:

    E[points] = Σ_placement P(placement | counts, turns left) × scale[placement]

Each player's final count is modelled as their current count plus a Poisson
draw with mean ``rate(goal) × turns_left``, the rate measured from the
archive by ``analysis/fit_round_goal_progress.py``. Placement is then the
rank of the final counts, with ties splitting slots the way
``score_round_goal_competitive`` does.

Information boundary
--------------------
Counts and remaining action cubes are public. The model reads nothing else.

For the template
----------------
Nothing here is Wingspan-specific beyond the count function passed in: a
placement scale, per-player progress rates and remaining turns describe any
competitive intermediate scoring.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_PROGRESS_RATES_PATH = "configs/round_goals/progress_rates.json"
#: Final counts are modelled up to this many items above the current count;
#: beyond it the Poisson tail is negligible for the rates involved (< 1e-4).
MAX_EXTRA_ITEMS = 12


@dataclass(frozen=True)
class GoalProgressRates:
    """Items gained per remaining turn, per goal, measured from the archive."""

    pooled_rate: float
    by_goal: Mapping[str, float]
    version: str = "round_goal_progress_v1"

    def rate_for(self, goal_name: str) -> float:
        return self.by_goal.get(goal_name, self.pooled_rate)


@lru_cache(maxsize=4)
def load_progress_rates(path: str | None = None) -> GoalProgressRates:
    resolved = path or DEFAULT_PROGRESS_RATES_PATH
    candidate = Path(resolved)
    if not candidate.is_absolute() and not candidate.exists():
        candidate = Path(__file__).resolve().parents[3] / resolved
    data = json.loads(candidate.read_text(encoding="utf-8"))
    return GoalProgressRates(
        pooled_rate=float(data["pooled_rate_per_turn"]),
        by_goal={
            goal: float(entry["rate_per_turn"]) for goal, entry in data.get("goals", {}).items()
        },
        version=data.get("version", "round_goal_progress_v1"),
    )


def _poisson_pmf(mean_value: float, limit: int) -> list[float]:
    """PMF of a Poisson over 0..limit, with the tail folded into the last cell."""

    if mean_value <= 0:
        return [1.0] + [0.0] * limit
    pmf = []
    term = math.exp(-mean_value)
    total = 0.0
    for k in range(limit + 1):
        if k:
            term *= mean_value / k
        pmf.append(term)
        total += term
    pmf[-1] += max(0.0, 1.0 - total)
    return pmf


def final_count_distribution(
    current_count: int, turns_left: int, rate_per_turn: float
) -> dict[int, float]:
    """Distribution over a player's count when the round is scored."""

    expected_gain = max(0.0, rate_per_turn) * max(0, turns_left)
    pmf = _poisson_pmf(expected_gain, MAX_EXTRA_ITEMS)
    return {current_count + k: probability for k, probability in enumerate(pmf) if probability}


def expected_placement_points(
    own_count: int,
    own_turns_left: int,
    opponent_counts: Sequence[int],
    opponent_turns_left: Sequence[int],
    placement_scores: Sequence[int],
    rate_per_turn: float,
) -> float:
    """Expected goal points for the acting player when this round is scored.

    Enumerates the acting player's final count against each opponent's
    distribution independently, which is the same independence the belief
    model and the search's determinization already assume; the alternative
    (joint opponent play) needs a model of their interaction that no part of
    this project has.
    """

    if not placement_scores:
        return 0.0
    own = final_count_distribution(own_count, own_turns_left, rate_per_turn)
    others = [
        final_count_distribution(count, turns, rate_per_turn)
        for count, turns in zip(opponent_counts, opponent_turns_left, strict=True)
    ]
    total = 0.0
    for own_final, own_probability in own.items():
        if own_probability < 1e-9:
            continue
        if own_final <= 0:
            # A player with no items scores nothing, however others place.
            continue
        # Per opponent: P(they beat me), P(they tie me).
        beat_tie = []
        for distribution in others:
            beat = sum(p for count, p in distribution.items() if count > own_final)
            tie = distribution.get(own_final, 0.0)
            beat_tie.append((beat, tie))
        total += own_probability * _expected_score_given_own(own_final, beat_tie, placement_scores)
    return total


def _expected_score_given_own(
    own_final: int,
    beat_tie: Sequence[tuple[float, float]],
    placement_scores: Sequence[int],
) -> float:
    """Expected score given my final count, summing over how many beat/tie me.

    Convolves the per-opponent (beat, tie, below) trinomial into a
    distribution over (ahead, level) counts, then applies the rule
    ``score_round_goal_competitive`` uses: the players level with me share
    the slots after those ahead of me, rounded down.
    """

    distribution: dict[tuple[int, int], float] = {(0, 0): 1.0}
    for beat, tie in beat_tie:
        updated: dict[tuple[int, int], float] = {}
        for (ahead, level), probability in distribution.items():
            for delta_ahead, delta_level, share in (
                (1, 0, beat),
                (0, 1, tie),
                (0, 0, max(0.0, 1.0 - beat - tie)),
            ):
                if share <= 0:
                    continue
                key = (ahead + delta_ahead, level + delta_level)
                updated[key] = updated.get(key, 0.0) + probability * share
        distribution = updated

    expected = 0.0
    for (ahead, level), probability in distribution.items():
        if probability < 1e-12:
            continue
        slots = placement_scores[ahead : ahead + level + 1]
        expected += probability * ((sum(slots) // (level + 1)) if slots else 0)
    return expected
