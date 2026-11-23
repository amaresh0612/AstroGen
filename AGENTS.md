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

There is **one** Report PDF (unified) and a **separate** AI Calculation Pack ZIP.

The PDF is a **Calculation & Evidence Report** — not a prediction narrative.
No AI summary is embedded in the PDF.

It contains:
- Cover: birth metadata, prediction location, active MD→Sukshma, RP, current transits
- Natal planet/cusp table, chart wheel (when session chart is available), full MD/AD timeline, PD detail, muhurtha
- KP Significator Strength table + Activation Score Card
- Sukshma evidence windows
- Long-term transit windows (Jupiter/Saturn/Rahu/Ketu)
- 90-day Panchanga & Kalam Reference

Prediction location is required before the PDF (or pack) can be generated.

The PDF must **not** contain statements like "Promotion is likely", "You will receive gains", or "Marriage is indicated". Those belong to the AI layer / pack workflow.

---

## JSON outputs

| File | Contents | Role |
|------|----------|------|
| `natal_ref.json` | Birth, planets, cusps, CSLs, significators, locked dasha | Immutable natal source of truth |
| `prediction_results.json` | Dynamic context: panchanga, kalam, hora, RP, transits, event evidence | AI evidence feed for a specific date/time/location |
| `*_90day_pack.json` | Every date/time-dependent calculation for a coverage period, including pre-stored RP | Static feed the AI predicts from without the app |

Never overwrite `natal_ref.json` dynamically. Never merge prediction data into it.

### 90-day pack — schema 2.6

The pack is generated **once per coverage period**; every question inside that
period is answered from the file. See `docs/static_pack_prediction.md`,
`docs/rp_coverage_semantics.md`, `docs/CHANGELOG_pack.md` and `docs/transit_fields.md`.

Schema 2.6 keeps `rp_convergence_v2` thresholds. Adds reproducibility metadata,
static-vs-timed RP usage notes, and interpretation labels. PDF separates static
RP–house alignment from timed `rp_trigger_windows`. Confirmed promotion uses
post-promotion evidence themes (never “pending”). Zero RP windows ≠ denial.
Capped `windows[]` must never be treated as complete totals.

- `days[].ruling_planets` — day lord, gapless ascendant and Moon
  sign/star/sub intervals from local midnight to local midnight, and a
  seven-part snapshot at the reference time. `start`/`end` are local
  wall-clock, half-open `[start, end)`, `24:00:00` = next local midnight.
  Resolve an exact-time RP query by locating the containing interval; use the
  reference snapshot only when the question names no time.
- `rp_trigger_windows` — `rp_convergence_v2` matching (unchanged thresholds) plus
  diagnostics schema 1.0: rejection reason codes, per-day funnels,
  `house_set_relations` (identical / subset peers). Promotion and wealth share
  houses `[2,6,10,11]` — identical activation is expected, not a cache bug.
  Aggregate from `days[]` totals; `windows[]` is capped at 6/topic/day.
  Zero RP windows with dasha permission ≠ denial of natal promise.
- `sukshma_timeline` / `prana_timeline` — gapless fine-dasha coverage with
  parent-child containment checks and second-precision timestamps.
- Never reuse one day's RP for another date, and never treat `generated_at`
  as the prediction date.

### Dasha lock

- `natal_ref["dasha"]["locked_periods"]` is the lock: PD-level rows (MD/AD/PD lord + ISO start/end) covering lock date −1y … +6y, produced once by `analysis.vimshottari.lock_dasha`.
- Every engine reads MD/AD/PD only via `analysis.vimshottari.resolve_dasha(natal_ref, dt)`; intervals are half-open `[start, end)`. Its `source` field is `locked_periods`, `locked_md_ad_pd`, `derived_from_full_timeline`, or `unavailable` — surface it, never hide it.
- Older natal files without `locked_periods` still work but the UI warns; regenerate them.

### Transit house basis

- `transit_house` — natal **Placidus cusp interval** (same basis as natal occupancy).
- `transit_house_sign` — whole-sign count from the natal Lagna sign, for reference only.

### Prediction location in code

Context, almanac, pack and PDF builders raise `analysis.context.PredictionLocationRequired` when lat/lng/tz are missing. `build_enhanced_pdf` also rejects a location that differs from the one in the context.

---

## Tests

```
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests
```

Fixtures use a fictional subject only. Parity tests load `app.py` functions via AST (no Streamlit import).

---

## Code locations

| Path | Role |
|------|------|
| `app.py` | Main Streamlit app (~3.6k lines): chart engine, UI, PDF, AI readings, org charts |
| `enhanced_report_ui.py` | Enhanced report UI: prediction location enforcement, PDF + JSON download |
| `agents/` | Thin OpenAI wrappers (`career_agent`, `relationship_agent`, `overall_agent`) |
| `analysis/` | KP engines: panchanga, hora, kalam, ruling_planets, dasha_fine, significator_strength, promise_denial, context |
| `analysis/kp_constants.py` | Single home for signs, nakshatras, Vimshottari order, kalam slots, time helpers |
| `analysis/vimshottari.py` | Dasha arithmetic mirroring `app.py` (365.25-day year) + `lock_dasha` / `resolve_dasha` |
| `analysis/transits.py` | Sidereal transit snapshot; `transit_house` = natal Placidus cusp interval |
| `scripts/generate_natal_ref.py` | Standalone natal_ref builder (planets = tropical − Lahiri ayanamsa, as `app.py`) |
| `analysis/fine_windows.py` | Sukshma/Prana windows with signified houses (evidence, not score) |
| `analysis/rp_windows.py` | Exact ascendant/Moon sign-star-sub intervals for a local day; `rp_at_local_time` lookup |
| `analysis/rp_triggers.py` | Per-topic RP activation windows, gated on dasha permission |
| `analysis/pack_builder.py` | 90-day static pack (schema 2.2) + its validation layers |
| `tests/` | pytest suite: app.py parity, golden chart, dasha lock, location rule, engines, KP significators |
| `reports/` | PDF builders: unified_pdf (one report), enhanced_pdf, natal_chart_section, almanac, kp_packet |
| `schemas/` | Typed dicts: natal_ref, event_houses, almanac_row, prediction_context |
| `prompts/` | Versioned AI prompt packs |
| `requirements.txt` | Runtime deps: streamlit, openai, swisseph, geopy, reportlab, pillow, etc. |

---

## Scoring model (frozen)

| Layer | Max | Gating |
|-------|-----|--------|
| CSL Direct-House Support | 3 | Does each house's CSL appear in that planet's locked natal `signified_houses` for the **same** house? Occupancy uses **cuspal Placidus intervals**, not whole-sign. |
| Dasha Permission | 3 | Does MD/AD/PD signify (L1–L4) each primary house? ← **gating factor** |
| Sig Quality | 2 | L1/L2/L3 significator bonus |
| **Total** | **8 → scaled to 10** | Zero dasha → cap 4.0 · any dark house → cap 6.0 |

Score is **evidence for the AI**, not the final prediction.

Verdict label is a band of the score (never contradicts it): STRONG ≥8.0 · ACTIVE ≥6.5 · MODERATE ≥5.0 · MIXED ≥4.0 · WEAK <4.0.

### Significators (method 2.0 — `analysis/significator_strength.py`)

Classical KP, strongest first, for planet P with star lord S:
L1 S occupies the house · L2 P occupies it · L3 S owns it · L4 P owns it.
Rahu/Ketu act as agents of their sign lord and same-sign planets; planets in a node's star inherit those agents' occupied (L1) and owned (L3) houses.

`natal_significators(natal_ref)` uses the stored matrix only when `kp_methodology.version` matches; older natal files are recomputed in memory (file untouched) and the UI/pack warn.

### Sukshma / Prana windows (`analysis/fine_windows.py`)

Listed beneath the locked PD with each lord's signified houses and the topics it touches (≥ half of a topic's primary houses). Exposed in `prediction_results.json` (`fine_dasha_windows`, per-topic `sukshma_windows`), the pack's daily dasha block, and a PDF evidence table. **Evidence only — not a scoring layer.**

Topics: `schemas/event_houses.py` — includes promotion (2,6,10,11), job_change (3,5,9,10,12), business (2,7,10,11), travel_home (3,4,9,12), expenses (12).

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
