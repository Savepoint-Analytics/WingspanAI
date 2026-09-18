"""Standing holdouts: every adopted or dropped switch keeps its other side alive.

Why this module exists
----------------------
An arm is adopted or dropped on one paired experiment, usually 80 games. That
is enough to act on and not enough to be sure of: a −4.5 that was really a
−1 with bad luck stays dropped forever, and an adopted default that only
looked good against this week's roster is never re-examined. Alex's rule
(2026-09-17): keep every decided arm running in a deterministic minority of
games, so the decision is a long-run A/B test with a guardrail rather than a
one-shot verdict.

Design
------
A ``Holdout`` names a config field, the value it reverts to (the losing side
of the decision), and a share. Which games revert is a SHA-256 draw over the
field name, the seed, the lineup and the agent's position in it, so:

- seed-matched arms hold out the same games and stay paired;
- both seat rotations of a game hold out together;
- each field draws independently, so with ``n`` holdouts at 5% roughly
  ``1 − 0.95**n`` of games deviate from the default somewhere.

The manifest records the effective configuration and the applied holdouts
per seat; ``analysis/holdout_guardrail.py`` pools them across batches and
reports each field's preferred-vs-held-out contrast with its detection limit.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Holdout:
    """Revert ``field`` to ``value`` in a ``share`` of games."""

    field: str
    value: Any
    share: float = 0.05

    def __post_init__(self) -> None:
        if not 0.0 <= self.share <= 1.0:
            raise ValueError(f"holdout share must be in [0, 1], got {self.share}")


def holdout_draw(key: str) -> float:
    """Uniform draw in [0, 1) from a string key, stable across processes and versions."""

    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def resolve_holdouts(
    values: Mapping[str, Any],
    holdouts: Iterable[Holdout],
    *,
    random_seed: int,
    lineup: Sequence[str],
    lineup_position: int,
) -> tuple[dict[str, Any], list[str]]:
    """Return ``(effective values, fields held out)`` for one agent in one game."""

    effective = dict(values)
    applied: list[str] = []
    for holdout in holdouts:
        if holdout.share <= 0.0 or holdout.field not in effective:
            continue
        if effective[holdout.field] == holdout.value:
            continue
        key = f"holdout:{holdout.field}:{random_seed}:{','.join(lineup)}:{lineup_position}"
        if holdout_draw(key) < holdout.share:
            effective[holdout.field] = holdout.value
            applied.append(holdout.field)
    return effective, applied
