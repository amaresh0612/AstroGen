---
name: design-pdf-astrology-report
description: >-
  Designs additive ReportLab PDF layouts for professional KP astrology reports
  in AstroGen. Use when creating or upgrading personal/organisation PDF
  structure, typography, tables, chart image embedding, or multi-page report
  sections without breaking existing generate_pdf_report behavior.
---

# Design PDF Astrology Reports

## Approach

- Implement **new** builders under `reports/pdf/` (e.g. `professional_personal.py`).
- Keep existing `generate_pdf_report` / `generate_org_pdf_report` untouched unless the user requests a switchover.
- Optional AI sections must fail soft (return buffer without AI text on API errors).

## Layout principles

- Page: A4, margins ≥ 0.45 inch (match current comfort).
- Hierarchy: title → metadata table → synopsis → topical sections → timing → appendix.
- Tables: wrap cells with `Paragraph`; font 7–9pt for dense KP grids.
- Embed lagna chart PNG from `render_chart_png_bytes_pil` when available.
- Accent color may stay earth/gold (`#8B4513` / gold) for brand continuity.

## Page plan (professional personal)

1. Cover + metadata + executive synopsis  
2. Planetary & cusp tables + chart image  
3. Persona / career / relationship / finance narratives  
4. Dasha timeline (current MD + antars near now)  
5. Appendix: significators + notes  

## Implementation sketch

```python
# reports/pdf/professional_personal.py
def build_professional_personal_pdf(birth_data, chart_data, narrative: dict, ...) -> io.BytesIO:
    ...
```

`narrative` should be produced by analysis/prompt modules, not invented inside the PDF layer.

## Checklist

- [ ] Builds without OpenAI
- [ ] No overlapping table columns
- [ ] Long nakshatra names wrap
- [ ] Org variant avoids romantic phrasing
