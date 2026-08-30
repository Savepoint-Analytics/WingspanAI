# Opening Setup Policies

Status: first implementation, 2026-08-29

## Purpose

Opening hand, bonus-card, and starting-food choices are now first-class policy decisions. This matters because the first setup choice determines early playability, habitat tempo, bonus alignment, and whether an agent starts with useful resources or dead cards.

The implementation lives in `src/wingspan_ai/agents/setup.py`.

## Runner Hook

The single-game runner deals full opening hands without applying setup, then asks each agent for `choose_initial_selection(player, context)` when available. The context is intentionally public:

- Face-up bird tray.
- Round-goal names.
- Round state.
- Player count.

Setup-selection telemetry now records:

- `selection_source`.
- `setup_policy_id`.
- Kept bird names.
- Kept bonus-card name.
- Starting food.
- Discarded birds and bonus cards.

Setup events are marked `private_state_included=true` because they contain opening hand and discarded-card details.

## Policies

### `DefaultSetupPolicy`

Policy ID: `default_setup_v1`

Preserves the prior deterministic baseline:

- Keep three low-cost birds, with victory points as a tie-breaker.
- Keep the first dealt bonus card.
- Take two food tokens biased toward kept bird costs.

This remains useful as a control condition.

### `PotentialPointsSetupPolicy`

Policy ID: `potential_points_setup_v1`

Enumerates legal keep-count choices and starting-food combinations, then scores each selection for:

- Early bird playability.
- Low food cost and opening tempo.
- Bird victory points.
- Egg capacity.
- Power text that suggests draw, tuck, cache, egg, or food production.
- Habitat coverage.
- Bonus-card alignment.
- First round-goal alignment.

This is the default opening policy for `PotentialPointsAgent`.

### `ArchetypeSetupPolicy`

Policy ID: `archetype_<name>_setup_v1`

Uses the potential-points opener as a base, then biases the opening toward the selected archetype:

- `egg_focus`: grassland access and egg capacity.
- `engine_builder`: flexible habitats and high-power cards.
- `food_acceleration`: forest access and food-producing powers.
- `card_draw`: wetland access and draw-card powers.
- `bonus_card_focus`: bonus-card tags, bonus-card powers, and kept-bonus alignment.
- `round_goal_chase`: first round-goal alignment.

This is the default opening policy for `StrategyArchetypeAgent`.

### `NetValueSetupPolicy`

Policy ID: `net_value_setup_v1`

Uses the potential-points opener as a base, then adds public setup-context pressure:

- Face-up tray cards that signal shared engine threats.
- Habitat overlap with public tray threats.
- Food-cost overlap with public tray threats.
- First round-goal alignment.

This is intentionally still conservative. It does not inspect opponent hidden hands or bonus cards. It is the default opening policy for `NetValueOpponentResponseAgent`.

## Agent Defaults

| Agent | Opening policy |
|---|---|
| `RandomLegalAgent` | `default_setup_v1` |
| `GreedyBaselineAgent` | `default_setup_v1` |
| `MonteCarloRolloutAgent` | `default_setup_v1` |
| `PotentialPointsAgent` | `potential_points_setup_v1` |
| `StrategyArchetypeAgent` | `archetype_<name>_setup_v1` |
| `NetValueOpponentResponseAgent` | `net_value_setup_v1` |
| `GuardrailedAgent` | delegates to wrapped agent setup policy |

## Current Limits

These policies are heuristic. They do not yet:

- Use sampled rollouts from setup.
- Estimate exact bonus-card endgame value.
- Model opponent opening selections.
- Model expansion-specific setup rules.
- Learn opening weights from tournament outcomes.

The next evidence step is to compare identical agents under default setup versus their strategic setup policy, then inspect whether score gains come from better first playable birds, stronger habitat openings, bonus progress, or later engine conversion.
