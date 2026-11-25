---
name: live
description: Use when the user wants to open the live Helix Stadium workspace in a browser — tweak the loaded tone by hand AND browse/reconcile their tone + IR library against the device, in one window (`helixgen device live`). This is the single surface that replaces the old standalone `library ui`: the active tone as a compact signal-flow canvas of blocks — click a block to edit its knobs in a focus panel, drag to reorder, add blocks from a categorized model browser, and adjective-search highlights the matching blocks + knobs — plus a slide-out LIBRARY DRAWER to search the authored library, see what has drifted from the Stadium, and copy/pull/organize setlists and IRs. Triggers on "open the live editor", "edit a tone by hand", "let me tweak the knobs", "dial it in by hand", "add/swap a block", "reorder the chain", "open my library", "what's on my Helix vs my library", "browse my tones", "reconcile my library", "show me what drifted", "pull the edited tone back", "open the helixgen workspace".
---

# live

Open the one local browser workspace for working with the Stadium live:
`helixgen device live`. It is the chain editor **and** the library hub in a
single window — the chain editor is the frame, the library is a drawer.

- **Chain editor (the frame):** the ACTIVE tone as a compact **signal-flow
  canvas** — each block a glyph tile (category icon + colour + a bypass dot),
  parallel paths drawn as branches. **Click a tile** to edit that block in a
  **focus panel** below (its knobs/switches, plus the amp/EQ/cab lenses and 2nd
  cab). **Drag a tile** to reorder it within its lane; **+ Add block** opens a
  **categorized model browser** (category rail + search); swap a block's model,
  split, add a 2nd cab, remove; bypass per block; undo/redo; device-native Save.
  **Adjective-search** lights the matching tiles (↑/↓ by direction) and the
  specific knobs once a tile is open. Every control writes to the device and is
  heard at once; the page follows the hardware. (Needs device firmware 1.4+.
  Moving a block *across* lanes **is** supported (`move_into_split`); the one
  structural thing the device can't do is collapse a whole parallel lane — there
  is no unsplit/merge op.)
- **Library drawer** (**Tones / Setlists / IRs** tabs): search the authored tone
  + IR library, see each tone's drift from the Stadium (a "changed — pull ←"
  badge), copy a tone onto the device, pull an edited preset back into the
  library, manage setlists and IRs (the IRs tab shows each IR's "Used by…" and a
  guarded remove/delete), and **load any library tone into the chain editor** to
  tweak it.

This verb **supersedes the old `library ui` command** — there is no separate
library launcher any more; the drawer is part of this one surface.

## Launch it — then get out of the way

The library drawer reads the tone library, so resolve `HELIXGEN_LIBRARY` the
same way the other skills do (honor a pre-set env var, else a populated
`~/.helixgen/library/`, else the plugin's bundled
`HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library"`), and carry it on the
call:

```bash
HELIXGEN_LIBRARY="<resolved>" helixgen device live --no-open
```

- **Run it in the background** — it is LONG-RUNNING (serves until Ctrl-C /
  SIGTERM). A few seconds after start it prints
  `live editor: http://127.0.0.1:<port>/`. **Never hand over a URL you have not
  seen printed.** Give the user that URL; where you can open a browser view for
  them (the Claude desktop app's browser pane), do.
- **No device needed to start.** It binds and serves even with no Stadium
  connected: the library drawer opens offline, and the chain fills in when a
  device is discovered. (With a device, it needs firmware 1.4+.)
- **Port busy?** "could not serve the page … is another `helixgen device live`
  already running?" usually means one is: check `http://127.0.0.1:8765/state`
  answers before reusing it, else re-run with `--port-http 0` (a free port).
- **Do not start it with `HELIXGEN_LOCK_TOKEN` set**, and release any
  `device lock` session first (`device unlock`): a held `editbuffer`/`all`
  lease makes the page refuse the knobs, a `library` lease makes it refuse Save
  and the drawer's library actions.
- **Then stop.** The human turns the knobs and drives the drawer. Do **not**
  narrate the page, poll it, or re-read state to "check on" it.
- **You can keep working while it's open (0.79.0).** The page holds **no** device
  lock for its lifetime, so you can go on generating tones and `device copy` /
  `push-ir`-ing them onto the Stadium while the user has the page up — the drawer
  reflects each write live, no reload. (Every drawer/CLI write still takes its
  scope for the instant it runs, so concurrent writes don't trample each other.)

## Saving keeps the library in step for you

Save on the page is the hardware's own in-place Save (device only). The library
drawer notices the drift and offers **"pull ←"** to update the library `.hsp`
from the device — so the user can reconcile right in the window, no manual
`device to-hsp` needed. If they ask you to close the gap from the CLI instead,
see the `device` skill's live-editor section (`device active --json` →
`to-hsp <pool_cid>`).

## Provisioning & isolation

This assumes `helixgen` is installed and current. If it is missing or a verb
fails on version, run the `setup` skill (step 0) first — it provisions the
pinned engine.

For a fully isolated session (tests/sandboxes), set `$HELIXGEN_HOME=<dir>` —
the tone library, device records, the cache and the device-lock leases all
follow it. Finer-grained overrides exist if you need them: `HELIXGEN_CACHE=<dir>`
(the cache directory) and `HELIXGEN_IRHASH_CACHE=<file>` (the IR-hash cache
file, which does not move with `HELIXGEN_IRS`). Normal sessions ignore these.
