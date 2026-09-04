# Multiplayer Rule Audit (3-5 Players)

Status: verified against the core rulebook, 2026-08-31

Implementation: `src/wingspan_ai/rules/multiplayer_audit.py`
Tests: `tests/test_multiplayer_audit.py`
Audit ID: `multiplayer_rule_audit_v1`

## Why

Every rule in this simulator was written and regression-tested against the
two-player case. Two things are player-count sensitive and would silently
corrupt a multiplayer claim if wrong:

1. **Action cubes per round.** If the schedule varied by player count and the
   simulator assumed otherwise, every 3-5 player game would be the wrong length.
2. **End-of-round goal scoring.** The green side ranks players against each
   other, so tie-splitting, place-skipping, and the zero-item rule barely matter
   at two players and matter a great deal at three to five.

## Verdict

Both are **correct** as implemented. All 17 checks pass across player counts
2-5.

### Action cubes

Core rulebook page 5, "Round Structure":

> Round 1: 8 turns per player / Round 2: 7 turns per player /
> Round 3: 6 turns per player / Round 4: 5 turns per player

Stated once for a game billed "for 1-5 players", with no player-count qualifier.
`BASE_ACTION_CUBES_BY_ROUND = {1: 8, 2: 7, 3: 6, 4: 5}` matches, and correctly
does not vary with player count.

Note the schedule already accounts for the goal-marking cube: "Use 1 of your
action cubes to mark your score on the end-of-round goal. As a result, you will
have 1 fewer action cube to use each round."

### Green goal placement scores

Core rulebook page 11 and the goal board art:

| Place | R1 | R2 | R3 | R4 |
|---|---:|---:|---:|---:|
| 1st | 4 | 5 | 6 | 7 |
| 2nd | 1 | 2 | 3 | 4 |
| 3rd | 0 | 1 | 2 | 3 |
| 4th-5th | 0 | 0 | 0 | 0 |

`ROUND_GOAL_GREEN_SCORES` matches exactly, and carries five entries per round so
a five-player table can be ranked.

### Ranking behaviour

Three rules govern multiplayer ranking, all verified behaviourally rather than
by reading the constants:

**Ties pool and divide, and skip the next place.** Page 11:

> If players tie, place both cubes on the tied place, and do not award the next
> place. At game end, you will add the points for that place and the next
> place(s), then divide by the number of players who tied and round down.

The rulebook's worked example is encoded as a test: on a 5/2/1 goal, two players
tied for 1st each score `(5 + 2) // 2 = 3`, and 2nd place is not awarded, so the
third player takes 3rd place points. Verified: `[3, 3, 1]`.

**Zero items never place.** Page 11: "You must have at least 1 of the targeted
items to score points for a goal." Verified: a table of `[2, 0, 0, 0]` scores
`[7, 0, 0, 0]` — the empty-handed players do not inherit 2nd and 3rd.

**Only the top three places score.** A five-player table with strictly
descending counts scores `[7, 4, 3, 0, 0]`.

A fourth invariant is checked as a safety net: with every player tied, the pooled
places divide and round down, so the table can never award more than the round's
total points.

## How the audit is enforced

The audit is not advisory. It runs automatically and blocks bad multiplayer
batches:

- `audit_rule_coverage(catalog, player_count=N)` embeds the audit in every batch
  manifest under `rule_audits.multiplayer`.
- `flows/simulation_batch.py` raises `MultiplayerAuditError` before writing
  artifacts, persisting rows, or uploading, whenever a **3+ player** game runs
  against failing checks. Two-player batches are unaffected.
- `v_run_quality` labels a run `multiplayer_rules_unverified` — never
  `claim_grade` — when `player_count >= 3` and the audit did not pass.

Verified end to end by deliberately corrupting `BASE_ACTION_CUBES_BY_ROUND` to
`{1: 9, ...}`: the three-player batch was blocked with
`multiplayer rule audit failed ... action_cubes_by_round`, while the two-player
batch still ran.

Run it directly:

```python
from wingspan_ai.rules import audit_multiplayer_rules

audit = audit_multiplayer_rules()        # all player counts
audit = audit_multiplayer_rules(5)       # scoped to one table size
assert audit["publication_safe"]
```

## Supply limits: a gap that turned out not to exist

An earlier draft of this audit listed the unbounded egg and food supplies as
player-count-sensitive simplifications, on the reasoning that the core box ships
75 egg miniatures and five players could plausibly exceed that. **That was
wrong.** Core rulebook page 8 is explicit:

> **Managing egg tokens.** There is no limit to the egg supply. In the unlikely
> event that no eggs remain in the supply, use a temporary substitute.

And page 7 for food:

> In the unlikely event that any type of food token is unavailable in the supply,
> use a temporary substitute.

Component counts are convenience, not rules. The simulator's unbounded supply is
therefore **correct**, and capping it at box contents would be the deviation.
Both are now positive checks (`egg_supply_is_unlimited`, `food_supply_is_unlimited`)
rather than declared gaps.

### Egg miniature counts by box

Recorded in `EGG_MINIATURE_COUNTS` for provenance only:

| Box | Egg miniatures |
|---|---:|
| Core | 75 |
| European | +15 |
| Oceania | +15 |
| Asia | +30 |
| All combined | 135 |

Note that even the physical component count rises with expansion content, which
reinforces that 75 was never intended as a ceiling.

## Known simplifications

One real gap remains, declared in `KNOWN_SIMPLIFICATIONS`:

| ID | Sensitive from | Gap | Impact |
|---|---:|---|---|
| `green_goals_only` | 2 players | Only the competitive green goal side is implemented, not the blue 1-point-per-item side. | Player-count neutral in itself, but green goals are swingier at low counts and blue is the usual two-player recommendation. Results are conditional on the green ruleset. |

## Not covered by this audit

- Whether bird **powers** behave correctly with more than two opponents. The
  all-player and fewest-birds handlers were implemented and tested at two
  players on 2026-08-31; their multi-opponent behaviour is exercised but not
  separately asserted at 3-5 players.
- Solo (1 player) automa rules, which are a separate rules module and out of
  scope.
- Expansion content.
