---
name: enhance-astro-reports
description: >-
  Plans and implements additive enhancements toward professional-level KP
  astrology reports (PDF, AI narrative, section structure) for AstroGen.
  Use when improving report quality, expanding PDF/AI readings, designing
  report templates, or upgrading overall/career/relationship deliverables
  without rewriting existing chart math.
---

# Enhance AstroGen Reports

## Mandate

- **Additive only**: new modules under `reports/`, `prompts/`, `analysis/`, `schemas/`.
- Do **not** modify `app.py` or existing agents unless the user explicitly requests a named change.
- Chart truth comes from existing calculators (`calculate_comprehensive_chart`, significators, dashas).

## Workflow

Copy and track:

```
Report enhancement progress:
- [ ] 1. Define report tier (concise / standard / professional)
- [ ] 2. Map required sections to available chart fields
- [ ] 3. Add/update prompt pack in prompts/
- [ ] 4. Add narrative or PDF builder in reports/
- [ ] 5. Validate citations against sample chart_result
- [ ] 6. Document how to wire into UI later (do not wire unless asked)
```

## Professional report tiers

| Tier | Length | AI sections | Timing depth |
|------|--------|-------------|--------------|
| Concise | ~1 page | Persona+Career+Rel+Finance bullets | Current MD/AD only |
| Standard | 3–5 pages | Full topical sections | MD/AD + next 2 windows |
| Professional | 8–15 pages | Full + significators appendix + transit notes | MD/AD/PD + multi-year windows |

Current `_ai_pdf_summary` ≈ Concise. Target enhancements toward **Standard** then **Professional**.

## Section template (professional)

Use this heading order:

1. Client & Chart Metadata
2. Executive Synopsis (8–12 lines, chart-cited)
3. Lagna & Moon Signature
4. KP Significator Overview (topic-relevant houses)
5. Life Path / Persona
6. Career & Profession
7. Relationships & Marriage
8. Wealth & Gains (non-advisory)
9. Timing: Current & Upcoming Dashas
10. Practical Guidance
11. Appendix: Tables / Chart Image

## Evidence citation format

Every substantive paragraph must include at least one of:

- `Lagna CSL = X`
- `Planet in Hn, star-lord Y, sublord Z`
- `Houses signified: …`
- `MD Lord / AD Lord (dates)`

## Related skills

- [craft-kp-prompts](../craft-kp-prompts/SKILL.md) for prompt packs
- [design-pdf-astrology-report](../design-pdf-astrology-report/SKILL.md) for PDF layout
- [extend-astrogen-additively](../extend-astrogen-additively/SKILL.md) for file layout
- Chart field reference: [chart-payload.md](chart-payload.md)
- Quality checklist: [quality-checklist.md](quality-checklist.md)
