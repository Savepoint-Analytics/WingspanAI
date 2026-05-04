from pathlib import Path
from unittest import TestCase

from wingspan_ai.content.loader import load_base_game_content_catalog, load_content_catalog
from wingspan_ai.content.schemas import ContentPack, PowerImplementationStatus


class ContentLoaderTests(TestCase):
    def test_loads_core_workbook_content_into_typed_catalog(self) -> None:
        catalog = load_base_game_content_catalog(Path("wingspan-card-list.xlsx"))

        self.assertEqual(len(catalog.birds), 180)
        self.assertEqual(len(catalog.bonus_cards), 26)
        self.assertEqual(len(catalog.round_goals), 16)
        self.assertEqual(catalog.rulesets[0].ruleset_id, "core_base_game_v1")
        self.assertEqual(catalog.rulesets[0].content_packs, [ContentPack.CORE])

    def test_loader_preserves_power_text_with_explicit_status(self) -> None:
        catalog = load_base_game_content_catalog(Path("wingspan-card-list.xlsx"))
        acorn_woodpecker = next(
            card for card in catalog.birds if card.common_name == "Acorn Woodpecker"
        )

        self.assertIn("Gain 1 [seed]", acorn_woodpecker.power.text or "")
        self.assertEqual(
            acorn_woodpecker.power.implementation_status,
            PowerImplementationStatus.NOT_IMPLEMENTED,
        )

    def test_loader_can_load_all_known_workbook_content(self) -> None:
        catalog = load_content_catalog(Path("wingspan-card-list.xlsx"))

        self.assertEqual(len(catalog.birds), 707)
        self.assertEqual(len(catalog.bonus_cards), 60)
        self.assertEqual(len(catalog.round_goals), 56)
