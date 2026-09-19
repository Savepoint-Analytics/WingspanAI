# Stepping Through a Game: `analysis/game_viewer.py`

Status: built 2026-09-18.

## Why

Paired arms say whether a change helped; they cannot show a person who
knows Wingspan *where* the agent plays badly. The viewer replays an
archived game exactly (every state is reconstructed from the events, so
it is the real state, not a summary) and prints each decision from one
seat's point of view: what that player could see, what they could do, how
the agent ranked it, what it chose and what the choice did. A strategy the
agent keeps missing becomes something to point at — and then a registered
arm.

## Usage

```bash
# the potential_points seat, whole game, to the terminal
python analysis/game_viewer.py artifacts/rr_belief_opp/experiment/<cell>/<batch>/seed_3
# one decision at a time: Enter steps, a lists every legal action, q quits
python analysis/game_viewer.py <game_dir> --interactive
# a slice, with every legal action listed
python analysis/game_viewer.py <game_dir> --turns 12-20 --all-actions
# follow the other seat; show everyone's hidden cards; write a Markdown transcript
python analysis/game_viewer.py <game_dir> --pov player_1 --all-private --out game.md
```

Find games with `find artifacts/<root> -name events.jsonl`; a game
directory is anything holding one. `--others` expands the non-POV seats'
turns from one line to the full view.

## What each decision shows

- **Board**: every player's rows (bird, `e` eggs, `c` cached food, `t`
  tucked), food, hand size, cubes; live score by category; the tray with
  each card's points, habitats and cost; the feeder dice; the four round
  goals with the current one marked.
- **Private information**, POV seat only unless `--all-private`: the hand
  with cost, points, habitats, egg limit, nest, power colour and text; the
  bonus card with its condition.
- **Ranking**: for games recorded from 2026-09-18 on, the search's own
  root values (`search_ranking`, basis `search`), which is what the agent
  chose from; older games fall back to the one-ply evaluator's
  `top_alternatives` (basis `evaluator one-ply`), which can disagree with
  the choice — the example below is one.
- **Evaluator breakdown** of the position after the chosen action
  (playable birds, egg and card conversion, engine power, habitat yield,
  bonus card, round goal, endgame conversion).
- **Search settings** in force (K, opponent model, budget report when
  capped), and the belief posterior about each opponent.
- **Effect**: score, food, hand and egg deltas, and the RNG draws the action
  caused (the cards drawn, the dice rolled).

Scores are live: `score_player` on the current state counts the current
standing on the round in progress as round-goal points — the same
quantity the evaluator sees — so laying two eggs can move the score by
more than two.

## Reading one

```
=== turn 32: round 3, player_2 (potential_points_p1) to act ===
  player_2 ◀ POV: score 32 (birds 19, goals 7, eggs 4, tuck 2); cubes 6; food inv×1 seed×1; hand 2
      W: Belted Kingfisher(4,e2) | Bald Eagle(9)
      hand: Scaled Quail [0vp G seed …]; White-Faced Ibis [8vp W inv×2+fish …]
      bonus: Prairie Manager — birds that can only live in [grassland]
  tray: Hooded Warbler [7vp F inv×2] | Northern Bobwhite [5vp G seed×3] | Red-Breasted Nuthatch [2vp F …]
  ranking (basis: evaluator one-ply):  6.66 Play Scaled Quail … 5.17 Draw tray cards 1, 2 …
  CHOSE: Draw 2 deck cards
  effect: hand 2 → 4; rng: draw_cards_from_deck → ['Wood Stork', "Cooper's Hawk"]
```

The one-ply evaluator liked playing the Quail; the depth-3 search drew two
blind cards instead of the Bobwhite it could see — with a grassland bonus
card in hand and a grassland round goal past. That is the kind of moment
to argue with. Whether it is a fault is a registered arm's job; the viewer
is for finding the candidates.

## Turning a sighting into an arm

1. Note the game, turn and the rule you think the agent broke.
2. Check it is a pattern, not a game: `--turns` around the same situation
   in a few other games of the same root.
3. Register the fix as a switch with a prediction, run the paired arm with
   `analysis/launch_arm.py`, read it with `arm_contrast` and the profile
   report, and add the row to the ledger — adopted or not, with a holdout.
