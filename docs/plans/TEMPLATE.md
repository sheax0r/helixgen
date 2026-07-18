# Plan: <title>

## Context

<1–3 sentences: why this change is needed. Link the coordination-workspace
backlog entry (helix `BACKLOG.md` #NN) and, if this is a core companion,
the helixgen-core PR — agent-facing surfaces ship in sync across repos.>

Standing constraints for any plan in this repo:

- Skills operate through the `helixgen` CLI only — never patch engine
  behavior here; the engine version pin lives in the skills (`setup` step 0,
  echoed in `tone`/`device` and README).
- Never commit paid IR packs, personal device exports, or WAV audio.
- Do not bump `.claude-plugin/*.json` versions unless the plan explicitly
  cuts a release; never touch `stable` or `helixgen--v*` tags by hand.

### Task 1: <name>

- [ ] <concrete step>
- [ ] <concrete step>

### Task 2: <name>

- [ ] <concrete step>
- [ ] <concrete step>

## Validation Commands

Run from the repo root; all must pass before the plan is complete:

```bash
# Skill-doc checks (the repo's only automated test suite; needs just pytest):
# frontmatter validity + <=1024-char size cap, CLI-first content pins
python3 -m pytest tests/

# Plugin/marketplace JSON parity — mirrors the release workflow's own gate
# (release.yml fails the build if the JSON breaks or the versions disagree)
python3 - <<'EOF'
import json
p = json.load(open(".claude-plugin/plugin.json"))
m = json.load(open(".claude-plugin/marketplace.json"))
entry = next(e for e in m["plugins"] if e["name"] == p["name"])
assert entry["version"] == p["version"], (p["version"], entry["version"])
print("plugin/marketplace versions agree:", p["version"])
EOF
```
