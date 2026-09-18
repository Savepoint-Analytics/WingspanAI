"""Measured per-bird play values for card-choice decisions.

The table (``configs/bird_values/bird_play_values_k4.json``, written by
``analysis/bird_play_values.py``) gives each bird the expected final-score
gain of playing it in round 1, estimated by exact counterfactual rollouts
over archived games with K=4 determinized continuations and shrunk toward
the mean play by an lme4 random effect. Unlisted birds take the intercept.

Values are conditional on the searching agent having chosen to play the
bird, so a bird it rarely plays is thinly observed and sits near the mean;
that is what a card-choice decision should assume about it anyway.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BIRD_PLAY_VALUES = "configs/bird_values/bird_play_values_k4.json"


@dataclass(frozen=True)
class BirdPlayValues:
    version: str
    intercept: float
    values: dict[str, float]

    def value(self, bird_name: str) -> float:
        return self.values.get(bird_name, self.intercept)


_CACHE: dict[str, BirdPlayValues] = {}


def load_bird_play_values(path: str | None = None) -> BirdPlayValues:
    resolved = path or DEFAULT_BIRD_PLAY_VALUES
    if resolved not in _CACHE:
        candidate = Path(resolved)
        if not candidate.is_absolute() and not candidate.exists():
            candidate = Path(__file__).resolve().parents[3] / resolved
        data = json.loads(candidate.read_text(encoding="utf-8"))
        _CACHE[resolved] = BirdPlayValues(
            version=data["version"],
            intercept=float(data["intercept_round1"]),
            values={name: float(entry["value"]) for name, entry in data["values"].items()},
        )
    return _CACHE[resolved]
