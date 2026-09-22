"""
Deterministic Identities - Gas Intelligence Platform
Milestone 2 / Commit 2

Provides file-level and row-level fingerprints so that uploading the same
file (or the same logical rows) twice never duplicates records.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_persian_text(value: Any) -> str:
    """Canonical Persian text: ZWNJ->space, Arabic ye/ke folded, spaces collapsed."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return canon_value(value)
    text = value.replace("\u200c", " ")
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def canon_value(value: Any) -> str:
    """Stable string form of any scalar for fingerprinting."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        return repr(round(value, 6))
    if isinstance(value, int):
        return str(value)
    text = normalize_persian_text(value)
    return text


def row_fingerprint(fields: dict) -> str:
    """sha256 over the canonical field values (order-independent)."""
    payload = json.dumps(fields, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()