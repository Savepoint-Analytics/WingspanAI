# PostgreSQL Event Table Design

Status: initial draft, 2026-05-04

## Purpose

The database should preserve raw simulation events for replay while also supporting fast run/game/agent summaries for analysis. The first design keeps ingestion simple: validate events with Pydantic, store raw JSONB, and derive analysis tables later.

## Tables

```sql
create table simulation_runs (
    simulation_run_id text primary key,
    run_started_at timestamptz not null default now(),
    run_label text,
    ruleset_id text,
    random_seed integer,
    metadata jsonb not null default '{}'::jsonb
);

create table games (
    game_id text primary key,
    simulation_run_id text not null references simulation_runs(simulation_run_id),
    random_seed integer not null,
    ruleset_id text not null,
    player_count integer not null,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    terminal_reason text,
    outcome jsonb not null default '{}'::jsonb
);

create table agents (
    agent_instance_id text primary key,
    simulation_run_id text not null references simulation_runs(simulation_run_id),
    player_id text not null,
    agent_id text not null,
    config jsonb not null default '{}'::jsonb
);

create table simulation_events (
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
);

create table game_scores (
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
);
```

## Indexes

```sql
create index simulation_events_run_game_idx
    on simulation_events (simulation_run_id, game_id);

create index simulation_events_name_time_idx
    on simulation_events (event_name, occurred_at);

create index simulation_events_turn_idx
    on simulation_events (game_id, round_number, turn_number, round_action_number);

create index simulation_events_global_turn_idx
    on simulation_events (game_id, global_turn_number);

create index simulation_events_payload_gin_idx
    on simulation_events using gin (payload);
```

## Ingestion Contract

The draft FastAPI service at `src/wingspan_ai/telemetry/api.py` accepts an `EventBatch` and currently stores events in memory. The production path should:

1. Validate incoming events with `SimulationEvent`.
2. Upsert or create run/game metadata from start/end events.
3. Insert raw events into `simulation_events`.
4. Populate `game_scores` from `game_ended` payloads.
5. Reject or route private events unless the destination is approved for private training/debug data.

## Analysis Views To Add

- Action frequency by agent, round, and action type.
- Final score distribution by matchup and seed.
- Game length distribution by terminal reason.
- Card play frequency and immediate score delta.
- Private/debug-only training views with explicit access separation.
