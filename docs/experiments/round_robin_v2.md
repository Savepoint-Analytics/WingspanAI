# Round Robin v2: Agent-vs-Agent on the Corrected Simulator

Status: result, 2026-09-01

Supersedes `round_robin_v1.md`, which was marked PROVISIONAL because it predated
the cross-process determinism fix.

## What changed since v1

| Correction | Effect on v1 |
|---|---|
| Cross-process determinism (ADR 0004) | v1's legal-action ordering varied per process; not reproducible |
| `random_seed` sole reproducibility key (ADR 0003) | v1 relied on a shared `batch_id` to stay seed-matched |
| Power coverage 71.8% → 100% | Five opponent-affecting powers previously resolved as self-benefit |
| Archetype policy repair | v1's archetype rows measured a bug (see `../agents/archetype_policy_fix.md`) |
| Per-seat agent RNG streams | Both seats previously shared one seed |

Design changes, all deliberate:

- **Seeds 1-10** instead of 1-5. v1's five-seed cells produced 0.000/1.000 seat
  readings that the seat-order study has since shown to be noise.
- **`control` setup only.** v1's setup-policy factor is zero-sum pool-wide and
  therefore not identifiable; holding setup constant gives a clean ranking.
- Same five-agent roster as v1, for direct comparability.

## Setup

- 10 unordered pairs x 2 seat rotations x 10 seeds = **200 games**.
- Full seat counterbalancing (ADR 0002); every agent plays every seat.
- Full 180-bird deck, 100% power coverage, all 200 replays valid.
- Run in five 2-seed chunks and pooled with `analysis/round_robin_aggregate.py`;
  `random_seed` independence (ADR 0003) makes chunks combinable.

## Standings

| Agent | Games | Win rate | 95% CI | Avg score | p vs chance |
|---|---:|---:|---:|---:|---:|
| `potential_points` | 80 | **0.756** | [0.647, 0.866] | **66.81** | **0.0000** |
| `archetype_engine_builder` | 80 | 0.550 | [0.440, 0.660] | 56.77 | 0.371 |
| `archetype_bonus_card_focus` | 80 | 0.487 | [0.378, 0.597] | 55.98 | 0.823 |
| `net_value_response` | 80 | 0.431 | [0.322, 0.541] | 50.86 | 0.219 |
| `greedy_immediate` | 80 | **0.275** | [0.165, 0.385] | 46.88 | **0.0001** |

## Findings

### 1. `potential_points` is the strongest agent, and it is now established

0.756 win rate, z = +4.58, p < 0.0001, with a 95% CI clear of chance. It wins
every matchup it plays, and all four are seat-robust: +12.4 against
bonus-card-focus, +10.6 against engine-builder, +15.9 against net-value, +17.2
against greedy.

Its v1 win rate was also 0.756 — identical. That is coincidence rather than
confirmation, since every other row moved, but the conclusion survives every
correction applied since.

### 2. `greedy_immediate` is the *weakest* agent, reversing v1

v1 placed it second at 0.506. It is now last at 0.275 (p = 0.0001). The change is
not subtle and has a clear cause: v1's archetypes were broken, collapsing into a
greedy-like fallback, so greedy was effectively competing against copies of
itself. With the archetypes repaired, immediate-score maximization is exposed as
the weak policy it is.

This is the single largest correction to the project's strategy picture.

### 3. The archetypes now separate

v1 had three agents tied at exactly 0.412. They now spread across 0.550, 0.487
and 0.431. The repair produced genuinely distinct policies rather than variants
of one food-hoarding baseline.

### 4. Seat effects have largely vanished

**9 of 10 matchups are seat-robust**, against 13 of 20 in v1. Aggregate seat
spread is 0.090 in win rate and 1.96 points in score, closely matching the
seat-order study's independent estimate of 1.82 points at two players.

Only `net_value_response` vs `archetype_engine_builder` remains non-robust
(0.700 in seat one, 0.150 in seat two), and it is also the closest matchup by
margin (-0.55), so a seat flip is what one would expect from an evenly matched
pair.

v1's dramatic seat artifacts — three matchups reading 0.000 against 1.000 — do
not reappear. They were small-sample noise compounded by the determinism bug, as
the seat study predicted.

### 5. `net_value_response` remains below average

0.431, fourth of five. Consistent with v1 and with the baseline matrix. Its
opponent-response modelling has improved (see the belief ablation) but its own
value function still misprices actions; the card over-draw diagnosis stands.

## Ranking against random is not ranking against agents

Comparing to `baseline_matrix10_v2.md`, where every variant faced `random_legal`:

| Agent | vs random (wins/10) | vs agents (win rate) |
|---|---:|---:|
| `potential_points` | 9.0 | 0.756 |
| `archetype_engine_builder` | 8.0 | 0.550 |
| `archetype_bonus_card_focus` | 6.0 | 0.487 |
| `net_value_response` | 8.0 | 0.431 |
| `greedy_immediate` | 5.0 | 0.275 |

The orderings differ. `net_value_response` beats random as often as
engine-builder (8.0 each) but is clearly worse head to head. Agent-vs-random
compresses the field because nine of thirteen variants clear 8/10; it cannot
separate the top of the table.

## Caveats

- 20 games per matchup. Only the extremes reach significance; the three middle
  agents have overlapping confidence intervals and should be treated as
  unranked among themselves.
- Two players, one setup policy, one ruleset.
- Monte Carlo and guardrailed variants excluded for compute (5.4 games/min with
  this roster).
- Chunk-level orderings were unstable below first place — `bonus_card_focus`
  ranged from 0.188 to 0.625 across 40-game chunks. Only the pooled result should
  be read.

## Follow-up

- [ ] Add guardrailed variants: guardrails were worth +5 wins/10 to greedy in the
      baseline matrix and may reorder the middle of this table.
- [ ] Cross setup policy *per agent* to make the opening effect identifiable.
- [ ] Raise to 30 seeds to separate the three middle agents.
- [ ] Re-test `bonus_card_focus` after the proposed weight adjustment.
