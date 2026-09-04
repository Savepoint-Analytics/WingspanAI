# ADR 0002: Keep the first player deterministic and counterbalance seats

- Status: accepted
- Date: 2026-08-31
- Deciders: Alex Oswald

(ADR 0001 is reserved for `0001-separate-wingspan-ai-from-savepoint.md`, still pending.)

## Context

The simulator does not randomize the first player. `setup_base_game` uses its
seeded RNG for exactly three things — shuffling the bird deck, the bonus deck,
and the round goals, plus the opening birdfeeder roll — and then returns a state
carrying `RoundState()` with its default `active_player_index = 0`
(`state/models.py`). Verified across 50 seeds at three players: the starting
index is always `0`.

Seat assignment follows from agent list order. `run_single_game` builds
`player_ids = [f"player_{index + 1}" ...]`, so the first-listed agent is always
`player_1` and always takes the first turn of the game.

Between rounds the first-player token rotates deterministically
(`base_game.py`): `active_player_index = completed_round % len(players)`. For two
players that means rounds 1 and 3 start with seat one, rounds 2 and 4 with seat
two. That rotation is rule-faithful. What is missing relative to physical
Wingspan is the *random initial* holder of the first-player token.

The consequence is that seat is a **systematic** rather than a random factor. An
agent that benefits from acting first in the odd rounds receives that benefit in
100% of games rather than about 50%. The 2026-08-31 round robin measured the
result directly: seven of twenty matchups were pure seat artifacts, three of them
reading 0.000 win rate in seat one and 1.000 in seat two.

## Decision

Keep setup deterministic. Do **not** randomize the first-player token.

Instead, counterbalance seats: every lineup is replayed once per seat rotation so
each agent occupies each seat exactly once per seed. `flows/round_robin.py`
always emits all `player_count` rotations and offers no parameter to run a
partial set.

Seat effects are measured rather than discarded. `summarize_seat_effect` and the
`v_seat_effect` / `v_seat_effect_magnitude` SQL views report win rate and average
score per seat index, plus the spread between best and worst seat.

## Alternatives considered

**Randomize the initial token from the seed.** More rule-faithful, and it would
make seat a genuinely random factor. Rejected for two reasons. First, it changes
every stochastic draw, invalidating existing replay hashes and stored artifacts —
the same blast radius as the `batch_id`/RNG namespace issue, which is unresolved.
Second, and more importantly, randomizing only *averages over* seat variance,
whereas counterbalancing *removes* it. Paired seat-rotated seeds are a stronger
design than independent randomization at the same sample size.

**Leave it deterministic and ignore seats.** Rejected: this is what produced the
misleading pre-2026-08-31 comparisons, where `RandomLegalAgent` was hardcoded to
`player_1` in every batch.

## Consequences

- Any comparison run outside `flows/round_robin.py` must counterbalance seats
  itself, or its result is confounded with turn order.
- A matchup is only strategy signal when it holds in every seat. Summaries expose
  this as `seat_robust`; non-robust rows should not be quoted as findings.
- Cell count scales with `player_count`: a lineup costs `player_count` runs
  rather than one. At five players that is 5x the games per lineup.
- The simulator remains a faithful model of Wingspan's *round-to-round* token
  rotation but an intentional simplification of its *setup*. This must be stated
  in any public write-up.

## Standing research question this enables

Does turn order matter, at which player counts, and by how much?

Because seat effect is now measured per seat index and per player count, and the
round robin accepts any `player_count` from 2 to 5, this is answerable by running
the same roster at several player counts and reading `win_rate_spread` and
`avg_score_spread` from `summarize_seat_effect`, or `v_seat_effect_magnitude` in
SQL. See `docs/experiments/seat_order_study_plan.md` for the experiment design.

## Revisit if

- The project needs to model physical setup exactly for a published claim.
- The RNG namespace is separated from `game_id`, making a seeding change cheap.
- Counterbalancing cost becomes prohibitive at five players, in which case a
  Latin-square subset rather than full rotation may be warranted.
