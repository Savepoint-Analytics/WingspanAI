# PROJECT_CONTEXT.md

_Last updated: 2026-05-03_

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

The project is in rule-fidelity and smoke-experiment validation.

Current focus:
1. Tighten the base-game economy loop so simulations are strategically credible.
2. Expand high-volume bird power handling, bonus-card scoring, and competitive round-goal scoring.
3. Keep legal actions concrete enough for habitat scaling, optional conversions, rerolls, and agent choice policies.
4. Preserve deterministic seeded runs, replayable telemetry, and hidden-information boundaries.
5. Use smoke batches to catch regressions before interpreting tournament results.
6. Prepare the analysis layer for baseline and heuristic comparisons once rule coverage is sufficient.

## Current assets

Project root currently includes:
- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `COMPANY_CONTEXT.md`
- `PROJECT_CONTEXT.md`
- `data/raw/wingspan-card-list.xlsx`
- `rulebook_pdfs/WS_Core_Rulebook.pdf`
- `rulebook_pdfs/WS_European_Rulebook.pdf`
- `rulebook_pdfs/WS_Oceania_Rulebook.pdf`
- `rulebook_pdfs/WS_Asia_Rulebook_r9.pdf`
- `rulebook_pdfs/WS_AE_AutoRulebook_r5.pdf`

The project is a git repository in this directory.

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

These tasks are scoped to be founder-manageable and reusable.

| Priority | Task | Success criteria |
|---|---|---|
| 1 | Define project package structure. | A proposed folder tree exists for `src/`, `data/`, `docs/`, `notebooks/`, `analysis/`, `tests/`, and `flows/`. |
| 1 | Create machine-readable game content schema. | Pydantic models exist for bird cards, bonus cards, round goals, food, habitats, powers, and ruleset metadata. |
| 1 | Validate `data/raw/wingspan-card-list.xlsx` fields. | A data audit documents available columns, missing fields, normalization needs, and expansion coverage. |
| 1 | Build base content loader. | The spreadsheet can be loaded into typed objects with validation errors reported clearly. |
| 1 | Define base-game state model. | Full game state, player state, public state, private state, decks, tray, birdfeeder, and round state are represented. |
| 1 | Draft rules-engine design doc. | Setup, legal actions, state transitions, scoring, powers, and randomness boundaries are documented. |
| 1 | Implement random legal agent. | Agent can select from generated legal actions with seeded randomness. |
| 1 | Add first rules tests. | Tests cover setup, playing a bird, gaining food, laying eggs, drawing cards, round transition, and final score skeleton. |
| 2 | Define simulation event schema. | Core events and required fields are documented in `docs/events/`. |
| 2 | Draft FastAPI ingestion service. | A local endpoint accepts simulation events and validates payloads. |
| 2 | Create PostgreSQL event table design. | Tables for runs, games, events, agents, and outcomes are documented or migrated. |
| 2 | Add single-game runner. | A full random-vs-random game can run and emit event logs. |
| 2 | Add Prefect simulation flow. | A batch of seeded games can be scheduled and summarized. |
| 2 | Add MLflow tracking skeleton. | Agent config, ruleset, seeds, metrics, and artifacts are logged for a simulation batch. |
| 2 | Implement greedy baseline. | Greedy agent beats random over a documented evaluation run. |
| 2 | Create R/Python analysis notebook. | First simulation logs can be summarized by score distribution, action frequency, and game length. |
| 3 | Implement strategy archetype bots. | At least three archetypes produce distinct telemetry signatures. |
| 3 | Add tournament runner. | Agents can be evaluated in repeated matches with fixed rulesets and seeds. |
| 3 | Draft Bayesian belief model plan. | Hidden score, opponent type, and next-action belief variables are defined. |
| 3 | Build first Monte Carlo rollout agent. | Agent estimates action value through sampled continuations under a compute budget. |
| 3 | Draft case-study outline. | A document explains problem, architecture, methods, early results, and next research questions. |

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
- Should Bayesian modelling start with opponent type, hidden score, card draw probabilities, or end-game score distributions? Answer: it should start with with what presumably more important and stronger in terms of signal strength and propensity to which it will impact the final outcome.  
- What observation encoding should be standard for learning agents?
- What reward shaping avoids teaching agents misleading short-term behavior?
- What compute budget should a move-level agent be allowed?

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

Recommended docs to add:
- `docs/architecture/simulator_architecture.md`
- `docs/architecture/reusable_board_game_ai_template.md`
- `docs/rules/base_game_scope.md`
- `docs/rules/expansion_configuration.md`
- `docs/events/simulation_event_taxonomy.md`
- `docs/agents/baseline_agents.md`
- `docs/agents/bayesian_agent_design.md`
- `docs/experiments/experiment_tracking.md`
- `docs/experiments/first_tournament_plan.md`
- `docs/decisions/0001-separate-wingspan-ai-from-savepoint.md`

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

## Things to avoid repeating

The following points are already established unless changed:
- This is a Wingspan AI research project, not Savepoint Analytics.
- The project should be case-study-ready.
- Wingspan is the first testbed, but reusability for similar games matters.
- Baselines and rules tests come before advanced ML.
- Bayesian game theory is a major research direction, especially for partial information and opponent modelling.
- Simulation telemetry is central, not an afterthought.
- Use small tasks with clear success criteria.

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
