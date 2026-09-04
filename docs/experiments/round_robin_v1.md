# Round Robin v1: First Agent-vs-Agent Comparison

Status: SUPERSEDED by `round_robin_v2.md`, 2026-09-01

> **PROVISIONAL — re-run required, 2026-08-31.** This run predates the fix in
> ADR 0004. The simulator was nondeterministic across Python processes:
> `BirdCard.habitats` is a `set[Habitat]` over a `StrEnum`, and Python randomizes
> string hashing per process, so the **order** of generated legal actions varied
> between runs. Agents that select by index or break ties by first-maximum
> therefore played different games. Each cell here ran inside a single process, so
> within-cell comparisons were internally consistent, but the results are not
> reproducible and should not be quoted until re-run on the fixed simulator.
>
> The headline (potential-points leads, seat-robust in every matchup) may well
> survive; it has not yet been re-verified. The archetype findings in section 3
> have since been acted on and fixed — see `../agents/archetype_policy_fix.md`.

## Purpose

Every prior strategy comparison in this project ran one agent against
`RandomLegalAgent`. That measures whether a policy beats noise, not whether it
beats another policy, and it leaves first-player advantage confounded with agent
strength. This run fixes both and treats opening setup as an explicit factor
rather than background noise.

## Setup

- Flow: `flows/round_robin.py`.
- Roster: `greedy_immediate`, `potential_points`, `net_value_response`,
  `archetype_engine_builder`, `archetype_bonus_card_focus`.
- Seeds 1-5, every unordered pair, **both seat orders**.
- Setup-policy factor: `control` (every agent on `default_setup_v1`) and
  `strategic` (every agent on its strongest matching opening policy).
- 40 cells, **200 games**, all replay-validated (0 invalid).
- Catalog: full 180-bird workbook deck at **100% power coverage**.
- Single shared `batch_id="rr_v1"`, so every cell saw identical deck order,
  birdfeeder rolls, and setup deals per seed.

```python
run_round_robin(
    seeds=[1, 2, 3, 4, 5],
    roster=["greedy_immediate", "potential_points", "net_value_response",
            "archetype_engine_builder", "archetype_bonus_card_focus"],
    setup_policy_kinds=["control", "strategic"],
    batch_label="round_robin_v1", batch_id="rr_v1",
)
```

## Standings

| Agent | Games | Win rate | Avg score |
|---|---:|---:|---:|
| `potential_points` | 80 | **0.756** | 58.45 |
| `greedy_immediate` | 80 | 0.506 | 45.30 |
| `archetype_bonus_card_focus` | 80 | 0.412 | 44.83 |
| `archetype_engine_builder` | 80 | 0.412 | 44.62 |
| `net_value_response` | 80 | 0.412 | 43.12 |

## Findings

### 1. `potential_points` leads, and the lead is seat-robust

It wins every matchup it plays, in both seat orders, under both setup levels:
+15.5 and +15.2 average margin against the two archetypes, +11.4 against
net-value, +19.0 against immediate greedy under control. This is the first
result in the project where a strategy ordering survives seat swapping.

Its action mix explains the gap: it is the only agent converting resources into
played birds at a healthy rate (21.8-23.1% of actions are `play_bird` versus
13.3-13.9% for greedy and the archetypes).

### 2. Seven of 20 matchups were pure seat artifacts

Without seat swapping these would have read as decisive results:

| Matchup (control) | A as seat 1 | A as seat 2 | Reported win rate |
|---|---:|---:|---:|
| `greedy_immediate` vs `archetype_bonus_card_focus` | 0.000 | 1.000 | 0.500 |
| `greedy_immediate` vs `archetype_engine_builder` | 0.000 | 1.000 | 0.500 |
| `archetype_engine_builder` vs `archetype_bonus_card_focus` | 0.200 | 0.800 | 0.500 |

Whoever sat second won, every time. Overall seat-two win rate was 0.537 versus
0.463 for seat one — a modest aggregate effect that hides much larger per-matchup
swings. **Only the 13 seat-robust rows should be read as strategy signal.**

### 3. The two archetypes are behaviourally indistinguishable

`archetype_engine_builder` and `archetype_bonus_card_focus` post identical win
rates in every single matchup (0.500/0.500, 0.700/0.700, 0.900/0.900,
0.250/0.250, 0.650/0.650) and near-identical action mixes:

| Agent | draw | food | eggs | play |
|---|---:|---:|---:|---:|
| `archetype_engine_builder` | 18.8% | 48.5% | 18.8% | 13.9% |
| `archetype_bonus_card_focus` | 17.4% | 50.0% | 18.8% | 13.8% |

This contradicts the project's stated success criterion that each archetype
should have a measurable behavioural signature in telemetry. Both spend roughly
half their actions gaining food and only ~14% playing birds. The archetype bots
are not currently implementing distinct strategies — they are variations on a
food-hoarding baseline.

### 4. `net_value_response` is the weakest agent, and it over-draws

It finishes last (0.412 win rate, 43.12 average score) and spends **44-46% of its
actions drawing cards** — roughly double any other agent. Cards it draws are not
converting into played birds (16.0-16.5% `play_bird`). The margin-aware
evaluation appears to overvalue hand size relative to board conversion.

This is worth reading alongside the belief-model work: improving opponent-response
prediction does not help if the agent's own value function misprices its actions.

### 5. The setup-policy effect table cannot be read as an absolute effect

| Agent | Control win rate | Strategic win rate | Difference |
|---|---:|---:|---:|
| `greedy_immediate` | 0.388 | 0.625 | +0.237 |
| `archetype_bonus_card_focus` | 0.350 | 0.475 | +0.125 |
| `archetype_engine_builder` | 0.350 | 0.475 | +0.125 |
| `net_value_response` | 0.525 | 0.300 | -0.225 |
| `potential_points` | 0.887 | 0.625 | -0.263 |

**These differences sum to approximately zero, because they must.** Within a
setup level every agent in the pool uses that level, so win rates are zero-sum
across the roster. The table therefore says only that strategic openings help
greedy and the archetypes *relative to* potential-points and net-value. It does
**not** show that strategic openings are bad in absolute terms for
`potential_points`.

Answering the absolute question needs a different design: cross setup policy
*per agent* (agent A strategic against agent B control) rather than applying one
level to the whole pool. That is the correct follow-up, and it is a design
limitation of this run rather than a result.

## Caveats

- 10 games per matchup cell (5 seeds x 2 seat orders). Small.
- Two-player games only.
- All power handlers are `heuristic_resolution`; choice-heavy powers use
  deterministic heuristics rather than agent decisions.
- Monte Carlo and guardrailed variants were excluded for compute reasons
  (~3 games/minute at this roster size).

## Follow-up

- [ ] Re-run the setup-policy factor per-agent rather than pool-wide, so the
      absolute effect of strategic openings is identifiable.
- [ ] Investigate why the archetype bots converge on the same food-heavy policy;
      they should not be producing identical win rates.
- [ ] Diagnose `net_value_response` card over-draw: likely hand-size
      overvaluation in the potential term rather than the opponent model.
- [ ] Extend to 30+ seeds and treat only `seat_robust` orderings as findings.
- [ ] Add Monte Carlo and guardrailed variants once compute budget allows.
