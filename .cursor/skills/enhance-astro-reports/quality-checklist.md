# Professional report quality checklist

Run before considering a report builder “done”:

## Factual

- [ ] All longitudes/lords come from chart payload (no invented positions)
- [ ] CSL for topic houses listed correctly
- [ ] Dasha dates match `dashas` / antardasha computation
- [ ] Significators consistent with `compute_kp_significators`

## Narrative

- [ ] Fixed section order
- [ ] Each major claim has a chart citation
- [ ] Timing given as windows, not certainties
- [ ] No medical / guaranteed financial / legal claims
- [ ] Tone calm, specific, non-fatalistic

## Deliverable

- [ ] Works with missing optional AI (PDF still builds)
- [ ] Tables readable on A4
- [ ] Same template produces consistent headings across clients
- [ ] Org reports use institutional language

## Additive hygiene

- [ ] No edits to existing `app.py` KP math
- [ ] New code lives under new packages
- [ ] Integration notes documented for a future minimal UI hook
