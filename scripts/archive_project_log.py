"""Move old ``## Update:`` sections out of PROJECT_CONTEXT.md, verbatim.

Why
---
`CLAUDE.md` makes `PROJECT_CONTEXT.md` longitudinal, so its chronological log
grows without bound: at 2026-10-02 it was 4,153 lines, of which 90% was dated
updates and 10% the standing brief that is read every session. The brief had
visibly degraded -- the top task appeared three times.

This moves updates older than the most recent ``--keep`` **verbatim and
unedited** into ``docs/history/project_log_<year>.md`` and leaves a dated index
behind. Nothing is summarised, rewritten or judged. The archive is append-only.

Two parsing traps, both live in this file and both fatal if missed:

1. **Code fences.** The protocol section contains a ```markdown block holding a
   literal ``## Update: YYYY-MM-DD - Short title`` template. A line-based parser
   treats that as a section heading and splits the protocol in half.
2. **Interleaved standing sections.** ``## Decision log``, ``## Things to avoid
   repeating`` and ``## Files that should exist near this file`` sit *after* the
   first update, so "everything past line N is history" silently archives
   standing instructions.

The completeness gate compares whitespace-normalised non-blank lines, because
Markdown wraps prose: a rule reading "verify a dry run's game\\ncount" does not
match a search for "game count", which produced a false negative during the
2026-10-02 audit.

    python scripts/archive_project_log.py --dry-run
    python scripts/archive_project_log.py --keep 10
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "PROJECT_CONTEXT.md"
UPDATE_HEADING = re.compile(r"^## Update:\s*(\d{4}-\d{2}-\d{2})")

INDEX_MARKER = "<!-- archived-log-index -->"


def split_sections(lines: list[str]) -> list[tuple[int, int, str]]:
    """``(start, end, heading)`` per top-level section, ignoring fenced blocks."""

    starts: list[int] = []
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and line.startswith("## "):
            starts.append(index)
    bounds = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        bounds.append((start, end, lines[start]))
    return bounds


def strip_index_blocks(text: str) -> str:
    """Drop this tool's own generated index block.

    The gate must be strict about *content* and silent about text this tool
    writes: an index is regenerated on every run, so rewording it is not data
    loss. Without this exemption the gate fails on its own output, which it did
    on the first idempotent run.
    """

    lines = text.split("\n")
    keep, skipping = [], False
    for line in lines:
        if line.strip() == INDEX_MARKER:
            skipping = True
            continue
        if skipping:
            # the block runs to the next top-level heading that is not its own
            if line.startswith("## ") and line.strip() != "## Archived project log":
                skipping = False
            else:
                continue
        keep.append(line)
    return "\n".join(keep)


def normalized(text: str) -> list[str]:
    text = strip_index_blocks(text)
    return [re.sub(r"\s+", " ", line).strip() for line in text.split("\n") if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--keep", type=int, default=10, help="most recent updates to leave inline")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    original = CONTEXT.read_text()
    lines = original.split("\n")
    sections = split_sections(lines)

    dated = [(start, end, head, UPDATE_HEADING.match(head).group(1))
             for start, end, head in sections if UPDATE_HEADING.match(head)]
    if not dated:
        print("no dated update sections found; nothing to archive")
        return 0
    dated.sort(key=lambda item: (item[3], item[0]))
    keep = set(id(item) for item in dated[-args.keep:]) if args.keep else set()
    move = [item for item in dated if id(item) not in keep]
    if not move:
        print(f"{len(dated)} updates, all within the most recent {args.keep}; nothing to archive")
        return 0

    years = sorted({date[:4] for _s, _e, _h, date in move})
    print(f"{len(dated)} dated updates; moving {len(move)}, keeping {len(dated) - len(move)}")
    print(f"  years: {', '.join(years)}")
    print(f"  standing sections preserved: "
          f"{len([s for s in sections if not UPDATE_HEADING.match(s[2])])}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    # the archive, one file per year, in date order
    per_year: dict[str, list[str]] = {}
    for start, end, _head, date in move:
        per_year.setdefault(date[:4], []).append("\n".join(lines[start:end]).rstrip())

    archive_paths = []
    for year, blocks in per_year.items():
        path = ROOT / "docs" / "history" / f"project_log_{year}.md"
        # Append-only, as the header promises. An earlier version used a bare
        # write_text here, which would have silently destroyed every previously
        # archived update on the second run -- the archive is the record, so
        # existing blocks are re-read and merged, then the whole file is sorted
        # by date so repeated runs converge on the same ordering.
        if path.exists():
            existing = split_sections(path.read_text().split("\n"))
            kept_blocks = [
                "\n".join(path.read_text().split("\n")[start:end]).rstrip()
                for start, end, head in existing
                if UPDATE_HEADING.match(head)
            ]
            blocks = kept_blocks + blocks
        def sort_key(block: str) -> tuple[str, str]:
            match = UPDATE_HEADING.match(block.split("\n", 1)[0])
            return (match.group(1) if match else "", block[:120])
        blocks = sorted(dict.fromkeys(blocks), key=sort_key)
        header = (
            f"# Project log {year}\n\n"
            "Archived from `PROJECT_CONTEXT.md`, **verbatim and unedited**, by\n"
            "`scripts/archive_project_log.py`. Append-only: entries here are never\n"
            "rewritten. New updates go to `PROJECT_CONTEXT.md`.\n\n"
            "Routed records live in their canonical homes and are not duplicated here:\n"
            "arm results in `docs/experiments/results_ledger.md`, decisions in\n"
            "`docs/decisions/`, findings in `docs/experiments/strategy_findings.md`.\n"
        )
        body = header + "\n" + "\n\n".join(blocks) + "\n"
        path.write_text(body)
        archive_paths.append((path, len(blocks)))  # len(blocks) is the merged total
        print(f"  wrote {path.relative_to(ROOT)} "
              f"({len(blocks)} updates, {len(body.splitlines())} lines)")

    # rebuild the context file, dropping moved blocks and inserting an index
    drop = set()
    for start, end, _head, _date in move:
        drop.update(range(start, end))
    # Counts come from the archive itself, so a second run reports the running
    # total rather than only what it just moved.
    index_lines = [
        INDEX_MARKER,
        "## Archived project log",
        "",
        "Earlier updates were moved **verbatim and unedited** to the project log;",
        "nothing was summarised. See `scripts/archive_project_log.py`, whose",
        "completeness gate asserts every original line survives the move.",
        "",
    ]
    for path, total in sorted(archive_paths):
        year = path.stem.removeprefix("project_log_")
        index_lines.append(f"- **{year}**: {total} updates in `{path.relative_to(ROOT)}`")
    index_lines.append("")

    # Remove a previous index block; otherwise each run leaves another behind.
    for start, end, head in sections:
        if head.strip() == "## Archived project log":
            drop.update(range(start, end))
            if start > 0 and lines[start - 1].strip() == INDEX_MARKER:
                drop.add(start - 1)

    first_moved = min(start for start, _e, _h, _d in move)
    rebuilt: list[str] = []
    inserted = False
    for index, line in enumerate(lines):
        if index in drop:
            if index == first_moved and not inserted:
                rebuilt.extend(index_lines)
                inserted = True
            continue
        rebuilt.append(line)
    CONTEXT.write_text("\n".join(rebuilt))

    # completeness gate
    after = normalized(CONTEXT.read_text())
    for path, _n in archive_paths:
        after += normalized(path.read_text())
    missing = []
    counts: dict[str, int] = {}
    for line in after:
        counts[line] = counts.get(line, 0) + 1
    for line in normalized(original):
        if counts.get(line, 0) <= 0:
            missing.append(line)
        else:
            counts[line] -= 1
    print(f"\ncompleteness gate: {len(normalized(original)):,} original lines checked")
    if missing:
        print(f"  FAILED: {len(missing)} unaccounted line(s)")
        for line in missing[:15]:
            print(f"    {line[:110]}")
        return 1
    print("  PASSED: every original line is present in the context file or the archive")
    print(f"\nPROJECT_CONTEXT.md: {len(lines):,} -> {len(rebuilt):,} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
