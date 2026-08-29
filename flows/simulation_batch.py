"""Prefect-compatible simulation batch flow."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from wingspan_ai.agents import (
    GreedyBaselineAgent,
    GuardrailedAgent,
    MonteCarloRolloutAgent,
    PotentialPointsAgent,
    RandomLegalAgent,
    StrategyArchetype,
    StrategyArchetypeAgent,
    load_guardrail_config,
)
from wingspan_ai.config import database_url_from_env, load_dotenv, object_storage_config_from_env
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.sample_catalog import make_sample_catalog
from wingspan_ai.rules import audit_rule_coverage
from wingspan_ai.simulation import (
    run_single_game,
    validate_simulation_replay,
    write_simulation_artifacts,
)
from wingspan_ai.storage import (
    upload_directory_to_object_storage,
    upload_file_to_object_storage,
)
from wingspan_ai.telemetry import PostgresEventRepository

try:
    from prefect import flow, task
except ImportError:

    def flow(func=None, **_kwargs):
        if func is None:
            return lambda wrapped: wrapped
        return func

    def task(func=None, **_kwargs):
        if func is None:
            return lambda wrapped: wrapped
        return func


BatchKind = Literal["smoke", "experiment", "production"]
PlayerTwoAgentKind = Literal[
    "random_legal",
    "greedy_immediate",
    "potential_points",
    "archetype_egg_focus",
    "archetype_engine_builder",
    "archetype_food_acceleration",
    "archetype_card_draw",
    "archetype_bonus_card_focus",
    "archetype_round_goal_chase",
    "monte_carlo_rollout",
]
VALID_BATCH_KINDS = frozenset({"smoke", "experiment", "production"})
VALID_PLAYER_TWO_AGENT_KINDS = frozenset(
    {
        "greedy_immediate",
        "random_legal",
        "potential_points",
        "archetype_egg_focus",
        "archetype_engine_builder",
        "archetype_food_acceleration",
        "archetype_card_draw",
        "archetype_bonus_card_focus",
        "archetype_round_goal_chase",
        "monte_carlo_rollout",
    }
)
DEFAULT_ARTIFACT_ROOT = "artifacts"
DEFAULT_RUN_LABEL = "core_random_vs_greedy"
MANIFEST_FILENAME = "batch_manifest.json"
MANIFEST_SCHEMA_VERSION = "wingspan.simulation_batch_manifest.v1"


@task
def run_seeded_game(
    workbook_path: str,
    random_seed: int,
    artifact_root: str | None = DEFAULT_ARTIFACT_ROOT,
    persist_postgres: bool | None = None,
    upload_artifacts: bool | None = None,
    *,
    batch_kind: BatchKind = "smoke",
    batch_label: str = DEFAULT_RUN_LABEL,
    batch_id: str | None = None,
    require_valid_replay: bool = True,
    guardrail_config_path: str | None = None,
    player_two_agent_kind: PlayerTwoAgentKind = "greedy_immediate",
) -> dict[str, Any]:
    """Run and persist one game within a labelled simulation batch."""

    load_dotenv()
    resolved_batch_kind = _validate_batch_kind(batch_kind)
    resolved_batch_label = _validate_path_segment(batch_label, "batch_label")
    resolved_batch_id = _validate_path_segment(batch_id or _new_batch_id(), "batch_id")
    resolved_player_two_agent_kind = _validate_player_two_agent_kind(player_two_agent_kind)
    resolved_workbook_path = Path(workbook_path)
    workbook_exists = resolved_workbook_path.exists()
    catalog = (
        load_base_game_content_catalog(resolved_workbook_path)
        if workbook_exists
        else make_sample_catalog()
    )
    base_agent = _make_player_two_agent(
        resolved_player_two_agent_kind,
        random_seed=random_seed,
    )
    guardrail_config = (
        load_guardrail_config(guardrail_config_path)
        if guardrail_config_path is not None
        else None
    )
    player_two_agent = (
        GuardrailedAgent(
            base_agent,
            guardrail_config,
            agent_id=_guardrailed_agent_id(resolved_player_two_agent_kind),
        )
        if guardrail_config is not None
        else base_agent
    )
    result = run_single_game(
        catalog,
        [
            RandomLegalAgent(agent_id="random_legal_p1", random_seed=random_seed),
            player_two_agent,
        ],
        random_seed=random_seed,
        game_id=f"{resolved_batch_id}_seed_{random_seed}",
    )
    replay_validation = validate_simulation_replay(catalog, result.events)
    replay_validation_payload = asdict(replay_validation)
    if require_valid_replay and not replay_validation.is_valid:
        error_summary = "; ".join(replay_validation.errors[:3])
        raise RuntimeError(f"Replay validation failed for seed {random_seed}: {error_summary}")

    rule_audits = audit_rule_coverage(catalog)

    artifact_dir = None
    if artifact_root is not None:
        artifact_dir = write_simulation_artifacts(
            result,
            _batch_directory(
                artifact_root,
                resolved_batch_kind,
                resolved_batch_label,
                resolved_batch_id,
            )
            / f"seed_{random_seed}",
        )

    batch_metadata = {
        "artifact_dir": str(artifact_dir) if artifact_dir is not None else None,
        "batch_id": resolved_batch_id,
        "batch_kind": resolved_batch_kind,
        "batch_label": resolved_batch_label,
        "catalog_source": str(resolved_workbook_path) if workbook_exists else "sample_catalog",
        "player_two_agent_kind": resolved_player_two_agent_kind,
        "player_two_agent_id": player_two_agent.agent_id,
        "guardrail_config_path": guardrail_config_path,
        "guardrail_config_name": guardrail_config.name if guardrail_config is not None else None,
        "replay_validation": replay_validation_payload,
        "rule_audits": rule_audits,
    }
    database_url = database_url_from_env()
    should_persist_postgres = bool(database_url) if persist_postgres is None else persist_postgres
    postgres_result = {"enabled": should_persist_postgres, "inserted": None}
    if should_persist_postgres:
        try:
            if database_url is None:
                raise RuntimeError(
                    "PostgreSQL persistence requested but no database URL is configured."
                )
            repository = PostgresEventRepository(database_url)
            postgres_result["inserted"] = repository.insert_simulation_result(
                result,
                run_label=f"{resolved_batch_kind}:{resolved_batch_label}",
                metadata=batch_metadata,
            )
        except Exception as error:
            if persist_postgres is True:
                raise
            postgres_result["error"] = _format_persistence_error(error)

    storage_config = object_storage_config_from_env()
    should_upload_artifacts = (
        bool(storage_config and artifact_dir) if upload_artifacts is None else upload_artifacts
    )
    storage_result = {"enabled": should_upload_artifacts, "uploaded": None}
    if should_upload_artifacts:
        try:
            if storage_config is None:
                raise RuntimeError("Artifact upload requested but no MinIO/S3 config is available.")
            if artifact_dir is None:
                raise RuntimeError("Artifact upload requested but artifact writing is disabled.")
            batch_prefix = _batch_object_prefix(
                storage_config.prefix,
                resolved_batch_kind,
                resolved_batch_label,
                resolved_batch_id,
            )
            key_prefix = (
                f"{batch_prefix}/seed_{random_seed}/"
                f"{result.outcome.simulation_run_id}"
            )
            uploaded_uris = upload_directory_to_object_storage(
                artifact_dir,
                storage_config,
                key_prefix=key_prefix,
            )
            storage_result["uploaded"] = {
                "count": len(uploaded_uris),
                "uris": uploaded_uris,
            }
        except Exception as error:
            if upload_artifacts is True:
                raise
            storage_result["error"] = _format_persistence_error(error)

    return {
        "batch_id": resolved_batch_id,
        "batch_kind": resolved_batch_kind,
        "batch_label": resolved_batch_label,
        "catalog_source": batch_metadata["catalog_source"],
        "player_two_agent_kind": resolved_player_two_agent_kind,
        "player_two_agent_id": player_two_agent.agent_id,
        "guardrail_config_path": guardrail_config_path,
        "guardrail_config_name": batch_metadata["guardrail_config_name"],
        "ruleset_id": result.state.ruleset.ruleset_id,
        "outcome": asdict(result.outcome),
        "event_count": len(result.events),
        "replay_validation": replay_validation_payload,
        "rule_audits": rule_audits,
        "artifact_dir": str(artifact_dir) if artifact_dir is not None else None,
        "postgres": postgres_result,
        "object_storage": storage_result,
    }


def _format_persistence_error(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def _new_batch_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid4().hex[:8]}"


def _validate_batch_kind(batch_kind: str) -> BatchKind:
    if batch_kind not in VALID_BATCH_KINDS:
        allowed = ", ".join(sorted(VALID_BATCH_KINDS))
        raise ValueError(f"batch_kind must be one of: {allowed}")
    return batch_kind  # type: ignore[return-value]


def _validate_player_two_agent_kind(agent_kind: str) -> PlayerTwoAgentKind:
    if agent_kind not in VALID_PLAYER_TWO_AGENT_KINDS:
        allowed = ", ".join(sorted(VALID_PLAYER_TWO_AGENT_KINDS))
        raise ValueError(f"player_two_agent_kind must be one of: {allowed}")
    return agent_kind  # type: ignore[return-value]


def _make_player_two_agent(agent_kind: PlayerTwoAgentKind, *, random_seed: int = 0):
    if agent_kind == "random_legal":
        return RandomLegalAgent(agent_id="random_legal_p2", random_seed=random_seed)
    if agent_kind == "potential_points":
        return PotentialPointsAgent(agent_id="potential_points_p2")
    if agent_kind == "archetype_egg_focus":
        return StrategyArchetypeAgent(StrategyArchetype.EGG_FOCUS, agent_id="egg_focus_p2")
    if agent_kind == "archetype_engine_builder":
        return StrategyArchetypeAgent(
            StrategyArchetype.ENGINE_BUILDER,
            agent_id="engine_builder_p2",
        )
    if agent_kind == "archetype_food_acceleration":
        return StrategyArchetypeAgent(
            StrategyArchetype.FOOD_ACCELERATION,
            agent_id="food_acceleration_p2",
        )
    if agent_kind == "archetype_card_draw":
        return StrategyArchetypeAgent(StrategyArchetype.CARD_DRAW, agent_id="card_draw_p2")
    if agent_kind == "archetype_bonus_card_focus":
        return StrategyArchetypeAgent(
            StrategyArchetype.BONUS_CARD_FOCUS,
            agent_id="bonus_card_focus_p2",
        )
    if agent_kind == "archetype_round_goal_chase":
        return StrategyArchetypeAgent(
            StrategyArchetype.ROUND_GOAL_CHASE,
            agent_id="round_goal_chase_p2",
        )
    if agent_kind == "monte_carlo_rollout":
        return MonteCarloRolloutAgent(agent_id="monte_carlo_rollout_p2", random_seed=random_seed)
    return GreedyBaselineAgent(agent_id="greedy_immediate_p2")


def _guardrailed_agent_id(agent_kind: PlayerTwoAgentKind) -> str:
    return f"guardrailed_{agent_kind}_p2"


def _validate_path_segment(value: str, name: str) -> str:
    resolved_value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", resolved_value):
        raise ValueError(
            f"{name} must start with an alphanumeric character and contain only "
            "letters, numbers, '.', '_', or '-'"
        )
    return resolved_value


def _batch_directory(
    artifact_root: str | Path,
    batch_kind: str,
    batch_label: str,
    batch_id: str,
) -> Path:
    return Path(artifact_root) / batch_kind / batch_label / batch_id


def _batch_object_prefix(
    configured_prefix: str,
    batch_kind: str,
    batch_label: str,
    batch_id: str,
) -> str:
    prefix = configured_prefix.strip("/")
    namespaced_path = f"{batch_kind}/{batch_label}/{batch_id}"
    return f"{prefix}/{namespaced_path}" if prefix else namespaced_path


def _write_batch_manifest(
    *,
    batch_directory: Path,
    batch_id: str,
    batch_kind: str,
    batch_label: str,
    workbook_path: str,
    started_at: str,
    completed_at: str,
    seeds: list[int],
    results: list[dict[str, Any]],
    guardrail_config_path: str | None,
) -> Path:
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "batch_id": batch_id,
        "batch_kind": batch_kind,
        "batch_label": batch_label,
        "status": "completed",
        "started_at": started_at,
        "completed_at": completed_at,
        "workbook_path": workbook_path,
        "catalog_sources": sorted({result["catalog_source"] for result in results}),
        "guardrail_config_path": guardrail_config_path,
        "player_two_agent_kinds": sorted({result["player_two_agent_kind"] for result in results}),
        "player_two_agent_ids": sorted({result["player_two_agent_id"] for result in results}),
        "guardrail_config_names": sorted(
            {
                result["guardrail_config_name"]
                for result in results
                if result["guardrail_config_name"] is not None
            }
        ),
        "seeds": seeds,
        "game_count": len(results),
        "event_count": sum(result["event_count"] for result in results),
        "replay_validation": {
            "all_valid": all(
                result["replay_validation"]["is_valid"] for result in results
            ),
            "valid_game_count": sum(
                1 for result in results if result["replay_validation"]["is_valid"]
            ),
            "invalid_game_count": sum(
                1 for result in results if not result["replay_validation"]["is_valid"]
            ),
        },
        "rule_audits": results[0].get("rule_audits") if results else None,
        "games": [
            {
                "outcome": result["outcome"],
                "event_count": result["event_count"],
                "ruleset_id": result["ruleset_id"],
                "player_two_agent_kind": result["player_two_agent_kind"],
                "player_two_agent_id": result["player_two_agent_id"],
                "guardrail_config_name": result["guardrail_config_name"],
                "replay_validation": result["replay_validation"],
                "artifact_dir": result["artifact_dir"],
                "postgres": result["postgres"],
                "object_storage": result["object_storage"],
            }
            for result in results
        ],
    }
    batch_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = batch_directory / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


@flow(name="wingspan-simulation-batch")
def run_simulation_batch(
    workbook_path: str = str(DEFAULT_WORKBOOK_PATH),
    seeds: list[int] | None = None,
    artifact_root: str | None = DEFAULT_ARTIFACT_ROOT,
    persist_postgres: bool | None = None,
    upload_artifacts: bool | None = None,
    *,
    batch_kind: BatchKind = "smoke",
    batch_label: str = DEFAULT_RUN_LABEL,
    batch_id: str | None = None,
    require_valid_replay: bool = True,
    guardrail_config_path: str | None = None,
    player_two_agent_kind: PlayerTwoAgentKind = "greedy_immediate",
) -> list[dict[str, Any]]:
    """Run a labelled, seeded batch for local smoke tests or Prefect orchestration."""

    load_dotenv()
    resolved_batch_kind = _validate_batch_kind(batch_kind)
    resolved_batch_label = _validate_path_segment(batch_label, "batch_label")
    resolved_batch_id = _validate_path_segment(batch_id or _new_batch_id(), "batch_id")
    resolved_player_two_agent_kind = _validate_player_two_agent_kind(player_two_agent_kind)
    resolved_seeds = seeds or [1, 2, 3]
    started_at = datetime.now(UTC).isoformat()
    results = [
        run_seeded_game(
            workbook_path,
            seed,
            artifact_root,
            persist_postgres,
            upload_artifacts,
            batch_kind=resolved_batch_kind,
            batch_label=resolved_batch_label,
            batch_id=resolved_batch_id,
            require_valid_replay=require_valid_replay,
            guardrail_config_path=guardrail_config_path,
            player_two_agent_kind=resolved_player_two_agent_kind,
        )
        for seed in resolved_seeds
    ]

    manifest_path = None
    manifest_storage_result = {"enabled": False, "uploaded": None}
    if artifact_root is not None:
        batch_directory = _batch_directory(
            artifact_root,
            resolved_batch_kind,
            resolved_batch_label,
            resolved_batch_id,
        )
        manifest_path = _write_batch_manifest(
            batch_directory=batch_directory,
            batch_id=resolved_batch_id,
            batch_kind=resolved_batch_kind,
            batch_label=resolved_batch_label,
            workbook_path=workbook_path,
            started_at=started_at,
            completed_at=datetime.now(UTC).isoformat(),
            seeds=resolved_seeds,
            results=results,
            guardrail_config_path=guardrail_config_path,
        )
        storage_config = object_storage_config_from_env()
        should_upload_manifest = (
            bool(storage_config) if upload_artifacts is None else upload_artifacts
        )
        manifest_storage_result["enabled"] = should_upload_manifest
        if should_upload_manifest:
            try:
                if storage_config is None:
                    raise RuntimeError(
                        "Manifest upload requested but no MinIO/S3 config is available."
                    )
                manifest_uri = upload_file_to_object_storage(
                    manifest_path,
                    storage_config,
                    object_key=(
                        f"{_batch_object_prefix(
                            storage_config.prefix,
                            resolved_batch_kind,
                            resolved_batch_label,
                            resolved_batch_id,
                        )}/{MANIFEST_FILENAME}"
                    ),
                )
                manifest_storage_result["uploaded"] = {
                    "count": 1,
                    "uris": [manifest_uri],
                }
            except Exception as error:
                if upload_artifacts is True:
                    raise
                manifest_storage_result["error"] = _format_persistence_error(error)

    manifest_summary = {
        "path": str(manifest_path) if manifest_path is not None else None,
        "object_storage": manifest_storage_result,
    }
    for result in results:
        result["batch_manifest"] = manifest_summary
    return results


if __name__ == "__main__":
    print(run_simulation_batch())
