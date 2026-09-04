"""Tests for experiment-level catalog filtering by power implementation status."""

from unittest import TestCase, skipIf

from wingspan_ai.content.filters import (
    filter_catalog_by_power_status,
    resolve_bird_power_status,
)
from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.sample_catalog import make_sample_catalog
from wingspan_ai.content.schemas import PowerImplementationStatus


class ContentFilterTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_default_filter_keeps_implemented_and_no_op_powers(self) -> None:
        result = filter_catalog_by_power_status(self.catalog)

        self.assertEqual(result.retained_bird_count, len(self.catalog.birds))
        self.assertEqual(result.excluded_bird_count, 0)
        self.assertEqual(result.retention_rate, 1.0)

    def test_excluded_handler_keys_drop_matching_birds(self) -> None:
        result = filter_catalog_by_power_status(
            self.catalog,
            excluded_handler_keys=["no_power"],
            minimum_bird_count=0,
        )

        self.assertEqual(result.retained_bird_count, 0)
        self.assertEqual(result.excluded_bird_count, len(self.catalog.birds))
        self.assertEqual(result.excluded_handler_keys, ("no_power",))

    def test_minimum_bird_count_guards_against_unplayable_decks(self) -> None:
        with self.assertRaises(ValueError) as raised:
            filter_catalog_by_power_status(
                self.catalog,
                [PowerImplementationStatus.READY],
            )

        self.assertIn("below the minimum", str(raised.exception))

    def test_manifest_payload_is_json_serializable_and_complete(self) -> None:
        payload = filter_catalog_by_power_status(self.catalog).as_manifest_payload()

        self.assertEqual(
            set(payload),
            {
                "original_bird_count",
                "retained_bird_count",
                "excluded_bird_count",
                "retention_rate",
                "allowed_statuses",
                "excluded_handler_keys",
                "excluded_bird_names",
            },
        )

    def test_filtering_does_not_mutate_the_source_catalog(self) -> None:
        original_count = len(self.catalog.birds)

        filter_catalog_by_power_status(
            self.catalog,
            excluded_handler_keys=["no_power"],
            minimum_bird_count=0,
        )

        self.assertEqual(len(self.catalog.birds), original_count)


class WorkbookContentFilterTests(TestCase):
    @skipIf(
        not DEFAULT_WORKBOOK_PATH.exists(),
        f"{DEFAULT_WORKBOOK_PATH} is not present",
    )
    def test_registry_status_wins_over_stale_card_status(self) -> None:
        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)

        for bird in catalog.birds:
            self.assertNotEqual(
                resolve_bird_power_status(bird),
                PowerImplementationStatus.NOT_IMPLEMENTED,
                bird.common_name,
            )

    @skipIf(
        not DEFAULT_WORKBOOK_PATH.exists(),
        f"{DEFAULT_WORKBOOK_PATH} is not present",
    )
    def test_excluding_a_handler_key_removes_exactly_those_birds(self) -> None:
        catalog = load_base_game_content_catalog(DEFAULT_WORKBOOK_PATH)

        result = filter_catalog_by_power_status(
            catalog,
            excluded_handler_keys=["predator_hunt"],
        )

        self.assertEqual(result.original_bird_count, 180)
        self.assertEqual(result.excluded_bird_count, 14)
        self.assertEqual(result.retained_bird_count, 166)
        self.assertEqual(result.excluded_handler_keys, ("predator_hunt",))
