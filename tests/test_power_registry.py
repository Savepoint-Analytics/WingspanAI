from unittest import TestCase

from wingspan_ai.content.schemas import PowerColor, PowerImplementationStatus
from wingspan_ai.rules.power_registry import POWER_HANDLER_REGISTRY, classify_power_handler_key


class PowerRegistryTests(TestCase):
    def test_power_registry_tracks_source_and_status(self) -> None:
        handler = POWER_HANDLER_REGISTRY["no_power"]

        self.assertEqual(handler.implementation_status, PowerImplementationStatus.NO_OP_FOR_V1)
        self.assertIn("rulebook", handler.source_reference.lower())
        self.assertEqual(handler.rulebook, "rulebook_pdfs/WS_Core_Rulebook.pdf")
        self.assertIsNotNone(handler.rulebook_page)

    def test_power_text_classifier_maps_supported_templates(self) -> None:
        handler_key = classify_power_handler_key(
            "Discard 1 [egg] from any of your other birds to gain 1 [wild] from the supply.",
            PowerColor.BROWN,
        )

        self.assertEqual(handler_key, "discard_egg_gain_wild_food")

    def test_power_text_classifier_maps_deck_search_template(self) -> None:
        handler_key = classify_power_handler_key(
            "Look at a [card] from the deck. If less than 75cm, tuck it behind this bird.",
            PowerColor.BROWN,
        )

        self.assertEqual(handler_key, "deck_search_tuck_by_wingspan")
