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
| `turn_number` | Active player's turn within the current round. In the base game this tops out at 8, 7, 6, and 5 in rounds 1-4. |
| `round_action_number` | Player-action sequence number within the current round across all players. For a 2-player base game this tops out at 16, 14, 12, and 10. |
| `global_turn_number` | Player-action sequence number across the whole game, used for replay/debug ordering. |
| `random_seed` | Seed used for setup and reproducibility. |
| `public_state_ref` | Reference key for a public state snapshot or replay frame. |
| `private_state_included` | Explicit flag for private/debug payloads. |
| `payload` | Event-specific JSON object. |

## Current Events

| Event | Emitted when | Key payload fields |
|---|---|---|
| `simulation_run_started` | A runner starts one game or batch member. | `player_count`, `agents` |
| `setup_selection_applied` | A player keeps/discards opening cards and starting food. | `selection_source`, `kept_bird_names`, `kept_bonus_card_names`, `starting_food` |
| `game_started` | Setup has produced initial public game state. | `bird_deck_count`, `bonus_deck_count`, `bird_tray`, `round_goals` |
| `round_started` | A new round begins. | `action_cubes` |
| `turn_started` | The active player starts a turn. | none yet |
| `legal_actions_generated` | Rules engine returns concrete legal actions. | `legal_action_count`, `legal_actions`, `legal_action_labels` |
| `action_selected` | Agent selects an action. | `agent_id`, `action`, `action_label`, `state_hash_before` |
| `action_resolved` | Transition has been applied. Its envelope uses the same action-start round/turn as `action_selected`; next-state counters live in the payload. | `acting_player_id`, `action`, `action_label`, `state_hash_before`, `state_hash_after`, `next_round_number`, `next_turn_number`, `next_round_action_number`, `next_global_turn_number`, `rng_draws` |
| `game_ended` | Runner builds final outcome. | `outcome`, `score_breakdowns` |
| `agent_decision_summary` | Agent provides policy diagnostics for the selected action. | `policy`, `legal_action_count`, `selected_action_type`, policy-specific fields |

## Private Information Rule

Events default to public or aggregate information. Any event that includes player hands, bonus cards, deck order, hidden scoring estimates, or training-only labels must set `private_state_included=true` and document why the payload is acceptable for the destination. Setup-selection events intentionally include private opening-hand choices and are marked private.

## Public State Snapshots

`SimulationResult.public_state_snapshots` stores JSON-serializable public observations keyed by `public_state_ref`. This gives analysis notebooks and future replay tools a stable handle for the public state around each emitted event without including private hands, bonus cards, or deck order.

Multiple telemetry events are emitted for one player action (`turn_started`, `legal_actions_generated`, `action_selected`, `agent_decision_summary`, `action_resolved`). Count `action_selected` or `action_resolved` events, not all events, when auditing Wingspan action-cube turn limits.

Base-game round/turn references:

- `rulebook_pdfs/WS_Core_Rulebook.pdf`, printed page 4: Wingspan is played over 4 rounds; players take 1 of 4 actions on their turn.
- `rulebook_pdfs/WS_Core_Rulebook.pdf`, printed page 5: round end occurs after all action cubes are placed; action-cube schedule is 8, 7, 6, and 5 turns per player.
- `rulebook_pdfs/WS_Core_Rulebook.pdf`, printed page 11: end-of-round goal scoring and bonus-card scoring references.

`write_simulation_artifacts(result, output_dir)` writes:

- `outcome.json`
- `events.jsonl`
- `public_state_snapshots.json`
- `replay_debug.json`

## Replay Direction

The runner stores action-level history, public snapshots, state hashes, and explicit RNG draw records for deterministic rerolls and stochastic power approximations.

Replay validation:

- `validate_simulation_replay(catalog, events)` reconstructs setup and transitions from telemetry, then verifies recorded state hashes.
- Deck draw records are emitted for direct deck draws, tray replenishment, tray refresh, tuck-from-deck powers, and deck-search powers.
