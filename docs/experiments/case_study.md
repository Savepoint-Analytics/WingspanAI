# Wingspan AI: What Ten Points of Search Taught Us About Building Board-Game NPCs

Status: refreshed 2026-10-05; first full draft 2026-09-18.
Private research write-up; see `COMPANY_CONTEXT.md` before any public use.
Numbers are the ledger's; nothing here is a claim the ledger does not carry.
Where an instrument disagrees with an arm, both numbers are given.

## The problem

A board-game NPC has to make good decisions under three things at once:
hidden information (the opponent's hand, the deck), a constrained economy
(food, eggs, cards and actions are all scarce and convertible), and a
clock — a human at the table will not wait ten seconds for a bot's turn. The
research question was never "can an AI play Wingspan"; it was **which
kinds of reasoning are actually worth their cost in a game like this**, and
how to find that out in a way that does not fool the person doing the
finding.

Wingspan is a good testbed because it has every one of those properties in
a rulebook small enough to encode faithfully: four action types, three
habitats, 170 birds with powers, hidden bonus cards, four round goals, a
shared bird tray and food feeder that make opponents interact, and a final
score built from six categories.

## What was built

- A **rule-faithful, deterministic simulator** for the base game: every
  base-game bird power handled, replay validated by state hashes, bit-for-bit
  reproducible across processes from a single seed (ADRs 0003, 0004).
  "Handled" means every power resolves and none silently no-ops. It does **not**
  mean the agent chooses how: in 16 handlers covering 112 of the 180 powered
  birds, a decision the rules give the player is made by a fixed rule in the
  transition function, outside the search and outside anything an arm can
  measure (`docs/rules/hidden_power_choices.md`).
  **10,956 archived games**, every one replayable.
- **Telemetry** that makes a game inspectable: every decision records the
  candidate actions, the choice, the agent's own ranked valuation of up to
  eight candidates, a profile of where the milliseconds went, and since
  October a per-round score and engine-state snapshot.
- **An analysis layer**: object storage as the durable complete log, a
  PostgreSQL schema for querying, sixteen derived views and a reproducible
  KPI pass.
- **Agents** from random and greedy through scripted archetypes, a Monte
  Carlo rollout agent, a Bayesian opponent-response agent, to the champion:
  `potential_points`, an expected-value evaluator with a depth-3
  determinized search on every turn.
- **An experimental method** that turned out to be the main product: paired
  seed-matched arms, pre-registered predictions with stated power, a
  value-per-millisecond ledger, and standing 5% holdouts on every decided
  switch.

## What we found

### 1. One idea was worth ten points; nothing else was worth two

Over six weeks and fifty-four ledger rows, the record has exactly
one large positive result: **searching three own turns ahead on every
turn, over four samples of the hidden information, is worth +10.4 points
(p < 0.001)** against a one-ply evaluator. Every strength idea since —
a Bayesian opponent posterior inside the search, an oracle that knows the
opponent's type from turn one, a measured card-synergy term, a data-driven
opener, feeder-odds valuation, reroll chance nodes, a denial term, an
evaluator tie-break correction — landed between −5.9 and +1.3, and the only
significant ones were negative.

That is not a failure of the ideas; it is the shape of the game as played
by these agents. The evaluator already prices resources, playable birds,
bonus cards and round goals well enough that refining it moves the score
less than the noise of eighty games. Planning — looking at what the
resources become over the next three turns — is where the points were.

### 2. Four kinds of privileged information are each worth nothing

This is the project's strongest result, and it was built one null at a time.
Each row is a separate arm giving the agent information a real player could
not have:

| Privileged knowledge | Worth |
|---|---|
| the deck order and the opponent's hand | **−2.4 (p=0.008)** — actively harmful |
| the birdfeeder roll in advance | −0.3 (n.s.) |
| feeder odds priced into the evaluator | null three times over (+0.5, −0.1, +0.2) |
| **the opponent's type, perfectly, from turn one** | **+0.00 (p=1.000)** at 3p; +0.24 at 2p |

The last one is the ceiling of the whole opponent-modelling family, and it
measures exactly zero. Over 90 paired three-player games the differences
summed to **precisely zero**, with 7 of 15 decks positive. It is not that
the switch does nothing: 79 of the 90 games played out differently, with
per-game swings from −35 to +19. It changes the agent's decisions and does
not change its score.

Peeking at the deck is worse than useless because it overfits the plan to
one ordering; averaging over samples is better because the plan has to
survive several. And knowing *who you are playing* is worth nothing because,
at strong play, **Wingspan is very nearly a solitaire optimisation problem.**
Interaction is real but it runs through the shared board — the tray, the
birdfeeder, the round goals — not through anyone's plan. That is why a denial
term costs **−5.9** (it pays the agent to draw tray cards the opponent wants,
against a supply that refills), and why the one interaction term that pays is
the round-goal placement model, which reasons about the shared *scoring race*
rather than about an opponent's intentions.

A calibration finding fell out on the way: the posterior identifies the
opponent's *action mix*, not its *type*. The roster's purest value-maximizer
is classified as "food-focused", because the model's likelihoods are built
on public candidate values that rank actions differently from the agent's
real scoring. A belief model is only as good as the response model behind
it — and since the oracle bounds what any such model could win at zero,
that effort was closed rather than continued.

### 3. The policies form a strict pecking order, with no rock-paper-scissors

Mean score margin and outscored rate across 23,346 player-games:

| | vs greedy | vs net_value | vs bonus_focus | vs engine_builder |
|---|---|---|---|---|
| `potential_points` | **+32.2** (0.91) | +17.6 (0.82) | +15.0 (0.80) | +17.0 (0.86) |
| `engine_builder` | +22.5 (0.81) | +6.6 (0.69) | +1.1 (0.52) | — |
| `bonus_card_focus` | +10.4 (0.76) | +5.2 (0.63) | — | −1.1 (0.47) |
| `net_value_response` | +9.5 (0.68) | — | −5.2 (0.37) | −6.6 (0.29) |

All ten pairs are consistent with one ordering and **there is no intransitive
triple anywhere**: no archetype beats a stronger one by exploiting it. Two
details matter more than the ranking. The champion's edge is **roughly
constant** across the three mid agents (+15.0 to +17.6) rather than
opponent-specific — the same separability the opponent-model nulls show from
the other direction. And `engine_builder` versus `bonus_card_focus` is the
only near-tie in the matrix (+1.1, outscored rate 0.52 over 390
player-games), making it the one pair where a seed-paired arm might find a
real interaction.

These are population statistics over unbalanced lineups, not a tournament.
For contrasts, pair by seed.

### 4. Observed value is not causal value — three times now

Three times the project measured what something was worth by watching games,
and three times the measurement failed to transfer to a decision:

- **Card synergy.** A rules-computed bench and exact counterfactual play
  rollouts (K=4 continuations, lme4 shrinkage) produced a table of
  mechanic-pair effects. Fed into the evaluator, the table cost **−4.5
  points**; restricted to the board, **+1.3 (n.s.)**. Pair synergy in
  two-player base Wingspan is small next to card main effects, and it
  depends on who is pursuing it and whether the egg cap binds.
- **Bird value at setup.** The same counterfactual fit gives each bird a
  play value. Using it to choose the three opening birds cost **−1.9**
  against a rule that keeps the three cheapest: the play value is
  conditional on the bird having been played in context, and the cheap
  birds' tempo is what wins the opening.
- **Per-decision value.** 2,045 archived decisions where the agent's own top
  two candidates were within 0.2 points — natural randomised trials, since
  noise picked the winner. In the one subset that showed a signal, declining
  a birdfeeder reroll was worth **+2.40 a decision** (29 decisions,
  p=0.0005). The arm built to capture it returned **−0.39**, with a
  confidence interval excluding the +1.44 that effect predicted.

The third is the sharpest version of the lesson: **a per-decision effect is
not an estimate of a whole-game effect**, because any switch that captures it
also changes unrelated decisions. Use per-decision measurement to *find*
candidates; always budget the arm on whole-game variance.

The honest instrument throughout is a forced intervention. The bonus-card
forced-keep study *did* transfer — the choice is worth 6.4 points and a
better chooser recovered +0.85 of it.

### 5. The evaluator is right where it says it is indifferent

Those same 2,045 near-ties answer a question worth asking of any evaluator:
when it reports two options as equivalent, is it right?

Overall realized difference between the chosen branch and the runner-up:
**+0.062, 95% CI [−0.149, +0.273]**, entirely inside a pre-registered
−0.3 to +0.3 band. That is the strong form — a positive finding of
indifference, not a failure to reject. **A third of near-ties (33.6%) end in
exactly zero difference**: both branches converge on the same final score.
There is no free third of a point in tie-breaking, which closed evaluator
tie-break tuning as a direction.

### 6. Cost is where the engineering wins are

Once the profiler showed that 73% of a decision was copying the game
state and 19% was evaluating leaves, a series of changes followed, each read
for points and milliseconds:

| Change | Δ score | latency | verdict |
|---|---:|---:|---|
| Belief opponent model (vs greedy) | +0.3 n.s. | −57% | adopted |
| Fast child expansion (no re-validation, no audit trail) | 0.0, bit-identical | −50% | adopted |
| One sample instead of four | −2.0 | −80% | priced: ≈ 0.9 points per doubling of time |
| 5 s decision cap, ladder v1 (samples first) | −2.0 | −64% | dominated by K=1 alone |
| 5 s cap, ladder v2 (depth first, deadline abort) | −1.5 n.s. | −69% | cap still bound on 45% of decisions |
| beam pre-ranking (cheap score picks beam and leaves) | −0.72, then −0.96 on re-run | −62% | not the unbudgeted default |
| **pre-ranking + ladder v2 at 5 s** | **−0.6 n.s., win +0.04** | **−85%** | **production configuration** |

Depth buys about 1.7 points per doubling of thinking time, samples about
0.9. That single table is what a production budget needs: it says which
knob to turn first when the clock runs out, and it was unknowable without
paired arms that report both numbers.

### 7. Against itself: the first player wins

Four self-play arms put the champion in every seat. Three roster findings
survived a planning opponent unchanged: the opponent model is worth
nothing at two players (+0.5 n.s.) and about two at three (+1.9, p=0.07,
replicating the roster's +2.1); a denial term is a liability (−5.9); and the
generalist profile holds (75.3 at 2p, winners separating on round goals and
eggs).

One thing the roster had hidden: **the first player wins 61% of two-player
games between equal agents, by about six points** — +5.1 on seeds 1–40,
+7.2 on fresh seeds 41–80, pooled **+6.2 (p<0.001) over 80 independent
decks**. It is the largest structural effect in the project and it belongs to
the rules rather than to any agent.

Self-play also reframed how the roster numbers should be read. Against the
weak roster the champion wins by a mean of 24.8 points and only 13.8% of
games are decided by five or fewer. **Against an equal opponent the margin
halves to 12.4 and 30.3% of games are inside five points.** Outcome noise
from an identical position is about ±4.9 points, so against a peer the noise
is the same order as the deciding margin in roughly a third of games. Roster
win rates are therefore a poor measure of skill differences, and any
risk-aware refinement is capped by that ~30%.

### 8. What strong play looks like

The champion is a generalist: it scores 35.5 bird points, 13.7 round-goal
points and 12.6 egg points, and it does **not** chase its bonus card. Of the
birds it plays, 44% match the bonus card it kept — mid-table. The
`bonus_card_focus` archetype reaches 59.7% fulfilment and the highest bonus
score of any agent (6.0), and finishes **14 points behind overall**. That is
the engine-versus-objective tradeoff in two rows.

Round goals are the flattest category across agents: the greedy baseline
scores 83% of the champion's goal points while managing only 46% of its bird
points, because qualifying for a goal takes one bird. As a share of its own
score, greedy takes 25.3% from goals against the champion's 18.1%.

On bonus cards specifically, the archive now ranks all 26 base-game cards
over 262–908 games each. The spread in how often a kept card matches what
gets played is **sevenfold**, from 0.082 to 0.577. The weakest,
**Breeding Manager**, matches 0.68 birds a game against the best card's 3.79
— close to dead on arrival, and now a finding on 391 games rather than a
hypothesis on 25.

## The method, which is the transferable part

Four rules, each learned by getting something wrong first.

1. **Pair by seed and register the prediction.** Two early "findings" (a
   greedy agent ranked second; a seat-3 advantage at three players) were
   artefacts of unpaired comparisons and post-hoc reading. Since then every
   arm runs the same seeds as its baseline, from a clean worktree at a
   recorded commit, with a prediction written down before launch.
2. **A registration must state the detection limit its sample will have, and
   the band must be wider than that limit.** Three arms in September
   registered bands their samples could not resolve, which guarantees an
   uninterpretable result whatever comes back. Per-game score SD is 9–11
   points at two players, so an 80-game paired arm resolves about ±3 points
   and nothing finer; ±1 needs ~860 games. If the band cannot clear the
   limit, do not launch — decide on cost or mechanism and say so.
3. **A re-read of existing data never changes a verdict; it only nominates a
   question for a fresh pre-registered arm.** An audit re-read every row by
   deck and on holdout-free games, and two rows changed enough to reopen a
   closed question. Both were then tested properly and **both reverted**. The
   audit's corrections to *method* were real and were kept; its re-ranked
   *results* were hypotheses from ~95 unadjusted re-reads.
4. **Value per millisecond.** Every calculation an agent does is kept only
   if its measured gain justifies its measured latency. A decision-tree
   profiler (game-agnostic; three lines to instrument a node) and a report
   that prices arms in points per second turned "is it faster" into a
   number on the same row as "is it better".

Alongside these, **standing holdouts**: every adopted or dropped switch keeps
its losing side alive in a deterministic 5% of games, keyed so paired designs
stay paired. A false positive at n=80 gets re-examined for free, and an agent
that later learns from the archive can never be trained only on the winning
side of every decision.

None of these is specific to Wingspan; nor is the simulator's split into
content, rules, state, legal actions, transition, scoring, policy, belief,
telemetry and orchestration. The template for the next game is the set of
interfaces those rules were enforced through.

## The data-integrity failure, and why it is in the write-up

For six weeks the analysis database silently held **44.5% fewer games than
the archive**. Every simulated game got an identifier built from its batch
and its deck, which omitted the lineup and the seat rotation — so four
different matchups on the same deck in the same batch all received the *same*
identifier, and a primary key on it discarded all but one. 10,831 archived
games collapsed to 6,014 rows.

The loss was not random. Which game survived depended on object listing
order, so the champion's own matchups — which sort late alphabetically — were
discarded most. The database reported the champion playing 463 player-games
when it had played 6,020, and from that unrepresentative 7% it reported a
**95% win rate at 88.3 points**. The truth is **73% at 75.6**.

Two things found it, and both are worth copying:

- **Cross-checking against an instrument with a different data path.** The
  paired-arm reader works from local artifacts keyed on
  (lineup, rotation, seed, ruleset) and never touched the broken identifier.
  It independently puts the champion at 75.3 in self-play. The corrected
  database says 75.6. The old 88.3 agreed with nothing — and *that
  disagreement was visible in September and was not acted on.*
- **Keeping the durable log separate from the queryable one.** Object storage
  held every game all along, so the fix was a re-key and a reload rather than
  a re-simulation.

No experimental result was affected: the arms read local artifacts and never
used that identifier. But a repaired database is not the point. The point is
that a measurement pipeline can be wrong by a factor of two in a direction
that *flatters the thing you are building*, and the only defences are an
independent instrument and the discipline to investigate a disagreement when
you see one.

## Limitations

- **Strength is relative to this roster and to self-play.** No human has
  played against the agent. Since the headline result is that modelling the
  opponent is worth nothing, and no opponent in any lineup has ever blocked
  or contested a telegraphed bonus card, a human is the obvious falsifier and
  that study has not been run.
- **The placement round-goal model's size is disputed.** Two paired arms put
  it at +1.12 (25 decks, deck-clustered p=0.097) and +0.41; the standing
  holdout guardrail, randomised but unpaired, puts it at **+7.64 (p<0.001)**
  on 71 held-out games. A sevenfold disagreement is unresolved and is
  recorded as a nomination, not averaged. The leading explanation is that the
  guardrail's held-out set is a *fixed* subset of decks rather than a fresh
  draw.
- **The +1.12 confirmation is itself fragile.** It met its registered
  criterion, but removing any of 14 of the 25 decks pushes it back above the
  threshold, the sign test on 16/25 positive decks is p=0.230, and a 20%
  trimmed mean is +0.85. The defensible effect is +0.8 to +1.1.
- **Several 2p arms sample only 10 decks** (10 seeds × 4 opponents × 2
  rotations), so their deck-clustered reads are weak even where the naive
  ones look strong.
- Base game only; no expansions, no automa.
- Latencies are from a shared laptop; ratios are trustworthy, absolutes
  are not.
- Per-round score snapshots began in October, so trajectory analysis applies
  to future games; the 10,956 archived games carry final scores only.
- IP: Wingspan content and rules are used as research inputs for a private
  case study; public release needs review (`COMPANY_CONTEXT.md`).

## What is next

The production question — how much strength survives a five-second clock —
is answered: essentially all of it, once the search is pre-ranked. The
opponent-modelling question is answered and closed at both player counts.

Three things remain, in order of what they would teach:

1. **Ten human games.** The only available falsifier of the headline finding.
   If "the opponent barely matters" survives a human who blocks and contests,
   it is a property of the game; if it does not, that is the better result.
2. **Resolve the placement-model disagreement.** Cheap: the held-out deck set
   is computable without running anything, so its composition can be compared
   to the rest directly.
3. **The European expansion**, as the first real test of whether the
   content-pack and rules-module boundaries generalise — the claim the
   reusable-template section rests on and which nothing has yet stressed.
