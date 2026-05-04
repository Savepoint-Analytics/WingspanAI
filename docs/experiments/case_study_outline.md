# Wingspan AI Case Study Outline

Status: initial outline, 2026-05-04

## Working Title

Wingspan AI: Simulation-Driven Strategy Discovery for Sequential Board-Game NPCs

## Thesis

A rules-aware simulator with structured telemetry can reveal why different AI strategies work in a stochastic, partially observable, economy-constrained game. Wingspan is the first testbed; the reusable architecture should transfer to board-game-like video game NPCs.

## Narrative Arc

1. **Problem**
   - Sequential economic games are hard because short-term efficient moves can damage long-term scoring.
   - Hidden information, card synergies, random draws, and opponent plans make pure greedy play fragile.

2. **Why Wingspan**
   - Multiple scoring paths.
   - Resource constraints.
   - Card and bonus uncertainty.
   - Engine-building tempo.
   - Expansion-aware rules.

3. **Architecture**
   - Content loader and typed schemas.
   - State and public/private observation boundaries.
   - Legal actions and deterministic transitions.
   - Event telemetry.
   - Agents, tournament runner, analysis helpers.

4. **Baselines**
   - Random legal agent.
   - Greedy immediate-score agent.
   - Strategy archetype bots.
   - Monte Carlo rollout agent.

5. **Analytics**
   - Score distributions.
   - Action frequencies by phase and archetype.
   - Card and habitat usage.
   - Round-goal and bonus-card contribution once scoring handlers mature.

6. **Bayesian Direction**
   - Beliefs over opponent archetype, hidden score, next action, and end-game score distribution.
   - Calibration and interpretability as first-class outcomes.

7. **Early Results**
   - To be filled after simulator fidelity improves and first tournaments are run.
   - Avoid publishing strategic claims until powers, scoring, and setup choices are more faithful.

8. **Reusable Template**
   - Game content.
   - State and observations.
   - Legal action generator.
   - Transition function.
   - Policy interface.
   - Telemetry.
   - Experiment tracking.

9. **Limitations**
   - IP/public-release considerations.
   - Current power/scoring simplifications.
   - Need for validation against rulebook edge cases and human play.

10. **Next Work**
    - Power handlers.
    - Bonus and round-goal scoring.
    - Batch tournaments.
    - Belief model implementation.
    - Strategy findings and visualizations.

## Evidence To Collect

- Full-game simulation traces.
- Tournament tables by agent matchup.
- Action-frequency charts.
- Score-category breakdowns.
- Belief calibration plots.
- Examples of interpretable decisions.
