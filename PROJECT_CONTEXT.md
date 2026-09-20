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
3. The opponent-model programme **against the scripted roster is closed**
   (2026-09-20): five models within ±1 at 2p; at 3p greedy's +2.1 (p=0.07)
   is unexplained by family accuracy, within-family pick, or a competent
   public-value family (all null), and the pooled holdout points the other
   way. The question now runs in **self-play**: A1 (mirror baseline) gives
   75.3 at 2p / 78.3 at 3p and a first seat signal (seat 1 +5.1, win 0.575
   at 2p, p=0.051); A2 (greedy study seat in the mirror) is in flight.
4. Standing holdouts (five fields) keep every decided switch's losing side
   alive at 5% (`docs/experiments/standing_holdouts.md`).
5. Card-choice decisions remain the parked place to spend evidence: the
   measured opener showed play value is not keep value (−1.9); bonus-card
   choice is worth 6.4 and `expected_points` gets 61% of it.
6. Keep the reusable template honest: holdouts, profiling, paired arms,
   replay hashing and the rules/agents/telemetry split know nothing about
   Wingspan. The template doc and the expansion configuration doc are the
   two unwritten architecture pieces.

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
| Baseline | `artifacts/rr_belief_opp` at `e218d13` is the default agent's baseline (2026-09-16). | Belief opponent model adopted for cost; every later arm pairs against it. | The next adopted change re-baselines. |
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
| 1 | Read A2 (`mirror_2p_greedy`, `mirror_3p_greedy`, launched 2026-09-20 ~12:40, ~3.5 h) with `arm_contrast --agent potential_points@1` against `mirror_2p` / `mirror_3p`. | Registered 2p +1 to +3, 3p +2 to +4 for the greedy study seat. A 2p null closes the two-player opponent question for good; pool A1+A2 for the seat effect (2p seat 1 +5.1 at p=0.051 needs the second 80). |
| 1 | A3 (denial term in the mirror) and, if A2 is positive, a `greedy`-cost-aware production check. | A3 registered +1 to +3; null means denial is not worth a search node even against a planner. |
| 2 | Read the pooled holdout guardrail now that six more default-agent roots exist. | `holdout_guardrail.py` over every default-agent root; any field over 100 games that agrees with its decision is retired. |
| 2 | Human-trace study H1–H3: Alex plays ten seat-swapped games with `flows/human_vs_agent.py` (built 2026-09-20). | Ten games archived and replay-valid; belief log loss on the human scored against every roster kind (`fit_response_model.py` on `artifacts/human`); H2 disagreement list through the viewer. |
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
- `docs/rules/expansion_configuration.md` — nothing beyond the base game is
  encoded yet; the content-pack plus rules-module decision stands.
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

## Update: 2026-05-03 - Context docs re-scoped to Wingspan AI

### What changed
Reworked `AGENTS.md`, `CLAUDE.md`, `COMPANY_CONTEXT.md`, and `PROJECT_CONTEXT.md` away from Savepoint Analytics platform context and toward the Wingspan AI research project.

### Why it matters
Future AI sessions should now treat this repository as a separate applied ML and simulation case study focused on Wingspan, Bayesian game theory, strategy discovery, and reusable board-game NPC AI templates.

### Decision
Keep the useful working style from the Savepoint docs: practical progress, reusable assets, simple architecture, clear documentation, and small tasks with success criteria. Remove Savepoint-specific client platform, pricing, website, and KPI-taxonomy assumptions.

### Follow-up tasks
- [ ] Create the initial source package and folder structure.
- [ ] Audit `data/raw/wingspan-card-list.xlsx` for schema completeness.
- [ ] Draft `docs/architecture/simulator_architecture.md`.
- [ ] Draft `docs/events/simulation_event_taxonomy.md`.

## Update: 2026-05-03 - Initial package structure, content schema, and workbook audit

### What changed
Created the initial Python package structure under `src/wingspan_ai/`, added working folders for `data/`, `docs/`, `notebooks/`, `analysis/`, `tests/`, and `flows/`, and documented the intended structure in `docs/architecture/project_package_structure.md`.

Added Pydantic content schemas in `src/wingspan_ai/content/schemas.py` for bird cards, bonus cards, round goals, food costs, habitats, powers, ruleset metadata, content packs, rules modules, and content catalogs.

Added a reproducible workbook audit utility in `src/wingspan_ai/content/workbook_audit.py` and documented findings in `docs/rules/wingspan_card_list_audit.md`.

### Why it matters
The project now has an importable package boundary and an explicit content model before rules-engine work begins. The workbook audit identifies which source fields are already usable and which fields need normalization or hand-authored rule support before typed loading can be trusted.

### Decision
Represent expansions as `ContentPack` values and game-changing expansion behavior as separate `RulesModule` values. Represent unsupported powers and scoring logic explicitly with `PowerImplementationStatus` so v1 experiments can filter or report unsupported mechanics instead of silently ignoring them.

### Follow-up tasks
- [ ] Build the base content loader from `data/raw/wingspan-card-list.xlsx` into typed content objects.
- [ ] Add normalization mappings for workbook set labels, power colors, beak directions, variable wingspans, blank nest types, and duet/map goals.
- [ ] Draft `docs/architecture/simulator_architecture.md`.
- [ ] Define base-game state models.

## Update: 2026-05-03 - Data and rule encoding recommendations documented

### What changed
Added `docs/rules/data_and_rule_encoding_recommendations.md` to answer the open data/rules questions about workbook sufficiency, power-handler mapping, expansion representation, v1 fidelity, stub-safe edge cases, and rulebook/source traceability. Linked the new note from `docs/README.md`, `docs/rules/game_content_schema.md`, and `docs/rules/wingspan_card_list_audit.md`.

### Why it matters
The detailed recommendations now live in the rules docs instead of only in chat or `PROJECT_CONTEXT.md`. Future implementation work can use the note as the source of truth for how to translate raw card data into executable simulator rules.

### Decision
Keep `PROJECT_CONTEXT.md` concise and use dedicated docs files for durable technical recommendations. Represent expansions as content packs plus rules modules, and require power/rule implementation status so unsupported mechanics are explicit.

### Follow-up tasks
- [ ] Create `docs/rules/power_handler_registry.md`.
- [ ] Add source-reference fields to rule and power handler metadata.
- [ ] Update the content loader to preserve raw `Power text` and assign implementation status.
- [ ] Let simulation experiments filter cards by power implementation status.

## Update: 2026-05-03 - Base loader, state model, rules skeleton, and random agent added

### What changed
Added a base workbook content loader in `src/wingspan_ai/content/loader.py`, base-game state models in `src/wingspan_ai/state/models.py`, legal action models in `src/wingspan_ai/rules/actions.py`, base setup/legal-action/transition/scoring functions in `src/wingspan_ai/rules/base_game.py`, and a seeded `RandomLegalAgent` in `src/wingspan_ai/agents/random_legal.py`.

Drafted `docs/architecture/simulator_architecture.md` to document setup, legal actions, transitions, scoring, powers, randomness, and public/private state boundaries.

Added first tests covering core content loading, setup, playing a bird, gaining food, laying eggs, drawing cards, round transition, final score skeleton, and random legal agent selection.

### Why it matters
The project now has the first runnable base-game loop primitives. The simulator is not full-fidelity yet, but content loading, typed state, legal actions, deterministic transitions, and a baseline agent can be tested and extended without mixing rules logic into notebooks or future ML code.

### Decision
Keep v1 power, bonus-card, and round-goal scoring behavior explicit but unimplemented. The loader preserves raw power text and assigns implementation status; the scoring skeleton returns zero for unsupported scoring categories until handler registries are added.

### Follow-up tasks
- [ ] Add a single-game runner that loops agents through full random-vs-random games.
- [ ] Add telemetry event contracts for setup, legal actions, selected actions, and resolved actions.
- [ ] Add a power-handler registry with source references and implementation status.
- [ ] Implement initial hand/food selection.
- [ ] Add first bonus-card and round-goal scoring handlers.

## Update: 2026-05-04 - Telemetry, runner, ingestion, orchestration, tracking, and analysis skeletons added

### What changed
Added versioned simulation event contracts in `src/wingspan_ai/telemetry/events.py`, a draft FastAPI ingestion app in `src/wingspan_ai/telemetry/api.py`, a single-game runner in `src/wingspan_ai/simulation/runner.py`, and a deterministic immediate-score `GreedyBaselineAgent` in `src/wingspan_ai/agents/greedy.py`.

Added a Prefect-compatible seeded batch flow in `flows/simulation_batch.py`, an MLflow logging helper in `src/wingspan_ai/experiments/mlflow_tracking.py`, reusable analysis helpers in `analysis/simulation_summary.py`, and a first simulation-review notebook in `notebooks/first_simulation_analysis.ipynb`.

Documented telemetry and storage design in `docs/events/simulation_event_taxonomy.md` and `docs/events/postgresql_event_table_design.md`.

### Why it matters
The project can now run full seeded random-vs-greedy games, emit event traces, summarize outcomes and action frequency, and has clear extension points for API ingestion, database persistence, Prefect orchestration, and MLflow tracking. These are still foundation skeletons, but they connect simulator behavior to the analytics and experiment architecture.

### Decision
Keep FastAPI, Prefect, and MLflow integrations optional/lazy so the core simulator and rules tests remain runnable before those heavier dependencies are installed. Store raw events first, then derive analysis tables and replay artifacts from validated telemetry.

### Follow-up tasks
- [ ] Add durable database ingestion from the FastAPI app into PostgreSQL.
- [ ] Add public state snapshot artifacts keyed by `public_state_ref`.
- [ ] Add batch-level tournament summaries and matchup metrics.
- [ ] Install or lock dev/service/orchestration/tracking dependencies for pytest, ruff, FastAPI, Prefect, and MLflow.
- [ ] Implement first power handlers, bonus-card scoring handlers, and round-goal scoring handlers.

## Update: 2026-05-04 - Strategy bots, tournament runner, rollout agent, and research docs added

### What changed
Added scripted strategy archetype agents in `src/wingspan_ai/agents/archetypes.py`, a first Monte Carlo rollout agent in `src/wingspan_ai/agents/monte_carlo.py`, and a seeded tournament runner with matchup summaries in `src/wingspan_ai/simulation/tournament.py`.

Setup now applies a deterministic v1 initial hand/food selection approximation: three birds, one bonus card, and two food tokens biased toward kept bird costs. The runner now returns public state snapshots keyed by `public_state_ref`.

Added a power-handler registry skeleton in `src/wingspan_ai/rules/power_registry.py` and documented it in `docs/rules/power_handler_registry.md`. Added first narrow scoring handlers for `Bird Feeder`, `Backyard Birder`, `Bird Counter`, and simple count-based habitat round goals.

Added optional PostgreSQL event persistence in `src/wingspan_ai/telemetry/postgres.py`, plus `requirements-dev.txt` and `requirements-services.txt` to lock the intended dev/service dependency groups without installing them in this environment.

Drafted `docs/agents/baseline_agents.md`, `docs/agents/bayesian_belief_model_plan.md`, and `docs/experiments/case_study_outline.md`.

### Why it matters
The project now has interpretable strategy variants, a rollout planning baseline, and a tournament layer that can produce matchup summaries. The Bayesian modelling direction and case-study narrative are documented, so future modelling work has a clear target instead of drifting toward generic RL.

### Decision
Keep these agents intentionally simple until rule fidelity improves. Archetype bots are for behavioural signatures; Monte Carlo is for value-estimation plumbing; tournament metrics are useful for smoke tests but should not be treated as strategic findings until powers, scoring, setup, and workbook content are fully restored and validated.

### Follow-up tasks
- [x] Restore or relocate `wingspan-card-list.xlsx`; workbook-backed tests now run from `data/raw/`.
- [ ] Replace deterministic setup approximation with agent-selectable initial hand/food choices.
- [ ] Expand bonus-card and round-goal scoring beyond the first narrow handlers.
- [ ] Implement high-volume base-game power handlers from the power registry.
- [ ] Persist public state snapshots as artifacts alongside simulation events.
- [ ] Add real PostgreSQL integration tests once a local service is available.

## Update: 2026-05-05 - Setup choices, first power resolution, and snapshot artifacts improved

### What changed
Added `InitialSelection`, `choose_default_initial_selection`, and `apply_initial_selection_choice` in `src/wingspan_ai/rules/base_game.py`. The single-game runner now deals full setup hands, assigns agent IDs, asks agents for `choose_initial_selection(player)` when available, and otherwise applies the default selection.

Added first executable power resolution scaffolding for simple `Gain 1 [food]` and `Draw 1 [card]` text templates. White powers are checked when a bird is played, and brown powers are checked when the matching habitat action is activated.

Added `src/wingspan_ai/content/sample_catalog.py` so tests and smoke flows can run without the missing source workbook. Updated `flows/simulation_batch.py` to use the workbook when present and the sample catalog otherwise.

Added `src/wingspan_ai/simulation/artifacts.py` to write `outcome.json`, `events.jsonl`, and `public_state_snapshots.json` artifacts for a simulation result.

### Why it matters
Setup is now an explicit policy boundary instead of hidden simulator behavior. This makes it possible to later compare opening-hand strategies and lets stronger agents reason about keep/discard and starting food choices. Power resolution and snapshot artifacts are still narrow, but they move the simulator closer to replayable, inspectable games.

### Decision
Use the synthetic sample catalog only for tests and smoke runs when `data/raw/wingspan-card-list.xlsx` is absent. Strategic experiments should use the real workbook.

### Follow-up tasks
- [x] Restore `wingspan-card-list.xlsx` or update loader tests to the new canonical source path.
- [ ] Add setup-choice telemetry events.
- [ ] Convert power text template matching into registry-backed handler keys during content loading.
- [ ] Add exact replay hashes and RNG draw records.
- [ ] Add database integration tests once PostgreSQL is available locally.

## Update: 2026-05-05 - Workbook restored under data/raw and tests re-enabled

### What changed
The source workbook is restored at `data/raw/wingspan-card-list.xlsx`. Updated the content loader default path, workbook audit default CLI path, tests, flow defaults, and docs to use this canonical raw-data location. The loader also supports `WINGSPAN_CARD_WORKBOOK` as an override.

### Why it matters
Workbook-backed loader and audit tests now run against the real content again instead of skipping. Smoke flows use real workbook content by default and only fall back to the sample catalog when the workbook is absent.

### Decision
Use `data/raw/wingspan-card-list.xlsx` as the canonical local workbook path. Keep Google Drive or other external storage as an archive/source-of-truth backup, but keep local simulation and tests file-based for reproducibility.

### Follow-up tasks
- [ ] Decide whether `data/raw/wingspan-card-list.xlsx` should be committed, Git-LFS tracked, or gitignored before public release.
- [ ] Add checksum/version metadata for the workbook.
- [ ] Add setup docs for restoring the workbook from Google Drive if the repo is cloned fresh.

## Update: 2026-05-13 - Core economy rule fidelity expanded

### What changed
Extended the base-game rules loop so legal actions now model habitat action scaling, multi-food and multi-card choices, optional player-mat conversions, deterministic birdfeeder rerolls, right-to-left brown power activation, first pink reaction hooks, first-player rotation, end-of-round tray refresh, competitive round-goal scoring, and broader base-game bonus-card scoring.

Updated greedy and archetype baselines so food choices are biased toward visible hand deficits instead of treating every food die as equal. Added regression tests for habitat scaling, rerolls, brown activation order, pink birdfeeder food preference, competitive goal scoring, and expanded bonus scoring.

### Why it matters
The simulator is still not full Wingspan fidelity, but the core economy loop now better preserves the real tradeoffs between food, cards, eggs, habitat engines, round goals, and final scoring. Smoke simulations are more useful for regression and baseline comparison, though results should still be labelled as early until more bird powers are implemented and audited.

### Decision
Keep rule-fidelity improvements in the rules engine and action models, with baseline agents consuming richer legal actions rather than hardcoding shortcuts. Treat high-volume powers and scoring handlers as the next blocker before strategy claims.

### Follow-up tasks
- [ ] Convert supported power text templates into registry-backed handler keys during content loading.
- [ ] Expand brown, white, and pink power handlers beyond the current deterministic templates.
- [ ] Add setup-choice telemetry and richer agent decision summaries.
- [ ] Add exact replay hashes and explicit RNG draw records.
- [ ] Audit competitive round-goal scoring against the local rulebook PDFs before publishing results.

## Update: 2026-05-16 - Replay telemetry and registry-backed power slice added

### What changed
Added registry-backed power text classification during workbook loading and runtime resolution. The first expanded handler slice now covers predator hunt approximations, discard-egg-to-gain-food, discard-food-to-tuck, fixed food from supply, and the existing draw/lay/tuck/cache/pink hooks through stable handler keys.

Added replay/debug support with full-state hashes, RNG draw records on stochastic rerolls and predator approximations, `replay_debug.json` artifacts, setup-selection telemetry, and emitted agent decision summaries. Added `src/wingspan_ai/rules/scoring_audit.py` plus `docs/rules/scoring_handler_audit.md` to expose bonus-card and round-goal scoring coverage.

### Why it matters
Simulation traces are now easier to audit: action events carry before/after state hashes, stochastic approximations are recorded, and setup choices are visible as private telemetry. Power and scoring support is still incomplete, but unsupported scoring/power areas are easier to identify and avoid overclaiming.

### Decision
Keep moving power behavior behind stable registry handler keys rather than expanding ad hoc text matching. Treat replay hashes and decision summaries as required smoke-batch telemetry from this point forward.

### Follow-up tasks
- [x] Add a replay validator that reconstructs event traces and checks state hashes.
- [x] Add exact deck draw records if private full-game replay becomes required.
- [x] Expand opponent-choice, "all players may", and deck-search power handlers.
- [x] Add per-handler rulebook/source-section references for scoring and powers.
- [ ] Add exact rulebook page numbers once PDF page mapping is audited.
- [ ] Add scoring audit output to batch/tournament summaries.

## Update: 2026-05-16 - Replay validator and human CLI path added

### What changed
Added `validate_simulation_replay` in `src/wingspan_ai/simulation/replay.py` to reconstruct setup and action transitions from telemetry, then verify `state_hash_before` and `state_hash_after` on every resolved action. Added exact deck draw records for direct deck draws, tray replenishment, round-end tray refresh, tuck-from-deck powers, and deck-search powers.

Expanded handler metadata with rulebook path and source-section fields. Added handler coverage for all-player gain-food, all-player lay-egg, and deck-search tuck-by-wingspan templates. Added `HumanCliAgent` and `flows/human_vs_greedy.py`, confirming a human can participate through the same legal-action interface as automated agents.

### Why it matters
The simulator can now audit a telemetry trace by replaying it, and human play is feasible without a separate UI because policies are already pluggable. This makes manual spot-checking and future human-vs-agent experiments possible while preserving the same rules boundary.

### Decision
Treat human play as a local terminal workflow for now. A richer UI can wait until the rules engine is more complete.

### Follow-up tasks
- [ ] Add a friendlier action renderer for human play instead of raw `LegalAction` JSON.
- [ ] Add exact rulebook page numbers for each handler after PDF page mapping.
- [ ] Add scoring audit output to batch/tournament summaries.

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


## Update: 2026-08-24 - Persistence regression, workload namespaces, and batch manifests

### What changed
Added an opt-in live persistence regression in `tests/test_persistence_integration.py`, gated by
`RUN_DB_INTEGRATION=1`. It runs one seeded game and verifies its PostgreSQL run, game, event, and
score rows plus its MinIO game artifacts and batch manifest.

Simulation batches now require a `smoke`, `experiment`, or `production` workload namespace and use
unique batch IDs. Local artifacts and MinIO keys follow
`<root-or-prefix>/<batch_kind>/<batch_label>/<batch_id>/`. Game IDs are batch-scoped to prevent
repeated seeds from overwriting earlier persisted game summaries.

Each batch writes `batch_manifest.json` with batch timing, source catalog, seeds, rulesets, outcomes,
event counts, PostgreSQL insertion results, local paths, and MinIO URIs.

### Why it matters
Persisted smoke runs can now be checked end to end, and every batch has a durable index joining its
local files, object-storage objects, and database run IDs. Workload namespaces keep exploratory and
production artifacts from becoming indistinguishable.

### Decision
Keep the normal test suite service-independent. Run the gated persistence test before sizeable
persisted batches or after schema, artifact, environment configuration, or object-storage changes.
Use `smoke` for regression batches, `experiment` for analysis inputs, and `production` only for
validated repeatable workloads.

## Update: 2026-08-26 - Replay-gated batches and rule audit summaries

### What changed
Checkpointed the PostgreSQL/MinIO persistence baseline in git before adding the next layer.

Simulation batches now run `validate_simulation_replay` after each seeded game and before artifact
writing, PostgreSQL persistence, or MinIO upload. Replay validation is required by default and each
game result plus `batch_manifest.json` records checked transition counts and validation errors.

Added combined rule-fidelity audit output for batches and tournaments. The audit reports power
handler classification/implementation coverage, unsupported power cards, handler source references,
bonus-card scoring coverage, round-goal scoring coverage, unsupported scoring items, and scoring
source references.

### Why it matters
Persisted batches are now labelled by trace validity and current rule coverage. This prevents
invalid replays or unsupported rule areas from being silently mixed into analysis datasets.

### Decision
Keep replay validation enabled by default for smoke, experiment, and production batches. Disable it
only when deliberately capturing malformed traces for debugging. Treat rule-audit summaries as
required metadata for any batch or tournament used in strategy analysis.

### Next
- [ ] Create analysis-ready PostgreSQL views or reusable SQL over decision, setup, power, score,
      replay-validation, and batch-outcome telemetry.
- [ ] Run a labelled 25-game persisted smoke batch and inspect replay/audit summaries before larger
      experiments.
- [ ] Use audit frequencies from that smoke batch to prioritize the next power/scoring fidelity sprint.

## Update: 2026-08-26 - YAML policy guardrails added

### What changed
Added `src/wingspan_ai/agents/guardrails.py`, a YAML-configured guardrail layer that evaluates
state/action predicates over legal actions and can exclude, penalize, or boost choices before an
agent selects. The rules engine remains the only source of legal actions.

Added `GuardrailedAgent`, which wraps agents exposing `select_action` and delegates final selection
over the guardrail-pruned candidate set. Strategy archetype and Monte Carlo agents now expose
`select_action` so they can be constrained by guardrails as well as used directly.

Added `configs/guardrails/base_heuristic.yaml` with first base-game guardrails for food deficits,
low egg capacity, scarce eggs, small hands, and early engine building. Batch flows accept
`guardrail_config_path` and record guardrail config metadata in manifests. Decision summaries emit
rule-hit counts, candidate counts, selected modifiers, selected guardrail reasons, and wrapped-agent
summaries.

### Why it matters
Guardrails provide explainable strategy constraints without contaminating legal-action generation.
They make it practical to narrow obvious low-value choices before deeper heuristic, rollout, or
Bayesian selection while preserving telemetry that explains how the action set was narrowed.

### Decision
Use guardrails as policy-level configuration, not rules-engine logic. Prefer boosts and penalties
over hard exclusions until simulation evidence shows an action class is consistently dominated.
Keep fail-open enabled by default so misconfigured guardrails do not dead-end a game.

### Next
- [ ] Run paired smoke batches comparing plain greedy and guardrailed greedy under fixed seeds.
- [ ] Add SQL/Python analysis for guardrail rule hits, excluded action counts, and score impact.
- [ ] Promote only evidence-backed guardrails from exploratory configs into reusable defaults.


## Update: 2026-08-28 - Potential-points greedy agent added

### What changed
Added `PotentialPointsAgent` in `src/wingspan_ai/agents/potential_points.py` as a new greedy-family baseline. It keeps the immediate-score greedy baseline intact, but evaluates legal actions by the estimated final-score potential of the resulting state. The first value breakdown includes realized score, playable bird potential, food/card/egg conversion potential, played engine power potential, bonus-card progress, round-goal pressure, endgame conversion value, and dead-resource penalties.

The agent emits decision summaries with selected value delta, realized score delta, the selected state's potential breakdown, top alternatives, and whether endgame search was used. It also includes a shallow final-turn search mode for the last five turns so late-game choices favor concrete point conversion over dead food or dead cards.

### Yellow, white, and timing-power plan
- Brown powers: value expected repeated habitat activations based on remaining turns and visible conversion demand.
- Pink powers: value passive opponent-turn triggers from estimated remaining opponent activity.
- Teal powers: value end-of-round triggers by the number of remaining round ends.
- Yellow powers: value end-of-game powers as one-shot final scoring conversions if the card can be played before game end; exact yellow handlers remain future work.
- White powers: value one-shot when-played effects for cards in hand; already-resolved white powers are captured through `apply_action` deltas.

### Why it matters
This addresses the strategic gap where food, cards, egg capacity, passive powers, bonus-card progress, and round-goal positioning should matter before they become realized points. It gives the project an interpretable bridge between the current immediate greedy baseline and heavier rollout/Bayesian/search agents.

### Next
- [ ] Run fixed-seed comparison batches: random vs immediate greedy, random vs potential-points greedy, and random vs guardrailed potential-points greedy.
- [ ] Replace text-based power valuation with registry-backed valuation handlers for common brown, pink, teal, yellow, and white patterns.
- [ ] Upgrade final-five-turn search to simulate all remaining player turns and completed round-goal scoring, not only same-player continuations.
- [ ] Calibrate potential weights from smoke-batch telemetry and card/action outcome summaries.

## Update: 2026-08-28 - Potential-points smoke comparison helper added

### What changed
Ran fixed-seed smoke comparisons for random vs immediate greedy, random vs potential-points greedy, and random vs guardrailed potential-points greedy across seeds 1-5. Added `analysis/simulation_batch_comparison.py` to summarize batch manifests, player-two win rate, score margin, action mix, selected value deltas, endgame-search usage, and guardrail candidate counts from local artifact events.

Started replacing potential-points text-token power valuation with registry-backed handler-key valuation. The evaluator now prefers explicit or classified `handler_key` values for common gain-food, draw-card, lay-egg, tuck, cache, predator, discard, all-player, and deck-search handlers before falling back to text-token valuation for unclassified powers.

### Why it matters
The project now has a repeatable way to compare baseline smoke batches without manually inspecting raw JSON artifacts. The first 5-seed comparison is encouraging for `PotentialPointsAgent`, but it is still smoke evidence only and should not be treated as a strategic finding until larger controlled batches and rule-fidelity filters are in place.

### Follow-up tasks
- [ ] Promote the comparison helper into a notebook or report artifact once batch sizes are large enough to interpret.
- [ ] Add compute-time telemetry for agent decision summaries before scaling potential-points tournaments.
- [ ] Extend registry-backed valuation into dedicated value-handler modules with tests per handler key.
- [ ] Run larger fixed-seed tournaments against immediate greedy, archetypes, Monte Carlo, and guardrailed variants after power/scoring coverage improves.

## Update: 2026-08-28 - Decision timing and 10-seed baseline matrix completed

### What changed
Added runner-level decision-time telemetry to every `agent_decision_summary`: `action_selection_elapsed_ms`, `decision_summary_elapsed_ms`, and `decision_total_elapsed_ms`.

Expanded `flows/simulation_batch.py` so player two can use `random_legal`, `greedy_immediate`, `potential_points`, six `archetype_*` agents, or `monte_carlo_rollout`, with guardrails able to wrap any selected variant.

Ran a 10-seed smoke matrix against random player one for random, immediate greedy, potential-points, guardrailed greedy, guardrailed potential-points, six archetypes, and Monte Carlo. Documented findings in `docs/experiments/potential_points_matrix10_smoke.md`.

### Why it matters
The potential-points win pattern looks behaviourally plausible at smoke scale: it plays far more birds than immediate greedy while maintaining eggs, round goals, cached food, and tucked cards. It does not appear to be driven by one obvious scoring category. The main caution is still simulator fidelity: the current power audit reports 49 unsupported powered cards and about 71.8% implemented power coverage.

Decision-time telemetry exposed the scaling bottleneck. Potential-points averaged about 407 ms per player-two decision, guardrailed potential-points about 153 ms, and Monte Carlo about 11 seconds. A 50-100 seed matrix should wait for compute-budget controls, smaller rollout settings, or faster action evaluation.

### Follow-up tasks
- [x] Add compute-budget controls for `MonteCarloRolloutAgent` in batch configuration.
- [ ] Reduce `apply_action` deep-copy cost for lookahead-heavy agents.
- [ ] Compare potential-points against non-random opponents in smaller matchup matrices.
- [ ] Tune guardrails separately for potential-points instead of reusing the immediate-greedy guardrail config unchanged.

## Update: 2026-08-28 - Lookahead budgets, profiling, and net-value response scaffold

### What changed
Added Monte Carlo budget controls: `max_decision_time_ms`, `rollout_count`, `rollout_depth`, and `min_rollouts_per_action`, with telemetry for completed rollouts and budget exhaustion.

Added `analysis/apply_action_profile.py` and profiled a workbook-backed initial state. `GameState.model_copy(deep=True)` averaged 7.887 ms, full `apply_action` averaged 8.468 ms, and deep copy accounted for about 93.1% of transition time.

Added `NetValueOpponentResponseAgent` in `src/wingspan_ai/agents/net_value.py` and documented the template in `docs/agents/net_value_opponent_response_agent.md`. The first scaffold estimates score-margin impact after the next opponent response and includes simple tray-card and birdfeeder-food denial value across forest/woodland, grassland/plains, and wetland/coastal dimensions.

### Why it matters
The project now has explicit compute controls before any 50-100 seed lookahead matrix. The profile shows that faster speculative search requires reducing full-state deep-copy cost or pruning candidate actions before expensive evaluation.

The net-value response template captures the competitive idea Alex raised: choose moves based on expected margin and opponent reaction, not only self-score maximization. The first implementation is intentionally marked `full_state_oracle_v0`; it is useful for plumbing and controlled ablations, but should move to public observations plus belief state before claim-grade experiments.

### Follow-up tasks
- [x] Add strict candidate sampling for Monte Carlo when a hard wall-clock cap matters more than one rollout per legal action.
- [x] Replace full-state opponent scoring in `NetValueOpponentResponseAgent` with public observation plus belief estimates.
- [ ] Design controlled fixtures for pink/passive trigger liability, tray/food denial, engine blocking, and round-goal blocking before implementation; each fixture should be well reasoned and backed by a hypothesis/data plan.
- [x] Prototype a lower-copy transition path for speculative evaluation.

## Update: 2026-08-29 - Strict lookahead budgets and public-belief opponent scoring

### What changed
Added `apply_action_in_place` as an explicit lower-copy transition path for callers that already own an isolated speculative branch. Normal simulator execution still uses `apply_action`, which deep-copies before mutating so existing callers remain protected.

Updated `MonteCarloRolloutAgent` with strict breadth control through `max_candidate_actions` and default `min_rollouts_per_action=0`. Under tight wall-clock budgets, the agent may stop before launching any rollout; unevaluated candidates receive static fallback scores and telemetry marks `used_static_fallback=true`.

Replaced `NetValueOpponentResponseAgent` opponent scoring with `public_observation_belief_v0`. Opponent potential, denial, and next-response estimates now use public boards, public tray cards, birdfeeder dice, hand counts, bonus-card counts, round goals, visible resources, and a first heuristic belief model rather than hidden opponent hands or bonus cards. The acting player's own value still uses their private hand, which matches the acting player's information.

### Profile and smoke checks
Fresh `analysis/apply_action_profile.py --iterations 25` results on seed 1:

- Legal action generation: 0.044 ms.
- `GameState.model_copy(deep=True)`: 8.092 ms.
- Full `apply_action`: 9.960 ms.
- Branch copy + `apply_action_in_place`: 8.101 ms.
- Isolated in-place transition: 0.062 ms.

One-seed smoke probes with replay validation passed:

- Strict Monte Carlo: `rollout_count=4`, `rollout_depth=6`, `max_decision_time_ms=75.0`, `max_candidate_actions=4`; player 2 won 66-35.
- Public-belief net value: `max_candidate_actions=5`, `max_opponent_response_actions=3`; player 2 won 66-38.

These are plumbing checks only, not strategic evidence.

### Why it matters
The project now has a hard-throughput option for Monte Carlo and a safe way to avoid repeated deep copies once a speculative branch is already isolated. The net-value agent also no longer relies on simulator-private opponent state, which is a necessary step before using blocking or opponent-response results as research evidence.

### Follow-up tasks
- [x] Add a calibration harness for `public_observation_belief_v0` against observed action choices and batch outcomes.
- [ ] Extend lower-copy branch evaluation into potential-points and net-value search loops where branch ownership is clear.
- [ ] Design, but do not yet implement, controlled blocking fixtures with explicit hypotheses, required simulator support, and data needed to validate the expected direction.
- [ ] Run a small 5-10 seed sanity matrix after calibration, then decide whether a 50-100 seed matrix is justified.

## Update: 2026-08-29 - Public-belief calibration harness added

### What changed
Added `analysis/net_value_calibration.py`, which reads simulation batch manifests and pairs each `NetValueOpponentResponseAgent` prediction with the opponent's next observed `action_selected` event. Net-value decision telemetry now includes ranked public response candidate values so calibration can report exact top-action matches and whether the observed action was inside the public candidate set.

Fixed a round-boundary edge case where the response estimator could label the acting player as the next opponent when turn order returned to the same player at a new round. The estimator now skips self-turns and targets the next actual opponent with available action cubes.

Documented the first calibration readout in `docs/experiments/public_belief_calibration.md`.

### First smoke readout
Three-seed public-belief calibration probe against random player one:

- Predictions matched to observed next actions: 78.
- Exact action-family matches: 13.
- Exact match rate: 16.7%.
- Observed action in uncapped public candidate set: 100.0%.
- Average observed candidate rank: 2.90.
- Predicted action mix: 39 lay-eggs, 39 play-bird, 0 draw-card, 0 gain-food.
- Observed random action mix: 35 draw-card, 18 gain-food, 8 lay-eggs, 17 play-bird.
- Player two win rate: 100.0%, with average final margin +32.33.

### Interpretation
This is calibration plumbing, not strategy evidence. Against a random legal opponent, exact best-response prediction should be low. The important finding is that the public response candidate template covers observed actions when uncapped, but the top-value heuristic is biased toward play-bird and lay-eggs. Draw-card and gain-food response likelihood need explicit probability calibration before the agent should drive controlled blocking experiments.

### Follow-up tasks
- [ ] Add an opponent-response probability layer so net-value can use expected response value, not only best response.
- [ ] Calibrate response-family probabilities separately for random, greedy, potential-points, archetype, and net-value opponents.
- [ ] Decide which calibrated opponent type should be used for blocking fixtures before implementing those fixtures.

## Update: 2026-08-29 - Opening setup policies added

### What changed
Added `src/wingspan_ai/agents/setup.py` with first-class policies for opening bird, bonus-card, and starting-food selection:

- `DefaultSetupPolicy`: preserves the prior deterministic control opener.
- `PotentialPointsSetupPolicy`: scores opening selections for playability, tempo, power value, bonus alignment, habitat coverage, and first round-goal alignment.
- `ArchetypeSetupPolicy`: adapts opening choices for egg-focus, engine-builder, food-acceleration, card-draw, bonus-card-focus, and round-goal-chase strategies.
- `NetValueSetupPolicy`: starts from potential-points setup and adds public tray/round-goal denial priors without looking at opponent hidden hands or bonus cards.

The runner now passes an `InitialSelectionContext` into setup policies. That context contains only public setup information beyond the acting player's own private hand: face-up bird tray, round goals, round state, and player count. Setup-selection telemetry now records `setup_policy_id`.

Guardrailed agents delegate setup selection to the wrapped base agent, so guardrailed potential-points and guardrailed archetypes keep their intended opening policy.

### Why it matters
Earlier smoke matrices compared midgame decision policies while giving almost every automated agent the same generic opening. That likely compressed or distorted strategy differences, especially for engine, food, card-draw, bonus-card, and round-goal archetypes.

Opening setup is now part of the agent policy surface. Future comparisons should treat setup policy as an experiment parameter, not background noise.

### Follow-up tasks
- [ ] Compare default setup versus strategic setup for the same turn policy over fixed seeds.
- [ ] Add setup-selection summaries to batch comparison reports.
- [ ] Calibrate opening weights from first-play timing, playable-bird rate, bonus progress, and final margin.
- [ ] Re-run small baseline matrices before interpreting earlier win-rate differences.

## Update: 2026-08-31 - Full power coverage, agent-vs-agent round robin, SQL analysis layer, and Bayesian response beliefs

### What changed

**Power fidelity (100% coverage).** Classified and implemented the remaining 49
unclassified bird powers behind registry handler keys. New handlers:
`discard_egg_draw_cards`, `draw_cards_then_discard`, `move_bird_habitat`,
`repeat_brown_power`, `trade_food_with_supply`, `draw_bonus_cards_keep_one`,
`draw_cards_player_select`, `draw_tray_cards`, and `play_additional_bird`.
`draw_card` and `gain_food_from_supply` now parse counts instead of assuming one.

The sweep also exposed five pre-existing misclassifications where
opponent-affecting powers resolved as pure self-benefit. Fixed with new handlers
`all_players_draw_cards` (5 cards), `each_player_gains_birdfeeder_food` (2),
`fewest_birds_draw_cards` (2), `fewest_birds_gain_food` (1), plus
`all_players_lay_eggs` (3), which was dead code because the generic `lay_egg`
check ran first. Three draw-then-discard cards had also been resolving as plain
draws, ignoring the discard.

Power audit now reports 174/174 powered cards classified and implemented
(was 125/174, 71.8%). Added `tests/test_power_handlers.py` with 24 per-handler
regression tests and a workbook-backed coverage guard.

**Experiment-level content filtering.** Added
`src/wingspan_ai/content/filters.py`. Batches can now exclude birds by power
implementation status or handler key, with provenance recorded in the manifest
and a minimum-deck-size guard. Exposed as `power_status_filter` and
`excluded_power_handler_keys` on the batch flow.

**Agent-vs-agent round robin.** Added `flows/round_robin.py`. Every unordered
agent pair plays every seed in both seat orders, with `setup_policy_kind`
(`control` / `strategic` / `agent_default`) as a crossed factor. Reports
standings, per-matchup seat-split win rates, a `seat_robust` flag, seat-effect
totals, and a setup-policy effect table. The batch flow now takes
`player_one_agent_kind`, `guardrail_seats`, `swap_seats`, and
`setup_policy_kind`; agent IDs are seat-suffixed rather than hardcoded to `_p2`.

**SQL analysis layer.** Added `analysis/sql/analysis_views.sql` (12 views) and
`analysis/apply_sql_views.py`. Views cover run factors, per-player scores, action
events, agent decisions, setup selections, action mix, agent performance,
head-to-head games and summaries, decision cost, setup-policy outcomes, and a
`v_run_quality` gate that labels runs `claim_grade` only when replay validation
passed and rule coverage is complete. Performance views exclude replay-invalid
games. All 12 validated against the live schema inside a rolled-back transaction;
**not yet applied** to the database.

**Bayesian opponent-response beliefs.** Added `src/wingspan_ai/belief/`, lifting
belief state out of `net_value.py` into a first-class module.
`OpponentBeliefState` maintains a posterior over six opponent profiles and
predicts a distribution over action families via
`P(a|z) ∝ prior(a|z)·exp(v(a)/T(z))`, marginalized over the posterior. The runner
calls a new optional `observe_action` hook on non-acting agents so beliefs update
from public information as the game proceeds.
`NetValueOpponentResponseAgent` gained `response_mode` (`expected` default,
`best` for ablation). Calibration now reports log loss, Brier score, and
improvement over a uniform guess. Documented in
`docs/agents/opponent_response_belief_model.md`.

### Why it matters

Every strategy result in the repo so far was agent-vs-random with 28% of powered
cards unimplemented. Both blockers are now removed: rule coverage is complete for
the base game, and the round robin measures agents against each other with seat
effects cancelled and openings as an explicit factor rather than background
noise. The SQL layer means those comparisons are queryable instead of scraped
from JSON artifacts.

### Roadblock discovered: batches are not seed-matched across `batch_id`

`game_id` participates in RNG seed material (`_roll_birdfeeder_for_state`,
`_record_deck_draw`) and `game_id` is derived from `batch_id`. Because `batch_id`
defaults to a timestamp plus UUID, **two batches run with the same numeric seeds
but different batch IDs see different deck order, birdfeeder rolls, and setup
deals.** Verified directly: seed 1 with `game_id=batchA_seed_1` scored 35-43,
and with `game_id=batchB_seed_1` scored 22-45.

Single-game determinism is intact — the same `game_id` always reproduces the same
result. The problem is only cross-batch comparison.

This means any earlier "fixed seed" comparison run as separate batches was not
actually seed-matched, including the 10-seed matrix in
`potential_points_matrix10_smoke.md` and the paired comparisons behind
`simulation_batch_comparison.py`, if those variants used separate batch IDs.
Those results are not wrong, but they are noisier than reported and their
seed-pairing claim does not hold.

`flows/round_robin.py` is unaffected: it passes one shared `batch_id` to every
matchup cell and separates cells by `batch_label`, so all cells see identical
game IDs per seed. `tests/test_round_robin.py` locks that invariant in.

### Decision

Treat `batch_id` as part of the reproducibility key, not just a storage key. Any
A/B comparison must either share a `batch_id` or explicitly accept unmatched
seeds. Recorded here rather than fixed in the RNG because separating the storage
key from the seed key changes every stochastic draw and invalidates existing
replay hashes and artifacts — that is Alex's call.

### Follow-up tasks
- [ ] Decide whether to split the RNG namespace from `game_id`, accepting that
      existing artifacts and replay hashes become non-reproducible.
- [ ] Re-run the 10-seed baseline matrix under a shared `batch_id` and correct
      `potential_points_matrix10_smoke.md` if the ordering changes.
- [ ] Apply the analysis views to PostgreSQL (`python analysis/apply_sql_views.py`).
- [ ] Run a 30+ seed round robin and treat only `seat_robust` orderings as findings.
- [ ] Re-run the setup-policy factor per-agent rather than pool-wide; the v1 design
      makes the effect zero-sum across the roster and therefore not identifiable.
- [ ] Investigate why `archetype_engine_builder` and `archetype_bonus_card_focus`
      post identical win rates and near-identical action mixes; archetypes are not
      producing distinct behavioural signatures.
- [ ] Diagnose `net_value_response` card over-draw (44-46% of actions) against its
      last-place finish; likely hand-size overvaluation, not the opponent model.
- [ ] Refit belief family priors per opponent kind from round-robin telemetry;
      the current `random_legal` prior comes from a single 3-seed probe.
- [ ] Separate `random_legal` from `card_draw` in the profile posterior; family
      frequency alone does not distinguish them.
- [ ] `tests/test_content_loader.py::test_default_workbook_path_points_to_raw_data`
      still fails when `WINGSPAN_CARD_WORKBOOK` is exported by `.envrc`.

## Update: 2026-08-31 - Round robin v1 results

### What changed
Ran the first agent-vs-agent round robin: 5 agents, seeds 1-5, both seat orders,
setup policy crossed, 40 cells, 200 games, all replay-valid. Documented in
`docs/experiments/round_robin_v1.md`.

### Results
`potential_points` leads at 0.756 win rate and 58.45 average score, and its lead
is seat-robust in every matchup under both setup levels. It is the only agent
converting resources into played birds at a healthy rate (21.8-23.1% of actions
versus 13.3-13.9% for greedy and the archetypes).

### Why it matters
This is the first strategy ordering in the project that survives seat swapping,
so it is the first result that is about strategy rather than turn order.

Three things the run exposed that agent-vs-random could not:

1. **Seven of 20 matchups were pure seat artifacts.** Three control matchups
   showed 0.000 win rate in seat one and 1.000 in seat two. Aggregate seat-two
   advantage was only 0.537 vs 0.463, so the per-matchup swings were invisible in
   the aggregate. Only the 13 seat-robust rows carry signal.
2. **The archetype bots are not distinct strategies.** `engine_builder` and
   `bonus_card_focus` post identical win rates in every matchup and near-identical
   action mixes (~49% gain-food, ~14% play-bird). This contradicts the standing
   success criterion that each archetype has a measurable behavioural signature.
3. **`net_value_response` finished last while drawing cards on 44-46% of its
   actions**, roughly double any other agent, without converting them to birds.
   The problem looks like own-value mispricing rather than opponent modelling.

### Decision
The v1 setup-policy factor is not identifiable and should not be quoted. Applying
one setup level to the whole roster makes win-rate differences zero-sum across
agents, so the table only shows relative movement, not whether strategic openings
help in absolute terms. Future runs must cross setup policy per agent.

## Update: 2026-08-31 - Seat handling decision and N-player counterbalancing

### What changed
Investigated whether the first player is randomly selected. It is not:
`setup_base_game` uses its seeded RNG only for deck/bonus/round-goal shuffles and
the opening birdfeeder roll, then returns `RoundState()` with the default
`active_player_index = 0`. Verified across 50 seeds at three players — the
starting index is always 0. Seat assignment follows agent list order, so the
first-listed agent always acts first. Between rounds the token rotates
deterministically as `completed_round % player_count`, which is rule-faithful;
only the *initial* token holder is unrandomized relative to physical Wingspan.

Recorded the decision in
`docs/decisions/0002-deterministic-first-player-with-seat-counterbalancing.md`
(the project's first ADR; 0001 remains reserved for the Savepoint separation doc).

Generalized seat handling from a two-player boolean swap to N-player rotation:

- `run_seeded_game` / `run_simulation_batch` take `player_agent_kinds` (1-5
  agents) and `seat_rotation` instead of `swap_seats`. The two-player
  `player_one_agent_kind` / `player_two_agent_kind` pair still works unchanged.
- `flows/round_robin.py` takes `player_count` (2-5) and always emits all
  `player_count` rotations per lineup. Counterbalancing cannot be disabled.
- `summarize_seat_effect` reports per-seat win rate and average score, plus
  `win_rate_spread` and `avg_score_spread` per player count.
- Added `v_seat_effect` and `v_seat_effect_magnitude` SQL views (14 total, all
  validated against the live schema in a rolled-back transaction).
- Verified the simulator runs and replay-validates at 2, 3, 4, and 5 players.

Wrote `docs/experiments/seat_order_study_plan.md` for the standing question.

### Decision
Keep the first player deterministic; do not randomize the token. Counterbalance
seats instead. Randomizing only averages over seat variance, whereas
counterbalancing removes it — paired seat-rotated seeds are a stronger design at
the same sample size — and changing the seeding would invalidate every existing
replay hash and artifact.

### Why it matters
Seat was a systematic rather than random factor, which is why seven of twenty
round-robin matchups came out as pure turn-order artifacts. Every pre-2026-08-31
batch is affected, since `RandomLegalAgent` was hardcoded to `player_1`.

### Standing research question
Does turn order matter, at which player counts, and by how much? The structural
prediction is that the effect is **largest at three players**, not two: with four
rounds and three players, seat one starts rounds 1 and 4 while seats two and
three start one round each. At two players the round starts are balanced 2-2.
This is testable now and is the opposite of the usual intuition.

### Machinery pilot
A 2-seed pilot confirmed rotations work end to end: 2 players gave a 0.000
win-rate spread over 12 games, 3 players gave 0.333 over 6 games. Both samples
are far too small to mean anything (the 3-player figures are literally 3/2/1 wins
out of 6) and are recorded in the study plan as a plumbing check only, explicitly
labelled as non-evidence.

### Follow-up tasks
- [ ] Run `seat_order_study_plan.md` at 2/3/4/5 players, 30 seeds, one shared
      `batch_id`, `control` setup only. Roughly a day of compute.
- [ ] Re-run `round_robin_v1` reporting under the v2 summary schema so its seat
      effect is quantified rather than only flagged.
- [ ] If the spread is material at higher player counts, re-examine whether
      `BASE_ACTION_CUBES_BY_ROUND` and round-goal scoring tiers are correct for
      3-5 players before publishing any multiplayer claim.

## Update: 2026-08-31 - Multiplayer rules verified and gated

### What changed
Extracted the core rulebook text and verified the two player-count-sensitive
rules directly against it, rather than from memory.

- **Action cubes** (page 5): 8/7/6/5 turns per player, stated once for a 1-5
  player game with no player-count qualifier. `BASE_ACTION_CUBES_BY_ROUND` is
  correct and correctly does not vary with player count.
- **Green goal tiers** (page 11 + goal board): 1st 4/5/6/7, 2nd 1/2/3/4,
  3rd 0/1/2/3, 4th-5th 0. `ROUND_GOAL_GREEN_SCORES` matches exactly.
- **Ranking behaviour**: tie pooling with place-skipping, the zero-item
  exclusion, and top-three-only scoring all verified behaviourally, including
  the rulebook's own worked example (5/2/1 goal, two tied for 1st score 3 each,
  2nd not awarded).

Added `src/wingspan_ai/rules/multiplayer_audit.py` encoding those rulebook values
and the worked example as citable data, plus 15 checks across player counts 2-5.
All pass. Documented in `docs/rules/multiplayer_rule_audit.md`.

### Enforcement, not advice
- `audit_rule_coverage(catalog, player_count=N)` embeds the audit in every batch
  manifest.
- `flows/simulation_batch.py` raises `MultiplayerAuditError` before any artifact,
  database row, or upload whenever a 3+ player game runs against failing checks.
- `v_run_quality` labels such runs `multiplayer_rules_unverified`, never
  `claim_grade`.

Verified by deliberately corrupting `BASE_ACTION_CUBES_BY_ROUND`: the 3-player
batch was blocked, the 2-player batch still ran.

### Known player-count-sensitive simplifications (declared, not hidden)
`KNOWN_SIMPLIFICATIONS` records three: unlimited egg supply (binds from ~4
players; the physical game has 75 eggs), unlimited food supply (103 tokens), and
green-goals-only. The egg supply is the one worth closing before publishing any
five-player result, because it plausibly binds and interacts with the egg-based
round goals that green scoring ranks.

### Correction to the 2026-08-31 batch_id finding
The earlier entry stated that batches with different `batch_id` values see
"different deck order, birdfeeder rolls, and setup deals". That was wrong on two
of three counts. `game_id` enters RNG seed material in exactly one place —
`_roll_birdfeeder_for_state` — so only **mid-game birdfeeder rerolls, pink/each-player
food gains, and predator hunts** diverge. Deck order, opening hands, bonus cards,
bird tray, round goals, and the initial birdfeeder roll are all seeded from
`random_seed` alone and are identical across batch IDs. Verified directly.

The cross-batch comparison problem is real but narrower than first reported.

## Update: 2026-08-31 - Egg-supply gap retracted; game_id removed from RNG seed

### Retraction: the egg-supply "gap" was not real
I previously flagged the simulator's unbounded egg supply as a
player-count-sensitive fidelity gap, reasoning that the core box ships 75 egg
miniatures and a five-player table could exceed that. **That was wrong.** Core
rulebook page 8 states plainly:

> Managing egg tokens. There is no limit to the egg supply. In the unlikely event
> that no eggs remain in the supply, use a temporary substitute.

Page 7 says the same for food tokens. Component counts are convenience, not
rules, so the simulator's unbounded supply is **correct** and capping it at box
contents would be the deviation.

Expansion egg miniatures, recorded in `EGG_MINIATURE_COUNTS` for provenance:
core 75, European +15, Oceania +15, Asia +30 (135 combined). The count rising
with expansions reinforces that 75 was never a ceiling.

`unlimited_egg_supply` and `unlimited_food_supply` were removed from
`KNOWN_SIMPLIFICATIONS` and replaced with positive checks
(`egg_supply_is_unlimited`, `food_supply_is_unlimited`) citing pages 8 and 7.
The audit now runs 17 checks; `green_goals_only` is the single remaining
declared simplification.

### ADR 0003: game_id removed from the RNG seed string
Implemented the one-line fix in `_roll_birdfeeder_for_state`:

```python
seed = f"{state.random_seed}:{state.round_state.global_turn_number}:{salt}"
```

`random_seed` is now the sole reproducibility key and `game_id` is purely a
storage key. Verified: the same seed under three different game IDs produces
byte-identical outcomes with valid replays, different seeds still diverge, and
two independently-run batches with different auto-generated `batch_id` values are
now seed-matched.

Guarded by `tests/test_base_game_rules.py::SeedNamespaceTests`, which asserts
recorded seed material contains no game ID, identical seeds produce identical
stochastic draws across game IDs, and different seeds still diverge.

### Consequences
- Cross-batch A/B comparison is valid by default. The shared-`batch_id`
  workaround is obsolete, though the round-robin flow still shares one because
  per-cell storage separation is useful on its own.
- The seat-order study no longer has to run as one indivisible batch; player
  counts can be added incrementally.
- Artifacts predating this change cannot be revalidated and were deleted.
- `docs/experiments/belief_response_mode_ablation.md` results remain valid (they
  were correctly matched at the time) but are no longer reproducible by
  re-running, because the seed formula changed. Noted in that doc.

## Update: 2026-08-31 - Archetype bots fixed; analysis views applied

### Archetype policy fix (three real bugs)
The round robin found `engine_builder` and `bonus_card_focus` posting identical
win rates in every matchup. Diagnosis found three separate defects, documented in
`docs/agents/archetype_policy_fix.md`:

1. **No opinion outside play-bird.** `engine_builder`, `bonus_card_focus`, and
   `round_goal_chase` scored only `PLAY_BIRD` and returned 0 otherwise, so on any
   turn without an affordable bird they collapsed into plain greedy. Because
   `_base_immediate_score` is 0 for both gain-food and draw-cards, and ties
   resolve to the first legal action, they all defaulted to **gain food** — the
   ~49% gain-food signature seen in telemetry. Measured: four of six archetypes
   scored only 2 of 10 legal actions non-zero.
2. **Bonus tags matched the whole game, not the held card.** Every one of the 180
   birds carries tags for all bonus cards it could satisfy (`Bird Feeder` on 78
   birds, `Small Clutch Specialist` on 83). Scoring `3 * len(tags)` was a large
   near-constant that discriminated nothing. `bonus_card_focus` scored **0.0
   bonus points** on average — failing at the one thing it is named for.
3. **Unbounded accumulation.** `food_acceleration` and `card_draw` applied a flat
   +8 to always-legal actions, so they looped forever: 87.2% and 82.1% of actions,
   scoring 21.7 and 11.0.

Fixes: full-spectrum preferences across all four action families; tag matching
against held bonus cards only; diminishing returns on food and card
accumulation; and `round_goal_chase` now values laying eggs when the round goal
is egg-based (previously scored 0, making egg goals literally unchaseable).

All six archetypes now score 10/10 actions non-zero. `engine_builder` and
`bonus_card_focus` are separated by L1 = 0.539 on action mix.
`bonus_card_focus` bonus points went 0.0 to 2.0 and its average score 41.7 to 51.6.
Guarded by `ArchetypeDistinctnessTests`.

Remaining weakness: `card_draw` and `bonus_card_focus` are now the closest pair
(L1 = 0.077) since both lean on drawing. They separate on bonus points but not
strongly on action mix.

### Analysis views applied
Ran `python analysis/apply_sql_views.py` against the configured PostgreSQL. All
14 views created and verified queryable via `--check`. Existing telemetry already
flows through them (6 runs, 12 player-score rows, 312 decision rows at time of
apply).

### Open issue found 2026-08-31: both seats share one agent RNG seed
`flows/simulation_batch.py` constructs every seeded agent with
`random_seed=random_seed`, so in a mirror matchup (random vs random, or Monte
Carlo vs Monte Carlo) both agents start with identically-seeded RNGs and make
correlated early choices. Not fixed immediately because the 10-seed matrix was
already in flight and changing it mid-run would make that batch internally
inconsistent.

Recommended fix: derive a per-seat agent seed, e.g. `random_seed * 100 + seat`,
so seat rotation and mirror matchups draw independent streams. This changes every
result involving `RandomLegalAgent` or `MonteCarloRolloutAgent`, so it should be
done between experiments, not during one.

Note this does **not** explain the random-vs-random row losing 1.0/10 with a -7.1
margin; correlated play would give similar scores, not a systematic loss. That
pattern points at a seat-one advantage, which the seat-order study measures
independently.

## Update: 2026-08-31 - CRITICAL: simulator was nondeterministic across processes

### What was found
While re-running the 10-seed matrix, two identical invocations produced different
results for the same variant with no code change between them (`random_legal`
1.0/10 then 4.0/10). Investigating showed the same seed produces different games
in different Python processes:

    run: {'player_1': 41, 'player_2':  9}
    run: {'player_1': 23, 'player_2': 19}
    run: {'player_1': 50, 'player_2': 17}

### Root cause
`BirdCard.habitats` is typed `set[Habitat]`, and `Habitat` is a `StrEnum`
inheriting `str.__hash__`. Python randomizes string hashing per process, so set
iteration order varies between processes. `_legal_play_bird_actions` iterated
that set directly, so the **order of the legal action list** differed per
process. Any agent selecting by index (`RandomLegalAgent`) or breaking a score
tie by first-maximum then played a different game. `PYTHONHASHSEED=0` produced
identical results, confirming it.

### Why it went unnoticed for so long
Within a single process the hash seed is fixed, so the simulator genuinely is
deterministic. The earlier determinism check looped three times inside one
process and passed. The bug only manifests across process boundaries, which is
exactly how batches are run.

### Fix (ADR 0004)
Added `ordered_habitats()` in `rules/base_game.py` returning canonical `Habitat`
enum order, applied at every site building an ordered structure from
`card.habitats`: `_legal_play_bird_actions`, `potential_points` open-habitat
enumeration, and `setup.py`. Order-independent set operations (`in`, `&`, `len`,
`Counter`, `any`, `all`) were left alone.

Verified: four separate processes now produce identical results.
`CrossProcessDeterminismTests` runs the same seed in two subprocesses under
different `PYTHONHASHSEED` values, which is the only form of test that can catch
this.

### Impact on prior results
Strictly larger than the ADR 0003 `game_id` issue, which affected only mid-game
birdfeeder rolls. This affected the legal action list itself. Every experiment
run before this fix is reproducible only within the process that produced it.

`round_robin_v1.md` and `belief_response_mode_ablation.md` are now banner-marked
**PROVISIONAL** and should not be quoted until re-run. Their per-cell comparisons
were internally consistent (each cell ran in one process), so the qualitative
findings may survive, but they are unverified. All stale artifacts deleted.

### Standing lesson
Any field typed as a `set` of `str` or `StrEnum` must pass through a canonical
ordering helper before it can influence a sequence. Determinism tests must cross
a process boundary; an in-process loop cannot detect this class of bug.

## Update: 2026-08-31 - Baseline matrix v2 on the corrected simulator

### What changed
Re-ran the 10-seed baseline matrix after four corrections: cross-process
determinism (ADR 0004), `random_seed` as sole reproducibility key (ADR 0003),
power coverage 71.8% to 100%, and the archetype policy repair. 130 games, all
replay-valid. Documented in `docs/experiments/baseline_matrix10_v2.md`;
`potential_points_matrix10_smoke.md` marked superseded.

### Results
`potential_points` retains the best score (62.8) and margin (+26.6) at 9.0/10.
The v1 headline survives the corrections. Four variants now reach 10.0/10
(guardrailed greedy, guardrailed potential, card-draw archetype, Monte Carlo),
so potential-points is no longer uniquely top on win rate, but it converts most
efficiently.

The largest swings are the two repaired archetypes: `card_draw` 0.0 to 10.0/10
and `food_acceleration` 0.0 to 8.5/10. Those v1 rows measured a degenerate
accumulation loop, not a strategy.

Guardrails are worth more than v1 suggested: `guardrailed_greedy` 10.0/10 (+26.5)
against plain greedy 5.0/10 (+10.0). v1's finding that the shared guardrail
config degraded potential-points is **reversed** — guarded 10.0/10 vs unguarded
9.0/10.

### Two results deliberately not claimed
- `archetype_bonus_card_focus` fell from 9.0 to 6.0 despite now scoring more
  bonus points. The held-card tag matching changed its play substantially and the
  net-negative effect is not yet understood. Open follow-up.
- The `random_legal` mirror row (3.5/10, -4.3 margin) is confounded by the shared
  per-seat agent seed and must not be read as a seat estimate.

### Caveat that still applies
All thirteen rows are agent-vs-random. Nine of thirteen clear 8/10, so the
opponent is a low bar. Agent-vs-agent ordering comes from the round robin, which
still needs re-running post-ADR-0004.

## Update: 2026-08-31 - Requested research question: bonus card selection

### The question (Alex, 2026-08-31)
Which bonus cards are better choices to keep at the start, and what circumstances
make a given card the right keep?

Setup deals 2 bonus cards and the player keeps 1. That binary choice is made
before almost anything is known and commits the player to a scoring path for the
whole game. Sub-questions: is there a context-free ranking; what makes a card
situational; how many points/win-rate is the choice worth; does it depend on
player count; and how far from optimal are the current setup policies?

Planned in `docs/experiments/bonus_card_selection_study_plan.md`.

### Why it is timely
Three findings from today make it concrete rather than speculative:
- A player holds one bonus card and **83% of hand cards match nothing** against
  it (50 of 60 hand cards over 20 seeded openings).
- Bonus cards yield roughly **2.0 points** even for an agent actively pursuing
  them, against 20-60 total.
- `archetype_bonus_card_focus` became the weakest archetype once it genuinely
  pursued its held card, while the version that ignored it and played birds
  aggressively scored 9.0/10.

Together these hint that bonus cards may be a low-value, high-variance path in
this simulator — but that is untested and could be an artifact of which cards get
dealt, or of weak pursuit, rather than of the cards.

### Most of the pipeline already exists
The setup choice is a policy hook; `setup_selection_applied` telemetry records
both kept **and discarded** bonus cards, which makes the counterfactual
identifiable; `v_setup_selections` and `v_setup_policy_outcomes` expose it in SQL;
`_score_single_bonus_card` scores one card against a board; and all 180 birds
carry `bonus_card_tags`.

The natural design is a **forced-keep paired experiment**: same seed, run twice
forcing each side of the dealt pair. ADR 0003 makes the two arms seed-matched.
The only missing piece is a setup policy that accepts a forced choice.

### Blocking prerequisite
The 26 bonus-card scoring handlers are covered but have never been individually
validated against the rulebook appendix. A mis-scored card would invert its
ranking, so validate before running.

## Update: 2026-09-01 - Seat order study v1: turn order does not measurably matter

### Result
750 counterbalanced games (300 at two players, 450 at three), 15 seeds, `control`
setup, cheap roster, on the post-ADR-0004 simulator. Documented in
`docs/experiments/seat_order_study_v1.md`.

**No statistically significant seat effect at either player count.** The largest
signal is seat 1 at three players: +1.156 points paired, p = 0.069 uncorrected,
which is p ~ 0.21 after Bonferroni across three seats. Point estimates cluster
around 1.0-1.2 points on a ~53-point average, roughly 2%. For scale, the best-to-
worst agent gap in the baseline matrix exceeds 30 points.

### The pre-registered prediction was wrong
The plan predicted a larger effect at three players, from round-start accounting
(seat 1 starts rounds 1 and 4; seats 2 and 3 start one each). Score spread came
out 1.82 at two players and 1.77 at three — indistinguishable. Starting a round
confers resource priority but not extra turns, and action cubes per player do not
vary with seat, which is the likely explanation.

### A signal that argues against a real effect
At three players seat 1 scores ~1.2 points more while winning slightly *less*
often (0.3263 vs a 0.3333 fair share). A genuine seat advantage should move win
rate and score together; the disagreement points to noise.

### Implication for the earlier round robin
`round_robin_v1` appeared to show large per-matchup seat effects, with three
matchups reading 0.000 in one seat and 1.000 in the other. Given a near-zero
aggregate effect, those were most likely 5-seed small-sample artifacts compounded
by the then-unfixed determinism bug.

### Decision unchanged
Keep counterbalancing. It costs `player_count` runs per lineup and removes a
variance source that would otherwise have to be assumed away rather than measured.

### Analysis error caught and corrected
A first aggregation swept in the 130 `baseline_matrix10_v2` games, where seat 1 is
always the weak `random_legal` agent, producing an apparent *significant* seat-1
disadvantage (0.4439, p = 0.023). Restricting to counterbalanced cells removed it.
Standing rule: seat statistics may only be computed over counterbalanced designs.

### Tooling added
`analysis/seat_effect_paired.py` reconstructs each agent's score in every seat
from artifacts and contrasts it against that agent's own cross-seat mean,
differencing out agent skill and deck luck.

### Follow-up
- [ ] Extend to 4 and 5 players, where round-start asymmetry is strongest.
- [ ] 30+ seeds if a sub-1-point effect is worth resolving.
- [ ] Fix the shared per-seat agent RNG seed before any mirror-matchup seat work.

## Update: 2026-09-01 - Round robin v2: greedy is the weakest agent, not the second best

### What changed
Re-ran the agent-vs-agent round robin on the corrected simulator. 200 games,
10 pairs x 2 seat rotations x 10 seeds, `control` setup, all replays valid.
Documented in `docs/experiments/round_robin_v2.md`; v1 marked superseded.

Also fixed the shared per-seat agent RNG seed first (`random_seed * 100 + seat`),
so mirror matchups and Monte Carlo no longer draw from correlated streams.

Design changes: seeds 1-10 rather than 1-5, and `control` setup only, because
v1's pool-wide setup factor is zero-sum and not identifiable.

### Standings
| Agent | Win rate | 95% CI | Avg score | p |
|---|---:|---|---:|---:|
| `potential_points` | 0.756 | [0.647, 0.866] | 66.81 | <0.0001 |
| `archetype_engine_builder` | 0.550 | [0.440, 0.660] | 56.77 | 0.371 |
| `archetype_bonus_card_focus` | 0.487 | [0.378, 0.597] | 55.98 | 0.823 |
| `net_value_response` | 0.431 | [0.322, 0.541] | 50.86 | 0.219 |
| `greedy_immediate` | 0.275 | [0.165, 0.385] | 46.88 | 0.0001 |

### The headline correction
**`greedy_immediate` moved from second (0.506) to last (0.275, p = 0.0001).**
v1's archetypes were broken and collapsed into a greedy-like fallback, so greedy
was effectively playing copies of itself. With the archetypes repaired,
immediate-score maximization is exposed as a weak policy. This is the largest
correction to the project's strategy picture so far.

`potential_points` remains strongest and is now statistically established
(z = +4.58), winning all four of its matchups seat-robustly.

The three previously tied at 0.412 now spread across 0.550 / 0.487 / 0.431.

### Seat effects largely vanished
9 of 10 matchups seat-robust, against 13 of 20 in v1. Aggregate seat spread 1.96
points, closely matching the seat-order study's independent 1.82-point estimate.
v1's three 0.000-vs-1.000 matchups did not reappear — they were small-sample
noise compounded by the determinism bug, exactly as the seat study predicted.

### Ranking against random is not ranking against agents
`net_value_response` beats random as often as `archetype_engine_builder`
(8.0/10 each) but is clearly worse head to head (0.431 vs 0.550). Agent-vs-random
compresses the field; nine of thirteen baseline variants clear 8/10.

### Caveat
20 games per matchup. Only the extremes reach significance; the three middle
agents have overlapping CIs and are unranked among themselves.

### Tooling
`analysis/round_robin_aggregate.py` pools chunked round-robin runs from artifacts,
which is what makes a 200-game run practical inside process time limits.

## Update: 2026-09-01 - Round robin v3: guardrails rescue weak policies, not strong ones

### What changed
Made guardrailed agents first-class roster entries via a `guardrailed:` prefix
(e.g. `guardrailed:potential_points`), so an agent can face its own guardrailed
twin. Previously guardrails were a seat-level batch setting and this comparison
was impossible.

Two implementation notes: the setup policy is applied to the **base** agent
before wrapping, because `GuardrailedAgent` delegates opening selection downward
and a policy set on the wrapper is never consulted; and the older seat-level
mechanism will not double-wrap a prefixed agent.

Ran 200 counterbalanced games. Documented in
`docs/experiments/round_robin_v3_guardrails.md`.

### Result
| Agent | Win rate | 95% CI | Avg score | p |
|---|---:|---|---:|---:|
| `potential_points` | 0.656 | [0.547, 0.766] | 66.46 | 0.005 |
| `guardrailed:potential_points` | 0.581 | [0.472, 0.691] | 64.75 | 0.146 |
| `archetype_engine_builder` | 0.525 | [0.415, 0.635] | 58.67 | 0.655 |
| `guardrailed:greedy_immediate` | 0.512 | [0.403, 0.622] | 56.73 | 0.823 |
| `greedy_immediate` | 0.225 | [0.115, 0.335] | 46.36 | <0.0001 |

### The finding: an asymmetry
- **Guardrails rescue immediate greedy decisively.** Head to head over 20
  counterbalanced games the guardrailed twin wins **0.750** with a **+12.75**
  margin (p = 0.025, seat-robust). Across the table: +0.287 win rate and +10.4
  points, moving greedy from clearly last to mid-table.
- **Guardrails do nothing measurable for potential-points.** The guardrailed twin
  loses head to head 0.450 (margin -3.90), and the matchup is not seat-robust
  with p = 0.655, so the honest reading is no detectable effect, possibly
  slightly negative.

Interpretation: `base_heuristic.yaml` encodes roughly the same knowledge
potential-points already computes — food deficits, egg capacity, hand size, early
engine building. It substitutes for a missing value function rather than adding
to a working one. Guardrails are a cheap way to make a weak policy competitive,
not a general improvement to stack on a good one.

### Seat effects now essentially absent
Win-rate spread 0.020, score spread 0.43 points, against 1.96 in v2 and 1.82 in
the seat-order study. The four non-seat-robust matchups are all closely matched
pairs (margins +0.00 to +5.15), which is where a seat flip is expected.

### Caveats
20 games per matchup; only the two extremes are significant and the three middle
agents are unranked among themselves. One guardrail config only, and it was
authored with immediate greedy in mind — which plausibly explains the asymmetry
and should be tested with a potential-points-oriented config.

Chunk-level guardrail effects on potential-points swung -0.06, -0.375, +0.19,
-0.31, +0.03 across five 40-game chunks. Only pooled results are meaningful at
this sample size.

### Follow-up
- [ ] Author a guardrail config tuned for potential-points and re-test.
- [ ] Add guardrailed archetypes to see whether the rescue effect generalizes.
- [ ] 30 seeds to separate the three middle agents.

## Update: 2026-09-02 - Seat order matters at 3 players, but LAST is best

### Result (contradicts the pre-registered prediction)
Ran the seat study at 3 players with a tray-aware roster
(`potential_points`, `guardrailed:potential_points`, `net_value_response`,
`guardrailed:net_value_response`). Paired within-agent score contrasts over 72
paired units:

| Seat | Paired delta | t | p |
|---:|---:|---:|---:|
| 1 | -2.505 | -2.23 | 0.025 |
| 2 | -1.130 | -0.85 | 0.396 |
| 3 | **+3.634** | +3.33 | **0.0009** |

Score spread 6.14 points, against 0.09 at two players. Seat 3 survives
Bonferroni correction across three seats (p ~ 0.003).

**Turn order does matter at three players** — Alex was right that the effect
strengthens with player count. But the direction is the opposite of both the
round-start prediction and the first-pick hypothesis: going **last** is worth
about +3.6 points and going **first** costs about -2.5.

First pick of the tray is evidently outweighed by something else. Acting last in
a round means acting with full information about opponents' positions on the
competitive end-of-round goal, which is the leading candidate explanation and is
untested.

Caveat: 72 paired units, one roster, 15 seeds. Needs replication before it is
treated as settled, and 4-5 player counts are unrun.

## Update: 2026-09-02 - Opponent-aware denial and pink power valuation

### Denial now asks what a card is worth to the opponent
`_tray_card_denial_value` previously summed `_public_card_threat_value(card)`,
which reads only the card. It now estimates what the card would do on each
opponent's board by calling `_played_power_value` — the same routine that values
a played bird for its owner — driven by how often that opponent is likely to
activate the relevant habitat in their remaining turns.

| Property | Before | After |
|---|---|---|
| Repeatable brown vs one-shot white | Gnatcatcher 0.92 < Goldfinch 1.16 (backwards) | 1.02 > 0.36 |
| Tempo | constant | 1 turn 0.23 -> 16 turns 1.92 |
| Opponent has no habitat room | unchanged | 0.00 |
| Opponent cannot afford it | ignored | discounted by shortfall |

Five tests cover these, including one asserting the estimate is unchanged when
hidden hand *contents* change at fixed hand count, so the agent cannot read
information it is not entitled to.

### Pink powers now depend on opponents
Every pink power was valued at a flat `turns_remaining * 0.35`. Black Vulton-style
cards ("when another player's predator succeeds") scored the same whether
opponents held zero predators or five. `_pink_trigger_rate` now models the four
real trigger classes found in the deck: opponent predator success (3 cards),
opponent lay-eggs action (5), opponent plays a bird in a named habitat (3), and
opponent gain-food action (1).

Verified: Black Vulture goes 0.00 triggers with no opponent predators to 2.58
with three; a habitat-gated pink drops to 0.00 when that opponent habitat is full.

### Bug found: both brood-parasite cowbirds valued at exactly zero
Exactly two birds in the deck have `egg_limit` 0 — Bronzed Cowbird (5 VP) and
Brown-Headed Cowbird (3 VP) — and both are lay-egg pinks whose whole mechanic is
laying in *other* birds' nests. The valuation checked the power card's **own**
egg capacity, so both scored zero regardless of trigger count. Now measured
against board-wide capacity in the matching nest type: 0.00 with no bowl-nest
birds, 1.44 with two.

### Still open
- Bonus-card fit in denial, which needs a belief posterior over opponent bonus
  cards.
- Tray-card blindness in greedy and the six archetypes (7 of 9 agents assign
  identical value to every tray card).
- Whether the seat-3 advantage is driven by end-of-round-goal information.

## Update: 2026-09-02 - Tray-card blindness and bonus-card fit both fixed

### Tray-card blindness
Seven of nine agents scored every face-up tray card identically — 100% blind
across 30 seeded openings while the options differed by a mean 3.0 victory
points. `GreedyBaselineAgent` because a draw yields no immediate points (its
`_heuristic_tiebreaker` returned a flat 10 for every draw), and every archetype
because it applied a flat family bonus. All tied, so they took whichever action
was enumerated first: always tray index 0.

Added `agents/tray_preference.py` with a shared affinity model (habitat room,
affordability, egg capacity, repeatable-vs-one-shot power) plus per-archetype
overlays. Greedy uses it as a sub-1.0 tie-break so it still never outranks a real
score difference.

Blindness went from 30/30 states to 0-1/30. Crucially the archetypes now
*disagree* about which card to take — picks-highest-VP rates range from 13/30
(card_draw) to 25/30 (greedy) — so they weight by strategy rather than all
collapsing onto raw victory points.

### Bonus-card fit in denial
Added `belief/bonus_cards.py`: a posterior over which bonus cards an opponent
holds, inferred from the tags on their **played** birds. Every bird satisfies
many bonus cards, so raw counts are dominated by common tags; the estimator
compares each tag against the average tag count on that opponent's own board.
Mass is scaled to their public `bonus_card_count`.

Verified: a board of four bowl-nest birds infers **Wildlife Gardener at 0.449**,
correctly ahead of Cartographer and Passerine Specialist at 0.136.

Denial now includes expected bonus fit. A **0 VP** niche bowl-nest card scores
0.79 denial against a 9 VP Bald Eagle's 1.13 — roughly 70% — driven almost
entirely by bonus fit (0.72 vs 0.04). Under intrinsic-strength scoring the niche
card was worth near zero. This closes the exact case Alex identified.

### Information boundary
The posterior reads only played birds and bonus-card count, both public. A test
asserts denial is unchanged when hidden hand *contents* change at fixed count.

238 tests pass.

## Update: 2026-09-03 - Bonus scoring rebuilt, mat scaling added and ablated

### Bonus-card scoring was wrong on five of twenty-six cards
Built an audit comparing `_score_single_bonus_card` against each card's own
printed `victory_point_text`. It found:

- **Omnivore Expert** ("Birds that eat [wild]") tested `choice_food_count` while
  every qualifying bird uses `wild_food_count`. It always scored zero.
- **Food Web Expert** ("Birds that eat *only* [invertebrate]") required a cost of
  exactly one invertebrate, so a bird costing two scored nothing.
- **Photographer**, **Historian**, **Anatomist** re-derived qualification from
  bird names with hand-written word lists and missed most qualifying birds;
  Photographer found almost none of its 63.

Replaced 86 lines of hand-written per-card logic with `rules/bonus_scoring.py`,
which parses the printed formula and counts qualifying birds from the workbook's
per-bird `bonus_card_tags`. All 26 cards now parse and score correctly. Bonus
points roughly doubled, ~2.0 to 3.0-3.8 per game.

Exactly four cards score from board state rather than bird identity, and they are
exactly the four with no tagged birds — a split now asserted from the data rather
than by hand. `tests/test_bonus_scoring.py` drives every card across its whole
tier range.

This partly explains an earlier speculation that bonus cards were simply a weak
scoring path: some of that was a scoring bug.

### Sample catalog was silently unusable for bonus scoring
Odd-index synthetic birds carried `{SEED: 0}` — a zero-count food entry making
*every* bird look like a seed eater — and no bonus tags at all. Both fixed, so
synthetic tests now exercise real semantics.

### Mat-scaling valuation: real gap, no measured payoff
Consolidated the three yield curves behind a public `habitat_action_yield()`, so
`_egg_rate` no longer keeps a hand-copied duplicate that could silently drift
from the rules. Added `habitat_yield_potential` to the potential breakdown.

Ablated over 60 seed-matched games per arm
(`docs/experiments/mat_scaling_ablation.md`):

| Scale | Decisions changed | Win-rate movement |
|---|---:|---|
| 1x | 0.64% | zero for every agent |
| 2x | 3.37% | at most one game in 24 |

Kept at 1x for correctness and fidelity, **not** on measured performance. For
contrast on the same harness: opponent-aware denial was +0.182 win rate and the
tray tie-break +0.112, so the harness resolves effects of that size easily.

Two traps found during implementation, both surfaced by an existing test failing
rather than by the ablation: double-counting grassland against
`_egg_conversion_potential`, and coupling yield to current food demand so that
gaining needed food *reduced* the estimate.

### Standing lesson
Measure before stacking. The earlier round robin caught a -0.325 win-rate
regression I had introduced via tray preference; had mat scaling been added on
top, the regression would have been attributed to the wrong feature.

## Update: 2026-09-03 - Seat-3 advantage did not replicate

### Outcome
Investigated the significant three-player seat-3 advantage from 2026-09-02
(+3.634 points, p=0.0009). **It did not replicate.** Re-measured on the corrected
simulator with current agents over 60 counterbalanced games, seats 1 and 3 swapped
sign and nothing reached significance:

| Seat | 2026-09-02 | 2026-09-03 |
|---:|---:|---:|
| 1 | -2.505 (p=0.025) | +2.017 (p=0.075) |
| 2 | -1.130 | -1.300 |
| 3 | +3.634 (p=0.0009) | -0.717 (p=0.575) |

Documented in `docs/experiments/seat_order_investigation_3p.md`;
`seat_order_study_v1.md` is annotated so its three-player result is not quoted
alone.

### Most likely reading
A policy artifact rather than a property of the game. Between the two runs the
agents gained opponent-aware denial, corrected bonus scoring, tray-card preference
and mat-yield valuation, and `net_value_response` was in both rosters. A seat
effect that flips direction when agents improve says more about how those agents
played than about turn structure.

### What does survive: a derived structural asymmetry
Turn order follows `active_player_index = completed_round % player_count`, so over
four rounds:

| Players | Rounds started | Rounds ended | Symmetric? |
|---|---|---|---|
| 2 | [2, 2] | [2, 2] | yes |
| 3 | [2, 1, 1] | [1, 1, 2] | no |
| 4 | [1, 1, 1, 1] | [1, 1, 1, 1] | yes |
| 5 | [1, 1, 1, 1, 0] | [1, 1, 1, 0, 1] | no |

This is derived from the rules, not measured, and it explains the two-player null
cleanly: there was no asymmetry to detect. Whether the asymmetry produces a
measurable advantage, and in which direction, is **not established**.

### Round-goal ablation
Stripping the competitive end-of-round goals shrank the seat spread from 3.32 to
2.47 points and left the ordering unchanged, with no significant seat in either
arm. Goals contribute something but are not the driver. Average score fell ~58 to
~47, confirming removal worked.

### Open, falsifiable
If the asymmetry drives a real effect it should appear at 3 and 5 players and
vanish at 4. Four players is the cheapest decisive test and would falsify the
structural explanation outright.

### Standing lesson
A single significant result on one agent set is not a finding. This one carried
p=0.0009 and still reversed. Strategy conclusions should be re-measured after any
material agent change, and `seat_order_study_v1.md` was quoted for a day before
this was caught.

---

## Update: 2026-09-03 - Four-player seat test, and a stability check added to the tooling

### The falsification test was run and produced nothing usable
Four tray-aware agents, seeds 1-15, full seat counterbalancing, 60 games — the same
roster and game count as the three-player control. The multiplayer rule audit passed
all eight four-player checks first, so green-goal placement (7/4/3/0, where fourth
place scoring zero matters at this table size) was verified rather than assumed.

Pooled, seat 3 came out at +3.24 points (p=0.032) and seat 4 at -3.65 (p=0.006), a
6.88-point spread. Seat 4 would survive a Bonferroni correction. Read literally that
refutes the structural account, which predicts no effect at four players.

It does not survive a leave-one-block-out check. Split into three 20-game blocks,
seat 3 reads +2.10, -2.08, +9.69 — it flips sign and the whole pooled result sits in
seeds 11-15. Excluding that one block leaves seat 3 at **+0.01 points (p=0.994)** and
seat 4 at -1.56 (p=0.360).

So: **no conclusion about four-player seat order.** The structural account is neither
confirmed nor refuted, because there is no reliable effect to test it against.

### Seat question, current state
| Players | Structure | Measured |
|---|---|---|
| 2 | balanced | null, 0.09 points. Confident. |
| 3 | asymmetric | +3.63 on old agents (p=0.0009), -0.72 on current. Did not replicate. |
| 4 | balanced | fragile; nothing survives the stability check. |
| 5 | asymmetric | not run. |

Three apparent seat findings have now evaporated under scrutiny. Recommendation is to
park the question rather than keep sampling at this size, and to keep seat
counterbalancing regardless — it removes the variance for free.

### The transferable finding is about sample size, not seats
Per-game score variance is roughly 15 points while plausible seat effects are about 2.
At 20-60 games that ratio produces spurious significance readily. Separating a real
seat effect from noise needs several hundred games per player count, which is a
multi-hour run and a deliberate decision, not a side quest.

### Tooling: the diagnostic now runs unprompted
`analysis/seat_effect_paired.py` performs a leave-one-block-out check on every report.
Any pooled effect that loses significance when a single seed block is removed, or that
flips sign across blocks, is labelled **FRAGILE** with an explicit "do not report as a
finding" warning. `tests/test_seat_effect_stability.py` pins the behaviour, including
the exact failure mode seen here: two quiet blocks plus one extreme block.

This check was applied by hand, after the p-values had already been computed and
quoted. That is the second time in two days a seat p-value was believed before it was
stress-tested. Automating it is the correction.

Write-up: `docs/experiments/seat_order_four_player_test.md`.

---

## Update: 2026-09-03 - Artifacts were never reaching MinIO

### One parameter default kept 1.7 GB off the durable tier
The question "is `artifacts/archive/rrv4_pre_fix` safe to delete?" turned out to have
a worse answer than "it's stale."

`artifacts/` is gitignored, so deletion is unrecoverable. Manifests recorded a
`schema_version` but no code version. And the code that produced that 322 MB archive
had never been committed — HEAD is `5450063` from 2026-08-29, the run is from
2026-09-02, and every change between them was uncommitted working-tree state that the
bonus-scoring rebuild has since overwritten. The archive was simultaneously the only
copy of that data and unreproducible, while backing the `+0.182` denial and `+0.112`
tray numbers quoted in `docs/experiments/mat_scaling_ablation.md`.

The fix was not compression, which was the first proposal. MinIO was already running
and the upload path already existed. `flows/simulation_batch.py` enabled it whenever
storage was configured — but `flows/round_robin.py` hardcoded `upload_artifacts=False`,
overriding that, and round robins produce nearly all of the project's data. The bucket
held 21 objects, all smoke tests. `flows/README.md` had documented the intended
behaviour correctly the whole time; the code had quietly diverged from its own docs.

### Done
- `flows/round_robin.py` now defaults `upload_artifacts=None`, inheriting the
  auto-detect instead of overriding it.
- `scripts/backfill_artifacts_to_object_storage.py` mirrored the full tree:
  3,214 objects, 1,737 MB in 176s (9.9 MB/s). Idempotent — a repeat dry run reports
  0 to upload and 3,259 already present, which is the completeness check.
- `src/wingspan_ai/provenance.py` records `git_commit`, `git_branch`, `dirty` and
  `reproducible` into every manifest. It reports `reproducible: false` today, which is
  exactly the condition that caused this.
- ADR 0005 records the policy: object storage is durable, local `artifacts/` is a
  prunable cache.

### Not done
Local pruning. Deferred until the corrected round robin has re-derived the numbers the
old artifacts back — a durable copy makes pruning safe, but the claims should stand on
current data first.

### Standing lesson
Twice in one session a conclusion was reached from what was in front of me rather than
from checking: the seat p-values before the stability test, and "safe to delete" from a
directory named `pre_fix`. The check that would have caught this one was ten seconds of
`grep minio`. Before asserting a property of the system — safe, stale, reproducible,
uploaded — verify it against the system.

---

## Update: 2026-09-04 - Feeder odds is a null; seat power finally computed

### The corrected simulator did not change the standings
Round robin v5, 200 games per arm on the six-face die. `potential_points` first
(0.681) and `greedy_immediate` last (0.275, identical to v2). Scores rose across
the board, consistent with the bonus-scoring fix. The middle three are not
separated at 80 games each, and per-agent movement versus v2 is a four-change
contrast that should not be attributed to any one fix.

### Second null in a row for a modelling improvement
`VALUE_FEEDER_ODDS` on versus off, 200 games each: pooled average score 59.38 vs
59.39, **delta -0.01 (p=0.993)**. No agent moves significantly.

After mat scaling, this is the second fidelity improvement that closed a real gap
and changed nothing. The consistent reading is that these heuristic agents are
not limited by the fidelity of their food or habitat valuation, so sharpening it
has nothing to bite on. Both terms stay on for correctness, and neither should be
described as an improvement.

That pattern is itself worth stating: **modelling the game more faithfully has
not, so far, made the agents stronger.** If a third such term also lands null, the
honest conclusion is that agent strength lives somewhere else — search depth,
opponent modelling, or the action-selection structure — and further fidelity work
should be justified on correctness alone.

### Power analysis, computed rather than guessed
The estimator is a paired within-agent contrast, so the relevant spread is the
seat-delta SD of **9.54**, not the raw score SD of 16.40 — counterbalancing
removes 42%. Quoting the raw figure is what produced the inflated "300+ games"
estimate in earlier write-ups.

At 80% power, alpha 0.05: 2 points needs **179 paired units**, 3 points needs 80,
1 point needs 714. The two-player run at n=200 detects down to 1.89 points.

The sharper point is about magnitude, not false positives. The 4-player run had
60 paired units and could only detect **3.45 points or more**. It reported
**+3.24** — sitting at its own detection limit, which is the signature of an
inflated estimate rather than a real effect. The earlier 3-player +3.63 and the
4-player +3.24/-3.65 are all near the detection limits of the runs that produced
them.

So the seat question is cheaper to answer than assumed: ~179 units per player
count, not 300+. Two players is answered and null. Three, four and five have
never been run at adequate power.

### A fourth seat finding evaporated
Two players pooled at +1.567 (p=0.0186), carried entirely by seeds 5-6 (+5.54);
excluding that block leaves +0.57 (p=0.43).

**Method note now standing:** set the stability block size to match how the run
was actually chunked. At the default 5 this looked like a possible power artifact;
at the 2 that mirrored the chunking it was unmistakably one block. A block size
unrelated to how work was batched can both hide and manufacture fragility.

### On publishing
Assessed and recorded: the bug fixes are not an article. The die-face error, the
bonus-scoring error and the upload gap are defects, not findings. What is
publishable is how they survived — a constant calibrated to its own bug and
documented with a formula that made it look derived; 269 tests passing a
distribution change without edits; four significant seat findings that were all
artifacts. That is an engineering and methods case study, not a research
contribution, and should be labelled as such. Publishing anything using Wingspan
card data needs legal review first.

---

## Update: 2026-09-04 - Third null, and the pattern becomes the finding

`VALUE_RESOURCE_SPENDING` on versus off, 200 games per arm: pooled average score
59.39 vs 59.22, **delta +0.17 (p=0.886)**. No agent moves significantly. Full
write-up in `docs/experiments/resource_spending_ablation.md`.

Three faithful modelling improvements have now measured null in a row —
mat-scaling valuation, feeder odds with the corrected six-face die, and
resource-spending selection. Each closed a real gap. One of them fixed an
outright scoring defect: eggs were spent in `Habitat` enum order and could take
the exact egg an active round goal was counting. Even that did not move play.

**Standing conclusion:** these heuristic agents are not limited by the fidelity
of their resource valuation. "Add more domain knowledge to the evaluation
function" is no longer a defensible default. Further fidelity work should be
justified on correctness grounds alone, and any future valuation term should be
built behind an ablation switch with the explicit prior that it lands null.

The alternative hypothesis is untested: strength may live in search depth,
opponent modelling, or the structure of action selection. That is the next
experiment.

Bounds worth keeping attached to the claim: at 200 paired units the detection
limit is about 1.9 points, so this bounds the effect as small rather than proving
it zero; and all three ablations used the same five-agent roster at two players,
so a term mattering only at higher player counts would not have shown up.

### Method note that worked
The `net_value_response` on-arm win rate looked alarming against the previous run
(0.362 vs 0.463) and was flagged as probably noise **before** the off-arm
finished. The paired contrast put it at -0.100, p=0.199. Registering the
prediction ahead of the data is what made it readable as noise instead of as a
finding.

## Update: 2026-09-05 - First positive result: lookahead depth and coverage

### What changed
The search-depth experiment ran as planned — `potential_points` at
`search_depth` 1/2/3/4 and `final_search_turns` 5 (historic) vs 8 (every
turn), same 200-game counterbalanced design, paired by lineup, rotation and
seed. Full write-up in `docs/experiments/search_depth_experiment.md`.

Two defects had to be fixed first (commit `5830657`):
- `search_depth` was a dead parameter. The search returned the leaf value
  whenever the active player changed, which happens after every action in a
  multiplayer game, so it was one ply deep regardless of the setting. It now
  plays opponent turns with the greedy baseline and descends to the next own
  turn, beam 4.
- `GameState` copies cloned the whole 180-card deck (47 ms per copy). Content
  models are now frozen and shared across copies (0.53 ms). The depth-1 arm is
  bit-identical to the pre-change run in all 200 games.

### Results (paired, n=80 `potential_points` games per arm)
Depth 1 (historic) 68.28. Depth 2 **+7.06**, depth 3 +7.39, depth 4 +9.81, all
p<0.001. Searching on every turn instead of the last five cubes of a round:
depth 2 **+10.54**, depth 3 **+13.55** (win rate 0.738 → 0.925). Every
opponent loses ground. Depth 2→3 is flat on the last-five trigger (+0.33,
p=0.74) but +3.0 (p=0.005) on every turn, and depth 3→4 is +2.4 (p=0.018), so
depth is not saturated; the gain depends on where the trigger places the leaves.

Points come from bird points and round goals with depth, and from eggs,
cached food, tucked cards and bonus cards with coverage. Draw share falls from
29% to 24.5% as search grows.

### Why it matters
After three valuation-fidelity nulls, this is the first intervention that moves
these agents, and it moves them by more than the whole spread between the
historic agents. The three nulls were measured on an agent whose search was
one ply; whether valuation fidelity matters *given* real search is reopened,
not settled.

### Decision
- Agent defaults unchanged (`search_depth=3`, `final_search_turns=5`) until the
  determinization test runs; manifests now record the search configuration.
- The result is an **upper bound** on the planning benefit: the search applies
  real actions to the full state, so it sees the true next deck card and the
  opponent's actual hidden hand. Draws falling with search is evidence against
  the deck-peek explanation, but not proof.
- Per-game timings are not reported; arms shared the machine unevenly.

### Follow-up tasks
1. Determinized search (shuffle unseen deck, re-sample opponent hand per
   branch, seeded from the state hash); re-run depth 3 every turn. Success
   criterion: gain vs depth 1 survives at p<0.05, or the leak is quantified.
2. Game-horizon evaluator ablation (`_turns_remaining_for_player` returns the
   round's remaining cubes, not the game's).
3. Re-run the feeder-odds ablation on the searching agent.
4. Resource-spending doc corrected: `net_value_response` win-share drop is
   p=0.038 paired (the table's p=0.199 was unpaired); score p=0.27; reading
   unchanged.

## Update: 2026-09-06 - Determinized search: the gain is planning, not peeking

### What changed
`PotentialPointsAgent` gained `determinization_samples` (module
`wingspan_ai.agents.determinization`): per decision, the bird deck is pooled
with opponents' hands and redealt, likewise bonus cards, and action scores are
averaged over K samples. `K=0` reproduces archived outcomes exactly. Two arms
at K=4, same 200-game paired design. Write-up in
`docs/experiments/determinized_search_test.md`.

### Results
Depth 3 every turn, determinized: **79.40, +10.43 over determinized depth 1
(p<0.001), win 0.90**. The perfect-information version scored 81.83, so the
leak was worth −2.42 (p=0.008), concentrated in bonus-card points (−1.0) and
cached food (−0.7). Determinizing the historic depth-1 agent changed nothing
(+0.70, p=0.47): its one-card draw peek was worthless, so the three valuation
nulls were measured on a clean baseline.

### Why it matters
The first positive result holds up under the player's real information. The
number to quote is +10.4, not +13.5.

### Decision
- Recommended new default: `search_depth=3, final_search_turns=8,
  determinization_samples=4`. Applied 2026-09-06 (Alex's call).
- Feeder rolls remain visible to every agent: legal-action generation bakes
  the reroll outcome into gain-food actions. This is a rules-fidelity defect
  and should be fixed in the engine (reroll as a chance node in
  `apply_action`) before any further search work relies on gain-food values.

### Follow-up tasks
1. Apply the new default and update docs that quote the 68-point agent.
2. Fix reroll resolution in the rules engine; re-run the default on 200 games
   to measure what the reroll knowledge was worth. Replays must still verify.
3. Game-horizon evaluator ablation.
4. Feeder-odds ablation re-run on the searching agent.
5. Merge `rules-fidelity-and-artifact-durability` into `main`.

## Update: 2026-09-06 - Reroll resolved at apply time; knowing the roll was worth nothing

### What changed
The rules engine no longer rolls the birdfeeder while listing gain-food
actions. When a reroll or a mid-action refill would intervene, the action
names a food *preference* and `apply_action` resolves the roll (`b33a5e1`).
Roll salts are unchanged, so archived games still replay to their recorded
hashes. `determinize_state` resamples `random_seed`, so the search sees
rerolls, predator hunts and pink reactions as chance nodes.
`expected_gain_food` gives the non-searching agents the expected value of a
preference. 200-game re-run at the default configuration in
`artifacts/rr_reroll_fix`; write-up in
`docs/experiments/reroll_chance_node.md`.

### Results
Null for every agent: `potential_points` 79.40 → 79.09 (−0.31, p=0.69), win
0.900 → 0.906. Rerolls chosen fell by about half across the roster (PP 5.9% →
3.7% of turns, engine builder 10.9% → 5.0%). 19 of 200 games were
bit-identical; 181 diverged somewhere without the outcome moving.

### Why it matters
The last known hidden-information leak in the search agent is closed and the
+10.4 / 0.90 result survives it. Pre-`b33a5e1` archives overstate reroll
frequency about 2× but their conclusions stand.

### Decision
- `artifacts/rr_reroll_fix` is the baseline for the default agent from here.
- Cost flagged: preference actions can put 70–107 legal actions at a search
  root (four forest birds, dry feeder); one probe decision took over five
  minutes. Collapse near-duplicate preferences inside the search before
  scaling to more players or deeper search.

### Follow-up tasks
1. Game-horizon evaluator ablation (running on branch `game-horizon-ablation`,
   80 `potential_points` games paired against `rr_reroll_fix`).
2. Feeder-odds ablation re-run on the searching agent.
3. Collapse gain-food preference actions in the search beam; measure decision
   time on the 107-action probe state.
4. Merge `rules-fidelity-and-artifact-durability` into `main`.

## Update: 2026-09-07 - Game-horizon ablation: −12 points; the round horizon is load-bearing

### What changed
`PotentialPointsAgent(planning_horizon="round" | "game")` on branch
`game-horizon-ablation` (`042f2d2`); `"game"` counts the cubes in every
remaining round, `"round"` reproduces the baseline bit-for-bit. 80 paired
`potential_points` games (the 120 non-PP games of the full design are
identical by construction) against `artifacts/rr_reroll_fix`. Write-up in
`docs/experiments/game_horizon_ablation.md`. Tracked `.DS_Store` files
untracked; Finder rewrote one mid-run and flipped 39 manifests to
`dirty: true` with no source change.

### Results
**79.09 → 67.09 (−12.00, p<0.001), win 0.906 → 0.631**, negative against
every opponent. Round goals −4.8, eggs −3.7; draws rose from 24% to 37% of
turns, egg lays fell from 28% to 19%.

### Why it matters
Every potential term is linear in `turns_remaining`, and the round-end
terminal rule (score realized points at the last cube) was the evaluator's
only "cash in now" signal. The round horizon encodes Wingspan's per-round
goal scoring and cube reset; the coefficients were tuned against it. A real
game-horizon evaluator needs per-round discounting and re-tuned weights — a
different evaluator, not a switch.

### Decision
- `planning_horizon="round"` stays the default; `"game"` is kept as a
  documented negative.
- The search-depth write-up's round-horizon caveat is resolved.

### Follow-up tasks
1. Collapse gain-food preference actions in the search beam (slowest baseline
   decision: 1262 s at a 100+-action root).
2. Feeder-odds ablation re-run on the searching agent.
3. If a game-horizon evaluator is attempted, build it as per-round discounted
   potential with round-goal terms per remaining round, and re-tune before
   measuring.

## Update: 2026-09-07 - Bounded gain-food search, and the feeder-odds null survives real search

### What changed
Two arms at `4506bdf` (clean worktree, 80 paired `potential_points` games each),
closing follow-up tasks 1 and 2 from the game-horizon entry.

1. **`search_food_candidates` (default 6).** Below the search root, keep every
   non-gain-food action plus the best six gain-food actions ranked by expected
   demand-weighted units (via `expected_gain_food`); the root still scores every
   legal action. Gain-food preference multisets were the compute driver: a root
   has a median of 4 gain-food options but a mean of 10.7 and a max of 100, and
   every node re-listed them. Write-up:
   `docs/experiments/search_food_candidates.md`.
2. **`potential_points.VALUE_FEEDER_ODDS`.** A PP-local ablation switch guarding
   the die-availability multiplier in `_registered_food_power_value`, so the
   ablation no longer changes opponents or the search's own opponent model the
   way the 2026-09-04 module global did. Module switches never reach the
   manifest, so `agent_decision_summary` now records an `ablation_flags` payload;
   all 2,080 decisions per arm carry the right value. Write-up:
   `docs/experiments/feeder_odds_search_rerun.md`.

### Results
- **Pruning: −0.99 points (p=0.074), win 0.906 → 0.863 (p=0.048).** Negative in
  all four opponent cells; the loss is round goals (−0.47) and cached food
  (−0.29), not bird points, and the action mix is unchanged. Cost side: mean
  decision 21.2 → 17.5 s, p99 234 → 161 s, **worst decision 1262 → 491 s**,
  worst game 70 → 30 min — understated, since the pruned arm shared the machine
  and the baseline did not (a back-to-back probe measured 33.7 → 9.4 s).
- **Feeder odds off: +0.49 (p=0.470), win −0.013 (p=0.656).** Null again, on a
  depth-3 determinized agent searching every turn. The 2026-09-04 null was not
  an artefact of the dead `search_depth`.

### Why it matters
The two results point the same way. Planning changes this agent (+10.4 for
depth/coverage, −12.0 for the wrong horizon); the coefficients inside the
evaluator do not. Restricting the *search* costs a measurable point, while
deleting a *valuation term* costs nothing — the constraint is what the agent
does with a valuation, not the valuation's fidelity. Four valuation nulls now,
one of them re-tested against the objection that killed the others' standing.

### Decision
- `search_food_candidates=6` stays the default: arms per week is the binding
  constraint, and ~1 point of a 78-point agent buys a third off the tail. Any
  claim about how strong `potential_points` *is* must use `None` or say it is
  the pruned agent's number. Arm-vs-arm contrasts are unaffected when both arms
  share the setting.
- `VALUE_FEEDER_ODDS` stays `True` in both modules, on correctness grounds only.
- Manifests record `potential_points_search: null` when defaults are used; the
  per-decision payload is what identifies an arm.

### Follow-up tasks
1. Optional: N=12 pruning arm if the ~1 point matters (80 games, ~10 h).
2. Cheap opponent model in the search — the greedy model evaluates all its own
   legal actions and is ~40% of what remains.
3. Untested: mat-scaling and resource-spending nulls have not been re-run on the
   searching agent.

## Update: 2026-09-16 - Belief posterior as the search's opponent model (built, arm not run)

### What changed
`src/wingspan_ai/agents/search_opponent.py` and
`PotentialPointsAgent(search_opponent_model="greedy" | "belief")`. The greedy
model is unchanged and stays the default, pinned to `GreedyBaselineAgent` by a
regression test. The belief model plays each opponent turn inside the search as
the action family the `OpponentBeliefState` posterior finds most likely (from
public candidate values only, ~0.2 ms) and picks within the family by a proxy
that never applies an action. `PotentialPointsAgent` now implements
`observe_action`, so the runner's hook Bayes-updates the posterior from real
actions; search branches read it and never write it. Threaded through
`PotentialPointsSearchConfig`, the manifest, `_make_agent`, and decision
telemetry, which records the posterior per opponent. 15 tests in
`tests/test_search_opponent.py`; suite at 361 passing.

Plan and registered predictions in
`docs/experiments/search_opponent_model_test.md`. Probe tool:
`analysis/search_opponent_profile.py`.

### Compute probe
Back-to-back on 26 real decisions (seed 1 vs `archetype_engine_builder`):
**41.1% less decision time** (142.9 s → 84.2 s; worst root 32.5 → 20.5 s),
40.8% on the heavy decisions, same action on 24 of 26. Clears the registered
30%. Larger than the 40% profiling share because the opponent model is paid
at every tree node, so its share grows with depth.

### Why it matters
This is the first place a belief posterior changes a `potential_points`
decision, and it arrives as the cheap opponent model the search-cost follow-up
asked for. Which of the two matters is what the arm will say: the registered
score prior is null within ±1.0 points, with a non-inferiority gate of ≥ −1.0
before the switch can become the default.

### Diagnostic found
The posterior against `archetype_engine_builder` collapsed to
`food_acceleration` at 0.9995 after 25 observations. Behaviourally defensible
(the archetype gains food on 36% of turns, its plurality family) but far too confident: the
profile priors are hand-tilted and were never fitted to this roster, and each
observation is scored as an independent draw. The 2026-08-31 follow-up to refit
family priors from round-robin telemetry is the fix and is still open.

### Follow-up tasks
1. Commit on a clean tree, then run the 80-game belief arm against
   `artifacts/rr_food_cand6` (three lineup groups × five two-seed chunks, as
   before). Contrast with `analysis/arm_contrast.py`.
2. Read the posterior in the arm's telemetry: does it concentrate, and does the
   predicted family match the family each opponent kind actually plays?
3. If the arm passes the gate, make `belief` the default and re-baseline; if it
   fails, try `search_food_candidates=None` + belief against the current
   default before deciding.
4. Refit belief profile priors from round-robin telemetry (open since
   2026-08-31); the collapse above is the motivation.

## Update: 2026-09-16 - Belief opponent model arm: null on score, decision cost halved

### Results
80 paired games at `b9805bc` against `artifacts/rr_food_cand6`, all manifests
clean and reproducible, all replays valid. `potential_points` **78.10 → 78.41
(+0.31, p=0.73), win 0.863 → 0.875 (+0.013, p=0.74)**; per-opponent cells two
up, two down, none significant; action mix unchanged to within half a point.
Only 3 of 80 games were identical — the search sees a different imagined
opponent almost everywhere and the outcome does not move. Both registered
predictions held and the non-inferiority gate passed. Write-up in
`docs/experiments/search_opponent_model_test.md`.

Decision cost over the 2,080 `potential_points` decisions: mean 17.5 → 7.6 s,
p99 161 → 63 s, worst 492 → 179 s, per game 454 → 197 s, **arm total 10.1 h →
4.4 h** (wall clock 1 h 15 min with four runners). The back-to-back probe's
41% is the clean number; the arm's 57% is the realized bill.

### The posterior identifies behaviour, not type
At game end the belief had concentrated (top-profile mass 0.73–0.88) and its
top profile matched each opponent's actual plurality family: engine builder
and greedy both read as `food_acceleration` (they gain food on 35% and 45% of
turns), net-value as `card_draw` (42% draws), bonus-focus as `card_draw` (36%).
`value_maximizing` won only 2 of 20 games against greedy, the roster's purest
maximizer, because that profile's likelihood is a softmax over *public
candidate values* that rank families differently from greedy's real scoring.
The model is a consistent action-mix classifier and an overconfident type
classifier. Refitting profile priors from round-robin telemetry (open since
2026-08-31) is the fix.

### Why it matters
This is the fifth null on a modelling term, but the first measured with a
belief in the loop of a real search: a posterior that tracks the opponent's
action mix changed thousands of imagined opponent turns per decision and the
score did not move. The engineering fact is the useful one — the search is
robust to a far cruder opponent model, so the opponent model is not where its
strength lives, and arms now cost half what they did.

### Decision
Recommended, pending Alex's call: make `search_opponent_model="belief"` the
default and re-baseline on `artifacts/rr_belief_opp`. Greedy stays as the
documented control.

### Follow-up tasks
1. Apply the default (if approved) and re-baseline; update the README agent
   description.
2. Refit belief profile priors per opponent kind from round-robin telemetry;
   then re-test whether `value_maximizing` becomes identifiable.
3. With arms at ~4.4 h, the bonus-card selection study (requested 2026-08-31,
   prerequisites now met) is affordable — next experiment.
4. The pruned-vs-unpruned question (`search_food_candidates`) could be re-asked
   at N=12 now that the other half of the search cost is gone.

## Update: 2026-09-16 - Belief opponent model is the default, with a 5% standing control

### Decision (Alex)
`search_opponent_model="belief"` is the default; `artifacts/rr_belief_opp` is
the baseline for the default agent. Alex flagged two risks with adopting on
one null arm: a false positive at n=80, and a bias hazard once agents learn
from past games, since everything they would learn from would have been
searched with one opponent model. Both are handled by a holdout rather than by
trust.

### What changed
- `PotentialPointsSearchConfig` gained `search_opponent_holdout_share` (0.05)
  and `search_opponent_holdout_model` ("greedy"). The flow resolves the
  effective model per game from a SHA-256 draw over
  `(random_seed, lineup, lineup position)` — reproducible, identical across
  seed-matched arms so pairing survives, and identical across seat rotations so
  the control subset is counterbalanced.
- Manifests record the effective model per `potential_points` seat in
  `games[].search_opponent_models` with a `holdout` flag; decisions already
  record it.
- `analysis/holdout_guardrail.py` pools artifact roots and reports the unpaired
  preferred-vs-held-out contrast with a detection limit, and refuses to call
  fewer than 40 held-out games a finding.
- 23 tests in `tests/test_search_opponent.py`; suite 368 passing.

### What to expect
The standard 80-game design holds out 6 games; seeds 1–30 hold out 8 of 240.
The control accrues across every batch run with the default, so the guardrail
becomes readable after roughly ten arms, not one. That is the intent: a
long-run check, not a per-arm test. Any arm-vs-arm contrast is unaffected
because both arms hold out the same games.

### Follow-up tasks
1. Run `analysis/holdout_guardrail.py` over all default-agent roots at each
   experiment write-up and quote it once ≥40 held-out games exist.
2. If a learning agent is added, key its training data on
   `search_opponent_models` so the held-out games can be excluded or weighted.

## Update: 2026-09-16 - Bonus-card selection study designed and launched

### What changed
Alex's 2026-08-31 question, with two objectives added today: whether some
bonus cards are better because of inherent synergy with the birds that qualify
for them, and the reverse for birds — whether some are better picks because
they work with good bonus cards and round goals or are simply overpowered for
their cost. Plan, registered predictions and the companion bird-value study in
`docs/experiments/bonus_card_selection_study_plan.md`.

Built:
- `ForcedBonusCardSetupPolicy(base_policy, dealt_index)`: keeps the dealt card
  at an index and lets the agent's own policy choose birds and food around it.
  `forced_bonus_choice={agent_kind: index}` on the batch and round-robin flows,
  applied to the study agent only and recorded in every manifest.
- `analysis/bonus_card_seed_coverage.py`: scans seeds cheaply (setup only) and
  picks the fewest that deal every card at least N times to the study seat.
  111 seeds give all 26 cards 8–11 paired units.
- `analysis/bonus_card_keep_contrast.py`: per-card paired advantage from the
  two forced arms, realized bonus points, completion rate, how much the choice
  is worth in absolute terms, and the current policy's hindsight accuracy
  computed from the deal without extra games.
- `analysis/card_structure.py`: static synergy tables. Bonus side: qualifying
  supply per card (count, deck share, expected qualifiers in the opening hand,
  mean VP/cost/eggs, brown share, power score, habitat split). Bird side: VP,
  cost, eggs, nest, habitats, power, bonus coverage, cost-efficiency, with a
  `--card-values` weight once the study has measured the cards.
- 6 tests in `tests/test_bonus_card_keep_study.py`.

### Structural finding before any game ran
Qualifying supply spans 43% of the deck (Bird Feeder, Backyard Birder — but
they need 5–8 birds for 3–7 points) to 11% (Historian, Food Web Expert, at
2 per bird). Four cards score from board state and have no qualifiers. This is
the basis for registered prediction 3: advantage should track expected
opening-hand qualifiers × points per qualifier.

### Content caveat found
The catalog's 26 bonus cards include `Anatomist [swift_start_asia]` and
`Visionary Leader`, while birds carry tags for `Diet Specialist` and `Bird
Bander`, which are not in the deck. Which 26 the physical base game ships needs
settling before any of this is quoted as a Wingspan claim.

### Launch
222 games (111 seeds × forced index 0 / 1), `potential_points` vs
`archetype_engine_builder`, rotation 0, agent-default setup, four runners.
Artifacts under `artifacts/bonus_keep/force0` and `force1`.

### Follow-up tasks
1. Read the result against the five registered predictions; write §8.
2. Replicate with `archetype_engine_builder` as the study agent (pursuit
   confound).
3. Bird-value study layer 2: per-bird scorecard event at game end, then the
   observational regression over archived games.
4. Settle the base-game bonus-card composition question.

## Update: 2026-09-16 - Bonus-card keep study: the choice is worth six points, per-bird cards win, synergy is power quality not breadth

### Results
222 games at `010cf7b`, 111 forced-keep pairs, all replays valid, 3 h 06 min
on four runners. Full write-up in
`docs/experiments/bonus_card_selection_study_plan.md` §8.

- **The keep decision is worth 6.4 points on average**; 58% of deals swing 5+
  and the largest swing was 29. The current `PotentialPointsSetupPolicy` picks
  the better side on **50%** of decided deals — a coin flip.
- **Per-bird cards beat their dealt partners by +3.25 (p=0.009, 51 units)**;
  tiered cards −0.93 (n.s.), board-state cards −1.12 (n.s.). Falconer +7.0,
  Bird Counter +6.4, Omnivore Expert +4.4 lead; Viticulturalist −5.4,
  Enclosure Builder −4.8, Bird Feeder −3.9, Large Bird Specialist −3.3
  (p=0.02) trail. Per-card resolution is ±7 points; the ranking is the
  deliverable.
- **Registered synergy prediction reversed** (ρ = −0.40): breadth of
  qualifying supply predicts *worse* keeps, because the broad cards are the
  tiered ones whose thresholds a 10–12-bird board rarely reaches. Post hoc,
  what tracks value is the payoff shape (per-bird ρ +0.49) and the qualifiers'
  power quality (power score +0.39, brown share +0.34). Answer to Alex's
  question 4: yes, a card is good when every qualifier pays and the qualifiers
  are engine birds the agent plays anyway.
- **Printed bonus points are the wrong lens**: realized bonus points when kept
  correlate ρ = 0.15 with keep value. Visionary Leader scores the most bonus
  points (8.44) and has negative keep value (−1.33).
- The weighted bird table (`card_structure.py --birds --card-values
  artifacts/bonus_keep/card_values.json`) is now a feature for the bird-value
  study: cheap brown birds covering Falconer/Bird Counter/Omnivore lead.

### Why it matters
First strategy findings about *content* rather than agents, with a registered
design, and they cost three hours. The setup decision is the largest single
lever this agent misuses; a per-bird preference would already beat its policy.

### Follow-up tasks
1. Replicate with `archetype_engine_builder` as the study agent.
2. Build a per-bird-preferring (or learned) keep policy behind a switch;
   success criterion >60% hindsight accuracy on fresh seeds, then a paired arm.
3. Bird-value study layer 2: per-bird scorecard event, observational
   regression over archived games.
4. Settle the base-game bonus-card composition (Anatomist / Visionary Leader
   in; Diet Specialist / Bird Bander out).

## Update: 2026-09-16 - Replication, the expected_points opener, bird scorecards, and composition settled

### Replication (pursuit confound)
Forced-keep study re-run with `archetype_engine_builder` as the study agent
vs `greedy_immediate`: 211 coverage seeds, 422 games, 27 minutes. The stake
replicates (6.8 points per deal) and so does the ordering: per-bird +1.61,
tiered **−1.25 (p=0.043)**, gap +2.9 (was +4.2). Individual card ranks agree
only moderately across pursuers (ρ=0.33) and board-state cards flip positive
for an egg-laying non-pursuer (Breeding Manager +7.5). Standing claim: a
linear payoff beats a threshold; per-card values are pursuer-dependent.

### The historic opening policy is worse than arbitrary
`_bonus_alignment_score` hand-codes keyword matches for Bird Feeder and
Backyard Birder — two of the worst keeps — and otherwise adds the bird's
*total* tag count regardless of the card scored (the 2026-08-31 archetype tag
bug, again). `dealt_first`, an arbitrary rule, beats it by +0.87 (p=0.031)
over 322 measured deals.

### `expected_points` opener (behind a switch)
`PotentialPointsSetupPolicy(bonus_scoring="expected_points")`: expected
points from the printed formula, printed prevalence and hand qualifiers;
Poisson expectation for tiers; neutral prior for board-state cards. Scored
on the archived forced games with no new runs (`analysis/keep_policy_eval.py`,
the "free paired arm"): **+0.85 (p=0.011), 61% vs 52%** over 322 deals;
62% out of sample on the engine-builder deals. Registered criterion met.
Captures ~¼ of the 3.4–4.1-point oracle headroom. Default unchanged pending
Alex's call; recommended to adopt and re-baseline.

### Bird-value layer 2
`bird_scorecard` event (per player at game end: points, eggs, cached food,
tucked cards, power activations, round played, tags per bird; activations
tracked on `BirdSlot` but excluded from dumps so hashes and replays are
unchanged) and `analysis/bird_value_regression.py` (ridge on birds played,
agent fixed effects, pure Python). Over 6,544 archived player-games: average
bird +6.3 on the board; Burrowing Owl +8.0 above that (n=865), Barn Swallow
+6.3, Bushtit +6.1, Brewer's Blackbird +5.9; Song Sparrow −7.9, Bobolink
−7.4, Turkey Vulture −6.7 (n=553). Observational; scorecard columns fill in
as new games accrue.

### Composition settled
Workbook `Set` column: Bird Bander and Diet Specialist are `european`;
Anatomist/Cartographer/Photographer `core, asia`; Visionary Leader `core`.
The 26 cards dealt are the base-game deck. `docs/rules/bonus_card_composition.md`.

### Follow-up tasks
1. Alex: adopt `expected_points` as the opener default and re-baseline?
2. A keep model on the 322 measured deals (hand, round goals, card) to chase
   the remaining ~3 points of headroom; hold out the engine-builder deals.
3. Bird-value layer 3 (forced bird keep) in waves by feature class, using
   `bird_value_coefficients.json` and the weighted bonus coverage to pick the
   first wave.
4. Fix `_bonus_alignment_score`'s card-independent tag term where it also
   drives bird selection (`_selection_score` weights it 1.8).

## Update: 2026-09-16 - expected_points is the opener default; re-baseline arm launched

### Decision (Alex)
`PotentialPointsSetupPolicy` defaults to `bonus_scoring="expected_points"`
(policy id `potential_points_setup_v2`); `tag_overlap` remains as v1 behind
the switch.

### A thing worth knowing
Every round-robin arm to date ran with `setup_policy_kinds=["control"]`, which
puts *all* agents on `default_setup_v1`. The champion's 0.90 win rate never
used its own strategic opener, so `rr_belief_opp` is unaffected by this
change, and "does the searching agent's own opener beat the control opener?"
has never been measured. Added `setup_policy_overrides={agent_kind: kind}` to
the flows so one agent can use `agent_default` while the lineup stays on
`control`; manifests now record `setup_policy_ids` per seat.

### Re-baseline arm (registered; result below)
Standard 80-game design at `rr_belief_opp`'s settings plus
`setup_policy_overrides={"potential_points": "agent_default"}`; artifacts
`artifacts/rr_opener_v2`. Prediction: `potential_points` **+1 to +3 points**
over `rr_belief_opp` — the v2 opener fixes a bonus choice worth ~0.85 and
also keeps birds/food strategically, which `control` does not. If it lands
null or negative, the strategic bird/food selection is suspect (its
`_bonus_alignment_score` term is the same card-independent tag count).

### Re-baseline result (2026-09-16): the v2 opener loses to the control opener
`artifacts/rr_opener_v2` vs `rr_belief_opp`, 80 paired games at `e218d13`:
`potential_points` **78.41 → 75.41 (−3.00, p=0.022)**, win 0.875 → 0.875;
by opponent −7.7 (bonus_card_focus, p=0.006), −3.65, −1.05, +0.40. The
registered prediction (+1 to +3) failed on the branch registered for it: the
bonus choice is worth +0.85, so the opener's bird/food selection costs about
four points. `_selection_score` keeps up to five birds and no food and weights
the card-independent `_bonus_alignment_score` term at 1.8. Round robins run
under `control`, so the champion's baseline is unaffected and `control` stays
the design. **Defect to fix:** `PotentialPointsSetupPolicy` bird/food
selection; measure against `default_setup_v1` with the same free paired-arm
trick once a variant exists. The forced-keep study's per-card deltas were
measured *conditional on* that bird selection and should be re-read after.

## Update: 2026-09-17 - Synergy programme: rules bench, counterfactual play attribution, hierarchical model

### What changed (Alex's direction: play-level value and card combinations)
Documented as a new agent, `docs/agents/synergy_planner_agent.md`. Built:
- **Activation ledger.** Every power resolution credits its owner-level yield
  to the bird (`BirdSlot.power_yield`, excluded from dumps like
  `activations`); `bird_scorecard` carries it.
- **Layer A, `analysis/card_synergy_bench.py`.** Rules-computed synergy for
  every same-habitat brown pair in both orders, on a size-matched blank
  baseline, over three seeds × rich/scarce contexts: 12,386 ordered pairs in
  47 s, 2,029 interact. Gray Catbird / Northern Mockingbird (repeat a brown
  power) are the universal partners (+2 eggs next to the "lay an egg on any
  bird" sparrows, +1.5 next to tuck birds). Rarity is not an obstacle: every
  pair is scored, dealt or not.
- **Layer B, `analysis/play_counterfactuals.py`.** Every archived
  `play_bird` decision reconstructed (the replay validator's path) and rolled
  out three ways under cheap continuations — actual, not-now (timing value),
  never (card value). 2,698 plays over 382 `potential_points` games in ~25
  min on four shards. `play_attribution_summary.py` aggregates with
  empirical-Bayes shrinkage; `analysis/r/play_attribution_hierarchical.R`
  fits bird + mechanic-pair random effects in lme4 (rebuilt from source to
  fix a Matrix ABI mismatch).

### Findings
- A play is worth **+4.2** to the final score on average, but **+5.2 on
  arrival and −1.0 downstream**: printed value overstates late plays because
  the alternative (eggs) was worth more. Round 1 downstream is **+1.5**,
  round 4 **−3.4**. Timing is a steady +1.4.
- Top causal card values (shrunken): Brown Pelican +6.2, Turkey Vulture +5.6,
  Barn Swallow +5.4, Common Grackle +5.4, Black-Billed Magpie +5.1.
- Mechanic interactions: `tuck_card × deck_search_tuck` +3.0 (n=51),
  `all_players_draw_cards × predator_hunt` +3.4; first engine play on an empty
  board +5 (deck-search tuck, lay-egg, feeder food).
- **Observed ≠ causal: ρ = 0.07** between the observational ridge and the
  counterfactual card value. Turkey Vulture: −6.7 observed, +5.6 causal. The
  ridge measures who plays a bird and when; only the counterfactual belongs
  in an evaluator.
- Bench single-bird yield vs counterfactual value ρ = 0.20; card-pair lift is
  too sparse at n ≥ 10, mechanic-level is where A and B meet.

### Follow-up tasks
1. Layer C: forced-play confirmation of the top mechanic pairs (tuck × tuck,
   draw × predator) — needs a keep-and-play forcing instrument.
2. Engine-potential term in `potential_points` from the mechanic-pair model,
   behind a switch; registered prediction +1 to +3.
3. Bench extensions: cross-habitat chains over several activations, white
   on-play, pink reactions.
4. Determinized continuations (several samples per branch) if per-play
   residual SD 4.7 proves too noisy for card-pair estimates.
5. R environment: `lme4` was reinstalled from source on 2026-09-17; `brms`
   for a full posterior when it is worth the compute.

## Update: 2026-09-17 - Layer C instrument, engine-potential term, arms launched

### Layer C (forced keep-and-play)
`agents/forced_play.py`: `inject_opening_cards` swaps named birds into a
dealt hand from the deck (recorded in `game_started`, re-applied by the replay
validator so hashes verify); `KeepBirdsSetupPolicy` keeps them, displacing the
base opener's birds rather than its food; `ForcedPlayAgent` plays them into a
shared row as soon as legal, waits rather than split the pair, steers gain-food
toward a waiting bird's fixed cost, and never lets a forced play eat its
partner's food. Flows take `opening_hand_overrides` / `forced_play_birds` per
agent kind. `analysis/forced_play_contrast.py` computes the 2×2 interaction
`(AB − AB') − (A'B − A'B')` per seed with matched non-interacting controls.

Arms launched (cheap study agent `archetype_engine_builder` vs greedy,
`control`, rotation 0, 60 seeds × 4 arms × 3 pairs = 720 games,
`artifacts/forced_play/cheap/`):
- P1 Common Grackle + Cooper's Hawk (tuck × deck-search-tuck; layer B +3.0),
  controls Eastern Phoebe / Yellow-Bellied Sapsucker.
- P2 Canvasback + Anhinga (all-players-draw × predator; layer B +3.4),
  controls Black-Chinned Hummingbird / Osprey.
- P3 Baird's Sparrow + Northern Mockingbird (lay-egg-any × repeat; layer A
  +2 eggs per activation), controls Eastern Phoebe / Indigo Bunting.
Registered predictions: P3 interaction **> +2** (the bench says +2 eggs per
activation and the mockingbird is a pure amplifier); P1 **+1 to +3**; P2
**0 to +2** (layer B's +3.4 was measured on a searching pursuer; the archetype
does not exploit extra cards well). Smoke completion: pairs land in the same
row 8/8 when both are played, both played ~65–100% of seeds depending on food.

### Engine-potential term (registered)
`PotentialPointsAgent(mechanic_synergy=True)` adds `mechanic_synergy_potential`
to the evaluator: for the board, the measured (played power × power on board)
effects between every pair of played birds, scaled by turns left in the round;
for the hand, each card's positive lift against the board (or its first-play
value on an empty board) at a 0.6 play rate. Table:
`configs/synergy/mechanic_pair_effects_v1.json` (584 pairs from the lme4 fit).
Threaded through the search's terminal values and the config/manifest;
off by default. Arm: standard 80-game design vs `rr_belief_opp`,
`artifacts/rr_synergy_term`. **Registered prediction: +1 to +3 points**,
concentrated in bird points and eggs, draws rising as the agent holds partial
combos; null is the honest prior after four valuation nulls, and a card-choice
term is the one kind that has paid.

## Update: 2026-09-17 - Engine-potential term: −4.5, a clear negative; layer C v1 instrument flaw found and fixed

### Engine-potential term
`rr_synergy_term` vs `rr_belief_opp`, 80 paired games: `potential_points`
**78.41 → 73.90 (−4.51, p=0.001)**, win 0.875 → 0.800, negative against every
opponent. Registered +1 to +3 failed. The mechanism engaged (draws 24.3% →
27.9%, plays and egg-lays down) and cost bird points −2.8, round goals −0.9,
eggs −0.8, tucks −0.5. Diagnosis: the hand term pays for *holding* combo
pieces, and the effects double count what a depth-3 search already realizes.
Term stays off. One more arm is worth running: board-only with halved
effects; if negative too, the synergy evidence belongs in card-selection
decisions (opener, draw choice), not the evaluator. Fifth valuation-term
null-or-worse; the pattern holds.

### Layer C v1: the instrument was measuring itself
Cheap pursuer, 60 seeds: P1 interaction −8.25 (p=0.01) with the pair
completing in only 11/60 seeds — because **Common Grackle's tuck-from-hand
power was tucking Cooper's Hawk**, and a food grant was being overwritten by
the opening choice. P2 +0.27 (n.s., 34/60 complete), P3 +0.03 ITT but +2.40
on the 42 completed seeds (n.s.). Fixed (`d2ad2d1`): the wrapper rejects any
action whose resolution removes a waiting forced bird from hand, steers to
lay-eggs when the shared row needs one, and `opening_food_bonus` is granted
after setup and replayed. Completion 12/12, 11/12, 12/12 on smoke. Re-run at
240 seeds per pair in flight (`artifacts/forced_play/v2`).

### Bench extensions
`cross`: 783 of 24,868 ordered cross-row pairs interact, but the dominant
pattern is deck-order coupling (a wetland draw changes the card a deck-search
predator then sees); real chains underneath: draw-then-tuck (Wood Duck →
Bushtit/Common Grackle, +0.75 when the hand is empty) and cross-row egg
capacity (Pileated Woodpecker → grassland birds with room, +2.0). `onplay`:
no interactions detected; the blank baselines share nest types with
residents, so nest-conditional whites are masked — needs an empty-row
baseline with egg-cost adjustment. `pink`: the cowbird class confirmed
(Loggerhead Shrike + either cowbird, +1 egg per opponent lay-eggs action);
pink reactions now credited to the ledger.

## Update: 2026-09-17 - Layer C at 240 seeds: one pair confirms, one is null, one reverses

`artifacts/forced_play/v2`, cheap pursuer, 2,880 games, completion 88–95%:
- **P2 Canvasback + Anhinga (all-players-draw × predator): +3.48 (p=0.021)**
  — layer B's +3.4 confirmed.
- P1 Common Grackle + Cooper's Hawk (tuck × deck-search-tuck): −1.06 (n.s.) —
  layer B's +3.0 does not appear for a non-searching pursuer.
- **P3 Baird's Sparrow + Northern Mockingbird (lay-egg-any × repeat): −3.38
  (p=0.005)** — the bench's +2 eggs per activation reverses because egg
  capacity binds in play; the mockingbird displaced a food bird. A synergy
  that spends a shared cap is worth only what the cap allows.

Confirmation rate across the three layers: one of three. The bench needs a
capacity-aware context before egg synergies are read; layer B carries a
pursuit confound that layer C exposes. `analysis/forced_play_contrast.py`;
per-pair reports under `artifacts/forced_play/v2/P*_contrast.md`.

### Determinized continuations
On 588 matched plays, K=4 determinized rollouts leave the mean unchanged
(+3.94 → +4.04) and cut the within-bird SD **36%** (8.28 → 5.27); per-bird
ranks between K=0 and K=4 agree only at ρ=0.54, so a real share of the K=0
ordering — and of the mechanic-pair table the engine-potential term used —
was path noise. Full K=4 attribution over all 382 games in flight; the pair
table will be rebuilt from it (`mechanic_pair_effects_v2`).

## Update: 2026-09-17 - K=4 attribution: the K=0 mechanic-pair table was mostly noise

Full re-attribution of all 2,698 plays with four determinized continuations
per branch. Aggregate unchanged (+4.27 card value, +1.62 timing; round shape
intact); lme4 residual SD 4.69 → **3.03**; per-bird ranks agree ρ=0.54 with
K=0, mechanic-pair ranks only **ρ=0.31**. `tuck_card × deck_search_tuck`
+2.96 → −0.04; `all_players_draw_cards × predator_hunt` +3.39 → −0.18. The
table that picked two of layer C's pairs and fed the engine-potential term
was path noise; `mechanic_pair_effects_v2.json` (K=4) replaces it as the
term's table, unmeasured. Layer C P1's null matches v2; P2's +3.48 is the one
surviving positive and is borderline after correction for three tests.

### Follow-up tasks
1. Engine-potential term, board-only variant on the v2 table with halved
   effects — one 80-game arm; if negative, move synergy evidence into the
   opener and draw choice instead of the evaluator.
2. Layer A egg synergies in a capacity-aware context (near-full boards).
3. Layer C on a searching pursuer for P2 only (the surviving pair).
4. K=4 is the standard for any future attribution run; note the 4× cost.

## Update: 2026-09-17 - Follow-ups launched: board-only synergy term, layer C P2 on the searching pursuer

### K=4 is the standard
`play_counterfactuals.py --continuation-samples` defaults to 4; any future
attribution run pays 4× and gets a value that does not depend on one deck
order.

### Arm A (registered): board-only synergy term
`PotentialPointsSearchConfig(mechanic_synergy=True, mechanic_synergy_hand=False,
mechanic_synergy_weight=0.5)` on the v2 (K=4) table, 80 games vs
`rr_belief_opp`, `artifacts/rr_synergy_board`. Prediction: **−1 to +1** —
removing the hand term removes the holding incentive that cost 4.5, and the
v2 board effects are small (pair SD 1.2), so the honest prior is a null; a
negative below −1.5 means synergy evidence belongs in card-selection
decisions (opener, draw choice), not the evaluator.

### Arm B (registered): layer C P2 with `potential_points` as pursuer
Canvasback + Anhinga vs Black-Chinned Hummingbird / Osprey, 2×2, 60 seeds,
`potential_points` (defaults) vs greedy, `control` setup, food bonus 2,
`artifacts/forced_play/pp/P2`. Prediction: interaction **0 to +3**; confirmed
if > 0 at p < 0.05. The K=4 table says the mechanic pair is ~0 for the
searching agent's own plays; the cheap-pursuer arm said +3.5; this arm
decides between them.

### Layer A, capacity-aware (2026-09-17)
`card_synergy_bench.py --contexts capped`: rows pre-filled with egg-full
blanks, placed birds one egg below their limit. Grassland pairs with positive
egg synergy: **830 → 34**; mean egg synergy 0.94 → 0.04; the P3 pair +2.00 →
0.00. The bench's egg synergies measured egg room, not the pair — the layer C
reversal reproduced in three seconds. Egg synergies are now reported at both
ends; anything fed to an agent must be weighted by how often the cap binds.

### Arm A result (2026-09-17): board-only synergy term is a small unresolved positive
`rr_synergy_board` vs `rr_belief_opp`: `potential_points` **78.41 → 79.72
(+1.31, p=0.17)**, win +0.013; 21 of 80 games bit-identical; action mix
unchanged; +0.6 bird points, +0.7 eggs. Inside the registered −1…+1 band at
its upper edge. Removing the hand term removed the harm (−4.5 → +1.3); what
remains is below the 80-game detection limit (~1.9). Decision: term stays
off; not adopted, not moved to the opener either — the registered
"move synergy evidence to card-selection" trigger (below −1.5) did not fire.
Worth one 200-game arm if the pipeline is idle; otherwise parked.

### Arm B result (2026-09-17): layer C P2 on the searching pursuer is null
`artifacts/forced_play/pp/P2`, 240 games (~6 h shared with another project):
interaction **−1.67 (p=0.35)**, −1.96 on 51 completed seeds; main effects
−1.2 / −1.2. The cheap pursuer's +3.48 does not transfer; the K=4 table's
−0.18 for this mechanic pair on the searching agent's plays was right. No
pair confirms for the searching agent across layer C.

### Synergy programme: standing conclusion
Pair-level synergy in 2p base Wingspan, as played by these agents, is small
next to card main effects, pursuer-dependent, and capacity-dependent. The
evaluator is not where combination evidence pays (−4.5 with a hand term,
+1.3 n.s. board-only). Next uses of the evidence are card-choice decisions:
the opener (bird main effects from layer B/C, capacity-aware bench) and the
draw choice. Instruments and lessons in `docs/agents/synergy_planner_agent.md`.

### Follow-up tasks (consolidated)
1. Opener: fix `PotentialPointsSetupPolicy` bird/food selection (−4 vs the
   plain opener) using layer B's bird card values (K=4, shrunken) as the bird
   scorer; free paired-arm evaluation on the bonus-keep deals where possible,
   then one 80-game arm.
2. Draw choice: tray-card preference from the same card values, behind a
   switch; one arm.
3. Keep model on the 322 measured deals (hand, round goals, card), held-out
   on the engine-builder deals.
4. Oracle opponent-type bound (does perfect type knowledge help at 2p?).
5. Holdout guardrail: run `analysis/holdout_guardrail.py` over all default-
   agent roots at the next write-up (rr_belief_opp, rr_opener_v2,
   rr_synergy_term, rr_synergy_board, bonus_keep, forced_play/pp).

## Update: 2026-09-17 - Decision-tree profiling and value per millisecond

### What changed
`agents/profiling.py`: a game-agnostic `DecisionProfiler` active per decision
and per opening choice; `profiling.node(name, aggregate=True, **metadata)` is
a no-op without an active profiler (~0.3 µs), aggregates hot nodes, reports
self time so shares add up, counts cache hits. Runner attaches
`decision_profile` (`summary` by default, `tree` on request, `off`) to
`agent_decision_summary` and `setup_selection_applied`; flows and manifests
carry `decision_profile_mode`. Instrumented: the whole potential_points
search, both opponent models, net_value, Monte Carlo, guardrails, openers.
Overhead 2–3%; 1.5 KB per decision. `analysis/decision_profile_report.py`
gives latency percentiles by agent/player count/round, the node table, and
`--value-against` points-per-second with a keep/optimize/drop/gate class.
Doc: `docs/architecture/decision_profiling.md`. 402 tests.

### Ledger (from the archive, every arm has per-decision latency)
Search depth 3 vs 1: +10.4 for 121 → 9,366 ms (**optimize**). Belief opponent
model: ≈0 for −57% latency (**keep**). Gain-food pruning: −1.0 for −18%
(neutral). Board-only synergy: +1.3 n.s. for +11% (neutral). Full synergy
term: −4.5 for +33% (**drop**). v2 opener: −3.0 (**drop**).

### Where the time goes (104 profiled default decisions)
`expand_children` **73%** at 12.5 ms per child versus `opponent_apply` at
0.17 ms for the same transition in place — the `GameState` deep copy is ~98%
of expanding a child. `terminal_value` 19% (4,677 leaves per decision).
Opponent model 3%. Latency by round: 1.8 → 5.9 → 10.5 → 15.7 s mean.

### Follow-up tasks
1. Incremental apply/undo (or copy-on-write) for search children — the one
   optimization worth ~70% of decision latency; measure with the profiler
   before/after and confirm bit-identical decisions.
2. Beam pre-ranking without expansion, then a `max_decision_time_ms` budget
   on `potential_points` that degrades K → depth → one-ply, each step priced
   by the ledger.
3. Read every future arm through `decision_profile_report.py --value-against`
   as well as `arm_contrast`.

## Update: 2026-09-17 - Fast search-child expansion (−50% latency, bit-identical); every decided arm now has a 5% holdout

### What changed
- **Fast expansion.** The profiler's 73% in `expand_children` was split by a
  single-state probe: per child 0.66 ms = deep copy 0.33 + re-validation of
  the action 0.21 + transition 0.07. `apply_action(trusted=True, lean=True)`
  skips re-validation (the search took the action from the generator on this
  exact state) and copies without the `rng_draw_records` audit trail, which
  grows with the game and which no branch reads. Switch
  `PotentialPointsSearchConfig.search_child_expansion = "fast" | "copy"`,
  default `fast`. **Bit-identical**: 104 decisions of four archived
  `rr_belief_opp` games reproduced action for action; every child of a
  fresh state hashes identically with the trail restored. Back-to-back
  probe (four games, no holdouts): mean decision **5,187 → 2,588 ms
  (×0.50)**, p95 26.0 → 11.7 s, per game 135 → 67 s, identical scores.
  `expand_children` 73% → 53%; `terminal_value` is now a third of the
  decision and the next target. `docs/architecture/decision_profiling.md`.
- **Generalized holdouts (Alex's rule).** `agents/holdout.py`:
  `Holdout(field, value, share)`; `PotentialPointsSearchConfig.holdouts`
  and `resolve_effective(seed, lineup, position)`; `_make_agent` builds the
  agent from the effective fields; manifests record
  `games[].search_holdouts[agent_id] = {effective, applied}`. Each field
  draws independently by SHA-256 over `(field, seed, lineup, position)`, so
  arms stay paired and seat rotations hold out together. The opponent-model
  holdout keeps its 2026-09-16 key. Standing holdouts now:
  `search_opponent_model → greedy`, `mechanic_synergy → True` (board-only),
  `search_child_expansion → copy`, 5% each; with three, ~14% of games
  deviate somewhere, identically on both sides of every pair.
  `analysis/holdout_guardrail.py` reports every field (`--field`,
  `--preferred`); registry, retirement rule and reading guide in
  `docs/experiments/standing_holdouts.md`. Pooled state: belief −1.34 vs
  greedy, p=0.51, 19 held-out games — unreadable by design yet.
- **Standing docs refreshed**: `PROJECT_CONTEXT.md` phase, assets,
  decisions, next tasks, open questions, backlog; `README.md` status and
  next steps; new `docs/experiments/results_ledger.md` (one row per arm
  with score, p, latency, points per second, decision).
- Tests: `tests/test_holdout.py` (draw independence, legacy key stability,
  fast/copy child agreement, identical agent decisions); 415 pass.

### Registered arm (3): measured opener, `potential_points_setup_v3_keep3`
The v2 opener lost −3.0 with a bonus choice worth +0.85, so bird/food
selection costs ~4. Diagnosis on 120 dealt hands: the heuristic keeps
**five birds and no food in 119 of 120** (the plain opener keeps three and
two food). The fix under test changes only *which* birds: each bird's
measured round-1 play value from the K=4 counterfactual fit
(`configs/bird_values/bird_play_values_k4.json`, written by
`analysis/bird_play_values.py`: lme4 shrunken effect + round-1 intercept
4.62; 173 birds), paid greedily from the starting food with a 0.5 discount
when unaffordable; keep count held at the plain opener's three so the arm
reads the bird values alone (`bird_scoring="measured"`,
`target_keep_count=3`; policy id `potential_points_setup_v3_keep3`; the
flow accepts a concrete opener id in `setup_policy_overrides`). On the 120
hands it keeps birds worth 16.9 measured points per deal against the plain
opener's 14.4 (+2.5 at full realization; 1.9 of 3 birds shared).
**Prediction: +1 to +3 vs `rr_belief_opp`; success ≥ +2 (Alex's
criterion); below +1 the values are not causal at keep time and the food
price floats next.** Design: 80 paired games, `setup_policy_kinds=["control"]`
with the study agent on `potential_points_setup_v3_keep3`, four lineup
runners, clean worktree. Note the standing holdouts run inside this arm and
not in the 2026-09-16 baseline; at 5% per field that is ≤ 4 deviating
games per field, all bit-identical for `search_child_expansion`.

## Update: 2026-09-18 - Opener arm running; oracle-type model and decision budget built and registered

### Opener arm (3) in flight
`artifacts/rr_opener_v3`, four runners from the clean worktree at
`70aa484`; manifests confirm `potential_points_setup_v3_keep3` on the study
seat and `default_setup_v1` elsewhere, `dirty: false`.

### Oracle-type opponent model (4), registered
`search_opponent_model="oracle"` (`OracleTypeSearchOpponentModel`): the
belief model seeded from turn one with the posterior it converges to for
each opponent kind by game end, pooled over 56–60 games per kind from three
default-agent roots by `analysis/oracle_type_posteriors.py` into
`configs/belief/oracle_type_posteriors.json`; never updated; reads the
seat's `agent_id`, so a bound and not a candidate default. The table is the
calibration finding in numbers: greedy → food_acceleration 0.49, engine
builder → food_acceleration 0.52, net_value → card_draw 0.77, bonus-card
focus → card_draw 0.41 — the model identifies action mix, not type.
**Prediction: null, −1 to +1 vs `rr_belief_opp`**; ≥ +2 would say inference
speed is the bottleneck and a refit of profile priors to the roster is
worth an arm; a null closes the opponent-model family at 2p and moves the
question to 3–4 players. Cost identical to `belief`. Doc:
`docs/experiments/search_opponent_model_test.md` (follow-up section).

### Decision budget (5), built and probed
`max_decision_time_ms` on the agent and the search config: anytime
decision — one-ply evaluator first, then one ply at a time over the K
samples while the measured cost of the last level says the next fits, as
many samples as fit at the deepest level; degrades K, then depth, then to
one-ply; bit-identical without a budget; `budget = {depth_used,
samples_used, cut_short, elapsed_ms}` on every decision. Probe at 5 s on a
loaded machine (four runners): **max 4,972 ms, never exceeded**; 32 of 104
decisions cut; depth 2 instead of 3 in 23; K < 4 in 12; scores identical
in 2 of 4 games and higher in the other two (n=4, noise).
**Registered arm: 5 s budget vs unbudgeted, 80 paired games vs
`rr_belief_opp`; prediction −2 to 0; success < 2 points lost with p95
under 5 s in every round → production configuration.** Doc:
`docs/architecture/decision_profiling.md`.

### Queue
Compute is the constraint (one laptop, four runners saturate it). Order:
opener arm (running) → oracle arm → budget arm. Launch scripts for the
next two are prepared under `artifacts/<root>/launch/` and start when the
previous arm's `GROUP COMPLETE` lines appear.

## Update: 2026-09-18 - Measured opener: −1.9 (n.s.); observed play value is not keep value

### Result (arm 3)
`artifacts/rr_opener_v3` vs `rr_belief_opp`, 80 paired games at `70aa484`,
clean: `potential_points` **78.41 → 76.51 (−1.90, p=0.13)**, win 0.875 →
0.938 (+0.06, p=0.14); by opponent −3.35 / +1.25 / −1.85 / −3.65, none
significant. Registered +1 to +3: failed. Not adopted; the plain opener
stays the champion's opener in round robins. `analysis/arm_contrast.py`
output in `artifacts/rr_opener_v3/launch/arm_contrast.txt`.

### Why
The measured opener kept birds worth 5.7 measured points (plain opener
4.9) and then played **64% of them instead of 72%, later (round 1.39 vs
1.29), and 6.9 birds a game instead of 7.35**. The K=4 play value is
conditional on the searching agent having chosen to play the bird — in
context, with the food already in hand. Kept at setup, a high-value bird
that costs three food waits for two gain-food actions; the plain opener's
cheapest-cost rule buys the tempo instead, and the 0.5 unaffordability
discount did not price that. Same lesson as the synergy programme:
observed value is not causal value at the decision where it is applied.

### Decision and holdout
Per the standing rule the dropped variant keeps a 5% holdout: a
`setup_policy` entry in `DEFAULT_HOLDOUTS`, resolved by the flow against
the opener the seat would otherwise use and recorded in
`games[].search_holdouts` (registry updated). The opener question is
parked: the plain opener is within 2 points of every variant tried, the
search is worth 10, and the causal keep value would need a forced-keep
study (layer 3) that the evidence does not yet justify. Floating the keep
count on the same values is not the next move.

### Queue
Oracle arm launched automatically at 00:39 (`rr_oracle_opp`); budget arm
follows. The opener arm took 45 min on four runners with the fast path
(the 2026-09-16 belief arm took 1 h 15 min).

## Update: 2026-09-18 - Oracle-type opponent model: +0.24 (null); opponent-model family closed at 2p

`artifacts/rr_oracle_opp` vs `rr_belief_opp`, 80 paired games at `9adb314`:
`potential_points` **78.41 → 78.65 (+0.24, p=0.83)**, win +0.025 (p=0.57);
by opponent +0.40 / +3.00 / −0.70 / −1.75. Null, as registered. Greedy,
belief and oracle opponent models now sit within ±0.3 of each other: the
acting player's plan at two players is robust to which family the imagined
opponent plays. Decision: `belief` stays (for cost), the greedy holdout
keeps watching, no profile-prior refit (the oracle already supplies what a
refit would learn), and the opponent-modelling question moves to 3–4
players. Nothing adopted or dropped, so no new holdout. Write-up in
`docs/experiments/search_opponent_model_test.md`. The arm took 48 min.
Budget arm (`rr_budget_5s`) launched by the queue at 01:27.

## Update: 2026-09-18 - 5 s decision budget: −2.0 (p=0.047) for −64% latency; the ladder paid for samples instead of depth

### Result (arm 5)
`artifacts/rr_budget_5s` vs `rr_belief_opp`, 80 paired games at `9adb314`,
four runners: `potential_points` **78.41 → 76.40 (−2.01, p=0.047)**, win
−0.037 (p=0.44). Mean decision 7,577 → 2,727 ms, per game 197 → 71 s:
**+0.41 points per second saved**, the best price on the ledger after the
free wins. p95 by round 4.7 / 4.9 / 5.1 / 5.4 s, max 12.9 s. The registered
band (−2 to 0) was hit at its edge; the success criterion (< 2 lost, p95 <
5 s every round) missed on both counts by a hair. Not the production
configuration yet.

### Diagnosis (2,080 budget reports)
56% of decisions cut. Where depth 3 was available, **depth 2 replaced it in
61%** of decisions while samples stayed at four in 75% — the ladder spent
the cap on K, which the ledger has never priced, instead of depth, which
it prices at −10.4 for two plies. 51 overruns above 5.5 s (worst 12.9 s)
came from 52–70-action roots: the level-cost prediction from the last two
levels' ratio misses big roots, and a level runs a whole sample once
started. Full write-up in `docs/architecture/decision_profiling.md`.

### Decision
No default change, no holdout (a production knob; when a budget ships,
the unbudgeted agent becomes the held-out side). Two follow-ups
registered below. The three arms of 2026-09-18 took 45–50 min each on four
runners; the fast path made a same-day arm cycle routine.

### Registered next arms
1. **Price K**: depth 3 with K=1 vs the K=4 baseline, 80 paired games.
   Prediction: −1 to −3 (the determinized-search test put K=4 at +2.4 over
   the true state, a different comparison). This is the number the budget
   ladder needs.
2. **Budget v2**: deepest level with one sample first, more samples with
   the time left, deadline check between root actions that abandons a
   level. Prediction at 5 s: ≥ −1 with p95 under the cap in every round →
   production configuration, holdout on the unbudgeted agent.

## Update: 2026-09-18 - K arm launched; ladder v2 built; beam pre-ranking built and registered

### In flight
- `artifacts/rr_k1`: depth 3 with K=1 vs the K=4 baseline (registered −1 to
  −3), four runners at `ad7526a`.
- `artifacts/rr_budget_v2`: 5 s budget on ladder v2, queued behind it at
  `f434b40` (registered ≥ −1 with p95 under the cap every round →
  production configuration, unbudgeted agent held out at 5%).

### Ladder v2
Depth before samples: one-ply, then one ply at a time on a single sample
(next level predicted from the measured ratio, or the root's candidate
count capped at 12 for the first deepening), abandoned at the deadline
between root actions, then the other samples at the deepest depth reached.
Two-game probe at 5 s: cap held to 5,003 ms; depth 3 kept in 29 of 36
eligible decisions (v1: 37%).

### Beam pre-ranking (registered)
`search_prerank`: `"none"` (historic), `"beam"` (a cheap immediate score —
printed points less egg cost +1 for a bird, eggs laid, demand-weighted
expected food, cards drawn — picks the beam at a beamed ply before anything
is expanded), `"beam_leaf"` (also evaluates only the
`search_leaf_candidates=6` cheapest-ranked leaves). Single-state probe,
K=1, three mid-game states: `beam` alone removes ~23% of leaf evaluations
and no measurable time (the middle ply is a fifth of the tree);
`beam_leaf` removes ~65% of leaf evaluations and **~60% of decision time**
(880/786/742 → 502/295/282 ms), agreeing with the full search on 9 of 15
archived decisions (`beam`: 11 of 15). Disagreement is not loss; the arm
decides. **Registered: `beam_leaf` vs `rr_belief_opp`, ≤ −0.5 acceptable
→ adopt with the `none` holdout; below −0.5 fall back to `beam` only if it
shows a latency gain in the arm's own profile, else drop both.** Queued
behind the budget v2 arm.

## Update: 2026-09-18 - K priced: K=1 costs 2.0 points for −80% latency; the v1 ladder was dominated

`artifacts/rr_k1` vs `rr_belief_opp` (80 paired games, `ad7526a`, clean):
depth 3 with K=1 **78.41 → 76.42 (−1.99, p=0.080)**, win −0.013; mean
decision 7,577 → 1,521 ms (×0.20), per game 197 → 40 s, **+0.33 points
per second saved**. Inside the registered band. Per doubling of time,
depth buys ≈ 1.7 points and samples ≈ 0.9, so ladder v2's depth-first
order is the right one; and the v1 ladder (−2.0 at ×0.36) was strictly
dominated by K=1 alone (−2.0 at ×0.20). K=4 stays the default; no switch
decided, no holdout. Knob table in `docs/architecture/decision_profiling.md`.
Budget v2 arm launched by the queue at 17:54; pre-ranking arm and the 3p
opponent-model study (belief / greedy / oracle, six lineups × 3 rotations
× 5 seeds = 90 games each, registered below) queued behind it.

### 3p opponent-model study (registered)
At two players three opponent models tie. At three, each search ply
carries two modelled opponent turns and the seat-order study found real
seat interaction, so the family the imagined opponents play could matter.
Design: `player_count=3`, roster `potential_points` + every pair of
{engine_builder, bonus_card_focus, net_value_response, greedy_immediate},
all three rotations, seeds 1–5, `control` openers; three roots
`artifacts/rr3p_opp/{belief,greedy,oracle}` paired game for game.
**Predictions: belief − greedy 0 to +2; oracle − belief 0 to +1; belief
cheaper than greedy by more than at 2p.** Below +1 for both, the
opponent-model question is closed at every player count the project runs.

## Update: 2026-09-18 - Ladder v2 at 5 s: −1.5 (n.s.) for −69% latency; cap binds, so make the decision cheaper first

`artifacts/rr_budget_v2` vs `rr_belief_opp` (80 paired, `f434b40`):
**−1.46 (p=0.12)**, win −0.037; mean decision 7,577 → 2,359 ms, p95 by
round 4.55 / 4.97 / 4.99 / 5.02 s, max 6.1 s, five overruns (v1: 51). Depth
3 kept in 54% of eligible decisions (v1: 37%), four samples in 79%; 45%
of decisions still cut because an unbudgeted decision under four-runner
load averages ~4.4 s with p95 near 12 s — the cap binds. Target (≥ −1,
p95 under cap) missed narrowly on both; −1.46 is not distinguishable from
−1 or from v1's −2.0 at n=80. Not production yet. Loss again concentrated
against `bonus_card_focus` (−4.2, p=0.03): the cut late plies are the ones
that see its bonus scoring. **Decision: keep ladder v2 as the ladder; the
production candidate is pre-ranking + ladder v2 at 5 s, registered ≥ −1
vs the unbudgeted baseline, to run once the pre-ranking arm (in flight)
has its own price.** Details in `docs/architecture/decision_profiling.md`.

## Update: 2026-09-18 - Beam pre-ranking: −0.7 (n.s.) for −58% latency; production candidate queued

`artifacts/rr_prerank` (`search_prerank="beam_leaf"`) vs `rr_belief_opp`
(80 paired, `5a3e7d5`): **−0.72 (p=0.55)**, win **+0.037**; mean decision
7,577 → 1,836 ms (×0.42 against the fast unbudgeted agent under the same
load); leaf evaluations 4,087 → 1,425 per decision. Registered ≤ −0.5: the
point estimate sits just outside a band the design cannot resolve, so by
the registration it is not the unbudgeted default and keeps a 5%
`beam_leaf` holdout. Its purpose is the budgeted agent: **production
candidate `beam_leaf` + ladder v2 at 5 s, registered ≥ −1 vs
`rr_belief_opp` with p95 under the cap in every round**, queued behind the
3p study (belief root launched 18:39). Also found: 220 of 2,080 decisions
had 40+-action roots (dry-feeder preference actions) averaging 4.9 s
(worst 65 s); the root is never pruned. A cheap-score root cut is the next
lever if the production arm's p95 is still over the cap.

## Update: 2026-09-18 - Game viewer: step through any archived game from one seat's point of view

`analysis/game_viewer.py <game_dir> [--pov player_2] [--interactive]
[--turns a-b] [--all-actions] [--all-private] [--out game.md]` replays a
game from its events (real states) and prints each decision: board with
live scores, the POV seat's hand and bonus card, tray, feeder, goals, the
legal actions, the ranking the agent chose from, the evaluator breakdown,
belief and budget state, the choice and its effect (including the RNG
draws). Purpose: let Alex find strategies the agent misses by eye and turn
them into registered arms (`docs/experiments/game_viewer.md`).

To make the "why" honest, `agent_decision_summary` now records
`search_ranking` — the search's own root values, the basis of the choice —
alongside the one-ply `top_alternatives`, which can disagree with the
choice (in the doc's example the evaluator preferred playing a bird and the
search drew two cards). Games archived before 2026-09-18 show the
evaluator ranking with that caveat.

Also this session: `analysis/launch_arm.py` (standard arm launcher with
queueing), `analysis/compact_artifacts.py` (8.5 GB recovered, 14 → 6.6 GB;
snapshots are read by nothing), a format-only commit over 27 drifted
files, and the workbook-path test made environment-independent — the suite
has no standing failures.

## Update: 2026-09-18 - Three players: the greedy opponent model beats belief by 2.1 (p=0.07); question open, priced

`artifacts/rr3p_opp/{belief,greedy,oracle}`, 90 paired 3p games each at
`5a3e7d5`: **greedy − belief +2.12 (p=0.073)**, win +0.067; **oracle −
belief +1.36 (p=0.18)**. The registered sign for belief − greedy (0 to +2)
was wrong: at three players the within-family proxy's error (it ignores
power activations) compounds over two modelled opponent turns per ply and
costs about two points; perfect type knowledge recovers about 1.4 of it.
The champion at 3p: 74.2 points, win 0.76 (seat 3 the hardest: 72.5 /
0.67). Cost: greedy 15.6 s a decision vs belief 8.8 s — +0.31 points per
second, the same rate as the fourth determinization sample. Decision:
`belief` stays the default (the cost case is stronger at 3p), greedy
holdout keeps watching; **registered next: `belief_apply`, family from the
posterior, pick within it by applying — +1 to +2 over belief at 3p for
+20–40% time, and no loss at 2p.** Write-up in
`docs/experiments/search_opponent_model_test.md`. The 3p study took 4 h 52
min for 270 games on six runners. Production arm launched by the queue at
23:31.

## Update: 2026-09-19 - Production configuration adopted: pre-ranking + ladder v2 at 5 s, −0.6 (n.s.), 1.1 s a decision

`artifacts/rr_prod_5s` vs `rr_belief_opp` (80 paired, `f89045c`):
`potential_points` **78.41 → 77.83 (−0.59, p=0.63), win 0.875 → 0.919**;
mean decision **7,577 → 1,105 ms**, p95 by round 1.3 / 3.1 / 3.8 / 4.2 s,
max 5,021 ms, 4% of decisions cut, depth 3 kept in 97% of eligible
decisions, four samples in 98%. Registered target (≥ −1, p95 under the cap
every round) met with room. **Adopted as the production configuration**
(`PRODUCTION_SEARCH_OVERRIDES = {max_decision_time_ms: 5000,
search_prerank: "beam_leaf"}`). Not the research baseline: a wall-clock
budget makes decisions depend on machine load and breaks the
cross-process determinism paired arms need (ADR 0004); research arms stay
unbudgeted, the production config gets its own 80-game check whenever the
search changes, and on deployment the unbudgeted agent is the 5% held-out
side. The price list closes: the search is +10.4 over one-ply and, in
production form, costs 1.1 s a decision instead of 9.4. Case study and
ledger updated. In flight: `rr3p_belief_apply` then `rr_belief_apply`.

## Update: 2026-09-19 - belief_apply: null at both player counts, and 84% of games identical — the family prediction is the gap

`rr3p_belief_apply` vs `rr3p_opp/belief`: **−0.48 (p=0.21)**, 76 of 90
games identical; 2p: −0.61 (p=0.26), 63 of 80 identical. Registered +1 to
+2 failed in the informative way: applying inside the predicted family
almost never changes the pick, so greedy's +2.1 at 3p comes from *which
family* the search assumes, not how it plays it. The belief model's
response likelihoods (hand-set, never fitted to the roster) are the weak
part. Not adopted; no holdout (see registry). **Registered next: refit
`P(family | profile, candidate values)` to the archive (~6,000 opponent
decisions), score by log loss vs the current priors, one 3p arm;
prediction +1 to +2 over belief at no extra cost.** Worktrees removed.

## Update: 2026-09-19 - Response-likelihood refit: gate failed; greedy's edge is responsiveness, not prediction

### What changed
Built `analysis/fit_response_model.py`: replays every archived game at the
current rules (17 roots, 1,680 games), records the public candidate values
and chosen family at each of 53,603 distinct opponent decisions, fits
`P(family | kind, values)` per roster kind by maximum likelihood, and
scores it the way the search uses it (sequential predict-then-observe,
uniform prior, leave-one-seed-out over 70 whole games). The belief model
gained `ProfileResponseModel.family_value_weight`, `load_profile_models`,
three roster-kind profiles, and a `search_belief_profiles` switch
(`hand_set` | `fitted`) on the agent and search config, recorded in
manifests and decision telemetry. `configs/belief/fitted_response_models.json`
holds the fit with its cross-validation.

### Result
Held-out log loss 1.194 (hand-set) → 1.183 (fitted); top-1 family 0.39 →
0.41; worse on `engine_builder`; knowing the true kind from turn one scores
*worse* (1.244) than inferring it. **Gate failed; the 3p arm was not run.**
The benchmark explains why the arm would have been null anyway: on the
same 6,760 real decisions the greedy opponent model matches the three
archetypes' families 35–47% of the time, the belief model 36–54%; greedy's
57% overall is its perfect prediction of `greedy_immediate`, and its +2.1
at 3p is not concentrated in lineups with that agent. So neither family
accuracy (this refit) nor the within-family pick (`belief_apply`) is the
mechanism. What differs is on branch states: greedy answers the
searcher's imagined move with a competent family; the belief model's
temperature-2 priors answer every branch the same way.

### Decision
`belief` stays the default with `hand_set` profiles; nothing adopted, no
holdout. **Registered: `search_opponent_model="competent"`** — argmax of
the public candidate values on the branch, no posterior, proxy pick —
prediction +1 to +2 over `belief` at 3p, 0 to +1 at 2p, cost ≈ `belief`.
Also registered today: the self-play / human-trace programme
(`docs/experiments/self_play_opponent_plan.md`, arms A1–A4, studies H1–H3).

### Follow-up tasks
- [ ] Build `CompetentSearchOpponentModel` (≈40 lines in `search_opponent.py`), one-game probe, launch the 3p arm then the 2p check.
- [ ] Self-play build: per-seat search config, `arm_contrast --study-position`, deterministic mirror probe; launch A1.
- [ ] `docs/experiments/strategy_findings.md` from the ledger (dominance, archetype signatures, seat, card value, category profile of the champion).

## Update: 2026-09-20 - Competent model, self-play and human-trace builds; four arms queued

### What changed
- `CompetentSearchOpponentModel` (`search_opponent_model="competent"`):
  the family with the highest public candidate value on the branch, no
  posterior, proxy pick inside. Probe: replay-valid, 2.9 s a decision
  against belief's 4.2 s under the same load.
- Self-play: `potential_points_search_by_position` on the batch flow and
  round robin (lineup position → config, recorded per game and per
  batch), pure mirror rosters allowed, `arm_contrast --agent kind@N`,
  `launch_arm --mirror [--study-search]`. Two processes replay a mirror
  game with identical action sequences (seed 11, both rotations).
- Human traces: the board renderer moved to `wingspan_ai.state.render`
  (shared by the viewer and `HumanCliAgent`, which now shows the full
  board, own hand and bonus card each turn); `human_cli` is a batch-flow
  agent kind; `flows/human_vs_agent.py` archives a human game against the
  production agent from either seat and prints the viewer command.
- `docs/experiments/strategy_findings.md`: the game questions answered
  from the ledger, one table per question with design and status, and the
  four things the archive cannot yet say (strong-vs-strong dominance, card
  and goal balance at ten seeds, human play, expansions). New descriptive
  finding: the champion's action mix is round-shaped (draws 26% → 14%,
  eggs 25% → 38% from round 1 to 4) while every archetype's is flat — the
  round-horizon result in behavioural form.

### In flight
Launched 2026-09-19 23:38, killed by a machine reboot at ~23:47 (partials
deleted), relaunched 2026-09-20 00:2x at `519cffb`: `rr3p_competent` (six
runners) → `rr_competent` → `mirror_2p` (seeds 1–40, four runners) →
`mirror_3p` (seeds 1–30, six runners), chained by `queue.sh`. About 12 h.
The queue is not reboot-safe.

### Follow-up tasks
- [ ] Read the four arms; ledger rows; decide `competent`; record A1.
- [ ] Launch A2 (opponent model in the mirror) paired against A1.
- [ ] Ten human games (Alex), then H1–H3.

## Update: 2026-09-20 - Competent model null at both counts; A1 mirror baseline read; A2 launched

### Results
- `rr3p_competent` vs `rr3p_opp/belief`: **+0.13 (p=0.91)**; `rr_competent`
  vs `rr_belief_opp`: **−0.72 (p=0.48)**. Registered +1 to +2 / 0 to +1
  failed. The apparent 30–40% latency saving is machine load (identical
  node counts, every node's ms/call lower); the model's own cost is 1%.
  Not adopted; no holdout. Pooled greedy holdout (51 games): belief +1.5
  (p=0.29). The roster opponent-model programme is closed
  (`search_opponent_model_test.md`).
- A1 `mirror_2p` (80) / `mirror_3p` (90): mean **75.3** / **78.3** (vs 78.4 /
  74.2 against the roster). Seat 1 **+5.1, win 0.575** at 2p (p=0.051 with
  rotations collapsed to 40 seeds — identical configs make the two
  rotations the same game in 28 of 40 seeds); 3p seat wins 0.40 / 0.37 /
  0.23. Winners separate on goals and eggs (15.8 / 14.0 vs 12.0 / 11.4).
  Predictions: score level missed high (70–74 → 75.3), seat-1 win hit.
  30 of 80 mirror games carry a holdout somewhere (five fields × two
  positions).

### Decision
`belief` stays the default. The opponent question moves to self-play:
**A2 launched** — `mirror_2p_greedy` (position 1 on `greedy`, paired vs
`mirror_2p`) then `mirror_3p_greedy` (vs `mirror_3p`), registered 2p +1 to
+3, 3p +2 to +4.

### Follow-up tasks
- [ ] Read A2; pool A1+A2 seat effect; ledger rows.
- [ ] A3 denial term in the mirror.
- [ ] Retire holdouts as they pass 100 games (mirror arms double the deviation rate).
