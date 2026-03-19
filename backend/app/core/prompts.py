"""
Centralized storage for AI prompts used in eBay Draft Commander
"""

EBAY_LISTING_PROMPT = """{category_suggestions}

ROLE: You are an expert e-commerce product identifier and listing specialist.
GOAL: Extract structured data for eBay Inventory API from product images.

PRIORITY ORDER (spend most effort on #1 and #2):
1. IDENTIFICATION (most important): Find Brand, Model, MPN (Part Number), Serial Number.
   - Read ALL visible text, labels, stickers, and engravings in the images.
   - If multiple codes exist, list them all in `oem_part_numbers`.
   - Distinguish between the MANUFACTURER (Brand) and COMPATIBLE WITH (e.g. "For Dell").
   - Be precise with part numbers — a single wrong digit makes the listing unsearchable.
2. CONDITION: Assess condition strictly based on visual evidence.
   - Look for factory seals, shrink wrap, unopened bags -> "New Old Stock" or "New".
   - Look for scratches, scuffs, dust, wear marks -> "Used".
   - Note ALL visible defects in wear_details.
3. CATEGORY: Review the `category_suggestions` provided above.
   - Choose the single most accurate `category_id` that matches the item.
   - Consider technical differences (e.g., a printer drum is NOT a musical drum).
   - If NONE of the suggestions are accurate, return `null` for the `category_id`.
4. SPECIFICS: Extract technical specs (Voltage, Amps, Capacity, Size, Color).
5. TITLE: Generate a search-optimized title (max 80 chars).
6. PRICE: Provide a rough estimate ONLY as a ballback. This will be overridden by
   market research. Do NOT spend effort researching pricing — just give your best
   guess of the BASE market value (no shipping included).

OUTPUT FORMAT: Return a JSON object with this EXACT structure:
{{
    "identification": {{
        "brand": "Brand Name",
        "model": "Model Number",
        "mpn": "Manuf. Part Number",
        "oem_part_numbers": ["Alt P/N 1", "Alt P/N 2"],
        "serial_number": "SNString or null",
        "product_type": "Noun (e.g. Switch, Router, Lens)",
        "compatible_systems": ["System 1", "System 2"],
        "estimated_weight_lbs": 0.0,
        "package_size": "small|medium|large|heavy",
        "confidence_score": 95,
        "category_id": "Chosen Category ID or null"
    }},
    "condition": {{
        "state": "New|New Open Box|New Old Stock|Used - Like New|Used - Good|Used - Acceptable|For Parts",
        "wear_details": "Description of any visible defects or 'pristine' if none",
        "accessories_found": ["Power Cord", "Manual", "Bracket"]
    }},
    "listing": {{
        "suggested_title": "SEO-optimized, max 80 chars. Format: [Brand] [Model/MPN] [Product Type] [Key Specs] [Condition Keyword]. Front-load searchable keywords buyers type into eBay search. Include model numbers and part numbers. No filler words (great, amazing, lot, wow, look). No special characters (!*~). Example: 'Xerox 108R00713 Solid Ink Cyan Phaser 8560 Genuine OEM New'",
        "description_html": "<b>Brand:</b> ...<br><b>Model:</b> ...<br>...",
        "suggested_price": 0.00
    }},
    "item_specifics": {{
        "Brand": "Value",
        "Model": "Value",
        "MPN": "Value",
        "Type": "Value"
    }}
}}
"""

INDUSTRIAL_RESEARCH_PROMPT = """Research this industrial equipment part for eBay listing:

Item: {search_terms}
NOTE: Return BASE market value only. Do NOT include shipping costs in prices.
Shipping is calculated separately.

Find and return:
1. EXACT product specifications (capacity, speed, interface, voltage)
2. What systems/equipment this is compatible with
3. Current market price range on eBay in {year}
4. Whether this is a rare/hard-to-find item
5. Common alternative part numbers

Return as JSON:
{{
    "product_name": "Full product name",
    "specifications": {{"key": "value"}},
    "compatible_with": ["system1", "system2"],
    "market_price": {{"low": 0, "mid": 0, "high": 0, "currency": "USD"}},
    "availability": "common|moderate|rare|very_rare",
    "alternative_part_numbers": [],
    "notes": "Any important details"
}}

Provide your response in a JSON block like this:
```json
{{ ... }}
```"""

ASPECT_ENRICHMENT_PROMPT = """You are filling in eBay item specifics for a product listing.

The item has already been identified as:
- Title: {title}
- Brand: {brand}
- Model: {model}
- MPN: {mpn}
- Category: {category_name}

Below are the REQUIRED and RECOMMENDED item specifics for this eBay category.
For each aspect, I've listed the allowed values (if constrained by eBay).

{aspect_list}

EXISTING SPECIFICS (already filled, do NOT overwrite unless empty):
{existing_specifics}

INSTRUCTIONS:
1. Using the product images and your knowledge of this product, fill in as many aspects as possible.
2. For aspects with allowed values, you MUST pick from the allowed list (exact match).
3. For free-text aspects, provide accurate values based on the images and product knowledge.
4. If you genuinely cannot determine a value, omit it (do NOT guess randomly).
5. Return ONLY a flat JSON object mapping aspect names to values.
6. Aspect values must be strings, max 65 characters each.
7. Do NOT include aspects you cannot determine.

Return JSON:
{{{{
    "Aspect Name": "Value",
    "Another Aspect": "Value"
}}}}"""
