# AstroGen Enhancement PRD
**Version 2.0 | 23 August 2026 | Revised architecture approved**

---

## 1. Executive Summary

AstroGen evolves from a PDF-dependent daily report workflow into a **locked natal reference + deterministic dynamic calculation engine + AI interpretation layer**. The user generates a natal chart once; all subsequent daily, monthly, and long-term questions are answered by combining that locked reference with freshly calculated date-specific data. No new chart or PDF is required for daily use.

**Core principle:** *The PDF is evidence. The engine is the product.*

---

## 2. Product Goal

Provide consistent, auditable, KP-first predictions for daily, short-term, and long-term questions using:
- One permanent locked natal reference (`data/natal_ref.json`)
- A deterministic dynamic calculation engine (`analysis/context.py → PredictionContext`)
- Structured AI interpretation consuming `PredictionContext`

---

## 3. Goals

- One permanent master natal reference — never recalculate without authorization
- Date-specific astronomical and Panchanga data calculated deterministically
- KP as the primary event-permission system
- Vedic astrology as supporting explanation; Numerology as energy/tone layer
- Ruling Planets as a core KP timing layer for every question
- Explicit promise/denial reasoning before timing predictions
- Significator strength classification (Level 1–4, qualitative)
- Daily / monthly / long-term / event-specific query modes
- Lightweight outcome tracking for calibration

---

## 4. Non-Goals (Deferred)

- Automatic birth-time rectification
- Mandatory divisional charts (D2–D12)
- Mandatory Ashtakavarga
- Artificial numeric probability scoring
- Permanent hosted service
- Recalculation of locked natal values without explicit authorization

---

## 5. Report Lock Rule

The natal chart is the locked source of truth.

| Locked (never recalculate) | Calculated dynamically |
|---------------------------|----------------------|
| Birth date / time / place | Transits for any requested date |
| Natal planetary positions | Panchanga, Kalam, Hora |
| House / cusp / sublord values | Ruling Planets for query time |
| Natal dasha framework (MD/AD/PD) | Sukshma / Prana dasha (derived from locked PD) |
| KP significators | Long-term transit windows |
| Numerology (name, life path) | Numerology day number |

Any proposed natal recalculation requires explicit user authorization.

---

## 6. Architecture

### Dependency flow (strict)

```
data/natal_ref.json          ← locked, generated once
        ↓
analysis/context.py          ← date + time + location input
        ↓
PredictionContext             ← single object passed everywhere
        ↓
analysis/* engines            ← significators, promise/denial, etc.
        ↓
reports/* builders            ← PDF sections, almanac
        ↓
Enhanced PDF / AI prompt      ← downstream output
```

### File structure

```
data/
  natal_ref.json              ← locked natal JSON (gitignored, generated once)
  natal_ref_template.json     ← schema template for reference

schemas/
  __init__.py
  natal_ref.py                ← TypedDict matching natal_ref.json
  event_houses.py             ← house clusters per topic
  almanac_row.py              ← single day row TypedDict
  prediction_context.py       ← PredictionContext TypedDict

analysis/
  __init__.py
  panchanga.py                ← Tithi, Vara, Nakshatra, Yoga, Karana + sunrise/sunset
  hora.py                     ← Unequal Hora (day sunrise→sunset, night sunset→sunrise)
  tarabala.py                 ← Tara category + Chandrashtama
  ruling_planets.py           ← Full KP RP set (Day, Asc sign/star/sub, Moon sign/star/sub)
  dasha_fine.py               ← Sukshma (L4) + Prana (L5) derived from locked PD only
  numerology_daily.py         ← Day number per date
  long_term_transits.py       ← Jupiter/Saturn/Rahu/Ketu: sign, house, nak, star lord, sub lord
  significator_strength.py    ← Level 1–4 qualitative classification (no numeric scores)
  promise_denial.py           ← Per-topic: PROMISED/SUPPORTED/CONDITIONALLY SUPPORTED/
                                 WEAK/INCONCLUSIVE/CONFLICTED/NOT SUPPORTED
  almanac_builder.py          ← 60-day batch orchestration
  context.py                  ← PredictionContext orchestrator

reports/
  __init__.py
  pdf/
    __init__.py
    almanac_section.py        ← ReportLab 60-day table pages
    kp_packet_section.py      ← Significator table, promise/denial, transit windows
  enhanced_pdf.py             ← Standalone enhanced PDF builder

scripts/
  generate_natal_ref.py       ← One-time script to create data/natal_ref.json from chart
```

---

## 7. Master Reference Data Model (`natal_ref.json`)

Fields (verified data only — never invent missing values):

```json
{
  "_meta": { "source_report": "", "generated_date": "", "version": "1.0" },
  "birth": { "name": "", "date": "", "time": "", "place": "", "lat": 0, "lng": 0, "tz": "", "ayanamsa": 0 },
  "planets": {
    "Sun": { "longitude": 0, "sign": "", "degree": "", "house": 0, "nakshatra": "", "pada": 0,
             "star_lord": "", "sub_lord": "", "sign_lord": "", "retrograde": false }
  },
  "houses": {
    "1": { "cusp_degree": 0, "sign": "", "degree": "", "nakshatra": "", "star_lord": "", "sub_lord": "" }
  },
  "cuspal_sublords": { "1": "", "2": "" },
  "significators": {
    "Sun": { "occupied_house": 0, "owned_houses": [], "signified_houses": [] }
  },
  "dasha": {
    "locked_md": { "lord": "", "start": "", "end": "" },
    "locked_ad": { "lord": "", "start": "", "end": "" },
    "locked_pd": { "lord": "", "start": "", "end": "" },
    "full_timeline": []
  },
  "numerology": { "name_number": 0, "life_path": 0 }
}
```

---

## 8. Calculation Engines

### Panchanga
Tithi, Vara, Moon Nakshatra/Pada, Yoga, Karana, Sunrise, Sunset, Moonrise, Moonset.

### Hora (Unequal)
Day Hora: sunrise → sunset divided into equal slots.
Night Hora: sunset → next sunrise divided into equal slots.
Correct weekday lord sequence.

### Ruling Planets
Day Lord, Ascendant Sign Lord, Ascendant Star Lord, Ascendant Sub Lord,
Moon Sign Lord, Moon Star Lord, Moon Sub Lord.
Cross-matched against event significators.
**Time and location dependent — reference time must be explicit.**

### Dasha Fine
Sukshma (L4) and Prana (L5) derived strictly from locked PD.
Never replaces locked MD/AD/PD.

### Significator Strength
Level 1: Planet occupies house (strongest)
Level 2: Planet in nakshatra of occupant of house
Level 3: Planet owns the house
Level 4: Planet in nakshatra of house owner
Qualitative only — no numeric scores.

### Promise / Denial
Output states: PROMISED / SUPPORTED / CONDITIONALLY SUPPORTED / WEAK / INCONCLUSIVE / CONFLICTED / NOT SUPPORTED
"Delayed" is an interpretation, not an output state.

### Long-term Transits
Jupiter / Saturn / Rahu / Ketu: sign-change dates, transit house, transit nakshatra, star lord, sub lord, relevant natal planet/cusp, relevant event houses.

---

## 9. Event House Reference

| Topic | Primary Houses |
|-------|---------------|
| Career | 6, 10, 11 |
| Promotion | 6, 10, 11 |
| Job Change | 6, 10, 11, 12 |
| Marriage | 2, 7, 11 |
| Relationship | 5, 7, 11 |
| Children | 5, 11 |
| Property | 4, 11 |
| Travel | 3, 9, 12 |
| Foreign Settlement | 4, 9, 12 |
| Wealth | 2, 6, 10, 11 |
| Education | 4, 5, 9 |

---

## 10. Query Modes

| Mode | Calculation scope |
|------|-----------------|
| DAILY | Full PredictionContext for one date/time |
| MONTHLY | Dasha + transits + 30-day almanac |
| LONG_TERM | Long-term transits + promise/denial + dasha windows |
| EVENT_SPECIFIC | Topic bundle: significators + promise/denial + dasha intersection |

---

## 11. 60-Day Almanac

Optional batch output — inspection/reference view, not core path.
Columns: Date, Vara, Sunrise, Sunset, Tithi, Moon Nak/Pada, Moon Sign, Yoga, Karana,
Rahu Kalam, Yamaganda, Gulika, Tarabala, Chandrashtama, Day#, Active MD/AD/PD, Hora Sequence.

---

## 12. Implementation Phases

| Phase | Deliverable |
|-------|-------------|
| A | schemas/ + data/natal_ref_template.json + scripts/generate_natal_ref.py |
| B | analysis/ engines (panchanga → hora → tarabala → ruling_planets → dasha_fine → numerology_daily → long_term_transits → significator_strength → promise_denial → almanac_builder) |
| C | analysis/context.py (PredictionContext orchestrator) |
| D | reports/ PDF sections + enhanced_pdf.py |
| E | Minimal app.py hook: one st.download_button (explicit approval required) |

---

## 13. Final Principle

> *Astrology should describe reality, not decorate it.*
> KP gives direction and event permission.
> Vedic astrology provides supporting meaning and ease/delay context.
> Numerology provides energy and emotional tone.
> Dynamic calculations provide date-specific triggers.
> Reality decides manifestation.
