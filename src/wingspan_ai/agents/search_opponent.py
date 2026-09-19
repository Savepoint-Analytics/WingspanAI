"""Opponent models that play the other seats inside the potential-points search.

Why this module exists
----------------------
The search in ``potential_points`` descends through opponent turns before it
reaches the acting player's next own turn, and something has to choose what
those opponents do. Until 2026-09-07 that was always the greedy baseline. It
is a reasonable model, but it prices every legal action through
``apply_action`` on every modelled opponent turn: about 16 ms per turn, and
roughly 40% of what a decision costs after gain-food pruning
(``docs/experiments/search_food_candidates.md``).

The belief model here answers the same question a different way. It asks the
project's Bayesian opponent model (``wingspan_ai.belief``) which action
*family* this opponent is most likely to choose, from public candidate values
only, then picks a concrete action inside that family with a proxy that never
applies an action. The family prediction costs about 0.2 ms.

That makes it two things at once: the cheap opponent model the search needed,
and the first place a belief posterior is allowed to change a decision. Which
of the two matters is what the ablation measures; the module makes no claim
that the belief-driven opponent is a better model, only a cheaper one.

Information boundary
--------------------
Family prediction reads only the public projection of the state
(``to_public_state``) and the belief posterior. Inside a determinized search
branch the opponent's hand is a sample the acting player imagined, and the
within-family proxy may read it, exactly as the greedy model always has.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from wingspan_ai.agents import profiling
from wingspan_ai.agents.greedy import GreedyBaselineAgent, _heuristic_tiebreaker

# ``net_value`` imports ``potential_points``, which is why ``potential_points``
# loads this module lazily rather than at import time; with that arrangement
# the import below is not a cycle.
from wingspan_ai.agents.net_value import (
    PublicOpponentBeliefModel,
    _public_player,
    _public_response_candidates,
)
from wingspan_ai.belief import OpponentBeliefState, ResponseDistribution
from wingspan_ai.rules.actions import ActionType, LegalAction
from wingspan_ai.rules.base_game import egg_cost_for_slot
from wingspan_ai.state.models import GameState, to_public_state

_PUBLIC_MODEL = PublicOpponentBeliefModel()

SEARCH_OPPONENT_MODELS = ("greedy", "belief", "oracle", "belief_apply")
#: Where the oracle-type model reads each opponent kind's converged posterior
#: (written by ``analysis/oracle_type_posteriors.py``).
DEFAULT_ORACLE_TYPE_POSTERIORS = "configs/belief/oracle_type_posteriors.json"
#: Default flipped to ``"belief"`` on 2026-09-16 after the 80-game arm in
#: ``docs/experiments/search_opponent_model_test.md``: score +0.31 (p=0.73),
#: decision cost more than halved.
DEFAULT_SEARCH_OPPONENT_MODEL = "belief"
#: A minority of games keep the previous model as a standing control, so the
#: adoption stays a long-run experiment rather than a one-shot result and a
#: later change (an agent that learns from past games, say) cannot quietly
#: bake the belief model's tendencies into everything it sees. Which games
#: are held out is a deterministic function of the game key, so seed-matched
#: arms hold out the same games and stay paired.
DEFAULT_SEARCH_OPPONENT_HOLDOUT_SHARE = 0.05
DEFAULT_SEARCH_OPPONENT_HOLDOUT_MODEL = "greedy"


def holdout_draw(key: str) -> float:
    """Uniform draw in [0, 1) from a string key, stable across processes and versions."""

    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def resolve_search_opponent_model(
    preferred: str,
    *,
    holdout_share: float,
    holdout_model: str,
    random_seed: int,
    lineup: Sequence[str],
    lineup_position: int,
) -> tuple[str, bool]:
    """Return ``(effective_model, is_holdout)`` for one agent in one game.

    The key is the game's seed, the lineup, and the agent's position in it —
    not the seat it ends up in — so the same game holds out in every seat
    rotation and the holdout subset is counterbalanced like everything else.
    """

    if preferred not in SEARCH_OPPONENT_MODELS:
        raise ValueError(f"unknown search opponent model: {preferred!r}")
    if holdout_model not in SEARCH_OPPONENT_MODELS:
        raise ValueError(f"unknown search opponent holdout model: {holdout_model!r}")
    if not 0.0 <= holdout_share <= 1.0:
        raise ValueError(f"holdout share must be in [0, 1], got {holdout_share}")
    if holdout_share <= 0.0 or holdout_model == preferred:
        return preferred, False
    key = f"search_opponent_holdout:{random_seed}:{','.join(lineup)}:{lineup_position}"
    if holdout_draw(key) < holdout_share:
        return holdout_model, True
    return preferred, False


class SearchOpponentModel(Protocol):
    """What the search needs from whatever plays the opponent seats."""

    model_id: str

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction: ...

    def observe_action(
        self, state_before: GameState, action: LegalAction, acting_player_id: str
    ) -> None: ...

    def telemetry_payload(self) -> dict: ...


@dataclass
class GreedySearchOpponentModel:
    """The historic model: the greedy baseline plays every opponent turn.

    Deterministic, needs no RNG stream, and sits mid-roster in strength, so
    the search sees the tray and feeder contention it exists to plan around.
    """

    model_id: str = "greedy"
    _agent: GreedyBaselineAgent = field(
        default_factory=lambda: GreedyBaselineAgent(agent_id="search_opponent_model"),
        init=False,
        repr=False,
        compare=False,
    )

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        with profiling.node("greedy_opponent_model"):
            return self._agent.select_action(state, legal_actions)

    def observe_action(
        self, state_before: GameState, action: LegalAction, acting_player_id: str
    ) -> None:
        return None

    def telemetry_payload(self) -> dict:
        return {"model_id": self.model_id}


@dataclass
class BeliefSearchOpponentModel:
    """Play each opponent turn as the family the belief posterior finds most likely.

    ``owner_agent_id`` identifies the seat whose beliefs these are, so the
    runner's ``observe_action`` calls can skip that seat's own actions. The
    posterior is updated only from the real game; speculative search branches
    read it and never write it.
    """

    owner_agent_id: str
    model_id: str = "belief"
    belief_states: dict[str, OpponentBeliefState] = field(default_factory=dict, compare=False)

    def belief_state_for(self, opponent_id: str) -> OpponentBeliefState:
        belief_state = self.belief_states.get(opponent_id)
        if belief_state is None:
            belief_state = OpponentBeliefState.uniform(opponent_id)
            self.belief_states[opponent_id] = belief_state
        return belief_state

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError("BeliefSearchOpponentModel cannot select from an empty action list")
        with profiling.node("belief_predict_family"):
            distribution = self.predict_family(state, state.active_player.player_id)
        available = {action.action_type for action in legal_actions}
        # The public candidate template can list a family the branch cannot
        # actually play (a hand with no affordable bird still looks playable
        # from outside), so walk the ranking until a family has legal actions.
        pool = legal_actions
        for family, _probability in distribution.ranked_families():
            if family in available:
                pool = [action for action in legal_actions if action.action_type == family]
                break
        with profiling.node("belief_within_family_pick"):
            return max(pool, key=lambda action: _proxy_action_score(state, action))

    def predict_family(self, state: GameState, opponent_id: str) -> ResponseDistribution:
        """Distribution over ``opponent_id``'s next action family, from public state only."""

        return self.belief_state_for(opponent_id).predict(
            _public_candidate_values(state, opponent_id)
        )

    def observe_action(
        self, state_before: GameState, action: LegalAction, acting_player_id: str
    ) -> None:
        """Bayes-update the acting opponent's type from the family they chose."""

        own_player_id = _own_player_id(state_before, self.owner_agent_id)
        if own_player_id is None or acting_player_id == own_player_id:
            return
        candidate_values = _public_candidate_values(state_before, acting_player_id)
        if not candidate_values:
            return
        self.belief_states[acting_player_id] = self.belief_state_for(acting_player_id).observe(
            action.action_type, candidate_values
        )

    def telemetry_payload(self) -> dict:
        return {
            "model_id": self.model_id,
            "opponent_belief_states": {
                opponent_id: {
                    "observation_count": belief_state.observation_count,
                    "most_likely_profile": (
                        max(
                            belief_state.profile_posterior,
                            key=lambda p: (belief_state.profile_posterior[p], p.value),
                        ).value
                        if belief_state.profile_posterior
                        else None
                    ),
                    "profile_posterior": {
                        profile.value: round(probability, 4)
                        for profile, probability in sorted(
                            belief_state.profile_posterior.items(),
                            key=lambda item: (-item[1], item[0].value),
                        )
                    },
                }
                for opponent_id, belief_state in sorted(self.belief_states.items())
            },
        }


@dataclass
class BeliefApplySearchOpponentModel(BeliefSearchOpponentModel):
    """Family from the posterior, then greedy's real pick inside that family.

    Registered 2026-09-18 after the three-player study: the belief model's
    within-family proxy (which ignores what a power does) cost about two
    points against greedy at 3p, where two opponent turns are modelled per
    ply. Applying only the predicted family's actions keeps greedy's
    accuracy where the search will actually go, at a fraction of its cost.
    """

    model_id: str = "belief_apply"
    _greedy: GreedyBaselineAgent = field(
        default_factory=lambda: GreedyBaselineAgent(agent_id="search_opponent_model"),
        init=False,
        repr=False,
        compare=False,
    )

    def select_action(self, state: GameState, legal_actions: list[LegalAction]) -> LegalAction:
        if not legal_actions:
            raise ValueError("BeliefApplySearchOpponentModel cannot select from an empty list")
        with profiling.node("belief_predict_family"):
            distribution = self.predict_family(state, state.active_player.player_id)
        available = {action.action_type for action in legal_actions}
        pool = legal_actions
        for family, _probability in distribution.ranked_families():
            if family in available:
                pool = [action for action in legal_actions if action.action_type == family]
                break
        with profiling.node("belief_within_family_apply", candidate_count=len(pool)):
            return self._greedy.select_action(state, pool)


@dataclass
class OracleTypeSearchOpponentModel(BeliefSearchOpponentModel):
    """The belief model with perfect type knowledge from turn one.

    An experimental bound, not a shippable model: it reads each opponent
    seat's ``agent_id`` — information a real player never has — and starts
    from the posterior the belief model converges to for that agent kind
    after a full game (``configs/belief/oracle_type_posteriors.json``), then
    never updates. If the score does not move against ``belief``, faster or
    better type inference cannot be worth anything at this player count with
    this response model; if it moves, that is the ceiling for inference.
    Opponent kinds absent from the table fall back to ordinary updating.
    """

    model_id: str = "oracle"
    posteriors_path: str | None = None
    _table: dict[str, dict[str, float]] = field(default_factory=dict, init=False, repr=False)
    _fixed: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        self._table = _load_oracle_posteriors(self.posteriors_path)

    def predict_family(self, state: GameState, opponent_id: str) -> ResponseDistribution:
        if opponent_id not in self.belief_states:
            self._seed_belief(state, opponent_id)
        return super().predict_family(state, opponent_id)

    def observe_action(
        self, state_before: GameState, action: LegalAction, acting_player_id: str
    ) -> None:
        if acting_player_id not in self.belief_states:
            self._seed_belief(state_before, acting_player_id)
        if acting_player_id in self._fixed:
            return
        super().observe_action(state_before, action, acting_player_id)

    def _seed_belief(self, state: GameState, opponent_id: str) -> None:
        agent_id = next((p.agent_id for p in state.players if p.player_id == opponent_id), None)
        kind = _agent_kind(agent_id) if agent_id else None
        posterior = self._table.get(kind or "")
        if posterior is None:
            self.belief_states[opponent_id] = OpponentBeliefState.uniform(opponent_id)
            return
        uniform = OpponentBeliefState.uniform(opponent_id)
        self.belief_states[opponent_id] = OpponentBeliefState(
            opponent_id=opponent_id,
            profile_posterior={
                profile: float(posterior.get(profile.value, 0.0))
                for profile in uniform.profile_posterior
            },
            observation_count=0,
            profile_models=uniform.profile_models,
            model_id=f"{uniform.model_id}+oracle_type",
        )
        self._fixed.add(opponent_id)

    def telemetry_payload(self) -> dict:
        payload = super().telemetry_payload()
        payload["oracle_fixed_players"] = sorted(self._fixed)
        return payload


_ORACLE_CACHE: dict[str, dict[str, dict[str, float]]] = {}


def _load_oracle_posteriors(path: str | None) -> dict[str, dict[str, float]]:
    resolved = path or DEFAULT_ORACLE_TYPE_POSTERIORS
    if resolved not in _ORACLE_CACHE:
        import json
        from pathlib import Path

        candidate = Path(resolved)
        if not candidate.is_absolute() and not candidate.exists():
            candidate = Path(__file__).resolve().parents[3] / resolved
        data = json.loads(candidate.read_text(encoding="utf-8"))
        _ORACLE_CACHE[resolved] = {
            kind: {profile: float(p) for profile, p in posterior.items()}
            for kind, posterior in data["posteriors"].items()
        }
    return _ORACLE_CACHE[resolved]


def _agent_kind(agent_id: str) -> str:
    kind = agent_id.removeprefix("guardrailed_")
    return kind.rsplit("_p", 1)[0] if "_p" in kind else kind


def build_search_opponent_model(kind: str, *, owner_agent_id: str) -> SearchOpponentModel:
    if kind == "greedy":
        return GreedySearchOpponentModel()
    if kind == "belief":
        return BeliefSearchOpponentModel(owner_agent_id=owner_agent_id)
    if kind == "oracle":
        return OracleTypeSearchOpponentModel(owner_agent_id=owner_agent_id)
    if kind == "belief_apply":
        return BeliefApplySearchOpponentModel(owner_agent_id=owner_agent_id)
    raise ValueError(
        f"unknown search opponent model: {kind!r}; expected one of {SEARCH_OPPONENT_MODELS}"
    )


def _public_candidate_values(state: GameState, opponent_id: str) -> dict[ActionType, float]:
    public_state = to_public_state(state)
    public_player = _public_player(public_state, opponent_id)
    if public_player.action_cubes_available <= 0:
        return {}
    belief = _PUBLIC_MODEL.estimate(state, observer_player_id=opponent_id, opponent_id=opponent_id)
    return {
        candidate.action_type: candidate.value_delta
        for candidate in _public_response_candidates(public_state, public_player, belief)
    }


def _proxy_action_score(state: GameState, action: LegalAction) -> tuple[float, float]:
    """Order actions inside a family without applying any of them.

    Mirrors what the greedy model would see for the two families that score
    immediately: a played bird is worth its printed points less the eggs the
    slot costs, and a lay-eggs action is worth the eggs it lays. Gain-food and
    draw-cards score zero immediately, so they fall through to greedy's own
    tie-break (food need, tray-card quality). Points a power would add on
    activation are not counted; that is the approximation this model makes.
    """

    player = state.active_player
    if action.action_type == ActionType.PLAY_BIRD and action.habitat is not None:
        card = next(c for c in player.hand if c.common_name == action.bird_common_name)
        immediate = float(card.victory_points) - egg_cost_for_slot(
            len(player.habitats[action.habitat])
        )
    elif action.action_type == ActionType.LAY_EGGS:
        immediate = float(action.egg_count or 0)
    else:
        immediate = 0.0
    return (immediate, _heuristic_tiebreaker(state, action))


def _own_player_id(state: GameState, agent_id: str) -> str | None:
    for player in state.players:
        if player.agent_id == agent_id:
            return player.player_id
    return None
