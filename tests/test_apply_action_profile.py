import importlib.util
from pathlib import Path
from unittest import TestCase

from wingspan_ai.content import make_sample_catalog

PROFILE_PATH = Path(__file__).parents[1] / "analysis" / "apply_action_profile.py"
PROFILE_SPEC = importlib.util.spec_from_file_location("apply_action_profile", PROFILE_PATH)
if PROFILE_SPEC is None or PROFILE_SPEC.loader is None:
    raise RuntimeError(f"Could not load profile module from {PROFILE_PATH}")
apply_action_profile = importlib.util.module_from_spec(PROFILE_SPEC)
PROFILE_SPEC.loader.exec_module(apply_action_profile)


class ApplyActionProfileTests(TestCase):
    def test_profile_apply_action_cost_reports_copy_share(self) -> None:
        profile = apply_action_profile.profile_apply_action_cost(
            make_sample_catalog(),
            random_seed=1,
            iterations=1,
        )

        self.assertGreater(profile["legal_action_count"], 0)
        self.assertIn("deep_copy_avg_ms", profile)
        self.assertIn("apply_action_avg_ms", profile)
        self.assertIn("deep_copy_share_of_apply_action", profile)
        self.assertGreaterEqual(profile["deep_copy_share_of_apply_action"], 0)

    def test_render_profile_markdown_includes_profiled_action(self) -> None:
        profile = apply_action_profile.profile_apply_action_cost(
            make_sample_catalog(),
            random_seed=1,
            iterations=1,
        )

        report = apply_action_profile.render_profile_markdown(profile)

        self.assertIn("# Apply Action Profile", report)
        self.assertIn("Profiled action", report)
