"""PostgreSQL persistence for simulation events."""

from __future__ import annotations

from collections.abc import Sequence

from wingspan_ai.telemetry.events import SimulationEvent


class PostgresEventRepository:
    """Persist validated simulation events into PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def insert_events(self, events: Sequence[SimulationEvent]) -> int:
        """Insert events into the `simulation_events` table."""

        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError(
                "psycopg is required for PostgreSQL ingestion. "
                "Install the db optional dependencies before using this repository."
            ) from error

        rows = [_event_row(event) for event in events]
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


def _event_row(event: SimulationEvent) -> dict:
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
        "payload": event.payload,
    }
