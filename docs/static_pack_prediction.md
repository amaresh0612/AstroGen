# Static Pack Prediction — generate once, predict from files

Pack schema **2.2** · engine `AstroGen-KP-v2.2`

The astrology app is a **one-time calculation source**. You generate the AI
Calculation Pack for a coverage period, upload the files to your AI project,
and every question inside that period is answered from those files. No website
visit, no API, no chart regeneration, no natal rebuild.

---

## The four files

| File | Role | Regenerate |
|---|---|---|
| `natal_ref_*.json` | Locked natal chart: planets, cusps, CSLs, significators, locked dasha | Never (immutable) |
| `*_90day_pack_*.json` | Every date- and time-dependent calculation for the coverage period | When the period runs out |
| `kp_rules.json` | Topic house map + KP evaluation order | Rarely |
| `longterm_transits_*.json` | Slow-planet ingresses over 5 years | Rarely |

---

## What changed in 2.2

Before 2.2, Ruling Planets were deliberately **not** stored. The pack said
"calculate dynamically at exact query time", which meant a question about a
future date had no RP evidence unless you went back to the app and generated a
fresh single-moment snapshot for that date. In practice that produced the
failure this release fixes: a November RP snapshot sitting beside January
panchanga data, with no honest way to combine them.

Four of the seven RPs (day lord and the Moon trio) were always derivable from
the daily panchanga block. The ascendant trio was the real gap, because the
ascendant sub lord changes roughly 249 times a day and no single daily value
can represent it.

2.2 stores the complete set.

### Added

| Path | Contents |
|---|---|
| `days[].ruling_planets` | Day lord, gapless ascendant and Moon sign/star/sub intervals for the whole local day, and a seven-part snapshot at the reference time |
| `rp_trigger_windows` | Per-topic activation windows and per-day counts for all 16 `kp_rules.json` topics |
| `sukshma_timeline` | Every Sukshma window overlapping the coverage period, in order |
| `usage` | Machine-readable rules for date selection, exact-time lookup, aggregation and out-of-range disclosure |
| `validation.trust_status.ruling_planets` | RP presence, timezone, gapless coverage, interval-count sanity |
| `validation.trust_status.rp_trigger_windows` | Topic coverage, significator validity, in-range dates |
| `validation.rp_summary` | Day count, interval counts, windows per topic, coverage, reference timezone |

### Unchanged

Daily panchanga, sunrise/sunset, Rahu Kalam, Yamaganda, Gulika, the 24 horas,
tarabala, numerology, MD/AD/PD/Sukshma/Prana, transits, natal fingerprint,
natal lock metadata, ayanamsa, prediction location and companion-file
references all keep their existing field names and values. 2.2 extends the
daily record; it does not restructure it.

---

## The daily ruling-planets block

```jsonc
"ruling_planets": {
  "date": "2027-01-18",
  "weekday": "Monday",
  "timezone": "Asia/Kolkata",
  "utc_offset": "+0530",
  "day_lord": "Moon",
  "coverage": { "start": "...T00:00:00+05:30", "end": "...T00:00:00+05:30",
                "local_day_minutes": 1440 },
  "interval_fields": ["start","end","sign","sign_lord","nakshatra","star_lord","sub_lord"],
  "reference_snapshot": { "day_lord": "...", "ascendant": {...}, "moon": {...},
                          "rp_list": [...], "local_time": "...", "reference_time": "09:00" },
  "ascendant_windows": [ ["00:00:00","00:00:55","Virgo","Mercury","Chitra","Mars","Jupiter"], ... ],
  "moon_windows":      [ ["00:00:00","01:43:54","Aries","Mars","Krittika","Sun","Moon"], ... ]
}
```

- `start` / `end` are **local wall-clock times on this date in this timezone**.
  `24:00:00` means the next local midnight.
- Intervals are half-open `[start, end)`, gapless, and cover the full local day.
- Roughly 250 ascendant intervals and 10 Moon intervals per day.
- The boundaries are solved directly against the 249 KP cut longitudes, so no
  change can be skipped — including the shortest subs, which last under two
  minutes.

### Resolving a time

Find the `ascendant_windows` row and the `moon_windows` row whose
`[start, end)` contains the local time, then add `day_lord`. That is the full
seven-part RP set for that moment. `analysis.rp_windows.rp_at_local_time` does
exactly this and is what the tests use.

Use `reference_snapshot` **only** when the question names no time.

---

## Trigger windows

`rp_trigger_windows.topics[topic]` holds, for each of the 16 topics:

- `houses` and the L1 / L1–L2 / L1–L3 significator sets from the locked natal chart
- `days[]` — one row per pack day: day lord, whether it signifies, which Moon RPs
  match, which locked MD/AD/PD lords grant permission, the gate result, and the
  window counts and total minutes for that day
- `windows[]` — the best moments of each qualifying day

### Criterion

| Stage | Rule |
|---|---|
| Day gate | Day lord signifies at L1–L2 **and** at least one locked MD/AD/PD lord signifies at L1–L3 |
| Window | Ascendant sub lord, ascendant star lord and Moon sub lord all signify at L1–L2 |
| `STRONG` | Day lord, ascendant star lord, ascendant sub lord and Moon sub lord all signify at L1 |
| `ACTIVE` | Window matched but not all four at L1 |

Plain membership in `signified_houses` was rejected as a criterion: most charts
signify most houses through some planet, so it matches nearly every minute and
carries no information. The filter uses classical KP strength instead — Level 1
(in the star of an occupant) and Level 2 (occupant) are the fruit-giving
significators.

### Listing and totals

A qualifying day often has dozens of matching windows, because the ascendant
sub lord turns over about 249 times. `windows[]` therefore lists at most **6 per
topic per day** — ranked by grade, then L1 count, then duration — while
`days[]` carries the complete `windows_total`, `strong_windows`,
`active_minutes` and `strong_minutes`.

So: **aggregate from `days[]`, name specific moments from `windows[]`**, and
re-derive any unlisted window from `ascendant_windows` and `moon_windows`,
which are stored in full. Nothing is hidden and nothing needs recalculating.

### What a trigger window is not

An activation filter, not proof of an event. Dasha permission is applied as a
gate so a window can never appear on a date whose MD/AD/PD ignores the topic,
but natal promise still decides whether anything is on offer at all.

---

## Answering questions from the pack

Evidence order is unchanged: **natal promise (cuspal sublord) → dasha
permission → RP activation → transit trigger.** RP convergence alone is never a
verdict.

**"How will January 2027 be for me in Hyderabad?"**
Select every `days[]` record in January. Read the locked natal file and
`kp_rules.json`. Review each day's `ruling_planets`, the per-topic `days[]`
rows for the month, the `sukshma_timeline` entries that fall in it, and the
long-term transit file. Judge promise and dasha permission first, then
aggregate activation: repeated supportive windows, short bursts, dasha
transitions, stronger and weaker phases, topics with no activation at all, and
topics where the evidence is thin. Never generalise from one day's snapshot.

**"How will 18 January 2027 be?"**
Use that date's record and the applicable RP windows.

**"What about 18 January 2027 at 3:30 PM in Hyderabad?"**
Locate the interval containing 15:30 local and read the ascendant and Moon
sign/star/sub lords from it. Do not substitute the 09:00 reference snapshot
when a more precise stored interval exists.

The pack's `generated_at` is metadata. It is never the prediction date.

---

## Out of range

`valid_from` and `valid_to` state the coverage. For a date outside it:

- Use the other static files only where they genuinely cover the period — the
  locked natal chart and the long-term transit file do, the daily pack does not.
- Say plainly which date-specific evidence is missing.
- Never invent RP windows or planetary positions, and never claim a calculation
  was performed when the data is absent.

A new pack is needed only when the requested period is not covered. A different
month inside the coverage never requires regeneration.

---

## Regenerating

From the app's Enhanced Report section 4, set the start date and prediction
location, generate, and download the ZIP. Build time is about 7 seconds for 90
days. The pack extracts to roughly 3.4 MB, about half of it RP interval data;
it is written without indentation for that reason, while the natal, rules and
transit files stay human-readable. Regenerate every 60–75 days so the coverage
always runs ahead of the questions you ask.
