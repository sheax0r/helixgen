"""Adding the generated (device-defs) blocks must not re-point any name a
recipe could already use. The fixture maps every model id, display name and
alias of the library as it stood before the 1.4 generation to the block it
resolved to (helixgen-core `Library.find_block`). The resolution itself lives
in the engine, so this skips where helixgen is not importable."""
import json
from pathlib import Path

import pytest

library = pytest.importorskip("helixgen.library")

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "name_resolution_pre_1_4.json"


def test_every_pre_1_4_name_resolves_to_the_same_block():
    lib = library.Library(ROOT / "data" / "library")
    blocks = lib.list_blocks()
    lib.list_blocks = lambda category=None: blocks  # 730 files, read once
    expected = json.loads(FIXTURE.read_text())
    changed = {}
    for name, model_id in expected.items():
        try:
            got = lib.find_block(name).model_id
        except (KeyError, LookupError):
            got = None
        if got != model_id:
            changed[name] = (model_id, got)
    assert not changed
