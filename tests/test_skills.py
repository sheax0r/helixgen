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


ENGINE_PIN = "0.25.0"  # the core version this plugin release is built against


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
