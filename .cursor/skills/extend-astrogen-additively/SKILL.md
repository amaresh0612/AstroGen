---
name: extend-astrogen-additively
description: >-
  Extends AstroGen with new packages and features without modifying existing
  app.py or agent files. Use when adding report engines, prompt packs,
  analysis helpers, schemas, tests, or documenting future UI wiring.
---

# Extend AstroGen Additively

## Hard rule

Do not edit existing application source unless the user explicitly names the file and change. Prefer parallel modules.

## Recommended package map

```
./
  analysis/          # pure functions: topic extracts, timing windows
  prompts/           # markdown or python prompt constants
  reports/
    narrative/       # assemble section text from chart + LLM
    pdf/             # ReportLab builders
  schemas/           # TypedDict / dataclass chart & report models
  tests/
    fixtures/        # anonymized chart JSON
```

## Import pattern

New code may import from the monolith carefully:

```python
# Prefer late/local import to avoid Streamlit side effects at import time
def _chart_api():
    import app as astrogen_app
    return astrogen_app
```

Better long-term: user-approved extraction of pure functions into `analysis/chart_engine.py` **copied** from `app.py` (duplicate-then-converge), not in-place moves, until a dedicated refactor is requested.

## UI wiring (later)

Document a minimal hook for the user, e.g. one button calling the new builder. Do not apply the hook until asked.

## Definition of done

- New files only (or user-approved touch points)
- README/notes for how to invoke the new report
- No secret files committed
