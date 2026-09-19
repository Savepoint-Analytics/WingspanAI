# Wingspan AI: What Ten Points of Search Taught Us About Building Board-Game NPCs

Status: first full draft, 2026-09-18, written from `results_ledger.md`.
Private research write-up; see `COMPANY_CONTEXT.md` before any public use.
Numbers are the ledger's; nothing here is a claim the ledger does not carry.

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
  ~8,000 archived games, every one replayable.
- **Telemetry** that makes a game inspectable: every decision records the
  candidates, the choice, the agent's own valuation of it, and since
  September a profile of where the milliseconds went.
- **Agents** from random and greedy through scripted archetypes, a Monte
  Carlo rollout agent, a Bayesian opponent-response agent, to the champion:
  `potential_points`, an expected-value evaluator with a depth-3
  determinized search on every turn.
- **An experimental method** that turned out to be the main product: paired
  seed-matched arms, pre-registered predictions, a value-per-millisecond
  ledger, and standing 5% holdouts on every decided switch.

## What we found

### 1. One idea was worth ten points; nothing else was worth two

Over three weeks and roughly twenty registered arms, the ledger has exactly
one large positive result: **searching three own turns ahead on every
turn, over four samples of the hidden information, is worth +10.4 points
(p < 0.001)** against a one-ply evaluator. Every strength idea since —
a Bayesian opponent posterior inside the search, an oracle that knows the
opponent's type from turn one, a measured card-synergy term, a data-driven
opener, feeder-odds valuation, reroll chance nodes — landed between −4.5
and +1.3, and the only significant ones were negative.

That is not a failure of the ideas; it is the shape of the game as played
by these agents. The evaluator already prices resources, playable birds,
bonus cards and round goals well enough that refining it moves the score
less than the noise of eighty games. Planning — looking at what the
resources become over the next three turns — is where the points were.

### 2. The opponent barely matters at two players

The Bayesian opponent model was the project's headline research direction.
It works as designed: the posterior over opponent type concentrates within
a game and predicts the opponent's action family well. Inside the search
it is worth **+0.3 points (n.s.)** over the greedy model it replaced, and
handing the search *perfect* type knowledge (the oracle arm) is worth
**+0.2**. Three opponent models within ±0.3 of each other: at two players
the champion's own plan is robust to what the imagined opponent does. The
belief model was kept anyway — it halved the decision cost. The question is
now being asked at three players, where the seat-order study found real
interaction.

A calibration finding fell out on the way: the posterior identifies the
opponent's *action mix*, not its *type*. The roster's purest value-maximizer
is classified as "food-focused", because the model's likelihoods are built
on public candidate values that rank actions differently from the agent's
real scoring. A belief model is only as good as the response model behind
it, and that is where the next modelling effort would go if the 3p study
says it matters.

### 3. Observed value is not causal value

Twice the project measured what a card or a pair of cards was worth by
watching games, and twice the measurement failed to transfer to a decision:

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

The lesson generalises beyond this game: a value estimated where a policy
chose to act is not the value of choosing that act somewhere else. Forced
interventions (the bonus-card forced-keep study, which *did* transfer:
the choice is worth 6.4 points and a better chooser recovered +0.85 of it)
are the honest instrument.

### 4. Cost is where the engineering wins are

Once the profiler showed that 73% of a decision was copying the game
state and 19% was evaluating leaves, three changes followed, each read for
points and milliseconds:

| Change | Δ score | latency | verdict |
|---|---:|---:|---|
| Belief opponent model (vs greedy) | +0.3 n.s. | −57% | adopted |
| Fast child expansion (no re-validation, no audit trail) | 0.0, bit-identical | −50% | adopted |
| One sample instead of four | −2.0 | −80% | priced: ≈ 0.9 points per doubling of time |
| 5 s decision cap, ladder v1 (samples first) | −2.0 | −64% | dominated by K=1 alone |
| 5 s cap, ladder v2 (depth first, deadline abort) | −1.5 n.s. | −69% | cap still bound on 45% of decisions |
| beam pre-ranking (cheap score picks beam and leaves) | −0.7 n.s. | −58% | the lever that unbinds the cap |
| **pre-ranking + ladder v2 at 5 s** | **−0.6 n.s., win +0.04** | **−85%** | **production configuration** |

Depth buys about 1.7 points per doubling of thinking time, samples about
0.9. That single table is what a production budget needs: it says which
knob to turn first when the clock runs out, and it was unknowable without
paired arms that report both numbers.

### 5. How the agent stands

Against a roster of scripted archetypes, a greedy baseline and the
Bayesian response agent, the champion wins **87.5% of two-player games at
a +22-point margin** (78.4 vs 56.1), thinking 7.6 s a decision. In its
production configuration — pre-ranked search under a five-second cap — it
wins **92% at +21, thinking 1.1 s a decision** (p95 under 4.2 s in every
round), a difference from the unbudgeted agent inside the noise. At three
players it wins 76% with the belief opponent model and 83% with the
greedy one; the opponent model starts to matter there. Against an opponent as strong
as itself, the margin model (Φ(margin/20)) says each point of mean score is
worth about two win-rate points — the number that makes the cost work
matter.

## The method, which is the transferable part

Three rules, each learned by getting something wrong first:

1. **Pair by seed and register the prediction.** Two early "findings" (a
   greedy agent ranked second; a seat-3 advantage at three players) were
   artefacts of unpaired comparisons and post-hoc reading. Since then every
   arm runs the same seeds as its baseline, from a clean worktree at a
   recorded commit, with a prediction written down before launch. The
   80-game design resolves ~1.9 points; anything inside that is reported as
   inside that.
2. **Value per millisecond.** Every calculation an agent does is kept only
   if its measured gain justifies its measured latency. A decision-tree
   profiler (game-agnostic; three lines to instrument a node) and a report
   that prices arms in points per second turned "is it faster" into a
   number on the same row as "is it better".
3. **Standing holdouts.** Every adopted or dropped switch keeps its losing
   side alive in a deterministic 5% of games, keyed so that paired designs
   stay paired. A false positive at n=80 gets re-examined for free, and an
   agent that later learns from the archive can never be trained only on
   the winning side of every decision.

None of these is specific to Wingspan; nor is the simulator's split into
content, rules, state, legal actions, transition, scoring, policy, belief,
telemetry and orchestration. The template for the next game is the set of
interfaces those rules were enforced through.

## Limitations

- One roster of scripted opponents, two players; no human games, no
  self-play. "Strong" means strong against this roster.
- Base game only; no expansions, no automa.
- Latencies are from a shared laptop; ratios are trustworthy, absolutes
  are not.
- The belief model's response likelihoods were never refit to the roster;
  the oracle arm bounds what a refit could win at 2p (≈ nothing) but not
  at 3p.
- IP: Wingspan content and rules are used as research inputs for a private
  case study; public release needs review (`COMPANY_CONTEXT.md`).

## What is next

The production question — how much strength survives a five-second clock —
is answered: essentially all of it, once the search is pre-ranked. The
research question has moved to three players, where the opponent model is
worth about two points and a hybrid (belief for the family, greedy inside
it) is in test. A self-play or human-trace
opponent is the only way to learn whether "the opponent barely matters" is
a property of the game or of the roster.
