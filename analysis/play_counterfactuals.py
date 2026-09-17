"""Play-level attribution by exact counterfactual rollout on archived games.

Layer B of the synergy programme (``docs/agents/synergy_planner_agent.md``).
Every archived game can be reconstructed to the state before any decision
(the replay validator already does this from telemetry). For each
``play_bird`` decision by the study agent, two branches are rolled out to the
end of the game under the same cheap continuation policies for both seats:

- **actual**: the bird is played as recorded;
- **not now**: the continuation policy chooses instead, with every action
  that plays *this* bird removed for this turn only — the bird stays in hand
  and may be played later. ``actual − not_now`` is the **timing** value.
- **never**: the bird is removed from the hand before the continuation
  chooses. ``actual − never`` is the **card** value in this context.

Because the state, seed and continuation are identical, each paired
difference in the study agent's final score is a realized marginal value in
that context, immediate and downstream together, with deck and opponent luck
differenced out. The bird's own end-of-rollout ledger (eggs, cache,
tucks, power yield) splits that value into what it did on arrival and what
it did afterwards.

The continuation policy defines the value: this run uses the one-ply
potential agent for a ``potential_points`` seat and the archived agent kind
for any cheap opponent, so the number is "what this play was worth to a
competent but non-searching continuation".

``--continuation-samples K`` rolls each branch out from K determinized copies
of the state (opponents' hidden cards and the deck resampled, the acting
player's own information unchanged) and averages, which trades K× the compute
for a value that no longer depends on one particular deck order — the fix for
the path-dependence noise of a single deterministic continuation.

    python analysis/play_counterfactuals.py artifacts/rr_belief_opp \\
        --study-agent potential_points --out artifacts/play_counterfactuals/rr_belief_opp.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wingspan_ai.agents.determinization import determinize_state  # noqa: E402
from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig  # noqa: E402
from wingspan_ai.content.loader import (  # noqa: E402
    DEFAULT_WORKBOOK_PATH,
    load_base_game_content_catalog,
)
from wingspan_ai.content.schemas import FoodType, Habitat  # noqa: E402
from wingspan_ai.rules.actions import ActionType, LegalAction, render_action  # noqa: E402
from wingspan_ai.rules.base_game import (  # noqa: E402
    InitialSelection,
    apply_action,
    apply_action_in_place,
    apply_initial_selection_choice,
    legal_actions_for_current_player,
    score_player,
    setup_base_game,
)
from wingspan_ai.state.models import GameState  # noqa: E402

CHEAP_SEARCH = PotentialPointsSearchConfig(
    search_depth=1, final_search_turns=0, determinization_samples=0
)
MAX_ROLLOUT_TURNS = 200


def load_events(events_path: Path) -> list[dict]:
    with events_path.open() as handle:
        return [json.loads(line) for line in handle]


def reconstruct_decisions(catalog, events: list[dict]):
    """Yield ``(state_before, action, event)`` for every resolved action, in order."""

    run_started = next(e for e in events if e["event_name"] == "simulation_run_started")
    game_started = next(e for e in events if e["event_name"] == "game_started")
    player_count = int(run_started["payload"]["player_count"])
    state = setup_base_game(
        catalog,
        player_ids=[f"player_{i + 1}" for i in range(player_count)],
        random_seed=game_started["random_seed"],
        game_id=game_started["game_id"],
        apply_initial_selection=False,
    )
    for event in events:
        if event["event_name"] != "setup_selection_applied":
            continue
        payload = event["payload"]
        player = next(p for p in state.players if p.player_id == payload["player_id"])
        player.agent_id = payload["agent_id"]
        selection = InitialSelection(
            player_id=player.player_id,
            kept_bird_names=list(payload["kept_bird_names"]),
            kept_bonus_card_names=list(payload["kept_bonus_card_names"]),
            starting_food=[FoodType(food) for food in payload["starting_food"]],
        )
        discarded_birds, discarded_bonus = apply_initial_selection_choice(player, selection)
        state.decks.bird_discard.extend(discarded_birds)
        state.decks.bonus_discard.extend(discarded_bonus)
    for event in events:
        if event["event_name"] != "action_resolved":
            continue
        action = LegalAction.model_validate(event["payload"]["action"])
        yield state, action, event
        state = apply_action(state, action)


def continuation_agents(agent_ids: dict[str, str]) -> dict[str, object]:
    """Cheap policies per player id, matching the archived kinds where cheap."""

    from flows.simulation_batch import _make_agent

    agents = {}
    for player_id, agent_id in agent_ids.items():
        kind = agent_id.removeprefix("guardrailed_").rsplit("_p", 1)[0]
        seat = f"p{player_id.rsplit('_', 1)[1]}"
        try:
            agents[player_id] = _make_agent(
                kind, seat=seat, random_seed=0, potential_points_search=CHEAP_SEARCH
            )
        except ValueError:
            agents[player_id] = _make_agent(
                "potential_points", seat=seat, random_seed=0, potential_points_search=CHEAP_SEARCH
            )
    return agents


def rollout(state: GameState, first_action: LegalAction, agents: dict[str, object]) -> GameState:
    branch = apply_action(state, first_action)
    turns = 0
    while not branch.round_state.game_over and turns < MAX_ROLLOUT_TURNS:
        legal = legal_actions_for_current_player(branch)
        if not legal:
            break
        agent = agents[branch.active_player.player_id]
        apply_action_in_place(branch, agent.select_action(branch, legal))
        turns += 1
    return branch


def rollout_value(
    state: GameState,
    first_action: LegalAction,
    agents: dict[str, object],
    player_id: str,
    samples: int,
) -> tuple[float, GameState]:
    """Mean final score over ``samples`` determinized continuations (0 = the true state).

    Returns the mean and the last end state (for the bird ledger).
    """

    if samples <= 0:
        end = rollout(state, first_action, agents)
        return float(score_player(end, player_id).total), end
    total = 0.0
    end = state
    for sample_index in range(samples):
        sampled = determinize_state(state, player_id, sample_index)
        end = rollout(sampled, first_action, agents)
        total += score_player(end, player_id).total
    return total / samples, end


def bird_ledger(state: GameState, player_id: str, bird_name: str) -> dict | None:
    player = next(p for p in state.players if p.player_id == player_id)
    for habitat in Habitat:
        for slot in player.habitats[habitat]:
            if slot.card.common_name == bird_name:
                return {
                    "eggs": slot.eggs,
                    "cached_food": slot.cached_food,
                    "tucked_cards": slot.tucked_cards,
                    "activations": slot.activations,
                    "power_yield": dict(slot.power_yield),
                }
    return None


def analyse_game(catalog, events_path: Path, study_agent: str, *, samples: int = 0) -> list[dict]:
    events = load_events(events_path)
    agent_ids = {
        e["payload"]["player_id"]: e["payload"]["agent_id"]
        for e in events
        if e["event_name"] == "setup_selection_applied"
    }
    study_players = [
        pid
        for pid, aid in agent_ids.items()
        if aid.removeprefix("guardrailed_").startswith(study_agent)
    ]
    if not study_players:
        return []
    agents = continuation_agents(agent_ids)
    rows = []
    for state, action, event in reconstruct_decisions(catalog, events):
        player_id = event["payload"]["acting_player_id"]
        if player_id not in study_players or action.action_type != ActionType.PLAY_BIRD:
            continue
        legal = legal_actions_for_current_player(state)
        without_bird = [
            a
            for a in legal
            if not (
                a.action_type == ActionType.PLAY_BIRD
                and a.bird_common_name == action.bird_common_name
            )
        ]
        if not without_bird:
            continue
        alternative = agents[player_id].select_action(state, without_bird)
        before_score = score_player(state, player_id).total
        actual_value, actual_end = rollout_value(state, action, agents, player_id, samples)
        not_now_value, _ = rollout_value(state, alternative, agents, player_id, samples)
        never_state = state.model_copy(deep=True)
        never_player = next(p for p in never_state.players if p.player_id == player_id)
        removed = next(c for c in never_player.hand if c.common_name == action.bird_common_name)
        never_player.hand.remove(removed)
        never_state.decks.bird_discard.append(removed)
        never_legal = legal_actions_for_current_player(never_state)
        if never_legal:
            never_value, _ = rollout_value(
                never_state,
                agents[player_id].select_action(never_state, never_legal),
                agents,
                player_id,
                samples,
            )
        else:
            never_value = float(score_player(never_state, player_id).total)
        player = next(p for p in state.players if p.player_id == player_id)
        board = sorted(
            slot.card.common_name for habitat in Habitat for slot in player.habitats[habitat]
        )
        rows.append(
            {
                "game_id": event["game_id"],
                "random_seed": event["random_seed"],
                "player_id": player_id,
                "agent_id": agent_ids[player_id],
                "round": event["round_number"],
                "global_turn": event["global_turn_number"],
                "bird": action.bird_common_name,
                "habitat": action.habitat.value if action.habitat else None,
                "board_before": board,
                "hand_size_before": len(player.hand),
                "food_before": sum(player.food_tokens.values()),
                "immediate_delta": score_player(apply_action(state, action), player_id).total
                - before_score,
                "alternative": render_action(alternative),
                "actual_final": actual_value,
                "not_now_final": not_now_value,
                "never_final": never_value,
                "timing_advantage": actual_value - not_now_value,
                "card_advantage": actual_value - never_value,
                "continuation_samples": samples,
                "ledger_at_end": bird_ledger(actual_end, player_id, action.bird_common_name),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--study-agent", default="potential_points")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    parser.add_argument("--limit", type=int, default=None, help="max games")
    parser.add_argument("--shard", type=int, nargs=2, default=None, metavar=("INDEX", "COUNT"))
    parser.add_argument(
        "--continuation-samples",
        type=int,
        default=0,
        help="determinized continuations per branch; 0 rolls out the true state once",
    )
    args = parser.parse_args(argv)
    catalog = load_base_game_content_catalog(args.workbook)
    paths = sorted(p for root in args.roots for p in root.rglob("events.jsonl"))
    if args.shard is not None:
        paths = paths[args.shard[0] :: args.shard[1]]
    if args.limit is not None:
        paths = paths[: args.limit]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    written = 0
    with args.out.open("w") as out:
        for index, path in enumerate(paths):
            rows = analyse_game(catalog, path, args.study_agent, samples=args.continuation_samples)
            for row in rows:
                out.write(json.dumps(row) + "\n")
            written += len(rows)
            print(
                f"[{index + 1}/{len(paths)}] {path.parts[-4]}/{path.parts[-2]}: {len(rows)} plays "
                f"({time.time() - started:.0f}s elapsed, {written} rows)",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
