"""Expansion configuration threading: packs and modules → ruleset → state → manifest.

Phase 0 of ``docs/rules/expansion_configuration.md``. The base game must be
bit-identical whether or not the configuration is spelled out, unimplemented
rules modules must be refused rather than silently ignored, and the manifest
must say which ruleset a game was played under.
"""

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipIf

from wingspan_ai.content import make_sample_catalog
from wingspan_ai.content.loader import (
    DEFAULT_WORKBOOK_PATH,
    build_ruleset,
    load_content_catalog,
    normalize_rules_modules,
    ruleset_id_for,
)
from wingspan_ai.content.schemas import ContentPack, RulesModule
from wingspan_ai.rules.base_game import (
    IMPLEMENTED_RULES_MODULES,
    apply_action,
    legal_actions_for_current_player,
    setup_base_game,
)

FLOW_PATH = Path(__file__).parents[1] / "flows" / "simulation_batch.py"
spec = importlib.util.spec_from_file_location("simulation_batch_cfg", FLOW_PATH)
simulation_batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulation_batch)


class RulesetIdTests(TestCase):
    def test_base_game_keeps_its_historic_id(self) -> None:
        self.assertEqual(ruleset_id_for([ContentPack.CORE]), "core_base_game_v1")
        self.assertEqual(
            ruleset_id_for([ContentPack.CORE], [RulesModule.BASE_GAME]), "core_base_game_v1"
        )

    def test_ids_are_order_independent_with_core_first(self) -> None:
        self.assertEqual(ruleset_id_for([ContentPack.ASIA, ContentPack.CORE]), "core_asia_v1")
        self.assertEqual(
            ruleset_id_for(
                [ContentPack.OCEANIA, ContentPack.CORE],
                [RulesModule.REVISED_PLAYER_MAT, RulesModule.NECTAR, RulesModule.BASE_GAME],
            ),
            "core_oceania__nectar_rules__revised_player_mat_v1",
        )
        self.assertEqual(
            normalize_rules_modules([RulesModule.NECTAR, RulesModule.NECTAR]),
            [RulesModule.BASE_GAME, RulesModule.NECTAR],
        )
        ruleset = build_ruleset([ContentPack.EUROPEAN, ContentPack.CORE], player_count=3)
        self.assertEqual(ruleset.content_packs, [ContentPack.CORE, ContentPack.EUROPEAN])
        self.assertEqual(ruleset.rules_modules, [RulesModule.BASE_GAME])
        self.assertEqual(ruleset.player_count, 3)


class EngineGuardTests(TestCase):
    def test_only_the_base_game_module_is_implemented(self) -> None:
        self.assertEqual(IMPLEMENTED_RULES_MODULES, frozenset({RulesModule.BASE_GAME}))

    def test_setup_refuses_an_unimplemented_module(self) -> None:
        catalog = make_sample_catalog().model_copy(
            update={"rulesets": [build_ruleset([ContentPack.CORE], [RulesModule.NECTAR])]}
        )
        with self.assertRaises(NotImplementedError) as raised:
            setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=1)
        self.assertIn("nectar_rules", str(raised.exception))

    def test_state_carries_the_catalog_ruleset(self) -> None:
        catalog = make_sample_catalog().model_copy(
            update={"rulesets": [build_ruleset([ContentPack.CORE], player_count=2)]}
        )
        state = setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=1)
        self.assertEqual(state.ruleset.ruleset_id, "core_base_game_v1")
        self.assertEqual(state.ruleset.content_packs, [ContentPack.CORE])


class BatchFlowConfigurationTests(TestCase):
    def _run(self, tmp_dir: str, batch_id: str, **kwargs):
        return simulation_batch.run_simulation_batch(
            workbook_path="missing-workbook.xlsx",
            seeds=[1],
            artifact_root=tmp_dir,
            persist_postgres=False,
            upload_artifacts=False,
            batch_kind="smoke",
            batch_label="cfg",
            batch_id=batch_id,
            **kwargs,
        )

    def test_explicit_core_config_is_bit_identical_to_the_default(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            default = self._run(tmp_dir, "default")[0]
            explicit = self._run(
                tmp_dir, "explicit", content_packs=["core"], rules_modules=["base_game_rules"]
            )[0]
            # State hashes cover the batch-scoped game id, so compare the
            # action sequences and outcomes instead.
            actions = []
            for result in (default, explicit):
                events = Path(result["artifact_dir"]) / "events.jsonl"
                actions.append(
                    [
                        json.loads(line)["payload"]["action_label"]
                        for line in events.read_text().splitlines()
                        if '"action_resolved"' in line
                    ]
                )
        self.assertTrue(actions[0])
        self.assertEqual(actions[0], actions[1])
        self.assertEqual(default["outcome"]["scores"], explicit["outcome"]["scores"])
        # The sample catalog names its own ruleset so archived sample games
        # are never mistaken for workbook games.
        self.assertEqual(default["ruleset_id"], "sample_core")
        self.assertEqual(explicit["ruleset_id"], "sample_core")
        self.assertEqual(explicit["content_packs"], ["core"])
        self.assertEqual(explicit["rules_modules"], ["base_game_rules"])

    def test_manifest_records_the_ruleset(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            result = self._run(tmp_dir, "manifest", content_packs=["core"])[0]
            manifest = json.loads(Path(result["batch_manifest"]["path"]).read_text())
        self.assertEqual(manifest["ruleset_ids"], ["sample_core"])
        self.assertEqual(manifest["content_packs"], ["core"])
        self.assertEqual(manifest["rules_modules"], ["base_game_rules"])
        self.assertEqual(manifest["games"][0]["ruleset_id"], "sample_core")
        self.assertEqual(manifest["games"][0]["content_packs"], ["core"])

    def test_expansion_content_needs_the_workbook(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                self._run(tmp_dir, "euro", content_packs=["core", "european"])
            with self.assertRaises(ValueError):
                self._run(tmp_dir, "nocore", content_packs=["european"])


@skipIf(not Path(DEFAULT_WORKBOOK_PATH).exists(), "workbook not available")
class WorkbookPackTests(TestCase):
    def test_each_expansion_pack_loads_with_its_own_ruleset_id(self) -> None:
        for pack, expected in (
            (ContentPack.EUROPEAN, "core_european_v1"),
            (ContentPack.OCEANIA, "core_oceania_v1"),
            (ContentPack.ASIA, "core_asia_v1"),
        ):
            catalog = load_content_catalog(content_packs={ContentPack.CORE, pack})
            self.assertEqual(catalog.rulesets[0].ruleset_id, expected)
            self.assertGreater(len([b for b in catalog.birds if b.content_pack == pack]), 50)

    def test_a_workbook_game_with_the_core_pack_plays_as_the_base_game(self) -> None:
        catalog = load_content_catalog(content_packs={ContentPack.CORE})
        state = setup_base_game(catalog, player_ids=["p1", "p2"], random_seed=2)
        self.assertEqual(state.ruleset.ruleset_id, "core_base_game_v1")
        state = apply_action(state, legal_actions_for_current_player(state)[0])
        self.assertEqual(state.ruleset.ruleset_id, "core_base_game_v1")
