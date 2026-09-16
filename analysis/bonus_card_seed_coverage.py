"""Pick seeds so every bonus card is dealt to the study seat about equally often.

The forced-keep study runs each seed twice, once per dealt bonus card, so a
seed contributes one paired unit to each of the two cards it deals. Left to
chance, 26 cards over a modest seed range come out badly unbalanced (the deck
is shuffled per seed; some cards land in the top two far more often than
others in any short range). Setup is cheap — a few milliseconds — so instead
of running whatever seeds 1–N deal, scan a wide range and choose the seeds
that bring every card up to a target count with the fewest games.

The dealt pair for the study seat depends on the seed alone (ADR 0003), not
on the lineup or opponent, so the selection transfers to any roster as long
as the study agent sits in ``player_1`` (seat rotation 0).

    python analysis/bonus_card_seed_coverage.py --target 8 --scan 1 600 \
        --out artifacts/bonus_keep/seeds.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.rules.base_game import setup_base_game

STUDY_PLAYER = "player_1"


def dealt_pairs(catalog, seeds: range, *, player_count: int = 2) -> dict[int, tuple[str, ...]]:
    player_ids = [f"player_{index + 1}" for index in range(player_count)]
    pairs: dict[int, tuple[str, ...]] = {}
    for seed in seeds:
        state = setup_base_game(
            catalog, player_ids=player_ids, random_seed=seed, apply_initial_selection=False
        )
        player = next(p for p in state.players if p.player_id == STUDY_PLAYER)
        pairs[seed] = tuple(card.name for card in player.bonus_cards)
    return pairs


def choose_seeds(
    pairs: dict[int, tuple[str, ...]], card_names: list[str], target: int
) -> tuple[list[int], Counter]:
    """Greedy cover: repeatedly take the seed that helps the most under-target cards.

    Ties go to the lower seed, so the choice is reproducible. Stops when every
    card has reached ``target`` or no remaining seed helps.
    """

    coverage: Counter = Counter({name: 0 for name in card_names})
    remaining = dict(pairs)
    chosen: list[int] = []
    while any(coverage[name] < target for name in card_names) and remaining:
        best_seed, best_gain = None, 0
        for seed in sorted(remaining):
            gain = sum(1 for name in remaining[seed] if coverage[name] < target)
            if gain > best_gain:
                best_seed, best_gain = seed, gain
        if best_seed is None:
            break
        chosen.append(best_seed)
        for name in remaining.pop(best_seed):
            coverage[name] += 1
    return chosen, coverage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--target", type=int, default=8, help="paired units per card")
    parser.add_argument("--scan", type=int, nargs=2, default=(1, 600), metavar=("LOW", "HIGH"))
    parser.add_argument("--player-count", type=int, default=2)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    catalog = load_base_game_content_catalog(args.workbook)
    card_names = sorted(card.name for card in catalog.bonus_cards)
    pairs = dealt_pairs(
        catalog, range(args.scan[0], args.scan[1] + 1), player_count=args.player_count
    )
    natural = Counter(name for pair in pairs.values() for name in pair)
    chosen, coverage = choose_seeds(pairs, card_names, args.target)

    print(f"scanned seeds {args.scan[0]}-{args.scan[1]}: {len(pairs)} deals")
    print(
        f"natural coverage per card over the scan: min {min(natural[n] for n in card_names)}, "
        f"max {max(natural[n] for n in card_names)}"
    )
    print(f"chosen {len(chosen)} seeds for target {args.target} per card")
    print("| Card | units | seeds |")
    print("|---|---:|---|")
    for name in card_names:
        seeds_for = [seed for seed in chosen if name in pairs[seed]]
        print(f"| {name} | {coverage[name]} | {', '.join(map(str, seeds_for))} |")
    short = [name for name in card_names if coverage[name] < args.target]
    if short:
        print(f"\nBelow target: {short} — widen --scan.")

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "target_per_card": args.target,
                    "scan": list(args.scan),
                    "player_count": args.player_count,
                    "study_player": STUDY_PLAYER,
                    "seeds": chosen,
                    "dealt_pairs": {str(seed): list(pairs[seed]) for seed in chosen},
                    "coverage": {name: coverage[name] for name in card_names},
                },
                indent=2,
            )
            + "\n"
        )
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
