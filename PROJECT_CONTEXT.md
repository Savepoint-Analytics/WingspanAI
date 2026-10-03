# PROJECT_CONTEXT.md

_Last updated: 2026-09-19_

## Purpose

This document preserves the longitudinal context for the Wingspan AI project.

Use it so future AI sessions, development sessions, and planning sessions do not restart from zero.

This document should capture:
- Decisions made.
- Why they were made.
- Work already discussed.
- Open questions.
- Current priorities.
- Tasks in progress.
- Things tried that did not work.
- Changes in direction.
- Important context that should survive across sessions.

Standing instructions and AI behaviour rules belong in `AGENTS.md` and `CLAUDE.md`.  
Research/case-study positioning belongs in `COMPANY_CONTEXT.md`.  
Project history, decisions, and working context belong here.

## Current project summary

Wingspan AI is an applied ML research project focused on building AI players for sequential, stochastic, partially observable, economy-constrained board games.

The first testbed is Wingspan. The project aims to:
- Digitize game content and rules.
- Build a reproducible simulation environment.
- Generate analytics events from simulated games.
- Compare scripted, heuristic, Bayesian, search-based, and learning-based AI players.
- Study dominant, dominated, and situational strategies.
- Develop reusable templates for NPC AI in video game adaptations of board games.
- Produce a credible research case study.

The project owner is Alex Oswald. Alex is the sole current contributor and final decision-maker.

## Current phase

_Standing sections refreshed 2026-09-19; the dated updates below are the record._

The simulator is rule-faithful for the base game (every base-game power
handled, replay-validated, deterministic across processes) and the project
is in **agent research with a production lens**: every change to the
champion agent is a registered, seed-paired arm read for both score and
latency (`docs/experiments/results_ledger.md`).

Current focus:
1. The champion is `potential_points`: depth-3 determinized search on every
   turn (K=4) with the Bayesian opponent posterior as the in-search opponent
   model. It wins 0.875 of 2p games against the roster at 78.4 points and
   0.76 of 3p games at 74.2. The only change worth ten points was the search
   itself; every valuation refinement since has been null or negative at 80
   games. The **production configuration** (adopted 2026-09-19) is
   `beam_leaf` pre-ranking under a 5 s anytime budget: −0.6 n.s. at 1.1 s a
   decision instead of 7.6. Research arms stay unbudgeted for determinism.
2. Value per millisecond. The price list is closed at 2p: depth ≈ 1.7
   points per doubling of decision time, K ≈ 0.9, opponent-model family ≈ 0.
   The profiler and `decision_profile_report.py` price every arm in points
   per second.
3. The opponent-model programme is **closed at both counts** (2026-09-20).
   2p: five models within ±1 vs the roster and the greedy model +0.5 n.s.
   in self-play — a cost knob. 3p: greedy is worth ≈+2 twice over (roster
   +2.1, mirror +1.9, combined p≈0.01), a score not a win effect, at ×1.55;
   nothing cheaper reproduces it. `belief` stays everywhere; the ledger
   carries the 3p price. Self-play A1 gives 75.3 at 2p / 78.3 at 3p; seat 1
   is **+6.2 at 2p** pooled over A1+A4 on 80 independent decks (p<0.001,
   win 0.61) — the first established seat finding, invisible against the
   roster. Denial as a root term is −5.9 (A3, dropped).
4. Standing holdouts (five fields) keep every decided switch's losing side
   alive at 5% (`docs/experiments/standing_holdouts.md`).
5. Card-choice decisions remain the parked place to spend evidence: the
   measured opener showed play value is not keep value (−1.9); bonus-card
   choice is worth 6.4 and `expected_points` gets 61% of it.
6. Keep the reusable template honest: holdouts, profiling, paired arms,
   replay hashing and the rules/agents/telemetry split know nothing about
   Wingspan. The template doc and the expansion configuration doc are the
   two unwritten architecture pieces — the expansion configuration doc is
   now written and phase 0 (packs/modules threading, teal/yellow hooks,
   ruleset grain, bit-identity guard) built on 2026-09-20.

## Current assets

Root: `README.md`, `AGENTS.md`, `CLAUDE.md`, `COMPANY_CONTEXT.md`,
`PROJECT_CONTEXT.md`, `data/raw/wingspan-card-list.xlsx`, `rulebook_pdfs/`.

- `src/wingspan_ai/`: content loader and schemas, `state/` Pydantic game
  state, `rules/base_game.py` (setup, legal actions, transitions, all
  base-game powers, scoring, `apply_action(trusted, lean)` fast path),
  `agents/` (random, greedy, archetypes, Monte Carlo, `potential_points`
  champion, `net_value`, guardrails, setup policies, `search_opponent`,
  `holdout`, `profiling`, `forced_play`), `belief/` opponent posterior,
  `simulation/` runner, replay hashing, tournament, artifacts, `telemetry/`
  events, FastAPI, PostgreSQL.
- `flows/`: `simulation_batch.py` (manifests, replay gate, rule audits,
  per-seat config, holdouts, profiling mode), `round_robin.py`.
- `analysis/`: `arm_contrast.py`, `decision_profile_report.py`,
  `holdout_guardrail.py`, bonus-card and synergy instruments, SQL views,
  `r/` lme4 models.
- `docs/`: architecture, rules, events, agents (model cards), experiments
  (plans, results, `results_ledger.md`, `standing_holdouts.md`), decisions
  (ADRs). Index: `docs/README.md`.
- `tests/`: 410 tests; `test_default_workbook_path_points_to_raw_data`
  fails only when `.envrc` sets `WINGSPAN_CARD_WORKBOOK`.
- `artifacts/`: every arm's manifests, events and outcomes, by root
  (`rr_belief_opp` is the current baseline for the default agent).

## Important decisions made

| Area | Decision | Rationale | Revisit if |
|---|---|---|---|
| Project identity | Treat this as **Wingspan AI**, a separate project from Savepoint Analytics. | Avoids contaminating research docs with Savepoint platform/client assumptions. | Alex decides to merge it into a broader Savepoint demo repo. |
| Primary use case | Use Wingspan as the first testbed for board-game NPC AI and strategic ML. | Wingspan has sequential decisions, hidden information, stochastic draws, resource constraints, card synergies, and multiple scoring paths. | Another game becomes a better first reusable template candidate. |
| Public framing | Position as a research case study, not a commercial game product. | Showcases ML/game analytics capability while reducing confusion around IP and product scope. | Legal review and licensing context change. |
| Architecture | Separate game content, rules, state transitions, agents, telemetry, orchestration, and analysis. | Keeps the implementation testable and reusable for other games. | This separation causes excessive overhead before the simulator works. |
| Simulator priority | Build deterministic, seedable base-game simulation before advanced ML. | Model results are not meaningful until legal actions and scoring are trustworthy. | Alex explicitly prioritizes exploratory modelling over simulator fidelity. |
| Analytics stack | Use FastAPI, PostgreSQL, Prefect, MLflow, Python, SQL, and R. | Matches Alex's preferred stack and supports reproducible experiments. | Local complexity slows early progress. |
| ML sequence | Start with baselines and heuristics before RL/deep learning. | Baselines are easier to debug and provide comparison anchors. | A specific research question requires earlier RL setup. |
| Reusability | Design a board-game AI template alongside Wingspan-specific implementation. | The case study should become reusable for similar games. | Reuse abstractions delay basic simulator completion. |
| Evidence standard | Every agent change is a registered prediction, then a seed-paired 80-game arm from a clean worktree, read with `arm_contrast` and `decision_profile_report`. | Unpaired and unregistered comparisons produced two false findings (greedy second; seat-3 advantage). | Never; tighten the design when it fails. |
| Baseline | `artifacts/rr_goal_placement` (2p) and `artifacts/rr3p_goal_placement` (3p) at `1b380e7` are the default agent's baselines (2026-09-22; `rr_belief_opp` before that). | The placement round-goal model was adopted, so the default agent changed. | The next adopted change re-baselines. |
| Standing holdouts | Every adopted or dropped switch keeps its losing side in a deterministic 5% of games (2026-09-17, generalizing the 2026-09-16 opponent-model control). | False positives at n=80; learning bias once agents learn from archived games. | A holdout accrues ≥100 games and agrees with the decision — retire it. |
| Attribution | K=4 determinization is the standard for any play-attribution run (2026-09-17). | K=0 pair tables were noise (ρ=0.31 with K=4). | Cheaper attribution that matches K=4 ranks. |
| Cost | Value per millisecond: an agent calculation is kept only if its measured gain justifies its measured latency; otherwise gated, optimized or dropped (2026-09-17). | Production agents must not bore the player. | Alex sets a different latency budget. |

## Technical architecture direction

### Conceptual layers

Recommended layers:

1. **Game content**
   - Bird cards.
   - Bonus cards.
   - Food/resource types.
   - Habitats.
   - Round goals.
   - Expansion modules.
   - Rule configuration.

2. **Rules engine**
   - Setup.
   - Legal action generation.
   - Action validation.
   - State transitions.
   - Triggered powers.
   - Round-end scoring.
   - Final scoring.
   - Seeded randomness.

3. **State and observations**
   - Full game state.
   - Public state.
   - Private player state.
   - Agent observation.
   - Belief state over hidden information and opponent type.

4. **Agents and policies**
   - Random legal policy.
   - Scripted baseline policies.
   - Heuristic expected-value policies.
   - Strategy archetypes.
   - Search/rollout agents.
   - Bayesian belief-based agents.
   - Learned policies and value functions.

5. **Simulation and tournaments**
   - Single-game runner.
   - Batch simulation.
   - Tournament runner.
   - Agent roster configuration.
   - Seed and ruleset management.

6. **Telemetry and analytics**
   - Simulation events.
   - FastAPI ingestion.
   - PostgreSQL storage.
   - SQL/R/Python analysis.
   - Strategy and card valuation summaries.

7. **Experiment tracking**
   - MLflow experiments.
   - Model/agent parameters.
   - Run artifacts.
   - Tournament outcomes.
   - Decision summaries and model cards.

### Reusable board-game template concepts

The framework should eventually support a game definition shaped around:
- `game_config`
- `ruleset`
- `content_catalog`
- `player_config`
- `game_state`
- `player_state`
- `public_observation`
- `private_observation`
- `belief_state`
- `legal_action`
- `action_mask`
- `transition_result`
- `reward_function`
- `scoring_function`
- `agent_policy`
- `simulation_event`
- `experiment_config`

Wingspan-specific logic can live under a Wingspan module, while generic interfaces should stay reusable.

## Methods to start with

The recommended method sequence is intentionally practical:

1. **Rules-first baseline**
   - Implement random legal play and basic legal-action validation.
   - Success criteria: full games complete without illegal actions or state corruption.

2. **Greedy scoring baseline**
   - Choose actions based on immediate point gain or simple expected point gain.
   - Success criteria: beats random legal policy over a meaningful simulation batch.

3. **Round-aware heuristic**
   - Include round goals, remaining turns, resource constraints, and engine setup value.
   - Success criteria: improves win rate and produces interpretable decision summaries.

4. **Strategy archetype bots**
   - Implement several coherent play styles such as egg focus, engine building, bonus-card focus, food acceleration, card draw/tuck, predator/cache, and round-goal chase.
   - Success criteria: each strategy has measurable behavioural signatures in telemetry.

5. **Monte Carlo rollout agent**
   - Estimate action value through sampled continuations using baseline policies.
   - Success criteria: improves against heuristics under a fixed move-time or rollout budget.

6. **Bayesian opponent model**
   - Maintain beliefs over opponent strategy type, hidden score potential, and likely next actions.
   - Success criteria: belief estimates become better calibrated over game time and improve selected decisions.

7. **MCTS or search hybrid**
   - Use action masks and rollout/value estimates for longer-horizon planning.
   - Success criteria: outperforms Monte Carlo rollouts or heuristics with acceptable compute.

8. **Learning-based agents**
   - Add imitation learning or RL once traces and environment API are stable.
   - Success criteria: learning agents beat baselines and produce logged artifacts in MLflow.

## Current recommended next tasks

The May 2026 build list is complete; the record is in the dated updates.
The 2026-09-17 list is also done: measured opener (−1.9, dropped), 5 s
budget (ladder v2 + pre-ranking adopted as the production configuration),
oracle-type arm (null at 2p), beam pre-ranking (−0.7, in production), case
study body (`docs/experiments/case_study.md`). Current tasks, in order
(2026-09-19):

| Priority | Task | Success criteria |
|---|---|---|
| 1 | **Ten human games** (Alex) with `flows/human_vs_agent.py` (built 2026-09-20), seat-swapped; then H1–H3. Now the main falsification risk to the headline finding: "nearly solitaire" has only ever been tested against robots that do not block or contest a telegraphed bonus card. The first-player advantage (+6.2 in self-play) is the first thing to read there. | Ten games archived and replay-valid; belief log loss on the human scored against every roster kind (`fit_response_model.py` on `artifacts/human`); H2 disagreement list through the viewer. |
| 2 | Fix `test_depth_is_bought_before_samples`, flaky at ~1 in 6 (pre-existing; see *Known flaky test*). Remove the wall-clock calibration -- inject a clock or assert the ladder's decision sequence. | The test passes 20 consecutive runs under load; no assertion derives from a measured elapsed time. |
| 2 | Expansion phase 1 — European (`expansion_configuration.md` §European): action-cubes-per-row state, ~10 unclassified templates, teal handlers with rulebook refs, 7 bonus + 10 goal handlers, audit, 25-game smoke, `rr_european_base` baseline arm. | Gates 1–9 pass for `core_european_v1`; `base_game_bit_identity.py` still identical. |
| 2 | Strong-play descriptive pass on the 330 mirror games (round-goal contention, engine timing, the champion's belief-posterior row for the oracle table). | `strategy_findings.md` §4 gains the goal-contention and timing rows; `oracle_type_posteriors.json` gains a `potential_points` row. |
| 2 | Read the pooled holdout guardrail now that six more default-agent roots exist. | `holdout_guardrail.py` over every default-agent root; any field over 100 games that agrees with its decision is retired. |
| 3 | Draw-choice preference from the K=4 bird values, behind a switch. | One 80-game arm; registered ±1 band (the opener lesson says expect a null). |
| 3 | Keep model on the 322 measured bonus-card deals, held out on the engine-builder deals. | Beats `expected_points` 61% pick rate on held-out deals (free on archived games). |
| 3 | `docs/architecture/reusable_board_game_ai_template.md`. | Lists every interface a second game must implement and every module that needs no change. |
| 4 | European expansion as the first content pack + rules module (`docs/rules/expansion_configuration.md` first). | Loader, handlers and scoring behind `ruleset` config; base-game batches bit-identical with the pack off. |

## Known flaky test

`tests/test_decision_budget.py::test_depth_is_bought_before_samples` fails
roughly **1 in 6 runs**, and more often under load. It is timing-calibrated: it
measures one probe decision's elapsed time, sets the budget to 0.65x that, then
asserts the ladder kept depth 2 and used fewer than 2 samples. Any variation in
machine load between the two runs moves that ratio across the assertion boundary.

Measured 2026-10-02 to rule out a regression: current HEAD fails 1 of 6, the
commit before the `reroll_penalty` switch fails **2 of 6**. So the flakiness is
pre-existing and was not introduced by that change.

This is a real defect, not an infrastructure excuse -- a suite with a 17% flaky
test teaches people to re-run rather than read failures. The fix is to remove the
dependence on wall-clock calibration: inject a fake clock, or assert on the
ladder's decision sequence rather than on counts derived from a measured budget.
Tracked in the task table.

## Open questions

### Scope and fidelity

- Which Wingspan expansions should be supported first after the base game?
  - Answer: all Wingspan expansions should eventually be supported.
  - Recommended implementation order follows release chronology: European Expansion, Oceania Expansion, Asia, then Americas.
  - Which expansions are active should be determined by each simulation's ruleset configuration.
- Should automa rules be included or treated separately?
  - Answer: include automa rules, but treat them as a separate rules module because they override or replace parts of normal multiplayer play.
- What level of card-power fidelity is required for first meaningful experiments?
  - Answer: enough fidelity to preserve engine economics and scoring incentives, with transparent simplifications for rare or complex powers.
  - Detailed recommendation: `docs/rules/data_and_rule_encoding_recommendations.md`.
- Which edge cases can be stubbed initially without corrupting strategy findings?
  - Answer: stub edge cases that add implementation complexity but do not alter the core economy loop.
  - Detailed recommendation: `docs/rules/data_and_rule_encoding_recommendations.md`.

### Data and rules

- Does `data/raw/wingspan-card-list.xlsx` contain enough structured information to encode all bird powers?
  - Answer: enough for static metadata and content loading, not enough for full executable power logic without a translation layer.
  - Detailed recommendation: `docs/rules/data_and_rule_encoding_recommendations.md`.
- Which card powers require hand-authored rule handlers?
  - Answer: timing-sensitive, conditional, choice-heavy, opponent-dependent, placement-changing, and expansion-specific powers need hand-authored handlers.
  - Detailed recommendation: `docs/rules/data_and_rule_encoding_recommendations.md`.
- How should expansions be represented: additive modules, alternate rulesets, or content packs?
  - Answer: use content packs plus rules modules, not one giant alternate ruleset.
  - Detailed recommendation: `docs/rules/data_and_rule_encoding_recommendations.md`.
- How should official rulebook references be tracked against encoded rules?
  - Answer: use a rule registry linking encoded rules and power handlers to source documents, workbook fields, implementation modules, tests, and implementation status.
  - Detailed recommendation: `docs/rules/data_and_rule_encoding_recommendations.md`.

### AI and modelling

- What is the first strategic question to test after random and greedy baselines?
  - Answered 2026-09-05: lookahead. Depth-3 search is worth +10; nothing else tried is worth more than ±2.
- Should Bayesian modelling start with opponent type, hidden score, card draw probabilities, or end-game score distributions? Answer: it should start with with what presumably more important and stronger in terms of signal strength and propensity to which it will impact the final outcome.
  - Where it stands 2026-09-17: the opponent posterior is in the search loop and is worth ≈0 points at 2p (but −57% latency). Hidden-information peeking is worth −2.4 (determinizing is better). The oracle-type arm will bound what is left.
- What observation encoding should be standard for learning agents? Open; the `bird_scorecard` and `agent_decision_summary` events are the candidates.
- What reward shaping avoids teaching agents misleading short-term behavior?
  - Partly answered: the round horizon (not game horizon) is load-bearing for the evaluator (−12 with the game horizon).
- What compute budget should a move-level agent be allowed?
  - Reframed 2026-09-17 as value per millisecond; the budget knob is the next build.

### Analytics

- What simulation events are required to replay a game exactly?
- What should be logged for private/hidden information, and how should it be marked?
- Which metrics best describe strategy quality beyond win rate?
- What result tables are needed for R analysis?

### Reusability

- Which interfaces must be generic from day one?
- Which Wingspan concepts are too specific to abstract early?
- What is the minimum game-definition template needed for another game?

## Metrics and evaluation

Important evaluation metrics:
- Win rate by agent matchup.
- Mean, median, and distribution of final scores.
- Score by category: birds, bonus cards, end-of-round goals, eggs, cached food, tucked cards, nectar if expansion rules apply.
- Action frequency by game phase.
- Resource efficiency.
- Turns to engine activation.
- Round-goal participation and placement.
- Bonus-card completion rate.
- Card draw/play conversion.
- Hidden score estimation error.
- Opponent type classification accuracy.
- Expected value calibration.
- Compute time per move.
- Robustness across seeds, player counts, and rulesets.

## Documentation backlog

Written: architecture, rules scope, event taxonomy, baseline and champion
agent docs, decision profiling, results ledger, standing holdouts, case
study body (`docs/experiments/case_study.md`, 2026-09-18), game viewer,
ADRs 0002–0005. Still to write:
- `docs/architecture/reusable_board_game_ai_template.md` — the template as
  it now exists (state/actions/transition/scoring/policy/belief/holdout/
  profiling), with what is and is not Wingspan-specific.
- (written 2026-09-20) `docs/rules/expansion_configuration.md`.
- `docs/experiments/strategy_findings.md` — the balance / dominance /
  archetype answers, collected from the ledger with detection limits.

## Project memory update protocol

Update this file when:
- A major technical decision is made.
- A major research decision is made.
- A task is completed that changes the project state.
- A roadblock is discovered.
- A tool or method is rejected after trying it.
- Expansion/ruleset scope changes.
- A reusable template boundary changes.
- A repeated explanation should no longer be repeated.

Use this format for updates:

```markdown
## Update: YYYY-MM-DD - Short title

### What changed
Briefly describe the change.

### Why it matters
Explain the implication.

### Decision
State the decision if one was made.

### Follow-up tasks
- [ ] Task 1
- [ ] Task 2
```

## Decision log

| Date | Decision | Notes |
|---|---|---|
| 2026-05-03 | Re-scope project context from Savepoint Analytics to Wingspan AI. | This directory is a separate research case study, not the Savepoint platform. |
| 2026-05-03 | Use Wingspan as first testbed for reusable board-game NPC AI. | The game has the right combination of partial information, stochastic setup, sequential actions, resource constraints, and multiple scoring systems. |
| 2026-05-03 | Use FastAPI, PostgreSQL, Prefect, MLflow, Python, SQL, and R as default stack. | Supports telemetry ingestion, batch simulation, experiment tracking, and exploratory analysis with familiar tools. |
| 2026-05-03 | Start with base game, random legal agent, greedy agent, and heuristics before advanced ML. | Valid simulator and baselines are prerequisites for credible Bayesian, search, or RL results. |
| 2026-05-03 | Use `src/wingspan_ai/` as the initial package root with separated content, rules, state, agents, simulation, telemetry, experiments, and reusable board-game modules. | Keeps simulator code organized while leaving room for a reusable board-game AI template. |
| 2026-05-03 | Model expansions as content packs plus rules modules. | Some expansions add content, while others change resources, mats, player counts, scoring, or automa behavior. |
| 2026-05-03 | Track power/scoring implementation status explicitly in content schemas. | Prevents unsupported powers from being silently treated as implemented during early experiments. |
| 2026-05-03 | Store data/rule encoding recommendations in `docs/rules/data_and_rule_encoding_recommendations.md`. | Keeps detailed technical guidance close to the rule docs and keeps `PROJECT_CONTEXT.md` concise. |
| 2026-05-03 | Keep first rules loop explicit and minimal: setup, legal actions, transitions, round advancement, score skeleton, and random legal agent. | Gives the project a tested simulator foundation before adding powers, telemetry, scoring handlers, single-game runners, or ML agents. |
| 2026-05-04 | Keep external service/orchestration/tracking integrations optional around a testable core simulator. | Lets the runner, events, and agents stay usable before FastAPI, Prefect, MLflow, PostgreSQL, and dev tools are installed locally. |
| 2026-05-04 | Treat archetype bots and Monte Carlo rollouts as experimental baselines, not strategic conclusions. | Current rule fidelity is enough for plumbing and behavioural signatures, but not enough for claims about optimal Wingspan play. |
| 2026-05-05 | Make initial setup choice an explicit policy boundary. | Opening hand and starting food choices matter strategically, so agents need a hook to control them before advanced modelling. |
| 2026-05-13 | Represent richer habitat actions as concrete `LegalAction` values. | Agents can now choose scaled food/card/egg outputs, conversion choices, and reroll options through the normal rules boundary. |
| 2026-08-31 | `random_seed` is the sole RNG key; determinism across processes is a gate on every batch (ADR 0003, 0004). | A cross-process nondeterminism bug invalidated earlier standings. |
| 2026-09-05 | Depth-3 determinized search on every turn is the champion's core. | +10.4 points; the only large positive result. |
| 2026-09-16 | Belief posterior is the search's opponent model; `rr_belief_opp` is the baseline; 5% of games keep greedy. | Null on score, half the latency. |
| 2026-09-16 | `expected_points` bonus-card choice adopted; the v2 opener as a whole is not (bird/food selection is a defect). | +0.85 on the choice, −3.0 on the whole opener. |
| 2026-09-17 | K=4 is the standard for attribution runs; the synergy evaluator term stays off; card-choice decisions get the synergy evidence next. | K=0 tables were noise; −4.5 / +1.3 n.s. for the term. |
| 2026-09-17 | Every decided switch keeps a 5% holdout; value per millisecond is the production yardstick; fast search-child expansion adopted. | Alex's guardrail rule; bit-identical decisions at half the per-child cost. |

## Things to avoid repeating

The following points are already established unless changed:
- This is a Wingspan AI research project, not Savepoint Analytics.
- The project should be case-study-ready.
- Wingspan is the first testbed, but reusability for similar games matters.
- Baselines and rules tests come before advanced ML.
- Bayesian game theory is a major research direction, especially for partial information and opponent modelling.
- Simulation telemetry is central, not an afterthought.
- Use small tasks with clear success criteria.
- Register the prediction before the arm; pair by seed; launch from a clean worktree; read score and latency together.
- Do not adopt or drop a switch without adding its `Holdout`.
- Do not read an unpaired or sub-detection-limit contrast as a finding; the 80-game limit is ~1.9 points.
- Do not read a single per-opponent cell as a finding: four cells give an 18.5% chance of a spurious hit, six give 26.5%. Pool the cell across arms, or treat it as a hypothesis for its own arm.

## Files that should exist near this file

Recommended root-level docs:

```text
README.md
AGENTS.md
CLAUDE.md
COMPANY_CONTEXT.md
PROJECT_CONTEXT.md
docs/
```


<!-- archived-log-index -->
## Archived project log

Earlier updates were moved **verbatim and unedited** to the project log;
nothing was summarised. See `scripts/archive_project_log.py`, whose
completeness gate asserts every original line survives the move.

- **2026**: 90 updates in `docs/history/project_log_2026.md`

## Update: 2026-09-28 - the event log is loaded; the archive is now fully queryable

`scripts/load_events_from_object_storage.py` (new) streams each archived
`events.jsonl`, keeps the eight families the view layer and KPI functions read,
and bulk-loads them with `COPY` through an unlogged staging table merged on
`event_id` — so the load is idempotent and additive. `executemany` over this
volume was not viable; `COPY` is the difference between minutes and hours.

**10,934 objects, 723,168 rows read, 440,437 newly inserted, zero failures.**

| | before | after |
|---|---:|---:|
| games carrying events | 4,491 | **10,936 of 10,956** |
| `potential_points_p1` coverage | 10.7% | **99.6%** |
| `engine_builder_p1` | 93.1% | 100% |
| `greedy_immediate_p2` | 99.9% | 100% |
| every other seat | **0%** | **99.1-100%** |

The remaining limit is real but narrow: `round_goal_scored` has 3,208 rows
because the event dates from 2026-09-22, so per-round goal *placement* covers
recent games only. Goal totals come from `game_scores` and are complete.

### What the load immediately bought

**Breeding Manager is now a finding, not a hypothesis.** It was flagged from 25
games as "worth a proper paired study rather than a claim". On **391 games** it
is still last of 26 bonus cards, matching 0.68 birds a game against the best
card's 3.79 (fulfilment 0.082 vs 0.577). The old numbers were *harsher* than the
truth (0.031 → 0.082) because they came from weaker agents' decks, but the
ranking held. The real spread across cards is 7-fold, not the tenfold the small
sample suggested.

**The archetypes behave as advertised** — a behavioural check that was
impossible before:

| agent | birds played | matching the kept bonus card | fulfilment |
|---|---:|---:|---:|
| `bonus_card_focus` | 7.02 | 4.13 | **0.597** |
| `potential_points` | 7.71 | 3.49 | 0.442 |
| `engine_builder` | 8.36 | 2.83 | 0.334 |
| `greedy_immediate` | 3.93 | 1.29 | 0.310 |

`bonus_card_focus` steers plays toward its card at nearly twice greedy's rate
while playing fewer birds than `engine_builder`. And the champion sits
mid-table at 0.442: it is **not** chasing its bonus card, it scores 5.4 bonus
points by playing well and taking the points where they fall. Against
`bonus_card_focus`'s 0.597 fulfilment and highest-of-any-agent 6.0 bonus points
for 14 fewer points overall, that is the engine-vs-objective tradeoff in two
rows.

### A suspicion I raised and then disproved

Reading the card table I saw `Anatomist [swift_start_asia]` being dealt and kept
512 times in base-game games and started writing it up as a rule-fidelity bug.
It is not one. `docs/rules/bonus_card_composition.md` settled this on
2026-09-16: the workbook's `Set` column reads `core, asia` because the Asia
swift-start pack **reprints** a core card, and the suffix is a naming artifact.
The core pool is exactly 26 cards, the right count, and the loader correctly
excludes `Forest Ranger [swift_start_asia]` (set `asia` only) and the five
automa cards. Recorded here so the question is not raised a third time.

### Counterfactual replay: feasible, and mostly already built

Asked whether archived games can be rewound to a decision point and replayed
down the other branch. Yes — `analysis/play_counterfactuals.py` already does it
for `play_bird` decisions, and three things make it general: the replay is exact
(ADR 0003 put only `random_seed` in the RNG), the **full** legal-action set is
logged at every decision, and the reconstruction under that script yields every
resolved action, not just plays.

Two things worth recording from that conversation:

1. **There is no "perfect" counterfactual.** Once play diverges, the outcome
   depends on the continuation policy for both seats, the deck order, and the
   opponents' hidden cards. The continuation policy *defines* what the number
   means; the existing script is explicit that its values are "what this play
   was worth to a competent but non-searching continuation", and
   `--continuation-samples K` averages over resampled worlds so the answer does
   not hinge on one shuffle.
2. **The near-tie design is the valuable part, and it is available
   retroactively.** Restricting to decisions where the agent's own evaluation
   had two options within ~0.2 points gives thousands of naturally occurring
   randomised trials, because noise decided which won. The log records the
   winning option's score but not the runner-up's — however, since the state
   rebuild is exact and the evaluator deterministic, every candidate's value can
   be **re-derived** on all 10,956 archived games without new instrumentation.

Why this matters more than another arm: an 80-game arm resolves about ±3 points,
which is why three recent registrations were unanswerable. Decision-level
pairing gives thousands of paired observations with deck and opponent luck
differenced out, putting ±0.5 effects in reach. The honest limit is selection on
the state distribution — the decisions available are the ones this agent reached
via its own earlier choices, so the value learned is conditional on that agent's
trajectory. Near-tie filtering reduces but does not remove it.

## Update: 2026-09-29 - near-tie counterfactuals confirm indifference; tie-break tuning closed

First collection read against the registration written before it
(`docs/experiments/near_tie_counterfactuals.md`). **2,045 near-tie decisions
across 90 games** from the placement-default roots.

**The registration was answerable as committed** — delivered n=2,045 against a
1,400 floor and SD=4.88 against a 5.5 ceiling. This is the first arm in four
where the power claim held, which is the 2026-09-25 rule working. One honest
caveat: the realized detection limit is 0.302 rather than the predicted 0.25
(SD came in at 4.88, not the assumed 4.0), which is a hair outside the band's
0.3 half-width, so the verdict rests on the confidence interval rather than on
the limit.

**Result: +0.062, p=0.565, 95% CI [−0.149, +0.273]** — the whole interval inside
the registered −0.3 to +0.3 band. That is the strong form: a positive finding of
indifference, not a failure to reject. Where the champion says two options are
within a hair, it is right, and its tie-breaking carries no recoverable signal.
**33.6% of near-ties end in exactly zero realized difference** — genuinely inert,
not merely close.

**No per-pair finding.** Sixteen cells reached n≥20, not the ~10 anticipated, so
the true Bonferroni threshold is 0.0031 rather than the registered 0.005;
nothing clears either. Two nominations recorded as nominations: `play_bird`
chosen over `draw_cards` at −1.51 (p=0.024, n=63 — mechanistically plausible
over-eagerness to play birds, and at the edge of what a 63-decision cell could
ever detect) and `gain_food` vs `gain_food` at +0.43 (p=0.051, n=393).

**What this buys: a line of work closed cheaply.** There is no free ≥0.3 points
in evaluator tie-breaking, so tuning it is not productive. Negative results that
close directions are the point of this instrument.

### Margins against a peer are half what they are against the roster

Measured while answering a design question, and it reframes several things:

| regime | mean winning margin | games within 5 points |
|---|---:|---:|
| vs the weak roster (2p) | 24.8 | 13.8% |
| **champion vs champion (2p)** | **12.4** | **30.3%** |

Outcome noise from an identical state is SD 4.88. So against a peer the noise is
the same order as the deciding margin in about a third of games, while against
the roster most games are blowouts. Any risk-aware or distributional idea is
capped by that ~30%, and is worth nothing at all in roster games — which is also
a caution about reading roster win rates as skill measurements.

### Gaussian-Markov agent: assessed, not built

Asked what a Gaussian Markov chain agent would look like. Three readings, two
dead on this project's own evidence:

- **Kalman-filtering opponents' hidden state** — dead. Perfect opponent-type
  knowledge measures +0.00, and a filter cannot beat the oracle it approximates.
- **A GMRF over bird/board synergies** — the nearest prior attempt, the
  engine-potential mechanic-pair term, measured −4.51 (p=0.001).
- **A round-indexed linear-Gaussian forecast of final score used as a
  distributional leaf evaluator** — the live one.

The argument for the third is the score/win disconnect already in the ledger:
the oracle gained +0.00 score but +0.011 win; the 3p greedy opponent model gained
+1.89 score and *lost* 0.011 win. The evaluator returns a scalar, so the agent
cannot express "when ahead take the low-variance line, when behind gamble".
P(win) = Φ((μ_me − μ_opp)/√(σ²_me + σ²_opp − 2cov)) can, and the shared
tray/feeder/goals make that covariance term mandatory rather than optional.

Design constraints worth keeping: `A_r` must be round-indexed (four rounds of
8/7/6/5 turns is non-stationary by construction); round goals are rank
statistics and should stay with the existing Poisson placement model rather than
be forced into a Gaussian; scoring is end-loaded so the chain should model engine
state with a separate terminal emission; and the model must never select actions,
only evaluate leaves, because hard constraints like food costs are inexpressible
in linear dynamics.

**The blocker is one cheap emitter:** per-round score snapshots are not emitted
(already flagged in the KPI coverage table), and a Markov chain over rounds
cannot be fit without round states. Adding it makes future games yield ~4
transitions each.

**Sequencing advice given:** pre-test the premise on the near-tie rows, which
already measure outcome variance from identical states, before building
anything. And if it is built, **register the win-rate band, not the score band** —
the mechanism is converting score into wins, so a score registration would
declare it null by construction, and win rates need far more games for the same
power.

## Update: 2026-09-30 - the reroll_penalty arm lands in the middle zone, and I registered a design the launcher cannot build

### Result

`reroll_penalty=2.0` vs a fresh default baseline, both sides at the same commit.

| read | n | Δ | p | SD | limit | 95% CI |
|---|---:|---:|---:|---:|---:|---|
| primary, all games | 80 | **−0.388** | 0.553 | 5.81 | 1.82 | [−1.66, +0.89] |
| by deck | 10 | −0.388 | 0.501 | — | — | — |
| differing games only | 41 | −0.756 | 0.556 | 8.15 | 3.56 | [−3.25, +1.74] |

**Middle zone by the registered rule: not adopted, not refuted.** The point
estimate is mildly negative — the opposite sign to the nomination.

**What it does settle:** the CI's upper bound of +0.89 excludes both the +1.5
adopt threshold and the +1.44 the nomination predicted, so **the near-tie +2.40
a decision does not transfer to whole-game score.** The strong form is dead.
What remains unresolved is anything inside ±0.9.

**The power model held**, which is worth noting after three arms where it did
not: predicted 47% bit-identical games against 49% delivered, predicted SD 6.5
against 5.81.

### My error, and the rule it earns

I registered **160 games over 20 decks**. The arm delivered **80 over 10**,
because `analysis/launch_arm.py --seeds` is ignored for 2p roster arms — its own
help text says "2p roster arms always use seeds 1-10". I dry-ran the launcher but
only checked that it wrote its scripts, not that it would produce the registered
number of games.

That matters rather than being cosmetic: the realized detection limit is **1.82**,
*above* the registered +1.5 adopt threshold, so the delivered arm could not
reliably detect its own adoption criterion. Fourth registration this month to
outrun its sample, and the first where the cause was a tooling assumption rather
than an optimistic variance estimate.

**Added to the standing registration rule (2026-09-25): verify a dry run's game
count against the registered n before launching, not just that it wrote its
scripts.**

### Closed on cost grounds

Resolving ±0.7 at the realized SD needs **540 games**; a 2p roster arm caps at
80, so it would need mirror mode. Not worth it: the prior was 29 post-hoc
decisions, the mechanism I proposed was falsified before launch (rerolls resolve
deterministically, so the search already sees the roll), feeder-odds valuation is
already null three times over, the point estimate is negative, and the strong
form is excluded. Recorded as closed with the nomination noted as *untested below
±0.9* rather than refuted.

If ever reopened, the better intervention is pricing the post-reroll feeder state
for the player's own later turns — the horizon mechanism — rather than a flat
penalty, which probing showed is blunt: 2 of 4 flipped decisions demoted
food-gaining below an unrelated action type instead of just declining the reroll.

### Net position on the near-tie programme

Two registered reads, both honest nulls, both cheap, and both closing a
direction:

1. Evaluator tie-breaking carries no recoverable signal (+0.062, CI inside the
   ±0.3 band). Tie-break tuning is not productive.
2. The one nomination worth testing did not transfer to whole-game score.

That is the instrument working as designed. The lesson to carry into any future
use: a per-decision effect measured at near-ties is **not** an estimate of a
whole-game effect, because a switch that captures it also changes unrelated
decisions. Measure the per-decision effect to *find* candidates, then always
budget the arm on whole-game variance.

## Update: 2026-09-30 (later) - arm worktrees now reap themselves

Seven `WingspanAI-arm-*` folders had accumulated beside the repo and looked like
duplicated projects. They were not: each carried a `.git` **file** pointing into
`WingspanAI/.git/worktrees/`, so one 18 MB object store was shared across all
eight checkouts, and each folder held only ~4.4 MB of source at a pinned commit.
Every arm writes its results to `MAIN/artifacts/<root>` — verified, the
worktrees contained **zero** outcome files — so nothing of value ever lived
outside the project repo.

**Why arms run in a separate checkout at all.** Two requirements collide: an arm
must run at one pinned commit (the launcher refuses to start on a dirty tree,
because provenance has to record `dirty: false`), and arms run for one to eight
hours while work continues. This session is the proof — the schema re-key, the
KPI rewrite, the near-tie instrument and an agent change all landed while arms
were in flight. Run from the main tree, those arms would have been executing
against code being mutated underneath them.

**The actual defect was cleanup.** The launcher has always printed "remove the
worktree when the arm is done", and that reminder was missed **7 times out of
9** — a design problem, not a diligence problem. Fixed:

- `queue.sh` now reaps its own worktree after every runner group reports
  `GROUP COMPLETE`, waiting for the runner processes to exit first (the marker is
  the last line of `run_group.py`, not proof the process is gone) and `cd`-ing to
  the main tree before removing the checkout it was standing in.
- `analysis/launch_arm.py --prune` cleans up worktrees whose queue died before
  reaping, with `--dry-run` support. It keeps anything still running, anything
  without `GROUP COMPLETE` in every runner log, and anything dirty — surfacing
  git's own refusal rather than forcing.

Verified end to end: incomplete arm kept, complete arm removed, dirty worktree
kept with the reason shown, generated `queue.sh` passes `zsh -n`, and
`arm_worktrees()` never returns the main checkout. The seven stale worktrees are
removed; `git worktree list` shows only the main tree.

## Update: 2026-10-02 - PROJECT_CONTEXT consolidated; the record audited first

Ran a coverage audit **before** moving anything, on the principle that
relocation must not be able to hide a gap. Two of my own audit passes were wrong
and worth recording as method lessons:

- Matching **folder names** against the ledger reported "41 of 59 arms lack a
  ledger row, 24 recorded nowhere". False: the ledger's artifact column names the
  *baseline* root, not the arm root, so `rr_prerank_v2`, `rr3p_oracle15` and the
  depth arms all looked missing while being fully recorded by description.
- String matching broke across **line wraps** — the dry-run rule reads
  `"verify a dry run's game\ncount"`, so a search for "game count" missed it.

Corrected audit, at switch-topic granularity: **all 16 switch topics across 59
artifact roots have both a ledger row and a supporting doc.** Nothing about any
experiment was recorded only here.

Two genuine orphans existed, both standing material trapped in dated updates, and
both now have canonical homes:

| orphan | moved to |
|---|---|
| rule: a per-decision effect is not a whole-game effect | `results_ledger.md` → *Standing rules for registering and reading an arm*, which now gathers all four registration rules in one place with pointers to the evidence |
| the Gaussian-Markov agent assessment | `docs/agents/gaussian_markov_value_agent.md` |

### The move

`scripts/archive_project_log.py` (new) moved **90 updates verbatim** to
`docs/history/project_log_2026.md`. **4,152 → 757 lines.** Nothing summarised.

Two parsing traps, both live in this file, both fatal if missed — and both are
why this is a tool rather than a one-off edit:

1. The protocol section contains a ```markdown block holding a literal
   `## Update: YYYY-MM-DD` template. A line-based parser treats it as a heading
   and splits the protocol in half.
2. `## Decision log`, `## Things to avoid repeating` and `## Files that should
   exist near this file` sit *after* the first update, so "everything past line
   N is history" would have archived standing instructions.

Two bugs found in my own tool while using it:

- The archive was documented append-only but used `write_text`. A second run
  would have **destroyed all 84 previously archived updates**. Now it re-reads,
  merges, de-duplicates and sorts by date, so repeated runs converge.
- Each run left another index block behind. Now a prior index is removed and the
  gate exempts the tool's own generated text — it caught that itself on the first
  idempotent run, which is the gate working.

**Completeness gate:** every whitespace-normalised non-blank line of the original
4,152-line file must be present in `PROJECT_CONTEXT.md` or the archive. Verified
end to end against a pre-move snapshot: **3,410 content lines, 0 unaccounted.**

### The rule is now enforced, not remembered

`CLAUDE.md` and `AGENTS.md` (byte-identical twins; edited together, verified to
differ only in the H1) previously said "put project history in
`PROJECT_CONTEXT.md`" with no bound — so the file would have regrown, and worse,
a future session would have found updates in two places with no statement of
which is canonical. They now state the 1,000-line bound, the archive procedure,
the content-type routing, and that **new updates always go to
`PROJECT_CONTEXT.md`** while `docs/history/` is append-only.

`tests/test_doc_structure.py` enforces it: the size bound, that the threshold in
the test matches the number in both instruction files, that there is at most one
archive index, no duplicate headings, no duplicate task rows, and that the two
promoted orphans still have their homes. Verified the guard actually fires with a
remedy in the message, rather than being vacuously true.

Also merged the duplicate top task — it appeared **three times** — and recorded a
pre-existing flaky test (see *Known flaky test*).
