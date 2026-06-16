"""
Centralized storage for AI prompts used in eBay Draft Commander
"""

EBAY_LISTING_PROMPT = """{category_suggestions}

ROLE: You are a meticulous inventory inspector and eBay listing specialist.
GOAL: Extract structured data from product images for eBay listings.

CRITICAL RULE: Your ONLY source of information is the images provided. Do NOT use
general knowledge about the brand or product line. Every value you return must come
from what you can SEE in the photos. If a detail is not visible, output null — never
fill in generic brand information or "Varies" values.

PRIORITY ORDER (spend most effort on #1 and #2):
1. IDENTIFICATION (most important): Find Brand, Model, MPN (Part Number), Serial Number.
   - Read ALL visible text on tags, labels, stickers, and engravings in the images.
   - Transcribe tag text EXACTLY as printed (size tags, material/content tags, care labels).
   - If multiple codes exist, list them all in `oem_part_numbers`.
   - Distinguish between the MANUFACTURER (Brand) and COMPATIBLE WITH (e.g. "For Dell").
   - Be precise with part numbers — a single wrong digit makes the listing unsearchable.
   - `product_type` must be specific (e.g. "Fleece Hat" not just "Hat", "Laser Printer" not just "Printer").
   - `material` field: transcribe from the content/material tag if visible.
2. CONDITION: Assess condition strictly based on visual evidence.
   - Look for factory seals, shrink wrap, unopened bags -> "New Old Stock" or "New".
   - Look for scratches, scuffs, dust, wear marks -> "Used".
   - Note ALL visible defects in wear_details.
3. CATEGORY: Review the `category_suggestions` provided above.
   - Choose the single most accurate `category_id` that matches the item.
   - Prefer the MOST SPECIFIC subcategory available.
   - Consider technical differences (e.g., a printer drum is NOT a musical drum).
   - If NONE of the suggestions are accurate, return `null` for the `category_id`.
4. SPECIFICS: Extract ONLY what you can see or read from the images.
   - Size: transcribe from size tag (e.g. "L/XL", "Medium", "32x30")
   - Color: describe the PRIMARY color you see (e.g. "Teal", "Black", "Red")
   - Material: transcribe from content tag (e.g. "100% Polyester Fleece")
   - Other specs: Voltage, Amps, Capacity — only from visible labels.
   - NEVER return "Varies" or lists of possible options. One specific value per field.
5. TITLE: Generate a search-optimized title (max 80 chars).
6. PRICE: Provide a rough estimate ONLY as a ballpark. This will be overridden by
   market research. Do NOT spend effort researching pricing — just give your best
   guess of the BASE market value (no shipping included).

OUTPUT FORMAT: Return a JSON object with this EXACT structure:
{{
    "identification": {{
        "brand": "Brand Name from label/tag",
        "model": "Model Number from tag or null",
        "mpn": "Part Number from tag or null",
        "oem_part_numbers": ["Alt P/N 1"],
        "serial_number": "SNString or null",
        "product_type": "Specific noun (e.g. Fleece Hat, Laser Printer, Wool Jacket)",
        "material": "From content tag or null",
        "compatible_systems": ["System 1", "System 2"],
        "estimated_weight_lbs": 0.0,
        "package_size": "small|medium|large|heavy",
        "confidence_score": 95,
        "category_id": "Chosen Category ID or null"
    }},
    "condition": {{
        "state": "New|New Open Box|New Old Stock|Used - Like New|Used - Good|Used - Acceptable|For Parts",
        "wear_details": "Description of visible defects or 'No visible defects'",
        "accessories_found": ["Power Cord", "Manual", "Bracket"]
    }},
    "listing": {{
        "suggested_title": "SEO-optimized, max 80 chars. Format: [Brand] [Model/MPN] [Product Type] [Key Specs] [Condition Keyword]. Front-load searchable keywords. Include model/part numbers. No filler words (great, amazing). No special characters (!*~). Example: 'Xerox 108R00713 Solid Ink Cyan Phaser 8560 Genuine OEM New'",
        "description_html": "Write a compelling 2-3 paragraph product description. Start with an engaging opening sentence about the item. Include a bulleted feature list highlighting key selling points (brand quality, material, size, condition, country of manufacture). End with what makes this item a good value. Use <b>, <br>, <ul><li> tags. Do NOT just list label:value pairs.",
        "suggested_price": 0.00
    }},
    "item_specifics": {{
        "Brand": "Exact value from tag",
        "Model": "Exact value from tag or null",
        "MPN": "Exact value from tag or null",
        "Type": "Specific product type",
        "Size": "Exact size from tag or null",
        "Color": "Primary color observed",
        "Material": "From content tag or null"
    }}
}}

REMINDER: Every value must come from the images. "Varies", "Options include", or
generic brand catalog info is WRONG. If you cannot see it, return null.
"""

INDUSTRIAL_RESEARCH_PROMPT = """Research this specific product for eBay listing pricing:

Item: {search_terms}
Product Type: {product_type}
Material/Key Detail: {material}
Condition: {condition}

NOTE: Return BASE market value only. Do NOT include shipping costs in prices.
Shipping is calculated separately.

IMPORTANT: Search for COMPARABLE SOLD LISTINGS of this SPECIFIC item type.
- If the item is a "Fleece Hat", search for used fleece hats by this brand — NOT all hats by this brand.
- If the item is a "Laser Printer Fuser", search for that specific fuser — NOT all printer parts.
- Include the material, condition, and product type in your search to get accurate comps.
- Discard outliers (new-with-tags items, different materials, different product types).
- Focus on sold prices from the last 90 days.

Find and return:
1. EXACT product specifications (capacity, speed, interface, voltage, material, size)
2. What systems/equipment this is compatible with
3. Current market price range on eBay in {year} for THIS SPECIFIC product type and condition
4. Whether this is a rare/hard-to-find item
5. Common alternative part numbers

Return as JSON:
{{
    "product_name": "Full specific product name",
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

{research_specs_section}
Below are the REQUIRED and RECOMMENDED item specifics for this eBay category.
For each aspect, I've listed the allowed values (if constrained by eBay).

{aspect_list}

EXISTING SPECIFICS (already filled, do NOT overwrite unless empty):
{existing_specifics}

INSTRUCTIONS:
1. Fill in aspects using SPECIFIC values for THIS item — not generic brand catalog info.
2. For aspects with allowed values, you MUST pick from the allowed list (exact match).
3. For free-text aspects, provide ONE specific value (not "Varies" or lists of options).
4. If you genuinely cannot determine a value, omit it (do NOT guess randomly).
5. Return ONLY a flat JSON object mapping aspect names to values.
6. Aspect values must be strings, max 65 characters each.
7. Do NOT include aspects you cannot determine.

FIELD DEFINITIONS (common mistakes to avoid):
- "Compatible Model": ONLY for parts/accessories — the device model it fits (e.g. "iPhone 14").
  For clothing/apparel/general items, OMIT this field entirely.
- "Compatible Brand": ONLY for parts/accessories — the brand of device it fits.
  For clothing/apparel/general items, OMIT this field entirely.
- "Style": The style of the item (e.g. "Beanie", "Fedora", "Baseball Cap").
- "Department": Who it's for (e.g. "Men", "Women", "Unisex").
- "Color": The PRIMARY color of THIS specific item (e.g. "Teal", not "Varies").
- "Size": The EXACT size from the tag (e.g. "L/XL", not "Varies (XS, S, M...)").
- "Material": The EXACT material from the tag (e.g. "100% Polyester Fleece", not "Varies").

Return JSON:
{{
    "Aspect Name": "Value",
    "Another Aspect": "Value"
}}"""


ASPECT_RESOLVE_PROMPT = """You are resolving the LAST missing required eBay item specifics so a listing can post. This listing is editable/scheduled, so a confident best-guess is better than leaving it blank — but accuracy still matters.

Item:
- Title: {title}
- Brand: {brand}
- Model: {model}
- Category: {category_name}

{research_specs_section}
Resolve EVERY aspect below. For each, give your best value for THIS specific item.

{aspect_list}

INSTRUCTIONS:
1. For aspects with allowed values, the value MUST be an EXACT match from that aspect's list.
2. For free-text aspects, give ONE specific value (never "Varies" or a list).
3. Give your best guess for every aspect — use the photos, title, brand, and research. Do not omit any.
4. For each aspect include a confidence 0.0–1.0 (how sure you are) and a one-word source: "image", "research", or "inferred".
5. Values are strings, max 65 characters.

Return ONLY a JSON object mapping each aspect name to an object:
{{
    "Aspect Name": {{"value": "...", "confidence": 0.0, "source": "image"}}
}}"""
