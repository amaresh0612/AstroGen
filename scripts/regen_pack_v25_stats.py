"""Regenerate 90-day pack (schema 2.5) and before/after RP stats. Fictional natal only."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from analysis.pack_builder import CALC_ENGINE_VERSION, SCHEMA_VERSION, build_90day_pack
from scripts.generate_natal_ref import build_natal_ref

FICTIONAL_BIRTH = dict(
    name="Test Subject",
    dob=date(1992, 3, 15),
    tob=__import__("datetime").time(10, 30, 0),
    place="Hyderabad, India",
    lat=17.385,
    lng=78.4867,
    tz_name="Asia/Kolkata",
)
LOCK_DT = __import__("datetime").datetime(2026, 10, 1, 9, 0, 0)

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def main() -> None:
    natal = build_natal_ref(**FICTIONAL_BIRTH, lock_dt=LOCK_DT)
    before_path = BUILD / "Test_Subject_90day_pack_Hyderabad_2026-11-22_v24.json"
    before = json.loads(before_path.read_text(encoding="utf-8"))
    bt = before["rp_trigger_windows"]["topics"]

    print("Building 90-day pack", SCHEMA_VERSION, "...")
    pack = build_90day_pack(
        natal_ref=natal,
        start_date=date(2026, 11, 22),
        num_days=90,
        reference_time="09:00",
        prediction_city="Hyderabad, India",
        prediction_lat=17.385,
        prediction_lng=78.4867,
        prediction_tz="Asia/Kolkata",
    )
    out = BUILD / f"Test_Subject_90day_pack_Hyderabad_2026-11-22_v{SCHEMA_VERSION.replace('.', '')}.json"
    out.write_text(json.dumps(pack, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("Wrote", out, "bytes", out.stat().st_size)

    at = pack["rp_trigger_windows"]["topics"]
    topics = [
        "career", "promotion", "wealth", "relationship", "children", "business", "marriage",
    ]
    lines = [
        "# RP topic stats — before (2.4) vs after (2.5)",
        "",
        f"Engine after: `{CALC_ENGINE_VERSION}` · schema `{SCHEMA_VERSION}`",
        "Natal / houses / dasha / prediction location: unchanged.",
        "Matching thresholds (`rp_convergence_v2`): **unchanged**.",
        "",
        "## Totals (diagnostics-only revision — activation counts must match)",
        "",
        "| Topic | houses | before windows | after windows | before strong | after strong | "
        "before minutes | after minutes | before gate days | after gate days |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for t in topics:
        b, a = bt[t]["summary"], at[t]["summary"]
        lines.append(
            f"| {t} | {at[t]['houses']} | {b['windows_total']} | {a['windows_total']} | "
            f"{b['strong_windows']} | {a['strong_windows']} | {b['active_minutes']} | "
            f"{a['active_minutes']} | {b['days_passing_gate']} | {a['days_passing_gate']} |"
        )
    same = all(bt[t]["summary"] == at[t]["summary"] for t in topics)
    lines += [
        "",
        f"All compared topic summaries identical: **{same}**",
        "",
        "## Methodology notes",
        "",
        "- promotion ≡ wealth: identical house set `[2,6,10,11]` → identical activation expected.",
        "- career ⊂ promotion: half-coverage (need 2) lets shared cores activate both.",
        "- relationship / children on this fictional natal: zero dasha L1–L2 → zero windows "
        "(exclusive children sample covered by synthetic regression test).",
        "- See `docs/rp_coverage_semantics.md` and pack `cross_topic_audit`.",
        "",
        "## Cross-topic audit",
        "",
    ]
    audit = pack["rp_trigger_windows"]["cross_topic_audit"]
    lines.append(
        f"- promotion_equals_wealth: "
        f"{audit['career_promotion_wealth']['promotion_equals_wealth']}"
    )
    lines.append(f"- children_vs_relationship: {audit.get('children_vs_relationship')}")
    lines += ["", "## Semantic warnings (after)", ""]
    for w in pack["validation"].get("warnings", []):
        lines.append(f"- {w}")

    lines += ["", "## Accepted window sample (promotion, first listed)", ""]
    pw = at["promotion"]["windows"][:1]
    lines.append("```json")
    lines.append(json.dumps(pw, indent=2))
    lines.append("```")

    lines += ["", "## Representative rejected sample (business)", ""]
    br = at["business"]["diagnostics"].get("representative_rejections") or []
    lines.append(f"Count: {len(br)}")
    if br:
        lines.append("```json")
        lines.append(json.dumps(br[0], indent=2))
        lines.append("```")
    lines.append(
        f"rejection_reason_totals: "
        f"{at['business']['diagnostics'].get('rejection_reason_totals')}"
    )

    lines += ["", "## Activation scope counts", ""]
    for t in ("career", "promotion", "wealth"):
        lines.append(f"- {t}: {at[t]['diagnostics'].get('activation_scope_counts')}")

    stats = BUILD / "rp_v25_before_after.md"
    stats.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", stats)
    print("same totals:", same)
    print("warnings:", len(pack["validation"]["warnings"]))


if __name__ == "__main__":
    main()
