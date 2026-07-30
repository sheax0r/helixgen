"""Lightweight checks on every `.claude/skills/<name>/SKILL.md` in the repo.

Mirrors what the Claude Code skill loader needs to succeed: a YAML frontmatter
block with `name` and `description` keys, combined size ≤ 1024 chars
(Anthropic skill-frontmatter convention) — plus content checks pinning the
CLI-first contract (4.0.0: no MCP server; skills drive the `helixgen` CLI).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"


def _skill_files() -> list[Path]:
    if not SKILLS_ROOT.is_dir():
        return []
    return sorted(SKILLS_ROOT.glob("*/SKILL.md"))


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Return {key: value} from a `---` … `---` YAML frontmatter block at start of file.

    Hand-rolled (no PyYAML dep) — the format is simple enough: single-line
    `key: value` pairs.
    """
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if m is None:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_has_name_and_description(skill_path: Path) -> None:
    text = skill_path.read_text()
    fm = _parse_frontmatter(text)
    assert "name" in fm and fm["name"], f"{skill_path}: missing or empty `name`"
    assert "description" in fm and fm["description"], (
        f"{skill_path}: missing or empty `description`"
    )


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_frontmatter_size_under_1024(skill_path: Path) -> None:
    text = skill_path.read_text()
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert m is not None, f"{skill_path}: no frontmatter block"
    # combined size = name + description (the two fields the loader cares about)
    fm = _parse_frontmatter(text)
    combined = (fm.get("name", "") + fm.get("description", ""))
    assert len(combined) <= 1024, (
        f"{skill_path}: name+description is {len(combined)} chars, > 1024 limit"
    )


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_name_matches_directory(skill_path: Path) -> None:
    fm = _parse_frontmatter(skill_path.read_text())
    assert fm.get("name") == skill_path.parent.name, (
        f"{skill_path}: frontmatter name {fm.get('name')!r} ≠ "
        f"directory name {skill_path.parent.name!r}"
    )


# --- CLI-first contract (4.0.0) ---------------------------------------------

# Removed MCP tool identifiers that must never reappear in skill text.
# (Prose mentions of "MCP" as history — "there is no MCP server" — are fine;
# these are the concrete tool names agents might try to call.)
STALE_MCP_TOKENS = [
    "generate_preset",
    "patch_preset",
    "view_preset",
    "list_blocks(",
    "show_block(",
    "list_irs(",
    "register_ir",  # also catches register_irs (the MCP tools; the CLI verb is register-irs)
    "compute_irhash",
    "discover_irs",
    "controller_mapping(",
    "device_sync_setlist",
    "device_sync_all",
    "device_install_preset",
    "device_setlist_",
    "device_list_presets",
    "device_import_hss",
    "device_export_hss",
    "device_ir_prune",
    "device_set_info",
    "mcp__helixgen__",
    "mcp_server",
    ".mcp.json",
    "MCP mirror",
]


# Underscore-form identifiers that only existed as MCP tool names (the CLI
# verbs are hyphenated) — caught anywhere, even in prose without parens.
STALE_MCP_REGEX = re.compile(
    r"\b(list_blocks|show_block|list_irs|controller_mapping|generate_preset|"
    r"patch_preset|view_preset|register_irs?|compute_irhash|discover_irs)\b"
)


def _stale_hits(text: str) -> list[str]:
    hits = [tok for tok in STALE_MCP_TOKENS if tok in text]
    hits += sorted(set(STALE_MCP_REGEX.findall(text)) - set(hits))
    return hits


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_has_no_stale_mcp_tool_references(skill_path: Path) -> None:
    hits = _stale_hits(skill_path.read_text())
    assert not hits, f"{skill_path}: stale MCP-era references: {hits}"


@pytest.mark.parametrize(
    "doc_path",
    [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "README.md"],
    ids=lambda p: p.name,
)
def test_prose_docs_have_no_stale_mcp_tool_references(doc_path: Path) -> None:
    # Prose docs may reference `.mcp.json`/`mcp_server` historically ("there
    # is no .mcp.json"), but never the removed tool identifiers.
    prose_tokens = [t for t in STALE_MCP_TOKENS if t not in (".mcp.json", "mcp_server")]
    text = doc_path.read_text()
    hits = [tok for tok in prose_tokens if tok in text]
    hits += sorted(set(STALE_MCP_REGEX.findall(text)) - set(hits))
    assert not hits, f"{doc_path}: stale MCP-era references: {hits}"


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_carries_library_env_mechanism(skill_path: Path) -> None:
    """Every skill must get HELIXGEN_LIBRARY to the CLI (bundled-library path)."""
    text = skill_path.read_text()
    assert "HELIXGEN_LIBRARY" in text, f"{skill_path}: no HELIXGEN_LIBRARY mechanism"
    assert "${CLAUDE_PLUGIN_ROOT}/data/library" in text, (
        f"{skill_path}: bundled-library path (${{CLAUDE_PLUGIN_ROOT}}/data/library) missing"
    )


# --- core 0.21.0 vocabulary (grid-slot live-ops, named setlists) -------------

# Dead-vocabulary patterns that must never appear in skills or prose docs.
# (docs/*.md are byte-synced from helixgen-core and exempt — core is
# authoritative there, including its own erratum-history prose.)
STALE_021_PATTERNS = [
    # the dead computed-index rule for live-ops block coordinates
    re.compile(r"\(\s*(?:blks_)?key\s*[-−]\s*1\s*\)\s*/\s*2"),
    re.compile(r"blks_key"),
    # the old closed --setlist choice (throwaway token never worked)
    re.compile(r"user\|factory\|throwaway"),
    re.compile(r"--setlist\s+throwaway\b"),
    # the old 8-bank slot ceiling ("1A".."8D" — real vocabulary runs to 128D;
    # the lookbehind keeps the correct "1A".."128D" from matching)
    re.compile(r"1A.{0,6}(?<!12)8D"),
    # the pre-manifest-v3 top-level manifest path (0.22.0 moved it to
    # ~/.helixgen/setlists/manifest.json; core docs are byte-synced and exempt)
    re.compile(r"\.helixgen/setlists\.json"),
    # the retired `register --doc` companion-markdown flag (manifest v3)
    re.compile(r"register\b[^\n]*--doc\b"),
]


@pytest.mark.parametrize(
    "path",
    _skill_files() + [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "README.md"],
    ids=lambda p: f"{p.parent.name}/{p.name}" if p.name == "SKILL.md" else p.name,
)
def test_no_stale_021_vocabulary(path: Path) -> None:
    text = path.read_text()
    hits = [pat.pattern for pat in STALE_021_PATTERNS if pat.search(text)]
    assert not hits, f"{path}: stale pre-0.21.0 vocabulary: {hits}"


def test_device_skill_documents_grid_slot_liveops() -> None:
    """Live-ops addressing is the DSP grid slot as printed by `device blocks`."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert "grid slot" in text
    assert "device blocks" in text
    # the new 0.21.0 discovery/read verbs
    assert "device params" in text
    assert "device active" in text
    # param values are raw units, never normalized
    assert "RAW units" in text
    # slot vocabulary runs to bank 128
    assert "128D" in text
    # named-setlist targeting on the preset verbs
    assert "--setlist" in text


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_documents_irhash_cache_isolation(skill_path: Path) -> None:
    """Env-prefix isolation guidance must cover the IR-hash cache (backlog #68f)."""
    text = skill_path.read_text()
    assert "HELIXGEN_IRHASH_CACHE" in text, (
        f"{skill_path}: HELIXGEN_IRHASH_CACHE (IR-hash cache file) not documented"
    )
    assert "HELIXGEN_CACHE" in text, (
        f"{skill_path}: HELIXGEN_CACHE (cache dir) not documented"
    )


def test_setup_skill_stale_shadow_recovery_is_color_safe() -> None:
    """`uv tool dir --bin` inside a substitution needs NO_COLOR (backlog #68a)."""
    text = (SKILLS_ROOT / "setup" / "SKILL.md").read_text()
    assert "NO_COLOR=1 uv tool dir" in text
    assert "~/.local/bin/helixgen" in text
    # the unguarded substitution form must not survive anywhere
    for path in _skill_files() + [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "README.md"]:
        assert '"$(uv tool dir' not in path.read_text(), (
            f"{path}: unguarded $(uv tool dir ...) substitution (FORCE_COLOR-unsafe)"
        )


def test_no_mcp_json_in_repo() -> None:
    assert not (REPO_ROOT / ".mcp.json").exists(), (
        ".mcp.json must not exist — the plugin is CLI-first (no MCP server)"
    )


def test_setup_skill_documents_cli_provisioning() -> None:
    text = (SKILLS_ROOT / "setup" / "SKILL.md").read_text()
    assert "uv tool install 'helixgen[device]==" in text
    assert "helixgen --version" in text
    # help-as-contract: capability discovery starts at --help
    assert "helixgen --help" in text
    assert "helixgen device --help" in text


ENGINE_PIN = "0.30.0"  # the core version this plugin release is built against


def test_engine_pin_is_consistent_across_surfaces() -> None:
    """Every pin-carrying surface must state the core pin, and all must agree.

    Also covers extra-widened forms (helixgen[device,analyze]==X.Y.Z) — any
    stated extras combination must pin the same core version.
    """
    pins = set()
    for path in [
        SKILLS_ROOT / "setup" / "SKILL.md",
        SKILLS_ROOT / "tone" / "SKILL.md",
        SKILLS_ROOT / "device" / "SKILL.md",
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / "README.md",
    ]:
        text = path.read_text()
        found = re.findall(r"helixgen\[device\]==([0-9][0-9.]*)", text)
        assert found, f"{path}: no engine pin (helixgen[device]==X.Y.Z) stated"
        pins.update(found)
        # any extras combination anywhere on the surface must pin the same core
        pins.update(re.findall(r"helixgen\[[a-z,]+\]==([0-9][0-9.]*)", text))
        # the `--version` output a surface tells the agent to expect is a second
        # copy of the pin — a half-applied bump would otherwise stay green here
        pins.update(re.findall(r"helixgen, version ([0-9][0-9.]*)", text))
    assert pins == {ENGINE_PIN}, (
        f"engine pin must be exactly {ENGINE_PIN} on every surface: {sorted(pins)}"
    )


# --- core 0.22.0 vocabulary (advisory device locks, manifest v3) --------------


def test_device_skill_documents_device_locks() -> None:
    """The lock model (0.22.0): auto-acquire, contention, session leases."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    # session-lease mechanics: lock with a label, token passthrough, unlock
    assert "session lease" in text.lower()
    assert "--label" in text
    assert "HELIXGEN_LOCK_TOKEN" in text
    assert "device unlock" in text
    # contention behavior: timeout env, holder-naming error, wait/retry
    assert "HELIXGEN_LOCK_TIMEOUT" in text
    assert "naming the holder" in text.lower() or "naming a lock" in text.lower()
    # introspection surface
    assert "lock --status --json" in text
    # the no-`--no-lock` rule, stated as an explicit-user-direction gate
    assert "--no-lock" in text
    assert re.search(r"--no-lock.{0,200}(explicit|user)", text, re.DOTALL | re.IGNORECASE)
    # scope vocabulary + isolation env
    for scope in ("editbuffer", "library", "irs", "globals"):
        assert f"`{scope}`" in text, f"lock scope `{scope}` not named"
    assert "HELIXGEN_LOCKS" in text


def test_device_skill_documents_manifest_v3() -> None:
    """Manifest v3 (0.22.0): new manifest path + per-device observed state."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert "setlists/manifest.json" in text
    assert "devices/<serial>.json" in text


def test_setup_skill_documents_helixgen_home() -> None:
    """HELIXGEN_HOME (0.22.0): the one-knob root + the auto-git-repo behavior."""
    text = (SKILLS_ROOT / "setup" / "SKILL.md").read_text()
    assert "HELIXGEN_HOME" in text
    assert "git_commit_tones" in text
    assert "HELIXGEN_LOCKS" in text


def test_plugin_and_marketplace_versions_agree() -> None:
    plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert plugin["version"] == market["plugins"][0]["version"]


# --- core 0.23.0 / 0.24.0 vocabulary (discover-first IP, loudness phase 2) ----

# The removed baked-in default device IP must never reappear as a default
# story in skills/prose (docs/*.md are byte-synced from core and exempt).
STALE_DEFAULT_IP_PATTERNS = [
    # the literal old default (the maintainer's own DHCP lease)
    re.compile(r"192\.168\.4\.84"),
    # any "defaults to <some IP>" phrasing — there is no default IP in 0.24.0
    re.compile(r"(built-?in|default)\s+(default\s+)?(IP\s+)?`?192\.168", re.IGNORECASE),
    re.compile(r"defaults?\s+to\s+`?\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", re.IGNORECASE),
    # a default-IP story without a literal ("the built-in default IP is used")
    re.compile(r"built-?in\s+default\s+(device\s+)?IP\s+(is|of|`)", re.IGNORECASE),
]


@pytest.mark.parametrize(
    "path",
    _skill_files() + [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "README.md"],
    ids=lambda p: f"{p.parent.name}/{p.name}" if p.name == "SKILL.md" else p.name,
)
def test_no_stale_default_ip_story(path: Path) -> None:
    """0.24.0 removed the baked-in default device IP — nothing may imply one."""
    text = path.read_text()
    hits = [pat.pattern for pat in STALE_DEFAULT_IP_PATTERNS if pat.search(text)]
    assert not hits, f"{path}: stale default-IP vocabulary (0.24.0 removed it): {hits}"


def test_setup_skill_is_discover_first() -> None:
    """Setup finds the device via `device discover`, not by hand (0.24.0)."""
    text = (SKILLS_ROOT / "setup" / "SKILL.md").read_text()
    assert "helixgen device discover" in text
    # the persisted record location
    assert "devices/<serial>.json" in text
    # the resolution chain, stated in order: --ip > env > persisted record
    assert re.search(
        r"`--ip`\s*>\s*`\$HELIXGEN_HELIX_IP`\s*>", text
    ), "setup: resolution chain (--ip > $HELIXGEN_HELIX_IP > record) not stated"
    # no default IP + fail-fast (missing address never stalls)
    assert re.search(r"no built-?in default IP", text, re.IGNORECASE)
    assert re.search(r"fail[s]? fast", text, re.IGNORECASE)
    assert "never stalls" in text
    # the env var is an override, not the primary path
    assert re.search(r"HELIXGEN_HELIX_IP.{0,200}override", text, re.DOTALL)
    # ask-the-user is the fallback only when discovery finds nothing
    assert re.search(r"found nothing.{0,200}ask the user", text, re.DOTALL | re.IGNORECASE)
    # stale-record recovery
    assert re.search(r"Re-run `device discover`", text)


def test_device_skill_documents_ip_resolution() -> None:
    """Device skill: resolution chain, fail-fast, multi-device, stale record."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert "helixgen device discover" in text
    assert "devices/<serial>.json" in text
    assert re.search(r"`--ip`\s*>\s*`\$HELIXGEN_HELIX_IP`\s*>", text), (
        "device: resolution chain (--ip > $HELIXGEN_HELIX_IP > record) not stated"
    )
    assert re.search(r"no built-?in default IP", text, re.IGNORECASE)
    assert re.search(r"fail[s]? fast", text, re.IGNORECASE)
    # multi-device: most recently discovered wins; --ip targets another
    assert re.search(r"most.recent(ly)?\s+discovered", text, re.IGNORECASE)
    # re-discover on network / DHCP lease change
    assert re.search(r"(new network|DHCP lease).{0,200}(stale|discover)", text,
                     re.DOTALL | re.IGNORECASE)


def test_device_skill_documents_normalize() -> None:
    """`device normalize` (0.23.0): dry-run default, local-.hsp-only, sync-to-apply."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert "device normalize" in text
    assert "device measure" in text
    # dry-run by default; --yes is the separate write step
    assert re.search(r"DRY-RUN by default", text)
    assert "--yes" in text
    # --yes writes the LOCAL .hsp only — never the device copy
    assert re.search(r"LOCAL `?\.hsp`?", text), "normalize: local-.hsp-only not stated"
    assert re.search(r"never the device copy|device copy is NOT written", text)
    # the device follows via sync/install
    assert re.search(r"--yes.{0,2000}device sync", text, re.DOTALL), (
        "normalize: sync-to-apply not stated"
    )
    # total-loudness equalization + idempotent re-runs
    assert re.search(r"total\s*loudness", text, re.IGNORECASE)
    assert "idempotent" in text
    # holds the editbuffer scope even in dry-run
    assert re.search(r"normalize.{0,400}even in.{0,20}dry-run", text,
                     re.DOTALL | re.IGNORECASE)


def test_tone_skill_documents_snapshot_edits_and_analyze() -> None:
    """0.23.0 tone-iteration surfaces: set-param --snapshot + analyze-audio."""
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    # per-snapshot surgical edits (flag form and patch-op form)
    assert "--snapshot" in text
    assert re.search(r'"snapshot"\s*:', text), "tone: patch-op snapshot field not shown"
    # analyze-audio: exists, and the [analyze] extra is NOT in the default install
    assert "analyze-audio" in text
    assert "[analyze]" in text
    assert "helixgen[device,analyze]==" in text, (
        "tone: how to add the analyze extra (uv tool install --force) not shown"
    )


# --- core 0.26.0 vocabulary (normalize field guidance + `normalized` record) --


def test_device_skill_documents_normalize_field_guidance() -> None:
    """Hardware-proven normalize run guidance (live session 2026-07-16)."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    # the playing protocol: one riff, played steadily, through the whole run
    assert re.search(r"same riff", text, re.IGNORECASE)
    # --seconds 10 suffices; the default 20 is conservative
    assert "--seconds 10" in text
    assert re.search(r"default\s+20.{0,40}conservative", text, re.DOTALL | re.IGNORECASE)
    # the gate needs pitched, steady playing (~4 s credited per window)
    assert "pitched" in text
    assert re.search(r"4\s?s\b", text)
    # cross-tone matching: always an explicit absolute --target-db
    assert re.search(r"ALWAYS pass an explicit", text)
    assert "--target-db" in text
    # the default-anchor trap: snapshot scope can drag to the quietest snapshot
    assert "quietest" in text
    # the ceiling: output level maxes at +20 dB, clean chains cap the target
    assert re.search(r"\+20\s?dB", text)
    assert re.search(r"ceiling", text, re.IGNORECASE)
    # chain-out clipping: output_db over 0 dBFS, normalize cannot fix it
    assert "output_db" in text
    assert re.search(r"0\s?dBFS", text)
    assert re.search(r"gain.stag", text, re.IGNORECASE)
    # re-runs with a different target are safe (nothing compounds)
    assert re.search(r"different\s+(`?--target-db`?|target)", text)
    assert re.search(r"nothing compounds|no compounding", text, re.IGNORECASE)


def test_device_skill_warns_sync_is_whole_pool_mirror() -> None:
    """The follow-up sync re-pushes EVERY hash-changed managed tone (not just
    the normalized ones) and overwrites hardware-side edits never pulled back."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert re.search(r"re-push(es)?\s+\*{0,2}EVERY", text)
    assert re.search(r"content hash differs", text)
    assert re.search(r"hardware-side edits", text)
    assert re.search(r"never pulled back", text)


def test_device_skill_documents_normalized_library_record() -> None:
    """`device normalize --yes` records a `normalized` record on library
    variants (0.26.0) — summaries in describe/library show, telemetry in
    --json."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert "`normalized`" in text
    assert "library show" in text
    assert re.search(r"library show[^\n]*--json", text)
    assert "per-target" in text


def test_tone_skill_documents_record_capture_extra() -> None:
    """analyze-audio's EXPERIMENTAL --record path needs the [capture] extra."""
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    assert "--record" in text
    assert "[capture]" in text
    assert re.search(r"EXPERIMENTAL.{0,200}--record|--record.{0,200}EXPERIMENTAL",
                     text, re.DOTALL)
    # the Stadium's USB return is the capture source story
    assert re.search(r"USB return", text)


def test_tone_skill_reads_normalized_record_before_tweaks() -> None:
    """The tone skill consumes the `normalized` telemetry: level-match state
    plus chain-out output_db (clipping) before proposing tone tweaks."""
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    assert "`normalized`" in text
    assert "output_db" in text
    assert re.search(r"library show[^\n]*--json", text)
    assert re.search(r"clipping", text, re.IGNORECASE)
    assert re.search(r"gain.stag", text, re.IGNORECASE)


def test_tone_skill_documents_patch_loop() -> None:
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    assert "helixgen patch" in text
    assert "decompile" in text  # states there is NO decompile round-trip
    # The skill must prefer surgical edits for adjustments.
    assert "Adjusting an existing tone" in text


def test_tone_skill_documents_coordinates() -> None:
    txt = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    assert "lane" in txt and "pos" in txt
    assert "duplicate" in txt.lower()


# --- core 0.27.0 vocabulary (loop-source measuring, restore --force refusal,
# telemetry reachability preflight, analyze-audio guardrails, add-guitar) ------


def test_device_skill_documents_loop_source() -> None:
    """`--source loop` (0.27.0): chain-out gating, null gain_db, raw output_db."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert "--source loop" in text
    # loop mode gates on chain-out level (the input-jack gate reads silence)
    assert re.search(r"loop.{0,400}chain-out level", text, re.DOTALL | re.IGNORECASE)
    assert re.search(r"gain_db.{0,60}null|null.{0,60}gain_db", text, re.DOTALL)
    # the cross-target comparison number is the RAW output_db
    assert re.search(r"raw[^\n]{0,80}output_db|output_db[^\n]{0,80}raw", text)
    # one loop, kept replaying across every target of a run
    assert re.search(r"SAME loop", text, re.IGNORECASE)


def test_device_skill_documents_restore_force_refusal() -> None:
    """slots restore --force refuses an occupied named-setlist position (0.27.0)."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert re.search(r"occupied[^\n]{0,80}(setlist|position)", text, re.IGNORECASE)
    assert re.search(r"refus\w+[^.]{0,120}`?--force`?|`?--force`?[^.]{0,120}refus", text)
    assert "incumbent" in text
    # pool semantics unchanged: --force still pushes into an occupied POOL slot
    assert re.search(r"--force[^\n]{0,120}pool|pool[^\n]{0,120}--force",
                     text, re.IGNORECASE)


def test_device_skill_documents_reachability_preflight() -> None:
    """tuner/meters/measure fail fast on an unreachable device; --port honored."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert re.search(r"preflight", text, re.IGNORECASE)
    assert re.search(r"unreachable|powered-off", text, re.IGNORECASE)
    assert "--port" in text


def test_tone_skill_documents_analyze_audio_guardrails() -> None:
    """analyze-audio 0.27.0: capture flags need --record; memory + hop caveats."""
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    # --input/--rate/--channels without --record is now a usage error
    assert "--input" in text and "--rate" in text and "--channels" in text
    assert re.search(r"usage error", text, re.IGNORECASE)
    # whole-file in-memory decode: keep captures short
    assert re.search(r"whole.file into memory", text, re.IGNORECASE)
    assert re.search(r"minutes", text)
    # momentary/short-term maxima ride a 100 ms hop (integrated unaffected)
    assert re.search(r"100\s?ms hop", text)
    assert re.search(r"integrated[^\n]{0,60}unaffected", text, re.IGNORECASE)


def test_device_skill_documents_discover_forget_and_port_default() -> None:
    """#77 surfaces: `--forget` pruning, the persisted nonstandard RPC `port`
    as the `--port` default (2002 otherwise), and empty/whitespace `--ip`
    rejection (behavior change — no longer treated as unset)."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    # pruning a stale persisted record without hitting the network
    assert "--forget SERIAL-OR-IP" in text
    # the persisted nonstandard RPC port becomes the --port default (2002 else);
    # require "nonstandard" coupled to the --port/2002 default so flattening the
    # conditional to a bare "2002" default cannot pass on an unrelated mention.
    assert re.search(r"`--port`[\s\S]{0,160}2002[\s\S]{0,60}nonstandard", text, re.IGNORECASE), (
        "device: --port default (2002 unless nonstandard) not stated"
    )
    # empty/whitespace --ip is rejected (behavior change #77), not treated as unset
    assert "whitespace-only `--ip`" in text
    assert re.search(r"whitespace-only `--ip`[\s\S]{0,160}reject", text, re.IGNORECASE), (
        "device: empty/whitespace --ip rejection not stated"
    )


def test_setup_skill_documents_discover_port_and_ip_rejection() -> None:
    """#77 surfaces in setup's discover section: the persisted nonstandard RPC
    `port` as the `--port` default (2002 otherwise) and the empty/whitespace
    `--ip` rejection (behavior change — no longer treated as unset)."""
    text = (SKILLS_ROOT / "setup" / "SKILL.md").read_text()
    # discover persists a nonstandard port; it becomes the --port default —
    # require "nonstandard" coupled to the --port/2002 default (see device test).
    assert re.search(r"`--port`[\s\S]{0,160}2002[\s\S]{0,60}nonstandard", text, re.IGNORECASE), (
        "setup: --port default (2002 unless nonstandard) not stated"
    )
    # empty/whitespace --ip is rejected (behavior change #77), not treated as unset
    assert "whitespace-only `--ip`" in text
    assert re.search(r"whitespace-only `--ip`[\s\S]{0,160}reject", text, re.IGNORECASE), (
        "setup: empty/whitespace --ip rejection not stated"
    )


def test_setup_skill_documents_add_guitar() -> None:
    """`library add-guitar` (0.27.0) is the core write path for new profiles."""
    text = (SKILLS_ROOT / "setup" / "SKILL.md").read_text()
    assert "library add-guitar" in text
    assert "--short-name" in text
    # an existing profile at slugify(name) is refused — edit it instead
    assert re.search(r"add-guitar.{0,600}refused", text, re.DOTALL | re.IGNORECASE)
    # the old direct-JSON-write creation story must not survive
    assert "no CLI verb to create a profile" not in text


def test_tone_skill_never_gates_normalization_on_path_output() -> None:
    """#91: an absent/null `path.output` means device-default output block, not
    a missing output target — it must never gate the normalization pass. The
    skill also has to say *why* it still steers to the amp channel volume:
    `device normalize` owns the output block and overwrites what is parked
    there (he-06i — the old "the meters tap upstream of `b13`" rationale was a
    false premise, corrected by core PR #51)."""
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    # the guard itself, tied to the normalization pass
    assert "Volume-normalization pass" in text
    assert re.search(
        r"[Nn]ever gate.{0,80}`path\.output`", text, re.DOTALL
    ), "tone: no explicit never-gate-on-path.output guard"
    # what absent/null actually means: device defaults, and every path has b13
    assert re.search(
        r"(absent|null).{0,200}device defaults", text, re.DOTALL | re.IGNORECASE
    ), "tone: absent/null output not explained as device defaults"
    assert re.search(r"0\.0 dB\s*/\s*0\.5 pan", text), (
        "tone: device-default output values (0.0 dB / 0.5 pan) not stated"
    )
    assert "`b13`" in text
    assert "has_output_override" in text
    # why the amp channel volume stays the actuator: normalize owns the output
    # block and a snapshot-scope run overwrites whatever is parked there
    assert re.search(
        r"actuator \*?\*?`device normalize` owns.{0,240}(overwrite|rewrite|discard)",
        text,
        re.DOTALL | re.IGNORECASE,
    ), "tone: normalize-owns-the-output-block rationale not stated"
    # and the retracted premise must be flagged as false, not merely dropped
    assert re.search(
        r"\*\*FALSE\*\*.{0,200}\*\*DOWNSTREAM\*\*", text, re.DOTALL
    ), "tone: the retracted upstream-tap premise is not marked FALSE"


def test_no_skill_claims_the_meter_taps_sit_upstream_of_the_output_gain() -> None:
    """he-06i / core PR #51: measured on Stadium XL fw 1.3.2, a −20 dB
    output-gain write moved the meter −20.04 dB — the taps are DOWNSTREAM.
    The old claim shipped as fact for the whole life of the loudness feature
    and broke `device normalize`; it must not creep back into any skill."""
    stale = re.compile(
        r"(meters?|taps?)[^.\n]{0,120}\bupstream\b[^.\n]{0,120}"
        r"(output[- ]block|output gain|`b13`)",
        re.IGNORECASE,
    )
    for skill in ("tone", "device", "setup"):
        text = (SKILLS_ROOT / skill / "SKILL.md").read_text()
        # the corrections quote the retracted wording; only quoted-and-retracted
        # occurrences are allowed, so require a nearby FALSE/DOWNSTREAM marker
        for m in stale.finditer(text):
            window = text[max(0, m.start() - 400): m.end() + 400]
            assert re.search(r"FALSE|DOWNSTREAM|used to give|old docs", window), (
                f"{skill}: un-retracted 'taps sit upstream of the output gain' "
                f"claim at offset {m.start()}: {m.group(0)!r}"
            )


# --- core 0.29.0: sync recomputes the .hsp hash at sync time (#92) ------------

STALE_REPUSH_PATTERNS = [
    # the pre-#92 story: hash detection compares the recorded hash, so it
    # supposedly can't see an in-place `.hsp` edit at all
    re.compile(r"recorded\s+`?\.hsp`?\s+hash\s+is\s+unchanged", re.IGNORECASE),
    re.compile(
        r"hash-based change\s+detection compares the `?\.hsp`?, not the",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(r"can'?t see a\s+transcoder fix on its own", re.IGNORECASE | re.DOTALL),
]


def test_device_skill_repush_rationale_is_unchanged_bytes_only() -> None:
    """#92: plain sync recomputes the file hash at sync time, so it already
    re-pushes genuinely edited `.hsp` files. `--repush` exists only for the
    unchanged-bytes case (refreshing after a transcoder upgrade) — the skill
    must not imply hash detection is blind to in-place edits."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    stale = [pat.pattern for pat in STALE_REPUSH_PATTERNS if pat.search(text)]
    assert not stale, f"device: pre-#92 --repush rationale survives: {stale}"
    # the load-bearing fact: the hash is recomputed from the file at sync time
    assert re.search(
        r"recomputed from the file at sync time", text, re.IGNORECASE
    ), "device: sync-time hash recomputation (#92) not stated"
    assert re.search(
        r"in-place edit.{0,80}already-synced tone is detected",
        text,
        re.DOTALL | re.IGNORECASE,
    ), "device: in-place-edit detection not stated on the pool-first bullet"
    # and --repush scoped to the unchanged-bytes case, not to edited files
    assert re.search(
        r"`--repush`.{0,400}\*\*only\*\* for the\s+unchanged-bytes case",
        text,
        re.DOTALL,
    ), "device: --repush not scoped to the unchanged-bytes case"


# --- review fixes: durability, library prefix, progress volume, actuator scope -


def test_tone_skill_prefixes_every_helixgen_call_with_the_library() -> None:
    """Every `helixgen` invocation in the tone skill must carry an explicit
    `HELIXGEN_LIBRARY=` prefix — shell exports don't persist across agent Bash
    calls, so a bare call silently resolves against the wrong library. `library
    doc` (step 7a) is the one that regressed."""
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    bare = [
        line.strip()
        for line in text.splitlines()
        if re.match(r"\s*helixgen\s", line)
    ]
    assert not bare, f"tone: unprefixed helixgen invocation(s): {bare}"


def test_tone_skill_warns_bundled_library_is_not_durable() -> None:
    """Step 7 writes the `.hsp` (and 7a its `description_md`) into whatever
    library resolved. Under the bundled-library fallback that is inside the
    plugin, which a `/plugin` update replaces — the skill doing the writing
    must say so, not just the README."""
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    assert re.search(
        r"`/plugin` update can\s+replace", text, re.IGNORECASE
    ), "tone: bundled-library volatility not warned at the write site"
    assert re.search(
        r"~/\.helixgen/library/.{0,60}durable", text, re.DOTALL | re.IGNORECASE
    ), "tone: durable-home alternative not named"


def test_device_skill_warns_bundled_library_irs_are_not_durable() -> None:
    """`register-irs`/`ir-scan` default to `<library>/irs`; under the bundled
    fallback that is the plugin's own tree. The device skill drives IR fixes in
    its troubleshooting table, so it must carry the warning too, not only
    setup."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert re.search(
        r"data/library/irs/.{0,120}`/plugin` update can\s+replace",
        text,
        re.DOTALL | re.IGNORECASE,
    ), "device: bundled-library IR volatility not warned"


def test_device_skill_states_plain_progress_is_per_item() -> None:
    """core's `_SyncProgressRenderer` emits a phase header plus one line per
    item (and per IR upload) in plain mode — not `one-line-per-phase`. An agent
    told to expect a handful of lines misreads ~100 as a failure."""
    text = (SKILLS_ROOT / "device" / "SKILL.md").read_text()
    assert not re.search(
        r"one-line-per-phase", text, re.IGNORECASE
    ), "device: stale `one-line-per-phase` progress claim survives"
    assert re.search(
        r"one line per \*\*?item", text, re.IGNORECASE
    ), "device: per-item progress volume not stated"


def test_tone_skill_scopes_the_output_level_actuator_claim() -> None:
    """`output.level` is not the actuator for the *authoring-time* pass (5.7),
    but `device normalize` does write it. An unqualified "not the
    volume-normalization actuator" contradicts the device skill and CLI.md."""
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    assert re.search(
        r"not\*\*\s+the\s+actuator\s+for\s+the\s+\*authoring-time\*\s+normalization",
        text,
        re.IGNORECASE,
    ), "tone: output-level claim not scoped to the authoring-time pass"
    assert re.search(
        r"actuator `device normalize` owns",
        text,
        re.DOTALL | re.IGNORECASE,
    ), "tone: `device normalize` output-level exception not stated"
