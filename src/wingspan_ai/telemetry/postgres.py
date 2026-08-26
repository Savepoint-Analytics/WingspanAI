"""PostgreSQL persistence for simulation events."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from wingspan_ai.telemetry.events import EventName, SimulationEvent

if TYPE_CHECKING:
    from wingspan_ai.simulation.runner import SimulationResult


class PostgresEventRepository:
    """Persist validated simulation results into PostgreSQL."""

    def __init__(self, database_url: str, *, auto_ensure_schema: bool = True) -> None:
        self.database_url = database_url
        self.auto_ensure_schema = auto_ensure_schema

    def ensure_schema(self) -> None:
        """Create the simulation telemetry schema when it does not exist."""

        psycopg, _jsonb = _import_psycopg()
        statements = [
            """
            create table if not exists simulation_runs (
                simulation_run_id text primary key,
                run_started_at timestamptz not null default now(),
                run_label text,
                ruleset_id text,
                random_seed integer,
                metadata jsonb not null default '{}'::jsonb
            )
            """,
            """
            create table if not exists games (
                game_id text primary key,
                simulation_run_id text not null references simulation_runs(simulation_run_id),
                random_seed integer not null,
                ruleset_id text not null,
                player_count integer not null,
                started_at timestamptz not null default now(),
                ended_at timestamptz,
                terminal_reason text,
                outcome jsonb not null default '{}'::jsonb
            )
            """,
            """
            create table if not exists agents (
                agent_instance_id text primary key,
                simulation_run_id text not null references simulation_runs(simulation_run_id),
                player_id text not null,
                agent_id text not null,
                config jsonb not null default '{}'::jsonb
            )
            """,
            """
            create table if not exists simulation_events (
                event_id text primary key,
                event_name text not null,
                event_version text not null,
                occurred_at timestamptz not null,
                simulation_run_id text not null references simulation_runs(simulation_run_id),
                game_id text references games(game_id),
                ruleset_id text,
                player_id text,
                agent_id text,
                round_number integer,
                turn_number integer,
                round_action_number integer,
                global_turn_number integer,
                random_seed integer,
                public_state_ref text,
                private_state_included boolean not null default false,
                payload jsonb not null default '{}'::jsonb,
                received_at timestamptz not null default now()
            )
            """,
            """
            create table if not exists game_scores (
                game_id text not null references games(game_id),
                player_id text not null,
                agent_id text,
                total_score integer not null,
                bird_points integer not null default 0,
                bonus_points integer not null default 0,
                round_goal_points integer not null default 0,
                egg_points integer not null default 0,
                cached_food_points integer not null default 0,
                tucked_card_points integer not null default 0,
                is_winner boolean not null default false,
                primary key (game_id, player_id)
            )
            """,
            """
            alter table simulation_events
            add column if not exists round_action_number integer
            """,
            """
            alter table simulation_events
            add column if not exists global_turn_number integer
            """,
            """
            create index if not exists simulation_events_run_game_idx
            on simulation_events (simulation_run_id, game_id)
            """,
            """
            create index if not exists simulation_events_name_time_idx
            on simulation_events (event_name, occurred_at)
            """,
            """
            create index if not exists simulation_events_turn_idx
            on simulation_events (game_id, round_number, turn_number, round_action_number)
            """,
            """
            create index if not exists simulation_events_global_turn_idx
            on simulation_events (game_id, global_turn_number)
            """,
            """
            create index if not exists simulation_events_payload_gin_idx
            on simulation_events using gin (payload)
            """,
        ]
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            connection.commit()

    def insert_simulation_result(
        self,
        result: SimulationResult,
        *,
        run_label: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, int]:
        """Persist run/game metadata, scores, and raw telemetry for a result."""

        if self.auto_ensure_schema:
            self.ensure_schema()

        self._upsert_simulation_metadata(result, run_label=run_label, metadata=metadata)
        event_count = self.insert_events(result.events, ensure_schema=False)
        return {"events": event_count, "games": 1, "runs": 1}

    def insert_events(
        self,
        events: Sequence[SimulationEvent],
        *,
        ensure_schema: bool | None = None,
    ) -> int:
        """Insert raw events into the `simulation_events` table."""

        should_ensure_schema = self.auto_ensure_schema if ensure_schema is None else ensure_schema
        if should_ensure_schema:
            self.ensure_schema()

        psycopg, jsonb = _import_psycopg()
        rows = [_event_row(event, jsonb=jsonb) for event in events]
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    insert into simulation_events (
                        event_id,
                        event_name,
                        event_version,
                        occurred_at,
                        simulation_run_id,
                        game_id,
                        ruleset_id,
                        player_id,
                        agent_id,
                        round_number,
                        turn_number,
                        round_action_number,
                        global_turn_number,
                        random_seed,
                        public_state_ref,
                        private_state_included,
                        payload
                    )
                    values (
                        %(event_id)s,
                        %(event_name)s,
                        %(event_version)s,
                        %(occurred_at)s,
                        %(simulation_run_id)s,
                        %(game_id)s,
                        %(ruleset_id)s,
                        %(player_id)s,
                        %(agent_id)s,
                        %(round_number)s,
                        %(turn_number)s,
                        %(round_action_number)s,
                        %(global_turn_number)s,
                        %(random_seed)s,
                        %(public_state_ref)s,
                        %(private_state_included)s,
                        %(payload)s
                    )
                    on conflict (event_id) do nothing
                    """,
                    rows,
                )
            connection.commit()
        return len(rows)

    def _upsert_simulation_metadata(
        self,
        result: SimulationResult,
        *,
        run_label: str | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        psycopg, jsonb = _import_psycopg()
        run_started = _first_event(result.events, EventName.SIMULATION_RUN_STARTED)
        game_started = _first_event(result.events, EventName.GAME_STARTED)
        game_ended = _first_event(result.events, EventName.GAME_ENDED)
        outcome = asdict(result.outcome)
        ruleset_id = result.state.ruleset.ruleset_id
        player_count = len(result.state.players)
        score_breakdowns = (
            game_ended.payload.get("score_breakdowns", {}) if game_ended is not None else {}
        )
        winners = set(result.outcome.winners)

        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into simulation_runs (
                        simulation_run_id,
                        run_started_at,
                        run_label,
                        ruleset_id,
                        random_seed,
                        metadata
                    )
                    values (
                        %(simulation_run_id)s,
                        coalesce(%(run_started_at)s, now()),
                        %(run_label)s,
                        %(ruleset_id)s,
                        %(random_seed)s,
                        %(metadata)s
                    )
                    on conflict (simulation_run_id) do update set
                        run_label = excluded.run_label,
                        ruleset_id = excluded.ruleset_id,
                        random_seed = excluded.random_seed,
                        metadata = simulation_runs.metadata || excluded.metadata
                    """,
                    {
                        "simulation_run_id": result.outcome.simulation_run_id,
                        "run_started_at": (
                            run_started.occurred_at if run_started is not None else None
                        ),
                        "run_label": run_label,
                        "ruleset_id": ruleset_id,
                        "random_seed": result.outcome.random_seed,
                        "metadata": jsonb(metadata or {}),
                    },
                )
                cursor.execute(
                    """
                    insert into games (
                        game_id,
                        simulation_run_id,
                        random_seed,
                        ruleset_id,
                        player_count,
                        started_at,
                        ended_at,
                        terminal_reason,
                        outcome
                    )
                    values (
                        %(game_id)s,
                        %(simulation_run_id)s,
                        %(random_seed)s,
                        %(ruleset_id)s,
                        %(player_count)s,
                        coalesce(%(started_at)s, now()),
                        %(ended_at)s,
                        %(terminal_reason)s,
                        %(outcome)s
                    )
                    on conflict (game_id) do update set
                        terminal_reason = excluded.terminal_reason,
                        ended_at = excluded.ended_at,
                        outcome = excluded.outcome
                    """,
                    {
                        "game_id": result.outcome.game_id,
                        "simulation_run_id": result.outcome.simulation_run_id,
                        "random_seed": result.outcome.random_seed,
                        "ruleset_id": ruleset_id,
                        "player_count": player_count,
                        "started_at": (
                            game_started.occurred_at if game_started is not None else None
                        ),
                        "ended_at": game_ended.occurred_at if game_ended is not None else None,
                        "terminal_reason": result.outcome.terminal_reason,
                        "outcome": jsonb(outcome),
                    },
                )
                for player in result.state.players:
                    cursor.execute(
                        """
                        insert into agents (
                            agent_instance_id,
                            simulation_run_id,
                            player_id,
                            agent_id,
                            config
                        )
                        values (
                            %(agent_instance_id)s,
                            %(simulation_run_id)s,
                            %(player_id)s,
                            %(agent_id)s,
                            %(config)s
                        )
                        on conflict (agent_instance_id) do update set
                            agent_id = excluded.agent_id,
                            config = excluded.config
                        """,
                        {
                            "agent_instance_id": (
                                f"{result.outcome.simulation_run_id}:"
                                f"{player.player_id}:{player.agent_id}"
                            ),
                            "simulation_run_id": result.outcome.simulation_run_id,
                            "player_id": player.player_id,
                            "agent_id": player.agent_id,
                            "config": jsonb({}),
                        },
                    )
                    breakdown = score_breakdowns.get(player.player_id, {})
                    cursor.execute(
                        """
                        insert into game_scores (
                            game_id,
                            player_id,
                            agent_id,
                            total_score,
                            bird_points,
                            bonus_points,
                            round_goal_points,
                            egg_points,
                            cached_food_points,
                            tucked_card_points,
                            is_winner
                        )
                        values (
                            %(game_id)s,
                            %(player_id)s,
                            %(agent_id)s,
                            %(total_score)s,
                            %(bird_points)s,
                            %(bonus_points)s,
                            %(round_goal_points)s,
                            %(egg_points)s,
                            %(cached_food_points)s,
                            %(tucked_card_points)s,
                            %(is_winner)s
                        )
                        on conflict (game_id, player_id) do update set
                            agent_id = excluded.agent_id,
                            total_score = excluded.total_score,
                            bird_points = excluded.bird_points,
                            bonus_points = excluded.bonus_points,
                            round_goal_points = excluded.round_goal_points,
                            egg_points = excluded.egg_points,
                            cached_food_points = excluded.cached_food_points,
                            tucked_card_points = excluded.tucked_card_points,
                            is_winner = excluded.is_winner
                        """,
                        {
                            "game_id": result.outcome.game_id,
                            "player_id": player.player_id,
                            "agent_id": player.agent_id,
                            "total_score": result.outcome.scores[player.player_id],
                            "bird_points": breakdown.get("bird_points", 0),
                            "bonus_points": breakdown.get("bonus_points", 0),
                            "round_goal_points": breakdown.get("round_goal_points", 0),
                            "egg_points": breakdown.get("egg_points", 0),
                            "cached_food_points": breakdown.get("cached_food_points", 0),
                            "tucked_card_points": breakdown.get("tucked_card_points", 0),
                            "is_winner": player.player_id in winners,
                        },
                    )
            connection.commit()


def _event_row(event: SimulationEvent, *, jsonb) -> dict:
    return {
        "event_id": event.event_id,
        "event_name": event.event_name.value,
        "event_version": event.event_version,
        "occurred_at": event.occurred_at,
        "simulation_run_id": event.simulation_run_id,
        "game_id": event.game_id,
        "ruleset_id": event.ruleset_id,
        "player_id": event.player_id,
        "agent_id": event.agent_id,
        "round_number": event.round_number,
        "turn_number": event.turn_number,
        "round_action_number": event.round_action_number,
        "global_turn_number": event.global_turn_number,
        "random_seed": event.random_seed,
        "public_state_ref": event.public_state_ref,
        "private_state_included": event.private_state_included,
        "payload": jsonb(event.payload),
    }


def _first_event(
    events: Sequence[SimulationEvent],
    event_name: EventName,
) -> SimulationEvent | None:
    return next((event for event in events if event.event_name == event_name), None)


def _import_psycopg():
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as error:
        raise RuntimeError(
            "psycopg is required for PostgreSQL ingestion. "
            "Install the db optional dependencies before using this repository."
        ) from error

    return psycopg, Jsonb
