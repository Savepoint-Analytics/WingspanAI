#!/usr/bin/env Rscript
# Hierarchical model of play-level card value with shrinkage.
#
# Layer B model of the synergy programme (docs/agents/synergy_planner_agent.md).
# Card-pair effects are sparse; mechanic-pair effects are not. This fits
#
#   card_advantage ~ round + (1 | bird) + (1 | played_mechanic:board_mechanic)
#
# on the counterfactual play-attribution rows, so each bird's value is shrunk
# toward the mean by how little we have seen of it, and each (played power x
# power already on board) interaction is estimated where the data is dense and
# pooled where it is not. lme4 gives empirical-Bayes (BLUP) shrinkage with
# conditional standard deviations; a full posterior needs brms/Stan, which is
# the natural upgrade once this is worth the compute.
#
# Usage:
#   Rscript analysis/r/play_attribution_hierarchical.R \
#       artifacts/play_counterfactuals/pp_shard*.jsonl \
#       --mechanics artifacts/play_counterfactuals/mechanics.json \
#       --out artifacts/play_counterfactuals/hierarchical
#
# `mechanics.json` (bird name -> power handler key) is written by
# analysis/play_attribution_summary.py --write-mechanics.

suppressPackageStartupMessages({
  library(jsonlite)
  library(dplyr)
  library(lme4)
})

args <- commandArgs(trailingOnly = TRUE)
files <- character()
mechanics_path <- NULL
out_dir <- "artifacts/play_counterfactuals/hierarchical"
i <- 1
while (i <= length(args)) {
  if (args[i] == "--mechanics") { mechanics_path <- args[i + 1]; i <- i + 2 }
  else if (args[i] == "--out") { out_dir <- args[i + 1]; i <- i + 2 }
  else { files <- c(files, args[i]); i <- i + 1 }
}
stopifnot(length(files) > 0, !is.null(mechanics_path))
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

rows <- bind_rows(lapply(files, function(f) stream_in(file(f), verbose = FALSE)))
mechanics <- fromJSON(mechanics_path)
mech_of <- function(name) {
  m <- mechanics[[name]]
  if (is.null(m)) "unknown" else m
}

# One row per (play, mechanic on board): a play with k distinct board powers
# contributes k interaction rows, each weighted 1/k so a crowded board does
# not count more than an empty one.
long <- bind_rows(lapply(seq_len(nrow(rows)), function(r) {
  board <- unique(unlist(rows$board_before[r]))
  board_mechs <- if (length(board) == 0) "empty" else unique(vapply(board, mech_of, ""))
  data.frame(
    play_id = r,
    bird = rows$bird[r],
    round = factor(rows$round[r]),
    played_mechanic = mech_of(rows$bird[r]),
    board_mechanic = board_mechs,
    card_advantage = rows$card_advantage[r],
    weight = 1 / length(board_mechs),
    stringsAsFactors = FALSE
  )
}))
long$pair <- interaction(long$played_mechanic, long$board_mechanic, sep = " x ")

cat(sprintf("plays: %d, interaction rows: %d, birds: %d, mechanic pairs: %d\n",
            nrow(rows), nrow(long), n_distinct(long$bird), n_distinct(long$pair)))

fit <- suppressWarnings(lmer(card_advantage ~ round + (1 | bird) + (1 | pair),
                             data = long, weights = weight, REML = TRUE))
vc <- as.data.frame(VarCorr(fit))
print(vc[, c("grp", "sdcor")], row.names = FALSE)

re <- ranef(fit, condVar = TRUE)
bird_effects <- as.data.frame(re$bird)
bird_effects$bird <- rownames(re$bird)
bird_effects$cond_sd <- sqrt(attr(re$bird, "postVar")[1, 1, ])
bird_effects <- bird_effects %>%
  rename(shrunken_effect = `(Intercept)`) %>%
  left_join(long %>% group_by(bird) %>% summarise(n = n_distinct(play_id), raw_mean = mean(card_advantage)), by = "bird") %>%
  arrange(desc(shrunken_effect))
write.csv(bird_effects, file.path(out_dir, "bird_effects.csv"), row.names = FALSE)

pair_effects <- as.data.frame(re$pair)
pair_effects$pair <- rownames(re$pair)
pair_effects$cond_sd <- sqrt(attr(re$pair, "postVar")[1, 1, ])
pair_effects <- pair_effects %>%
  rename(shrunken_effect = `(Intercept)`) %>%
  left_join(long %>% group_by(pair) %>% summarise(n = n_distinct(play_id)), by = "pair") %>%
  arrange(desc(shrunken_effect))
write.csv(pair_effects, file.path(out_dir, "mechanic_pair_effects.csv"), row.names = FALSE)

cat("\nTop birds (shrunken card value, points above the mean play):\n")
print(head(bird_effects %>% select(bird, n, raw_mean, shrunken_effect, cond_sd), 15), row.names = FALSE)
cat("\nBottom birds:\n")
print(tail(bird_effects %>% select(bird, n, raw_mean, shrunken_effect, cond_sd), 8), row.names = FALSE)
cat("\nTop mechanic-pair interactions (played x on board):\n")
print(head(pair_effects %>% select(pair, n, shrunken_effect, cond_sd), 12), row.names = FALSE)
cat("\nBottom mechanic-pair interactions:\n")
print(tail(pair_effects %>% select(pair, n, shrunken_effect, cond_sd), 8), row.names = FALSE)
cat(sprintf("\nwrote %s\n", out_dir))
