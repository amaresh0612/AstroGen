# Validation report — schema 2.6 (23 Nov 2026)

Fictional fixture natal (`Test Subject`, 1992) · Hyderabad prediction location.
Structural / internal / semantic categories are separate (pack `validation`).

## Structural

| Check | Result |
|---|---|
| Day count / unique dates | PASS |
| Prediction lat/lng/tz on every day | PASS |
| Forbidden merged natal fields in days[] | PASS |
| RP interval gapless coverage | PASS |
| Fine-dasha timelines continuous | PASS |

## Internal consistency

| Check | Result |
|---|---|
| Locked MD/AD/PD resolve via `locked_periods` | PASS |
| Cuspal occupancy | PASS |
| Significator methodology version present | PASS |
| `windows_listed` ≤ `windows_total` | PASS |
| Reproducibility metadata present | PASS |

## Astrology-semantic (warnings, not failures)

| Flag | Meaning |
|---|---|
| promotion ≡ wealth identical activation | Same `EVENT_HOUSES` `[2,6,10,11]` — expected |
| career ≈ promotion under half-coverage | Documented selectivity limit; thresholds unchanged |
| Broad L1–L2 on some topics | Soft warning; not suppressed |
| dasha permission without RP windows | Timing support absent — not denial |

## Pre-publication (`analysis.report_consistency`)

| Check | Behaviour |
|---|---|
| Confirmed promotion still “pending” | BLOCK |
| Zero-window topic called time-supported | BLOCK |
| Capped list used as probability | BLOCK |
| Health diagnosis language | BLOCK |
| Natal fingerprint / method version | WARN / CRITICAL as coded |

## Note on 1989 client packages

This repo regenerates the **fictional** fixture pack. Client 1989-aligned packages
must be regenerated in the UI with the locked 1989 natal + prediction location;
do not mix with any older 1990-aligned artefact.
