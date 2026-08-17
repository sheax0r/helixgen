# helixgen

A Claude Code plugin that generates Line 6 Helix Stadium presets from natural-language tone descriptions. Ask in plain English — *"Plexi crunch for my Strat, push it for the lead"* — and get a working `.hsp` file you can drop onto your device.

![Demo: register an IR, ask Claude /tone for a U2 "Streets" rhythm clean, generate the .hsp](docs/demo.gif)

> ⚠️ **Unofficial tool — use at your own risk.** Not affiliated with or endorsed by Line 6 / Yamaha (see [Trademark notice](#trademark-notice)). Loading any user-generated preset on your hardware carries risk — rejected loads, corrupted preset slots, on-device crashes. Review what you import. The MIT [LICENSE](LICENSE) disclaims all warranty.

## Invoking the skills by name

Each skill is reachable directly, so you can ask for one instead of hoping it
gets picked up:

| | What it does |
|---|---|
| `/helixgen:setup` | Provision the CLI, preferences, guitar profiles and the device connection |
| `/helixgen:tone` | Design and generate a preset from a tone description |
| `/helixgen:device` | Install, sync, level-match, back up, or manage setlists and IRs |

Each takes free text — `/helixgen:tone lead in Zombie on my EC-1000`.

## Install

helixgen is a Claude Code plugin. Requires **Python 3.11+**.

```
/plugin marketplace add sheax0r/helixgen
/plugin install helixgen@helixgen
```

The plugin bundles the block library and contributes the `/tone`, `setup`, and `device` skills, which drive the engine — the [`helixgen-core`](https://github.com/sheax0r/helixgen-core) package's `helixgen` **CLI** (as of 4.0.0 there is no MCP server; the CLI is the only engine surface). The only thing the plugin needs from your environment is [`uv`](https://docs.astral.sh/uv/) on your `PATH`:

```bash
brew install uv                                        # macOS
curl -LsSf https://astral.sh/uv/install.sh | sh         # or see docs.astral.sh/uv
```

The `setup` skill provisions the engine on first use as an isolated CLI tool — `uv tool install 'helixgen[device]==0.49.0'` (network access required that once; nothing touches your system Python) — and verifies it with `helixgen --version`. That's the whole setup — nothing to `pip install` yourself.

**Using the Python CLI directly** (no plugin)? Same binary — see [`docs/CLI.md`](docs/CLI.md). A standalone install starts with an empty library at `~/.helixgen/library/`, so seed it first with `helixgen bootstrap` (the plugin's skills instead point `HELIXGEN_LIBRARY` at the bundled `data/library`).

## Use it

In any Claude Code session, type something like:

> `/tone Les Paul with stock humbuckers, classic rock / hard rock. Make me one preset with three snapshots: a clean intro, a Plexi crunch for verses, and a singing lead for solos — Slash / Joe Bonamassa territory.`

A good prompt usually includes (a) your guitar (model and pickup type are most useful), (b) the musical style or a band/song reference, and (c) the role(s) you need. The skill will ask you for anything missing.

What the skill does: designs the chain, generates the `.hsp`, and reports back with the signal chain, your guitar-side knob/selector settings, the file path, and one suggested tweak to try after loading. Multi-part requests ("rhythm + lead", "verse + chorus + solo") become snapshots in one preset; fundamentally different sounds get split into separate presets.

**Iterate on the tone.** Generation is the start, not the end. After loading the preset, come back to the same session and describe what's off — *"the lead is too compressed,"* *"verses are too dark, more sparkle,"* *"swap the delay for something shorter and slappier,"* *"clean snapshot needs a touch of room reverb."* Claude adjusts the preset in place and tells you what changed, so you can A/B against the previous version. Same `.hsp` filename by default — just re-import.

## Impulse Responses (IRs)

Stadium identifies user IRs by a content-derived hash, not by filename or slot. helixgen reproduces that 32-character `irhash` bit-identically — no device round-trip — so you can register an IR library once and then reference IRs by `.wav` basename in any preset the `/tone` skill writes (`With Pan` blocks and the rest of the `HX2_ImpulseResponse*` family).

In Claude Code, ask the skill to register an IR — it runs `helixgen register-irs <wav>` (one file) or `helixgen ir-scan <dir>` (a whole directory, recursively, in one run). Memory will remember your IR directory after the first time.

**Prerequisite for direct IR hashing:** computing an IR's hash from a WAV (`register-irs <wav>`, `ir-scan`) needs **libsndfile** (`brew install libsndfile` on macOS; `apt install libsndfile1` on Debian/Ubuntu). Only 48 kHz sources are supported for direct hashing.

**Caveat:** for the `irhash` in a generated preset to actually resolve on the device, the matching WAV must also be on the device. Over the LAN, helixgen uploads it for you — `helixgen device sync` and `device install --auto-irs` push each referenced IR automatically (and `device push-ir` does one by hand); if you load presets via HX Edit/USB instead, import the WAV via the Stadium app's **Librarian → Cab IRs → Import**. If a slot displays "No Model" on the device after loading a preset, that IR isn't on the device yet.

See [`ir-hash-algorithm.md`](https://github.com/sheax0r/helixgen-core/blob/main/docs/ir-hash-algorithm.md) for the hash algorithm and the field-validated reference implementation.

## Loading presets onto your device

On a **Stadium** connected to your LAN, the `/device` skill installs presets directly over the network (see the next section) — no desktop app needed. The manual route below works for any Helix, or when the device isn't network-reachable.

The `/tone` skill writes into your tone library at `library/tones/<variant-slug>.hsp` — no more `/tmp` scratch files. Which library that is depends on your setup: `~/.helixgen/library/` if you built your own, otherwise the plugin's bundled library, which a `/plugin` update can replace — so move tones you want to keep out of it. The skill reports the exact path; `helixgen describe "<tone>"` finds it again later.

**To load on the device:**

1. Connect your Stadium / Helix to your computer via USB.
2. Open Line 6's **HX Edit** application (or whichever Helix management app matches your device — check Line 6's downloads page if unsure).
3. Use the app's import / open command to load the `.hsp` (or `.hlx`) file.
4. Save the loaded preset to a slot on the device.

If HX Edit refuses to open the file, double-check that the chassis in your library matches your hardware (Stadium chassis → `.hsp`, legacy Helix chassis → `.hlx`).

## Control your Stadium over the network (2.0)

As of **2.0**, helixgen can talk to a **Helix Stadium** directly over your LAN —
no editor app required. It speaks the Stadium's own control protocol (OSC over
ZeroMQ; see [`docs/helix-protocol.md`](docs/helix-protocol.md)), so you can list,
read, create, rename, delete, load, save, and live-tweak presets from the CLI.

The plugin's `[device]` extra already includes the transport deps (pyzmq,
msgpack, paramiko). Find your device once — no IP hunting:

```bash
helixgen device discover                 # finds the Stadium via mDNS (subnet-probe fallback) and persists its address

helixgen device list                     # presets in the pool (--setlist also takes device setlist names)
helixgen device active                   # the preset currently active on the device
helixgen device read 904                 # a preset's metadata
helixgen device create --from 904 --pos 7   # copy a preset into a slot
helixgen device rename 930 "My Tone"
helixgen device save "My Tone" --pos 7   # persist the live edit buffer to a slot
helixgen device delete 930               # remove a preset
helixgen device pull 904 backup.sbe      # back up a preset's raw content blob
helixgen device backup --setlist user    # back up a whole setlist to local files
helixgen device push backup.sbe "Clone" --pos 7   # restore/clone a backup
helixgen device install MyTone.hsp "My Tone" --pos 7   # author a helixgen .hsp onto the device (EXPERIMENTAL)
helixgen device list-irs                 # impulse responses on the device (name + hash)
helixgen device push-ir cab.wav          # upload an IR (SFTP; device auto-registers) (EXPERIMENTAL)
helixgen device pull-ir "cab.wav" out.wav  # download an IR by on-device filename (EXPERIMENTAL)
helixgen device measure                  # how loud is the ACTIVE tone while you play (read-only)
helixgen device normalize MyTone.hsp     # level-match its snapshots (dry-run; --yes writes the local .hsp, then re-sync)
```

As of core **0.24.0** there is no built-in default device IP: every `device`
verb resolves `--ip`, then `$HELIXGEN_HELIX_IP`, then the record
`device discover` persisted — and fails fast with a pointer to
`device discover` when none is available. Re-run discover if the device
changes networks or DHCP leases.

IR transfer uses the editor's own SFTP identity (located from your installed Helix
app, never bundled) — see [`helix-sftp-access.md`](https://github.com/sheax0r/helixgen-core/blob/main/docs/helix-sftp-access.md).
Needs the `paramiko` from the `[device]` extra.

`device install` is the **`/tone` → playable-on-your-amp** path: it transcodes
a helixgen-authored `.hsp` directly into device content and installs a new,
playable preset — no editor, no file import, no template (full fidelity:
dual-amp, parallel splits, snapshots, footswitch/EXP assignments).

The `/device` skill drives these same verbs. Only 48 kHz-family
Stadium hardware is supported; this is **Stadium-only** (not legacy Helix), and
it writes to your device — test against an expendable slot first.

As of core **0.22.0**, every device-mutating verb auto-acquires a
**machine-local advisory lock**, so concurrent helixgen processes (or agents)
on the same machine never collide on the device; `helixgen device lock` /
`unlock` / `lock --status` manage session-length leases. See
[`docs/CLI.md`](docs/CLI.md) "Device locks".

## CLI

The `helixgen` CLI is the engine's only surface — the Claude Code plugin's skills drive exactly the same commands you can run by hand: generation, surgical `.hsp` edits (`patch` and the single-op verbs), library inspection, IR management, device control, and ingesting your own preset exports to grow the block library. It's self-documenting: `helixgen --help` orients you, and each verb's `--help` is its full contract.

See [`docs/CLI.md`](docs/CLI.md) for the full surface: install, recipe format, all subcommands, IR registration, library location.

For the underlying Helix Stadium format and hardware model — DSP/path layout, the 8-snapshot model, footswitch/expression-pedal layout, IR hashing, trails — see [`helix-format-reference.md`](https://github.com/sheax0r/helixgen-core/blob/main/docs/helix-format-reference.md).

## Limitations (v1)

- **Device validation:** `.hsp` output has been load-tested on a Helix **Stadium XL** and works. The non-XL **Helix Stadium** uses the same `.hsp` format and should work but is **untested** — the chassis baked into your library carries the device_id of whichever Stadium variant first exported a preset into it, so a chassis built from XL exports might or might not load cleanly on a non-XL Stadium. `.hlx` output is code-complete and round-trips through the parser and a real HX Edit export fixture, but has **never been loaded on a legacy Helix** (Floor / LT / Rack / Native) — treat it as plausibly-working-but-unverified until someone confirms.
- Wire values only — no display-value (0–10) translation.
- Output is not byte-identical to HX Edit's exports; it aims to load correctly.

Footswitch assignment, expression-pedal routing, snapshots, and per-path input routing **are** generated (hardware-validated on a Stadium XL) — you don't have to wire them on-device after loading.

## Acknowledgments

helixgen leans **heavily** on [**sensorium/phelix**](https://github.com/sensorium/phelix) — a community-maintained, hand-curated repository of Helix block JSON files. The `helixgen bootstrap` command clones phelix and ingests its `blocks/` directory; without that pre-extracted catalog the cold-start experience of this tool would be considerably worse.

## Trademark notice

helixgen is an unofficial community project. **Line 6**, **Helix**, **HX**, and related product names are trademarks of **Yamaha Guitar Group, Inc.** helixgen is not affiliated with, endorsed by, or sponsored by Line 6 or Yamaha. References in this project to Line 6 hardware, file formats (`.hlx`, `.hsp`), and model identifiers are descriptive — helixgen generates files intended to be compatible with Line 6 Helix devices but is not a Line 6 product.

If you are a representative of Line 6 / Yamaha and have concerns about this project's name or scope, please open an issue.

## Tests

Skill-doc checks (needs only pytest):

```bash
python3 -m pytest
```

The engine test suite lives in [helixgen-core](https://github.com/sheax0r/helixgen-core).
