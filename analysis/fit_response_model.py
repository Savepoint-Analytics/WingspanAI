"""Fit the belief model's response likelihoods to the scripted roster from the archive.

Why
---
The belief search opponent model predicts which action *family* an opponent
will play from public candidate values, through ``P(family | profile, values)``
likelihoods that were set by hand in 2026-08 and never fitted. The
2026-09-18/19 three-player arms priced that: the greedy opponent model beats
belief by about two points, the oracle-type bound recovers 1.4 of it, and
``belief_apply`` showed the within-family pick is not where the loss is
(84% identical games). What costs is the family the search assumes. This
script fits the likelihoods to what the roster actually does.

What it does
------------
``extract``: replays every archived game under the given roots, and for every
decision by a non-``potential_points`` seat records the public candidate
values the belief model would have seen (``_public_candidate_values`` on the
real state, public projection only), the family chosen, and the seat's agent
kind. Identical decisions reached by more than one root (seed-paired arms
replay the same opponents until the searching seat diverges) are flagged
``duplicate`` so the fit counts each once; scoring uses whole games from the
``--eval-root`` roots only, so a game is never scored from mid-trajectory.

``fit``: per roster kind, maximum-likelihood fit of

    logit(a) = log prior(a) + w(a) * v(a)

over the available families, with the slope either shared (``prior_temp``:
``w = 1/T``, the hand-set form) or per family (``logit``). Scored the way the
search uses the model — sequentially through each held-out game, predict then
observe, uniform prior over profiles — by leave-one-seed-out cross-validation
against the hand-set profiles, and against the ceiling where the kind is
known from turn one. Writes the full-data fit to ``configs/belief/`` when
asked and prints the comparison.

    python analysis/fit_response_model.py extract artifacts/rr_belief_opp artifacts/rr3p_opp \\
        --out artifacts/response_fit/observations.jsonl
    python analysis/fit_response_model.py fit artifacts/response_fit/observations.jsonl \\
        --eval-root artifacts/rr_belief_opp --eval-root artifacts/rr3p_opp/belief \\
        --out configs/belief/fitted_response_models.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.play_counterfactuals import load_events, reconstruct_decisions  # noqa: E402
from wingspan_ai.agents.search_opponent import _public_candidate_values  # noqa: E402
from wingspan_ai.belief import (  # noqa: E402
    ACTION_FAMILIES,
    DEFAULT_PROFILE_MODELS,
    OpponentBeliefState,
    OpponentProfile,
    ProfileResponseModel,
)
from wingspan_ai.content.loader import (  # noqa: E402
    DEFAULT_WORKBOOK_PATH,
    load_base_game_content_catalog,
)
from wingspan_ai.rules.actions import ActionType  # noqa: E402
from wingspan_ai.simulation.replay import canonical_state_payload  # noqa: E402

STUDY_AGENT_KIND = "potential_points"
FORMS = ("prior_temp", "logit")
FAMILY_INDEX = {family: i for i, family in enumerate(ACTION_FAMILIES)}


def agent_kind(agent_id: str) -> str:
    kind = agent_id.removeprefix("guardrailed_")
    return kind.rsplit("_p", 1)[0] if "_p" in kind else kind


# --------------------------------------------------------------------------- extract


def extract_game(catalog, events_path: Path) -> list[dict]:
    events = load_events(events_path)
    run_started = next(e for e in events if e["event_name"] == "simulation_run_started")
    player_count = int(run_started["payload"]["player_count"])
    seed = next(e for e in events if e["event_name"] == "game_started")["random_seed"]
    lineup = ",".join(
        agent_kind(a["agent_id"]) if isinstance(a, dict) else agent_kind(str(a))
        for a in run_started["payload"]["agents"]
    )
    rows: list[dict] = []
    for state, action, event in reconstruct_decisions(catalog, events):
        kind = agent_kind(event["agent_id"])
        if kind == STUDY_AGENT_KIND:
            continue
        candidates = _public_candidate_values(state, event["player_id"])
        # The recorded state hash covers the batch-scoped game id, so the same
        # decision reached by two roots hashes differently; hash without it.
        payload = canonical_state_payload(state)
        payload.pop("game_id", None)
        content_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        rows.append(
            {
                "player_count": player_count,
                "seed": seed,
                "lineup": lineup,
                "game_id": event["game_id"],
                "player_id": event["player_id"],
                "kind": kind,
                "round": event["round_number"],
                "global_turn": event["global_turn_number"],
                "state_hash_before": content_hash,
                "candidates": {f.value: round(v, 6) for f, v in candidates.items()},
                "observed": action.action_type.value,
            }
        )
    return rows


def extract(roots: list[Path], out: Path, workbook: Path) -> None:
    catalog = load_base_game_content_catalog(workbook)
    seen: set[tuple] = set()
    kept = dropped = games = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with out.open("w", encoding="utf-8") as handle:
        for root in roots:
            for events_path in sorted(root.rglob("events.jsonl")):
                games += 1
                for row in extract_game(catalog, events_path):
                    key = (row["player_count"], row["seed"], row["kind"], row["state_hash_before"])
                    row["duplicate"] = key in seen
                    seen.add(key)
                    row["events_path"] = str(events_path)
                    handle.write(json.dumps(row) + "\n")
                    if row["duplicate"]:
                        dropped += 1
                    else:
                        kept += 1
                if games % 50 == 0:
                    print(f"{games} games, {kept} decisions kept, {time.time() - started:.0f} s")
    print(
        f"done: {games} games, {kept} distinct opponent decisions, "
        f"{dropped} flagged duplicate -> {out}"
    )


# --------------------------------------------------------------------------- fit


def _softmax(logits: dict[ActionType, float]) -> dict[ActionType, float]:
    top = max(logits.values())
    weights = {f: math.exp(v - top) for f, v in logits.items()}
    total = sum(weights.values())
    return {f: w / total for f, w in weights.items()}


class KindModel:
    """``logit(a) = b[a] + w[a] * v(a)``; ``prior_temp`` ties every ``w[a]`` to one slope."""

    def __init__(self, form: str) -> None:
        self.form = form
        self.b = [0.0] * len(ACTION_FAMILIES)
        self.w = [0.5] * len(ACTION_FAMILIES)

    def slope(self, i: int) -> float:
        return self.w[0] if self.form == "prior_temp" else self.w[i]

    def probabilities(self, candidates: dict[ActionType, float]) -> dict[ActionType, float]:
        logits = {
            f: self.b[FAMILY_INDEX[f]] + self.slope(FAMILY_INDEX[f]) * v
            for f, v in candidates.items()
        }
        return _softmax(logits)

    def fit(
        self,
        rows: list[tuple[dict[ActionType, float], ActionType]],
        ridge: float = 1e-3,
        max_iterations: int = 300,
    ) -> float:
        """Gradient ascent with backtracking on the mean log-likelihood (light ridge)."""

        # Flatten once: per row, the available family indices, their values,
        # and the observed family's index.
        flat = [
            (
                [FAMILY_INDEX[f] for f in candidates],
                [v for v in candidates.values()],
                FAMILY_INDEX[observed],
            )
            for candidates, observed in rows
        ]
        n = len(flat)
        k = len(ACTION_FAMILIES)
        exp = math.exp

        def objective_and_gradient(b: list[float], w: list[float]):
            gb = [0.0] * k
            gw = [0.0] * k
            ll = 0.0
            for idx, vals, obs in flat:
                logits = [
                    b[i] + (w[0] if self.form == "prior_temp" else w[i]) * v
                    for i, v in zip(idx, vals, strict=True)
                ]
                top = max(logits)
                weights = [exp(x - top) for x in logits]
                total = sum(weights)
                for i, v, wt in zip(idx, vals, weights, strict=True):
                    prob = wt / total
                    residual = (1.0 if i == obs else 0.0) - prob
                    gb[i] += residual
                    gw[i] += residual * v
                    if i == obs:
                        ll += math.log(max(prob, 1e-12))
            ll = ll / n - 0.5 * ridge * (sum(x * x for x in b) + sum(x * x for x in w))
            gb = [g / n - ridge * x for g, x in zip(gb, b, strict=True)]
            gw = [g / n - ridge * x for g, x in zip(gw, w, strict=True)]
            if self.form == "prior_temp":
                shared = sum(gw)
                gw = [shared] * k
            return ll, gb, gw

        step = 1.0
        ll, gb, gw = objective_and_gradient(self.b, self.w)
        for _iteration in range(max_iterations):
            while True:
                b_new = [x + step * g for x, g in zip(self.b, gb, strict=True)]
                w_new = [x + step * g for x, g in zip(self.w, gw, strict=True)]
                ll_new, gb_new, gw_new = objective_and_gradient(b_new, w_new)
                if ll_new >= ll or step < 1e-6:
                    break
                step *= 0.5
            improved = ll_new - ll
            self.b, self.w, ll, gb, gw = b_new, w_new, ll_new, gb_new, gw_new
            step = min(step * 1.5, 8.0)
            if improved < 1e-7:
                break
        return ll

    def as_profile(self, profile: OpponentProfile) -> ProfileResponseModel:
        prior = _softmax({f: self.b[FAMILY_INDEX[f]] for f in ACTION_FAMILIES})
        return ProfileResponseModel(
            profile=profile,
            family_prior=prior,
            value_temperature=1.0,
            family_value_weight={f: self.slope(FAMILY_INDEX[f]) for f in ACTION_FAMILIES},
        )


def load_observations(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            row["candidates"] = {ActionType(f): v for f, v in row["candidates"].items()}
            row["observed"] = ActionType(row["observed"])
            rows.append(row)
    return rows


def fit_profiles(
    rows: list[dict], form: str
) -> tuple[dict[OpponentProfile, ProfileResponseModel], dict[str, float]]:
    """One fitted profile per roster kind, plus the hand-set random-legal catch-all."""

    by_kind: dict[str, list] = defaultdict(list)
    for row in rows:
        if row["observed"] in row["candidates"]:
            by_kind[row["kind"]].append((row["candidates"], row["observed"]))
    profiles: dict[OpponentProfile, ProfileResponseModel] = {
        OpponentProfile.RANDOM_LEGAL: DEFAULT_PROFILE_MODELS[OpponentProfile.RANDOM_LEGAL]
    }
    train_ll: dict[str, float] = {}
    for kind, data in sorted(by_kind.items()):
        model = KindModel(form)
        train_ll[kind] = model.fit(data)
        profiles[OpponentProfile(kind)] = model.as_profile(OpponentProfile(kind))
    return profiles, train_ll


def sequential_score(
    rows: list[dict],
    profiles: dict[OpponentProfile, ProfileResponseModel],
    *,
    known_kind: bool = False,
) -> dict[str, Counter]:
    """Predict-then-observe through each game per opponent, as the search does.

    Returns per-kind counters of decisions, log loss, top-1 hits, and hits of
    the family the search would play (the most likely one).
    """

    by_game: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        by_game[(row["game_id"], row["player_id"])].append(row)
    totals: dict[str, Counter] = defaultdict(Counter)
    for (_game, player_id), decisions in by_game.items():
        decisions.sort(key=lambda r: r["global_turn"])
        kind = decisions[0]["kind"]
        if known_kind and OpponentProfile(kind) in profiles:
            belief = OpponentBeliefState(
                opponent_id=player_id,
                profile_posterior={OpponentProfile(kind): 1.0},
                profile_models=profiles,
            )
        else:
            belief = OpponentBeliefState.uniform(player_id, profile_models=profiles)
        for row in decisions:
            candidates, observed = row["candidates"], row["observed"]
            if observed not in candidates:
                totals[kind]["unmodelled"] += 1
                continue
            distribution = belief.predict(candidates)
            p = max(distribution.probability_of(observed), 1e-9)
            totals[kind]["n"] += 1
            totals[kind]["log_loss"] += -math.log(p)
            totals[kind]["top1"] += 1 if distribution.most_likely_family == observed else 0
            if not known_kind:
                belief = belief.observe(observed, candidates)
    return totals


def _summarize(totals: dict[str, Counter]) -> dict[str, dict[str, float]]:
    out = {}
    grand = Counter()
    for kind, c in sorted(totals.items()):
        grand.update(c)
        out[kind] = {
            "n": c["n"],
            "log_loss": round(c["log_loss"] / max(c["n"], 1), 4),
            "top1": round(c["top1"] / max(c["n"], 1), 4),
        }
    out["all"] = {
        "n": grand["n"],
        "log_loss": round(grand["log_loss"] / max(grand["n"], 1), 4),
        "top1": round(grand["top1"] / max(grand["n"], 1), 4),
        "unmodelled": grand["unmodelled"],
    }
    return out


def is_eval_row(row: dict, eval_roots: list[str]) -> bool:
    return any(row["events_path"].startswith(root) for root in eval_roots)


def cross_validate(rows: list[dict], form: str, eval_roots: list[str]) -> dict[str, dict]:
    train_pool = [r for r in rows if not r["duplicate"]]
    eval_pool = [r for r in rows if is_eval_row(r, eval_roots)]
    seeds = sorted({row["seed"] for row in eval_pool})
    pooled: dict[str, dict[str, Counter]] = {
        "hand_set": defaultdict(Counter),
        "fitted": defaultdict(Counter),
        "fitted_known_kind": defaultdict(Counter),
    }
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor() as pool:
        fold_results = list(
            pool.map(
                _run_fold,
                [(seed, train_pool, eval_pool, form) for seed in seeds],
            )
        )
    for seed, fold in zip(seeds, fold_results, strict=True):
        print(
            f"  fold seed {seed}: "
            + ", ".join(
                f"{label} {_summarize(totals)['all']['log_loss']:.4f}"
                for label, totals in fold.items()
            ),
            flush=True,
        )
        for label, totals in fold.items():
            for kind, c in totals.items():
                pooled[label][kind].update(c)
    return {label: _summarize(totals) for label, totals in pooled.items()}


def _run_fold(args: tuple) -> dict[str, dict[str, Counter]]:
    seed, train_pool, eval_pool, form = args
    train = [r for r in train_pool if r["seed"] != seed]
    test = [r for r in eval_pool if r["seed"] == seed]
    profiles, _ = fit_profiles(train, form)
    return {
        "hand_set": sequential_score(test, DEFAULT_PROFILE_MODELS),
        "fitted": sequential_score(test, profiles),
        "fitted_known_kind": sequential_score(test, profiles, known_kind=True),
    }


def fit(observations: Path, out: Path | None, forms: tuple[str, ...], eval_roots: list[str]) -> int:
    rows = load_observations(observations)
    distinct = [r for r in rows if not r["duplicate"]]
    eval_games = {r["game_id"] for r in rows if is_eval_row(r, eval_roots)}
    mix = Counter((r["kind"], r["observed"].value) for r in distinct)
    print(
        f"{len(rows)} opponent decisions from {len({r['game_id'] for r in rows})} games; "
        f"{len(distinct)} distinct for fitting; {len(eval_games)} whole games for scoring"
    )
    if not eval_games:
        print("no evaluation games: pass --eval-root matching the events paths")
        return 1
    for kind in sorted({r["kind"] for r in rows}):
        n = sum(v for (k, _), v in mix.items() if k == kind)
        shares = ", ".join(f"{f.value} {mix[(kind, f.value)] / n:.2f}" for f in ACTION_FAMILIES)
        print(f"  {kind}: {n} decisions — {shares}")

    results = {}
    for form in forms:
        cv = cross_validate(rows, form, eval_roots)
        results[form] = cv
        print(f"\nform={form}, leave-one-seed-out, sequential predict-then-observe:", flush=True)
        print(f"  {'':22s} {'hand_set':>18s} {'fitted':>18s} {'known kind':>18s}")
        for kind in cv["fitted"]:
            h, f, k = cv["hand_set"][kind], cv["fitted"][kind], cv["fitted_known_kind"][kind]
            print(
                f"  {kind:22s} {h['log_loss']:7.4f} / {h['top1']:.3f}"
                f"   {f['log_loss']:7.4f} / {f['top1']:.3f}"
                f"   {k['log_loss']:7.4f} / {k['top1']:.3f}   (n={f['n']})"
            )
    best_form = min(forms, key=lambda f: results[f]["fitted"]["all"]["log_loss"])
    gain = (
        results[best_form]["hand_set"]["all"]["log_loss"]
        - results[best_form]["fitted"]["all"]["log_loss"]
    )
    print(
        f"\nbest form: {best_form}; held-out log-loss gain over hand-set: {gain:+.4f} per decision"
    )

    if out is not None:
        profiles, train_ll = fit_profiles(distinct, best_form)
        payload = {
            "version": "fitted_response_models_v1",
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": str(observations),
            "form": best_form,
            "decisions": len(distinct),
            "eval_roots": eval_roots,
            "train_mean_log_likelihood": {k: round(v, 4) for k, v in train_ll.items()},
            "cross_validation": results[best_form],
            "profiles": {p.value: m.as_payload() for p, m in sorted(profiles.items())},
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out}")
        for profile, model in sorted(profiles.items()):
            if profile is OpponentProfile.RANDOM_LEGAL:
                continue
            prior = ", ".join(f"{f.value} {p:.2f}" for f, p in model.family_prior.items())
            slope = ", ".join(
                f"{f.value} {w:+.2f}" for f, w in (model.family_value_weight or {}).items()
            )
            print(f"  {profile.value}: prior [{prior}]  slope [{slope}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("extract", help="replay archived games into an observation file")
    ex.add_argument("roots", nargs="+", type=Path)
    ex.add_argument("--out", type=Path, default=Path("artifacts/response_fit/observations.jsonl"))
    ex.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    ft = sub.add_parser("fit", help="fit and cross-validate the response likelihoods")
    ft.add_argument("observations", type=Path)
    ft.add_argument("--out", type=Path, default=None, help="write the full-data fit here")
    ft.add_argument("--forms", nargs="+", choices=FORMS, default=list(FORMS))
    ft.add_argument(
        "--eval-root",
        action="append",
        default=[],
        help="score whole games whose events path starts here (repeatable)",
    )
    args = parser.parse_args(argv)
    if args.command == "extract":
        extract(args.roots, args.out, args.workbook)
        return 0
    return fit(args.observations, args.out, tuple(args.forms), args.eval_root)


if __name__ == "__main__":
    raise SystemExit(main())
