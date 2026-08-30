# Wingspan AI

Wingspan AI is an applied ML research project for studying AI players in sequential, stochastic, partially observable, economy-constrained board games.

The first testbed is **Wingspan**. The broader goal is to build a reusable simulation, telemetry, and experiment framework that can later be adapted to video game NPC AI for board-game-like strategy systems.

This project is separate from Savepoint Analytics, but it may become a research case study that showcases applied ML, game analytics, Bayesian game theory, simulation orchestration, and strategic economic thinking.

## Research Goal

The project aims to understand how to win Wingspan under different starting states, opponent types, player counts, rulesets, expansions, stochastic draws, and hidden-information conditions.

The main research direction is to test multiple AI methods, with special interest in an AI player that incorporates Bayesian game theory:
- Maintain beliefs about opponent strategy type, hidden score potential, and likely next actions.
- Evaluate moves as constrained optimization decisions with expected benefits, costs, risks, and opportunity costs.
- Classify dominant, dominated, situational, and opponent-dependent strategies.
- Use simulation results to document when specific cards, engines, bonus cards, and round-goal choices are strategically valuable.

## Objectives

- **Digitize game content:** define structured data and class objects for birds, bonus cards, resources, dice, round objectives, habitats, powers, scoring rules, and expansion metadata.
- **Encode the rules:** implement game state, legal actions, deterministic state transitions, seeded randomness, and scoring so simulated games reproduce physical play closely enough for research.
- **Create a reusable environment API:** expose reset, step, observation, reward, done, and info-style interfaces for heuristic agents, search, RL, and analysis.
- **Instrument simulation telemetry:** log simulation and decision events through FastAPI into a database so games can be replayed, analyzed, and compared.
- **Develop baseline opponents:** implement random, beginner, intermediate, and scripted strategy agents as sparring partners and data sources.
- **Test ML and game-theory methods:** compare heuristic, Bayesian, search, reinforcement learning, imitation learning, and hybrid approaches.
- **Evaluate and iterate:** run tournaments, track experiments with MLflow, orchestrate batches with Prefect, and analyze results with Python, SQL, and R.
- **Build a reusable template:** separate Wingspan-specific content from generic board-game AI concepts so similar projects can be reconfigured for other games.

## Target Tech Stack

- **Python 3.12+** for simulator, rules engine, agents, ML, event contracts, and orchestration tasks.
- **FastAPI** for simulation and analytics event ingestion.
- **PostgreSQL** for simulation event logs, run metadata, outcomes, and analysis-ready tables.
- **Prefect** for simulation batches, tournaments, model training, evaluation, and reporting workflows.
- **MLflow** for experiment tracking, model/agent versioning, artifacts, metrics, and comparison.
- **R** for exploratory analysis, statistical modelling, strategy analysis, and visualization where useful.
- **SQL** for reproducible analysis tables, event queries, and simulation summaries.
- **Pydantic** for typed game content, configuration, event schemas, and validation.
- **pytest** for rules-engine and simulator regression tests.

## AI Methods To Explore

Start with interpretable baselines, then layer complexity:

1. Random legal-action agent.
2. Greedy immediate-point agent.
3. Round-aware expected-value heuristic.
4. Strategy archetype agents, such as egg focus, engine builder, card draw/tuck, bonus-card focus, food acceleration, predator/cache, and round-goal chase.
5. Monte Carlo rollout agents.
6. Monte Carlo Tree Search with action masking.
7. Bayesian opponent modelling and belief updates.
8. Bayesian game-theory-driven action selection.
9. Contextual bandits for local action optimization.
10. Imitation learning from human or scripted traces if useful data exists.
11. Reinforcement learning such as PPO/A2C/DQN variants once the simulator and environment API are stable.
12. Hybrid agents that combine rules, search, belief models, and learned value functions.

## Reusable Board-Game AI Template

Wingspan-specific implementation should be separated from generic framework concepts:

- `game_config`
- `ruleset`
- `content_catalog`
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

This structure should make it easier to adapt the approach to other board games with resource economies, card/deck uncertainty, player boards, hidden information, turn sequencing, and end-game scoring.

## Roadmap

### 1. Game Content and Data Models

- Define `BirdCard` with food costs, habitats, powers, power color, nest type, wingspan, points, egg capacity, expansion, and scoring relevance.
- Define bonus cards.
- Define food/resource types.
- Define dice and birdfeeder state.
- Define round objectives.
- Define habitats and player board slots.
- Define scoring categories.
- Define expansion modules and ruleset configuration.
- Load and validate `data/raw/wingspan-card-list.xlsx`.

### 2. Rules Engine

- Represent player mats, birds, resources, bonus cards, round goals, hands, decks, tray, birdfeeder, and turn structure.
- Define legal actions including playing birds, gaining food, laying eggs, drawing cards, resolving bird powers, and end-of-round scoring.
- Implement deterministic transitions for habitat activations, predator hunts, caching, tucking, bonus-card effects, and round-end scoring.
- Use seeded randomness for reproducibility.
- Add unit tests for every important rule interaction before relying on simulation output.

### 3. State, Observation, and Hidden Information

- Define full game state.
- Define what each player can know about themselves.
- Define what each player can observe about opponents.
- Separate public observations from private training/debug state.
- Track known, inferred, and hidden information.
- Estimate current guaranteed points and potential future points.
- Model hidden opponent score, likely goals, and strategy type as beliefs.

### 4. Environment API

- Wrap the simulator in an environment with reset, step, observation, reward, done, and info methods.
- Design action masks for legal actions.
- Design observation encodings for visible state and partial information.
- Define reward schemes for win probability, final score, intermediate shaping, and strategy-specific diagnostics.

### 5. Analytics Events and Data Store

- Define simulation event contracts.
- Emit events for setup, turns, legal actions, selected actions, resolved actions, state changes, scoring, and model decisions.
- Send events through FastAPI.
- Store runs, games, agents, event logs, outcomes, and summaries in PostgreSQL.
- Make simulation games replayable and inspectable from logged data.

### 6. Baseline Bots and Heuristics

- Implement random legal play.
- Implement greedy point maximization.
- Implement expected-value turn selection.
- Implement scripted beginner and intermediate strategies.
- Implement strategy archetype bots for common play styles.
- Use these agents as benchmarks, data generators, and regression tests.

### 7. Bayesian and Game-Theory Agents

- Define opponent type priors.
- Update beliefs from observed actions, resource choices, played birds, card draw behaviour, and round-goal commitments.
- Estimate hidden score and future scoring potential.
- Evaluate actions by expected end-game win probability rather than only immediate points.
- Explore Bayesian Nash-style framing where strategy choices depend on beliefs about opponent strategy types.

### 8. Search, Learning, and Self-Play

- Add Monte Carlo rollouts.
- Explore MCTS with action masking.
- Test contextual bandits for local action decisions.
- Add imitation learning if useful traces exist.
- Explore RL only after the environment is stable.
- Use curriculum strategies to scale from simplified rules to full game complexity.

### 9. Evaluation and Tooling

- Track win rates, final score distributions, score category mix, action diversity, game length, strategy signatures, belief calibration, and compute time.
- Run tournaments between agent versions.
- Perform ablation studies on features, rewards, and belief components.
- Use MLflow for experiment comparison.
- Use Prefect for batch simulations and model workflows.
- Use Python/R analysis to turn simulation logs into strategic findings.

### 10. Sabermetric Card and Strategy Analysis

- Identify which cards are valuable in specific game contexts.
- Analyze bird-card synergy with bonus cards, round goals, habitats, and available resources.
- Estimate when cards are worth collecting, playing, holding, or ignoring.
- Identify play styles that are optimal against other play styles.
- Document dominant, dominated, and situational strategies.

## Near-Term Next Steps

1. Define the initial folder/package structure for source code, data, docs, tests, flows, notebooks, and analysis.
2. Audit `data/raw/wingspan-card-list.xlsx` for usable fields, missing fields, expansion coverage, and fields that need normalization.
3. Create Pydantic schemas for bird cards, bonus cards, round goals, food, powers, rulesets, and simulation configuration.
4. Draft the simulator architecture doc, including state, actions, transitions, scoring, observations, and randomness.
5. Implement base content loading and validation.
6. Implement base-game setup and state model.
7. Implement legal-action generation for the first core actions: play bird, gain food, lay eggs, draw cards.
8. Add first unit tests for setup, legal actions, state transitions, and scoring skeleton.
9. Define the simulation event taxonomy.
10. Draft a FastAPI ingestion endpoint and PostgreSQL table design for simulation events.
11. Implement random legal agent and single-game runner.
12. Add Prefect flow for running a batch of seeded games.
13. Add MLflow tracking for run config, agent config, ruleset, seeds, outcomes, and artifacts.
14. Implement greedy and round-aware baseline agents.
15. Create the first R/Python analysis notebook for score distributions, action frequencies, and strategy signatures.

## Current Foundation Artifacts

- `src/wingspan_ai/content/loader.py`: base workbook loader for typed core-game content.
- `src/wingspan_ai/content/sample_catalog.py`: synthetic catalog for tests and smoke runs when the workbook is absent.
- `src/wingspan_ai/content/schemas.py`: initial Pydantic schemas for game content, powers, food costs, rulesets, and content catalogs.
- `src/wingspan_ai/content/workbook_audit.py`: reproducible audit utility for `data/raw/wingspan-card-list.xlsx`.
- `src/wingspan_ai/state/models.py`: base-game state, public state, private state, decks, tray, birdfeeder, and player board models.
- `src/wingspan_ai/rules/actions.py`: concrete legal action model, including scaled habitat choices, rerolls, and conversion options.
- `src/wingspan_ai/rules/base_game.py`: setup, legal action generation, state transitions, habitat activation, power scaffolding, round advancement, and scoring.
- `src/wingspan_ai/simulation/artifacts.py`: writes outcome, event, and public-state snapshot artifacts.
- `src/wingspan_ai/agents/random_legal.py`: seeded random legal-action baseline agent.
- `src/wingspan_ai/agents/greedy.py`: immediate-score greedy baseline agent with food-choice tiebreaks based on hand needs.
- `src/wingspan_ai/agents/potential_points.py`: expected-value greedy variant that estimates final-score potential from resources, playable birds, powers, bonus-card progress, round-goal pressure, and endgame conversion.
- `src/wingspan_ai/agents/net_value.py`: score-margin agent scaffold that estimates next opponent response and shared-resource denial value from public observations plus a first belief heuristic.
- `src/wingspan_ai/agents/guardrails.py`: YAML-configured policy guardrails that filter or rescore legal actions before agent selection.
- `src/wingspan_ai/agents/human_cli.py`: terminal-backed human player policy for local human-vs-agent smoke games.
- `src/wingspan_ai/agents/archetypes.py`: scripted strategy archetype bots for behavioural signatures.
- `src/wingspan_ai/agents/monte_carlo.py`: Monte Carlo rollout agent with candidate, rollout-depth, rollout-count, and decision-time budget controls.
- `src/wingspan_ai/simulation/tournament.py`: seeded tournament runner and matchup summaries.
- `src/wingspan_ai/telemetry/events.py`: versioned simulation event schema and in-memory event sink.
- `src/wingspan_ai/telemetry/api.py`: draft FastAPI event ingestion service.
- `src/wingspan_ai/telemetry/postgres.py`: PostgreSQL repository for simulation runs, games, agents, events, and final scores.
- `src/wingspan_ai/storage/object_storage.py`: S3-compatible MinIO artifact upload helper.
- `src/wingspan_ai/config.py`: local `.env` loader and connection config helpers.
- `src/wingspan_ai/simulation/runner.py`: single-game runner with event emission and outcomes.
- `analysis/net_value_calibration.py`: compares net-value public-belief response predictions against observed next opponent actions from batch artifacts.
- `src/wingspan_ai/simulation/replay.py`: deterministic state hashing helpers for replay/debug audits.
- `src/wingspan_ai/rules/scoring_audit.py`: bonus-card and round-goal scoring coverage audit helper.
- `src/wingspan_ai/rules/audit.py`: combined scoring and power coverage summary for batches and tournaments.
- `src/wingspan_ai/experiments/mlflow_tracking.py`: MLflow logging skeleton for simulation results.
- `flows/simulation_batch.py`: Prefect-compatible seeded batch flow with replay validation, rule-fidelity audits, workload namespaces, batch-scoped game IDs, PostgreSQL/MinIO persistence, and a batch manifest.
- `analysis/simulation_summary.py`: first reusable analysis helpers for outcomes and action frequency.
- `analysis/simulation_batch_comparison.py`: compares batch manifests, action mixes, score margins, and potential/guardrail decision telemetry.
- `analysis/apply_action_profile.py`: profiles legal action generation, deep-copy cost, and full transition cost for lookahead-heavy agents.
- `notebooks/first_simulation_analysis.ipynb`: first Python notebook for tiny simulation-batch review.
- `docs/architecture/project_package_structure.md`: recommended package and project folder structure.
- `docs/architecture/simulator_architecture.md`: initial rules-engine and simulator architecture draft.
- `docs/agents/baseline_agents.md`: current baseline and strategy archetype definitions.
- `docs/agents/net_value_opponent_response_agent.md`: score-margin and opponent-response agent template.
- `docs/agents/guardrail_policies.md`: YAML guardrail policy schema, telemetry, and usage notes.
- `docs/agents/bayesian_belief_model_plan.md`: first Bayesian belief model plan.
- `docs/events/simulation_event_taxonomy.md`: event envelope, current event names, and replay direction.
- `docs/events/postgresql_event_table_design.md`: draft PostgreSQL tables and indexes for events/outcomes.
- `docs/experiments/case_study_outline.md`: first case-study outline.
- `docs/rules/game_content_schema.md`: summary of the machine-readable content schema.
- `docs/rules/power_handler_registry.md`: power-handler registry metadata plan.
- `docs/rules/wingspan_card_list_audit.md`: current workbook field audit and normalization needs.

## Project Context Files

- `AGENTS.md` contains standing instructions for AI coding agents.
- `CLAUDE.md` contains equivalent Claude-oriented project instructions.
- `COMPANY_CONTEXT.md` contains research and case-study positioning context. The filename is retained for tool compatibility.
- `PROJECT_CONTEXT.md` contains current decisions, working memory, open questions, and next tasks.

Read these files before making major architectural or documentation changes.

## Current Resources

- `data/raw/wingspan-card-list.xlsx`: information about birds, bonus cards, and end-of-round goals.
- `rulebook_pdfs/`: local rulebook PDFs for core Wingspan and expansions.
- Tabletop Simulator Wingspan scripting reference: https://github.com/nmombo/Wingspan
- Wingspan data reference: https://github.com/coolbutuseless/wingspan

## Notes

This project should be treated as a private research and engineering workspace unless Alex explicitly decides what to publish. Avoid implying endorsement, affiliation, or commercial rights related to Wingspan or its publisher.
