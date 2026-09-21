# Docs

Project documentation beyond the root context files.

- `architecture/`: package structure, simulator design, and reusable board-game AI interfaces.
- `rules/`: encoded rule assumptions, expansion scope, data/rule encoding recommendations, and fidelity notes.
- `events/`: simulation telemetry contracts.
- `agents/`: baseline strategy definitions and model cards.
- `experiments/`: experiment plans and results.
- `decisions/`: ADR-style decisions.

Analysis layer:

- `analysis/sql/analysis_views.sql`: reproducible metric definitions over simulation telemetry.
- `analysis/apply_sql_views.py`: applies and probes the analysis views.
- `analysis/arm_contrast.py`: paired contrast of experimental arms against a baseline; `--agent kind@N` reads lineup position N (the study seat of a mirror match).
- `analysis/holdout_guardrail.py`: the standing 5% controls (every decided switch keeps its losing side; registry in `experiments/standing_holdouts.md`), pooled across batches.
- `analysis/decision_profile_report.py`: latency percentiles, node breakdown, cache hit rates and value per second against a baseline.
- `analysis/card_structure.py`: static synergy tables — what the deck supplies each bonus card, and what each bird carries.
- `analysis/bonus_card_seed_coverage.py` and `analysis/bonus_card_keep_contrast.py`: seed selection and the per-card paired contrast for the forced-keep study.
- `analysis/keep_policy_eval.py`: scores opening bonus-card policies on the forced arms without new games.
- `analysis/bird_value_regression.py`: observational bird value — ridge on birds played with agent fixed effects, over every archived game.
- `analysis/card_synergy_bench.py`: rules-computed pair synergy for every same-habitat brown pair (layer A of the synergy programme).
- `analysis/play_counterfactuals.py` and `analysis/play_attribution_summary.py`: exact counterfactual rollouts per archived play — timing value, card value, context lift (layer B).
- `analysis/r/play_attribution_hierarchical.R`: lme4 hierarchical model of play value — bird random effects and mechanic-pair interactions with shrinkage.
- `analysis/forced_play_contrast.py`: layer C — the 2×2 forced keep-and-play interaction contrast with matched controls.
- `analysis/bird_play_values.py`: writes the per-bird K=4 play-value table the measured opener reads (`configs/bird_values/`).
- `flows/human_vs_agent.py`: play one archived, replay-validated game from the terminal against the production agent (human-trace study H1–H3).
- `analysis/game_viewer.py`: step through an archived game decision by decision from one seat's point of view — board, private hand, legal actions, the search's own ranking, the choice and its effect (`experiments/game_viewer.md`).
- `analysis/base_game_bit_identity.py`: the base-game guard — replays an archived `rr_belief_opp` cell with the current code and diffs the action sequences; run after any engine, loader or flow change.
- `analysis/mirror_seat_effect.py`: turn-order effect in mirror matches, pooled across roots with one observation per seed (rotations of a seed are the same game; averaging them cancels a study-seat config).
- `analysis/launch_arm.py`: launches a paired arm the standard way (clean worktree at a commit, lineup runners, `--after` queueing) and writes `artifacts/<root>/launch/arm.json` as the record; `--mirror` runs self-play with an optional `--study-search` on lineup position 1. Not reboot-safe: after a reboot, delete the partial artifacts and relaunch.
- `analysis/compact_artifacts.py`: gzips per-game snapshot and replay-debug files under finished roots (about 60% of a root); reversible.
- `analysis/oracle_type_posteriors.py`: writes each opponent kind's converged belief posterior for the oracle-type search opponent model (`configs/belief/`).
- `analysis/fit_response_model.py`: fits the belief model's response likelihoods `P(family | profile, candidate values)` per roster kind from the archive (replayed real states, public candidate values), scored by leave-one-seed-out sequential log loss against the hand-set profiles (`configs/belief/fitted_response_models.json`).

Key rules docs:

- `architecture/simulator_architecture.md`: base simulator and rules-engine design.
- `architecture/decision_profiling.md`: the decision-tree profiler, the latency/value-per-ms report, the ledger of every arm's points-per-second, and where a default decision's time goes.
- `agents/archetype_policy_fix.md`: why the archetype bots were indistinguishable and how they were fixed.
- `agents/baseline_agents.md`: random, greedy, archetype, and Monte Carlo baseline definitions.
- `agents/bayesian_belief_model_plan.md`: first Bayesian belief model plan.
- `agents/opponent_fit_denial_gap.md`: why no agent can value denying a card an opponent specifically needs.
- `agents/opponent_response_belief_model.md`: Bayesian opponent-type and action-family response belief model.
- `agents/synergy_planner_agent.md`: the synergy programme — rules-computed pair synergy, counterfactual play attribution, mechanic-level model, forced-play confirmation, and the engine-potential term it feeds.
- `agents/net_value_opponent_response_agent.md`: score-margin, blocking, and next-opponent-response agent template.
- `agents/opening_setup_policies.md`: opening hand, bonus-card, and starting-food setup policy definitions.
- `events/simulation_event_taxonomy.md`: current simulation telemetry envelope and emitted event names.
- `events/postgresql_event_table_design.md`: draft event-log database tables and indexes.
- `experiments/case_study.md`: the case-study body — problem, what was built, the five findings, the method, limitations — written from the ledger.
- `experiments/case_study_outline.md`: public case-study narrative outline.
- `experiments/results_ledger.md`: one row per registered arm and study — score delta, p, latency, points per second, decision — and the round-robin and card-study headlines.
- `experiments/standing_holdouts.md`: registry of every decided switch kept alive at 5% as a long-run guardrail, how the draw works, how to read and retire one.
- `experiments/lookahead_compute_profile.md`: `apply_action` deep-copy profile and budgeted lookahead-agent probes.
- `experiments/baseline_matrix10_v2.md`: 10-seed baseline matrix on the corrected simulator.
- `experiments/potential_points_matrix10_smoke.md`: (superseded) 10-seed baseline matrix findings, decision timing, and current interpretation caveats.
- `experiments/public_belief_calibration.md`: first calibration harness and smoke readout for the net-value public opponent belief model (superseded).
- `experiments/belief_response_mode_ablation.md`: seed-matched expected-response vs best-response ablation.
- `experiments/mat_scaling_ablation.md`: does valuing the player-mat yield curve improve play?
- `experiments/round_robin_v3_guardrails.md`: guardrailed agents as first-class competitors.
- `experiments/round_robin_v2.md`: agent-vs-agent ranking on the corrected simulator (200 games).
- `experiments/round_robin_v1.md`: (superseded) first seat-swapped agent-vs-agent round robin (200 games).
- `experiments/bonus_card_selection_study_plan.md`: which bonus cards to keep — the choice is worth six points, per-bird cards win (+3.25, p=0.009), synergy is qualifier power quality not breadth, and the current policy is a coin flip.
- `experiments/resource_spending_ablation.md`: the third null, and why the pattern is the finding.
- `experiments/search_depth_experiment.md`: the first positive result — lookahead depth and coverage, after fixing a dead `search_depth` knob.
- `experiments/determinized_search_test.md`: how much of the search gain survives when the search cannot read hidden cards (+10.4 of +13.5).
- `experiments/game_horizon_ablation.md`: counting the whole game's turns instead of the round's costs −12.0; the round horizon is load-bearing.
- `experiments/reroll_chance_node.md`: feeder rolls resolved at apply time so rerolls are a chance node; knowing the roll was worth nothing (−0.31, n.s.).
- `experiments/round_robin_v5_feeder_odds.md`: corrected dice, and the feeder-odds ablation (null).
- `experiments/search_food_candidates.md`: bounding gain-food continuations in the search — a third off the decision-time tail for about 1 point.
- `experiments/feeder_odds_search_rerun.md`: the feeder-odds ablation re-run on the searching agent (still null, +0.49).
- `experiments/strategy_findings.md`: what the archive says about the game — dominance, hidden information, horizon, the champion's profile, openings, opponent and seat — one table per question with the design and detection limit behind each row, and what it cannot yet say.
- `experiments/self_play_opponent_plan.md`: registered design for mirror-match (self-play) and human-trace opponents — the test of whether "the opponent barely matters" is a property of the game or of the scripted roster.
- `experiments/search_opponent_model_test.md`: the Bayesian opponent posterior plays the opponent seats inside the search — decision cost more than halved, score null (+0.31), and the posterior tracks action mix rather than opponent type.
- `experiments/seat_effect_power_analysis.md`: how big a seat effect this design can detect, computed from measured variance.
- `experiments/seat_order_four_player_test.md`: the four-player test, and why seat claims need a stability check.
- `experiments/seat_order_investigation_3p.md`: why seat 3 appeared to win, and why it did not replicate.
- `experiments/seat_order_study_v1.md`: does turn order matter at 2-3 players? (result)
- `experiments/seat_order_study_plan.md`: planned study of whether turn order matters, at
  which player counts, and by how much.
- `decisions/0002-deterministic-first-player-with-seat-counterbalancing.md`: seat handling ADR.
- `decisions/0003-random-seed-is-the-sole-reproducibility-key.md`: RNG namespace ADR.
- `decisions/0004-cross-process-determinism-and-canonical-set-ordering.md`: cross-process determinism ADR.
- `decisions/0005-artifact-storage-is-object-storage.md`: artifacts are durable in MinIO; local `artifacts/` is a prunable cache.
- `rules/expansion_configuration.md`: packs + rules modules, ruleset ids, the engine's module gate, per-expansion rule deltas with rulebook pages (European, Oceania, Asia), the nine gates before a ruleset's first ledger row, and the phase order.
- `rules/birdfeeder_dice.md`: the six-face die, reroll/refill rules, and derived probabilities.
- `rules/bonus_card_composition.md`: the 26 core bonus cards are the base-game deck; Bird Bander and Diet Specialist are European.
- `rules/game_content_schema.md`: current content schema and enum design.
- `rules/power_handler_registry.md`: registry metadata approach for bird power handlers.
- `rules/multiplayer_rule_audit.md`: 3-5 player rule verification and the publication gate.
- `rules/scoring_handler_audit.md`: current scoring coverage audit utility and remaining validation work.
- `rules/wingspan_card_list_audit.md`: source workbook audit and normalization needs.
- `rules/data_and_rule_encoding_recommendations.md`: recommendations for power fidelity, handler mapping, expansion representation, and rule traceability.
