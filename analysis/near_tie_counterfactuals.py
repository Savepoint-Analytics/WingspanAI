"""Near-tie counterfactuals: where the evaluator is wrong when it feels indifferent.

The design
----------
``play_counterfactuals.py`` asks what a *bird play* was worth. This asks a
sharper question that needs far less compute per unit of evidence.

At every decision the searching agent records its own ranked valuation of the
candidates (``agent_decision_summary.search_ranking.top``). When the top two
differ by a hair, the agent is **indifferent** and which one won was decided by
noise in its own estimate. Those decisions are naturally occurring randomised
trials: measured over the archive, **33% of ranked champion decisions have a
top-two margin within 0.2 points**, and the median margin is 0.47.

For each such decision we rebuild the state, roll the chosen action and the
runner-up out to the end of the game under identical continuations and identical
determinized worlds, and record ``realized_delta = chosen - runner_up``.

Reading the sign, precisely:

- **> 0** -- the agent's preference *among options it calls a tie* still carries
  real signal. Its tie-breaking is better than a coin flip, and the margin it
  reports understates what it knows.
- **= 0** -- genuine indifference. The evaluator has extracted what there is to
  extract at this margin, and nothing is on the table.
- **< 0** -- the tie-breaking is actively harmful: among near-ties the agent
  systematically takes the worse branch.

The **by-pair** table is where the actionable finding lives. A significant
non-zero delta for one tied action-type pair (say ``play_bird`` chosen over
``lay_eggs``) while others sit at zero means the evaluator mis-prices that
tradeoff specifically at the margin -- a tunable bias, unlike a win rate.

Reading the output honestly
---------------------------
Three limits belong on every claim from this instrument:

1. **The continuation defines the value.** Both branches are played out by the
   same cheap policy, so a number here means "worth this much to a competent
   non-searching continuation", not "worth this much under optimal play". A
   deeper continuation can reverse a small effect.
2. **Selection on the state distribution.** The decisions available are the ones
   this agent reached by its own earlier choices. Near-tie filtering removes the
   agent's *preference* from which branch was taken; it does not make the states
   themselves representative of Wingspan.
3. **Indifference is measured with the same evaluator being tested.** If the
   evaluator is blind to a feature, it will also be blind to it when deciding
   two options are close, so near-ties are not a uniform sample of close
   decisions. This biases toward finding *less* than the true error, not more.

Usage
-----
    python analysis/near_tie_counterfactuals.py artifacts/rr_goal_placement \\
        --epsilon 0.2 --continuation-samples 2 \\
        --out artifacts/near_ties/rr_goal_placement.jsonl
    python analysis/near_tie_counterfactuals.py --report artifacts/near_ties/*.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.arm_contrast import student_t_two_sided_p  # noqa: E402
from analysis.play_counterfactuals import (  # noqa: E402
    continuation_agents,
    load_events,
    reconstruct_decisions,
    rollout_value,
)
from wingspan_ai.content.loader import (  # noqa: E402
    DEFAULT_WORKBOOK_PATH,
    load_base_game_content_catalog,
)
from wingspan_ai.rules.actions import render_action  # noqa: E402
from wingspan_ai.rules.base_game import (  # noqa: E402
    legal_actions_for_current_player,
)
from wingspan_ai.simulation.replay import state_hash  # noqa: E402


#: Alignment key between ``action_resolved`` and ``agent_decision_summary``.
def decision_key(event: dict) -> tuple:
    return (
        event.get("player_id"),
        event.get("round_number"),
        event.get("round_action_number"),
        event.get("global_turn_number"),
    )


def rankings_by_decision(events: list[dict], policy: str) -> dict[tuple, dict]:
    """``{alignment key: search_ranking}`` for one policy's ranked decisions."""

    out: dict[tuple, dict] = {}
    for event in events:
        if event.get("event_name") != "agent_decision_summary":
            continue
        payload = event.get("payload") or {}
        if payload.get("policy") != policy:
            continue
        ranking = payload.get("search_ranking") or {}
        top = ranking.get("top") or []
        if len(top) >= 2:
            out[decision_key(event)] = ranking
    return out


def near_tie(ranking: dict, epsilon: float) -> tuple[dict, dict] | None:
    """``(chosen, runner_up)`` when the top two are within ``epsilon``.

    The ranking is already sorted, but the chosen entry is flagged rather than
    assumed first: the agent breaks ties on a secondary key and an action
    priority, so the top-valued entry is not always the one taken.
    """

    top = ranking["top"]
    chosen = next((entry for entry in top if entry.get("chosen")), None)
    if chosen is None:
        return None
    others = [entry for entry in top if entry is not chosen]
    if not others:
        return None
    runner_up = max(others, key=lambda entry: entry["value"])
    if abs(chosen["value"] - runner_up["value"]) > epsilon:
        return None
    return chosen, runner_up


def analyse_game(
    catalog,
    events_path: Path,
    *,
    policy: str,
    epsilon: float,
    samples: int,
) -> list[dict]:
    events = load_events(events_path)
    agent_ids = {
        event["payload"]["player_id"]: event["payload"]["agent_id"]
        for event in events
        if event["event_name"] == "setup_selection_applied"
    }
    rankings = rankings_by_decision(events, policy)
    if not rankings:
        return []
    agents = continuation_agents(agent_ids)
    rows: list[dict] = []
    for state, _action, event in reconstruct_decisions(catalog, events):
        ranking = rankings.get(decision_key(event))
        if ranking is None:
            continue
        pair = near_tie(ranking, epsilon)
        if pair is None:
            continue
        chosen_entry, runner_entry = pair
        player_id = event["payload"]["acting_player_id"]
        # The reconstruction must be standing exactly where the log says, or the
        # branch values describe a different game.
        expected = event["payload"].get("state_hash_before")
        if expected and state_hash(state) != expected:
            continue
        legal = legal_actions_for_current_player(state)
        by_label = {render_action(candidate): candidate for candidate in legal}
        chosen_action = by_label.get(chosen_entry["action_label"])
        runner_action = by_label.get(runner_entry["action_label"])
        if chosen_action is None or runner_action is None or chosen_action == runner_action:
            continue
        # Same state, same sample indices, so the two branches see identical
        # determinized worlds and the difference is paired.
        chosen_value, _ = rollout_value(state, chosen_action, agents, player_id, samples)
        runner_value, _ = rollout_value(state, runner_action, agents, player_id, samples)
        player = next(p for p in state.players if p.player_id == player_id)
        rows.append(
            {
                "game_id": event.get("game_id"),
                "random_seed": event.get("random_seed"),
                "player_id": player_id,
                "agent_id": agent_ids.get(player_id),
                "round": event.get("round_number"),
                "global_turn": event.get("global_turn_number"),
                "basis": ranking.get("basis"),
                "legal_action_count": len(legal),
                "chosen_type": chosen_entry["action_type"],
                "runner_up_type": runner_entry["action_type"],
                "chosen_label": chosen_entry["action_label"],
                "runner_up_label": runner_entry["action_label"],
                "predicted_margin": round(chosen_entry["value"] - runner_entry["value"], 4),
                "chosen_final": chosen_value,
                "runner_up_final": runner_value,
                "realized_delta": chosen_value - runner_value,
                "hand_size_before": len(player.hand),
                "food_before": sum(player.food_tokens.values()),
                "continuation_samples": samples,
            }
        )
    return rows


def report(paths: list[Path], min_rows: int = 20) -> None:
    rows: list[dict] = []
    for path in paths:
        with path.open() as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    if not rows:
        print("no rows")
        return
    deltas = [row["realized_delta"] for row in rows]
    print(f"# Near-tie counterfactuals\n\n- decisions: **{len(rows):,}**")
    print(f"- games: {len({row['game_id'] for row in rows}):,}")
    print(f"- mean |predicted margin|: {mean(abs(r['predicted_margin']) for r in rows):.3f}")
    overall, p = paired(deltas)
    print(
        f"- **overall realized delta: {overall:+.3f} (p={p:.3f})** — above zero means the"
        " agent's tie-breaking still carries signal; zero means genuine indifference;"
        " below zero means it takes the worse branch\n"
    )

    print("## By tied action-type pair\n")
    print("| chosen | runner-up | n | realized Δ | p | 95% CI |")
    print("|---|---|---:|---:|---:|---|")
    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        groups[(row["chosen_type"], row["runner_up_type"])].append(row["realized_delta"])
    for (chosen, runner), values in sorted(
        groups.items(), key=lambda item: -len(item[1])
    ):
        if len(values) < min_rows:
            continue
        delta, pv = paired(values)
        half = 1.96 * stdev(values) / len(values) ** 0.5 if len(values) > 1 else 0.0
        print(
            f"| `{chosen}` | `{runner}` | {len(values):,} | {delta:+.3f} | {pv:.3f} "
            f"| [{delta - half:+.2f}, {delta + half:+.2f}] |"
        )
    print(f"\n_pairs with fewer than {min_rows} decisions omitted_")

    print("\n## By round\n")
    print("| round | n | realized Δ | p |")
    print("|---|---:|---:|---:|")
    by_round: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        by_round[int(row["round"] or 0)].append(row["realized_delta"])
    for round_number, values in sorted(by_round.items()):
        delta, pv = paired(values)
        print(f"| {round_number} | {len(values):,} | {delta:+.3f} | {pv:.3f} |")


def paired(values: list[float]) -> tuple[float, float]:
    """Mean and two-sided p against zero, by the exact t."""

    if len(values) < 2:
        return (values[0] if values else 0.0), 1.0
    spread = stdev(values)
    if spread == 0:
        return mean(values), 1.0
    t = mean(values) / (spread / len(values) ** 0.5)
    return mean(values), student_t_two_sided_p(t, len(values) - 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument(
        "--report", action="store_true", help="roots are jsonl outputs to summarize"
    )
    parser.add_argument("--policy", default="potential_points")
    parser.add_argument(
        "--epsilon", type=float, default=0.2, help="top-two margin that counts as a tie"
    )
    parser.add_argument("--continuation-samples", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None, help="max games")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    args = parser.parse_args(argv)

    if args.report:
        # The shell expands globs, so these are normally literal paths already.
        # Only fall back to globbing for a pattern that reached us unexpanded.
        expanded: list[Path] = []
        for root in args.roots:
            if root.exists():
                expanded.append(root)
            else:
                expanded.extend(sorted(Path(root.anchor or ".").glob(
                    str(root.relative_to(root.anchor)) if root.anchor else str(root)
                )))
        if not expanded:
            print("no such output files")
            return 1
        report(expanded)
        return 0
    if args.out is None:
        parser.error("--out is required unless --report is passed")

    catalog = load_base_game_content_catalog(args.workbook)
    paths = sorted({path for root in args.roots for path in root.rglob("events.jsonl")})
    if args.limit:
        paths = paths[: args.limit]
    print(f"{len(paths):,} games; policy={args.policy} epsilon={args.epsilon} "
          f"samples={args.continuation_samples}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with args.out.open("w") as handle:
        for index, path in enumerate(paths, start=1):
            try:
                rows = analyse_game(
                    catalog,
                    path,
                    policy=args.policy,
                    epsilon=args.epsilon,
                    samples=args.continuation_samples,
                )
            except Exception as error:
                print(f"  skipped {path}: {type(error).__name__}: {error}", flush=True)
                continue
            for row in rows:
                handle.write(json.dumps(row) + "\n")
            written += len(rows)
            if index % 20 == 0:
                print(f"  {index:,}/{len(paths):,} games, {written:,} near-ties", flush=True)
    print(f"done: {written:,} near-tie decisions -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
