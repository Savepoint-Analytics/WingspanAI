"""Static synergy tables: what the deck supplies each bonus card, and what each bird carries.

Two questions Alex added to the bonus-card study on 2026-09-16, answered here
from the content alone before any game is simulated:

1. **Bonus cards.** Are some cards better keeps because the birds that qualify
   for them are inherently good — plentiful in the deck, cheap, high-scoring,
   egg-rich, or carrying strong repeatable powers? For each card this lists
   the qualifying supply and what that supply looks like.
2. **Birds.** Are some birds better picks because they qualify for many bonus
   cards, feed the round goals, or are simply strong for their cost? For each
   bird this lists points, cost, egg capacity, nest, habitats, power, how many
   bonus cards it satisfies, and a cost-efficiency figure.

The simulation study measures realized value; these tables say where that
value could come from, and give the bird-side study its feature set. Bonus
weights for the bird table can be supplied later from the forced-keep result
(``--card-values``: JSON of card name → mean advantage) so a bird's bonus
coverage is weighted by how good those cards actually turned out to be.

    python analysis/card_structure.py --bonus
    python analysis/card_structure.py --birds --top 40
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from wingspan_ai.agents.setup import _opening_power_score
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.schemas import BirdCard, BonusCard, Habitat, PowerColor
from wingspan_ai.rules.bonus_scoring import BOARD_STATE_COUNTERS, normalize_bonus_name

OPENING_HAND = 5


def total_food_cost(card: BirdCard) -> int:
    cost = card.food_cost
    return sum(cost.fixed.values()) + cost.wild_food_count + cost.choice_food_count


def qualifiers(bonus: BonusCard, birds: list[BirdCard]) -> list[BirdCard]:
    name = normalize_bonus_name(bonus.name)
    return [
        bird
        for bird in birds
        if any(normalize_bonus_name(tag) == name for tag in bird.bonus_card_tags)
    ]


def bonus_coverage(birds: list[BirdCard], bonus_cards: list[BonusCard]) -> dict[str, list[str]]:
    """Bird name → the bonus cards it satisfies (card names, normalized)."""

    by_name = {normalize_bonus_name(b.name): b.name for b in bonus_cards}
    coverage: dict[str, list[str]] = defaultdict(list)
    for bird in birds:
        for tag in sorted(bird.bonus_card_tags):
            key = normalize_bonus_name(tag)
            if key in by_name:
                coverage[bird.common_name].append(by_name[key])
    return coverage


def bonus_table(birds: list[BirdCard], bonus_cards: list[BonusCard]) -> str:
    lines = [
        "# Bonus cards: what the deck supplies",
        "",
        f"Deck: {len(birds)} birds. 'Exp. in opening hand' is the expected number of",
        f"qualifying birds among {OPENING_HAND} dealt cards.",
        "",
        "| Card | Scoring | Qualifiers | % deck | Exp. in hand | Mean VP | Mean cost | "
        "Mean eggs | Brown % | Power score | F/G/W |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    rows = []
    for bonus in bonus_cards:
        name = normalize_bonus_name(bonus.name)
        qs = qualifiers(bonus, birds)
        if not qs and name in BOARD_STATE_COUNTERS:
            rows.append(
                (
                    bonus.name,
                    bonus.victory_point_text or "",
                    "board state",
                    None,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    "",
                )
            )
            continue
        share = len(qs) / len(birds) if birds else 0.0
        habitats = Counter(h for bird in qs for h in bird.habitats)
        fgw = "/".join(
            f"{habitats[h] / max(len(qs), 1):.0%}"
            for h in (Habitat.FOREST, Habitat.GRASSLAND, Habitat.WETLAND)
        )
        rows.append(
            (
                bonus.name,
                bonus.victory_point_text or "",
                len(qs),
                share,
                OPENING_HAND * share,
                mean(b.victory_points for b in qs) if qs else 0.0,
                mean(total_food_cost(b) for b in qs) if qs else 0.0,
                mean(b.egg_limit for b in qs) if qs else 0.0,
                (sum(1 for b in qs if b.power.color == PowerColor.BROWN) / len(qs)) if qs else 0.0,
                mean(_opening_power_score(b) for b in qs) if qs else 0.0,
                fgw,
            )
        )
    rows.sort(key=lambda r: -(r[3] or 0))
    for r in rows:
        if r[2] == "board state":
            lines.append(f"| {r[0]} | {r[1]} | board state | — | — | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:.0%} | {r[4]:.2f} | {r[5]:.2f} | {r[6]:.2f} | "
            f"{r[7]:.2f} | {r[8]:.0%} | {r[9]:.2f} | {r[10]} |"
        )
    lines += [
        "",
        "Four cards score from board state (eggs on birds, hand size, fewest-habitat",
        "count) and have no qualifying birds by construction.",
    ]
    return "\n".join(lines) + "\n"


def bird_table(
    birds: list[BirdCard],
    bonus_cards: list[BonusCard],
    *,
    top: int | None,
    card_values: dict[str, float] | None,
) -> str:
    coverage = bonus_coverage(birds, bonus_cards)
    lines = [
        "# Birds: what each card carries",
        "",
        "'Efficiency' is (VP + 0.5 × egg capacity + power score) per food token, a",
        "cost-adjusted view of the card alone. 'Bonus cards' counts the cards it",
        "satisfies; 'Weighted' sums those cards' measured keep advantage when",
        "``--card-values`` is given, otherwise it is blank.",
        "",
        "| Bird | VP | Cost | Eggs | Nest | Habitats | Power | Power score | "
        "Bonus cards | Weighted | Efficiency |",
        "|---|---:|---:|---:|---|---|---|---:|---:|---:|---:|",
    ]
    rows = []
    for bird in birds:
        cost = total_food_cost(bird)
        power_score = _opening_power_score(bird)
        efficiency = (bird.victory_points + 0.5 * bird.egg_limit + power_score) / max(cost, 1)
        covered = coverage.get(bird.common_name, [])
        weighted = sum(card_values.get(name, 0.0) for name in covered) if card_values else None
        rows.append((bird, cost, power_score, covered, weighted, efficiency))
    rows.sort(key=lambda r: -r[5])
    if top is not None:
        rows = rows[:top]
    for bird, cost, power_score, covered, weighted, efficiency in rows:
        habitats = "".join(
            h.value[0].upper()
            for h in (Habitat.FOREST, Habitat.GRASSLAND, Habitat.WETLAND)
            if h in bird.habitats
        )
        lines.append(
            f"| {bird.common_name} | {bird.victory_points} | {cost} | {bird.egg_limit} | "
            f"{bird.nest_type.value if bird.nest_type else '—'} | {habitats} | "
            f"{bird.power.color.value} | {power_score:.1f} | {len(covered)} | "
            f"{'' if weighted is None else f'{weighted:+.1f}'} | {efficiency:.2f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--bonus", action="store_true", help="bonus-card supply table")
    parser.add_argument("--birds", action="store_true", help="per-bird table")
    parser.add_argument("--top", type=int, default=None, help="limit the bird table")
    parser.add_argument("--card-values", type=Path, default=None)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    args = parser.parse_args(argv)
    if not (args.bonus or args.birds):
        args.bonus = args.birds = True
    catalog = load_base_game_content_catalog(args.workbook)
    if args.bonus:
        print(bonus_table(catalog.birds, catalog.bonus_cards))
    if args.birds:
        values = json.loads(args.card_values.read_text()) if args.card_values is not None else None
        print(bird_table(catalog.birds, catalog.bonus_cards, top=args.top, card_values=values))
    return 0


if __name__ == "__main__":
    sys.exit(main())
