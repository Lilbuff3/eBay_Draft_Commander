# Gemini CCG Response: Listing Quality Fix

## Date: 2026-03-30

## Problem
Stetson fleece hat test listing performed poorly:
- Generic "Varies..." item specifics instead of actual values from photos
- Price $113 for a ~$20 fleece hat (researched ALL Stetson hats instead of fleece hats)
- Bare-bones description (just label:value pairs)
- Wrong field mapping (Compatible Model = use cases)
- Generic category

## Gemini Recommendations (Summarized)

### Stage 1: Vision Analysis
- Force model to be a "visual inspector" — ONLY use image evidence
- Mandate "Not Visibly Present" instead of generic brand info
- Transcribe ALL tag text verbatim (size, material, care, origin)

### Stage 2: Web Research
- Use vision output to create targeted search (material + brand + product type + condition)
- Search comparable SOLD listings, not general brand catalog
- Discard outliers (different materials, NWT items)
- Focus on 90-day sold prices

### Stage 3: Aspect Mapping
- Define field semantics (Compatible Model = parts only, omit for clothing)
- Give copywriting persona for descriptions
- Enforce single specific values, never "Varies"

## Actions Taken
1. Rewrote `EBAY_LISTING_PROMPT` with image-grounding rules
2. Updated `INDUSTRIAL_RESEARCH_PROMPT` with product_type/material/condition params
3. Updated `ASPECT_ENRICHMENT_PROMPT` with field definitions
4. Modified `research_part_number()` signature and call site to pass specifics
5. All 310 unit tests pass
