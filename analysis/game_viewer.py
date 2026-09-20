"""Step through an archived game decision by decision, from one seat's point of view.

Why this exists
---------------
Aggregate contrasts say whether an agent got better; they do not show a
person who knows the game *where* it plays badly. This walks a game exactly
as it happened (replayed from its events, so every state is the real one)
and at each decision prints what the acting agent could see, what it could
do, how it ranked the options and what it chose — so a strategy it keeps
missing can be spotted by eye and then turned into a registered arm.

What is shown at a decision
---------------------------
- the public board: every player's rows (bird, eggs, cached food, tucked
  cards), food, hand size, cubes; the tray, the feeder dice, the round goals
  with the current standings; running score breakdowns;
- the acting player's private information (their hand with cost, points,
  habitats and power text; their bonus card) — only for the seat whose point
  of view is being followed, unless ``--all-private``;
- the legal actions (count; ``--all-actions`` lists them all);
- the ranking the agent chose from (``search_ranking``, recorded since
  2026-09-18: the search's own root values; older games fall back to the
  evaluator's ``top_alternatives``), the evaluator breakdown of the chosen
  action's resulting position, the opponent belief state, the budget report;
- what the action did: score and resource deltas, RNG draws it triggered.

Usage
-----
    python analysis/game_viewer.py artifacts/rr_belief_opp/.../seed_3   # whole game, PP seat
    python analysis/game_viewer.py <game_dir> --pov player_2             # follow seat 2
    python analysis/game_viewer.py <game_dir> --interactive              # Enter steps, q quits
    python analysis/game_viewer.py <game_dir> --turns 12-20 --all-actions
    python analysis/game_viewer.py <game_dir> --out game.md              # transcript to a file

Scores shown are live: ``score_player`` on the current state, which counts
the current standing on the round in progress as round-goal points (the
same quantity the agent's evaluator sees), so laying two eggs can move the
score by more than two.

``game_dir`` is any directory holding ``events.jsonl``; ``--pov`` defaults
to the first ``potential_points`` seat (or seat 1).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.play_counterfactuals import load_events, reconstruct_decisions  # noqa: E402
from wingspan_ai.content.loader import (  # noqa: E402
    load_base_game_content_catalog,
    resolve_workbook_path,
)
from wingspan_ai.rules.actions import render_action  # noqa: E402
from wingspan_ai.rules.base_game import apply_action, score_player  # noqa: E402
from wingspan_ai.state.models import GameState  # noqa: E402
from wingspan_ai.state.render import board_lines, food_str  # noqa: E402


def decision_lines(summary: dict | None, all_actions: bool, legal_labels: list[str]) -> list[str]:
    lines = []
    if all_actions:
        lines.append(f"  legal actions ({len(legal_labels)}):")
        lines += [f"    - {label}" for label in legal_labels]
    if not summary:
        return lines
    policy = summary.get("policy")
    ranking = summary.get("search_ranking")
    if ranking and ranking.get("top"):
        basis = ranking.get("basis")
        lines.append(f"  ranking ({policy}, basis: {basis}):")
        for row in ranking["top"]:
            mark = "▶" if row.get("chosen") else " "
            lines.append(
                f"    {mark} {row['value']:8.2f}  (tie {row['tie_break']:+.1f})  "
                f"{row['action_label']}"
            )
    elif summary.get("top_alternatives"):
        lines.append(f"  ranking ({policy}, basis: evaluator one-ply):")
        for row in summary["top_alternatives"]:
            label = row.get("action_label") or row.get("action")
            lines.append(
                f"      {row.get('value_delta', 0):8.2f}  "
                f"(realized {row.get('realized_delta', 0):+.1f})  {label}"
            )
    breakdown = summary.get("selected_after_breakdown")
    if breakdown:
        parts = [
            f"{k.replace('_potential', '').replace('_', ' ')} {v:+.1f}"
            for k, v in breakdown.items()
            if isinstance(v, (int, float)) and abs(v) >= 0.05
        ]
        lines.append("  evaluator after chosen action: " + ", ".join(parts))
    if summary.get("endgame_search_used") is not None:
        bits = [
            f"search {'on' if summary.get('endgame_search_used') else 'off'}",
            f"K={summary.get('determinization_samples')}",
            f"opponent model {summary.get('search_opponent_model')}",
        ]
        budget = summary.get("budget")
        if budget:
            bits.append(
                f"budget {budget.get('elapsed_ms', 0):.0f}/{budget.get('budget_ms')} ms, "
                f"depth {budget.get('depth_used')}/{budget.get('full_depth')}, "
                f"samples {budget.get('samples_used')}"
                + (" (cut)" if budget.get("cut_short") else "")
            )
        lines.append("  " + "; ".join(bits))
    model = summary.get("opponent_model")
    if isinstance(model, dict) and model.get("opponent_belief_states"):
        for opp, belief in model["opponent_belief_states"].items():
            lines.append(
                f"  belief about {opp}: {belief.get('most_likely_profile')} "
                f"(obs {belief.get('observation_count')}; "
                + ", ".join(
                    f"{k} {v:.2f}" for k, v in list(belief.get("profile_posterior", {}).items())[:3]
                )
                + ")"
            )
    return lines


def effect_lines(before: GameState, after: GameState, player_id: str, event: dict) -> list[str]:
    b = score_player(before, player_id)
    a = score_player(after, player_id)
    pb = next(p for p in before.players if p.player_id == player_id)
    pa = next(p for p in after.players if p.player_id == player_id)
    food_delta = Counter(pa.food_tokens) - Counter(pb.food_tokens)
    food_lost = Counter(pb.food_tokens) - Counter(pa.food_tokens)
    parts = [f"score {b.total} → {a.total} ({a.total - b.total:+d})"]
    if food_delta or food_lost:
        parts.append(
            "food "
            + (" +" + food_str(food_delta) if food_delta else "")
            + (" −" + food_str(food_lost) if food_lost else "")
        )
    if len(pa.hand) != len(pb.hand):
        parts.append(f"hand {len(pb.hand)} → {len(pa.hand)}")
    eggs_b = sum(s.eggs for row in pb.habitats.values() for s in row)
    eggs_a = sum(s.eggs for row in pa.habitats.values() for s in row)
    if eggs_a != eggs_b:
        parts.append(f"eggs {eggs_b} → {eggs_a}")
    draws = event["payload"].get("rng_draws") or []
    if draws:
        parts.append(
            "rng: " + "; ".join(f"{d.get('draw_type')} → {d.get('result')}" for d in draws[:3])
        )
    return ["  effect: " + "; ".join(parts)]


def view(
    game_dir: Path,
    *,
    pov: str | None,
    turns: tuple[int, int] | None,
    interactive: bool,
    all_actions: bool,
    all_private: bool,
    others: bool,
    out,
) -> int:
    events = load_events(game_dir / "events.jsonl")
    catalog = load_base_game_content_catalog(resolve_workbook_path())
    summaries = {
        e["global_turn_number"]: e for e in events if e["event_name"] == "agent_decision_summary"
    }
    legal = {
        e["global_turn_number"]: e["payload"].get("legal_action_labels", [])
        for e in events
        if e["event_name"] == "legal_actions_generated"
    }
    started = next(e for e in events if e["event_name"] == "game_started")
    setup = [e for e in events if e["event_name"] == "setup_selection_applied"]
    ended = next((e for e in events if e["event_name"] == "game_ended"), None)

    def emit(lines):
        text = "\n".join(lines)
        print(text, file=out)

    emit([f"# Game {started['game_id']} (seed {started['random_seed']})", ""])
    emit(["## Setup"])
    for e in setup:
        p = e["payload"]
        emit(
            [
                f"  {p['player_id']} ({p['agent_id']}, {p.get('setup_policy_id')}): kept "
                f"{', '.join(p['kept_bird_names'])}; food {', '.join(p['starting_food'])}; "
                f"bonus {', '.join(p['kept_bonus_card_names'])}; discarded "
                f"{', '.join(p.get('discarded_bird_names', []))} / "
                f"{', '.join(p.get('discarded_bonus_card_names', []))}"
            ]
        )
    emit([""])

    pov_id = pov
    shown = 0
    for state, action, event in reconstruct_decisions(catalog, events):
        if pov_id is None:
            pov_id = next(
                (
                    p.player_id
                    for p in state.players
                    if str(p.agent_id).startswith("potential_points")
                ),
                state.players[0].player_id,
            )
        turn = event["global_turn_number"]
        if turns and not (turns[0] <= turn <= turns[1]):
            continue
        acting = state.active_player.player_id
        after = apply_action(state, action)
        if acting != pov_id and not others:
            emit(
                [f"--- turn {turn} (R{event['round_number']}): {acting} → {render_action(action)}"]
                + effect_lines(state, after, acting, event)
            )
            continue
        emit(
            [
                "",
                f"=== turn {turn}: round {event['round_number']}, {acting} "
                f"({state.active_player.agent_id}) to act ===",
            ]
        )
        emit(board_lines(state, pov_id, all_private))
        summary = (
            summaries.get(turn, {}).get("payload")
            if summaries.get(turn) and summaries[turn].get("player_id") == acting
            else None
        )
        emit(decision_lines(summary, all_actions, legal.get(turn, [])))
        emit([f"  CHOSE: {render_action(action)}"] + effect_lines(state, after, acting, event))
        shown += 1
        if interactive:
            try:
                answer = input("  [Enter] next, a = all actions, q = quit > ").strip().lower()
            except EOFError:
                answer = "q"
            if answer == "q":
                return 0
            if answer == "a":
                emit(
                    [f"  legal actions ({len(legal.get(turn, []))}):"]
                    + [f"    - {label}" for label in legal.get(turn, [])]
                )
    if ended:
        outcome = ended["payload"].get("outcome") or ended["payload"]
        emit(
            [
                "",
                "## Final",
                f"  scores {outcome.get('scores')}; winners {outcome.get('winners')}",
            ]
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("game_dir", type=Path)
    parser.add_argument(
        "--pov", default=None, help="player id to follow (default: the potential_points seat)"
    )
    parser.add_argument("--turns", default=None, help="global turn range, e.g. 10-20")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument(
        "--all-actions", action="store_true", help="list every legal action at each POV decision"
    )
    parser.add_argument(
        "--all-private", action="store_true", help="show every player's hand and bonus card"
    )
    parser.add_argument(
        "--others", action="store_true", help="show other seats' decisions in full, not one line"
    )
    parser.add_argument("--out", type=Path, default=None, help="write the transcript to a file")
    args = parser.parse_args(argv)
    if not (args.game_dir / "events.jsonl").exists():
        print(f"{args.game_dir} has no events.jsonl")
        return 1
    turns = None
    if args.turns:
        lo, _, hi = args.turns.partition("-")
        turns = (int(lo), int(hi or lo))
    out = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    try:
        return view(
            args.game_dir,
            pov=args.pov,
            turns=turns,
            interactive=args.interactive,
            all_actions=args.all_actions,
            all_private=args.all_private,
            others=args.others,
            out=out,
        )
    finally:
        if args.out:
            out.close()
            print(f"wrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
