# COMPANY_CONTEXT.md

_Last updated: 2026-05-03_

## Purpose

This document is the source of truth for the public, research, and portfolio context around the Wingspan AI project.

The filename is retained for compatibility with AI coding tools, but this is not a company brief. This project is separate from Savepoint Analytics. Use this file when asking AI tools for help with:
- Project positioning.
- Research case-study framing.
- Portfolio copy.
- README and documentation tone.
- Public explanation of the technical work.
- Strategic decisions about what to build next.
- Reusable board-game NPC AI templates.
- Experiment narratives and findings.

## Executive snapshot

**Project:** Wingspan AI  
**Owner:** Alex Oswald  
**Project category:** applied ML research case study and reusable simulation/AI framework  
**Primary domain:** board-game AI, video game NPC AI, game theory, sequential decision-making, and game economy optimization  
**Primary example game:** Wingspan  
**Core promise:** build a simulation and analytics environment for testing how different AI methods play a complex, stochastic, partially observable, economy-constrained board game, then generalize the approach for other board-game-like video game NPCs.

The project should demonstrate how to:
- Encode a complex board game as a rules-faithful simulator.
- Generate analyzable simulation telemetry.
- Compare multiple AI-player approaches under controlled conditions.
- Use Bayesian game theory and belief modelling to reason about hidden information and opponent type.
- Identify dominant, dominated, and situational strategies.
- Build reusable templates for similar strategy/economy games.
- Eventually determine how Bayesian game theory and belief modelling performs against human players, and other black blox model AI players 

## What this project is

Wingspan AI is a research engineering project focused on AI players for sequential gameplay.

It combines:
1. **Rules modelling**
   - Machine-readable game content.
   - Deterministic rules engine.
   - Legal action generation.
   - Seeded stochastic transitions.
   - Expansion-aware configuration.

2. **Simulation**
   - Repeatable games and tournaments.
   - Multiple player counts and rulesets.
   - Configurable agent rosters.
   - Full event traces for replay and analysis.

3. **AI-player development**
   - Scripted baseline bots.
   - Heuristic and expected-value agents.
   - Strategy archetypes.
   - Bayesian opponent models.
   - Search/rollout agents.
   - Reinforcement learning and imitation learning where useful.

4. **Analytics and research**
   - Simulation telemetry ingestion.
   - Win-rate, score, action, and strategy analysis.
   - Card, bonus-card, and round-goal value analysis.
   - Synergy analysis.
   - Dominant and dominated strategy classification.
   - Case-study-ready findings.

5. **Reusable template development**
   - Separate board-game framework concepts from Wingspan-specific content.
   - Design abstractions that can be reconfigured for other games with resource economies, card/deck uncertainty, player boards, end-game scoring, and opponent interaction.

## What this project is not

This project is not:
- The Savepoint Analytics platform.
- A commercial Wingspan clone.
- A production game client.
- A generic reinforcement-learning sandbox with no domain structure.
- A project where black-box model performance is enough without strategic interpretation.

Public or commercial use of Wingspan-related assets, rules, names, card data, or derived materials should be reviewed carefully before release. Treat current materials as research inputs for a private technical case study unless Alex decides otherwise.

## Intended audience

### Primary audience

Alex, as the project owner and research lead.

### Secondary audiences

Potential future readers may include:
- Game studios evaluating Alex's ML and analytics capability.
- Technical collaborators.
- Hiring or consulting prospects.
- Data science and game AI practitioners.
- Board-game strategy and game economy audiences.

The project should therefore be written and structured so a technical reader can see both:
- The engineering discipline behind the simulator and experiments.
- The strategic/game-theory insight produced by the analysis.

## Case-study positioning

### Recommended positioning statement

Wingspan AI is an applied ML research case study that uses a complex board game to explore how AI players can reason under uncertainty, optimize constrained economies, model opponent strategy, and discover situationally dominant play patterns.

### Short version

An ML research lab for board-game NPC strategy, using Wingspan as the first testbed.

### Technical version

Wingspan AI combines a Python rules engine, simulation telemetry, FastAPI/PostgreSQL analytics ingestion, Prefect orchestration, MLflow experiment tracking, and Python/R analysis to evaluate scripted, heuristic, Bayesian, search-based, and learning-based AI players.

### Strategic version

The project studies how to win a sequential economic game when the best action depends on starting state, hidden information, opponent type, ruleset, stochastic draws, and long-term scoring tradeoffs.

## Core differentiation

The project should differentiate on:

1. **Strategic interpretability**
   - The goal is not only "which agent wins" but why it wins.
   - Strategy analysis should explain resource tradeoffs, card synergies, timing windows, and opponent-dependent choices.

2. **Bayesian and game-theoretic framing**
   - Hidden information and opponent uncertainty are first-class design concerns.
   - Agents should eventually maintain beliefs about opponent type, likely goals, hidden points, and end-game scoring potential.

3. **Simulation telemetry**
   - Every game should produce analyzable events.
   - The analytics layer should make it possible to inspect action choice, score evolution, strategy commitments, and model errors.

4. **Reusable board-game AI template**
   - Wingspan-specific rules should be separated from concepts like state, actions, observations, rewards, policies, beliefs, and scoring.
   - The architecture should be able to support other board games with constrained economies and sequential optimization.

5. **Practical engineering**
   - The project should be runnable, testable, and reproducible.
   - Experiments should be tracked and comparable.

## Research questions

Important research questions include:
- What is the minimum simulator fidelity needed before AI results become meaningful?
- Which baseline heuristics perform best against beginner, intermediate, and specialized opponents?
- Can Bayesian opponent modelling improve decisions under hidden scoring and strategy uncertainty?
- Can agents classify opponent strategy type early enough to exploit it?
- Which cards, bonus cards, and round goals have high expected value only in specific contexts?
- Which strategies are robust across openings, rulesets, and opponents?
- Which strategies are powerful but fragile?
- Which actions look locally efficient but reduce end-game win probability?
- How does expansion content change strategic balance?
- Which algorithm families provide the best interpretability-to-performance tradeoff?

## Default technical assumptions

The default implementation direction is:
- Python-first simulator and ML code.
- Pydantic models for structured game content and event contracts.
- FastAPI analytics ingestion service.
- PostgreSQL for event logs and experiment analysis tables.
- Prefect for batch simulation, tournaments, and training workflows.
- MLflow for experiment tracking and model/version comparison.
- R and Python for exploratory analysis and reporting.
- pytest for rules and simulation regression coverage.
- Seeded randomness everywhere simulation results need reproducibility.

## Case-study success criteria

A strong version of this project should be able to show:
- A game can be simulated from setup through final scoring.
- Agents can play legal games without manual intervention.
- Simulation batches can be orchestrated and reproduced.
- Events can be logged and queried.
- Multiple agent types can be compared.
- Strategy archetypes can be detected or labelled.
- At least one Bayesian/belief-based agent can update assumptions about opponents or hidden score potential.
- Analysis can identify specific strategic patterns, not just aggregate win rates.
- The framework has clear extension points for another board game.

## Communication style

When writing public-facing or case-study material:
- Lead with the research problem and why it matters for game AI.
- Use Wingspan as the concrete testbed.
- Explain technical choices briefly and credibly.
- Emphasize constrained optimization, hidden information, strategy discovery, and reusable NPC AI templates.
- Avoid overstating results before experiments exist.
- Avoid implying endorsement, affiliation, or commercial rights related to Wingspan or its publisher.

## Current stage

The project is moving from foundation-building into rule-fidelity and smoke-experiment validation.

Current assets:
- `README.md` with objectives, roadmap, next steps, and resources.
- `data/raw/wingspan-card-list.xlsx` with card, bonus-card, and round-goal information.
- Rulebook PDFs in `rulebook_pdfs/`.
- A seeded simulator with scaled core actions, baseline agents, telemetry events, tournaments, artifact writing, and workbook-backed smoke batches.

Near-term goal:
1. Continue tightening base-game fidelity around high-volume powers, scoring, and choice policies.
2. Use smoke batches to catch simulator regressions before interpreting strategy results.
3. Expand event/replay detail so game traces can explain why an agent chose an action.
4. Compare baseline and heuristic agents only when the relevant mechanics are implemented or explicitly filtered.
5. Convert validated findings into reusable architecture and case-study material.

## Things to avoid repeating

The following points are established unless Alex changes direction:
- This is separate from Savepoint Analytics.
- The project should be useful as a research case study.
- The first concrete testbed is Wingspan.
- Reusability for other board games matters.
- FastAPI, PostgreSQL, Prefect, MLflow, Python, and R are the preferred stack.
- Advanced ML should come after a validated simulator and baseline agents.
- Strategic explanation matters as much as model performance.

## How to update this file

Update this file when:
- The project positioning changes.
- The intended public case-study angle changes.
- Core audience or use case changes.
- The relationship to Savepoint changes.
- A major research direction is accepted or rejected.

Put implementation history, decisions, and task status in `PROJECT_CONTEXT.md`.
