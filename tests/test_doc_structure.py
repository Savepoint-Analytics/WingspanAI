"""Documentation-structure rules that would otherwise decay silently.

`PROJECT_CONTEXT.md` is longitudinal by design, so its chronological log grows
without bound: by 2026-10-02 it was 4,153 lines, 90% dated updates, and the
standing brief read every session had degraded enough that the top task appeared
three times. `CLAUDE.md` now bounds it at ~1,000 lines, and the project's own
lesson -- a printed worktree reminder missed 7 times out of 9 -- says a rule in
prose is not enough. So it is a test.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "PROJECT_CONTEXT.md"
#: Matches the threshold stated in CLAUDE.md and AGENTS.md. Change all three together.
MAX_CONTEXT_LINES = 1000


class ProjectContextSizeTests(TestCase):
    def test_project_context_stays_readable(self) -> None:
        lines = len(CONTEXT.read_text().split("\n"))
        self.assertLessEqual(
            lines,
            MAX_CONTEXT_LINES,
            f"PROJECT_CONTEXT.md is {lines:,} lines, over the {MAX_CONTEXT_LINES:,} line "
            "bound in CLAUDE.md. Archive older updates with:\n"
            "    python scripts/archive_project_log.py --keep 10\n"
            "It moves them verbatim to docs/history/ and refuses to finish unless every "
            "original line is still present. Nothing is summarised or deleted.",
        )

    def test_the_threshold_here_matches_the_instruction_files(self) -> None:
        """A number in two places drifts; this fails when it does."""

        for name in ("CLAUDE.md", "AGENTS.md"):
            text = (ROOT / name).read_text()
            self.assertIn(
                "**1,000 lines**",
                text,
                f"{name} no longer states the 1,000-line bound that "
                "MAX_CONTEXT_LINES encodes",
            )


class ProjectContextStructureTests(TestCase):
    def sections(self) -> list[str]:
        """Top-level headings, ignoring fenced blocks.

        The protocol section contains a ```markdown template with a literal
        ``## Update: YYYY-MM-DD`` line in it. Counting that as a heading is the
        bug that would have split the protocol in half during archiving.
        """

        headings, in_fence = [], False
        for line in CONTEXT.read_text().split("\n"):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence and line.startswith("## "):
                headings.append(line)
        return headings

    def test_exactly_one_archive_index(self) -> None:
        """Each archive run used to leave another index behind."""

        indexes = [h for h in self.sections() if h.strip() == "## Archived project log"]
        self.assertLessEqual(len(indexes), 1, f"{len(indexes)} archive index sections")

    def test_no_duplicate_section_headings(self) -> None:
        headings = [h for h in self.sections() if not h.startswith("## Update:")]
        duplicates = {h for h in headings if headings.count(h) > 1}
        self.assertFalse(duplicates, f"duplicated headings: {sorted(duplicates)}")

    def test_no_duplicate_task_rows(self) -> None:
        """The top task appeared three times before 2026-10-02."""

        text = CONTEXT.read_text()
        start = text.index("## Current recommended next tasks")
        table = text[start : text.index("\n## ", start + 10)]
        rows = [
            re.sub(r"\s+", " ", line).strip()
            for line in table.split("\n")
            if re.match(r"^\|\s*[123]\s*\|", line)
        ]
        tasks = [row.split("|")[2].strip()[:60] for row in rows if len(row.split("|")) > 2]
        duplicates = {t for t in tasks if tasks.count(t) > 1}
        self.assertFalse(duplicates, f"duplicated task rows: {sorted(duplicates)}")


class ArchiveIntegrityTests(TestCase):
    def test_the_archive_is_never_the_only_copy_of_a_standing_rule(self) -> None:
        """Standing rules belong in the brief or the ledger, not a dated update.

        Two items were found trapped in dated updates during the 2026-10-02
        audit: the per-decision/whole-game rule and the Gaussian-Markov
        assessment. Both now have canonical homes.
        """

        ledger = (ROOT / "docs/experiments/results_ledger.md").read_text()
        self.assertIn("Standing rules for registering and reading an arm", ledger)
        self.assertTrue((ROOT / "docs/agents/gaussian_markov_value_agent.md").exists())

    def test_history_files_say_they_are_verbatim(self) -> None:
        for path in (ROOT / "docs/history").glob("project_log_*.md"):
            self.assertIn("verbatim", path.read_text()[:600], f"{path.name} lacks the notice")
