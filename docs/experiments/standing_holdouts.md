# Standing Holdouts: every decided arm stays alive at 5%

Status: mechanism generalized 2026-09-17 (`src/wingspan_ai/agents/holdout.py`).
The first holdout (search opponent model) dates from 2026-09-16.

## Why

An arm is adopted or dropped on one paired experiment, usually 80 games.
That is enough to act on and not enough to be sure of. Two failure modes
Alex named:

- **False positive.** A −4.5 that was really a −1 with bad luck is dropped
  forever, and nothing in the pipeline ever re-examines it.
- **Learning bias.** When agents start learning from past games, every
  archived game was played with the winning side of every decision. A
  learner then never sees the losing side and cannot tell the project it
  was wrong.

The rule: **every decided switch keeps its losing side running in a
deterministic minority of games, by default 5%.** Each decision becomes a
long-run A/B test with a guardrail instead of a one-shot verdict.

## Mechanism

```python
Holdout(field="mechanic_synergy", value=True, share=0.05)
```

`PotentialPointsSearchConfig.holdouts` is a tuple of these. Fields that
name an agent constructor argument are resolved by `resolve_effective`; the
one non-agent field, `setup_policy`, is resolved by the flow against the
opener the seat would otherwise use (`flows/simulation_batch.py::_make_agent`)
and recorded in the same manifest entry.
`resolve_effective(random_seed, lineup, lineup_position)` returns the
effective agent fields for one seat in one game plus the list of fields
that were held out; `flows/simulation_batch.py::_make_agent` builds the
agent from the effective fields and the manifest records both
(`games[].search_holdouts[agent_id] = {"effective": ..., "applied": ...}`).

Which games hold out is a SHA-256 draw over
`holdout:<field>:<seed>:<lineup>:<position>`, so:

- seed-matched arms hold out the same games and stay paired;
- both seat rotations hold out together, so the control subset is
  counterbalanced like everything else;
- each field draws independently. With `n` holdouts at 5%, about
  `1 − 0.95**n` of games deviate from the default somewhere (three holdouts:
  14%). Fine for an arm contrast, because the deviation is identical on both
  sides of every pair; it is not fine to grow without bound, which is why
  the registry below is short and holdouts that have accrued enough games
  to read should be retired (see "Retiring a holdout").
- a field whose default already equals the holdout value never draws, so a
  config that sets `search_child_expansion="copy"` explicitly is not
  "held out" from itself.

The opponent-model holdout keeps its original key
(`search_opponent_holdout:<seed>:<lineup>:<position>`) so the games it has
held out since 2026-09-16 are the same games in every later batch.

Passing `holdouts=()` disables every holdout for a batch. Use it for
probes where a deviating game would confuse the measurement (profiling
runs, bit-identity checks); leave the defaults on for every arm.

## Registry

| Field | Default | Held-out value | Share | Since | Decision it guards | Read with |
|---|---|---|---:|---|---|---|
| `search_opponent_model` | `belief` | `greedy` | 5% | 2026-09-16 | belief model +0.31 n.s. at −57% latency, adopted | `holdout_guardrail.py` |
| `mechanic_synergy` | `False` | `True` (board-only, weight 1.0) | 5% | 2026-09-17 | board-only synergy term +1.31 p=0.17, not adopted | `holdout_guardrail.py` |
| `search_child_expansion` | `fast` | `copy` | 5% | 2026-09-17 | fast child expansion bit-identical at −53% per child, adopted | `holdout_guardrail.py` |
| `setup_policy` (flow-resolved) | seat's opener (`default_setup_v1` in round robins) | `potential_points_setup_v3_keep3` | 5% | 2026-09-18 | measured opener −1.90 p=0.13, not adopted | `holdout_guardrail.py --field setup_policy` |

Decisions **not** guarded by a holdout, and why:

- Full synergy term (hand included), −4.5 at p=0.001: the board-only
  holdout covers the mechanism; the hand term's loss was large and its
  cause is understood (the agent keeps cards for the term).
- `expected_points` opener as a whole (`potential_points_setup_v2`), which
  lost the re-baseline −3.0: its bird selection is the known defect and the
  `setup_policy` holdout above covers the opener slot; a second opener
  holdout would double the deviating games for a decision already explained.
- The oracle-type opponent model (+0.24 n.s., 2026-09-18): a bound that
  reads the opponent's agent id, never a candidate default, so nothing was
  adopted or dropped; the opponent-model slot is already guarded by the
  greedy holdout.
- The 5 s decision budget (−2.0, p=0.047, 2026-09-18): a production knob,
  not a default; nothing changed for the batches, so no holdout until a
  budget becomes the shipped configuration (then the unbudgeted agent is
  the held-out side).
- Search depth, beam, K, food candidates: these are cost knobs priced by
  the ledger, not adopt/drop decisions. Their contrasts are re-run when the
  agent changes.

## Reading the guardrail

```bash
python analysis/holdout_guardrail.py artifacts/rr_belief_opp artifacts/rr_opener_v2 \
    artifacts/rr_synergy_board artifacts/bonus_keep
python analysis/holdout_guardrail.py artifacts/* --field search_child_expansion
```

The report pools every root, splits the `potential_points` seats by each
field's effective value, and prints the unpaired Welch contrast, the win
rate, the per-opponent split, and the **detection limit at 80% power**.
Under 40 held-out games it says so and refuses to be read as a finding. At
5% a standard 80-game arm contributes about 4–6 held-out games per field,
so a holdout takes roughly ten arms to become readable at the ±3-point
level. That is the design: the guardrail is cheap because it is slow.

State at 2026-09-17 for the opponent model (four roots, 320 games):
belief −1.34 versus greedy, p = 0.51, 19 held-out games — unreadable, as
expected, and pointing the way the arm said (no real difference).

## Retiring a holdout

When a field has accrued ≥ 100 held-out games and the guardrail agrees
with the original decision within its detection limit, remove the
`Holdout` from `DEFAULT_HOLDOUTS`, record the pooled result here, and
move the row to a "retired" table. If the guardrail disagrees, that is a
registered arm, not a silent revert: run the paired contrast again on the
current agent and decide on it.

## For the template

None of this is Wingspan-specific. `Holdout`, `holdout_draw` and
`resolve_holdouts` take a mapping of field values and a lineup; any agent
config for any game can carry a tuple of holdouts and any batch manifest
can record what was applied. The one convention worth keeping is the
key shape: field, seed, lineup, position, in that order, so that paired
designs stay paired.
