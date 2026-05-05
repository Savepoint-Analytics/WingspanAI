"""Simulation artifact writers."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from wingspan_ai.simulation.runner import SimulationResult


def write_simulation_artifacts(result: SimulationResult, output_dir: str | Path) -> Path:
    """Write outcome, events, and public snapshots for one simulation result."""

    resolved_dir = Path(output_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)

    (resolved_dir / "outcome.json").write_text(
        json.dumps(asdict(result.outcome), indent=2),
        encoding="utf-8",
    )
    (resolved_dir / "events.jsonl").write_text(
        "\n".join(event.model_dump_json() for event in result.events),
        encoding="utf-8",
    )
    (resolved_dir / "public_state_snapshots.json").write_text(
        json.dumps(result.public_state_snapshots, indent=2),
        encoding="utf-8",
    )
    return resolved_dir
