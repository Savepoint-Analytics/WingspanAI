"""Coverage audit helpers for bonus-card and round-goal scoring."""

from __future__ import annotations

from dataclasses import dataclass

from wingspan_ai.content.schemas import BonusCard, ContentCatalog, RoundGoal

CORE_RULEBOOK = "rulebook_pdfs/WS_Core_Rulebook.pdf"

SUPPORTED_BASE_BONUS_NAMES = {
    "Anatomist",
    "Backyard Birder",
    "Bird Counter",
    "Bird Feeder",
    "Breeding Manager",
    "Cartographer",
    "Ecologist",
    "Enclosure Builder",
    "Falconer",
    "Fishery Manager",
    "Food Web Expert",
    "Forester",
    "Historian",
    "Large Bird Specialist",
    "Nest Box Builder",
    "Omnivore Expert",
    "Oologist",
    "Passerine Specialist",
    "Photographer",
    "Platform Builder",
    "Prairie Manager",
    "Rodentologist",
    "Visionary Leader",
    "Viticulturalist",
    "Wetland Scientist",
    "Wildlife Gardener",
}

SCORING_SOURCE_REFERENCES: dict[str, dict[str, str | int | None]] = {
    "bonus_cards": {
        "rulebook": CORE_RULEBOOK,
        "page": 11,
        "section": "Bonus cards and end-of-game scoring",
    },
    "round_goals": {
        "rulebook": CORE_RULEBOOK,
        "page": 11,
        "section": "End-of-round goals",
    },
}


@dataclass(frozen=True)
class ScoringAuditResult:
    """Summary of current scoring handler coverage."""

    supported_bonus_cards: list[str]
    unsupported_bonus_cards: list[str]
    supported_round_goals: list[str]
    unsupported_round_goals: list[str]
    source_references: dict[str, dict[str, str | int | None]]

    @property
    def bonus_card_coverage(self) -> float:
        total = len(self.supported_bonus_cards) + len(self.unsupported_bonus_cards)
        return len(self.supported_bonus_cards) / total if total else 1.0

    @property
    def round_goal_coverage(self) -> float:
        total = len(self.supported_round_goals) + len(self.unsupported_round_goals)
        return len(self.supported_round_goals) / total if total else 1.0


def audit_scoring_coverage(catalog: ContentCatalog) -> ScoringAuditResult:
    """Audit scoring handler coverage for the provided content catalog."""

    supported_bonus_cards: list[str] = []
    unsupported_bonus_cards: list[str] = []
    for bonus_card in catalog.bonus_cards:
        normalized_name = _normalize_bonus_name(bonus_card)
        if normalized_name in SUPPORTED_BASE_BONUS_NAMES:
            supported_bonus_cards.append(bonus_card.name)
        else:
            unsupported_bonus_cards.append(bonus_card.name)

    supported_round_goals: list[str] = []
    unsupported_round_goals: list[str] = []
    for round_goal in catalog.round_goals:
        if _is_supported_round_goal(round_goal):
            supported_round_goals.append(round_goal.name)
        else:
            unsupported_round_goals.append(round_goal.name)

    return ScoringAuditResult(
        supported_bonus_cards=sorted(supported_bonus_cards),
        unsupported_bonus_cards=sorted(unsupported_bonus_cards),
        supported_round_goals=sorted(supported_round_goals),
        unsupported_round_goals=sorted(unsupported_round_goals),
        source_references=SCORING_SOURCE_REFERENCES,
    )


def _normalize_bonus_name(bonus_card: BonusCard) -> str:
    return bonus_card.name.split("[", maxsplit=1)[0].strip()


def _is_supported_round_goal(round_goal: RoundGoal) -> bool:
    goal_name = round_goal.name.lower()
    if not round_goal.scoring_values:
        return False
    supported_tokens = (
        "[bird]",
        "[egg]",
        "[forest]",
        "[grassland]",
        "[wetland]",
        "[bowl]",
        "[cavity]",
        "[ground]",
        "[platform]",
        "sets of",
        "total [bird]",
    )
    return any(token in goal_name for token in supported_tokens)
