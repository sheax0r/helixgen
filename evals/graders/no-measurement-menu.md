# Grader: the response must not gate the run on a measurement-mode question

PASS when the response either runs (or states it is running) the
`helixgen device normalize` dry-run, or explains what it found from running
it.

FAIL when the response asks the user ANY of the following before running:

- how they want to feed the measurement signal
- whether to use the cable / the loop / the sample, or to play by hand
- whether to calibrate first
- which normalization mode to use

These are all answered by the dry-run itself, which is free and writes
nothing: it reports whether the stimulus reached the jack, whether the rig is
calibrated, and whether each target is reachable. Presenting them as a choice
sends the user back to hand-playing windows they do not need to play.

ALSO PASS (these are legitimate and must not be marked down):

- asking whether the user has edited tones directly on the device before a
  `device sync`, which would overwrite unpulled device-side edits
- reporting, AFTER the trims, that the rig is uncalibrated and offering
  `device calibrate` as a footnote
- stating that a target came back UNREACHABLE and needs gain staging

Score 1 for PASS, 0 for FAIL. Judge only the gating behavior, not tone,
formatting, or how thorough the plan is.
