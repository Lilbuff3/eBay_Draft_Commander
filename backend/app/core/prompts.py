"""
Centralized storage for AI prompts used in eBay Draft Commander
"""

EBAY_LISTING_PROMPT = """Analyze these product photos for a high-end eBay listing.

ROLE: You are an expert e-commerce specialist.
GOAL: Extract structured data for eBay Inventory API.
NOTE: This listing uses FREE SHIPPING. When suggesting a price, factor in an
estimated shipping cost of $5-$12 (USPS Ground Advantage) so the seller's margin
is preserved. Do NOT suggest a price that would be unprofitable after shipping.

CRITICAL INSTRUCTIONS:
1. IDENTIFICATION: Find Brand, Model, MPN (Part Number), and Serial Number.
   - If multiple codes exist, list them all in `oem_part_numbers`.
   - Distinguish between the MANUFACTURER (Brand) and COMPATIBLE WITH (e.g. "For Dell").
2. CONDITION: Assess condition strictly based on visual evidence.
   - Look for factory seals -> "New Old Stock" or "New".
   - Look for scratches/wear -> "Used".
3. SPECIFICS: Extract technical specs (Voltage, Amps, Capacity, Size, Color).

OUTPUT FORMAT: Return a JSON object with this EXACT structure:
{
    "identification": {
        "brand": "Brand Name",
        "model": "Model Number",
        "mpn": "Manuf. Part Number",
        "oem_part_numbers": ["Alt P/N 1", "Alt P/N 2"],
        "serial_number": "SNString or null",
        "product_type": "Noun (e.g. Switch, Router, Lens)",
        "compatible_systems": ["System 1", "System 2"],
        "confidence_score": 95
    },
    "condition": {
        "state": "New|New Open Box|New Old Stock|Used - Like New|Used - Good|Used - Acceptable|For Parts",
        "wear_details": "Description of any visible defects or 'pristine' if none",
        "accessories_found": ["Power Cord", "Manual", "Bracket"]
    },
    "listing": {
        "suggested_title": "Brand Model MPN Product Type Key Spec (Max 80 Chars)",
        "description_html": "<b>Brand:</b> ...<br><b>Model:</b> ...<br>...",
        "suggested_price": 0.00
    },
    "item_specifics": {
        "Brand": "Value",
        "Model": "Value",
        "MPN": "Value",
        "Type": "Value"
        // Add any other relevant specifics found (e.g. 'Connectivity', 'Voltage')
    },
    "category_suggestion": "Best eBay Category Name path"
}
"""

INDUSTRIAL_RESEARCH_PROMPT = """Research this industrial equipment part for eBay listing:

Item: {search_terms}
NOTE: This listing uses FREE SHIPPING, so the market price should account for
the seller covering shipping costs (~$5-$12 USPS depending on size/weight).

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
