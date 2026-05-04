"""MLflow tracking helpers for simulation results."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from wingspan_ai.simulation.runner import SimulationResult


def log_simulation_result(
    result: SimulationResult,
    *,
    experiment_name: str = "wingspan-ai-simulations",
) -> None:
    """Log one simulation result to MLflow.

    MLflow is imported lazily so local rules tests do not require experiment
    tracking dependencies until this helper is used.
    """

    try:
        import mlflow
    except ImportError as error:
        raise RuntimeError(
            "MLflow is required for experiment tracking. "
            "Install the tracking optional dependencies before calling this helper."
        ) from error

    outcome = result.outcome
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=f"{outcome.game_id}_{outcome.random_seed}"):
        mlflow.log_param("game_id", outcome.game_id)
        mlflow.log_param("simulation_run_id", outcome.simulation_run_id)
        mlflow.log_param("random_seed", outcome.random_seed)
        mlflow.log_param("terminal_reason", outcome.terminal_reason)
        mlflow.log_metric("turns_played", outcome.turns_played)
        mlflow.log_metric("event_count", len(result.events))
        for player_id, score in outcome.scores.items():
            mlflow.log_metric(f"score_{player_id}", score)
        mlflow.log_param("winners", ",".join(outcome.winners))

        with TemporaryDirectory() as tmp_dir:
            artifact_path = Path(tmp_dir) / "simulation_events.jsonl"
            artifact_path.write_text(
                "\n".join(event.model_dump_json() for event in result.events),
                encoding="utf-8",
            )
            outcome_path = Path(tmp_dir) / "outcome.json"
            outcome_path.write_text(json.dumps(asdict(outcome), indent=2), encoding="utf-8")
            mlflow.log_artifacts(tmp_dir)
