# ADR 0005: Simulation artifacts live in object storage, not on local disk

- Status: accepted
- Date: 2026-09-03

## Decision

Every simulation batch uploads its artifact directory to the configured
S3-compatible bucket (`savepoint-ai`, prefix `board-games/wingspan`). The local
`artifacts/` tree is a working cache that may be pruned. Object storage is the
durable copy.

Batch manifests additionally record `code_provenance`: the git commit, branch,
and whether the tree was dirty when the run executed.

## Why

The upload path already existed (`wingspan_ai.storage.object_storage`) and
`flows/simulation_batch.py` already enabled it whenever storage was configured.
But `flows/round_robin.py` hardcoded `upload_artifacts=False`, overriding that
default, and round robins produce nearly all of the project's data. The result:
1.7 GB across 3,259 files accumulated on a single laptop while the bucket held
21 objects, all of them smoke tests.

That went unnoticed until a routine "can we delete this archive?" question. The
answer turned out to be no, and for a worse reason than staleness: `artifacts/`
is gitignored, the manifests recorded no code version, and the code that produced
the 322 MB `rrv4_pre_fix` archive had never been committed and had since been
edited over. It was simultaneously the only copy of that data and unreproducible.
The numbers it backs (`+0.182` denial, `+0.112` tray tie-break) are quoted in
`docs/experiments/mat_scaling_ablation.md`.

Local disk is a single point of failure for evidence behind published results.

## Alternatives considered

- **Compress in place.** Telemetry JSONL gzips ~28x, so 1.7 GB would fall to
  roughly 60 MB. Cheap, but it keeps one unreplicated copy on one machine and
  does nothing about provenance. Rejected as a substitute; still fine as an
  additional step.
- **Delete superseded archives.** Only safe once a durable copy exists and the
  claims resting on the data have been re-derived. Deferred, not rejected.
- **Commit artifacts to git.** Binary-ish telemetry at this volume would bloat
  the repository permanently. Rejected.

## What would cause this to be revisited

- Bucket egress or storage cost becoming material.
- A move to a hosted object store where a laptop-local MinIO endpoint no longer
  applies.
- Artifact volume growing enough that per-batch upload measurably slows runs.
  Measured cost today is ~4.9 MB/s, about 3 seconds for a 14 MB cell.

## Consequences

- `flows/round_robin.py` now defaults `upload_artifacts=None`, inheriting the
  auto-detect rather than overriding it.
- `scripts/backfill_artifacts_to_object_storage.py` mirrors the existing tree and
  is idempotent, so an interrupted run can be repeated.
- `code_provenance.reproducible` is false for any run made from a dirty tree.
  Those artifacts must be preserved; clean-tree artifacts can be regenerated.

## Follow-up (2026-09-24): storage tiers, compaction, and a provenance bug

Measured: the bucket held 21.1 GB across 44,096 objects, of which
**12.0 GB (57%) was `public_state_snapshots.json`** — a full public state per
turn that nothing reads, because every analysis and the replay validator
reconstruct state from `events.jsonl`. `scripts/compact_object_storage.py`
gzips those objects in place (reversible with `--restore`, verified on a
round trip before the bulk run); `analysis/compact_artifacts.py` does the
same for the local cache and recovered 2.23 GB.

The tiers are now explicit. **Object storage is the durable, complete log.**
**PostgreSQL is the queryable analysis layer**, which means it carries
summaries for every game and events only for the runs under analysis — so
`insert_events` and the batch flow take `event_names`, and
`ANALYSIS_EVENT_NAMES` names the eight families the view layer reads. The
four per-turn decision families left out were 94% of stored payload weight.

**Provenance bug found while backfilling.** Chunked arms write several
batches into one batch directory and each chunk overwrites
`batch_manifest.json`, so the surviving manifest lists only the last chunk's
games: 2,433 manifests covered 5,826 of 10,399 archived games. The lost
manifests take their `code_provenance`, holdout record and per-seat search
config with them. `scripts/backfill_summaries.py --source minio-events`
recovers run, game and score rows directly from the event objects, but the
fix is for a chunked run to write its manifest under a chunk-unique key.
