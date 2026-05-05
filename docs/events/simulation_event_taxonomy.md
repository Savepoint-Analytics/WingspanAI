# Simulation Event Taxonomy

Status: initial draft, 2026-05-04

## Purpose

Simulation telemetry should make games replayable, auditable, and useful for strategy analysis. The first event schema lives in `src/wingspan_ai/telemetry/events.py` and is emitted by `src/wingspan_ai/simulation/runner.py`.

## Event Envelope

Every event uses a stable envelope:

| Field | Purpose |
|---|---|
| `event_id` | Unique event identifier. |
| `event_name` | Stable event name enum. |
| `event_version` | Contract version, currently `1.0`. |
| `occurred_at` | UTC event timestamp. |
| `simulation_run_id` | Batch/run identifier. |
| `game_id` | Game identifier within a run. |
| `ruleset_id` | Ruleset configuration identifier. |
| `player_id` | Current active player where applicable. |
| `agent_id` | Current active agent where applicable. |
| `round_number` | Current round. |
| `turn_number` | Current turn. |
| `random_seed` | Seed used for setup and reproducibility. |
| `public_state_ref` | Reference key for a public state snapshot or replay frame. |
| `private_state_included` | Explicit flag for private/debug payloads. |
| `payload` | Event-specific JSON object. |

## Current Events

| Event | Emitted when | Key payload fields |
|---|---|---|
| `simulation_run_started` | A runner starts one game or batch member. | `player_count`, `agents` |
| `game_started` | Setup has produced initial public game state. | `bird_deck_count`, `bonus_deck_count`, `bird_tray`, `round_goals` |
| `round_started` | A new round begins. | `action_cubes` |
| `turn_started` | The active player starts a turn. | none yet |
| `legal_actions_generated` | Rules engine returns concrete legal actions. | `legal_action_count`, `legal_actions` |
| `action_selected` | Agent selects an action. | `agent_id`, `action` |
| `action_resolved` | Transition has been applied. | `acting_player_id`, `action` |
| `game_ended` | Runner builds final outcome. | `outcome`, `score_breakdowns` |
| `agent_decision_summary` | Reserved for richer policy diagnostics. | not emitted yet |

## Private Information Rule

Events default to public or aggregate information. Any event that includes player hands, bonus cards, deck order, hidden scoring estimates, or training-only labels must set `private_state_included=true` and document why the payload is acceptable for the destination.

## Public State Snapshots

`SimulationResult.public_state_snapshots` stores JSON-serializable public observations keyed by `public_state_ref`. This gives analysis notebooks and future replay tools a stable handle for the public state around each emitted event without including private hands, bonus cards, or deck order.

`write_simulation_artifacts(result, output_dir)` writes:

- `outcome.json`
- `events.jsonl`
- `public_state_snapshots.json`

## Replay Direction

The first runner stores enough action-level history and public snapshots to inspect decisions, but exact replay will also need deck-order references and stochastic resolution records once bird powers are implemented.

Near-term replay additions:

- Add `state_hash_before` and `state_hash_after`.
- Add explicit RNG draw records for birdfeeder rerolls, predator powers, deck draws, and stochastic power handlers.
