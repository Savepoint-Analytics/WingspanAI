from pathlib import Path
from unittest import TestCase, skipIf

from wingspan_ai.content.loader import (
    DEFAULT_WORKBOOK_PATH,
    load_base_game_content_catalog,
    load_content_catalog,
    resolve_workbook_path,
)
from wingspan_ai.content.schemas import ContentPack, PowerImplementationStatus

WORKBOOK_PATH = DEFAULT_WORKBOOK_PATH


@skipIf(not WORKBOOK_PATH.exists(), f"{WORKBOOK_PATH} is not present")
class ContentLoaderTests(TestCase):
    def test_default_workbook_path_points_to_raw_data(self) -> None:
        self.assertEqual(resolve_workbook_path(), Path("data/raw/wingspan-card-list.xlsx"))

    def test_loads_core_workbook_content_into_typed_catalog(self) -> None:
        catalog = load_base_game_content_catalog(WORKBOOK_PATH)

        self.assertEqual(len(catalog.birds), 180)
        self.assertEqual(len(catalog.bonus_cards), 26)
        self.assertEqual(len(catalog.round_goals), 16)
        self.assertEqual(catalog.rulesets[0].ruleset_id, "core_base_game_v1")
        self.assertEqual(catalog.rulesets[0].content_packs, [ContentPack.CORE])

    def test_loader_preserves_power_text_with_explicit_status(self) -> None:
        catalog = load_base_game_content_catalog(WORKBOOK_PATH)
        acorn_woodpecker = next(
            card for card in catalog.birds if card.common_name == "Acorn Woodpecker"
        )

        self.assertIn("Gain 1 [seed]", acorn_woodpecker.power.text or "")
        self.assertEqual(
            acorn_woodpecker.power.implementation_status,
            PowerImplementationStatus.HEURISTIC_RESOLUTION,
        )
        self.assertEqual(acorn_woodpecker.power.handler_key, "gain_food_from_birdfeeder")

    def test_loader_can_load_all_known_workbook_content(self) -> None:
        catalog = load_content_catalog(WORKBOOK_PATH)

        self.assertEqual(len(catalog.birds), 707)
        self.assertEqual(len(catalog.bonus_cards), 60)
        self.assertEqual(len(catalog.round_goals), 56)
