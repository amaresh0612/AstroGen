---
name: craft-kp-prompts
description: >-
  Designs versioned KP astrology system/user prompt packs for AstroGen AI
  readings and PDF summaries. Use when writing or upgrading overall, career,
  relationship, finance, or organisation prompts, or when structuring LLM
  output for professional reports.
---

# Craft KP Prompts

## Placement

Add packs under `prompts/` (new files only), e.g.:

```
prompts/
  v2_overall.md
  v2_career.md
  v2_relationship.md
  v2_pdf_summary.md
  v2_org_foundation.md
```

Do not silently overwrite `AGENTS` in `app.py` unless the user asks.

## System prompt skeleton

```text
You are AstroGen, an expert KP (Krishnamurti Paddhati) astrologer.
Scope: {TOPIC_SCOPE}.
Rules:
- Use ONLY the chart data in the user message.
- Cite Lagna/CSL, planet star-lord & sublord, significator houses, and MD/AD timing.
- No medical diagnoses; no guaranteed financial or legal outcomes.
- Output EXACTLY the section headings below with the requested bullet counts.
Tone: professional, compassionate, specific, non-fatalistic.
```

## Required user-message blocks

1. Birth metadata  
2. Planets (sign, degree, nakshatra, nak-lord, sublord, house)  
3. House cusps + CSL (at least topic houses)  
4. Significators for topic planets/houses  
5. Current + upcoming MD/AD (dates)  
6. Optional: key transits  

## Output contracts

### Interactive reading (overall)

```text
## Synopsis
## Persona & Life Themes (6–8 bullets)
## Strengths & Challenges (4–6 bullets)
## Timing Windows (4–6 bullets with MD/AD)
## Practical Guidance (5 bullets)
```

### Career

Focus houses 10/6/2/11; planets Jupiter, Saturn, Mercury, Sun as relevant.

### Relationship

Focus houses 7/5/8; Venus, Moon, 7th CSL; compassionate phrasing.

### PDF concise (compat with current)

Keep exact section labels if replacing `_ai_pdf_summary` behavior later:

`PERSONA` / `CAREER` / `RELATIONSHIP & MARRIAGE` / `FINANCE` with fixed line counts.

## Parameters

| Use | Model | temp | max_tokens |
|-----|-------|------|------------|
| PDF concise | gpt-4o-mini | 0.5 | 300–500 |
| Interactive | gpt-4o-mini | 0.6–0.7 | 1200–2000 |
| Professional longform | user-chosen stronger model | 0.4–0.6 | 2500–4000 |

## Reference

See [examples.md](examples.md) for sample prompt snippets.
