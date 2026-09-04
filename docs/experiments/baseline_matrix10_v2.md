# Baseline Matrix v2 (10 seeds, corrected simulator)

Status: superseding result, 2026-08-31

Supersedes `potential_points_matrix10_smoke.md`, which is retained only as a
record of the pre-correction state.

## What changed since v1

Four corrections landed between the two runs, all of which affect the numbers:

1. **Cross-process determinism (ADR 0004).** `card.habitats` is a `set[Habitat]`
   over a `StrEnum`, so legal-action ordering varied with Python's per-process
   string-hash randomization. v1 is not reproducible.
2. **`random_seed` is the sole reproducibility key (ADR 0003).** `game_id` no
   longer perturbs mid-game rolls, so separate batches are seed-matched. v1's
   variants ran as separate batches and were therefore **not** seed-matched
   despite the "seeds 1-10" label.
3. **Power coverage 71.8% → 100%**, including five opponent-affecting powers
   that previously resolved as pure self-benefit.
4. **Archetype policy repair.** Three bugs fixed; see
   `../agents/archetype_policy_fix.md`.

## Setup

- Seeds 1-10, player one `random_legal`, player two the listed variant.
- Full 180-bird workbook deck, 100% power coverage.
- Replay validation passed on all 130 games.
- Ties split as half a win.

## Results

| Player-two variant | Wins /10 | Avg score | Avg margin | v1 wins | Δ |
|---|---:|---:|---:|---:|---:|
| `guardrailed_greedy` | **10.0** | 58.4 | +26.5 | 10.0 | 0.0 |
| `guardrailed_potential` | **10.0** | 58.0 | +23.9 | 9.0 | +1.0 |
| `archetype_card_draw` | **10.0** | 52.2 | +18.6 | 0.0 | **+10.0** |
| `monte_carlo_rollout` | **10.0** | 56.8 | +22.6 | 9.0 | +1.0 |
| `potential_points` | 9.0 | **62.8** | **+26.6** | 10.0 | −1.0 |
| `archetype_food_acceleration` | 8.5 | 45.7 | +11.8 | 0.0 | **+8.5** |
| `archetype_egg_focus` | 8.0 | 49.5 | +15.8 | 5.5 | +2.5 |
| `archetype_engine_builder` | 8.0 | 53.3 | +19.4 | 8.0 | 0.0 |
| `archetype_round_goal_chase` | 8.0 | 47.4 | +15.0 | 8.0 | 0.0 |
| `net_value_response` | 8.0 | 44.2 | +9.6 | n/a | n/a |
| `archetype_bonus_card_focus` | 6.0 | 44.2 | +6.8 | 9.0 | −3.0 |
| `greedy_immediate` | 5.0 | 43.6 | +10.0 | 7.0 | −2.0 |
| `random_legal` | 3.5 | 31.3 | −4.3 | 5.0 | −1.5 |

## Findings

### 1. `potential_points` keeps the highest score and margin

62.8 average and +26.6 margin, both the best in the matrix, on 9/10 wins. The
central claim from v1 survives the corrections. It is no longer alone at 10/10 —
four variants now reach that — but it converts most efficiently.

### 2. The two repaired archetypes are the largest swings

`archetype_card_draw` moved from 0.0/10 (−37.0 margin) to 10.0/10 (+18.6), and
`archetype_food_acceleration` from 0.0/10 (−20.8) to 8.5/10 (+11.8). Both were
degenerate accumulation loops that never converted resources into points; adding
diminishing returns made them viable. This is the clearest confirmation that the
v1 archetype rows measured a bug rather than a strategy.

### 3. Guardrails are worth more than v1 suggested

`guardrailed_greedy` reaches 10.0/10 (+26.5) against plain greedy's 5.0/10
(+10.0) — a far larger lift than v1's 10.0 versus 7.0. Guardrails also no longer
hurt potential-points: `guardrailed_potential` is 10.0/10 versus 9.0/10
unguarded, reversing v1's finding that the shared guardrail config degraded it.

### 4. `random_legal` loses to itself as player two

3.5/10 with a −4.3 margin in a mirror matchup. Two contributors, not yet
separated:
- **Seat effect.** Seat one may be genuinely advantaged; the seat-order study
  measures this directly.
- **Shared agent seed.** `flows/simulation_batch.py` gives both seats
  `random_seed=random_seed`, so mirror matchups start with identically seeded
  RNGs and make correlated early choices. This is a known open issue.

Do not read the mirror row as a seat estimate until the agent-seed issue is
fixed.

### 5. `net_value_response` remains mid-table

8.0/10 with the second-lowest margin (+9.6) among non-random variants, matching
the round robin's finding that it under-converts. Its card over-draw diagnosis
still stands.

## Caveats

- 10 seeds, one opponent type (`random_legal`), two players only. Beating a
  random opponent is a low bar; nine of thirteen variants clear 8/10.
- These are agent-vs-random results. For agent-vs-agent ordering see the round
  robin, which needs re-running post-ADR-0004.
- Every power handler is `heuristic_resolution`; choice-heavy powers use
  deterministic heuristics rather than agent decisions.

## Follow-up

- [ ] Re-run `round_robin_v1` on the corrected simulator; it is the result that
      actually ranks agents against each other.
- [ ] Fix the shared per-seat agent seed, then re-measure the mirror row.
- [x] Diagnosed why `archetype_bonus_card_focus` fell from 9.0 to 6.0: a player
      holds one bonus card and 83% of hand cards match nothing against it, so the
      play-bird bonus (mean 5.14) barely exceeds the flat draw-cards bonus (5.00)
      and the agent draws more than it plays. The v1 agent scored well for the
      wrong reason — counting all tags made it an aggressive play-birds bot with a
      bonus-card label, scoring 0.0 bonus points. See
      `../agents/archetype_policy_fix.md`. A weight adjustment is proposed but
      deliberately not applied, since it would stale this matrix row.
