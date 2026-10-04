"""Instrument split in tools/harvest-factory-corpus.py.

Line 6 titles every factory bass preset `BAS …`; the harvester must route those
to the bass corpus and everything else to guitar, or bass amps/cabs/DIs leak
into the guitar baselines the tone skill quotes.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "harvest", REPO_ROOT / "tools" / "harvest-factory-corpus.py")
harvest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harvest)


@pytest.mark.parametrize("name, expected", [
    ("50-13C-BAS-Rock-Legends.hsp", "bass"),
    ("65-17B-BAS-Live-n-Let-DI.sbe", "bass"),
    ("59-15D-BAS-Slap-City", "bass"),
    ("00-1A-Stadium-Rock-Rig.hsp", "guitar"),
    ("03-1D-Brit-MegaGuitar.hsp", "guitar"),
    ("10-3C-Badonkulous.hsp", "guitar"),
    ("99-1A-Bassman-Blues.hsp", "guitar"),   # "Bass" inside a word is not the BAS tag
    ("Rock-BAS-Thing.hsp", "guitar"),        # BAS must lead the title
])
def test_instrument_of(name: str, expected: str) -> None:
    assert harvest.instrument_of(name) == expected


def test_split_by_instrument_keeps_both_keys_and_order() -> None:
    files = [Path("01-1B-Double-Double.hsp"), Path("50-13C-BAS-Rock-Legends.hsp"),
             Path("02-1C-Plexiglass.hsp")]
    got = harvest.split_by_instrument(files)
    assert got == {"guitar": [files[0], files[2]], "bass": [files[1]]}
    assert harvest.split_by_instrument([]) == {"guitar": [], "bass": []}


@pytest.mark.parametrize("fname, instrument", [
    ("factory-corpus.json", "guitar"), ("factory-corpus-bass.json", "bass")])
def test_published_corpora_are_instrument_pure(fname: str, instrument: str) -> None:
    path = REPO_ROOT / "data" / fname
    if not path.exists():
        pytest.skip(f"{fname} not harvested yet")
    c = json.loads(path.read_text())
    assert c["instrument"] == instrument
    assert c["inputs"], "empty corpus"
    assert all(harvest.instrument_of(f) == instrument for f in c["inputs"])
