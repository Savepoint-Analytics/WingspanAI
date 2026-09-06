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
    NetValueOpponentResponseAgent,
    PotentialPointsAgent,
    RandomLegalAgent,
    StrategyArchetype,
    StrategyArchetypeAgent,
    load_guardrail_config,
)
from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig
from wingspan_ai.agents.setup import (
    ArchetypeSetupPolicy,
    DefaultSetupPolicy,
    NetValueSetupPolicy,
    PotentialPointsSetupPolicy,
)
from wingspan_ai.config import database_url_from_env, load_dotenv, object_storage_config_from_env
from wingspan_ai.content.filters import filter_catalog_by_power_status
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.sample_catalog import make_sample_catalog
from wingspan_ai.provenance import code_provenance
from wingspan_ai.rules import MultiplayerAuditError, audit_rule_coverage
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
    "net_value_response",
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
        "net_value_response",
        "archetype_egg_focus",
        "archetype_engine_builder",
        "archetype_food_acceleration",
        "archetype_card_draw",
        "archetype_bonus_card_focus",
        "archetype_round_goal_chase",
        "monte_carlo_rollout",
    }
)
#: Prefix marking a roster entry as a guardrailed variant of a base agent,
#: e.g. "guardrailed:potential_points". This makes guardrailed agents
#: first-class competitors in a round robin, rather than a seat-level setting.
GUARDRAILED_PREFIX = "guardrailed:"
DEFAULT_GUARDRAIL_CONFIG_PATH = "configs/guardrails/base_heuristic.yaml"
SetupPolicyKind = Literal["agent_default", "control", "strategic"]
VALID_SETUP_POLICY_KINDS = frozenset({"agent_default", "control", "strategic"})
#: Wingspan supports 1-5 players; the simulator is verified for 2-5.
MAX_PLAYER_COUNT = 5
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
    player_one_agent_kind: PlayerTwoAgentKind = "random_legal",
    player_two_agent_kind: PlayerTwoAgentKind = "greedy_immediate",
    player_agent_kinds: list[str] | None = None,
    guardrail_seats: tuple[str, ...] = ("p2",),
    setup_policy_kind: SetupPolicyKind = "agent_default",
    seat_rotation: int = 0,
    power_status_filter: list[str] | None = None,
    excluded_power_handler_keys: list[str] | None = None,
    monte_carlo_rollout_count: int = 8,
    monte_carlo_rollout_depth: int = 12,
    monte_carlo_max_decision_time_ms: float | None = None,
    monte_carlo_max_candidate_actions: int | None = 12,
    net_value_max_candidate_actions: int | None = 12,
    net_value_max_opponent_response_actions: int | None = 8,
    net_value_response_mode: str = "expected",
    potential_points_search: PotentialPointsSearchConfig | None = None,
) -> dict[str, Any]:
    """Run and persist one game within a labelled simulation batch."""

    load_dotenv()
    resolved_batch_kind = _validate_batch_kind(batch_kind)
    resolved_batch_label = _validate_path_segment(batch_label, "batch_label")
    resolved_batch_id = _validate_path_segment(batch_id or _new_batch_id(), "batch_id")
    resolved_lineup = _resolve_agent_lineup(
        player_agent_kinds,
        player_one_agent_kind,
        player_two_agent_kind,
    )
    resolved_player_one_agent_kind = resolved_lineup[0]
    resolved_player_two_agent_kind = resolved_lineup[1] if len(resolved_lineup) > 1 else None
    resolved_setup_policy_kind = _validate_setup_policy_kind(setup_policy_kind)
    resolved_workbook_path = Path(workbook_path)
    workbook_exists = resolved_workbook_path.exists()
    catalog = (
        load_base_game_content_catalog(resolved_workbook_path)
        if workbook_exists
        else make_sample_catalog()
    )
    content_filter_payload = None
    if power_status_filter is not None or excluded_power_handler_keys is not None:
        filter_result = filter_catalog_by_power_status(
            catalog,
            power_status_filter,
            excluded_handler_keys=excluded_power_handler_keys,
        )
        catalog = filter_result.catalog
        content_filter_payload = filter_result.as_manifest_payload()

    guardrail_config = (
        load_guardrail_config(guardrail_config_path) if guardrail_config_path is not None else None
    )

    def build_seat_agent(agent_kind: PlayerTwoAgentKind, seat: str):
        base_agent = _make_agent(
            agent_kind,
            seat=seat,
            setup_policy_kind=resolved_setup_policy_kind,
            random_seed=random_seed,
            monte_carlo_rollout_count=monte_carlo_rollout_count,
            monte_carlo_rollout_depth=monte_carlo_rollout_depth,
            monte_carlo_max_decision_time_ms=monte_carlo_max_decision_time_ms,
            monte_carlo_max_candidate_actions=monte_carlo_max_candidate_actions,
            net_value_max_candidate_actions=net_value_max_candidate_actions,
            net_value_max_opponent_response_actions=net_value_max_opponent_response_actions,
            net_value_response_mode=net_value_response_mode,
            potential_points_search=potential_points_search,
        )
        if guardrail_config is None or seat not in guardrail_seats:
            return base_agent
        return GuardrailedAgent(
            base_agent,
            guardrail_config,
            agent_id=_guardrailed_agent_id(agent_kind, seat),
        )

    # Agent identity travels with the policy, not the seat. `seat_rotation`
    # rotates the lineup so the same matchup can be replayed with each agent in
    # each seat, which is how seat advantage is cancelled (see ADR 0002).
    lineup_agents = [
        build_seat_agent(agent_kind, f"p{index + 1}")
        for index, agent_kind in enumerate(resolved_lineup)
    ]
    resolved_seat_rotation = seat_rotation % len(lineup_agents)
    seated_agents = lineup_agents[resolved_seat_rotation:] + lineup_agents[:resolved_seat_rotation]
    result = run_single_game(
        catalog,
        seated_agents,
        random_seed=random_seed,
        game_id=f"{resolved_batch_id}_seed_{random_seed}",
    )
    replay_validation = validate_simulation_replay(catalog, result.events)
    replay_validation_payload = asdict(replay_validation)
    if require_valid_replay and not replay_validation.is_valid:
        error_summary = "; ".join(replay_validation.errors[:3])
        raise RuntimeError(f"Replay validation failed for seed {random_seed}: {error_summary}")

    rule_audits = audit_rule_coverage(catalog, player_count=len(lineup_agents))
    multiplayer_audit = rule_audits.get("multiplayer") or {}
    # A 3+ player result is only meaningful if the player-count-sensitive rules
    # hold. Fail loudly rather than let a bad multiplayer batch look valid.
    if len(lineup_agents) >= 3 and not multiplayer_audit.get("publication_safe", False):
        raise MultiplayerAuditError(list(multiplayer_audit.get("failed_checks", [])))

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
        "player_one_agent_kind": resolved_player_one_agent_kind,
        "player_one_agent_id": lineup_agents[0].agent_id,
        "player_two_agent_kind": resolved_player_two_agent_kind,
        "player_two_agent_id": (lineup_agents[1].agent_id if len(lineup_agents) > 1 else None),
        "player_agent_kinds": list(resolved_lineup),
        "player_agent_ids": [agent.agent_id for agent in lineup_agents],
        "player_count": len(lineup_agents),
        "seat_rotation": resolved_seat_rotation,
        "seated_agent_ids": [agent.agent_id for agent in seated_agents],
        "setup_policy_kind": resolved_setup_policy_kind,
        "guardrail_config_path": guardrail_config_path,
        "guardrail_seats": list(guardrail_seats),
        "guardrail_config_name": guardrail_config.name if guardrail_config is not None else None,
        "content_filter": content_filter_payload,
        "monte_carlo_rollout_count": monte_carlo_rollout_count,
        "monte_carlo_rollout_depth": monte_carlo_rollout_depth,
        "monte_carlo_max_decision_time_ms": monte_carlo_max_decision_time_ms,
        "monte_carlo_max_candidate_actions": monte_carlo_max_candidate_actions,
        "net_value_max_candidate_actions": net_value_max_candidate_actions,
        "net_value_max_opponent_response_actions": net_value_max_opponent_response_actions,
        "net_value_response_mode": net_value_response_mode,
        "potential_points_search": _search_payload(potential_points_search),
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
            key_prefix = f"{batch_prefix}/seed_{random_seed}/{result.outcome.simulation_run_id}"
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
        "player_one_agent_kind": resolved_player_one_agent_kind,
        "player_one_agent_id": lineup_agents[0].agent_id,
        "player_two_agent_kind": resolved_player_two_agent_kind,
        "player_two_agent_id": (lineup_agents[1].agent_id if len(lineup_agents) > 1 else None),
        "player_agent_kinds": list(resolved_lineup),
        "player_agent_ids": [agent.agent_id for agent in lineup_agents],
        "player_count": len(lineup_agents),
        "seat_rotation": resolved_seat_rotation,
        "seated_agent_ids": [agent.agent_id for agent in seated_agents],
        "setup_policy_kind": resolved_setup_policy_kind,
        "content_filter": content_filter_payload,
        "guardrail_config_path": guardrail_config_path,
        "guardrail_config_name": batch_metadata["guardrail_config_name"],
        "monte_carlo_rollout_count": monte_carlo_rollout_count,
        "monte_carlo_rollout_depth": monte_carlo_rollout_depth,
        "monte_carlo_max_decision_time_ms": monte_carlo_max_decision_time_ms,
        "monte_carlo_max_candidate_actions": monte_carlo_max_candidate_actions,
        "net_value_max_candidate_actions": net_value_max_candidate_actions,
        "net_value_max_opponent_response_actions": net_value_max_opponent_response_actions,
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
    base_kind = agent_kind.removeprefix(GUARDRAILED_PREFIX)
    if base_kind not in VALID_PLAYER_TWO_AGENT_KINDS:
        allowed = ", ".join(sorted(VALID_PLAYER_TWO_AGENT_KINDS))
        raise ValueError(
            f"agent kind must be one of: {allowed}, optionally prefixed with '{GUARDRAILED_PREFIX}'"
        )
    return agent_kind  # type: ignore[return-value]


def _apply_setup_policy(agent, agent_kind: PlayerTwoAgentKind, setup_policy_kind: str):
    """Override an agent's opening policy so setup can be a crossed factor.

    ``agent_default`` leaves each agent with whatever opening policy it ships
    with. ``control`` forces every agent onto the deterministic baseline opener,
    which reproduces the pre-setup-policy comparisons. ``strategic`` gives every
    agent the strongest opening policy that matches its turn policy.
    """

    if setup_policy_kind == "agent_default":
        return agent
    if setup_policy_kind == "control":
        agent.setup_policy = DefaultSetupPolicy()
        return agent
    if agent_kind.startswith("archetype_"):
        agent.setup_policy = ArchetypeSetupPolicy(agent_kind.removeprefix("archetype_"))
    elif agent_kind == "net_value_response":
        agent.setup_policy = NetValueSetupPolicy()
    else:
        agent.setup_policy = PotentialPointsSetupPolicy()
    return agent


def _search_payload(config: PotentialPointsSearchConfig | None) -> dict | None:
    """Manifest form of the potential-points search settings; None means agent defaults."""

    return config.as_manifest_payload() if config is not None else None


def _make_agent(
    agent_kind: PlayerTwoAgentKind,
    *,
    seat: str = "p2",
    setup_policy_kind: SetupPolicyKind = "agent_default",
    random_seed: int = 0,
    monte_carlo_rollout_count: int = 8,
    monte_carlo_rollout_depth: int = 12,
    monte_carlo_max_decision_time_ms: float | None = None,
    monte_carlo_max_candidate_actions: int | None = 12,
    net_value_max_candidate_actions: int | None = 12,
    net_value_max_opponent_response_actions: int | None = 8,
    net_value_response_mode: str = "expected",
    potential_points_search: PotentialPointsSearchConfig | None = None,
    guardrail_config_path: str | None = None,
):
    # A "guardrailed:" prefix wraps the base agent in its own guardrail layer,
    # so a roster can pit an agent against its guardrailed twin.
    wants_guardrails = agent_kind.startswith(GUARDRAILED_PREFIX)
    agent_kind = agent_kind.removeprefix(GUARDRAILED_PREFIX)  # type: ignore[assignment]

    # Each lineup slot gets its own agent RNG stream. Sharing `random_seed`
    # across seats made mirror matchups (random vs random, Monte Carlo vs
    # Monte Carlo) start from identical streams and make correlated early
    # choices, which is a confound rather than reproducibility.
    seat_ordinal = int(seat[1:]) if seat[1:].isdigit() else 0
    agent_random_seed = random_seed * 100 + seat_ordinal
    archetypes = {
        "archetype_egg_focus": (StrategyArchetype.EGG_FOCUS, "egg_focus"),
        "archetype_engine_builder": (StrategyArchetype.ENGINE_BUILDER, "engine_builder"),
        "archetype_food_acceleration": (StrategyArchetype.FOOD_ACCELERATION, "food_acceleration"),
        "archetype_card_draw": (StrategyArchetype.CARD_DRAW, "card_draw"),
        "archetype_bonus_card_focus": (StrategyArchetype.BONUS_CARD_FOCUS, "bonus_card_focus"),
        "archetype_round_goal_chase": (StrategyArchetype.ROUND_GOAL_CHASE, "round_goal_chase"),
    }

    if agent_kind == "random_legal":
        agent = RandomLegalAgent(agent_id=f"random_legal_{seat}", random_seed=agent_random_seed)
    elif agent_kind == "potential_points":
        search = potential_points_search or PotentialPointsSearchConfig()
        agent = PotentialPointsAgent(
            agent_id=f"potential_points_{seat}",
            search_depth=search.search_depth,
            final_search_turns=search.final_search_turns,
            search_beam_width=search.search_beam_width,
            determinization_samples=search.determinization_samples,
        )
    elif agent_kind == "net_value_response":
        agent = NetValueOpponentResponseAgent(
            agent_id=f"net_value_response_{seat}",
            max_candidate_actions=net_value_max_candidate_actions,
            max_opponent_response_actions=net_value_max_opponent_response_actions,
            response_mode=net_value_response_mode,
        )
    elif agent_kind in archetypes:
        archetype, archetype_label = archetypes[agent_kind]
        agent = StrategyArchetypeAgent(archetype, agent_id=f"{archetype_label}_{seat}")
    elif agent_kind == "monte_carlo_rollout":
        agent = MonteCarloRolloutAgent(
            agent_id=f"monte_carlo_rollout_{seat}",
            rollout_count=monte_carlo_rollout_count,
            rollout_depth=monte_carlo_rollout_depth,
            max_decision_time_ms=monte_carlo_max_decision_time_ms,
            max_candidate_actions=monte_carlo_max_candidate_actions,
            random_seed=agent_random_seed,
        )
    else:
        agent = GreedyBaselineAgent(agent_id=f"greedy_immediate_{seat}")

    # Apply the setup policy to the base agent before wrapping: GuardrailedAgent
    # delegates opening selection downward, so a policy set on the wrapper is
    # never consulted.
    agent = _apply_setup_policy(agent, agent_kind, setup_policy_kind)
    if not wants_guardrails:
        return agent
    config = load_guardrail_config(guardrail_config_path or DEFAULT_GUARDRAIL_CONFIG_PATH)
    return GuardrailedAgent(agent, config, agent_id=f"guardrailed_{agent.agent_id}")


def _make_player_two_agent(agent_kind: PlayerTwoAgentKind, **kwargs):
    """Backwards-compatible alias for the player-two seat."""

    return _make_agent(agent_kind, seat="p2", **kwargs)


def _guardrailed_agent_id(agent_kind: PlayerTwoAgentKind, seat: str = "p2") -> str:
    return f"guardrailed_{agent_kind}_{seat}"


def _resolve_agent_lineup(
    player_agent_kinds: list[str] | None,
    player_one_agent_kind: str,
    player_two_agent_kind: str,
) -> list[PlayerTwoAgentKind]:
    """Resolve the seated agent lineup, validating every entry.

    `player_agent_kinds` supports 1-5 player games. When omitted, the two-player
    `player_one_agent_kind` / `player_two_agent_kind` pair is used so existing
    callers and docs keep working unchanged.
    """

    kinds = (
        list(player_agent_kinds)
        if player_agent_kinds
        else [player_one_agent_kind, player_two_agent_kind]
    )
    if not 1 <= len(kinds) <= MAX_PLAYER_COUNT:
        raise ValueError(
            f"player_agent_kinds must contain 1 to {MAX_PLAYER_COUNT} agents, got {len(kinds)}"
        )
    return [_validate_player_two_agent_kind(kind) for kind in kinds]


def _validate_setup_policy_kind(setup_policy_kind: str) -> SetupPolicyKind:
    if setup_policy_kind not in VALID_SETUP_POLICY_KINDS:
        allowed = ", ".join(sorted(VALID_SETUP_POLICY_KINDS))
        raise ValueError(f"setup_policy_kind must be one of: {allowed}")
    return setup_policy_kind  # type: ignore[return-value]


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
    seat_rotation: int = 0,
    monte_carlo_rollout_count: int,
    monte_carlo_rollout_depth: int,
    monte_carlo_max_decision_time_ms: float | None,
    monte_carlo_max_candidate_actions: int | None,
    net_value_max_candidate_actions: int | None,
    net_value_max_opponent_response_actions: int | None,
    potential_points_search: PotentialPointsSearchConfig | None = None,
) -> Path:
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "code_provenance": code_provenance(),
        "batch_id": batch_id,
        "batch_kind": batch_kind,
        "batch_label": batch_label,
        "status": "completed",
        "started_at": started_at,
        "completed_at": completed_at,
        "workbook_path": workbook_path,
        "catalog_sources": sorted({result["catalog_source"] for result in results}),
        "guardrail_config_path": guardrail_config_path,
        "player_one_agent_kinds": sorted({result["player_one_agent_kind"] for result in results}),
        "player_one_agent_ids": sorted({result["player_one_agent_id"] for result in results}),
        "player_two_agent_kinds": sorted({result["player_two_agent_kind"] for result in results}),
        "player_two_agent_ids": sorted({result["player_two_agent_id"] for result in results}),
        "seat_rotation": seat_rotation,
        "player_counts": sorted({result["player_count"] for result in results}),
        "setup_policy_kinds": sorted({result["setup_policy_kind"] for result in results}),
        "content_filter": results[0].get("content_filter") if results else None,
        "monte_carlo_rollout_count": monte_carlo_rollout_count,
        "monte_carlo_rollout_depth": monte_carlo_rollout_depth,
        "monte_carlo_max_decision_time_ms": monte_carlo_max_decision_time_ms,
        "monte_carlo_max_candidate_actions": monte_carlo_max_candidate_actions,
        "net_value_max_candidate_actions": net_value_max_candidate_actions,
        "net_value_max_opponent_response_actions": net_value_max_opponent_response_actions,
        "potential_points_search": _search_payload(potential_points_search),
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
            "all_valid": all(result["replay_validation"]["is_valid"] for result in results),
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
                "player_one_agent_kind": result["player_one_agent_kind"],
                "player_one_agent_id": result["player_one_agent_id"],
                "player_two_agent_kind": result["player_two_agent_kind"],
                "player_two_agent_id": result["player_two_agent_id"],
                "seat_rotation": result["seat_rotation"],
                "player_count": result["player_count"],
                "player_agent_kinds": result["player_agent_kinds"],
                "seated_agent_ids": result["seated_agent_ids"],
                "setup_policy_kind": result["setup_policy_kind"],
                "guardrail_config_name": result["guardrail_config_name"],
                "monte_carlo_rollout_count": result["monte_carlo_rollout_count"],
                "monte_carlo_rollout_depth": result["monte_carlo_rollout_depth"],
                "monte_carlo_max_decision_time_ms": result["monte_carlo_max_decision_time_ms"],
                "monte_carlo_max_candidate_actions": result["monte_carlo_max_candidate_actions"],
                "net_value_max_candidate_actions": result["net_value_max_candidate_actions"],
                "net_value_max_opponent_response_actions": result[
                    "net_value_max_opponent_response_actions"
                ],
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
    player_one_agent_kind: PlayerTwoAgentKind = "random_legal",
    player_two_agent_kind: PlayerTwoAgentKind = "greedy_immediate",
    player_agent_kinds: list[str] | None = None,
    guardrail_seats: tuple[str, ...] = ("p2",),
    setup_policy_kind: SetupPolicyKind = "agent_default",
    seat_rotation: int = 0,
    power_status_filter: list[str] | None = None,
    excluded_power_handler_keys: list[str] | None = None,
    monte_carlo_rollout_count: int = 8,
    monte_carlo_rollout_depth: int = 12,
    monte_carlo_max_decision_time_ms: float | None = None,
    monte_carlo_max_candidate_actions: int | None = 12,
    net_value_max_candidate_actions: int | None = 12,
    net_value_max_opponent_response_actions: int | None = 8,
    net_value_response_mode: str = "expected",
    potential_points_search: PotentialPointsSearchConfig | None = None,
) -> list[dict[str, Any]]:
    """Run a labelled, seeded batch for local smoke tests or Prefect orchestration."""

    load_dotenv()
    resolved_batch_kind = _validate_batch_kind(batch_kind)
    resolved_batch_label = _validate_path_segment(batch_label, "batch_label")
    resolved_batch_id = _validate_path_segment(batch_id or _new_batch_id(), "batch_id")
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
            player_one_agent_kind=player_one_agent_kind,
            player_two_agent_kind=player_two_agent_kind,
            player_agent_kinds=player_agent_kinds,
            guardrail_seats=guardrail_seats,
            setup_policy_kind=setup_policy_kind,
            seat_rotation=seat_rotation,
            power_status_filter=power_status_filter,
            excluded_power_handler_keys=excluded_power_handler_keys,
            monte_carlo_rollout_count=monte_carlo_rollout_count,
            monte_carlo_rollout_depth=monte_carlo_rollout_depth,
            monte_carlo_max_decision_time_ms=monte_carlo_max_decision_time_ms,
            monte_carlo_max_candidate_actions=monte_carlo_max_candidate_actions,
            net_value_max_candidate_actions=net_value_max_candidate_actions,
            net_value_max_opponent_response_actions=net_value_max_opponent_response_actions,
            net_value_response_mode=net_value_response_mode,
            potential_points_search=potential_points_search,
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
            seat_rotation=seat_rotation,
            monte_carlo_rollout_count=monte_carlo_rollout_count,
            monte_carlo_rollout_depth=monte_carlo_rollout_depth,
            monte_carlo_max_decision_time_ms=monte_carlo_max_decision_time_ms,
            monte_carlo_max_candidate_actions=monte_carlo_max_candidate_actions,
            net_value_max_candidate_actions=net_value_max_candidate_actions,
            net_value_max_opponent_response_actions=net_value_max_opponent_response_actions,
            potential_points_search=potential_points_search,
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
                        f"{
                            _batch_object_prefix(
                                storage_config.prefix,
                                resolved_batch_kind,
                                resolved_batch_label,
                                resolved_batch_id,
                            )
                        }/{MANIFEST_FILENAME}"
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
