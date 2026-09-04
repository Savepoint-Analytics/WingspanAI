-- Analysis-ready views over Wingspan AI simulation telemetry.
--
-- These views are the reproducible metric layer between raw event storage and
-- Python/R analysis. Raw tables stay append-only and untouched; every derived
-- definition lives here so that a metric has exactly one definition.
--
-- Apply with:
--   python analysis/apply_sql_views.py
--
-- Naming: `v_` prefix, `lower_snake_case`, one grain documented per view.

-- ---------------------------------------------------------------------------
-- Grain: one row per simulation run.
-- Flattens the batch metadata written by flows/simulation_batch.py so that
-- experiment factors (agents, setup policy, content filter, rule coverage) are
-- queryable columns rather than nested JSON.
-- ---------------------------------------------------------------------------
create or replace view v_simulation_runs as
select
    r.simulation_run_id,
    r.run_started_at,
    r.run_label,
    split_part(r.run_label, ':', 1) as batch_kind,
    split_part(r.run_label, ':', 2) as batch_label,
    r.ruleset_id,
    r.random_seed,
    r.metadata ->> 'batch_id'                              as batch_id,
    r.metadata ->> 'catalog_source'                        as catalog_source,
    r.metadata ->> 'player_one_agent_kind'                 as player_one_agent_kind,
    r.metadata ->> 'player_one_agent_id'                   as player_one_agent_id,
    r.metadata ->> 'player_two_agent_kind'                 as player_two_agent_kind,
    r.metadata ->> 'player_two_agent_id'                   as player_two_agent_id,
    r.metadata ->> 'setup_policy_kind'                     as setup_policy_kind,
    (r.metadata ->> 'seat_rotation')::integer              as seat_rotation,
    (r.metadata ->> 'player_count')::integer               as player_count,
    r.metadata -> 'player_agent_kinds'                     as player_agent_kinds,
    r.metadata -> 'seated_agent_ids'                       as seated_agent_ids,
    r.metadata ->> 'guardrail_config_name'                 as guardrail_config_name,
    (r.metadata -> 'replay_validation' ->> 'is_valid')::boolean
                                                           as replay_is_valid,
    (r.metadata -> 'replay_validation' ->> 'checked_transitions')::integer
                                                           as replay_checked_transitions,
    (r.metadata -> 'rule_audits' -> 'powers' ->> 'implementation_coverage')::numeric
                                                           as power_implementation_coverage,
    (r.metadata -> 'rule_audits' -> 'powers' ->> 'unsupported_power_count')::integer
                                                           as unsupported_power_count,
    (r.metadata -> 'rule_audits' -> 'scoring' ->> 'bonus_card_coverage')::numeric
                                                           as bonus_card_coverage,
    (r.metadata -> 'rule_audits' -> 'scoring' ->> 'round_goal_coverage')::numeric
                                                           as round_goal_coverage,
    (r.metadata -> 'rule_audits' -> 'multiplayer' ->> 'publication_safe')::boolean
                                                           as multiplayer_rules_verified,
    (r.metadata -> 'rule_audits' -> 'multiplayer' ->> 'failed_check_count')::integer
                                                           as multiplayer_failed_checks,
    (r.metadata -> 'content_filter' ->> 'retained_bird_count')::integer
                                                           as filtered_bird_count,
    (r.metadata -> 'content_filter' ->> 'excluded_bird_count')::integer
                                                           as excluded_bird_count,
    r.metadata                                             as raw_metadata
from simulation_runs r;

-- ---------------------------------------------------------------------------
-- Grain: one row per game per player.
-- The primary analysis table: final score, category breakdown, win flag, and
-- the run factors needed to group results without re-joining JSON.
-- ---------------------------------------------------------------------------
create or replace view v_game_player_scores as
select
    g.game_id,
    g.simulation_run_id,
    g.random_seed,
    g.ruleset_id,
    g.player_count,
    g.terminal_reason,
    (g.outcome ->> 'turns_played')::integer as turns_played,
    s.player_id,
    -- Seat one always acts first; the first-player token is deterministic.
    nullif(split_part(s.player_id, '_', 2), '')::integer as seat_index,
    s.agent_id,
    s.total_score,
    s.bird_points,
    s.bonus_points,
    s.round_goal_points,
    s.egg_points,
    s.cached_food_points,
    s.tucked_card_points,
    s.is_winner,
    run.batch_kind,
    run.batch_label,
    run.batch_id,
    run.setup_policy_kind,
    run.seat_rotation,
    run.player_count as run_player_count,
    run.guardrail_config_name,
    run.replay_is_valid,
    run.power_implementation_coverage,
    run.multiplayer_rules_verified
from game_scores s
join games g
    on g.game_id = s.game_id
join v_simulation_runs run
    on run.simulation_run_id = g.simulation_run_id;

-- ---------------------------------------------------------------------------
-- Grain: one row per resolved action.
-- Action mix, timing within the game, and the replay hashes needed to tie an
-- action back to a verified state transition.
-- ---------------------------------------------------------------------------
create or replace view v_action_events as
select
    e.event_id,
    e.game_id,
    e.simulation_run_id,
    e.player_id,
    e.agent_id,
    e.round_number,
    e.turn_number,
    e.round_action_number,
    e.global_turn_number,
    e.occurred_at,
    e.payload -> 'action' ->> 'action_type'   as action_type,
    e.payload ->> 'action_label'              as action_label,
    e.payload -> 'action' ->> 'habitat'       as habitat,
    e.payload -> 'action' ->> 'bird_common_name' as bird_common_name,
    e.payload -> 'action' ->> 'food_type'     as food_type,
    (e.payload -> 'action' ->> 'egg_count')::integer as egg_count,
    (e.payload -> 'action' ->> 'reroll_birdfeeder')::boolean as reroll_birdfeeder,
    (e.payload -> 'action' ->> 'spend_card_for_extra_food')::boolean
                                              as spend_card_for_extra_food,
    (e.payload -> 'action' ->> 'spend_egg_for_extra_card')::boolean
                                              as spend_egg_for_extra_card,
    e.payload -> 'action' ->> 'spend_food_for_extra_egg' as spend_food_for_extra_egg,
    (e.payload -> 'action' ->> 'draw_from_deck_count')::integer as draw_from_deck_count,
    e.payload ->> 'state_hash_before'         as state_hash_before,
    e.payload ->> 'state_hash_after'          as state_hash_after
from simulation_events e
where e.event_name = 'action_resolved';

-- ---------------------------------------------------------------------------
-- Grain: one row per agent decision.
-- Union of the fields emitted by every agent family. Columns are null when the
-- acting policy does not emit them, which keeps one decision table rather than
-- one per agent type.
-- ---------------------------------------------------------------------------
create or replace view v_agent_decisions as
select
    e.event_id,
    e.game_id,
    e.simulation_run_id,
    e.player_id,
    e.agent_id,
    e.round_number,
    e.turn_number,
    e.round_action_number,
    e.global_turn_number,
    e.payload ->> 'policy'                                  as policy,
    e.payload ->> 'selected_action_type'                    as selected_action_type,
    (e.payload ->> 'legal_action_count')::integer           as legal_action_count,
    (e.payload ->> 'score_delta')::numeric                  as score_delta,
    (e.payload ->> 'action_selection_elapsed_ms')::numeric  as action_selection_elapsed_ms,
    (e.payload ->> 'decision_summary_elapsed_ms')::numeric  as decision_summary_elapsed_ms,
    (e.payload ->> 'decision_total_elapsed_ms')::numeric    as decision_total_elapsed_ms,
    -- potential-points fields
    (e.payload ->> 'selected_value_delta')::numeric         as selected_value_delta,
    (e.payload ->> 'realized_score_delta')::numeric         as realized_score_delta,
    (e.payload ->> 'used_endgame_search')::boolean          as used_endgame_search,
    -- monte-carlo fields
    (e.payload ->> 'completed_rollouts')::integer           as completed_rollouts,
    (e.payload ->> 'budget_exhausted')::boolean             as budget_exhausted,
    (e.payload ->> 'used_static_fallback')::boolean         as used_static_fallback,
    -- net-value fields
    (e.payload ->> 'selected_net_margin_delta')::numeric    as selected_net_margin_delta,
    (e.payload ->> 'selected_denial_value')::numeric        as selected_denial_value,
    e.payload -> 'predicted_opponent_response'              as predicted_opponent_response,
    e.payload -> 'public_response_candidates'               as public_response_candidates,
    -- guardrail fields
    (e.payload ->> 'guardrail_candidate_count')::integer    as guardrail_candidate_count,
    (e.payload ->> 'guardrail_excluded_count')::integer     as guardrail_excluded_count,
    e.payload -> 'selected_guardrail_reasons'               as selected_guardrail_reasons,
    e.payload -> 'guardrail_rule_hits'                      as guardrail_rule_hits,
    e.payload                                               as raw_payload
from simulation_events e
where e.event_name = 'agent_decision_summary';

-- ---------------------------------------------------------------------------
-- Grain: one row per player per game setup.
-- Opening choices are private information, so this view is intentionally
-- separate from the public action views and callers must opt into it.
-- ---------------------------------------------------------------------------
create or replace view v_setup_selections as
select
    e.event_id,
    e.game_id,
    e.simulation_run_id,
    e.player_id,
    e.agent_id,
    e.payload ->> 'selection_source'                as selection_source,
    e.payload ->> 'setup_policy_id'                 as setup_policy_id,
    jsonb_array_length(e.payload -> 'kept_bird_names')        as kept_bird_count,
    jsonb_array_length(e.payload -> 'kept_bonus_card_names')  as kept_bonus_card_count,
    jsonb_array_length(e.payload -> 'starting_food')          as starting_food_count,
    jsonb_array_length(e.payload -> 'discarded_bird_names')   as discarded_bird_count,
    e.payload -> 'kept_bird_names'                  as kept_bird_names,
    e.payload -> 'kept_bonus_card_names'            as kept_bonus_card_names,
    e.payload -> 'starting_food'                    as starting_food
from simulation_events e
where e.event_name = 'setup_selection_applied';

-- ---------------------------------------------------------------------------
-- Grain: one row per game/agent/action_type.
-- The action-mix signature used to tell strategy archetypes apart.
-- ---------------------------------------------------------------------------
create or replace view v_agent_action_mix as
select
    a.game_id,
    a.simulation_run_id,
    a.agent_id,
    a.player_id,
    a.action_type,
    count(*)                                          as action_count,
    round(
        100.0 * count(*) / nullif(sum(count(*)) over (partition by a.game_id, a.agent_id), 0),
        2
    )                                                 as action_share_pct
from v_action_events a
group by a.game_id, a.simulation_run_id, a.agent_id, a.player_id, a.action_type;

-- ---------------------------------------------------------------------------
-- Grain: one row per agent per run factor combination.
-- Headline comparison table: win rate, score distribution, and score mix.
-- Filters to replay-valid games only, because an unverified trace should never
-- reach a strategy claim.
-- ---------------------------------------------------------------------------
create or replace view v_agent_performance as
select
    s.agent_id,
    s.batch_kind,
    s.batch_label,
    s.setup_policy_kind,
    s.guardrail_config_name,
    count(*)                                        as games,
    round(avg(s.total_score), 2)                    as avg_score,
    percentile_cont(0.5) within group (order by s.total_score) as median_score,
    min(s.total_score)                              as min_score,
    max(s.total_score)                              as max_score,
    round(stddev_samp(s.total_score), 2)            as score_stddev,
    round(avg(case when s.is_winner then 1.0 else 0.0 end), 4) as win_rate,
    round(avg(s.bird_points), 2)                    as avg_bird_points,
    round(avg(s.bonus_points), 2)                   as avg_bonus_points,
    round(avg(s.round_goal_points), 2)              as avg_round_goal_points,
    round(avg(s.egg_points), 2)                     as avg_egg_points,
    round(avg(s.cached_food_points), 2)             as avg_cached_food_points,
    round(avg(s.tucked_card_points), 2)             as avg_tucked_card_points
from v_game_player_scores s
where s.replay_is_valid is not false
group by
    s.agent_id,
    s.batch_kind,
    s.batch_label,
    s.setup_policy_kind,
    s.guardrail_config_name;

-- ---------------------------------------------------------------------------
-- Grain: one row per ordered agent pair per game.
-- Self-join over scores so head-to-head margins can be computed directly.
-- ---------------------------------------------------------------------------
create or replace view v_head_to_head_games as
select
    a.game_id,
    a.simulation_run_id,
    a.random_seed,
    a.batch_label,
    a.setup_policy_kind,
    a.seat_rotation,
    a.agent_id                       as agent_id,
    b.agent_id                       as opponent_agent_id,
    a.player_id                      as player_id,
    b.player_id                      as opponent_player_id,
    a.total_score                    as score,
    b.total_score                    as opponent_score,
    a.total_score - b.total_score    as score_margin,
    a.is_winner,
    a.replay_is_valid
from v_game_player_scores a
join v_game_player_scores b
    on b.game_id = a.game_id
   and b.player_id <> a.player_id;

-- ---------------------------------------------------------------------------
-- Grain: one row per agent matchup per setup-policy level.
-- Seat-aware: reports the agent's win rate in each seat so a result can be
-- checked for seat robustness before it is treated as a strategy finding.
-- ---------------------------------------------------------------------------
create or replace view v_head_to_head_summary as
select
    h.agent_id,
    h.opponent_agent_id,
    h.setup_policy_kind,
    h.batch_label,
    count(*)                                                   as games,
    round(avg(case when h.is_winner then 1.0 else 0.0 end), 4) as win_rate,
    round(avg(h.score_margin), 2)                              as avg_score_margin,
    round(
        avg(case when h.player_id = 'player_1' and h.is_winner then 1.0
                 when h.player_id = 'player_1' then 0.0 end),
        4
    )                                                          as win_rate_as_seat_one,
    round(
        avg(case when h.player_id = 'player_2' and h.is_winner then 1.0
                 when h.player_id = 'player_2' then 0.0 end),
        4
    )                                                          as win_rate_as_seat_two
from v_head_to_head_games h
where h.replay_is_valid is not false
group by h.agent_id, h.opponent_agent_id, h.setup_policy_kind, h.batch_label;

-- ---------------------------------------------------------------------------
-- Grain: one row per agent per run.
-- Compute cost per decision, needed before scaling any lookahead-heavy matrix.
-- ---------------------------------------------------------------------------
create or replace view v_decision_cost as
select
    d.agent_id,
    d.simulation_run_id,
    d.policy,
    count(*)                                          as decisions,
    round(avg(d.decision_total_elapsed_ms), 3)        as avg_decision_ms,
    round(
        percentile_cont(0.95) within group (order by d.decision_total_elapsed_ms)::numeric,
        3
    )                                                 as p95_decision_ms,
    round(max(d.decision_total_elapsed_ms), 3)        as max_decision_ms,
    round(avg(d.legal_action_count), 2)               as avg_legal_actions,
    sum(case when d.budget_exhausted then 1 else 0 end)      as budget_exhausted_decisions,
    sum(case when d.used_static_fallback then 1 else 0 end)  as static_fallback_decisions
from v_agent_decisions d
group by d.agent_id, d.simulation_run_id, d.policy;

-- ---------------------------------------------------------------------------
-- Grain: one row per setup policy per agent.
-- Ties opening choices to final outcomes, which is what the setup-policy
-- experiment needs and what the artifact-only comparison could not express.
-- ---------------------------------------------------------------------------
create or replace view v_setup_policy_outcomes as
select
    sel.setup_policy_id,
    sel.agent_id,
    scores.setup_policy_kind,
    scores.batch_label,
    count(*)                                                     as games,
    round(avg(sel.kept_bird_count), 2)                           as avg_kept_birds,
    round(avg(sel.starting_food_count), 2)                       as avg_starting_food,
    round(avg(scores.total_score), 2)                            as avg_final_score,
    round(avg(case when scores.is_winner then 1.0 else 0.0 end), 4) as win_rate,
    round(avg(scores.bird_points), 2)                            as avg_bird_points
from v_setup_selections sel
join v_game_player_scores scores
    on scores.game_id = sel.game_id
   and scores.player_id = sel.player_id
where scores.replay_is_valid is not false
group by sel.setup_policy_id, sel.agent_id, scores.setup_policy_kind, scores.batch_label;

-- ---------------------------------------------------------------------------
-- Grain: one row per run.
-- Data-quality gate. Query this before interpreting any batch: a run that is
-- not replay-valid or has unsupported powers should not back a claim.
-- ---------------------------------------------------------------------------
create or replace view v_run_quality as
select
    run.simulation_run_id,
    run.batch_kind,
    run.batch_label,
    run.batch_id,
    run.catalog_source,
    run.replay_is_valid,
    run.replay_checked_transitions,
    run.power_implementation_coverage,
    run.unsupported_power_count,
    run.bonus_card_coverage,
    run.round_goal_coverage,
    run.filtered_bird_count,
    run.excluded_bird_count,
    run.player_count,
    run.multiplayer_rules_verified,
    run.multiplayer_failed_checks,
    case
        when run.replay_is_valid is not true then 'replay_invalid'
        -- A 3+ player result must have passed the player-count-sensitive
        -- rule audit (ADR 0002 follow-up); see rules/multiplayer_audit.py.
        when coalesce(run.player_count, 2) >= 3
             and run.multiplayer_rules_verified is not true
            then 'multiplayer_rules_unverified'
        when coalesce(run.power_implementation_coverage, 0) < 0.9 then 'low_power_coverage'
        when coalesce(run.bonus_card_coverage, 0) < 1.0 then 'incomplete_bonus_scoring'
        when coalesce(run.round_goal_coverage, 0) < 1.0 then 'incomplete_round_goal_scoring'
        else 'claim_grade'
    end as quality_gate
from v_simulation_runs run;

-- ---------------------------------------------------------------------------
-- Grain: one row per seat index per player count.
-- Answers the standing research question: does turn order matter, at which
-- player counts, and by how much? `seat_index` 1 always acts first because the
-- simulator's first-player token is deterministic (ADR 0002); seat advantage is
-- removed by counterbalancing rotations, not by randomizing the token.
--
-- Read `win_rate` against `fair_share_win_rate`. A seat effect exists when they
-- differ; the size of the difference is the magnitude.
-- ---------------------------------------------------------------------------
create or replace view v_seat_effect as
select
    s.player_count,
    s.seat_index,
    s.batch_kind,
    s.batch_label,
    count(*)                                                   as games,
    round(1.0 / nullif(s.player_count, 0), 4)                  as fair_share_win_rate,
    round(avg(case when s.is_winner then 1.0 else 0.0 end), 4) as win_rate,
    round(
        avg(case when s.is_winner then 1.0 else 0.0 end) - 1.0 / nullif(s.player_count, 0),
        4
    )                                                          as win_rate_vs_fair_share,
    round(avg(s.total_score), 2)                               as avg_score,
    round(stddev_samp(s.total_score), 2)                       as score_stddev
from v_game_player_scores s
where s.replay_is_valid is not false
group by s.player_count, s.seat_index, s.batch_kind, s.batch_label;

-- ---------------------------------------------------------------------------
-- Grain: one row per player count per batch.
-- Collapses `v_seat_effect` into a single magnitude per configuration, which is
-- the "by how much does order matter" headline.
-- ---------------------------------------------------------------------------
create or replace view v_seat_effect_magnitude as
select
    e.player_count,
    e.batch_kind,
    e.batch_label,
    sum(e.games)                                    as games,
    max(e.win_rate) - min(e.win_rate)               as win_rate_spread,
    round(max(e.avg_score) - min(e.avg_score), 2)   as avg_score_spread,
    max(e.win_rate_vs_fair_share)                   as best_seat_edge,
    min(e.win_rate_vs_fair_share)                   as worst_seat_edge
from v_seat_effect e
group by e.player_count, e.batch_kind, e.batch_label;

-- ---------------------------------------------------------------------------
-- Grain: one row per game per player, for rows that FAIL integrity.
-- `total_score` is persisted from the run outcome while the six category
-- columns come from the game-ended breakdown payload. Nothing in the write path
-- asserts they agree, so a scoring bug could inflate a total with no category
-- showing where the points came from. This view should always be empty.
-- ---------------------------------------------------------------------------
create or replace view v_score_integrity_failures as
select
    s.game_id,
    s.player_id,
    s.agent_id,
    s.total_score,
    s.bird_points
        + s.bonus_points
        + s.round_goal_points
        + s.egg_points
        + s.cached_food_points
        + s.tucked_card_points as category_sum,
    s.total_score
        - (
            s.bird_points
            + s.bonus_points
            + s.round_goal_points
            + s.egg_points
            + s.cached_food_points
            + s.tucked_card_points
        ) as discrepancy
from game_scores s
where s.total_score <> (
    s.bird_points
    + s.bonus_points
    + s.round_goal_points
    + s.egg_points
    + s.cached_food_points
    + s.tucked_card_points
);

-- ---------------------------------------------------------------------------
-- Grain: one row per scoring category.
-- Where do points actually come from? Reports mean points, share of the average
-- final score, and how often a category is scored at all. `players_scoring_pct`
-- near zero is the signal that a category may be unimplemented rather than
-- merely unpopular.
-- ---------------------------------------------------------------------------
create or replace view v_score_composition as
with scored as (
    select * from v_game_player_scores where replay_is_valid is not false
), totals as (
    select nullif(avg(total_score), 0) as avg_total, count(*) as n from scored
)
select
    category,
    round(avg(points), 2) as avg_points,
    round(100.0 * avg(points) / (select avg_total from totals), 1) as share_of_total_pct,
    round(100.0 * sum(case when points > 0 then 1 else 0 end) / count(*), 1)
        as players_scoring_pct,
    max(points) as max_points,
    (select n from totals) as player_games
from scored,
     lateral (values
         ('bird_points', bird_points),
         ('bonus_points', bonus_points),
         ('round_goal_points', round_goal_points),
         ('egg_points', egg_points),
         ('cached_food_points', cached_food_points),
         ('tucked_card_points', tucked_card_points)
     ) as unpivoted(category, points)
group by category;
