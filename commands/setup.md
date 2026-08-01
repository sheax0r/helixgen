---
description: Provision the helixgen CLI, preferences, guitar profiles and the device connection
argument-hint: "[optional: what to set up, e.g. 'my Stadium' or 'a guitar profile for my Tele']"
---

Use the `setup` skill.

$ARGUMENTS

With no arguments, do a full pass and report what is already in place versus
what is missing: the `uv`-provisioned CLI at the pinned version, the block
library, `~/.helixgen/preferences.json` (including the `normalization` block),
guitar profiles, and whether a Stadium has been discovered on the LAN. Offer
the gaps rather than filling them silently — except where the skill says a
value is confirm-once-then-silent.
