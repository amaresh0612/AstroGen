# Professional Report Enhancement Plan

Steering-only document. No application code changes implied.

## Current baseline

AstroGen already delivers:

- Full KP chart (Lahiri, Placidus→sidereal cusps, sublords, padas)
- Vimshottari maha/antar/pratyantar
- KP significators, transits, muhurtha kalas, numerology
- Odia-style lagna chart PNG
- Personal + organisation PDF (ReportLab)
- Concise AI PDF summary + interactive overall/career/relationship readings

## Gap to “professional level”

| Area | Today | Target |
|------|-------|--------|
| AI depth | Short bullets / ~1200 tokens | Multi-section longform with citations |
| Context | Planets + houses + dasha | + significators + AD + topic CSL bundle |
| PDF narrative | Optional thin AI block | Full narrative chapters |
| Prompt ops | Inline `AGENTS` dict | Versioned `prompts/` packs |
| Code shape | Monolith `app.py` | Additive `reports/` + `analysis/` packages |
| QA | Manual | Checklist + golden fixtures |

## Phased plan (additive)

### Phase A — Prompt & context packs

- Add `prompts/v2_*.md`
- Add context builder that includes significators + AD windows

### Phase B — Narrative engine

- `reports/narrative/` assembling section dicts from chart + LLM

### Phase C — Professional PDF

- Parallel `build_professional_personal_pdf` / org variant

### Phase D — UI hook (explicit user approval)

- Single download/button wiring in Streamlit

### Phase E — Hardening

- Anonymized fixtures, checklist automation, prompt regression samples

## Invariants

- Existing chart math remains authoritative
- Existing UX keeps working
- Secrets never committed
