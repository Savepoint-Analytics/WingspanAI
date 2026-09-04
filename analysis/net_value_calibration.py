"""Calibrate net-value opponent-response predictions against observed actions."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


def load_batch_manifest(path: str | Path) -> dict[str, Any]:
    """Load a simulation batch manifest."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def collect_calibration_rows(paths: list[str | Path]) -> list[dict[str, Any]]:
    """Pair net-value response predictions with the opponent's next selected action."""

    rows: list[dict[str, Any]] = []
    for path in paths:
        manifest = load_batch_manifest(path)
        for game in manifest.get("games", []):
            events = list(_iter_game_events(game))
            outcome = game.get("outcome", {})
            score_margin = (
                outcome.get("scores", {}).get("player_2", 0)
                - outcome.get("scores", {}).get("player_1", 0)
            )
            for event_index, event in enumerate(events):
                if event.get("event_name") != "agent_decision_summary":
                    continue
                summary = _net_value_summary(event.get("payload", {}))
                if summary is None:
                    continue

                response = summary.get("selected_opponent_response", {})
                opponent_id = response.get("opponent_id")
                predicted_action_type = response.get("response_action_type")
                if opponent_id is None or predicted_action_type is None:
                    continue
                observed_event = _next_action_selected(
                    events[event_index + 1 :],
                    player_id=opponent_id,
                )
                observed_action = (
                    observed_event.get("payload", {}).get("action", {})
                    if observed_event is not None
                    else {}
                )
                observed_action_type = observed_action.get("action_type")
                candidate_values = response.get("response_candidate_values", [])
                belief = response.get("response_belief") or {}
                family_probabilities = belief.get("family_probabilities", {})
                rows.append(
                    {
                        "batch_id": manifest.get("batch_id"),
                        "batch_label": manifest.get("batch_label"),
                        "game_id": game.get("outcome", {}).get("game_id"),
                        "random_seed": outcome.get("random_seed"),
                        "predictor_agent_id": event.get("agent_id"),
                        "opponent_id": opponent_id,
                        "prediction_global_turn_number": event.get("global_turn_number"),
                        "observed_global_turn_number": (
                            observed_event.get("global_turn_number")
                            if observed_event is not None
                            else None
                        ),
                        "predicted_action_type": predicted_action_type,
                        "observed_action_type": observed_action_type,
                        "prediction_matched": predicted_action_type == observed_action_type,
                        "observed_candidate_rank": _candidate_rank(
                            candidate_values,
                            observed_action_type,
                        ),
                        "predicted_response_value_delta": response.get(
                            "response_value_delta",
                        ),
                        "selected_net_margin_delta": summary.get(
                            "selected_breakdown",
                            {},
                        ).get("net_margin_delta"),
                        "selected_shared_denial_value": summary.get(
                            "selected_breakdown",
                            {},
                        ).get("shared_denial_value"),
                        "candidate_action_types": [
                            candidate.get("action_type") for candidate in candidate_values
                        ],
                        "response_mode": response.get("response_mode", "best"),
                        "belief_model_id": belief.get("model_id"),
                        "family_probabilities": family_probabilities,
                        "observed_family_probability": (
                            family_probabilities.get(observed_action_type)
                            if observed_action_type is not None
                            else None
                        ),
                        "most_likely_profile": belief.get("most_likely_profile"),
                        "expected_response_value": belief.get("expected_value"),
                        "best_response_value": belief.get("best_value"),
                        "score_margin": score_margin,
                        "player_two_won": "player_2" in outcome.get("winners", []),
                    }
                )
    return rows


def summarize_calibration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize calibration rows into accuracy, coverage, and outcome diagnostics."""

    matched_rows = [row for row in rows if row["observed_action_type"] is not None]
    exact_matches = [row for row in matched_rows if row["prediction_matched"]]
    observed_in_candidates = [
        row for row in matched_rows if row["observed_candidate_rank"] is not None
    ]
    rank_values = [
        row["observed_candidate_rank"]
        for row in observed_in_candidates
        if isinstance(row["observed_candidate_rank"], int)
    ]
    probability_rows = [
        row for row in matched_rows if row.get("observed_family_probability") is not None
    ]
    return {
        "prediction_count": len(rows),
        "matched_observation_count": len(matched_rows),
        **_probabilistic_scores(probability_rows),
        "exact_match_count": len(exact_matches),
        "exact_match_rate": len(exact_matches) / len(matched_rows)
        if matched_rows
        else None,
        "observed_in_candidate_set_count": len(observed_in_candidates),
        "observed_in_candidate_set_rate": len(observed_in_candidates) / len(matched_rows)
        if matched_rows
        else None,
        "average_observed_candidate_rank": mean(rank_values) if rank_values else None,
        "predicted_action_counts": dict(Counter(row["predicted_action_type"] for row in rows)),
        "observed_action_counts": dict(
            Counter(row["observed_action_type"] for row in matched_rows)
        ),
        "average_predicted_response_value_delta": _mean_optional(
            row["predicted_response_value_delta"] for row in rows
        ),
        "average_selected_net_margin_delta": _mean_optional(
            row["selected_net_margin_delta"] for row in rows
        ),
        "average_selected_shared_denial_value": _mean_optional(
            row["selected_shared_denial_value"] for row in rows
        ),
        "average_score_margin": _mean_optional(row["score_margin"] for row in rows),
        "player_two_win_rate": _mean_optional(
            1.0 if row["player_two_won"] else 0.0 for row in rows
        ),
    }


def render_markdown_report(calibration: dict[str, Any]) -> str:
    """Render calibration results as a compact Markdown report."""

    summary = calibration["summary"]
    lines = [
        "# Net-Value Public Belief Calibration",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Predictions | {summary['prediction_count']} |",
        f"| Matched observations | {summary['matched_observation_count']} |",
        f"| Exact action-family matches | {summary['exact_match_count']} |",
        f"| Exact match rate | {_format_optional(summary['exact_match_rate'], 3)} |",
        "| Probabilistic predictions | "
        f"{summary['probabilistic_prediction_count']} |",
        f"| Mean log loss | {_format_optional(summary['mean_log_loss'], 4)} |",
        f"| Uniform-guess log loss | {_format_optional(summary['uniform_log_loss'], 4)} |",
        "| Log loss improvement vs uniform | "
        f"{_format_optional(summary['log_loss_improvement'], 4)} |",
        f"| Mean Brier score | {_format_optional(summary['mean_brier_score'], 4)} |",
        "| Mean probability on observed family | "
        f"{_format_optional(summary['mean_observed_family_probability'], 4)} |",
        "| Observed action in public candidate set | "
        f"{_format_optional(summary['observed_in_candidate_set_rate'], 3)} |",
        "| Avg observed candidate rank | "
        f"{_format_optional(summary['average_observed_candidate_rank'], 2)} |",
        "| Avg predicted response value | "
        f"{_format_optional(summary['average_predicted_response_value_delta'], 3)} |",
        "| Avg selected net margin delta | "
        f"{_format_optional(summary['average_selected_net_margin_delta'], 3)} |",
        "| Avg selected denial value | "
        f"{_format_optional(summary['average_selected_shared_denial_value'], 3)} |",
        f"| Avg final P2 margin | {_format_optional(summary['average_score_margin'], 2)} |",
        f"| P2 win rate | {_format_optional(summary['player_two_win_rate'], 3)} |",
        "",
        "## Action Mix",
        "",
        "| Kind | Action | Count |",
        "|---|---|---:|",
    ]
    for action_type, count in sorted(summary["predicted_action_counts"].items()):
        lines.append(f"| Predicted | {action_type} | {count} |")
    for action_type, count in sorted(summary["observed_action_counts"].items()):
        lines.append(f"| Observed | {action_type} | {count} |")

    lines.extend(
        [
            "",
            "## Prediction Rows",
            "",
            "| Batch | Seed | Turn | Opponent | Predicted | Observed | Rank | Match |",
            "|---|---:|---:|---|---|---|---:|---|",
        ]
    )
    for row in calibration["rows"]:
        lines.append(
            "| {batch_label} | {random_seed} | {prediction_global_turn_number} | "
            "{opponent_id} | {predicted_action_type} | {observed_action_type} | "
            "{observed_candidate_rank} | {prediction_matched} |".format(
                batch_label=row["batch_label"],
                random_seed=row["random_seed"],
                prediction_global_turn_number=row["prediction_global_turn_number"],
                opponent_id=row["opponent_id"],
                predicted_action_type=row["predicted_action_type"],
                observed_action_type=row["observed_action_type"],
                observed_candidate_rank=(
                    row["observed_candidate_rank"]
                    if row["observed_candidate_rank"] is not None
                    else "n/a"
                ),
                prediction_matched="yes" if row["prediction_matched"] else "no",
            )
        )
    return "\n".join(lines) + "\n"


def build_calibration_report(paths: list[str | Path]) -> dict[str, Any]:
    """Build a full calibration report from one or more batch manifests."""

    rows = collect_calibration_rows(paths)
    return {
        "manifest_paths": [str(path) for path in paths],
        "summary": summarize_calibration(rows),
        "rows": rows,
    }


def _iter_game_events(game: dict[str, Any]):
    artifact_dir = game.get("artifact_dir")
    if artifact_dir is None:
        return
    events_path = Path(artifact_dir) / "events.jsonl"
    if not events_path.exists():
        return
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if line:
            yield json.loads(line)


def _net_value_summary(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("policy") == "net_value_opponent_response":
        return payload
    base_summary = payload.get("base_decision_summary")
    if (
        isinstance(base_summary, dict)
        and base_summary.get("policy") == "net_value_opponent_response"
    ):
        return base_summary
    return None


def _next_action_selected(
    events: list[dict[str, Any]],
    *,
    player_id: str | None,
) -> dict[str, Any] | None:
    if player_id is None:
        return None
    for event in events:
        if event.get("event_name") != "action_selected":
            continue
        if event.get("player_id") == player_id:
            return event
    return None


def _candidate_rank(
    candidate_values: list[dict[str, Any]],
    observed_action_type: str | None,
) -> int | None:
    if observed_action_type is None:
        return None
    for rank, candidate in enumerate(candidate_values, start=1):
        if candidate.get("action_type") == observed_action_type:
            return rank
    return None


def _probabilistic_scores(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Score the belief model as a distribution, not a single point prediction.

    Exact-match rate cannot distinguish a confidently wrong model from a
    well-calibrated uncertain one. Log loss and Brier score can, and comparing
    against a uniform guess shows whether the belief model adds information at
    all.
    """

    if not rows:
        return {
            "probabilistic_prediction_count": 0,
            "mean_log_loss": None,
            "mean_brier_score": None,
            "uniform_log_loss": None,
            "log_loss_improvement": None,
            "mean_observed_family_probability": None,
        }

    log_losses = []
    brier_scores = []
    uniform_losses = []
    for row in rows:
        probabilities = row.get("family_probabilities") or {}
        observed = row["observed_action_type"]
        observed_probability = max(float(row["observed_family_probability"]), 1e-9)
        log_losses.append(-math.log(observed_probability))
        families = set(probabilities) | {observed}
        brier_scores.append(
            sum(
                (float(probabilities.get(family, 0.0)) - (1.0 if family == observed else 0.0))
                ** 2
                for family in families
            )
        )
        uniform_losses.append(-math.log(1.0 / max(len(probabilities), 1)))

    mean_log_loss = mean(log_losses)
    mean_uniform_loss = mean(uniform_losses)
    return {
        "probabilistic_prediction_count": len(rows),
        "mean_log_loss": mean_log_loss,
        "mean_brier_score": mean(brier_scores),
        "uniform_log_loss": mean_uniform_loss,
        # Positive means the belief model beats a uniform guess.
        "log_loss_improvement": mean_uniform_loss - mean_log_loss,
        "mean_observed_family_probability": mean(
            float(row["observed_family_probability"]) for row in rows
        ),
    }


def _mean_optional(values: Any) -> float | None:
    numeric_values = [value for value in values if isinstance(value, int | float)]
    return mean(numeric_values) if numeric_values else None


def _format_optional(value: float | None, digits: int) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", help="Path(s) to batch_manifest.json files.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    args = parser.parse_args()

    report = build_calibration_report(args.manifests)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_markdown_report(report), end="")


if __name__ == "__main__":
    main()
