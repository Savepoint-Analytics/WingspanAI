"""Bayesian opponent-type beliefs and action-family response probabilities.

Why this module exists
----------------------
`NetValueOpponentResponseAgent` previously predicted the opponent's next move as
the single highest-value public candidate. The first calibration probe
(`docs/experiments/public_belief_calibration.md`) showed why that fails: against
a random-legal opponent the model predicted 39 lay-eggs and 39 play-bird and
zero draw-card or gain-food turns, while the opponent actually drew 35 times and
gained food 18 times. Exact-match accuracy was 16.7%.

The fix is not a better point estimate. A best-response model asks "what is the
strongest reply?" when the decision-relevant question is "what is the opponent
likely to do?". This module answers the second question with a distribution over
action families, marginalized over a posterior about *what kind of player* the
opponent is.

Model
-----
For opponent type ``z`` and action family ``a`` with public value estimate
``v(a)``:

    P(a | z) is proportional to  prior(a | z) * exp(v(a) / T(z))

``prior(a | z)`` captures how often a player of type ``z`` picks family ``a``
regardless of value, and ``T(z)`` is a rationality temperature. A large ``T``
ignores value entirely (a random opponent); a small ``T`` collapses to
best-response (a strict maximizer). The predictive distribution marginalizes:

    P(a) = sum over z of  P(z) * P(a | z)

Observing the opponent's actual action updates ``P(z)`` by Bayes' rule, so the
belief sharpens toward the opponent's real type as the game proceeds.

Information boundary
--------------------
Everything here consumes only public candidate values supplied by the caller.
This module never reads hidden hands, bonus cards, or deck order.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from wingspan_ai.rules.actions import ActionType

BELIEF_MODEL_ID = "opponent_type_response_belief_v1"

#: Families a base-game opponent can choose between on their turn.
ACTION_FAMILIES: tuple[ActionType, ...] = (
    ActionType.PLAY_BIRD,
    ActionType.GAIN_FOOD,
    ActionType.LAY_EGGS,
    ActionType.DRAW_CARDS,
)

# Guards against overflow when a value estimate is large relative to temperature.
_MAX_LOGIT = 60.0
_MIN_PROBABILITY = 1e-9


class OpponentProfile(StrEnum):
    """Opponent types the belief model can distinguish from public behaviour."""

    RANDOM_LEGAL = "random_legal"
    VALUE_MAXIMIZING = "value_maximizing"
    ENGINE_BUILDER = "engine_builder"
    EGG_FOCUS = "egg_focus"
    CARD_DRAW = "card_draw"
    FOOD_ACCELERATION = "food_acceleration"


@dataclass(frozen=True)
class ProfileResponseModel:
    """Family priors and rationality temperature for one opponent type."""

    profile: OpponentProfile
    family_prior: Mapping[ActionType, float]
    #: Higher temperature means public value estimates matter less.
    value_temperature: float

    def family_probabilities(
        self,
        candidate_values: Mapping[ActionType, float],
    ) -> dict[ActionType, float]:
        """Return P(family | profile) over the families that are available."""

        if not candidate_values:
            return {}
        logits: dict[ActionType, float] = {}
        for family, value in candidate_values.items():
            prior = max(self.family_prior.get(family, 0.0), _MIN_PROBABILITY)
            if math.isinf(self.value_temperature):
                scaled_value = 0.0
            else:
                scaled_value = value / self.value_temperature
            logits[family] = math.log(prior) + _clip_logit(scaled_value)
        return _softmax(logits)


def _clip_logit(value: float) -> float:
    return max(-_MAX_LOGIT, min(_MAX_LOGIT, value))


def _softmax(logits: Mapping[ActionType, float]) -> dict[ActionType, float]:
    if not logits:
        return {}
    highest = max(logits.values())
    weights = {family: math.exp(logit - highest) for family, logit in logits.items()}
    total = sum(weights.values())
    if total <= 0:
        uniform = 1.0 / len(logits)
        return dict.fromkeys(logits, uniform)
    return {family: weight / total for family, weight in weights.items()}


def _normalize(weights: Mapping[OpponentProfile, float]) -> dict[OpponentProfile, float]:
    total = sum(max(weight, 0.0) for weight in weights.values())
    if total <= 0:
        uniform = 1.0 / len(weights) if weights else 0.0
        return dict.fromkeys(weights, uniform)
    return {profile: max(weight, 0.0) / total for profile, weight in weights.items()}


# Family priors for a uniformly random legal agent are not uniform over families.
# A random agent samples a concrete legal action, and families expand into very
# different numbers of concrete actions: draw-card choices over tray/deck
# combinations dominate, while lay-eggs usually expands to one or two options.
# These weights are taken from the observed action mix of `random_legal_p1` in
# the 3-seed calibration probe (draw 35, food 18, play 17, eggs 8 of 78 turns),
# documented in docs/experiments/public_belief_calibration.md.
RANDOM_LEGAL_FAMILY_PRIOR: dict[ActionType, float] = {
    ActionType.DRAW_CARDS: 0.45,
    ActionType.GAIN_FOOD: 0.23,
    ActionType.PLAY_BIRD: 0.22,
    ActionType.LAY_EGGS: 0.10,
}

UNIFORM_FAMILY_PRIOR: dict[ActionType, float] = dict.fromkeys(ACTION_FAMILIES, 0.25)


def _tilted_prior(favoured: ActionType, weight: float = 0.45) -> dict[ActionType, float]:
    """Prior that favours one family while keeping the rest plausible."""

    remainder = (1.0 - weight) / (len(ACTION_FAMILIES) - 1)
    return {
        family: weight if family == favoured else remainder for family in ACTION_FAMILIES
    }


DEFAULT_PROFILE_MODELS: dict[OpponentProfile, ProfileResponseModel] = {
    OpponentProfile.RANDOM_LEGAL: ProfileResponseModel(
        profile=OpponentProfile.RANDOM_LEGAL,
        family_prior=RANDOM_LEGAL_FAMILY_PRIOR,
        # Infinite temperature: a random opponent ignores value entirely.
        value_temperature=math.inf,
    ),
    OpponentProfile.VALUE_MAXIMIZING: ProfileResponseModel(
        profile=OpponentProfile.VALUE_MAXIMIZING,
        family_prior=UNIFORM_FAMILY_PRIOR,
        # Low temperature approaches the previous best-response behaviour.
        value_temperature=0.75,
    ),
    OpponentProfile.ENGINE_BUILDER: ProfileResponseModel(
        profile=OpponentProfile.ENGINE_BUILDER,
        family_prior=_tilted_prior(ActionType.PLAY_BIRD),
        value_temperature=2.0,
    ),
    OpponentProfile.EGG_FOCUS: ProfileResponseModel(
        profile=OpponentProfile.EGG_FOCUS,
        family_prior=_tilted_prior(ActionType.LAY_EGGS),
        value_temperature=2.0,
    ),
    OpponentProfile.CARD_DRAW: ProfileResponseModel(
        profile=OpponentProfile.CARD_DRAW,
        family_prior=_tilted_prior(ActionType.DRAW_CARDS),
        value_temperature=2.0,
    ),
    OpponentProfile.FOOD_ACCELERATION: ProfileResponseModel(
        profile=OpponentProfile.FOOD_ACCELERATION,
        family_prior=_tilted_prior(ActionType.GAIN_FOOD),
        value_temperature=2.0,
    ),
}


@dataclass(frozen=True)
class ResponseDistribution:
    """Predicted distribution over the opponent's next action family."""

    opponent_id: str | None
    probabilities: Mapping[ActionType, float]
    candidate_values: Mapping[ActionType, float]
    profile_posterior: Mapping[OpponentProfile, float]
    model_id: str = BELIEF_MODEL_ID

    @property
    def expected_value(self) -> float:
        """Probability-weighted opponent value, not the single best reply."""

        return sum(
            self.probabilities.get(family, 0.0) * value
            for family, value in self.candidate_values.items()
        )

    @property
    def best_value(self) -> float:
        return max(self.candidate_values.values(), default=0.0)

    @property
    def most_likely_family(self) -> ActionType | None:
        if not self.probabilities:
            return None
        return max(
            self.probabilities,
            key=lambda family: (self.probabilities[family], family.value),
        )

    @property
    def most_likely_profile(self) -> OpponentProfile | None:
        if not self.profile_posterior:
            return None
        return max(
            self.profile_posterior,
            key=lambda profile: (self.profile_posterior[profile], profile.value),
        )

    def probability_of(self, family: ActionType) -> float:
        return self.probabilities.get(family, 0.0)

    def ranked_families(self) -> list[tuple[ActionType, float]]:
        return sorted(
            self.probabilities.items(),
            key=lambda item: (-item[1], item[0].value),
        )

    def as_telemetry_payload(self) -> dict[str, object]:
        """Return a JSON-serializable summary for decision telemetry."""

        return {
            "model_id": self.model_id,
            "opponent_id": self.opponent_id,
            "expected_value": round(self.expected_value, 4),
            "best_value": round(self.best_value, 4),
            "most_likely_family": (
                self.most_likely_family.value if self.most_likely_family else None
            ),
            "most_likely_profile": (
                self.most_likely_profile.value if self.most_likely_profile else None
            ),
            "family_probabilities": {
                family.value: round(probability, 4)
                for family, probability in self.ranked_families()
            },
            "profile_posterior": {
                profile.value: round(probability, 4)
                for profile, probability in sorted(
                    self.profile_posterior.items(),
                    key=lambda item: (-item[1], item[0].value),
                )
            },
        }


@dataclass(frozen=True)
class OpponentBeliefState:
    """Posterior over one opponent's type, updated from observed action families.

    Immutable: `observe` returns a new state so belief history stays inspectable
    and speculative search branches cannot corrupt the caller's belief.
    """

    opponent_id: str
    profile_posterior: Mapping[OpponentProfile, float]
    observation_count: int = 0
    profile_models: Mapping[OpponentProfile, ProfileResponseModel] = field(
        default_factory=lambda: DEFAULT_PROFILE_MODELS
    )
    model_id: str = BELIEF_MODEL_ID

    @classmethod
    def uniform(
        cls,
        opponent_id: str,
        *,
        profiles: Iterable[OpponentProfile] | None = None,
        profile_models: Mapping[OpponentProfile, ProfileResponseModel] | None = None,
    ) -> OpponentBeliefState:
        """Start from an uninformative prior over opponent types."""

        models = dict(profile_models or DEFAULT_PROFILE_MODELS)
        resolved_profiles = list(profiles) if profiles is not None else list(models)
        if not resolved_profiles:
            raise ValueError("belief state requires at least one opponent profile")
        weight = 1.0 / len(resolved_profiles)
        return cls(
            opponent_id=opponent_id,
            profile_posterior=dict.fromkeys(resolved_profiles, weight),
            profile_models=models,
        )

    def predict(
        self,
        candidate_values: Mapping[ActionType, float],
    ) -> ResponseDistribution:
        """Marginalize P(family | profile) over the current profile posterior."""

        if not candidate_values:
            return ResponseDistribution(
                opponent_id=self.opponent_id,
                probabilities={},
                candidate_values={},
                profile_posterior=dict(self.profile_posterior),
                model_id=self.model_id,
            )

        mixed: dict[ActionType, float] = dict.fromkeys(candidate_values, 0.0)
        for profile, profile_probability in self.profile_posterior.items():
            model = self.profile_models.get(profile)
            if model is None or profile_probability <= 0:
                continue
            for family, probability in model.family_probabilities(candidate_values).items():
                mixed[family] += profile_probability * probability

        total = sum(mixed.values())
        if total <= 0:
            uniform = 1.0 / len(candidate_values)
            mixed = dict.fromkeys(candidate_values, uniform)
        else:
            mixed = {family: value / total for family, value in mixed.items()}

        return ResponseDistribution(
            opponent_id=self.opponent_id,
            probabilities=mixed,
            candidate_values=dict(candidate_values),
            profile_posterior=dict(self.profile_posterior),
            model_id=self.model_id,
        )

    def observe(
        self,
        observed_family: ActionType,
        candidate_values: Mapping[ActionType, float],
    ) -> OpponentBeliefState:
        """Bayes-update the profile posterior from one observed action family.

        Observations of families that were not in the candidate set are ignored
        rather than treated as evidence, because an unmodelled family means the
        candidate template was incomplete, not that every profile was wrong.
        """

        if not candidate_values or observed_family not in candidate_values:
            return self

        updated: dict[OpponentProfile, float] = {}
        for profile, profile_probability in self.profile_posterior.items():
            model = self.profile_models.get(profile)
            if model is None:
                continue
            likelihood = model.family_probabilities(candidate_values).get(
                observed_family,
                _MIN_PROBABILITY,
            )
            updated[profile] = profile_probability * max(likelihood, _MIN_PROBABILITY)

        return OpponentBeliefState(
            opponent_id=self.opponent_id,
            profile_posterior=_normalize(updated),
            observation_count=self.observation_count + 1,
            profile_models=self.profile_models,
            model_id=self.model_id,
        )


def brier_score(distribution: ResponseDistribution, observed_family: ActionType) -> float:
    """Multi-class Brier score for one prediction. Lower is better."""

    families = set(distribution.probabilities) | {observed_family}
    return sum(
        (distribution.probability_of(family) - (1.0 if family == observed_family else 0.0)) ** 2
        for family in families
    )


def log_loss(distribution: ResponseDistribution, observed_family: ActionType) -> float:
    """Negative log-likelihood of one observed family. Lower is better."""

    return -math.log(max(distribution.probability_of(observed_family), _MIN_PROBABILITY))


def uniform_baseline_log_loss(family_count: int) -> float:
    """Log loss of a uniform guess, for judging whether a model beats chance."""

    if family_count <= 0:
        return 0.0
    return -math.log(1.0 / family_count)


def summarize_calibration(
    distributions: Sequence[ResponseDistribution],
    observed_families: Sequence[ActionType],
) -> dict[str, float | int]:
    """Score a batch of predictions against the families that actually occurred."""

    if len(distributions) != len(observed_families):
        raise ValueError("distributions and observed_families must be the same length")
    if not distributions:
        return {
            "predictions": 0,
            "top1_accuracy": 0.0,
            "mean_log_loss": 0.0,
            "mean_brier_score": 0.0,
            "uniform_log_loss": 0.0,
            "log_loss_improvement": 0.0,
        }

    top1_hits = 0
    log_losses = []
    brier_scores = []
    uniform_losses = []
    for distribution, observed_family in zip(distributions, observed_families, strict=True):
        if distribution.most_likely_family == observed_family:
            top1_hits += 1
        log_losses.append(log_loss(distribution, observed_family))
        brier_scores.append(brier_score(distribution, observed_family))
        uniform_losses.append(uniform_baseline_log_loss(len(distribution.probabilities)))

    mean_log_loss = sum(log_losses) / len(log_losses)
    mean_uniform_loss = sum(uniform_losses) / len(uniform_losses)
    return {
        "predictions": len(distributions),
        "top1_accuracy": round(top1_hits / len(distributions), 4),
        "mean_log_loss": round(mean_log_loss, 4),
        "mean_brier_score": round(sum(brier_scores) / len(brier_scores), 4),
        "uniform_log_loss": round(mean_uniform_loss, 4),
        # Positive means the belief model beats a uniform guess.
        "log_loss_improvement": round(mean_uniform_loss - mean_log_loss, 4),
    }
