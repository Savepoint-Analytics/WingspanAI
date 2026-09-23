"""Regression coverage for the Wingspan KPI taxonomy helpers.

Hand-built rows so the expected numbers are obvious by inspection. The
properties pinned are the ones the taxonomy depends on: category shares that
sum to the score, fulfilment measured against the birds actually played, the
habitat specialization index, and a coverage report that says `missing`
rather than returning zeros.
"""

from __future__ import annotations

from wingspan_ai.analysis import (
    action_kpis,
    agent_key,
    bird_utilization_kpis,
    bonus_card_kpis,
    comparative_kpis,
    round_goal_kpis,
    scoring_kpis,
    taxonomy_coverage_report,
    tempo_kpis,
)


def _score(game, player, agent, total, **categories):
    row = {
        "game_id": game,
        "player_id": player,
        "agent_id": agent,
        "total_score": total,
        "is_winner": categories.pop("is_winner", False),
    }
    for name in (
        "bird_points",
        "bonus_points",
        "round_goal_points",
        "egg_points",
        "cached_food_points",
        "tucked_card_points",
    ):
        row[name] = categories.get(name, 0)
    return row


def _event(
    name, *, game="g1", player="player_1", agent="engine_builder_p1", round_number=1, payload=None
):
    return {
        "name": name,
        "game_id": game,
        "player_id": player,
        "agent_id": agent,
        "round_number": round_number,
        "payload": payload or {},
    }


def _bird(
    common_name, habitat, *, vp=4, eggs=0, activations=0, round_played=1, tags=(), color="brown"
):
    return {
        "common_name": common_name,
        "habitat": habitat,
        "victory_points": vp,
        "eggs": eggs,
        "cached_food": 0,
        "tucked_cards": 0,
        "activations": activations,
        "power_color": color,
        "round_played": round_played,
        "bonus_card_tags": list(tags),
        "power_yield": {"food": activations},
    }


def test_agent_key_strips_the_seat_suffix():
    assert agent_key("engine_builder_p2") == "engine_builder"
    assert agent_key("guardrailed_potential_points_p1") == "potential_points"
    assert agent_key(None) == "unknown"


def test_scoring_kpis_report_category_shares_of_the_total():
    scores = [
        _score(
            "g1",
            "player_1",
            "potential_points_p1",
            80,
            bird_points=40,
            egg_points=40,
            is_winner=True,
        ),
        _score("g1", "player_2", "greedy_immediate_p2", 40, bird_points=20, egg_points=20),
    ]
    by_agent = {row["agent"]: row for row in scoring_kpis(scores)["by_agent"]}
    champion = by_agent["potential_points"]
    assert champion["avg_total_score"] == 80
    assert champion["win_rate"] == 1.0
    assert champion["bird_points_share"] == 0.5
    assert champion["egg_points_share"] == 0.5
    composition = {row["category"]: row for row in scoring_kpis(scores)["composition"]}
    assert composition["bird_points"]["avg_points"] == 30
    # Nobody scored a bonus card, so the share is zero rather than absent.
    assert composition["bonus_points"]["players_scoring_pct"] == 0.0


def test_round_goal_kpis_use_the_event_when_present_and_stay_empty_when_not():
    scores = [_score("g1", "player_1", "engine_builder_p1", 50, round_goal_points=10)]
    without = round_goal_kpis(scores)
    assert without["by_agent"][0]["avg_round_goal_points"] == 10
    assert without["by_agent"][0]["goal_share_of_score"] == 0.2
    assert without["by_round"] == []
    event = _event(
        "round_goal_scored",
        payload={
            "goal_round": 1,
            "goal_name": "[egg] in [bowl]",
            "counts": {"player_1": 3, "player_2": 1},
            "points_awarded": {"player_1": 4, "player_2": 1},
            "agent_ids": {"player_1": "engine_builder_p1", "player_2": "greedy_immediate_p2"},
            "contested": False,
        },
    )
    with_event = round_goal_kpis(scores, [event])["by_round"]
    rows = {(row["agent"], row["round_number"]): row for row in with_event}
    assert rows[("engine_builder", 1)]["took_first_rate"] == 1.0
    assert rows[("greedy_immediate", 1)]["took_first_rate"] == 0.0
    assert rows[("greedy_immediate", 1)]["qualified_rate"] == 1.0


def test_bird_utilization_counts_draws_plays_habitats_and_specialization():
    events = [
        _event(
            "action_resolved",
            payload={
                "action": {
                    "action_type": "draw_cards",
                    "tray_indices": [0, 1],
                    "draw_from_deck_count": 1,
                }
            },
        ),
        _event(
            "action_resolved", payload={"action": {"action_type": "play_bird", "habitat": "forest"}}
        ),
        _event(
            "bird_scorecard",
            payload={
                "agent_id": "engine_builder_p1",
                "player_id": "player_1",
                "bonus_card_names": ["Bird Feeder"],
                "birds": [
                    _bird("A", "forest", activations=4, tags=["Bird Feeder"]),
                    _bird("B", "forest", activations=2),
                ],
            },
        ),
    ]
    result = bird_utilization_kpis(events)
    draw = result["draw_efficiency"][0]
    assert draw["cards_drawn"] == 3 and draw["birds_played"] == 1
    agent_row = result["by_agent"][0]
    assert agent_row["avg_birds_played"] == 2
    assert agent_row["avg_activation_rate_proxy"] == 3.0
    # Both birds in one habitat: the Herfindahl index is 1.0.
    assert agent_row["avg_specialization_hhi"] == 1.0
    assert agent_row["avg_forest_birds"] == 2


def test_bonus_card_fulfilment_counts_only_birds_tagged_for_the_held_card():
    events = [
        _event(
            "setup_selection_applied",
            payload={
                "agent_id": "engine_builder_p1",
                "player_id": "player_1",
                "kept_bonus_card_names": ["Bird Feeder"],
                "discarded_bonus_card_names": ["Falconer"],
                "kept_bird_names": ["A", "B", "C"],
                "discarded_bird_names": ["D", "E"],
            },
        ),
        _event(
            "bird_scorecard",
            payload={
                "agent_id": "engine_builder_p1",
                "player_id": "player_1",
                "bonus_card_names": ["Bird Feeder"],
                "birds": [
                    _bird("A", "forest", tags=["Bird Feeder"]),
                    _bird("B", "wetland", tags=["Falconer"]),
                    _bird("C", "grassland", tags=[]),
                ],
            },
        ),
    ]
    result = bonus_card_kpis(events)
    selection = result["selection"][0]
    assert selection["kept_bonus"] == "Bird Feeder"
    assert selection["avg_bonus_seen"] == 2
    assert selection["avg_birds_seen"] == 5
    fulfilment = result["fulfilment"][0]
    # One of three played birds matches the card actually held.
    assert fulfilment["avg_birds_matching_bonus"] == 1
    assert round(fulfilment["avg_fulfilment_vs_end_pool"], 4) == round(1 / 3, 4)


def test_action_and_tempo_kpis():
    events = [
        _event("action_resolved", payload={"action": {"action_type": "gain_food"}}),
        _event(
            "action_resolved", payload={"action": {"action_type": "play_bird", "habitat": "forest"}}
        ),
        _event(
            "bird_scorecard",
            payload={
                "agent_id": "engine_builder_p1",
                "player_id": "player_1",
                "bonus_card_names": [],
                "birds": [
                    _bird("A", "forest", round_played=1),
                    _bird("B", "wetland", round_played=3),
                ],
            },
        ),
    ]
    actions = action_kpis(events, [_score("g1", "player_1", "engine_builder_p1", 40)])
    row = actions["by_agent"][0]
    assert row["actions"] == 2
    assert row["play_bird_share"] == 0.5
    assert row["gain_food_share"] == 0.5
    assert actions["action_efficiency"][0]["avg_points_per_action"] == 20.0
    tempo = tempo_kpis(events)["first_habitat_round"][0]
    assert tempo["avg_first_forest_round"] == 1
    assert tempo["avg_first_wetland_round"] == 3


def test_comparative_kpis_measure_margin_and_head_to_head():
    scores = [
        _score("g1", "player_1", "potential_points_p1", 80, is_winner=True),
        _score("g1", "player_2", "greedy_immediate_p2", 50),
        _score("g2", "player_1", "potential_points_p1", 60, is_winner=True),
        _score("g2", "player_2", "greedy_immediate_p2", 55),
    ]
    result = comparative_kpis(scores)
    margins = result["margins"][0]
    assert margins["winner_agent"] == "potential_points"
    assert margins["wins"] == 2
    assert margins["avg_margin"] == 17.5
    head = {(row["agent"], row["opponent"]): row for row in result["head_to_head"]}
    assert head[("potential_points", "greedy_immediate")]["win_rate"] == 1.0
    assert head[("greedy_immediate", "potential_points")]["avg_score_margin"] == -17.5


def test_coverage_report_marks_food_economy_missing_whatever_is_present():
    events = [
        _event("bird_scorecard", payload={"birds": []}),
        _event("setup_selection_applied", payload={}),
        _event("action_resolved", payload={"action": {}}),
    ]
    rows = {row["kpi_family"]: row for row in taxonomy_coverage_report(events)}
    assert len(rows) == 9
    assert rows["bird_utilization"]["coverage"] == "supported"
    assert rows["turn_action_level"]["coverage"] == "supported"
    assert rows["bonus_cards"]["coverage"] == "partial"
    # No event carries food tokens, so this family can never be satisfied.
    assert rows["food_economy"]["coverage"] == "missing"
    assert "food_state" in rows["food_economy"]["missing_events"]
    # Round goals need an event this run does not have.
    assert rows["end_of_round_goals"]["coverage"] == "missing"
