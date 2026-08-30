# Simulator and Rules Engine Architecture

Status: initial draft, 2026-05-03

## Purpose

The simulator should make Wingspan games reproducible, inspectable, and useful for AI-player research. The first implementation target is the base-game economy loop: setup, legal action generation, deterministic state transitions, seeded randomness, public/private state boundaries, and final-score scaffolding.

This document describes the intended rules-engine shape. Detailed power handlers, round-goal scoring, bonus-card scoring, telemetry emission, and experiment orchestration should build on this foundation rather than live inside it.

## Current Implementation Slice

Implemented modules:

- `src/wingspan_ai/content/loader.py`: translates `data/raw/wingspan-card-list.xlsx` into typed `ContentCatalog` objects.
- `src/wingspan_ai/state/models.py`: represents full game state, player state, public state, private state, decks, tray, birdfeeder, habitats, and round state.
- `src/wingspan_ai/rules/actions.py`: defines concrete legal action objects.
- `src/wingspan_ai/rules/base_game.py`: handles base setup, legal actions, state transitions, round advancement, and scoring skeleton.
- `src/wingspan_ai/agents/random_legal.py`: selects uniformly from legal actions using seeded randomness.

## Core Boundaries

| Layer | Owns | Should not own |
|---|---|---|
| Content loader | Workbook parsing, normalization, validation issues, typed content objects. | Rule decisions, state mutation, agent choices. |
| State models | Full state, public/private projections, decks, tray, birdfeeder, player boards. | Validation of whether an action is legal. |
| Rules engine | Setup, legal action generation, transition functions, scoring rules, randomness boundaries. | Model training, event storage, notebooks. |
| Agents | Choosing from legal actions or scoring candidate actions. | Mutating game state directly. |
| Simulation runner | Sequencing agents through full games and emitting telemetry. | Card parsing or low-level rule implementations. |

## Setup

Base-game setup should be deterministic for a given seed:

1. Load a `ContentCatalog`.
2. Filter to the requested content packs and rules modules.
3. Shuffle bird cards, bonus cards, and round goals with `random.Random(seed)`.
4. Deal five bird cards and two bonus cards to each player.
5. Deal three public tray cards.
6. Roll five birdfeeder dice from base food faces.
7. Select four round goals.
8. Initialize round 1 with eight action cubes per player.

Initial hand/food selection now uses an explicit `InitialSelection` object. The runner asks agents for `choose_initial_selection(player, context)` when available, otherwise it falls back to `DefaultSetupPolicy`: keep three low-cost birds, keep one bonus card, and choose two starting food tokens biased toward kept bird costs. Automated agents can now attach setup policies for potential-points, archetype, and net-value openings while only receiving public setup context beyond their own private hand.

## Legal Actions

The base legal action families are:

- `play_bird`: choose a bird from hand and a legal habitat; requires food and egg payment.
- `gain_food`: choose one visible birdfeeder die face.
- `lay_eggs`: place up to two eggs on available played-bird capacity.
- `draw_cards`: draw from the public tray or the face-down deck.

Legal action generation should remain pure: given a `GameState` and player, it returns concrete `LegalAction` values without mutating state. Action masks for ML agents can later be derived from the same list.

## Transitions

`apply_action` validates that the selected action appears in the generated legal action list, deep-copies the current state, applies the transition, then advances turn order.

Current transition rules:

- Playing a bird spends food, spends required eggs, removes the bird from hand, and appends a `BirdSlot` to the selected habitat.
- Gaining food uses habitat-scaled food counts, optional discard-card conversions, and deterministic reroll choices when the birdfeeder can be rerolled.
- Laying eggs uses habitat-scaled egg counts and optional spend-food conversions, then fills played birds in deterministic habitat order up to capacity.
- Drawing cards uses habitat-scaled card counts, tray/deck choice tuples, and optional spend-egg conversions.
- Habitat powers resolve right-to-left after the base habitat action.
- Round transition scores the completed competitive round goal, refreshes the public bird tray, rotates first player, and resets action cubes to 7, 6, and 5 for rounds 2, 3, and 4.
- The game is marked over after all round-4 action cubes are spent.

## Scoring

The current final-score implementation counts:

- Bird victory points.
- Eggs.
- Cached food.
- Tucked cards.
- Accumulated competitive round-goal placement points.
- A broader slice of base-game bonus-card handlers.

The bonus-card handlers are still not exhaustive, but common base-game categories such as nest type, food cost, predator/flocking tags, habitat-only birds, wingspan thresholds, egg thresholds, and some name-based cards are now covered for smoke experiments.

## Power Handlers

The first executable power path is deliberately small:

- White powers are checked after playing a bird.
- Brown powers are checked after activating the matching habitat action.
- Brown powers resolve right-to-left.
- Pink powers have first deterministic reaction hooks for egg laying, food gain, caching, and tuck reactions.
- Workbook loading and runtime resolution now classify common power text into stable registry handler keys.
- Implemented handler keys currently cover simple `Gain 1 [food]`, `Gain 1 [die]`, `Draw 1 [card]`, `Lay 1 [egg]`, simple tuck/draw, cache, all-player food powers, discard-egg-to-gain-food, discard-food-to-tuck, and deterministic predator approximations.

This is a scaffold, not a full parser. More high-volume powers should continue moving behind registry handler keys before strategic experiments treat them as faithful.

## Bird Powers

The loader preserves raw power text and assigns implementation status. Base v1 transitions do not execute powers yet.

Recommended power-handler path:

1. Add a power handler registry with source references and implementation status.
2. Implement high-impact base powers that affect the core economy loop.
3. Mark safe v1 no-ops explicitly.
4. Allow experiments to filter out birds whose powers are not ready for the research question.

## Randomness

Randomness should be localized and seedable:

- Setup shuffles and birdfeeder rolls use local `random.Random(seed)` instances.
- Agents own their own random generators.
- Future stochastic powers should receive an explicit RNG from the transition boundary.

No rules function should depend on global random state.

## Public and Private Information

`GameState` contains full game state for simulation and training logs. `to_public_state` strips hidden hands, hidden bonus cards, and deck order while preserving public counts. `to_private_state` exposes one player's private hand and bonus cards.

Telemetry should mark private/debug payloads explicitly before they are used for model training or analysis.

## Near-Term Follow-Ups

- Add a single-game runner that loops agents through `legal_actions -> select_action -> apply_action`.
- Add telemetry events around setup, legal action generation, selected action, and resolved action.
- Add power-handler registry metadata and source references.
- Add first bonus-card and round-goal scoring handlers.
- Decide how initial hand/food selection should be represented for automated agents.
