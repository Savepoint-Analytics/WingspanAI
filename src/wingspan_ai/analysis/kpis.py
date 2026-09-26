"""KPI functions for the Wingspan round/game KPI taxonomy, per player and agent.

One function per section of the taxonomy. Each takes rows from
``wingspan_ai.analysis.persistence`` — score rows for the cheap families,
event records for the rest — and returns lists of dictionaries so a notebook
can render them with or without pandas.

Two rules the module holds to:

* **A proxy is named a proxy.** Several KPIs in the taxonomy ask for a
  counterfactual the simulator never recorded: the optimal goal placement,
  the points left on the table, whether a player pivoted. Where a recorded
  quantity stands in for one, the column ends in ``_proxy`` and the docstring
  says what it is not.
* **A missing measurement is reported, not imputed.** The food-economy family
  is the clearest case: no event carries a player's food tokens, so food
  waste and overshoot cannot be computed at all. ``taxonomy_coverage_report``
  marks them ``missing`` rather than returning zeros.

Coverage depends on the run. ``bird_scorecard`` (per-bird eggs, cache, tucks,
activations, round played, bonus tags) exists only for games simulated after
2026-09-16, and ``round_goal_scored`` only after 2026-09-22; the coverage
report reads the events present rather than assuming.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

Row = dict[str, Any]

SCORE_CATEGORIES = (
    "bird_points",
    "bonus_points",
    "round_goal_points",
    "egg_points",
    "cached_food_points",
    "tucked_card_points",
)
HABITATS = ("forest", "grassland", "wetland")
#: Which habitat row an action activates. Playing a bird names its own habitat.
ACTION_HABITAT = {"gain_food": "forest", "lay_eggs": "grassland", "draw_cards": "wetland"}


def agent_key(agent_id: object) -> str:
    """``engine_builder_p2`` → ``engine_builder``; the seat is a separate field."""

    text = str(agent_id or "unknown").removeprefix("guardrailed_")
    return text.rsplit("_p", 1)[0] if "_p" in text else text


def game_key(row: Mapping[str, Any]) -> str:
    """A game's identity: the run id, not ``game_id`` (ADR 0006).

    ``game_id`` omits the lineup and seat rotation, so every game in a batch
    sharing a seed carries the same one -- 44.5% of the archive collides.
    Grouping by it merges distinct games, which silently corrupted the tempo
    and win-margin KPIs (two games' players became one four-player game).
    Older local event records predate the field, so fall back rather than
    raise.
    """

    return str(row.get("simulation_run_id") or row.get("game_id") or "unknown")


# ------------------------------------------------------------------ core scoring


def scoring_kpis(score_rows: Iterable[Mapping[str, Any]]) -> dict[str, list[Row]]:
    """Final score, its six categories, and each category's share of the total.

    The taxonomy also asks for a per-round cumulative score and per-round
    delta. Those need a score snapshot at each round end, which the simulator
    does not emit; ``round_played`` on ``bird_scorecard`` supports the bird
    component only (see ``tempo_kpis``).
    """

    rows = [dict(row) for row in score_rows]
    by_agent: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_agent[agent_key(row.get("agent_id"))].append(row)

    summary: list[Row] = []
    for agent, group in sorted(by_agent.items()):
        total = _mean(group, "total_score")
        record: Row = {
            "agent": agent,
            "player_games": len(group),
            "win_rate": _mean(group, "is_winner"),
            "avg_total_score": total,
        }
        for category in SCORE_CATEGORIES:
            record[f"avg_{category}"] = _mean(group, category)
            record[f"{category}_share"] = (_mean(group, category) / total) if total else 0.0
        summary.append(record)

    composition = [
        {
            "category": category,
            "avg_points": _mean(rows, category),
            "share_of_total": (_mean(rows, category) / _mean(rows, "total_score"))
            if _mean(rows, "total_score")
            else 0.0,
            "players_scoring_pct": sum(1 for row in rows if _number(row.get(category)) > 0)
            / max(len(rows), 1),
            "max_points": max((_number(row.get(category)) for row in rows), default=0.0),
        }
        for category in SCORE_CATEGORIES
    ]
    return {"by_agent": summary, "composition": composition}


# ------------------------------------------------------------- end-of-round goals


def round_goal_kpis(
    score_rows: Iterable[Mapping[str, Any]],
    events: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, list[Row]]:
    """Goal points, their share of the final score, and per-round placement.

    Per-round placement needs ``round_goal_scored`` (emitted from
    2026-09-22). Without it only the whole-game total is available, and
    ``by_round`` comes back empty rather than guessed. The taxonomy's goal-fit
    score, rank volatility and points-left-on-the-table all need a
    counterfactual placement the events do not carry.
    """

    rows = [dict(row) for row in score_rows]
    by_agent: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_agent[agent_key(row.get("agent_id"))].append(row)
    totals = [
        {
            "agent": agent,
            "player_games": len(group),
            "avg_round_goal_points": _mean(group, "round_goal_points"),
            "goal_share_of_score": (_mean(group, "round_goal_points") / _mean(group, "total_score"))
            if _mean(group, "total_score")
            else 0.0,
            "scored_any_goal_rate": sum(
                1 for row in group if _number(row.get("round_goal_points")) > 0
            )
            / max(len(group), 1),
        }
        for agent, group in sorted(by_agent.items())
    ]

    per_round: list[Row] = []
    for event in _named(events or [], "round_goal_scored"):
        payload = event["payload"]
        counts = _mapping(payload.get("counts"))
        points = _mapping(payload.get("points_awarded"))
        agents = _mapping(payload.get("agent_ids"))
        top = max((_number(value) for value in counts.values()), default=0.0)
        for player_id, count in counts.items():
            per_round.append(
                {
                    "agent": agent_key(agents.get(player_id, player_id)),
                    "round_number": payload.get("goal_round"),
                    "goal_name": payload.get("goal_name"),
                    "count": _number(count),
                    "points": _number(points.get(player_id)),
                    "took_first": _number(count) == top and top > 0,
                    "qualified": _number(count) > 0,
                    "contested": bool(payload.get("contested")),
                }
            )
    return {
        "by_agent": totals,
        "by_round": _summarize(
            per_round,
            ("agent", "round_number"),
            "scored_rounds",
            ("took_first", "qualified", "contested"),
            ("count", "points"),
        ),
    }


# ------------------------------------------------------------------ bonus cards


def bonus_card_kpis(events: Iterable[Mapping[str, Any]]) -> dict[str, list[Row]]:
    """Bonus-card selection, the pool it was drafted against, and fulfilment.

    Uses ``setup_selection_applied`` (kept and discarded cards, so the draft
    pool is known) and ``bird_scorecard`` (``bonus_card_tags`` per played
    bird, so the realised eligible count is known at game end).

    ``fulfilment_vs_end_pool`` is realised tags over the birds actually
    played. The taxonomy's "eligible pool at draft" needs the bonus card's
    criteria evaluated against the opening hand; the tags are only recorded
    for played birds, so the draft-time pool is not available and that KPI is
    reported as a gap rather than approximated by the end-of-game pool.
    """

    rows = list(events)
    selections: dict[tuple[str, str], Row] = {}
    for event in _named(rows, "setup_selection_applied"):
        payload = event["payload"]
        key = (game_key(event), str(payload.get("player_id")))
        kept = list(payload.get("kept_bonus_card_names") or [])
        discarded = list(payload.get("discarded_bonus_card_names") or [])
        selections[key] = {
            "agent": agent_key(payload.get("agent_id")),
            "kept_bonus": kept[0] if kept else None,
            "bonus_seen": len(kept) + len(discarded),
            "kept_birds": len(payload.get("kept_bird_names") or []),
            "birds_seen": len(payload.get("kept_bird_names") or [])
            + len(payload.get("discarded_bird_names") or []),
        }

    fulfilment: list[Row] = []
    for event in _named(rows, "bird_scorecard"):
        payload = event["payload"]
        key = (game_key(event), str(payload.get("player_id")))
        selection = selections.get(key, {})
        held = [str(name) for name in (payload.get("bonus_card_names") or [])]
        birds = list(payload.get("birds") or [])
        matching = sum(
            1
            for bird in birds
            if any(tag in held for tag in (_mapping(bird).get("bonus_card_tags") or []))
        )
        fulfilment.append(
            {
                "agent": selection.get("agent", agent_key(payload.get("agent_id"))),
                "kept_bonus": selection.get("kept_bonus"),
                "bonus_seen": selection.get("bonus_seen"),
                "birds_played": len(birds),
                "birds_matching_bonus": matching,
                "fulfilment_vs_end_pool": matching / len(birds) if birds else 0.0,
            }
        )
    return {
        "selection": _summarize(
            list(selections.values()),
            ("agent", "kept_bonus"),
            "games",
            (),
            ("bonus_seen", "kept_birds", "birds_seen"),
        ),
        "fulfilment": _summarize(
            fulfilment,
            ("agent",),
            "games",
            (),
            ("birds_played", "birds_matching_bonus", "fulfilment_vs_end_pool"),
        ),
        "by_card": _summarize(
            fulfilment,
            ("kept_bonus",),
            "games",
            (),
            ("birds_matching_bonus", "fulfilment_vs_end_pool"),
        ),
    }


# --------------------------------------------------------------- bird utilization


def bird_utilization_kpis(events: Iterable[Mapping[str, Any]]) -> dict[str, list[Row]]:
    """Draw efficiency, habitat spread, power mix, and per-bird yield.

    ``activation_rate_proxy`` is activations per played bird. The taxonomy
    asks for activations against the theoretical maximum available, which
    needs the turns each bird was on the board and the habitat activations
    that occurred — the first is available (``round_played``), the second is
    not attributed per bird, so this is a rate, not a ratio to a ceiling.
    """

    rows = list(events)
    drawn: Counter = Counter()
    played: Counter = Counter()
    for event in _named(rows, "action_resolved"):
        action = _mapping(event["payload"].get("action"))
        agent = agent_key(event.get("agent_id"))
        kind = action.get("action_type")
        if kind == "draw_cards":
            count = len(action.get("tray_indices") or []) + _number(
                action.get("draw_from_deck_count")
            )
            drawn[agent] += int(count)
        elif kind == "play_bird":
            played[agent] += 1

    per_player: list[Row] = []
    per_bird: list[Row] = []
    for event in _named(rows, "bird_scorecard"):
        payload = event["payload"]
        agent = agent_key(payload.get("agent_id"))
        birds = [_mapping(bird) for bird in (payload.get("birds") or [])]
        if not birds:
            continue
        habitats = Counter(str(bird.get("habitat")) for bird in birds)
        colors = Counter(str(bird.get("power_color")) for bird in birds)
        activations = sum(_number(bird.get("activations")) for bird in birds)
        record: Row = {
            "agent": agent,
            "birds_played": len(birds),
            "avg_victory_points": sum(_number(b.get("victory_points")) for b in birds) / len(birds),
            "eggs_on_board": sum(_number(b.get("eggs")) for b in birds),
            "cached_food": sum(_number(b.get("cached_food")) for b in birds),
            "tucked_cards": sum(_number(b.get("tucked_cards")) for b in birds),
            "activations": activations,
            "activation_rate_proxy": activations / len(birds),
            "specialization_hhi": _hhi([habitats.get(h, 0) for h in HABITATS]),
        }
        for habitat in HABITATS:
            record[f"{habitat}_birds"] = habitats.get(habitat, 0)
        for color in ("brown", "white", "pink", "teal", "yellow", "none"):
            record[f"{color}_powers"] = colors.get(color, 0)
        per_player.append(record)
        for bird in birds:
            yields = _mapping(bird.get("power_yield"))
            per_bird.append(
                {
                    "agent": agent,
                    "common_name": bird.get("common_name"),
                    "habitat": bird.get("habitat"),
                    "power_color": bird.get("power_color"),
                    "round_played": bird.get("round_played"),
                    "victory_points": _number(bird.get("victory_points")),
                    "eggs": _number(bird.get("eggs")),
                    "activations": _number(bird.get("activations")),
                    "yield_food": _number(yields.get("food")),
                    "yield_cards": _number(yields.get("cards")),
                    "yield_eggs": _number(yields.get("eggs")),
                }
            )

    efficiency = [
        {
            "agent": agent,
            "cards_drawn": drawn.get(agent, 0),
            "birds_played": played.get(agent, 0),
            "play_rate_of_drawn": played.get(agent, 0) / drawn[agent] if drawn.get(agent) else 0.0,
        }
        for agent in sorted(set(drawn) | set(played))
    ]
    return {
        "draw_efficiency": efficiency,
        "by_agent": _summarize(
            per_player,
            ("agent",),
            "player_games",
            (),
            tuple(key for key in (per_player[0] if per_player else {}) if key != "agent"),
        ),
        "by_power_color": _summarize(
            per_bird, ("power_color",), "birds", (), ("activations", "yield_food", "yield_cards")
        ),
        "top_birds": _summarize(
            per_bird,
            ("common_name",),
            "times_played",
            (),
            ("victory_points", "eggs", "activations"),
        )[:25],
    }


# ------------------------------------------------------------------ turn / action


def action_kpis(
    events: Iterable[Mapping[str, Any]],
    score_rows: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, list[Row]]:
    """Action mix per agent and per round, and points generated per action."""

    rows = list(events)
    actions: list[Row] = []
    for event in _named(rows, "action_resolved"):
        action = _mapping(event["payload"].get("action"))
        kind = str(action.get("action_type"))
        actions.append(
            {
                "agent": agent_key(event.get("agent_id")),
                "game_key": game_key(event),
                "round_number": event.get("round_number"),
                "action_type": kind,
                "habitat": action.get("habitat") or ACTION_HABITAT.get(kind),
            }
        )
    counts_by_agent: dict[str, Counter] = defaultdict(Counter)
    counts_by_round: dict[tuple[str, int], Counter] = defaultdict(Counter)
    actions_per_game: Counter = Counter()
    for row in actions:
        agent = str(row["agent"])
        counts_by_agent[agent][str(row["action_type"])] += 1
        counts_by_round[(agent, int(row["round_number"] or 0))][str(row["action_type"])] += 1
        actions_per_game[(str(row["game_key"]), agent)] += 1

    def mix(counter: Counter) -> Row:
        total = max(sum(counter.values()), 1)
        return {
            "actions": sum(counter.values()),
            **{f"{kind}_share": counter.get(kind, 0) / total for kind in sorted(ACTION_HABITAT)},
            "play_bird_share": counter.get("play_bird", 0) / total,
        }

    by_agent = [
        {"agent": agent, **mix(counter)} for agent, counter in sorted(counts_by_agent.items())
    ]
    by_round = [
        {"agent": agent, "round_number": round_number, **mix(counter)}
        for (agent, round_number), counter in sorted(counts_by_round.items())
    ]

    efficiency: list[Row] = []
    if score_rows is not None:
        scores = {
            (game_key(row), agent_key(row.get("agent_id"))): _number(
                row.get("total_score")
            )
            for row in score_rows
        }
        per_agent: dict[str, list[float]] = defaultdict(list)
        for (game, agent), action_count in actions_per_game.items():
            score = scores.get((game, agent))
            if score and action_count:
                per_agent[agent].append(score / action_count)
        efficiency = [
            {
                "agent": agent,
                "games": len(values),
                "avg_points_per_action": sum(values) / len(values),
            }
            for agent, values in sorted(per_agent.items())
        ]
    return {"by_agent": by_agent, "by_round": by_round, "action_efficiency": efficiency}


# ------------------------------------------------------------------------ tempo


def tempo_kpis(events: Iterable[Mapping[str, Any]]) -> dict[str, list[Row]]:
    """When each habitat row was first opened, and how play spreads over rounds."""

    first_open: list[Row] = []
    by_round: list[Row] = []
    for event in _named(events, "bird_scorecard"):
        payload = event["payload"]
        agent = agent_key(payload.get("agent_id"))
        birds = [_mapping(bird) for bird in (payload.get("birds") or [])]
        earliest: dict[str, float] = {}
        rounds: Counter = Counter()
        for bird in birds:
            habitat = str(bird.get("habitat"))
            played = _number(bird.get("round_played"))
            if played:
                rounds[int(played)] += 1
                earliest[habitat] = min(earliest.get(habitat, played), played)
        record: Row = {"agent": agent}
        for habitat in HABITATS:
            record[f"first_{habitat}_round"] = earliest.get(habitat)
        first_open.append(record)
        for round_number, count in rounds.items():
            by_round.append({"agent": agent, "round_number": round_number, "birds_played": count})
    return {
        "first_habitat_round": _summarize(
            first_open,
            ("agent",),
            "player_games",
            (),
            tuple(f"first_{habitat}_round" for habitat in HABITATS),
        ),
        "birds_by_round": _summarize(
            by_round, ("agent", "round_number"), "player_games", (), ("birds_played",)
        ),
    }


# ------------------------------------------------------------------- comparative


def comparative_kpis(score_rows: Iterable[Mapping[str, Any]]) -> dict[str, list[Row]]:
    """Win margin, gap to the runner-up, and bonus-card/agent head-to-head."""

    rows = [dict(row) for row in score_rows]
    by_game: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_game[game_key(row)].append(row)

    margins: list[Row] = []
    for game, players in by_game.items():
        if len(players) < 2:
            continue
        ordered = sorted(players, key=lambda row: -_number(row.get("total_score")))
        best, second = ordered[0], ordered[1]
        margins.append(
            {
                "game_key": game,
                "winner_agent": agent_key(best.get("agent_id")),
                "runner_up_agent": agent_key(second.get("agent_id")),
                "winning_score": _number(best.get("total_score")),
                "margin": _number(best.get("total_score")) - _number(second.get("total_score")),
            }
        )
    head_to_head: dict[tuple[str, str], list[float]] = defaultdict(list)
    for players in by_game.values():
        for player in players:
            for opponent in players:
                if player is opponent:
                    continue
                head_to_head[
                    (agent_key(player.get("agent_id")), agent_key(opponent.get("agent_id")))
                ].append(_number(player.get("total_score")) - _number(opponent.get("total_score")))
    return {
        "margins": _summarize(margins, ("winner_agent",), "wins", (), ("winning_score", "margin")),
        "head_to_head": [
            {
                "agent": agent,
                "opponent": opponent,
                "player_games": len(deltas),
                "avg_score_margin": sum(deltas) / len(deltas),
                "win_rate": sum(1 for delta in deltas if delta > 0) / len(deltas),
            }
            for (agent, opponent), deltas in sorted(head_to_head.items())
        ],
    }


# --------------------------------------------------------------------- coverage


#: Taxonomy section → (events or tables it needs, coverage, note).
TAXONOMY_COVERAGE: tuple[tuple[str, frozenset[str], str, str], ...] = (
    (
        "core_scoring",
        frozenset({"game_ended"}),
        "partial",
        "Final score and its six categories are in game_scores. Cumulative score by round and "
        "per-round delta need a score snapshot at each round end, which is not emitted.",
    ),
    (
        "end_of_round_goals",
        frozenset({"round_goal_scored"}),
        "partial",
        "Goal totals come from game_scores. Per-round placement needs round_goal_scored "
        "(emitted from 2026-09-22). Goal fit, rank volatility and points-left-on-the-table "
        "need a counterfactual placement that is never recorded.",
    ),
    (
        "bonus_cards",
        frozenset({"setup_selection_applied", "bird_scorecard"}),
        "partial",
        "Selection, seen pool and end-of-game fulfilment are supported. The draft-time "
        "eligible pool needs bonus criteria evaluated against the opening hand; tags are "
        "recorded only for played birds.",
    ),
    (
        "bird_utilization",
        frozenset({"action_resolved", "bird_scorecard"}),
        "supported",
        "Draw efficiency, habitat spread, power-colour mix, per-bird yield and activations.",
    ),
    (
        "card_recycling",
        frozenset({"bird_scorecard"}),
        "partial",
        "Activations of recycling powers are visible through power_yield, but the cards "
        "cycled past and the rejected options are not recorded, so selection quality and "
        "best-of-N capture rate are unavailable.",
    ),
    (
        "food_economy",
        frozenset({"food_state"}),
        "missing",
        "No event carries a player's food tokens. Unspent food, waste rate, excess by type "
        "and engine overshoot cannot be computed; a per-turn food snapshot would close all "
        "of them.",
    ),
    (
        "turn_action_level",
        frozenset({"action_resolved"}),
        "supported",
        "Action mix per agent and round, habitat visitation, and points per action.",
    ),
    (
        "strategic_archetype",
        frozenset({"bird_scorecard"}),
        "partial",
        "Specialization index and engine yield are supported. Combo density needs power text "
        "cross-references and the pivot flag needs a strategy-change label; neither exists.",
    ),
    (
        "comparative_positional",
        frozenset({"game_ended"}),
        "partial",
        "Win margin, gap to runner-up and head-to-head are supported from game_scores. "
        "Relative rank by round needs the per-round score snapshot.",
    ),
)


def taxonomy_coverage_report(
    events: Iterable[Mapping[str, Any]] = (),
    *,
    has_scores: bool = True,
) -> list[Row]:
    """Map each taxonomy section onto what this run can actually answer."""

    names = {str(event.get("name")) for event in events}
    if has_scores:
        names.add("game_ended")
    report: list[Row] = []
    for family, required, level, note in TAXONOMY_COVERAGE:
        missing = sorted(required - names)
        report.append(
            {
                "kpi_family": family,
                "coverage": "missing" if missing and level != "missing" else level,
                "missing_events": ", ".join(missing),
                "note": note,
            }
        )
    return report


# ---------------------------------------------------------------------- helpers


def _named(events: Iterable[Mapping[str, Any]], name: str) -> list[Mapping[str, Any]]:
    return [event for event in events if event.get("name") == name]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    return float(value) if isinstance(value, int | float) else 0.0


def _mean(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = [_number(row.get(field)) for row in rows if row.get(field) is not None]
    return sum(values) / len(values) if values else 0.0


def _hhi(counts: Sequence[float]) -> float:
    """Herfindahl index over a distribution: 1/n is uniform, 1.0 is one bucket."""

    total = sum(counts)
    return sum((count / total) ** 2 for count in counts) if total else 0.0


def _summarize(
    rows: Iterable[Mapping[str, Any]],
    group_fields: tuple[str, ...],
    count_name: str,
    bool_fields: tuple[str, ...],
    numeric_fields: tuple[str, ...],
) -> list[Row]:
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(field) for field in group_fields)].append(row)
    output: list[Row] = []
    for key, values in grouped.items():
        record: Row = dict(zip(group_fields, key, strict=True))
        record[count_name] = len(values)
        for field in bool_fields:
            present = [bool(value[field]) for value in values if value.get(field) is not None]
            if present:
                record[f"{field}_rate"] = sum(present) / len(present)
        for field in numeric_fields:
            present = [
                _number(value[field])
                for value in values
                if isinstance(value.get(field), int | float)
            ]
            if present:
                record[f"avg_{field}"] = sum(present) / len(present)
        output.append(record)
    return sorted(
        output,
        key=lambda row: (-int(row[count_name]), *(str(row.get(field)) for field in group_fields)),
    )
