# ADR 0007 - Choices inside bird powers resolve through a per-player seam, with today's rules frozen as the default

_Status: **proposed**, 2026-10-15. Awaiting Alex's review of findings A and B
in `docs/architecture/power_decision_methods.md`. Extends ADR 0003 (seeded
randomness) and ADR 0004 (canonical ordering); supersedes nothing._

## Context

The rules layer makes decisions the rulebook gives to the player. The three
fidelity audits of 2026-10-08 (`docs/rules/hidden_power_choices.md`,
`egg_spending_fidelity.md`, `card_discard_fidelity.md`) measured the extent:

| where the hidden choice lives | size |
|---|---|
| inside power handlers (16 handlers) | 112 of 180 powered birds, plus up to 12 pink birds if finding B holds |
| inside the action list (`_legal_gain_food_actions` bakes one pre-chosen discard into every spend-a-card variant) | 7 actions offered, 1 distinct card, on a measured 3-card hand |
| inside the egg guardrail (bare string match on nest type; cannot see bonus cards) | 17 of 180 birds; 4 of 26 bonus cards |

Three properties of the current code make this worse than a list of
heuristics that could each be tuned:

1. **The choices are invisible to every arm and every manifest.** A batch is
   described by its search configuration; the hand-written `min`/`max`/helper
   calls inside handlers are not part of it, so no registered arm has ever
   varied them and no result ledger row records them.
2. **The choice is made for the wrong player in some handlers.** Pink
   reactions fire on an opponent's turn; `all_players_lay_eggs` and
   `draw_cards_player_select` have other players choose. The code resolves
   these with the active player's context.
3. **The guardrails that exist do not share what they know.** The card
   guardrail considers bonus-card fit; the egg guardrail considers round
   goals; neither considers the other. Fixing each in place would add a third
   guardrail with a third blind spot.

The project is also two weeks from the ten human games (priority 1), whose
registration (`docs/experiments/self_play_opponent_plan.md`) names the exact
agent configuration the human faces. Anything that changes the champion's
behaviour before game ten is archived changes the opponent mid-study.

## Decision

Introduce one seam and route every in-power choice through it, with the
current behaviour frozen as the default:

- **Handlers stop choosing.** A handler that reaches a player choice builds a
  typed, frozen `PowerDecision` (kind, handler key, source bird, *deciding*
  player, canonically ordered options, chained-power depth) and asks that
  player's `DecisionResolver` for an option index.
- **Nine decision kinds, not sixteen handler-specific refactors.**
  `activate_optional_power`, `choose_food`, `choose_egg_target`,
  `choose_egg_to_spend`, `choose_card_from_hand`, `choose_card_to_keep`,
  `choose_habitat`, `choose_bird_to_play`, `choose_power_to_repeat`. A method
  written for a kind covers every handler that raises it; handler-specific
  overrides exist only where the value is handler-specific (movers, bonus-card
  keep, extra-bird play). Lookup order: `(handler_key, kind)` override → kind
  method → `legacy`.
- **The default resolver is today's code.** `LegacyHeuristicResolver`
  reproduces every current call exactly. With no resolver profile configured,
  `analysis/base_game_bit_identity.py` is identical and the archive stays
  replay-valid. Every other method is an opt-in arm.
- **Resolvers are looked up by the deciding player and see only that player's
  observation.** No resolver reads the true deck; a method that needs futures
  determinizes (`agents/determinization.py`). Peeking was measured at −2.4 and
  is not reopened here.
- **Three method tiers per kind — heuristic (H), greedy one-step (G),
  search/Bayes (S) — configured per kind and per search position (root /
  tree / rollout).** A G resolver inside every child expansion multiplies
  search cost by the option count, so the tier at the root is a separate
  setting from the tier in the tree. Style (what the player values) is an
  existing `StrategyArchetype` weight vector and is independent of tier.
- **Every resolved decision is a versioned event** (`power_decision_resolved`:
  kind, handler, options, chosen index, `method_key`, per-option values when
  computed). Replay feeds logged choices back through a `ReplayResolver`, so
  replay validation survives non-legacy methods. **The manifest records the
  resolver profile**, which closes the "invisible to every manifest" gap.
- **Lifting into `LegalAction` is reserved** for choices whose options are
  known at action time and for which there is evidence. `move_bird_habitat`'s
  destination qualifies and stays a separate task; choices that depend on a
  draw or a die roll do not, because lifting them means enumerating chance
  outcomes or leaking hidden cards into the action space.

### Constraints that follow

- Resolver randomness, where any method has it, is seeded from `decision_id`
  (`game_id:global_turn:depth:seq`), per ADR 0003. Options are emitted in
  canonical order, per ADR 0004.
- **Until the ten human games are archived, only bit-identical work on this
  seam merges to `main`.** The seam, the legacy resolver, the telemetry and
  the registry fields (plan tasks 1–3) are gated on `base_game_bit_identity.py`
  staying identical and are safe to land. Any method that changes a choice
  (plan tasks 4–8) waits, or lives on a branch, until the study closes.
- The bundled fidelity fixes already in the task list (egg defects 1–3, card
  gaps 2–3) are built as resolver methods for `choose_egg_to_spend` and
  `choose_card_from_hand`, not as a third stand-alone guardrail.

## Why

- **It makes the choices visible before it makes them better.** The ledger,
  manifests and replay cannot currently see these decisions. Routing them
  through one seam with a frozen default puts them under the same arm
  discipline as everything else, at zero behaviour change.
- **Bit-identity by construction, not by care.** The legacy resolver is the
  existing code moved, not rewritten; the guard that already protects every
  other change protects this one.
- **One method, many handlers.** Nine kinds across sixteen handlers means a
  `choose_card_from_hand` method that knows about `Visionary Leader` fixes the
  discard in every handler that discards, and the action-list case, at once.
- **It is the smallest step that does not foreclose the right long-term
  shape.** The `PowerDecision` object is exactly what a pending-decision state
  machine (option C below) would park on the state, so C is a mechanical later
  move rather than a second redesign.
- **It respects the human study.** The study registration is the first time
  rule 1 has stopped work before compute was spent; this ADR keeps that
  intact by naming what may and may not land before game ten.

## Alternatives considered

| option | why not now |
|---|---|
| **A. Lift every choice into `LegalAction`** | Many options do not exist at action time (bonus cards drawn, the feeder after an earlier reroll). Enumerating them means enumerating chance outcomes or exposing hidden cards. `play_additional_bird` alone multiplies branching by birds × payments. Kept for choices that qualify (movers). |
| **C. Pending-decision state machine** (transition pauses on `state.pending_decision`; the choice is the next action — the OpenSpiel pattern) | The most faithful shape and the likely end state for the reusable template, but it rewrites `apply_action`, replay and every agent loop. Too large before the human games, and B is designed to convert to it. |
| **Fix each guardrail in place** | Produces a third guardrail with a third blind spot; leaves the choices invisible to arms and manifests; does not address the wrong-player cases. |
| **Do nothing until after the human games** | Tasks 1–3 are bit-identical and cost nothing against the study; deferring them only delays the behaviour-changing work that has to wait anyway. |

## Consequences

- `power_handler_registry.md` gains `decision_kinds` and `choice_fidelity`
  fields per entry; `hidden_power_choices.md`'s inventory becomes a printout
  of the registry rather than a hand count, and the 174 vs 180 powered-card
  discrepancy between the two docs is reconciled in the process.
- `docs/events/` gains `power_decision_resolved` v1. Event volume rises by one
  event per resolved choice; the 25-game smoke batch is the first measure.
- A 25-game batch with a non-legacy profile must replay bit-identically from
  its own events before any method arm is registered.
- The first behaviour-changing arm after the study is the mover destination
  (plan task 4), measured first as a counterfactual on archived states
  (`analysis/play_counterfactuals.py`) before any games are spent.

## What would cause this decision to be revisited

- A lifted decision (movers) shows the top-level search needs to branch on
  sub-choices more broadly than a root-level G or S resolver approximates —
  that is the signal to move to C.
- A second game for the reusable template needs pending-decision state for
  its own rules (Agricola-style multi-step actions), in which case C is built
  for the template and Wingspan migrates onto it.
- Finding A or B in `power_decision_methods.md` fails Alex's rulebook check,
  which changes the count of decision kinds or which handlers raise
  `activate_optional_power`, but not the seam itself.
- The bit-identity guard fails on task 1. That is a defect in the legacy
  resolver, not a reason to accept drift; the fix is to the resolver.

## Build order

The nine one- or two-day tasks with success criteria are in
`docs/architecture/power_decision_methods.md` §Build order and are not
repeated here. Tasks 1–3 may land during the human study; tasks 4–9 may not.
