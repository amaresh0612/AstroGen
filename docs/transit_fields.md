# Long-term transit field definitions

Source: `analysis/long_term_transits.py` · export: `longterm_transits_*.json`
Schema: **1.1**

These records are **slow-planet sign ingresses** (Jupiter, Saturn, Rahu, Ketu)
over a multi-year horizon. They are calculations only — topic relevance is
judged by the AI using `kp_rules.json` and the locked natal chart.

| Field | Meaning |
|---|---|
| `planet` | Slow planet that changed sidereal sign |
| `ingress_date` | Civil date of the sign change (search refined from noon UT) |
| `ingress_datetime_utc` | Exact UT ISO timestamp of the crossing |
| `from_sign` / `to_sign` | Sidereal signs left / entered (Lahiri ayanamsa) |
| `transit_house` | Natal **Placidus cusp-interval** house containing the ingress longitude — same basis as natal occupancy. Not whole-sign |
| `transit_house_sign` | Whole-sign count from the natal Lagna sign — reference only |
| `nakshatra` / `star_lord` / `sub_lord` | Sidereal nakshatra, star lord and KP sub lord of the planet at ingress |
| `same_sign_natal_planets` | Natal planets whose natal sidereal **sign** equals `to_sign` |

## Same-sign is not a conjunction

`same_sign_natal_planets` (schema 1.1; previously misnamed `conjunct_natal_planets`)
lists natal planets that share the ingress sign. **No degree orb is applied.**
Angular separation is not computed. Do not treat these as close conjunctions.

There is currently **no** degree-based conjunction field in this file. If a
future release adds one, it will name an explicit orb in degrees.

## Natal vs transit reference

- Natal houses / planets come from the locked `natal_ref`.
- Transit longitudes are ephemeris positions at the ingress moment (Lahiri).
- `transit_house` projects the transit longitude into the **natal** Placidus
  cusp framework — it answers “which natal house is this transit activating?”,
  not “which house of a transit chart?”.
