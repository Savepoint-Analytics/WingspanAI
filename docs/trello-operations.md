# Trello consumer operations

The pinned Trello workflow reads private board configuration from SPWF_CONFIG
and credentials from the named Actions secrets. SPWF_LIVE=true enables writes;
set it to false to return to an entirely offline preview.

Use a dedicated test card for integration validation. Check the card history and
workflow logs for the move and audit comment, then rerun the event to confirm no
additional writes. Opening a same-repository PR requests Review. Replaying an
older push while that PR is open must preserve Review. Experiment completion
must stop at Review, including when a PR merges.

After activation, record at least ten successful ordinary-work pushes across
fourteen days. Test pushes do not count. Investigate missed or incorrect moves
before adding further integrations. A green consumer job alone is insufficient:
inspect the synchronization result and the card history for errors or partial
move/comment failures. Replays do not repair a missing comment after a move.
