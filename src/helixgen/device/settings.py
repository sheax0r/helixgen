"""Global-settings (device *property*) codec + catalog.

The Stadium exposes its global settings — and various live values — as
**properties** in a dotted namespace (``global.*``, ``dsp.globaleq.*``,
``preset.*``, ``volatile.*``). Each property has a **definition** (name, type,
range, enum labels, default) and a **current value**. Both travel over the 2002
RPC channel as ``msgpack`` blobs with a distinctive dialect: the 4-character
field names are encoded as msgpack ``uint32`` (their ASCII big-endian value),
not as strings.

Protocol (hardware-reverse-engineered 2026-07-13, see
``docs/superpowers/specs/2026-07-13-global-settings-re-findings.md``):

- read current value   ``/PropertyValueGet [reqid, key:s]`` → value blob
- read definition      ``/PropertyDefWithKeyGet [reqid, key:s]`` → def blob
- write value          ``/PropertyValueSet [reqid, ctx:i=0, valueblob:b]`` → ``/success``

This module is the **codec** (pure, device-free, unit-tested against golden
blobs). The :class:`~helixgen.device.client.HelixClient` methods that send these
commands live in ``client.py`` and call in here.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, NamedTuple, Optional

# 8-byte magics
VALUE_MAGIC = b"lavppgsm"   # property *value* blob
DEF_MAGIC = b"fedppgsm"     # property *definition* blob


def _require_msgpack():
    try:
        import msgpack
        return msgpack
    except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent
        raise RuntimeError(
            "the device settings codec needs msgpack; install with "
            "`pip install 'helixgen[device]'`"
        ) from exc


def _u32(name: str) -> int:
    """The device's uint32 encoding of a 4-char msgpack field name."""
    return struct.unpack(">I", name.encode("ascii"))[0]


# value-blob field keys
K_KEY = _u32("key_")
K_TYPE = _u32("type")
K_VAL = _u32("val_")
# def-blob field keys
K_DVAL = _u32("dval")
K_NAME = _u32("name")
K_SHRT = _u32("shrt")
K_UNTS = _u32("unts")
K_VMAX = _u32("vmax")
K_VMIN = _u32("vmin")
K_VNME = _u32("vnme")
K_ID = _u32("id__")


class PropertyValue(NamedTuple):
    """A property's current value."""
    key: str
    type: str           # 'f' (float) or 'i' (int)
    value: Any          # float or int


class PropertyDef(NamedTuple):
    """A property's definition (the self-describing catalog entry)."""
    key: str
    name: str           # display name (newlines collapsed to spaces)
    short: str
    type: str           # 'f' or 'i'
    vmin: Any
    vmax: Any
    default: Any
    enum: List[str]     # value labels for enum props (empty if continuous)
    units: int
    id: Optional[int]


def encode_value_blob(key: str, typ: str, value: Any) -> bytes:
    """Build a property *value* blob byte-for-byte as the app does.

    ``typ`` is ``'f'`` (packs ``value`` as msgpack float64) or ``'i'`` (packs as
    int). The map is ``{key_, type, val_}`` with uint32 field keys.
    """
    if typ not in ("f", "i"):
        raise ValueError(f"unsupported property type {typ!r} (want 'f' or 'i')")
    msgpack = _require_msgpack()
    val = float(value) if typ == "f" else int(value)
    payload = msgpack.packb(
        {K_KEY: key, K_TYPE: typ, K_VAL: val}, use_single_float=False)
    return VALUE_MAGIC + payload


def _unpack(blob: bytes, magic: bytes) -> Dict[int, Any]:
    if blob[:8] != magic:
        raise ValueError(
            f"blob magic {blob[:8]!r} != expected {magic!r}")
    msgpack = _require_msgpack()
    return msgpack.unpackb(blob[8:], raw=False, strict_map_key=False)


def decode_value_blob(blob: bytes) -> PropertyValue:
    """Decode a ``lavppgsm`` value blob into a :class:`PropertyValue`."""
    m = _unpack(blob, VALUE_MAGIC)
    typ = m.get(K_TYPE, "f")
    return PropertyValue(key=m.get(K_KEY, ""), type=typ, value=m.get(K_VAL))


def decode_property_def(blob: bytes) -> PropertyDef:
    """Decode a ``fedppgsm`` definition blob into a :class:`PropertyDef`."""
    m = _unpack(blob, DEF_MAGIC)
    dval = m.get(K_DVAL) or {}
    default = dval.get(K_VAL) if isinstance(dval, dict) else None
    typ = dval.get(K_TYPE, "f") if isinstance(dval, dict) else "f"
    name = (m.get(K_NAME) or "").replace("\n", " ")
    enum = list(m.get(K_VNME) or [])
    return PropertyDef(
        key=m.get(K_KEY) or (dval.get(K_KEY) if isinstance(dval, dict) else "") or "",
        name=name,
        short=m.get(K_SHRT) or "",
        type=typ,
        vmin=m.get(K_VMIN),
        vmax=m.get(K_VMAX),
        default=default,
        enum=enum,
        units=m.get(K_UNTS, 0),
        id=m.get(K_ID),
    )


def coerce_value(pdef: PropertyDef, raw: str) -> Any:
    """Coerce a user-supplied string ``raw`` into the value this property wants,
    validating against the definition. Accepts an enum label (case-insensitive)
    or its index for enum props; a number within ``[vmin, vmax]`` otherwise.
    Raises :class:`ValueError` with a helpful message on any mismatch.
    """
    if pdef.enum:
        # match a label (case-insensitive) first, then a bare index
        for i, label in enumerate(pdef.enum):
            if raw.strip().lower() == label.lower():
                return i
        try:
            idx = int(raw)
        except ValueError:
            raise ValueError(
                f"{pdef.key}: {raw!r} is not one of {pdef.enum}")
        if not 0 <= idx < len(pdef.enum):
            raise ValueError(
                f"{pdef.key}: index {idx} out of range for {pdef.enum}")
        return idx
    if pdef.type == "i":
        try:
            val: Any = int(raw)
        except ValueError:
            raise ValueError(f"{pdef.key}: {raw!r} is not an integer")
    else:
        try:
            val = float(raw)
        except ValueError:
            raise ValueError(f"{pdef.key}: {raw!r} is not a number")
    if pdef.vmin is not None and val < pdef.vmin:
        raise ValueError(f"{pdef.key}: {val} below min {pdef.vmin}")
    if pdef.vmax is not None and val > pdef.vmax:
        raise ValueError(f"{pdef.key}: {val} above max {pdef.vmax}")
    return val


def render_value(pdef: PropertyDef, value: Any) -> str:
    """Human string for a current value: an enum label when applicable."""
    if pdef.enum and isinstance(value, int) and 0 <= value < len(pdef.enum):
        return f"{pdef.enum[value]} ({value})"
    return str(value)
