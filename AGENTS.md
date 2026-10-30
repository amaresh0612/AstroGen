# AstroGen — Agent Guide

AstroGen is a **KP (Krishnamurti Paddhati) Vedic astrology** Streamlit app that computes sidereal charts (Lahiri ayanamsa), Vimshottari dashas, KP sublords, significators, transits, muhurtha kalas, numerology, personal and organisation PDF reports, and AI readings (overall / career / relationship).

---

## ✅ V1 Architecture — FROZEN

```
LOCKED NATAL JSON (natal_ref.json)
        ↓
Prediction Date + Time + Prediction Location  ← MUST be explicit, never default to natal
        ↓
Panchanga / Kalam (Rahu/Yama/Gulika) / 24 unequal Horas  ← uses PREDICTION location
        ↓
Ruling Planets  ← uses PREDICTION date/time/location
        ↓
Natal KP Promise (CSL + Significators)
        ↓
MD → AD → PD  ← locked, never recalculated
        ↓
Sukshma / Prana  ← dynamic below locked levels
        ↓
RP confirmation (house-overlap)
        ↓
Long-term transits (Jupiter/Saturn/Rahu/Ketu)
        ↓
Event Activation Score  (0–10, dasha-gated)
        ↓
Manifestation Classification
        ↓
PredictionContext (event_evidence trail)
        ↓
PDF (Calculation & Evidence Report) + prediction_results.json
        ↓
AI INTERPRETER  ← sole source of narrative/predictions
```

**The calculation engine produces evidence. The AI interprets it. Never conflate the two.**

---

## Non-negotiable

- **Do not modify existing application code** unless the user explicitly asks to change a specific file.
- Prefer **additive** work: new modules, new packages, new prompts, new report builders, new tests, new docs, rules, and skills.
- Treat chart math in `app.py` as the source of truth for KP calculations until extracted behind new wrappers.

---

## Critical location rule

> **FOR ANY DATE/TIME-DEPENDENT CALCULATION, THE APPLICATION MUST OBTAIN OR EXPLICITLY RESOLVE THE PREDICTION LOCATION BEFORE CALCULATING SUNRISE, SUNSET, KALAM, HORA, DYNAMIC ASCENDANT OR RULING PLANETS. NATAL/BIRTH LOCATION MUST NEVER BE USED AS A SILENT DEFAULT FOR CURRENT LOCATION. HORA MUST NEVER BE GENERATED BEFORE PREDICTION LOCATION IS KNOWN.**

```
NATAL LOCATION (Bhubaneswar)  →  natal chart only
PREDICTION LOCATION (Hyderabad)  →  all dynamic calculations
```

These are always separate fields. The UI enforces this with a hard block.

---

## PDF role

The PDF is a **Calculation & Evidence Report** — not a prediction narrative.

It contains:
- Natal reference lock (birth, cusps, CSLs, significators, dasha)
- Prediction location confirmation
- Ruling Planets
- KP Activation Score Card (score + KP verdict + dasha activation + manifestations)
- KP Significator Strength table
- Long-term transit windows (Jupiter/Saturn/Rahu/Ketu)
- 60-day Panchanga & Kalam Reference

The PDF must **not** contain statements like "Promotion is likely", "You will receive gains", or "Marriage is indicated". Those belong to the AI layer.

---

## JSON outputs

| File | Contents | Role |
|------|----------|------|
| `natal_ref.json` | Birth, planets, cusps, CSLs, significators, locked dasha | Immutable natal source of truth |
| `prediction_results.json` | Dynamic context: panchanga, kalam, hora, RP, transits, event evidence | AI evidence feed for a specific date/time/location |

Never overwrite `natal_ref.json` dynamically. Never merge prediction data into it.

---

## Code locations

| Path | Role |
|------|------|
| `app.py` | Main Streamlit app (~3.6k lines): chart engine, UI, PDF, AI readings, org charts |
| `enhanced_report_ui.py` | Enhanced report UI: prediction location enforcement, PDF + JSON download |
| `agents/` | Thin OpenAI wrappers (`career_agent`, `relationship_agent`, `overall_agent`) |
| `analysis/` | KP engines: panchanga, hora, kalam, ruling_planets, dasha_fine, significator_strength, promise_denial, context |
| `reports/` | PDF builders: enhanced_pdf, almanac_section, kp_packet_section |
| `schemas/` | Typed dicts: natal_ref, event_houses, almanac_row, prediction_context |
| `prompts/` | Versioned AI prompt packs |
| `requirements.txt` | Runtime deps: streamlit, openai, swisseph, geopy, reportlab, pillow, etc. |

---

## Scoring model (frozen)

| Layer | Max | Gating |
|-------|-----|--------|
| CSL Direct-House Support | 3 | Does each house's CSL appear in that planet's locked natal `signified_houses` for the **same** house? Occupancy uses **cuspal Placidus intervals**, not whole-sign. |
| Dasha Permission | 3 | Does MD/AD/PD cover each primary house? ← **gating factor** |
| Sig Quality | 2 | L1/L2/L3 significator bonus |
| **Total** | **8 → scaled to 10** | Zero dasha → cap 4.0 · any dark house → cap 6.0 |

Score is **evidence for the AI**, not the final prediction.

---

## What NOT to do

- Do not add D2/D4/D7/D9/D10 divisional charts
- Do not add Ashtakavarga
- Do not add birth-time rectification
- Do not add any scoring beyond the 3-layer model above
- Do not let the PDF make predictions — that is the AI's job
- Do not recalculate or overwrite locked MD/AD/PD
- Do not silently use natal location for prediction calculations

---

## Secrets

- `OPENAI_API_KEY` via Streamlit secrets or env
- Never commit `.env` or `.streamlit/secrets.toml`
- Never commit birth data fixtures with real identities
