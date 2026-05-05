"""Workbook loader for normalized Wingspan content models."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from wingspan_ai.content.schemas import (
    BeakDirection,
    BirdCard,
    BonusCard,
    ContentCatalog,
    ContentPack,
    FoodCost,
    FoodType,
    Habitat,
    NestType,
    Power,
    PowerColor,
    PowerImplementationStatus,
    RoundGoal,
    RulesetMetadata,
    RulesModule,
)
from wingspan_ai.content.workbook_audit import SET_TO_CONTENT_PACK, is_blank, read_sheet_rows

BASE_FOOD_TYPES = (
    FoodType.INVERTEBRATE,
    FoodType.SEED,
    FoodType.FISH,
    FoodType.FRUIT,
    FoodType.RODENT,
)

FOOD_COLUMNS = {
    "Invertebrate": FoodType.INVERTEBRATE,
    "Seed": FoodType.SEED,
    "Fish": FoodType.FISH,
    "Fruit": FoodType.FRUIT,
    "Rodent": FoodType.RODENT,
    "Nectar": FoodType.NECTAR,
}

HABITAT_COLUMNS = {
    "Forest": Habitat.FOREST,
    "Grassland": Habitat.GRASSLAND,
    "Wetland": Habitat.WETLAND,
}

BEAK_DIRECTION_MAP = {
    "L": BeakDirection.LEFT,
    "R": BeakDirection.RIGHT,
    "N": BeakDirection.NONE,
    "LR": BeakDirection.LEFT_RIGHT,
    "LL": BeakDirection.LEFT_LEFT,
}

DEFAULT_WORKBOOK_PATH = Path("data/raw/wingspan-card-list.xlsx")


@dataclass(frozen=True)
class ContentLoadIssue:
    """A row-level issue found while translating workbook rows."""

    sheet: str
    row_number: int | None
    field: str
    message: str
    value: Any = None

    def format(self) -> str:
        row = f" row {self.row_number}" if self.row_number is not None else ""
        value = f" value={self.value!r}" if self.value is not None else ""
        return f"{self.sheet}{row} [{self.field}]: {self.message}{value}"


class ContentLoadError(ValueError):
    """Raised when workbook content cannot be loaded into typed models."""

    def __init__(self, issues: list[ContentLoadIssue]) -> None:
        self.issues = issues
        issue_preview = "\n".join(f"- {issue.format()}" for issue in issues[:20])
        remaining = "" if len(issues) <= 20 else f"\n...and {len(issues) - 20} more issue(s)"
        super().__init__(f"Content workbook failed validation:\n{issue_preview}{remaining}")


def load_content_catalog(
    workbook_path: str | Path | None = None,
    *,
    content_packs: set[ContentPack] | None = None,
    include_default_ruleset: bool = True,
) -> ContentCatalog:
    """Load the card workbook into typed content models.

    Args:
        workbook_path: Source workbook path.
        content_packs: Optional pack filter. When omitted, all known packs are loaded.
        include_default_ruleset: Include a ruleset matching the requested content packs.
    """

    path = resolve_workbook_path(workbook_path)
    issues: list[ContentLoadIssue] = []
    birds = _load_birds(path, content_packs, issues)
    bonus_cards = _load_bonus_cards(path, content_packs, issues)
    round_goals = _load_round_goals(path, content_packs, issues)

    if issues:
        raise ContentLoadError(issues)

    rulesets: list[RulesetMetadata] = []
    if include_default_ruleset:
        loaded_packs = sorted(
            {card.content_pack for card in birds}
            | {pack for bonus in bonus_cards for pack in bonus.content_packs}
            | {goal.content_pack for goal in round_goals},
            key=lambda pack: pack.value,
        )
        rulesets.append(
            RulesetMetadata(
                ruleset_id=_default_ruleset_id(loaded_packs),
                content_packs=loaded_packs,
                rules_modules=[RulesModule.BASE_GAME],
                player_count=2,
            )
        )

    return ContentCatalog(
        birds=birds,
        bonus_cards=bonus_cards,
        round_goals=round_goals,
        rulesets=rulesets,
    )


def load_base_game_content_catalog(
    workbook_path: str | Path | None = None,
) -> ContentCatalog:
    """Load only core/base-game content from the source workbook."""

    return load_content_catalog(workbook_path, content_packs={ContentPack.CORE})


def resolve_workbook_path(workbook_path: str | Path | None = None) -> Path:
    """Resolve the workbook from an explicit path, env var, or project default."""

    if workbook_path is not None:
        return Path(workbook_path)
    env_path = os.environ.get("WINGSPAN_CARD_WORKBOOK")
    if env_path:
        return Path(env_path)
    return DEFAULT_WORKBOOK_PATH


def _load_birds(
    path: Path,
    content_packs: set[ContentPack] | None,
    issues: list[ContentLoadIssue],
) -> list[BirdCard]:
    _, rows = read_sheet_rows(path, "Birds")
    birds: list[BirdCard] = []

    for row in rows:
        row_number = _row_number(row)
        content_pack = _parse_single_content_pack(row, "Birds", "Set", issues)
        if content_pack is None or _should_skip_pack({content_pack}, content_packs):
            continue

        card = _build_model(
            BirdCard,
            sheet="Birds",
            row_number=row_number,
            issues=issues,
            common_name=row.get("Common name"),
            scientific_name=row.get("Scientific name"),
            content_pack=content_pack,
            habitats=_parse_habitats(row),
            food_cost=_parse_food_cost(row),
            victory_points=_parse_int(row.get("Victory points"), default=0),
            nest_type=_parse_nest_type(row.get("Nest type")),
            egg_limit=_parse_int(row.get("Egg limit"), default=0),
            wingspan_cm=_parse_wingspan_cm(row.get("Wingspan")),
            wingspan_is_variable=_is_variable_wingspan(row.get("Wingspan")),
            power=_parse_power(row),
            predator=_is_marked(row.get("Predator")),
            flocking=_is_marked(row.get("Flocking")),
            bonus_card_power=_is_marked(row.get("Bonus card")),
            beak_direction=_parse_beak_direction(row.get("Beak direction")),
            automa_banned=_is_marked(row.get("Automa ban")),
            swift_start=_is_marked(row.get("Swift Start")),
            geography=_parse_geography(row),
            bonus_card_tags=_parse_bonus_card_tags(row),
            source_row=row_number,
        )
        if card is not None:
            birds.append(card)

    return birds


def _load_bonus_cards(
    path: Path,
    content_packs: set[ContentPack] | None,
    issues: list[ContentLoadIssue],
) -> list[BonusCard]:
    _, rows = read_sheet_rows(path, "Bonus")
    bonus_cards: list[BonusCard] = []

    for row in rows:
        row_number = _row_number(row)
        packs = _parse_content_pack_set(row, "Bonus", "Set", issues)
        if not packs or _should_skip_pack(packs, content_packs):
            continue

        filtered_packs = packs if content_packs is None else packs & content_packs
        bonus_card = _build_model(
            BonusCard,
            sheet="Bonus",
            row_number=row_number,
            issues=issues,
            name=row.get("Bonus card"),
            content_packs=filtered_packs,
            condition=row.get("Condition"),
            victory_point_text=row.get("VP"),
            automa_compatible=_is_marked(row.get("Automa")),
            explanatory_text=row.get("Explanatory text"),
            prevalence_percent=_parse_percent(row.get("%")),
            implementation_status=PowerImplementationStatus.NOT_IMPLEMENTED,
            source_row=row_number,
        )
        if bonus_card is not None:
            bonus_cards.append(bonus_card)

    return bonus_cards


def _load_round_goals(
    path: Path,
    content_packs: set[ContentPack] | None,
    issues: list[ContentLoadIssue],
) -> list[RoundGoal]:
    _, rows = read_sheet_rows(path, "Goals")
    round_goals: list[RoundGoal] = []

    for row in rows:
        row_number = _row_number(row)
        content_pack = _parse_single_content_pack(row, "Goals", "Set", issues)
        if content_pack is None or _should_skip_pack({content_pack}, content_packs):
            continue

        scoring_values = _parse_round_goal_scoring_values(row)
        goal = _build_model(
            RoundGoal,
            sheet="Goals",
            row_number=row_number,
            issues=issues,
            name=row.get("Goal"),
            content_pack=content_pack,
            scoring_values=scoring_values,
            reverse_goal_name=row.get("Reverse"),
            rules_module=RulesModule.BASE_GAME,
            implementation_status=PowerImplementationStatus.NOT_IMPLEMENTED,
            source_row=row_number,
        )
        if goal is not None:
            round_goals.append(goal)

    return round_goals


def _build_model(
    model_cls: type[Any],
    *,
    sheet: str,
    row_number: int | None,
    issues: list[ContentLoadIssue],
    **data: Any,
) -> Any | None:
    try:
        return model_cls(**data)
    except ValidationError as error:
        for validation_error in error.errors():
            field = ".".join(str(part) for part in validation_error["loc"])
            issues.append(
                ContentLoadIssue(
                    sheet=sheet,
                    row_number=row_number,
                    field=field,
                    message=str(validation_error["msg"]),
                    value=validation_error.get("input"),
                )
            )
        return None


def _parse_single_content_pack(
    row: dict[Any, Any],
    sheet: str,
    field: str,
    issues: list[ContentLoadIssue],
) -> ContentPack | None:
    packs = _parse_content_pack_set(row, sheet, field, issues)
    if not packs:
        return None
    if len(packs) > 1:
        issues.append(
            ContentLoadIssue(
                sheet=sheet,
                row_number=_row_number(row),
                field=field,
                message="expected one content pack for this sheet",
                value=row.get(field),
            )
        )
        return None
    return next(iter(packs))


def _parse_content_pack_set(
    row: dict[Any, Any],
    sheet: str,
    field: str,
    issues: list[ContentLoadIssue],
) -> set[ContentPack]:
    raw_value = row.get(field)
    if is_blank(raw_value):
        issues.append(
            ContentLoadIssue(
                sheet=sheet,
                row_number=_row_number(row),
                field=field,
                message="missing content pack",
            )
        )
        return set()

    packs: set[ContentPack] = set()
    for raw_pack in str(raw_value).split(","):
        cleaned = raw_pack.strip()
        content_pack = SET_TO_CONTENT_PACK.get(cleaned)
        if content_pack is None:
            issues.append(
                ContentLoadIssue(
                    sheet=sheet,
                    row_number=_row_number(row),
                    field=field,
                    message="unknown content pack",
                    value=cleaned,
                )
            )
        else:
            packs.add(content_pack)
    return packs


def _parse_habitats(row: dict[Any, Any]) -> set[Habitat]:
    return {habitat for column, habitat in HABITAT_COLUMNS.items() if _is_marked(row.get(column))}


def _parse_food_cost(row: dict[Any, Any]) -> FoodCost:
    fixed = {
        food_type: count
        for column, food_type in FOOD_COLUMNS.items()
        if (count := _parse_count(row.get(column))) > 0
    }
    return FoodCost(
        fixed=fixed,
        wild_food_count=_parse_count(row.get("Wild (food)")),
        choice_food_count=_parse_count(row.get("/ (food cost)")),
        variable_food=_is_marked(row.get("* (food cost)")),
    )


def _parse_power(row: dict[Any, Any]) -> Power:
    raw_color = row.get("Color")
    raw_text = row.get("Power text")
    color = PowerColor.NONE if is_blank(raw_color) else PowerColor(str(raw_color).strip().lower())
    status = (
        PowerImplementationStatus.NO_OP_FOR_V1
        if color == PowerColor.NONE and is_blank(raw_text)
        else PowerImplementationStatus.NOT_IMPLEMENTED
    )
    return Power(
        color=color,
        text=None if is_blank(raw_text) else str(raw_text),
        implementation_status=status,
    )


def _parse_nest_type(value: Any) -> NestType | None:
    if is_blank(value):
        return None
    return NestType(str(value).strip().lower())


def _parse_beak_direction(value: Any) -> BeakDirection | None:
    if is_blank(value):
        return None
    return BEAK_DIRECTION_MAP.get(str(value).strip(), BeakDirection.UNKNOWN)


def _parse_wingspan_cm(value: Any) -> int | None:
    if is_blank(value) or _is_variable_wingspan(value):
        return None
    return _parse_int(value, default=0)


def _is_variable_wingspan(value: Any) -> bool:
    return isinstance(value, str) and value.strip() == "*"


def _parse_geography(row: dict[Any, Any]) -> set[str]:
    columns = (
        "North America",
        "Central America",
        "South America",
        "Europe",
        "Asia",
        "Africa",
        "Oceania",
    )
    return {column for column in columns if _is_marked(row.get(column))}


def _parse_bonus_card_tags(row: dict[Any, Any]) -> set[str]:
    source_columns = [
        column
        for column in row
        if isinstance(column, str)
        and column not in {"__row_number__", "Bonus card"}
        and column
        in {
            "Anatomist",
            "Cartographer",
            "Historian",
            "Photographer",
            "Backyard Birder",
            "Bird Bander",
            "Bird Counter",
            "Bird Feeder",
            "Diet Specialist",
            "Enclosure Builder",
            "Endangered Species Protector",
            "Falconer",
            "Fishery Manager",
            "Food Web Expert",
            "Forester",
            "Large Bird Specialist",
            "Nest Box Builder",
            "Omnivore Expert",
            "Passerine Specialist",
            "Platform Builder",
            "Prairie Manager",
            "Rodentologist",
            "Small Clutch Specialist",
            "Viticulturalist",
            "Wetland Scientist",
            "Wildlife Gardener",
        }
    ]
    return {column for column in source_columns if _is_marked(row.get(column))}


def _parse_round_goal_scoring_values(row: dict[Any, Any]) -> dict[int, int]:
    scoring_values: dict[int, int] = {}
    for column in (1, 2, 3, 4):
        if is_blank(row.get(column)):
            continue
        score = _try_parse_int(row.get(column))
        if score is None:
            continue
        scoring_values[int(column)] = max(score, 0)
    return scoring_values


def _parse_count(value: Any) -> int:
    if is_blank(value):
        return 0
    if isinstance(value, int | float):
        return int(value)
    cleaned = str(value).strip()
    if cleaned.upper() == "X":
        return 1
    if set(cleaned) == {"/"}:
        return len(cleaned)
    return int(cleaned)


def _parse_int(value: Any, *, default: int) -> int:
    if is_blank(value):
        return default
    if isinstance(value, int | float):
        return int(value)
    return int(str(value).strip())


def _try_parse_int(value: Any) -> int | None:
    try:
        return _parse_int(value, default=0)
    except ValueError:
        return None


def _parse_percent(value: Any) -> float | None:
    if is_blank(value):
        return None
    cleaned = str(value).replace("%", "").replace("*", "").strip()
    if cleaned in {"", "-"}:
        return None
    return float(cleaned)


def _is_marked(value: Any) -> bool:
    if is_blank(value):
        return False
    if isinstance(value, int | float):
        return value != 0
    return str(value).strip().upper() in {"X", "*", "Y", "YES", "TRUE", "1"}


def _should_skip_pack(
    row_packs: set[ContentPack],
    requested_packs: set[ContentPack] | None,
) -> bool:
    return requested_packs is not None and not bool(row_packs & requested_packs)


def _row_number(row: dict[Any, Any]) -> int | None:
    value = row.get("__row_number__")
    return int(value) if value is not None else None


def _default_ruleset_id(content_packs: list[ContentPack]) -> str:
    if content_packs == [ContentPack.CORE]:
        return "core_base_game_v1"
    pack_slug = "_".join(pack.value for pack in content_packs)
    return f"{pack_slug}_ruleset_v1"
