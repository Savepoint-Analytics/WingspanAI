# Power decision methods: who chooses inside a bird power, and how

Status: **draft plan for Alex's review, 2026-10-08. Nothing here is adopted or
built.** Answers the gap named at the top of `docs/rules/power_handler_registry.md`
and audited in `docs/rules/hidden_power_choices.md`: in 16 handlers covering 112 of
180 powered birds, a choice the rules give the player is made by a fixed rule
inside the transition function. Companion audits: `egg_spending_fidelity.md`,
`card_discard_fidelity.md`.

## Recommendation

1. **One seam, not 16 refactors.** Handlers stop choosing. They raise a typed
   `PowerDecision` and ask a per-player `DecisionResolver` for the answer.
2. **The default resolver is today's code, frozen.** `LegacyHeuristicResolver`
   reproduces every current `min`/`max`/helper call exactly, so with the switch
   off `analysis/base_game_bit_identity.py` stays identical and the archive stays
   replay-valid. Every later method is an opt-in arm.
3. **Write methods per decision kind, not per handler.** The 16 handlers reduce
   to **9 decision kinds** (choose a food, choose an egg target, choose a card to
   keep, and so on). A method written once for a kind covers every handler that
   raises it. Handler-specific overrides are added only where the value is
   genuinely handler-specific (movers, bonus-card keep, extra-bird play).
4. **Three method tiers per kind: heuristic (H), greedy one-step (G),
   search/Bayes (S).** Which tier runs is configured per kind *and per search
   depth* (root / tree / rollout), because a G resolver inside every child
   expansion multiplies search cost by the option count.
5. **Lift into `LegalAction` only when the options are known at action time
   and there is evidence.** That is `move_bird_habitat` today (already a priority-3
   task). Everything whose options depend on a draw or a die roll stays a
   resolver decision, because lifting it would mean enumerating chance outcomes
   or leaking hidden cards into the action space.

## Two findings from reading the code that widen the audit

Both should be checked by Alex against the rulebook and the code before
being treated as settled.

**A. Optional activation applies to every brown power, not just
`discard_to_tuck`.** The core rulebook says of each habitat's brown powers:
"Using each power is optional" / "All powers are optional"
(`rulebook_pdfs/WS_Core_Rulebook.pdf`, PDF pp. 7–9). `hidden_power_choices.md`
names the forced-activation gap for `discard_to_tuck` only. If every handler
fires unconditionally, as that audit says, then *activate or skip* is a hidden
decision on every brown bird. It mostly does not matter, because activating is
usually free value. It matters where activating has a cost or helps an opponent:
`all_players_*` and `each_player_*` powers, `tuck_card` (costs a hand card),
`discard_egg_*`, and movers when the destination is worse than staying. I have
not checked each handler for a skip path; that check is task 1 below.

**B. `pink_reaction` is classed as mechanical but makes three choices.**
`_react_pink_power` calls `_place_eggs_on_player_birds` with no preferred slot
(which bird gets the egg: the first bird in board order with room),
`_gain_preferred_food_from_birdfeeder` (which die), and
`_choose_discard_card_for_food` (which card to tuck). So the 112/180 figure is
an undercount by up to 12 birds. I have not counted how many of the 12 pink
birds reach each branch.

Minor: `power_handler_registry.md` reports 174 powered cards and
`hidden_power_choices.md` reports 180. One of the two denominators is stale or
they count different things; worth one line in whichever doc is wrong.

## Why a resolver seam rather than lifting everything into `LegalAction`

| option | how it works | for | against |
|---|---|---|---|
| **A. Lift all choices into `LegalAction`** | Each power choice becomes a field on the top-level action, enumerated up front | Search sees every choice natively | Many options don't exist yet at action time (the bonus cards drawn, the feeder after an earlier power rerolled it). Enumerating them means enumerating chance outcomes or leaking hidden cards. Branching explodes: `play_additional_bird` alone multiplies by birds × payments |
| **B. Resolver injection (recommended)** | Handler raises `PowerDecision`; the deciding player's resolver answers in-line | Small, incremental, bit-identical by default; works for post-reveal choices; one method serves many handlers | Top-level search sees a resolved choice, not a branch, unless the resolver itself looks ahead |
| **C. Pending-decision state machine** | Transition pauses with `state.pending_decision`; the next "action" is the choice (the OpenSpiel pattern) | Most faithful; the correct long-term shape for the reusable template | Rewrites `apply_action`, replay and every agent loop. Too large before the human games |

B is designed so that C is a mechanical later move: the `PowerDecision` object
B introduces is exactly the object C would park on the state. B's main
weakness (search can't branch) is mostly closed by a G or S resolver at the
root. Value of an action = value with the best sub-choice, which approximates
the lifted tree at a fraction of the branching.

## The interface

```python
class DecisionKind(StrEnum):
    ACTIVATE_OPTIONAL_POWER = "activate_optional_power"   # yes / no
    CHOOSE_FOOD = "choose_food"                           # die, supply food, or give/get pair
    CHOOSE_EGG_TARGET = "choose_egg_target"               # which bird receives an egg
    CHOOSE_EGG_TO_SPEND = "choose_egg_to_spend"           # which bird pays an egg
    CHOOSE_CARD_FROM_HAND = "choose_card_from_hand"       # discard or tuck
    CHOOSE_CARD_TO_KEEP = "choose_card_to_keep"           # from a revealed set
    CHOOSE_HABITAT = "choose_habitat"                     # destination row
    CHOOSE_BIRD_TO_PLAY = "choose_bird_to_play"           # nested play, incl. payment
    CHOOSE_POWER_TO_REPEAT = "choose_power_to_repeat"     # which brown power


class PowerDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    decision_id: str                 # deterministic: game_id:global_turn:depth:seq
    kind: DecisionKind
    handler_key: str
    source_bird: str
    deciding_player_id: str          # NOT always the active player
    options: tuple[DecisionOption, ...]   # typed, canonical order
    depth: int                       # chained-power depth
    habitat: Habitat | None


class DecisionResolver(Protocol):
    method_key: str
    def resolve(self, decision: PowerDecision, observation: PlayerObservation) -> int: ...
```

Five rules that keep the project's guarantees:

1. **Look up the deciding player's resolver, not the active player's.** Pink
   reactions fire on an opponent's turn; `all_players_lay_eggs` has every
   player choose for themselves; `draw_cards_player_select` has opponents pick.
   The engine holds `resolvers: dict[player_id, DecisionResolver]`.
2. **Resolvers see the deciding player's observation only.** A G or S resolver
   that needs futures determinizes (`agents/determinization.py`) rather than
   reading the true deck. The project already measured peeking as worse (−2.4).
3. **Options are emitted in canonical order** (ADR 0004), and any resolver
   randomness is seeded from `decision_id` (ADR 0003). Same seed, same choices.
4. **Every resolved decision is logged** as a new `power_decision_resolved`
   event: kind, handler, options, chosen index, `method_key`, the per-option
   values when the method computed them. Replay feeds the logged choices back
   through a `ReplayResolver`, so replay validation survives non-legacy
   methods.
5. **The manifest records the resolver profile.** A batch is no longer
   described by its search config alone. This also closes the
   "invisible to every manifest" point in `hidden_power_choices.md`.

Lookup order inside a resolver profile: handler-specific override for
`(handler_key, kind)` → kind-level method → `legacy`.

## Method tiers

### Two axes: style and tier

A resolver is defined by two independent settings:

- **Style**: *what the player values*. This is one of the existing
  `StrategyArchetype`s (`egg_focus`, `engine_builder`, `food_acceleration`,
  `card_draw`, `bonus_card_focus`, `round_goal_chase`), expressed as a weight
  vector over the things a power choice can affect: eggs, food, cards, tucks,
  bonus progress, round-goal progress, engine (future activations), and what
  the opponent gains.
- **Tier**: *how far the player looks ahead*. A heuristic looks zero steps
  ahead; greedy looks one step ahead; search looks many.

**Definition, heuristic (H):** a fixed decision rule, aligned with a play
style, that ranks the options from the current observation alone. It does not
simulate any option. It encodes a preference ("an egg-focused player puts the
egg where it advances the egg goal"), not a forecast. Formally, it is
`argmax over options of style_weights · features(option, observation)`, where
the features are read directly off the option and the board, never off a
simulated successor state. Same style, same observation, same choice.

What a heuristic is not:
- **Not greedy.** Greedy applies each option to a state copy and scores the
  result. A heuristic never calls the transition function.
- **Not the evaluator.** Greedy and search use the agent's evaluator, whose
  weights are fit or tuned. A heuristic uses the style's stated preferences,
  so it can be wrong in a way you can read and argue with.

`legacy` is today's code, frozen. It is a heuristic with no style: one generic
rule per handler, such as "emptiest habitat" or "first bird with room". It
exists for bit-identity and as the reference arm. It is not a play style, and
it should not be read as one.

Style also applies above the heuristic tier. Greedy and search can score
outcomes with the style's weights blended into the evaluator. That turns
"style × tier" into a grid of agents, rather than the heuristic tier being the
only place a play style lives.

| tier | what it does | cost | when to use |
|---|---|---|---|
| **H — heuristic** | Style-aligned rule over the observation; no simulation (definition above). `legacy` = today's style-less rules, frozen | ~free | Rollouts; opponents inside search; archetype baselines; opponent-style inference |
| **G — greedy one-step** | Apply each option to a lean state copy; score with the agent's own evaluator (`evaluate_state_potential`); take the max | options × one evaluation | Root and shallow tree; the general cross-handler method |
| **S1 — rollout** | Per option, average short rollouts over K determinized states, rollout policy using H resolvers | options × K × rollout | Post-reveal choices with long-horizon effects: card to keep or discard, bonus keep |
| **S2 — belief-weighted EV** | Expectation over a posterior: bonus-card completion (`belief/bonus_cards.py`), feeder outcomes (`agents/feeder_odds.py`), opponent picks (`search_opponent.py` belief models) | options × posterior samples | Choices whose value hinges on hidden information or on what an opponent does next |
| **S3 — lifted into the tree** | The option is a `LegalAction` field; the depth-3 search branches on it | branching × search | Only where options are known at action time and evidence justifies the branching |

**G's known blind spot, and it bites exactly where the evidence is.** The
evaluator prices birds largely on what their powers *produce*, and 99% of
mover activations record zero yield. A G resolver on the current evaluator
will therefore score every mover destination roughly equally and fix nothing.
Movers need either an evaluator term for **expected future activations of the
bird's row** (cubes left × chance the row is chosen × whether the bird stays
rightmost) or S1 rollouts. The same applies to `ACTIVATE_OPTIONAL_POWER` on
`all_players_*` powers: G needs the opponent's gain priced in, which
`net_value.py`'s opponent-response term already does.

**Expect S2's opponent-facing uses to be small at 2p.** The opponent posterior
in the search loop measured ≈0 points at 2p. Register those arms with a ±1
band, not an expected win.

### Which tier is the default

There are three different defaults. Keeping them apart avoids confusion:

| context | default | why |
|---|---|---|
| Engine default (switch off; every existing agent and batch) | **`legacy` heuristic** | Bit-identity with the archive; nothing changes unless an arm asks for it |
| Proposed production search agent (`PotentialPointsAgent`), once arms justify it | **greedy at the root**, style heuristic in the tree, `legacy` in rollouts | Greedy is where the actual move is decided and the budget is spent; heuristics keep the inner nodes cheap |
| Archetype agents (`StrategyArchetypeAgent`) and opponents inside search | **style heuristic** matching the agent's archetype | These agents *are* a play style; a heuristic is the faithful expression of it |

So greedy is not the engine default; it is the proposed default for the one
decision per turn that matters most. Promoting it there still needs an arm
(build-order task 6).

**A by-product of style heuristics: opponent-style inference.** Because each
style's heuristic is a deterministic rule, every observed power choice is
evidence about the opponent's style. The likelihood of the choice under each
archetype's rule feeds the existing `BeliefSearchOpponentModel` posterior.
Power choices are a cleaner signal than top-level actions, which are confounded
by what the hand allows. Whether that signal is worth anything at 2p is open:
the current opponent posterior measured ≈0.

### Cost control by depth

```yaml
power_resolvers:
  style: engine_builder            # any StrategyArchetype; weights live in the archetype config
  default: {root: greedy, tree: heuristic, rollout: legacy}
  overrides:
    move_bird_habitat:          {root: rollout, tree: greedy, rollout: heuristic}
    draw_bonus_cards_keep_one:  {root: belief_ev, tree: greedy, rollout: legacy}
    play_additional_bird:       {root: greedy, tree: heuristic, rollout: legacy}
  opponents_in_search: {tier: heuristic, style: from_belief}   # or legacy
```

At roughly 1.7 points per doubling of thinking time (cost ledger), a G resolver in
every tree node is only worth it if it beats a deeper search with the same
milliseconds. `docs/architecture/decision_profiling.md`'s points-per-second
ledger is the arbiter: each profile row gets a points-per-second entry before
it can become a default.

## Registry changes

Add to `PowerHandlerMetadata`, separate from `implementation_status` so
*coverage* and *who chooses* are reported separately:

| field | values | purpose |
|---|---|---|
| `decision_kinds` | tuple of `DecisionKind` | which choices this handler raises |
| `choice_fidelity` | `mechanical` / `engine_decided` / `resolver_decided` / `lifted_to_action` | the "coverage is not fidelity" line, made queryable |
| `options_known_at` | `action_time` / `post_reveal` / `mixed` | decides whether lifting is even possible |
| `deciding_players` | `self` / `each_player` / `opponents` | drives rule 1 |
| `available_methods` | method keys | what a profile may select |

A registry test replaces the grep-based re-run of the audit. It runs each handler
on fixture states with a `RecordingResolver` and asserts that every handler with
non-empty `decision_kinds` raises at least one decision, and every handler
marked `mechanical` raises none. A future handler that sneaks in a `min(...)`
over player options then fails a test instead of waiting for the next audit.

## Every registry entry

Card counts are from `hidden_power_choices.md`; "—" means not stated there and
not yet counted. *Lift?* means whether S3 is even possible.

### Handlers with a hidden choice today

In the H column, the text after the arrow lists the **features** the style
heuristic reads for that decision, not one fixed rule. Each style weights the
same features differently. For example, on `lay_egg` an `egg_focus` player
weights round-goal progress highest, and a `bonus_card_focus` player weights
bonus thresholds (Oologist, Breeding Manager) highest. A neutral `balanced`
weighting is the comparison point against `legacy`.

| handler | cards | decision kinds | H: legacy → style-heuristic features | G | S / Bayes | lift? | priority |
|---|---:|---|---|---|---|---|---|
| `move_bird_habitat` | 8 | HABITAT, ACTIVATE | emptiest row → row with most expected remaining activations, never into a row about to be filled to its right | needs the row-activation evaluator term first | **S1 rollouts** across destinations and "stay" | yes (action time) | **1** |
| `tuck_card` | 21 | CARD_FROM_HAND, EGG_TARGET, ACTIVATE | `discard_priority` → plus count-based bonus branch (card gap 2) | yes | S1 when hand > 3 | mixed | **2** |
| `lay_egg` | 12 | EGG_TARGET | first bird with room → goal-, bonus- and threshold-aware (egg defects 1–3) | yes | — | mostly | **2** |
| `draw_bonus_cards_keep_one` | 15 | CARD_TO_KEEP | score-on-current-board → expected end-game score given turns left | yes | **S2**: completion probability from `bonus_cards.py` with deck composition | no (post-reveal) | **3** |
| `play_additional_bird` | 10 | BIRD_TO_PLAY, EGG_TO_SPEND, ACTIVATE | max printed points → reuse `_legal_play_bird_actions` restricted to the habitat, ranked by the bird-value table | **yes, the natural fit**: the candidates are already legal plays | S1 only at root | yes, but branching is large; keep resolver | 4 |
| `draw_cards_then_discard` | 8 | CARD_FROM_HAND | `discard_priority` → shares the CARD_FROM_HAND style heuristic | yes | S1 | no (post-reveal) | 4 |
| `gain_food_from_birdfeeder` | 13 | FOOD | hand-deficit order → deficit weighted by turns-to-play, plus what the remaining dice leave for the next player | yes | **S2**: `feeder_odds` for reroll and denial value | no (feeder may change earlier in the row) | 5 |
| `gain_food_from_supply` | 7 | FOOD | shares FOOD | yes | — | yes | 5 |
| `discard_egg_gain_wild_food` | 5 | ACTIVATE, EGG_TO_SPEND, FOOD | always activate; `egg_spend_order` → shared EGG_TO_SPEND fix | yes | — | yes | 5 |
| `discard_egg_draw_cards` | — (2 in registry table) | ACTIVATE, EGG_TO_SPEND | as above | yes | — | yes | 5 |
| `draw_card` | 3 | CARD_TO_KEEP (tray vs deck) | shares the tray-preference logic in `tray_preference.py` | yes | S2 over deck draw | yes | 6 |
| `all_players_lay_eggs` | 3 | EGG_TARGET ×each player, ACTIVATE | each player uses **their own** resolver | yes for self | S2 for the activate decision: what does it give the opponent | self only | 6 |
| `each_player_gains_birdfeeder_food` | 2 | FOOD ×each player, ACTIVATE | own resolver per player, in turn order | yes | S2 (what's left for whom) | no | 6 |
| `repeat_brown_power` | 2 | POWER_TO_REPEAT | first eligible brown to the left → highest expected yield | **yes**: options = candidate birds, value = repeat their power on a copy | — | yes | 6 |
| `trade_food_with_supply` | 1 | ACTIVATE, FOOD (give, get) | most-abundant → most-needed, plus a decline option | yes | — | yes | 7 |
| `fewest_birds_gain_food` | 1 | FOOD | shares FOOD | yes | — | — | 7 |
| `draw_cards_player_select` | 1 | CARD_TO_KEEP ×each player | highest VP first → each picker's own resolver | yes | **S2**: denial, i.e. what the opponent takes from what you leave (`opponent_fit_denial_gap.md`) | no | 7 |

### Handlers the audit calls mechanical

| handler | cards | remaining decision | plan |
|---|---:|---|---|
| `pink_reaction` | 12 | **EGG_TARGET, FOOD, CARD_FROM_HAND** (finding B) | Reclassify; route through the shared kinds; same priority as the kind it shares |
| `predator_hunt` | 14 | ACTIVATE only | legacy = always; free to activate, so no work beyond the flag |
| `deck_search_tuck_by_wingspan` | 10 | ACTIVATE only | as above |
| `cache_food` | 5 | ACTIVATE only | as above |
| `discard_to_tuck` | 5 | **ACTIVATE** (the one the audit names) | G: activate iff the tucked cards outvalue the food spent |
| `draw_tray_cards` | 1 | ACTIVATE only | as above |
| `all_players_draw_cards` | — (5 in registry table) | ACTIVATE (gives opponents cards) | G with the opponent-gain term |
| `all_players_gain_food` | — | ACTIVATE, plus each player's accept; the registry note says it "assumes all eligible players accept" | own resolver per player |
| `fewest_birds_draw_cards` | — (2 in registry table) | ACTIVATE only | as above |
| `no_power` | 6 | none | none |

## Build order, in one- or two-day tasks

| # | task | success criteria |
|---|---|---|
| 1 | **Seam + legacy resolver.** `PowerDecision`, `DecisionResolver`, `LegacyHeuristicResolver`, per-player lookup; route the 16 handlers plus `_react_pink_power` through it with no behaviour change. Check every handler for a skip path (finding A) and record the result in the registry | `base_game_bit_identity.py` identical; full test suite green; the `RecordingResolver` registry test passes and lists every decision point |
| 2 | **Telemetry + replay.** `power_decision_resolved` event (versioned in `docs/events/`), `ReplayResolver`, resolver profile in the manifest | A 25-game batch with a non-legacy profile replays bit-identically from its own events |
| 3 | **Registry fields** (`decision_kinds`, `choice_fidelity`, …) and the audit doc's numbers regenerated from them | `hidden_power_choices.md`'s inventory table can be printed from the registry; the 174 vs 180 count reconciled |
| 4 | **Movers.** Row-activation evaluator term, style heuristic (engine-weighted features: expected remaining activations per row), S1 resolver. First measure with `analysis/play_counterfactuals.py` on archived states that the alternative destination is worth anything | Counterfactual result recorded first. Then, on an arm: burial rate falls from 51.6%; mover mean round played moves toward 2.13; points delta within the registered band |
| 5 | **Shared EGG_TARGET / EGG_TO_SPEND / CARD_FROM_HAND style heuristics** (shared features, per-style weights), done together with the egg defects 1–3 and card gaps 2–3 already in the task list (same fix shape) | The demonstrated cases in the two fidelity docs reverse; one ablation arm behind `VALUE_RESOURCE_SPENDING` |
| 6 | **Generic G resolver** (one implementation, every kind) at the root only | Points-per-second row in the decision-profiling ledger; adopted only if it beats spending the same milliseconds on search |
| 7 | **Bonus-card keep (S2)** | Beats the current keep rule's pick rate on the 322 measured bonus-card deals (free on archived games, same instrument as the existing keep-model task) |
| 8 | **Optional activation** for the cost-bearing and opponent-feeding powers | Decline rate logged; arm vs legacy-always-activate within a registered band |
| 9 | Later: decide B → C (pending-decision state) as part of `reusable_board_game_ai_template.md` | ADR in `docs/decisions/` with the trigger to revisit |

## Decision record (draft)

- **Decision:** introduce a per-player decision resolver seam with a frozen
  legacy default; write methods per decision kind; tier by search depth; lift
  into the action space only with evidence and action-time options.
- **Why:** it fixes the "invisible to every arm and manifest" problem first and
  keeps bit-identity. It lets one method serve 16 handlers, and it doesn't commit
  the engine to a pending-decision rewrite before the human games.
- **Alternatives:** lift everything (A), pending-decision state machine (C).
- **Revisit when:** a lifted decision (movers) shows the search needs to
  branch on sub-choices more broadly, or when Agricola work needs C for the
  shared template.
