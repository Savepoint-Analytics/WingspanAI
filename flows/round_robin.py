"""Agent-vs-agent round robin with mandatory seat counterbalancing.

Every strategy comparison in this project before 2026-08-31 ran one agent against
`RandomLegalAgent` in a fixed seat. That measures whether a policy beats noise,
not whether it beats another policy, and it leaves turn-order advantage
confounded with agent strength.

Seat handling (ADR 0002)
------------------------
The simulator seats the first-listed agent in seat one deterministically; the
first-player token is never randomized at setup. Rather than randomize it, this
flow **counterbalances**: every lineup is replayed once per seat rotation, so
each agent occupies each seat exactly once per seed. Turn-order advantage then
cancels within a matchup instead of averaging out over many seeds, which removes
seat variance entirely rather than merely diluting it.

Counterbalancing is not optional. `build_matchup_cells` always emits all
`player_count` rotations, and there is no parameter to run a partial set.

Seat effects are still measured rather than discarded: `summarize_seat_effect`
reports win rate and average score per seat index plus the spread between the
best and worst seat, which is the magnitude answer to "does turn order matter,
and by how much". Because the flow accepts any `player_count` from 2 to 5, that
question can be asked per player count without changing this module.

Seed matching
-------------
`game_id` participates in RNG seed material and is derived from `batch_id`. Two
batches with different `batch_id` values see different deck order, birdfeeder
rolls, and setup deals even at the same numeric seed. This flow passes a single
`batch_id` to every cell so all cells share `game_id` per seed, and separates
cells by `batch_label`, which is a storage key only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any

from flows.simulation_batch import (
    DEFAULT_ARTIFACT_ROOT,
    MAX_PLAYER_COUNT,
    BatchKind,
    PlayerTwoAgentKind,
    SetupPolicyKind,
    _batch_directory,
    _new_batch_id,
    _validate_batch_kind,
    _validate_path_segment,
    _validate_player_two_agent_kind,
    _validate_setup_policy_kind,
    flow,
    run_simulation_batch,
)
from wingspan_ai.config import load_dotenv
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH
from wingspan_ai.provenance import code_provenance

ROUND_ROBIN_SCHEMA_VERSION = "wingspan.round_robin_summary.v2"
ROUND_ROBIN_FILENAME = "round_robin_summary.json"
#: Roster entries may carry a "guardrailed:" prefix, e.g.
#: "guardrailed:potential_points", making an agent and its guardrailed twin
#: separate competitors in the same round robin.
DEFAULT_ROSTER: tuple[PlayerTwoAgentKind, ...] = (
    "greedy_immediate",
    "potential_points",
    "net_value_response",
    "archetype_engine_builder",
    "archetype_bonus_card_focus",
    "archetype_round_goal_chase",
)


@dataclass(frozen=True)
class MatchupCell:
    """One agent lineup under one setup-policy level and one seat rotation."""

    lineup: tuple[str, ...]
    setup_policy_kind: str
    seat_rotation: int

    @property
    def player_count(self) -> int:
        return len(self.lineup)

    @property
    def seated_lineup(self) -> tuple[str, ...]:
        """Lineup in seat order after rotation. Seat one is index 0."""

        rotation = self.seat_rotation % self.player_count
        return self.lineup[rotation:] + self.lineup[:rotation]

    def seat_index_of(self, lineup_index: int) -> int:
        """Return the zero-based seat occupied by one lineup position."""

        return (lineup_index - self.seat_rotation) % self.player_count

    @property
    def cell_label(self) -> str:
        return f"{'__vs__'.join(self.lineup)}__{self.setup_policy_kind}__rot{self.seat_rotation}"


def build_matchup_cells(
    roster: list[PlayerTwoAgentKind],
    setup_policy_kinds: list[SetupPolicyKind],
    player_count: int = 2,
) -> list[MatchupCell]:
    """Enumerate every lineup in every seat rotation for each setup level.

    Counterbalancing is mandatory: all `player_count` rotations are always
    emitted so each agent occupies each seat exactly once per lineup per seed.
    """

    if not 2 <= player_count <= MAX_PLAYER_COUNT:
        raise ValueError(f"player_count must be between 2 and {MAX_PLAYER_COUNT}")
    if len(roster) < player_count:
        raise ValueError(
            f"roster needs at least {player_count} agents for {player_count}-player games"
        )

    cells: list[MatchupCell] = []
    for lineup in combinations(roster, player_count):
        for setup_policy_kind in setup_policy_kinds:
            for seat_rotation in range(player_count):
                cells.append(
                    MatchupCell(
                        lineup=tuple(lineup),
                        setup_policy_kind=setup_policy_kind,
                        seat_rotation=seat_rotation,
                    )
                )
    return cells


def _cell_batch_label(cell: MatchupCell) -> str:
    """Return a path-safe directory name for one cell.

    Roster entries may carry a "guardrailed:" prefix, and the colon is not a
    legal path segment character, so it is rewritten rather than rejected.
    """

    label = cell.cell_label.replace("__", "-").replace(":", "-")
    return _validate_path_segment(label, "batch_label")


def _lineup_scores(game: dict[str, Any], cell: MatchupCell) -> list[int]:
    """Map seat scores back to lineup order, undoing the rotation."""

    scores = game["outcome"]["scores"]
    return [scores[f"player_{cell.seat_index_of(index) + 1}"] for index in range(cell.player_count)]


def _win_credit(scores: list[int]) -> list[float]:
    """Split one win across tied top scorers so win rates stay comparable."""

    best = max(scores)
    winners = [index for index, score in enumerate(scores) if score == best]
    credit = 1.0 / len(winners)
    return [credit if index in winners else 0.0 for index in range(len(scores))]


def _is_seat_robust(rates: list[float]) -> bool:
    """Return whether one side leads in every seat without contradiction.

    A 0.500 rate in some seat is inconclusive, not robust, so robustness needs a
    strict lead in at least one seat and no contradiction in any other.
    """

    if not rates:
        return False
    above = [rate > 0.5 for rate in rates]
    below = [rate < 0.5 for rate in rates]
    if any(above) and not any(below):
        return True
    return bool(any(below) and not any(above))


def summarize_seat_effect(
    cells: list[MatchupCell],
    cell_results: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    """Measure how much turn order is worth, per seat index.

    This is the standing research question: does seat order matter, at which
    player counts, and by how much? Reported per player count so results stay
    separable when a roster is run at 2, 3, and 5 players.
    """

    by_count: dict[int, dict[int, dict[str, Any]]] = {}
    for cell, results in zip(cells, cell_results, strict=True):
        seats = by_count.setdefault(cell.player_count, {})
        for game in results:
            scores = _lineup_scores(game, cell)
            credits = _win_credit(scores)
            for lineup_index in range(cell.player_count):
                seat_index = cell.seat_index_of(lineup_index)
                bucket = seats.setdefault(
                    seat_index,
                    {"games": 0, "wins": 0.0, "scores": []},
                )
                bucket["games"] += 1
                bucket["wins"] += credits[lineup_index]
                bucket["scores"].append(scores[lineup_index])

    summary: dict[str, Any] = {}
    for player_count, seats in sorted(by_count.items()):
        rows = []
        for seat_index, bucket in sorted(seats.items()):
            rows.append(
                {
                    "seat": seat_index + 1,
                    "games": bucket["games"],
                    "win_rate": round(bucket["wins"] / (bucket["games"] or 1), 4),
                    "avg_score": round(mean(bucket["scores"]), 2),
                }
            )
        win_rates = [row["win_rate"] for row in rows]
        avg_scores = [row["avg_score"] for row in rows]
        fair_share = 1.0 / player_count if player_count else 0.0
        summary[str(player_count)] = {
            "player_count": player_count,
            "fair_share_win_rate": round(fair_share, 4),
            "seats": rows,
            # Magnitude of the seat effect: how far apart the best and worst
            # seats are. Zero means turn order did not matter in this sample.
            "win_rate_spread": round(max(win_rates) - min(win_rates), 4),
            "avg_score_spread": round(max(avg_scores) - min(avg_scores), 2),
            "best_seat": rows[win_rates.index(max(win_rates))]["seat"],
            "worst_seat": rows[win_rates.index(min(win_rates))]["seat"],
        }
    return summary


def summarize_round_robin(
    cells: list[MatchupCell],
    cell_results: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    """Reduce per-game results into pairwise matchup and per-agent summaries."""

    matchups: dict[tuple[str, str, str], dict[str, Any]] = {}
    standings: dict[str, dict[str, Any]] = {}
    total_games = 0
    player_counts: set[int] = set()

    for cell, results in zip(cells, cell_results, strict=True):
        player_counts.add(cell.player_count)
        for game in results:
            total_games += 1
            scores = _lineup_scores(game, cell)
            credits = _win_credit(scores)
            replay_valid = game["replay_validation"]["is_valid"]

            for lineup_index, agent in enumerate(cell.lineup):
                totals = standings.setdefault(
                    agent,
                    {"agent": agent, "games": 0, "wins": 0.0, "scores": []},
                )
                totals["games"] += 1
                totals["wins"] += credits[lineup_index]
                totals["scores"].append(scores[lineup_index])

            # Pairwise score superiority. At two players this equals the game
            # win; at more it isolates head-to-head strength within the table.
            for index_a, index_b in combinations(range(cell.player_count), 2):
                agent_a, agent_b = cell.lineup[index_a], cell.lineup[index_b]
                key = (agent_a, agent_b, cell.setup_policy_kind)
                record = matchups.setdefault(
                    key,
                    {
                        "agent_a": agent_a,
                        "agent_b": agent_b,
                        "setup_policy_kind": cell.setup_policy_kind,
                        "games": 0,
                        "agent_a_wins": 0.0,
                        "agent_a_scores": [],
                        "agent_b_scores": [],
                        "by_seat": {},
                        "invalid_replays": 0,
                    },
                )
                score_a, score_b = scores[index_a], scores[index_b]
                if score_a > score_b:
                    win_a = 1.0
                elif score_b > score_a:
                    win_a = 0.0
                else:
                    win_a = 0.5
                record["games"] += 1
                record["agent_a_wins"] += win_a
                record["agent_a_scores"].append(score_a)
                record["agent_b_scores"].append(score_b)
                record["invalid_replays"] += 0 if replay_valid else 1
                seat_bucket = record["by_seat"].setdefault(
                    cell.seat_index_of(index_a),
                    {"games": 0, "wins": 0.0},
                )
                seat_bucket["games"] += 1
                seat_bucket["wins"] += win_a

    matchup_rows = []
    for record in matchups.values():
        games = record["games"] or 1
        seat_rates = {
            seat: bucket["wins"] / (bucket["games"] or 1)
            for seat, bucket in sorted(record["by_seat"].items())
        }
        matchup_rows.append(
            {
                "agent_a": record["agent_a"],
                "agent_b": record["agent_b"],
                "setup_policy_kind": record["setup_policy_kind"],
                "games": record["games"],
                "agent_a_win_rate": round(record["agent_a_wins"] / games, 4),
                "agent_a_avg_score": round(mean(record["agent_a_scores"]), 2),
                "agent_b_avg_score": round(mean(record["agent_b_scores"]), 2),
                "avg_margin_for_agent_a": round(
                    mean(record["agent_a_scores"]) - mean(record["agent_b_scores"]), 2
                ),
                "agent_a_win_rate_by_seat": {
                    str(seat + 1): round(rate, 4) for seat, rate in seat_rates.items()
                },
                # Only a matchup that holds in every seat is strategy signal
                # rather than a turn-order artifact.
                "seat_robust": _is_seat_robust(list(seat_rates.values())),
                "invalid_replays": record["invalid_replays"],
            }
        )

    standing_rows = sorted(
        (
            {
                "agent": totals["agent"],
                "games": totals["games"],
                "win_rate": round(totals["wins"] / (totals["games"] or 1), 4),
                "avg_score": round(mean(totals["scores"]), 2),
            }
            for totals in standings.values()
        ),
        key=lambda row: (-row["win_rate"], -row["avg_score"], row["agent"]),
    )

    return {
        "schema_version": ROUND_ROBIN_SCHEMA_VERSION,
        "code_provenance": code_provenance(),
        "total_games": total_games,
        "player_counts": sorted(player_counts),
        "seat_effect": summarize_seat_effect(cells, cell_results),
        "standings": standing_rows,
        "matchups": sorted(
            matchup_rows,
            key=lambda row: (row["setup_policy_kind"], row["agent_a"], row["agent_b"]),
        ),
    }


def summarize_setup_policy_effect(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare each agent's win rate across setup-policy levels.

    Caveat: when one setup level is applied to the whole roster, win rates are
    zero-sum across agents, so these differences are relative movement only and
    do not identify the absolute effect of a strategic opening. Crossing setup
    policy per agent is required for that.
    """

    per_agent: dict[str, dict[str, dict[str, float]]] = {}
    for row in summary["matchups"]:
        level = row["setup_policy_kind"]
        for agent, wins in (
            (row["agent_a"], row["agent_a_win_rate"] * row["games"]),
            (row["agent_b"], (1 - row["agent_a_win_rate"]) * row["games"]),
        ):
            bucket = per_agent.setdefault(agent, {}).setdefault(level, {"games": 0, "wins": 0.0})
            bucket["games"] += row["games"]
            bucket["wins"] += wins

    effects = []
    for agent, levels in sorted(per_agent.items()):
        row: dict[str, Any] = {"agent": agent}
        for level, bucket in levels.items():
            row[f"{level}_win_rate"] = round(bucket["wins"] / (bucket["games"] or 1), 4)
        if "control_win_rate" in row and "strategic_win_rate" in row:
            row["strategic_minus_control"] = round(
                row["strategic_win_rate"] - row["control_win_rate"], 4
            )
        effects.append(row)
    return effects


@flow(name="wingspan-round-robin")
def run_round_robin(
    workbook_path: str = str(DEFAULT_WORKBOOK_PATH),
    seeds: list[int] | None = None,
    roster: list[PlayerTwoAgentKind] | None = None,
    setup_policy_kinds: list[SetupPolicyKind] | None = None,
    artifact_root: str | None = DEFAULT_ARTIFACT_ROOT,
    *,
    player_count: int = 2,
    batch_kind: BatchKind = "experiment",
    batch_label: str = "round_robin",
    batch_id: str | None = None,
    persist_postgres: bool | None = False,
    upload_artifacts: bool | None = None,
    require_valid_replay: bool = True,
    power_status_filter: list[str] | None = None,
    excluded_power_handler_keys: list[str] | None = None,
    guardrail_config_path: str | None = None,
    monte_carlo_rollout_count: int = 4,
    monte_carlo_rollout_depth: int = 6,
    monte_carlo_max_decision_time_ms: float | None = 75.0,
    monte_carlo_max_candidate_actions: int | None = 4,
    net_value_max_candidate_actions: int | None = 5,
    net_value_max_opponent_response_actions: int | None = 3,
    net_value_response_mode: str = "expected",
) -> dict[str, Any]:
    """Run every agent lineup in every seat rotation across the setup factor.

    Seat counterbalancing is always applied and cannot be disabled.
    """

    load_dotenv()
    resolved_batch_kind = _validate_batch_kind(batch_kind)
    resolved_batch_label = _validate_path_segment(batch_label, "batch_label")
    resolved_batch_id = _validate_path_segment(batch_id or _new_batch_id(), "batch_id")
    resolved_roster = [
        _validate_player_two_agent_kind(agent) for agent in (roster or list(DEFAULT_ROSTER))
    ]
    if len(set(resolved_roster)) < player_count:
        raise ValueError(f"round robin requires at least {player_count} distinct agent kinds")
    resolved_setup_policy_kinds = [
        _validate_setup_policy_kind(kind)
        for kind in (setup_policy_kinds or ["control", "strategic"])
    ]
    resolved_seeds = seeds or [1, 2, 3, 4, 5]

    cells = build_matchup_cells(resolved_roster, resolved_setup_policy_kinds, player_count)
    started_at = datetime.now(UTC).isoformat()
    cell_results: list[list[dict[str, Any]]] = []
    for cell in cells:
        cell_results.append(
            run_simulation_batch(
                workbook_path=workbook_path,
                seeds=resolved_seeds,
                artifact_root=artifact_root,
                persist_postgres=persist_postgres,
                upload_artifacts=upload_artifacts,
                batch_kind=resolved_batch_kind,
                batch_label=_cell_batch_label(cell),
                batch_id=resolved_batch_id,
                require_valid_replay=require_valid_replay,
                player_agent_kinds=list(cell.lineup),
                setup_policy_kind=cell.setup_policy_kind,
                seat_rotation=cell.seat_rotation,
                power_status_filter=power_status_filter,
                excluded_power_handler_keys=excluded_power_handler_keys,
                guardrail_config_path=guardrail_config_path,
                monte_carlo_rollout_count=monte_carlo_rollout_count,
                monte_carlo_rollout_depth=monte_carlo_rollout_depth,
                monte_carlo_max_decision_time_ms=monte_carlo_max_decision_time_ms,
                monte_carlo_max_candidate_actions=monte_carlo_max_candidate_actions,
                net_value_max_candidate_actions=net_value_max_candidate_actions,
                net_value_max_opponent_response_actions=net_value_max_opponent_response_actions,
                net_value_response_mode=net_value_response_mode,
            )
        )

    summary = summarize_round_robin(cells, cell_results)
    summary.update(
        {
            "batch_id": resolved_batch_id,
            "batch_kind": resolved_batch_kind,
            "batch_label": resolved_batch_label,
            "started_at": started_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "roster": resolved_roster,
            "player_count": player_count,
            "setup_policy_kinds": resolved_setup_policy_kinds,
            "seeds": resolved_seeds,
            "cell_count": len(cells),
            "seat_counterbalanced": True,
            "power_status_filter": power_status_filter,
            "excluded_power_handler_keys": excluded_power_handler_keys,
            "setup_policy_effect": summarize_setup_policy_effect(summary),
        }
    )

    if artifact_root is not None:
        summary_directory = _batch_directory(
            artifact_root,
            resolved_batch_kind,
            resolved_batch_label,
            resolved_batch_id,
        )
        summary_directory.mkdir(parents=True, exist_ok=True)
        summary_path = summary_directory / ROUND_ROBIN_FILENAME
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary["summary_path"] = str(summary_path)

    return summary


def format_round_robin_report(summary: dict[str, Any]) -> str:
    """Render a round-robin summary as markdown tables."""

    lines = [
        f"# Round-Robin Summary: {summary.get('batch_label', 'round_robin')}",
        "",
        f"- Batch ID: `{summary.get('batch_id')}`",
        f"- Seeds: {summary.get('seeds')}",
        f"- Roster: {', '.join(summary.get('roster', []))}",
        f"- Player count: {summary.get('player_count')}",
        f"- Setup policy levels: {', '.join(summary.get('setup_policy_kinds', []))}",
        f"- Total games: {summary.get('total_games')}",
        f"- Seat counterbalanced: {summary.get('seat_counterbalanced', True)}",
        "",
        "## Seat effect",
        "",
    ]
    for _count, effect in sorted(summary.get("seat_effect", {}).items()):
        lines += [
            f"**{effect['player_count']} players** "
            f"(fair share {effect['fair_share_win_rate']:.3f}) - "
            f"win-rate spread **{effect['win_rate_spread']:.3f}**, "
            f"score spread **{effect['avg_score_spread']:.2f}**",
            "",
            "| Seat | Games | Win rate | Avg score |",
            "|---:|---:|---:|---:|",
        ]
        for row in effect["seats"]:
            lines.append(
                f"| {row['seat']} | {row['games']} | "
                f"{row['win_rate']:.3f} | {row['avg_score']:.2f} |"
            )
        lines.append("")

    lines += [
        "## Standings",
        "",
        "| Agent | Games | Win rate | Avg score |",
        "|---|---:|---:|---:|",
    ]
    for row in summary["standings"]:
        lines.append(
            f"| `{row['agent']}` | {row['games']} | "
            f"{row['win_rate']:.3f} | {row['avg_score']:.2f} |"
        )

    seat_keys = sorted(
        {seat for row in summary["matchups"] for seat in row.get("agent_a_win_rate_by_seat", {})}
    )
    seat_header = " ".join(f"A seat {seat} |" for seat in seat_keys)
    seat_divider = " ".join("---:|" for _ in seat_keys)
    lines += [
        "",
        "## Matchups",
        "",
        f"| Setup | Agent A | Agent B | Games | A win rate | {seat_header} "
        "Seat robust | Avg margin (A) |",
        f"|---|---|---|---:|---:| {seat_divider} :--:|---:|",
    ]
    for row in summary["matchups"]:
        by_seat = row.get("agent_a_win_rate_by_seat", {})
        seat_cells = " ".join(f"{by_seat.get(seat, float('nan')):.3f} |" for seat in seat_keys)
        lines.append(
            f"| {row['setup_policy_kind']} | `{row['agent_a']}` | `{row['agent_b']}` | "
            f"{row['games']} | {row['agent_a_win_rate']:.3f} | {seat_cells} "
            f"{'yes' if row['seat_robust'] else 'NO'} | "
            f"{row['avg_margin_for_agent_a']:+.2f} |"
        )

    effects = summary.get("setup_policy_effect", [])
    if effects:
        lines += [
            "",
            "## Setup-policy effect",
            "",
            "> Zero-sum across the roster when one level is applied pool-wide.",
            "> Relative movement only; not an absolute effect.",
            "",
            "| Agent | Control win rate | Strategic win rate | Strategic - control |",
            "|---|---:|---:|---:|",
        ]
        for row in effects:
            control = row.get("control_win_rate")
            strategic = row.get("strategic_win_rate")
            delta = row.get("strategic_minus_control")
            lines.append(
                f"| `{row['agent']}` | "
                f"{'n/a' if control is None else f'{control:.3f}'} | "
                f"{'n/a' if strategic is None else f'{strategic:.3f}'} | "
                f"{'n/a' if delta is None else f'{delta:+.3f}'} |"
            )

    return "\n".join(lines) + "\n"


def main() -> None:
    """CLI entry point: re-render a stored round-robin summary as markdown."""

    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary_path", type=Path, help=f"path to {ROUND_ROBIN_FILENAME}")
    args = parser.parse_args()
    summary = json.loads(args.summary_path.read_text(encoding="utf-8"))
    print(format_round_robin_report(summary))


if __name__ == "__main__":
    main()
