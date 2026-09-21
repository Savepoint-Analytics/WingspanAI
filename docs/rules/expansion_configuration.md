# Expansion configuration: content packs, rules modules, and the gates before analysis

Status: decided 2026-09-20 (phase 0 built); nothing beyond the base game is
implemented. Rule references are to the PDFs in `rulebook_pdfs/`
(`WS_European_Rulebook.pdf`, `WS_Oceania_Rulebook.pdf`,
`WS_Asia_Rulebook_r9.pdf`), page numbers as printed.

## Decision

An expansion is **a content pack plus zero or more rules modules**, never one
monolithic alternate ruleset (the May 2026 decision in
`data_and_rule_encoding_recommendations.md`, now built):

- **`ContentPack`** adds cards: birds, bonus cards, round goals. Packs shuffle
  into one deck (every rulebook says so: European p.2, Oceania p.2, Asia
  p.6), so a ruleset lists the packs in play. Core is always present.
- **`RulesModule`** changes how the game is played: legal actions, resources,
  scoring, setup, timing. `base_game_rules` is always present.
- A **ruleset** is the pair, named deterministically by
  `wingspan_ai.content.loader.ruleset_id_for`: `core_base_game_v1` for the
  base game (the historic id every archived event, manifest and database
  row already carries), otherwise `<packs>[__<modules>]_v1` with core first
  and the rest sorted — `core_european_v1`,
  `core_oceania__nectar_rules__revised_player_mat_v1`.
- The ruleset lives on the **catalog** (`ContentCatalog.rulesets[0]`), which
  `setup_base_game` stamps on every `GameState`; events, manifests and the
  database carry it from there. The batch flow takes `content_packs` and
  `rules_modules` and builds the catalog for them.
- The engine **refuses a rules module it does not implement**
  (`rules.base_game.IMPLEMENTED_RULES_MODULES`, `NotImplementedError` at
  setup). A batch that claims nectar rules gets nectar rules or nothing.
  Content packs are not gated: unsupported card powers are tagged by the
  registry (`PowerImplementationStatus`) and can be excluded per batch
  (`power_status_filter`), which is the honest bridge while a pack is
  being implemented — the same bridge the core content crossed in August.

Why this shape: Oceania's new player mat is usable without the rest of
Oceania (rulebook p.2, step 3.b.i), Asia's Duet and Flock modes are modes
of any deck, and European is content plus one timing rule. Packs and
modules compose; a monolithic ruleset per expansion would need every
combination spelled out.

Revisit if: a module turns out to need pack-specific content to make sense
(nectar without nectar birds is legal but pointless), in which case the
loader should warn, not refuse.

## What phase 0 built (2026-09-20)

| Piece | Where | Guard |
|---|---|---|
| Ruleset ids, `build_ruleset`, `normalize_rules_modules` | `content/loader.py` | `tests/test_expansion_configuration.py` |
| `content_packs` / `rules_modules` on `run_seeded_game`, `run_simulation_batch`, `run_round_robin`; recorded per game and per batch in the manifest (`ruleset_id`, `content_packs`, `rules_modules`, `ruleset_ids`) | `flows/` | same |
| Engine refuses unimplemented modules | `rules/base_game.py` | same |
| **Base-game bit-identity**: an explicit `core` + `base_game_rules` batch produces the same action sequence as the default; the mirror probe (seed 11, both rotations) and an `rr_belief_opp` cell replayed on the new code match the archive's action sequences | test + `analysis/base_game_bit_identity.py` (verified 2026-09-20: seed 1, both rotations, identical to the 2026-09-16 archive) | must hold after every phase |
| End-of-round (teal) and end-of-game (yellow) power hooks in `_advance_turn` | `rules/base_game.py` | `tests/test_power_timing.py` |
| `ruleset_id` in every aggregate analysis view; `arm_contrast` pairs only within a ruleset | `analysis/sql/analysis_views.sql`, `analysis/arm_contrast.py` | `apply_sql_views.py --check` |

The evaluator's teal trigger count (`docs/agents/end_of_round_teal_powers.md`)
was already fixed before phase 0; the doc's status line predates the fix.

## Rule deltas by expansion

### European (81 birds, 7 bonus cards, 10 goals)

| Delta | Rule | Reference | Engine status |
|---|---|---|---|
| Teal "round end" powers | Resolve when all turns of the round are done, **before** scoring the round goal; player order from the round's first player; a player orders their own freely; they do not trigger pink powers | p.2 "Bird Powers"; p.1 end-of-round reference tile (powers → goal → cubes → tray → first-player token) | **hook built** (phase 0); handlers per card are phase 1 |
| Action cubes stay on the row until scoring | Some teal powers count cubes on a habitat row (Dunnock: "for each action cube on their [grassland]"); one Oceania goal does too | p.2 "Setup Changes" | **state gap**: `PlayerState` tracks cubes remaining, not cubes placed per habitat; add `action_cubes_placed: dict[Habitat, int]`, reset at round end |
| `*` alternative food cost | Some birds may pay part of their cost differently (Bonelli's Eagle: pay cards from hand instead of food, tuck them) | p.2 | phase 1, per card (a `FoodCost` alternative or a white-power handler) |
| New goal types | Birds in one row, food cost of played birds, birds with tucked cards, white/no-power birds, brown powers, birds worth >4, filled columns, birds in hand, food in personal supply; the **green goal-mat side** is recommended (blue side scores some goals badly) | p.1, p.3 appendix | phase 1: `round_goal` scoring handlers; the scoring-audit utility reports coverage |
| New bonus cards | Behaviorist (columns with 3 power colours), Ethologist (power colours in one habitat), Diet Specialist, Citizen Scientist; existing Cartographer/Anatomist/Photographer gain terms | p.2 | phase 1: `bonus_scoring` handlers (`bonus_card_composition.md` already notes Diet Specialist and Bird Bander are European) |
| Powers that reference other players' boards, cards in hand, excess food | e.g. Griffon Vulture caches per opponent's [predator]; White Wagtail plays a bird if all four action types were used this round (needs per-round action-type tracking) | card text | phase 1, per handler; **state gap**: actions used this round |

Nothing else changes: same mats, dice, food, scoring.

### Oceania (95 birds, 5 bonus cards, 8 goals)

| Delta | Rule | Reference | Engine status |
|---|---|---|---|
| **Nectar** food type | Wild when paying a bird's cost, an "any food" ability, or a mat upgrade; **not** wild for powers naming a specific food; may be a bird's printed cost; the 2-for-1 conversion applies; cannot be traded away in 2-for-1 | p.2–3 "Nectar" | `FoodType.NECTAR` exists; economy is `nectar_rules` module, **not built** |
| Nectar spoils | Unspent nectar in the personal supply is discarded at each round end (back to supply); cached nectar and spent nectar stay | p.2 | module |
| Spent-nectar scoring | Nectar spent goes to the "spent nectar" space of the habitat where it was spent (bird's row, or the row activated); at game end, per habitat: most 5, second 2, ties split rounded down, need ≥1 to qualify | p.3 | module + a seventh score category (`nectar_points`) in `FinalScoreBreakdown`, events, SQL views |
| Nectar dice | The five base dice are replaced; the new dice show nectar (exact faces in `docs/rules/birdfeeder_dice.md` once audited from the components) | p.2 step 3.a | module; seeded roll paths + replay validation are the guard |
| Starting nectar | Choose 5 from cards + standard food as usual, then every player gains 1 nectar | p.2 step 3.d | module (setup) |
| **Revised player mat** | Forest col 2/4: may discard 1 food to **reset the birdfeeder** before gaining; Wetland col 2/4: may discard 1 food to **reset the bird tray** before drawing; order printed on the space | p.3 "New Player Mat Action" | `revised_player_mat` module: new `LegalAction` fields (`reset_birdfeeder`, `reset_tray`) and yield changes; usable without nectar |
| Yellow "game end" powers | Once, after all end-of-round steps of round 4; any order among one player's; no pink triggers | p.3 "Game End Powers" | **hook built** (phase 0); handlers per card are phase 2 |
| End-of-round order with both expansions | round-end powers → discard nectar → score goal → remove cubes → refresh tray → (round 4) game-end powers, else pass first player | p.3 | the nectar discard slots between the two existing calls in `_advance_turn` |
| Flightless birds (`*` wingspan) | Wild for any wingspan condition (predators, ascending/descending bonus cards) | p.3 | phase 2: `wingspan_cm` becomes optional / a wildcard flag |
| Adjacency | Orthogonal: left/right in the row, above/below across rows | p.3 | phase 2: a board-geometry helper (columns are slot indices) |
| Data Analyst bonus cards | Longest ascending/descending wingspan run per habitat, ties allowed | p.5 | phase 2 |

### Asia (90 birds, 13 bonus cards + 3 shared with core, 12 goals)

| Delta | Rule | Reference | Engine status |
|---|---|---|---|
| Standard game | "No new rules to learn unless playing Duet or Flock"; cards shuffle in | p.6 | phase 3 is content only: teal 16, yellow 3, brown 54, white 15, pink 2 |
| Beak direction | Cards face left/right; some Asia bonus cards and goals count them | workbook column `Beak direction`; rulebook goal appendix | phase 3: already a workbook field; scoring handlers |
| Duet mode (2p) | Replaces the goal mat with the Duet map; place a Duet token on the map each time a bird is played; Duet goals; scoring for largest contiguous group | p.6 (setup), p.10 red boxes, `ROUND END—DUET` p.9 | `duet_mode` module: **deferred** — a map state, new goal family, new scoring; structurally the largest change and it only exists at 2p |
| Flock mode (6–7p) | Two groups with their own tray and feeder, shared goals and pink powers, two simultaneous active players, turn-order dial; needs two decks | p.7 | `flock_mode` module: **deferred** — player-count and concurrency changes outside the research programme's 2–3p focus |

## Gates a ruleset must pass before its first ledger row

1. **Content loads** without `ContentLoadError` for the pack set (all three
   do today: European 261 birds / 33 bonus / 26 goals, Oceania 275 / 31 / 24,
   Asia 270 / 39 / 28 with core).
2. **Powers**: `audit_power_coverage` at 100% classified for the pack, or the
   unclassified cards excluded by `power_status_filter` with provenance in the
   manifest (today's text-template pass: European 88%, Oceania 89%, Asia 95%
   — matched to a template, not verified for teal/yellow semantics). Each new
   handler gets a row in `tests/test_power_handlers.py` and a source
   reference in the registry.
3. **Scoring**: bonus-card and round-goal audit at 100% for the pack.
4. **Rules modules** the ruleset names are in `IMPLEMENTED_RULES_MODULES`,
   each with fixture tests citing the rulebook page.
5. **Replay-validated 25-game smoke batch** under the ruleset, deterministic
   across two processes (ADR 0004) — the dice change in Oceania is the risk.
6. **Base-game bit-identity still holds** (the phase 0 guards).
7. **Rule audit against the PDF** for every delta row above, recorded in
   this document's tables.
8. **Roster viability**: the scripted archetypes and the champion play legal,
   sensible games under the module (nectar demand, reset actions); otherwise
   roster arms measure the roster's confusion, not the expansion.
9. **A baseline arm** for the ruleset (`rr_<ruleset>_base`, 80 paired games
   at 2p), the root every later arm on that ruleset pairs against.

## Order and cost

| Phase | Scope | Days | Compute |
|---|---|---|---|
| 1 | European: content, ~10 unclassified templates, teal handlers, action-cube-per-row state, 7 bonus / 10 goal handlers, audit | 3–5 | smoke + baseline arm (~1 h) |
| 2 | Oceania: `nectar_rules` (economy, spoilage, dice, seventh score category), `revised_player_mat`, yellow handlers, flightless/adjacency, audit | 8–12 | smoke, determinism check, baseline arm |
| 3 | Asia content: handlers, beak goals/bonus, audit | 5–8 | smoke + baseline arm |
| 4 | Per-ruleset re-instrumentation: bird play values, bonus keep study, synergy bench, oracle posteriors, fitted profiles; one baseline per player count studied | ~1 week of compute, little code | — |
| — | Duet, Flock, Automa | deferred | — |

Analysis on a ruleset starts when it passes its gates and has its baseline
arm — European first, not after all three. Cross-ruleset comparisons are
unpaired by construction (different decks): n ≥ 200 at a ±3 limit, or
paired only within a ruleset. Say which in the ledger row.

## For the template

Packs, modules, ruleset ids, the setup-time refusal and the ruleset grain
in the analysis layer know nothing about Wingspan. A second game supplies
its own pack and module enums and its own `IMPLEMENTED_RULES_MODULES`.
