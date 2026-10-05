"""Replay one archived rr_belief_opp cell with the current code and diff the action sequences.

The base-game bit-identity guard of ``docs/rules/expansion_configuration.md``:
after any engine, loader or flow change, the core ruleset must still produce
exactly the archived games. Runs seeds ``--seeds`` (default 1) of the
``potential_points`` vs ``archetype_engine_builder`` lineup in both rotations
(about 3 minutes a seed unloaded), then compares the ``action_label``
sequence and final scores against every archived batch holding that seed.

    python analysis/base_game_bit_identity.py --seeds 1

**Read a DIFFERENT result carefully.** The archive it compares against
(``rr_belief_opp``, 2026-09-16) predates several *intentional* changes to the
agent's adopted defaults -- the placement round-goal model became the default on
2026-09-22, for one -- so any game whose decisions that switch touched now
reports DIFFERENT and should. On 2026-10-04 seed 1 was identical and seed 2 was
not, for exactly this reason, which cost half an hour of chasing a
non-regression.

So this answers "did the *rules* change" only for games the adopted switches do
not touch. To test whether a specific change is decision-neutral, compare action
sequences with and without that change in one process rather than against the
archive. The round-score snapshot emitter was cleared that way: identical
``action_label`` hashes on three seeds with the emitter monkeypatched out.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flows.round_robin import run_round_robin  # noqa: E402

ARCHIVE = "artifacts/rr_belief_opp/experiment/potential_points-vs-archetype_engine_builder-control"


def action_sequence(path: str) -> str:
    labels = [
        json.loads(line)["payload"]["action_label"]
        for line in open(path, encoding="utf-8")
        if '"action_resolved"' in line
    ]
    return hashlib.md5("|".join(labels).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", default="1")
    parser.add_argument("--artifact-root", default="artifacts/probes/bit_identity")
    args = parser.parse_args(argv)
    seeds = [int(s) for s in args.seeds.split(",")]
    run_round_robin(
        workbook_path="data/raw/wingspan-card-list.xlsx",
        seeds=seeds,
        roster=["potential_points", "archetype_engine_builder"],
        setup_policy_kinds=["control"],
        artifact_root=args.artifact_root,
        batch_label="bit_identity",
        content_packs=["core"],
        rules_modules=["base_game_rules"],
    )
    failures = 0
    for seed in seeds:
        for rot in (0, 1):
            new = glob.glob(f"{args.artifact_root}/experiment/*rot{rot}/*/seed_{seed}/events.jsonl")
            old = glob.glob(f"{ARCHIVE}-rot{rot}/*/seed_{seed}/events.jsonl")
            if not new or not old:
                print(f"seed {seed} rot{rot}: missing game ({len(new)} new, {len(old)} archived)")
                failures += 1
                continue
            same = any(action_sequence(o) == action_sequence(new[0]) for o in old)
            failures += 0 if same else 1
            print(f"seed {seed} rot{rot}: {'IDENTICAL' if same else 'DIFFERENT'} to the archive")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
