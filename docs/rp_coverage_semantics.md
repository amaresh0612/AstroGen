# RP house-coverage semantics (pack schema 2.5)

Matching criterion remains **`rp_convergence_v2`**. Schema 2.5 does **not**
change thresholds, natal significators, `EVENT_HOUSES`, dasha locks, or
prediction location. It documents how coverage works and adds audits so every
activation (or zero-window day) is explainable.

## How matched houses are calculated

1. Take the window’s RP planets that already cleared the L1–L2 topic filter:
   day lord, ascendant sign/star/sub, Moon sign/star/sub.
2. For each such planet, collect primary houses of the **topic under evaluation**
   that the planet signifies at **L1 or L2**.
3. **OR-union** those houses → `matched_houses`.

A house is matched if *any* qualifying RP planet signifies it at L1–L2. There is
no requirement that every primary house appear, and no AND across planets.

## How the minimum coverage threshold is applied

```
min_required = max(1, ceil(len(primary_houses) / 2))
pass iff len(matched_houses) >= min_required
```

Failed intervals receive `HOUSE_COVERAGE_INSUFFICIENT` (often alongside other
reason codes).

| Topic | Primary houses | n | min_required | Example pass | Example fail |
|---|---|---|---|---|---|
| Career | 6, 10, 11 | 3 | 2 | [6, 11] | [11] |
| Promotion | 2, 6, 10, 11 | 4 | 2 | [6, 11] | [6] |
| Wealth | 2, 6, 10, 11 | 4 | 2 | [6, 11] | [2] |
| Relationship | 5, 7, 11 | 3 | 2 | [5, 11] | [5] |
| Children | 5, 11 | 2 | 1 | [5] | [] |

## Why related topics share windows

OR-matching + half-coverage implies:

- **Identical house sets** (promotion ≡ wealth `[2,6,10,11]`): activations are
  always identical. This is correct under house-only matching — not a cache bug.
- **Nested sets** (career ⊂ promotion/wealth; children ⊂ relationship): a matched
  core like `[6,11]` meets career need=2 **and** promotion need=2, so both fire.
  A single house `[5]` meets children need=1 but **fails** relationship need=2.

Half-coverage is **not** selective enough to separate career from promotion when
only the career core matches, nor to separate promotion from wealth at all.

## Is a more topic-sensitive rule justified?

Methodologically discussable (e.g. require a topic-unique house such as 2 for
promotion, or majority `> n/2` for even-sized sets). That would be a **new KP
convention**, change activation counts, and is **not** applied in 2.5.

`criteria.methodology_limitations` and `criteria.coverage_semantics` in the pack
state this explicitly. Zero RP windows with dasha permission still means
**timing support absent**, not denial of natal promise.

## Where to audit in the pack

| Path | Use |
|---|---|
| `rp_trigger_windows.criteria.coverage_semantics` | Full rule + examples |
| `topics.*.diagnostics.coverage_rule` | Per-topic min_required |
| `topics.*.diagnostics.activation_scope_counts` | distinctive vs shared |
| `topics.*.diagnostics.representative_rejections` | Rejected interval samples |
| `cross_topic_audit.children_vs_relationship` | Exclusive children moments |
| `cross_topic_audit.career_promotion_wealth` | Identical/near-identical totals |
| `validation.warnings` | Soft semantic flags (structural PASS) |
