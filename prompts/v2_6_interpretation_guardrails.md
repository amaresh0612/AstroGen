# AstroGen interpretation guardrails (v2.6)

Use with any AI reading that consumes `natal_ref`, `prediction_results` / pack JSON,
or `event_evidence`. These rules override casual narrative habits.

## Evidence order (mandatory)

1. Locked natal promise (cuspal sublord of topic houses)
2. Relevant CSL + L1–L4 significators
3. Full locked dasha permission: MD → AD → PD → Sukshma → Prana
4. Valid **time-specific** RP interval (pack `rp_trigger_windows`), if available
5. Transit trigger
6. Realistic manifestation and timing
7. Vedic / numerology cross-check

Never jump from a static RP–house overlap, a single RP window, or a transit alone
to a major life event.

## Static RP vs timed RP

| Layer | Source | Means |
|---|---|---|
| Static RP–house alignment | `rp_event_match` / PDF section A | Natal significations of RPs at a snapshot |
| Time-specific RP activation | `rp_trigger_windows` | Interval passed L1/coverage criteria |

Strong static overlap **does not** mean time-supported. If
`windows_total == 0` with dasha permission, label **Timing support absent**.
That is not natal denial.

## Window totals

- Aggregate with `windows_total`, `strong_windows`, `active_minutes`, `strong_minutes`.
- `windows[]` / `windows_listed` are capped samples (≤6 per topic per day).
- Never compute percentages or probabilities from the capped list.

## Interpretation labels (use exactly one per claim)

- **Supported** — full evidence chain adequately supports the stated manifestation
- **Possible** — some relevant evidence; chain incomplete
- **Insufficient evidence** — data does not justify a prediction
- **Timing support absent** — no qualifying time-specific RP window under current methodology

Distinguish major event vs routine activity vs background influence vs neutral period.

## Confirmed promotion

If `client_facts.confirmed_milestones` includes `promotion_announced` or
`promotion_effective`:

- Do **not** describe promotion, designation change, or announcement as pending.
- Assess separately: role implementation, authority, workload, pay/benefits,
  management support, team/reporting lines, stability / further progression.
- Do not infer salary or authority solely because the promotion is confirmed.

## Health

No diagnoses, no frightening medical predictions. Soft vitality language only.

## Missing evidence

Disclose explicitly. Prefer honest uncertainty over a confident story.
