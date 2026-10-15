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
- `tests/`: 410 tests (527 passed, 2 skipped on 2026-10-05 at `275f6bf`, per the website-ai claims audit); `test_default_workbook_path_points_to_raw_data`
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
| 2 | **Offer the card discard as a choice** (`card_discard_fidelity.md` gap 1). `_legal_gain_food_actions` bakes one pre-chosen card into every spend-a-card variant: measured, 7 actions offering 1 discard option from a 3-card hand. Enumerate one variant per card instead. | The agent can weigh giving up one card against another; action count rises (7 → 21 in the measured case) so it needs the production beam pre-ranking; replay validation and the bit-identity guard updated. |
| 2 | **Give `bonus_fit` and the egg protection a count-based branch** (card gap 2 + egg defect 1, same fix shape, cheaper together). Four bonus cards have zero tagged birds because their condition is a board property: `Visionary Leader` (every card in hand scores), `Ecologist`, `Oologist`, `Breeding Manager`. | Holding `Visionary Leader` changes the discard choice; holding `Breeding Manager` stops the 4-egg bird being raided. |
| 2 | **Fix the wild-nest egg protection** (`egg_spending_fidelity.md` defect 2). The goal *scoring* treats a wild nest as any nest type; the *protection* does a bare string match, so `"[wild]" in "[egg] in [ground]"` is False. 17 of 180 birds, 8 nest-type egg goals. Two lines, behind `VALUE_RESOURCE_SPENDING`. | Wild-nest birds rank as protected when the active goal counts their eggs; the 2026-09-04 ablation design re-run as the check. |
| 2 | **Pass bonus cards into the egg protection** (defect 1). Its docstring already claims it does; its signature cannot. `Oologist` needs a bird at exactly 1 egg protected, `Breeding Manager` one at exactly 4 — both threshold conditions, so protection should ask "does spending cross a threshold", not add a flat +2. | Demonstrated cases reverse: [4,2] eggs with Breeding Manager held no longer spends from the 4-egg bird. |
| 3 | **Lift `move_bird_habitat`'s destination into the legal-action space** (`hidden_power_choices.md`). 8 cards, 51.6% end buried, 99% record zero power yield so the evaluator prices them at nothing. The only hidden choice whose heuristic looks actively wrong rather than merely unoptimised. | The destination is a search decision; replay validation and the bit-identity guard both updated for the wider action space. |
| 1 | **Ten human games** (Alex) with `flows/human_vs_agent.py` (built 2026-09-20), seat-swapped; then H1–H3. Now the main falsification risk to the headline finding: "nearly solitaire" has only ever been tested against robots that do not block or contest a telegraphed bonus card. The first-player advantage (+6.2 in self-play) is the first thing to read there. | Ten games archived and replay-valid; belief log loss on the human scored against every roster kind (`fit_response_model.py` on `artifacts/human`); H2 disagreement list through the viewer. |
| 2 | Expansion phase 1 — European (`expansion_configuration.md` §European): action-cubes-per-row state, ~10 unclassified templates, teal handlers with rulebook refs, 7 bonus + 10 goal handlers, audit, 25-game smoke, `rr_european_base` baseline arm. | Gates 1–9 pass for `core_european_v1`; `base_game_bit_identity.py` still identical. |
| 2 | Strong-play descriptive pass on the 330 mirror games (round-goal contention, engine timing, the champion's belief-posterior row for the oracle table). | `strategy_findings.md` §4 gains the goal-contention and timing rows; `oracle_type_posteriors.json` gains a `potential_points` row. |
| 2 | **Test whether the guardrail's `round_goal_model` +7.64 is deck selection.** It disagrees seven-fold with two paired arms (+1.12, +0.41). The held-out set is a deterministic function of (field, seed, lineup, position), so it is a *fixed* subset of decks -- computable without running anything. Compare the held-out decks' goal composition to the rest. | Either the held-out decks are unusual for goal scoring, which explains the gap and closes it, or they are not, and the size of the placement effect becomes an open question worth an arm. |
| 3 | Revisit holdout retirement once a field's point estimate sits inside a detection limit under 2 points. `search_prerank` (190 games, +1.76 vs limit 3.0) and `search_opponent_model` (126, +3.02, p=0.105) are past the 100-game bar but under their own limits, so "agrees with its decision" currently means "is not measurably different from it". | A field is retired only when it is both past the bar and resolved; the 5% tax per field is recorded as accepted until then. |
| 3 | Draw-choice preference from the K=4 bird values, behind a switch. | One 80-game arm; registered ±1 band (the opener lesson says expect a null). |
| 3 | Keep model on the 322 measured bonus-card deals, held out on the engine-builder deals. | Beats `expected_points` 61% pick rate on held-out deals (free on archived games). |
| 3 | `docs/architecture/reusable_board_game_ai_template.md`. | Lists every interface a second game must implement and every module that needs no change. |
| 4 | European expansion as the first content pack + rules module (`docs/rules/expansion_configuration.md` first). | Loader, handlers and scoring behind `ruleset` config; base-game batches bit-identical with the pack off. |

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

- **2026**: 93 updates in `docs/history/project_log_2026.md`

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

## Update: 2026-10-05 - Case study refreshed, and a silently deleted section recovered

`case_study.md` was a 200-line draft from 2026-09-18, structurally complete but
missing the last fortnight. Refreshed to 2026-10-05. Two structural defects
fixed alongside the staleness: the self-play section sat **after** Limitations,
and Limitations still claimed "no self-play" while that section reported it.

What the refresh adds, all of it already settled:

- **Section 2 is now the strongest in the document.** "The opponent barely
  matters at two players" becomes "four kinds of privileged information are each
  worth nothing" — deck order (−2.4, actively harmful), the feeder roll, feeder
  odds (null ×3), and perfect opponent type (+0.00 at 3p). The reading: at
  strong play Wingspan is very nearly a solitaire optimisation problem, with
  interaction running through the shared board rather than anyone's plan.
- **The strict transitive dominance ordering** — the direct answer to "is one
  heuristic dominant", previously absent.
- **The near-tie programme** as a third instance of "observed value is not
  causal value", and the sharpest one: a per-decision effect is not a whole-game
  effect.
- **Section 5**: the evaluator is right where it says it is indifferent
  (+0.062, CI inside the registered band, a third of near-ties exactly zero).
- **Peer-versus-roster margins** (12.4 vs 24.8; 30.3% vs 13.8% inside five
  points), which reframes roster win rates as a poor measure of skill.
- **The method section goes from three rules to four**, adding the powered-band
  rule and the re-read rule.
- **A new section on the data-integrity failure**, written as a credibility
  asset rather than a blemish: what the `game_id` collision did, that it
  flattered the thing being built (95% at 88.3 against the true 73% at 75.6),
  and the two things that caught it — cross-checking against an instrument with
  a different data path, and keeping the durable log separate from the queryable
  one. It also records that the disagreement was visible in September and was
  not acted on.
- **Limitations** now carry the placement-model dispute (+1.12 paired vs +7.64
  from the guardrail, unresolved and not averaged), the fragility of the +1.12
  confirmation, and the 10-deck sampling of several 2p arms.

### A section had been silently deleted, and the case study found it

Verifying every figure in the refresh against the source docs — 42 of them —
turned up two that traced nowhere: the head-to-head matrix's `+32.2` and
`+17.6`. The cause: the head-to-head section was written into
`kpi_taxonomy_findings.md` on 2026-09-27 and **deleted on 2026-09-28** by a
scripted edit that replaced everything between two headings, including the
section that happened to sit between them. Nobody noticed for a week.

Restored, regenerated from the database so the numbers are current rather than
recovered, with a note on the deletion. This is the **second** time an
index-based splice has destroyed content this month (the first was the archive
tool's `write_text`, caught before it ran twice), so
`tests/test_doc_structure.py` now asserts that the expected sections of the KPI
doc, the ledger and the case study are present. Cheap, and it makes the next
such deletion loud.

The lesson worth keeping: **the provenance rule the case study states about
itself is what caught this.** "Nothing here is a claim the ledger does not
carry" is only useful if it is actually checked, and checking it found a
week-old data loss that no test, read or review had surfaced.

## Update: 2026-10-06 - The joint opener, adopted on mechanism before the human games

Alex, preparing the ten human games, observed that a human picks birds, bonus
card and food **in tandem** with all four goals face up, and asked whether the
agent could do the same. It could not: it chose the bonus card **first**, scored
against all five dealt birds including the ones it was about to discard, and
`goal_horizon` defaulted to `"first"`.

**Three of my own claims died in measurement**, which is most of the value here:

| claim | measured |
|---|---|
| the sequencing costs points | **false** — joint enumeration is never strictly better, 0/240; the 37% that differ are **ties** |
| reading all four goals matters | **barely** — changes 1 hand in 240 |
| the fix works by pricing the bonus against the *kept* cards | **mostly false** — the opener keeps all five birds in 570/600 openings, so subset pricing bites in 0.3% |

The 37% tie rate was the clue. `expected_bonus_points` — which prices every card
from its parsed rule and prevalence — was used only for the initial pick, while
the in-loop tradeoff was priced by a hand-written if-chain covering a dozen named
cards and **returning 0 for the rest**. The good scorer saw the wrong card set
and the crude one made the decision.

**Adopted `potential_points_setup_v4`**: enumerate (bonus × keep set × food)
together, price the bonus in-loop with `expected_bonus_points`, drop the crude
term so it is not double-counted, and break the frequent ties with the richer
scorer so joint enumeration cannot be arbitrarily *worse*. Changes the opening in
**9.6%** of hands. The driver is the in-loop pricing: 36 of 41 bonus changes
happen at keep==5, where kept and dealt are the same cards.

### No arm, and that is rule 1 working for the first time in advance

| to measure | games needed |
|---|---:|
| the population effect (~0.2 points) | **21,609** |
| the conditional effect on the 9.6% that change | 972 (~2.7 h), limit 2.08 — which multiplies back to 0.20 |

Rule 1 says: if no affordable sample clears the band, decide on mechanism and say
so. **This is the first time the rule stopped an arm before the compute was
spent** rather than after the fact. Adopted on three grounds: it strictly
dominates under its own scorer by construction; the defect is a plain error, not
a weight judgement; and it gives the agent the coordination the human study needs
for fairness — where ~0.2 points is itself the answer to the fairness objection.
It is **not** a claim the agent is stronger.

Holdout: `setup_policy` now keeps `..._v2`, replacing the control on `..._v3_keep3`
(two holdouts cannot share a field; that question is closed and its control had
accrued 19 games against a 7.5-point limit over six roots).

### The bigger thing this turned up

**The opener keeps all five birds, and so zero starting food, in 95% of hands.**
That is poor play by convention, and forcing three was measured at −1.9 — so
neither extreme is right and the trade between a kept bird and a kept food token
is not understood. Larger than anything in this change and never studied
directly. Registered as the follow-up.

### Study registration tightened

`self_play_opponent_plan.md` now names the configuration the ten games face —
opener, search config, 5/5 seat split, **ten distinct seeds rather than five
played twice** (pairing is right for an agent arm and invalid for a human, who
would have seen the deck), and that standing holdouts stay on so H3 is read on
the holdout-free subset too. This was implicit and changed on the eve of the
study, which is exactly when it needed writing down.

One process note: the first version of this change shipped with a **vacuous
test** — it asserted subset pricing differed from dealt-hand pricing, which never
happens at keep==5. Its vacuity guard is what caught the overstated mechanism.

## Update: 2026-10-08 - Two rules-fidelity audits: hidden power choices, and which egg gets spent

Prompted by Alex on the eight "move to another habitat if rightmost" cards
(Song Sparrow and siblings): *"I can easily see its play potential to be badly
under-utilized."* Correct, and the question generalised much further than the
card.

### `docs/rules/hidden_power_choices.md`

**16 handlers, 112 of the 180 powered base-game birds (62%)** resolve a decision
the rules give the player with a fixed rule inside the transition function. The
largest are `tuck_card` (21 cards: which card to tuck),
`draw_bonus_cards_keep_one` (15), `gain_food_from_birdfeeder` (13: which die),
`lay_egg` (12: which bird) and `play_additional_bird` (10).

Three severities, which should not be lumped together: the heuristic looks
*actively wrong* (`move_bird_habitat` moves to the **emptiest** habitat —
8 cards); it is *sensible but invisible to the search* (most of the rest — the
cost is that the search cannot plan around it, not that it is bad); or an
optional power *fires unconditionally* (`discard_to_tuck`).

Why it is invisible to the whole apparatus: these resolve after the agent has
committed, so **no arm can measure them**, the near-tie instrument cannot see
them, and no manifest records them.

Measured for the movers: **51.6% end the game buried** behind a later bird
(1,030 of 1,998), **99.0% record zero power yield** against 21.1% for other
brown birds, and they are played *later* (round 2.55 vs 2.13). The zero-yield
figure is the mechanism — the move produces no food, eggs or cards, so the
evaluator, which prices birds largely on power output, sees nothing.

**Coverage is not fidelity**, and both the power registry and the case study now
say so. `power_handler_registry.md`'s "complete base-game coverage" is true and
means every power resolves; it was easy to misread as "every power is played
well".

### `docs/rules/egg_spending_fidelity.md`

A guardrail already exists and works: `egg_spend_order` ranks eggs by round-goal
protection, added after traversal order "could spend the very egg an active round
goal was counting", and read as a null in the 2026-09-04 ablation. Verified
working on seed 5.

Three defects found:

1. **The two egg bonus cards are not inputs, and the docstring says they are.**
   `_egg_scoring_protection`'s docstring claims it uses "the current round goal
   **and the player's own bonus cards**"; its signature is
   `(habitat, slot, state)` and the body never mentions them. Demonstrated:
   holding Breeding Manager with birds at [4, 2] eggs, spending 1 takes from the
   **4-egg** bird, destroying the only qualifying bird. Holding Oologist with
   [1, 3], it empties the **1-egg** bird.
   A prediction of mine was wrong and the reason matters: I expected the `-eggs`
   term to protect Oologist by accident. It did not — the round goal decided the
   order, so **the outcome for a bonus card is incidental**, never considered.
   Suggestive but untested: Breeding Manager is the **worst of all 26** bonus
   cards on the archive (0.68 qualifying birds a game, fulfilment 0.082, 391
   games), and its condition is the one this heuristic most readily breaks.
2. **Wild-nest birds are unprotected while their eggs still count.** Goal
   *scoring* treats wild as any nest type in three places; the *protection* does
   a bare string match, so `"[wild]" in "[egg] in [ground]"` is False. **17 of
   180 birds (9.4%)**, 8 nest-type egg goals. A plain inconsistency inside one
   layer, two lines to fix.
3. **Only the current round's goal is protected**, though all four are public
   from setup. Weaker, and the opener's 0.55 later-goal discount is the
   precedent for pricing it.

Not defects, and worth recording as such: end-of-game egg points cost exactly 1
whichever egg goes, egg capacity is neutral-to-good, and
`_place_eggs_on_player_birds` already handles wild nests correctly.

Three tasks added. The case for fixing 1 and 2 is **correctness** — the code
does not do what its own docstring says, and two parts of one layer disagree
about wild nests — rather than measured points; the September ablation suggests
expecting small.

## Update: 2026-10-08 (later) - Card-discard audit completes the fidelity family

`docs/rules/card_discard_fidelity.md`. Third of three on decisions the rules
layer makes for the player, and the comparison between them is the most useful
result:

**The card guardrail considers bonus-card fit. The egg guardrail considers round
goals. Neither considers what the other does.** They were written against
different threats, months apart, and neither learned from the other.

`discard_priority` ranks a card on what it can still do for the player —
`(bonus_fit, has_room, affordable, victory_points, -food_cost)` — after a real
bug: the previous rule was printed points alone and "would discard a cheap bird
that completes a held bonus card in order to keep an unaffordable high-point
bird that will never be played."

### Gap 1, the one that matters: the agent chooses *whether*, never *which*

`_legal_gain_food_actions` calls the chooser **while building the action list**
and bakes the result into every variant. Measured, seed 11, three-card hand, one
forest bird:

- **7 spend-a-card actions offered**
- **1 distinct discard option** (`Cedar Waxwing`), on all seven

Seven food combinations, one card. The search can weigh which *food* to take
against giving up a card, and cannot weigh giving up one card against another.
This is the hidden-choice pattern appearing in the **action space** rather than
inside a power handler, which makes it the most consequential of the three.

### Gap 2: `bonus_fit` is blind to the four count-based bonus cards

It matches a held card's name against a bird's `bonus_card_tags`, so it only
sees conditions that are properties of a *bird*. **Four of 26 bonus cards have
zero tagged birds** because their condition is a property of the *board*:
`Visionary Leader` (cards in hand), `Ecologist` (habitat shape), `Oologist`,
`Breeding Manager`.

`Visionary Leader` is the severe one: it scores **every** card in hand, and
`bonus_fit` is 0 for all of them. Demonstrated — the discard is identical
holding `Cartographer`, `Historian` or `Visionary Leader`. The term that exists
to protect bonus cards is identically useless on the one card where every
discard is a direct loss. For the other 22 it works; `Historian` alone has 20
tagged birds.

### Gap 3, and a correction to the obvious framing

`discard_priority(card, player, state=None)` accepts a state, every caller
passes one, and **the body never uses it**. The tempting write-up is "symmetric
to the egg gap" — it is not, and I checked before claiming it. **None of the 16
base-game round goals involves cards or tucked cards**; they are birds in
habitats, eggs, or total birds. There is nothing card-shaped to protect.

What it does cost is narrower: four goals count birds in a named habitat or in
total, so when the goal is `[bird] in [forest]` discarding your only affordable
forest bird is worse than discarding a wetland bird, and the proxies
(`has_room`, `affordable`) cannot tell. Also recorded: one call site omits
`state` where four pass it — harmless while unused, a trap the moment it is not.

Not gaps, worth recording: **tucking is not losing** (a tucked card is 1 VP, so
`tuck_card` converts a card into a point), the tuple ordering is sensible, and
the agent can decline the action entirely — which makes the pre-chosen card more
load-bearing rather than less.

Two tasks added, and gap 2 is deliberately merged with the egg audit's defect 1:
both are "the protection cannot see board-condition bonus cards", so one fix
serves both and doing them separately costs twice.

## Update: 2026-10-09 - Human play shows the table at setup

### What changed

Alex, playing `flows/human_vs_agent.py --seed 101 --seat 1`, could not see the
round goals, birdfeeder or tray before choosing an opening, nor which agent he
was playing, nor what the opponent kept. Fixed on branch `human-play-fixes`:

- `InitialSelectionContext` carries `birdfeeder_faces` and `seat_agent_ids`;
  the runner sets every seat's agent id before any seat chooses.
- `HumanCliAgent` prints a setup screen (seats, R1–R4 goals with green-side
  points, feeder dice, full tray cards) before the keep prompt, and accepts `0`
  to keep no birds.
- New runner hook `observe_setup_complete(state)`, called once after all
  openings are applied: the human sees each seat's birds-kept count and starting
  food. Opponent card names stay hidden. Observation only, so replay is
  unchanged.
- `human_vs_agent.py` prints the opponent and its search budget at start; its
  `--help` lists every opponent with a description and explains what is shown.
- `scripts/inspect_setup.py` reproduces every seat's dealt and kept opening for
  a seed without playing (the method used to answer what p2 kept).

### Why it matters

The human-trace study compares human and agent openings. A human choosing
without the goals and feeder in view would make an uninformed choice, not a human one.

### Decision

Seed 101 is spent for the study: its opponent hand has been inspected. In that
seed `potential_points_p2` (`potential_points_setup_v4`) kept all five birds and
no food. That is the registered keep-five follow-up from 2026-10-06, reproduced
here (286/300 openings keep five at seeds 1–300), not a new defect.

### Follow-up tasks

- Show the opponent's last action at the start of the human's turn (seat 2 sees
  the board after the agent has moved, but not what it did).

