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

Key rules docs:

- `architecture/simulator_architecture.md`: base simulator and rules-engine design.
- `agents/archetype_policy_fix.md`: why the archetype bots were indistinguishable and how they were fixed.
- `agents/baseline_agents.md`: random, greedy, archetype, and Monte Carlo baseline definitions.
- `agents/bayesian_belief_model_plan.md`: first Bayesian belief model plan.
- `agents/opponent_fit_denial_gap.md`: why no agent can value denying a card an opponent specifically needs.
- `agents/opponent_response_belief_model.md`: Bayesian opponent-type and action-family response belief model.
- `agents/net_value_opponent_response_agent.md`: score-margin, blocking, and next-opponent-response agent template.
- `agents/opening_setup_policies.md`: opening hand, bonus-card, and starting-food setup policy definitions.
- `events/simulation_event_taxonomy.md`: current simulation telemetry envelope and emitted event names.
- `events/postgresql_event_table_design.md`: draft event-log database tables and indexes.
- `experiments/case_study_outline.md`: public case-study narrative outline.
- `experiments/lookahead_compute_profile.md`: `apply_action` deep-copy profile and budgeted lookahead-agent probes.
- `experiments/baseline_matrix10_v2.md`: 10-seed baseline matrix on the corrected simulator.
- `experiments/potential_points_matrix10_smoke.md`: (superseded) 10-seed baseline matrix findings, decision timing, and current interpretation caveats.
- `experiments/public_belief_calibration.md`: first calibration harness and smoke readout for the net-value public opponent belief model (superseded).
- `experiments/belief_response_mode_ablation.md`: seed-matched expected-response vs best-response ablation.
- `experiments/mat_scaling_ablation.md`: does valuing the player-mat yield curve improve play?
- `experiments/round_robin_v3_guardrails.md`: guardrailed agents as first-class competitors.
- `experiments/round_robin_v2.md`: agent-vs-agent ranking on the corrected simulator (200 games).
- `experiments/round_robin_v1.md`: (superseded) first seat-swapped agent-vs-agent round robin (200 games).
- `experiments/bonus_card_selection_study_plan.md`: which bonus cards to keep at setup, and when.
- `experiments/resource_spending_ablation.md`: the third null, and why the pattern is the finding.
- `experiments/round_robin_v5_feeder_odds.md`: corrected dice, and the feeder-odds ablation (null).
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
- `rules/birdfeeder_dice.md`: the six-face die, reroll/refill rules, and derived probabilities.
- `rules/game_content_schema.md`: current content schema and enum design.
- `rules/power_handler_registry.md`: registry metadata approach for bird power handlers.
- `rules/multiplayer_rule_audit.md`: 3-5 player rule verification and the publication gate.
- `rules/scoring_handler_audit.md`: current scoring coverage audit utility and remaining validation work.
- `rules/wingspan_card_list_audit.md`: source workbook audit and normalization needs.
- `rules/data_and_rule_encoding_recommendations.md`: recommendations for power fidelity, handler mapping, expansion representation, and rule traceability.
