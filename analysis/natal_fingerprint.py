"""
Natal chart fingerprint — stable identity for lock validation.

Schema (matches packs generated before the Oct 2026 module restore):
    chart_id  : "{Name}-{YYYYMMDD}-{HHMM}"
    hash      : first 16 hex chars of sha256 over immutable chart content
    version   : natal_ref _meta.version
    locked    : always True
    file_hint : natal_ref_{Name}_{YYYY-MM-DD}.json
"""
from __future__ import annotations

import hashlib
import json


def _hash_payload(natal_ref: dict) -> dict:
    """Immutable chart content only — excludes dasha lock date and _meta timestamps."""
    birth = natal_ref.get("birth", {})
    return {
        "birth": {k: birth.get(k) for k in ("date", "time", "lat", "lng", "tz")},
        "planets": {
            p: round(float(d.get("longitude", 0.0)), 4)
            for p, d in sorted((natal_ref.get("planets") or {}).items())
        },
        "cusps": {
            h: round(float(d.get("cusp_degree", 0.0)), 4)
            for h, d in sorted((natal_ref.get("houses") or {}).items(), key=lambda kv: int(kv[0]))
        },
        "cuspal_sublords": natal_ref.get("cuspal_sublords", {}),
    }


def build_natal_fingerprint(natal_ref: dict) -> dict:
    birth = natal_ref.get("birth", {})
    name = (birth.get("name") or "Chart").replace(" ", "_")
    date_s = (birth.get("date") or "").replace("-", "")
    time_s = (birth.get("time") or "00:00").replace(":", "")[:4]

    digest = hashlib.sha256(
        json.dumps(_hash_payload(natal_ref), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    return {
        "chart_id": f"{name}-{date_s}-{time_s}",
        "hash": digest[:16],
        "version": (natal_ref.get("_meta") or {}).get("version", "1.0"),
        "locked": True,
        "file_hint": f"natal_ref_{name}_{birth.get('date', '')}.json",
    }


def natal_reference_filename(natal_ref: dict) -> str:
    return build_natal_fingerprint(natal_ref)["file_hint"]
