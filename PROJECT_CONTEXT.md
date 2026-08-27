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

