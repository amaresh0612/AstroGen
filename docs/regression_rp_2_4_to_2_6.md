# RP regression — 2.4 → 2.6 (fixture natal)

**Matching thresholds:** unchanged (`rp_convergence_v2`).  
**Expectation:** activation totals identical; diagnostics / interpretation metadata richer.

Source comparison: `build/Test_Subject_90day_pack_Hyderabad_2026-11-22_v24.json` vs
`build/Test_Subject_90day_pack_Hyderabad_2026-11-22_v26.json`.

| Topic | 2.4 windows | 2.6 windows | Changed? | Reason |
|---|---:|---:|---|---|
| career | 1902 | 1902 | No | Baseline retained |
| promotion | 1905 | 1905 | No | Identical houses with wealth |
| wealth | 1905 | 1905 | No | Identical houses with promotion |
| relationship | 0 | 0 | No | No dasha L1–L2 on fixture |
| children | 0 | 0 | No | Same; exclusive-interval logic covered by synthetic test |
| business | 1905 | 1905 | No | Baseline retained |
| marriage | 0 | 0 | No | No dasha gate on fixture |

### What did change (non-count)

- `criteria.coverage_semantics`, `cross_topic_audit`, `representative_rejections`
- Pack `reproducibility`, expanded `usage` (static vs timed, labels)
- PDF templates: static vs timed RP sections; post-promotion evidence themes
- Consistency gate module + AI guardrail prompt

### Client charts (e.g. 5585 identical career/promotion/wealth)

Same methodology explanation: half-coverage + nested/identical house sets.
Regenerate the **1989** pack in the UI to refresh diagnostics; do not merge with
a 1990 package. Children-only sample `2027-02-17 19:48:48–19:51:34` (house 5)
remains explainable via `cross_topic_audit.children_vs_relationship` after regen.
