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

Policy ID: `potential_points_setup_v2` (`bonus_scoring="expected_points"`, default since 2026-09-16); `potential_points_setup_v1` is the historic `tag_overlap` scorer, still available behind the switch

Enumerates legal keep-count choices and starting-food combinations, then scores each selection for:

- Early bird playability.
- Low food cost and opening tempo.
- Bird victory points.
- Egg capacity.
- Power text that suggests draw, tuck, cache, egg, or food production.
- Habitat coverage.
- Bonus-card alignment.
- First round-goal alignment.

This is the default opening policy for `PotentialPointsAgent` — and it is
worse than `DefaultSetupPolicy`: on 120 dealt hands it keeps five birds and
no food in 119, and it lost −3.0 (p=0.022) to the plain opener on
2026-09-16 with a bonus choice that is worth +0.85 on its own. Round robins
run the champion under `control` for that reason.

**`bird_scoring="measured"`** (`potential_points_setup_v3`, or
`..._v3_keep3` with `target_keep_count=3`) replaces the hand-written bird
score with each bird's measured round-1 play value from the K=4
counterfactual attribution (`configs/bird_values/bird_play_values_k4.json`,
`agents/bird_values.py`), paid greedily from the starting food with a 0.5
discount when unaffordable, plus a food price when the keep count floats.
The `_keep3` variant holds the plain opener's three-birds-two-food shape
and changes only which birds. **Arm 2026-09-18 (`rr_opener_v3`, 80 paired
games vs the plain opener): −1.90 (p=0.13), win +0.06 (p=0.14). Not
adopted.** It kept birds worth 5.7 measured points against the plain
opener's 4.9, then played 64% of them (vs 72%), later (round 1.39 vs 1.29),
and 6.9 birds a game instead of 7.35: the plain opener's cheapest-cost rule
buys tempo that a play value conditional on having been played does not
see. Observed play value is not keep value — the synergy programme's lesson
again. The variant stays available and is the `setup_policy` standing
holdout (5% of default-agent games).

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
| `PotentialPointsAgent` | `potential_points_setup_v2` |
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
