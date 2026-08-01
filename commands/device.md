---
description: Push tones to a Helix Stadium over the LAN — install, sync, level-match, back up, or manage setlists and IRs
argument-hint: "[what to do, e.g. 'sync my library', 'level-match these snapshots', 'back up the device']"
---

Use the `device` skill.

$ARGUMENTS

With no arguments, ask what they want to do and offer the common paths:
install or sync authored tones onto the hardware, level-match loudness
(`device normalize`, including the `device calibrate` setup for a recorded
stimulus), back up or restore, or on-device housekeeping (setlists, IRs,
preset colour and notes). Confirm the device is reachable before any write,
and never re-sync without checking for hardware-side edits first.
