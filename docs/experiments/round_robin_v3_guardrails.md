# Round Robin v3: Guardrails as First-Class Competitors

Status: result, 2026-09-01

Extends `round_robin_v2.md` by adding guardrailed variants to the roster, so an
agent faces its own guardrailed twin head to head.

## Why

Guardrails were previously a seat-level batch setting, not a roster entry, so an
agent could never play against its own guardrailed version. The baseline matrix
suggested guardrails were worth about +5 wins per 10 to immediate greedy — large
enough to reorder the middle of the v2 table — but that was measured against a
random opponent and could not isolate the guardrail contribution.

`flows/simulation_batch.py` now accepts a `guardrailed:` roster prefix, e.g.
`guardrailed:potential_points`. The setup policy is applied to the base agent
before wrapping, because `GuardrailedAgent` delegates opening selection downward
and a policy set on the wrapper is never consulted.

## Setup

- Roster: `potential_points`, `guardrailed:potential_points`,
  `greedy_immediate`, `guardrailed:greedy_immediate`,
  `archetype_engine_builder`.
- Guardrail config: `configs/guardrails/base_heuristic.yaml`.
- 10 pairs x 2 seat rotations x 10 seeds = **200 games**, all replays valid.
- `control` setup, full counterbalancing, corrected simulator.

## Standings

| Agent | Win rate | 95% CI | Avg score | p vs chance |
|---|---:|---|---:|---:|
| `potential_points` | **0.656** | [0.547, 0.766] | 66.46 | **0.005** |
| `guardrailed:potential_points` | 0.581 | [0.472, 0.691] | 64.75 | 0.146 |
| `archetype_engine_builder` | 0.525 | [0.415, 0.635] | 58.67 | 0.655 |
| `guardrailed:greedy_immediate` | 0.512 | [0.403, 0.622] | 56.73 | 0.823 |
| `greedy_immediate` | **0.225** | [0.115, 0.335] | 46.36 | **<0.0001** |

## Findings

### 1. Guardrails rescue a weak policy, decisively

Head to head over 20 counterbalanced games, `guardrailed:greedy_immediate` beats
plain `greedy_immediate` **0.750** with a **+12.75** average margin (p = 0.025,
seat-robust). Across the whole table the guardrail layer lifts greedy from 0.225
to 0.512 win rate and from 46.36 to 56.73 average score — **+0.287 win rate,
+10.4 points**.

That moves greedy from clearly last to mid-table, level with the best archetype.

### 2. Guardrails do not help an already-strong policy

`guardrailed:potential_points` loses to plain `potential_points` head to head
(0.450, margin −3.90) and sits below it in the standings (0.581 versus 0.656,
−0.075 win rate, −1.7 points). Neither difference is significant (p = 0.655 head
to head), and the matchup is **not seat-robust**, so the honest reading is **no
detectable effect**, possibly slightly negative.

### 3. The asymmetry is the result

Guardrails are worth a great deal to immediate-score greedy and nothing
measurable to potential-points. The natural interpretation is that the guardrail
config encodes roughly the same knowledge potential-points already computes —
food deficits, egg capacity, hand size, early engine building — so it substitutes
for a missing value function rather than adding to a working one.

This reframes guardrails: they are a cheap way to make a weak policy competitive,
not a general improvement to stack on top of a good one.

### 4. `potential_points` remains the strongest agent

0.656, p = 0.005, still the only agent significantly above chance on the upside.
Its margin over the field narrowed from v2 (0.756) because the roster is now
harder — two of four opponents are guardrailed.

### 5. Seat effects are essentially absent

Win-rate spread 0.020, score spread **0.43 points**, against 1.96 in v2 and 1.82
in the seat-order study. Six of ten matchups are seat-robust; the four that are
not are all closely matched pairs (margins +0.00 to +5.15), which is where a seat
flip is expected.

## Caveats

- 20 games per matchup, 80 per agent. Only the two extremes reach significance;
  the three middle agents have overlapping CIs and are unranked among themselves.
- One guardrail config. `base_heuristic.yaml` was authored with immediate greedy
  in mind, which plausibly explains why it suits greedy and not potential-points.
  A config tuned for potential-points might behave differently.
- Chunk-level orderings were unstable: the guardrail effect on potential-points
  read −0.06, −0.375, +0.19, −0.31 and +0.03 across five 40-game chunks. Only the
  pooled result is meaningful.

## Follow-up

- [ ] Author a guardrail config tuned for potential-points rather than reusing
      the greedy-oriented one, and re-test.
- [ ] Add guardrailed archetypes to see whether the rescue effect generalizes to
      other weak policies.
- [ ] Raise to 30 seeds to separate the three middle agents.
