# Chart payload reference (`chart_result`)

Fields produced by `calculate_comprehensive_chart` / session state (read-only contract for new report builders).

## Top-level

| Key | Type | Notes |
|-----|------|-------|
| `planets` | dict | Sun…Ketu entries |
| `houses` | dict | `'1st (Lagna)'` … `'12th'` |
| `house_cusps_degrees` | list[float] | 12 sidereal cusps |
| `cuspal_sublords` | dict[str,str] | `"1"`…`"12"` → lord |
| `asc_degree` | float | Sidereal Lagna |
| `ayanamsa` | float | Lahiri value used |
| `location` | dict | `lat`, `lng`, `tz_name` |
| `dashas` | dict | `current`, `upcoming`, `raw` |
| `raw_dashas` | list | Maha periods (may also live under dashas) |

## Planet entry

Typical keys: `full_degree`, `sign`, `degree`, `deg_decimal_in_sign`, `nakshatra`, `nakshatra_lord`, `pada`, `sublord`, `sign_lord`, `position`, `house_cuspal`, `house_whole`.

## House entry

Typical keys: `cusp_degree`, `sign`, `degree`, `nakshatra`, `nakshatra_lord`, `pada`, `sublord`.

## Birth details (`birth_details`)

`dob`, `tob` / `tob_display`, `place`, `gender`, optional `lat`/`lng`.

## Helpers to call (do not reimplement)

- `compute_kp_significators(chart_result)`
- `compute_antardashas(maha)` / `compute_pratyantardashas(bhukti)`
- `compute_current_transits(natal_chart)`
- `_build_ai_pdf_context(chart_data, birth_data)` — compact LLM context pattern to extend, not replace in-app
