# Seat Order Study Plan

Status: planned experiment, designed 2026-08-31. Not yet run.

## Research questions

1. **Does turn order matter?** Is a seat's win rate reliably different from its
   fair share (`1 / player_count`)?
2. **When does it matter?** Is the effect confined to two-player games, or does
   it persist at three, four, and five players? Does it grow or shrink with
   player count?
3. **By how much?** What is the size of the advantage, in win-rate points and in
   final-score points?
4. **Is it uniform?** Does seat advantage decay monotonically from seat one, or
   does the last seat gain something back from acting last in even rounds?

## Why the answer is not obvious

The simulator rotates the first-player token deterministically each round:
`active_player_index = completed_round % player_count`. Two structural effects
pull in opposite directions.

- **Round-count asymmetry.** With four rounds and two players, seat one starts
  rounds 1 and 3 and seat two starts rounds 2 and 4 — balanced. With three
  players, seat one starts rounds 1 and 4, seat two starts round 2, seat three
  starts round 3. Seat one starts twice as many rounds as anyone else. At five
  players, seats 1-4 each start one round and seat five starts none.
- **Shared-resource depletion.** Acting earlier in a round means first pick of
  the bird tray and the birdfeeder dice before opponents deplete them.

The prediction is therefore that **the seat effect should be largest at three
players and smallest at two**, which is the opposite of the intuition that
two-player games are the most order-sensitive. That is worth testing.

## Design

Fixed factors:

- Roster: a fixed set of agents, at least as large as the largest player count.
- Seeds: 30 minimum. At 3 games/minute this is the binding cost constraint.
- Setup policy: one level only (`control`), so setup is not confounded with seat.
- Content: full workbook deck at 100% power coverage, replay validation on.
- Seeds are matched automatically; `random_seed` is the sole reproducibility
  key (ADR 0003), so player counts can be added incrementally.

Varied factor:

- `player_count` in {2, 3, 4, 5}.

Seat counterbalancing is mandatory and automatic (ADR 0002): each lineup runs
once per rotation, so each agent occupies each seat exactly once per seed. This
is what separates a *seat* effect from an *agent* effect — without it the two are
inseparable.

### Cost

Games per player count = `C(roster, player_count) x player_count x seeds`.

With a 5-agent roster and 30 seeds:

| Players | Lineups | Rotations | Games | Approx. runtime |
|---:|---:|---:|---:|---|
| 2 | 10 | 2 | 600 | ~3.3 h |
| 3 | 10 | 3 | 900 | ~7.5 h |
| 4 | 5 | 4 | 600 | ~6.7 h |
| 5 | 1 | 5 | 150 | ~2.2 h |

Runtime assumes ~3 games/min at two players and scales with turn count
(52 turns at two players, 130 at five). Total is roughly a day of compute. Use a
cheap roster (`greedy_immediate`, archetypes) rather than `potential_points` or
`net_value_response` if the budget is tight — seat effect is a property of the
turn structure, not of agent sophistication, so weak agents are acceptable here
and arguably preferable because they add less policy variance.

### Commands

```python
from flows.round_robin import run_round_robin, format_round_robin_report

for player_count in (2, 3, 4, 5):
    summary = run_round_robin(
        seeds=list(range(1, 31)),
        roster=["greedy_immediate", "archetype_egg_focus", "archetype_engine_builder",
                "archetype_card_draw", "archetype_food_acceleration"],
        setup_policy_kinds=["control"],
        player_count=player_count,
        batch_label=f"seat_order_p{player_count}",
    )
    print(format_round_robin_report(summary))
```

In SQL, after `python analysis/apply_sql_views.py`:

```sql
select * from v_seat_effect_magnitude order by player_count;
select * from v_seat_effect where batch_label like 'seat_order%' order by player_count, seat_index;
```

## Metrics

Primary, from `summarize_seat_effect` / `v_seat_effect`:

- `win_rate` per seat versus `fair_share_win_rate`.
- `win_rate_spread` — best minus worst seat. **The headline magnitude.**
- `avg_score_spread` — the same in final-score points, which is easier to
  interpret strategically than win-rate points.
- `win_rate_vs_fair_share` per seat — direction and size of each seat's edge.

## Reading the result

- **Spread near zero at every player count** → turn order does not matter in the
  current rules encoding. Seat counterbalancing can then be relaxed to cut
  compute, though keeping it costs only correctness insurance.
- **Spread grows with player count** → order matters more in multiplayer, and
  every multiplayer result in the project needs counterbalancing.
- **Spread largest at three players** → confirms the round-start asymmetry
  hypothesis above, and points at the token-rotation rule rather than resource
  depletion as the dominant mechanism.
- **Seat one and seat N both above fair share** → two competing mechanisms, and
  the middle seats are the disadvantaged ones.

## Confounds to control

- **Agent strength.** Counterbalancing handles this within a lineup. Do not
  compare seat effects across rosters.
- **Setup policy.** Hold at `control`. Strategic openings interact with tray
  access, which is itself seat-dependent.
- **Seed matching.** Automatic since ADR 0003. Player counts can be run and
  compared independently.
- **Turn count.** A five-player game has 130 turns versus 52 at two players.
  Score levels are not comparable across player counts; only *within-count*
  seat spreads are.

## Machinery pilot (INVALID — superseded)

> The pilot below ran **before** the ADR 0004 determinism fix, so its numbers
> are not reproducible and are retained only as a record that the rotation
> machinery executed. Do not read anything into the spreads.

A 2-seed pilot was run on 2026-08-31 purely to confirm the rotation machinery
works end to end. Roster: `greedy_immediate`, `archetype_egg_focus`,
`archetype_card_draw`; `control` setup.

| Players | Games | Seat 1 | Seat 2 | Seat 3 | Win-rate spread | Score spread |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 12 | 0.500 | 0.500 | - | 0.000 | 2.84 |
| 3 | 6 | 0.500 | 0.333 | 0.167 | 0.333 | 1.17 |

**These numbers cannot support any conclusion and must not be quoted.** At three
players the sample is six games, so win-credit granularity is 1/6 = 0.167 and the
observed 0.500 / 0.333 / 0.167 pattern is exactly 3 / 2 / 1 wins — a shape that
arises readily by chance. The two-player 0.000 spread is likewise 6 wins out of
12.

What the pilot does establish: rotations are generated and applied correctly,
seat scores map back to lineup identity, per-seat aggregation works at both
player counts, and the summary reports a magnitude. It is a plumbing check, not a
result. The directional hint that three players shows more spread than two is
consistent with the round-start asymmetry hypothesis but is not evidence for it.

## Prerequisites

- [x] Simulator verified for 2-5 players (all replay-valid, 2026-08-31).
- [x] Cross-process determinism fixed (ADR 0004). This study measures small
      ordering-sensitive effects and would have been especially corrupted by
      the legal-action ordering bug.
- [x] Seat counterbalancing mandatory in the round-robin flow.
- [x] Seat-effect measurement per seat index and player count.
- [x] `v_seat_effect` and `v_seat_effect_magnitude` SQL views.
- [x] Multiplayer rules verified for 3-5 players and enforced as a batch gate
      (`docs/rules/multiplayer_rule_audit.md`). Batches of 3+ players now fail
      loudly rather than produce unverified multiplayer results.
- [x] `batch_id`/RNG namespace resolved: `game_id` removed from the seed string
      (ADR 0003), so seed matching is automatic and counts are independent.
- [ ] Confirm compute budget for roughly one day of simulation.
