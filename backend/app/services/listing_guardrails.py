"""
Listing-Quality Guardrails.

A thin layer between AI/pricing output and eBay submission that catches the
recurring defects a review of 24 scheduled listings surfaced: duplicate
listings, wildly wrong prices, bad brand values, and malformed titles. See
docs/superpowers/specs/2026-06-27-listing-quality-guardrails-design.md.

Two hook points (wired by callers, not here):
- Dedup (compute_photo_hashes / find_duplicate) runs EARLY, at capture, so a
  re-send is caught before a wasted AI call.
- Title/brand/price (apply_pre_listing_guardrails) run LATE, right before the
  actual eBay submission.

All functions here are pure / best-effort:
- clean_title and normalize_aspects are no-ops on already-clean input.
- apply_pre_listing_guardrails wraps every guard so a raise is caught and
  logged — a guardrail must never block a listing by crashing. The only
  intentional "block" is returning a review_reason.
"""
import math
import re
import statistics
from typing import Any, Dict, List, Optional

from PIL import Image

from backend.app.core.constants import (
    BRAND_BLOCKLIST,
    PRICE_COMP_MULTIPLE,
    PRICE_REVIEW_THRESHOLD,
    TITLE_MAX_LENGTH,
)
from backend.app.core.logger import get_logger

logger = get_logger('listing_guardrails')

_BRAND_BLOCKLIST_LOWER = {b.lower() for b in BRAND_BLOCKLIST}

# Aspect names treated as "identity" aspects for normalize_aspects (blocklist
# mapping + slash-split). Brand is the one that actually surfaced bad values;
# kept as a set so it's easy to extend later without touching call sites.
_IDENTITY_ASPECTS = {'Brand'}

# Dangling trailing punctuation/fragments left behind when the AI self-truncates
# at its 80-char title budget mid-thought, e.g. "...(Alkaline," or "...Meter -".
_TRAILING_DANGLE_RE = re.compile(r'[,:\-(]+\s*$')


# ---------------------------------------------------------------------------
# Title hygiene
# ---------------------------------------------------------------------------

_SPAM_WORDS_RE = re.compile(
    r'\b(l@@k|look|wow|must see|rare|awesome|cheap|best price|great deal|fast ship(?:ping)?|free ship(?:ping)?|mint!|new!)\b',
    re.IGNORECASE
)
_FORBIDDEN_TITLE_CHARS = re.compile(r'[*~_!#$^+=<>{}\[\]|\\]+')


def clean_title(title: Optional[str]) -> str:
    """Strip dangling trailing fragments, collapse repeated words, normalize
    whitespace, and guarantee the result is <= TITLE_MAX_LENGTH with no
    mid-word cut. No-op on an already-clean title.
    """
    if not title:
        return ""

    # Normalize whitespace first so downstream regexes see single spaces.
    text = re.sub(r'\s+', ' ', title).strip()

    # Repeatedly strip dangling trailing punctuation/fragments — a single pass
    # can uncover another dangling char (e.g. "...(Alkaline," -> "...(Alkaline"
    # -> still has a lone trailing "(" once the comma is gone... actually we
    # strip the whole run in one regex pass, but loop defensively in case
    # stripping reveals a new trailing word fragment followed by punctuation).
    prev = None
    while prev != text:
        prev = text
        text = _TRAILING_DANGLE_RE.sub('', text).strip()
        # An unbalanced "(word" with no closing paren at all, dangling at the
        # very end (e.g. "...Cleaner (Alkaline" with the comma already gone)
        # is also a fragment — strip a trailing open-paren group with no close.
        if '(' in text and ')' not in text[text.rfind('('):]:
            text = text[:text.rfind('(')].strip()

    # Collapse consecutive duplicate words, case-insensitive (e.g.
    # "Sencore Sencore LC102" -> "Sencore LC102").
    words = text.split(' ')
    deduped = []
    for w in words:
        if deduped and deduped[-1].lower() == w.lower():
            continue
        deduped.append(w)
    text = ' '.join(deduped).strip()

    # Final length guard: truncate on a word boundary, never mid-word.
    if len(text) > TITLE_MAX_LENGTH:
        truncated = text[:TITLE_MAX_LENGTH]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        text = truncated.rstrip(' ,:-(').strip()

    return text


def optimize_cassini_title(
    title: Optional[str],
    specifics: Optional[Dict[str, Any]] = None,
    condition: Optional[str] = None
) -> str:
    """Optimize title to target 75-80 characters, front-loading keywords,
    eliminating duplicates and spam tokens, and appending high-value specific attributes.
    """
    if not title:
        return ""

    # 1. Strip forbidden characters and spam words
    text = _FORBIDDEN_TITLE_CHARS.sub(' ', title)
    text = _SPAM_WORDS_RE.sub('', text)
    text = clean_title(text)

    if not specifics:
        return clean_title(text)

    # 2. Backfill high-value aspect keywords if title is under-budget (< 68 chars)
    attribute_priority = ['MPN', 'Model', 'Color', 'Material', 'Size', 'Department']
    existing_words = {w.lower().rstrip(',:;-') for w in text.split()}

    for attr in attribute_priority:
        val = specifics.get(attr)
        if not val or not isinstance(val, str):
            continue
        val_clean = val.strip()
        val_lower = val_clean.lower()
        if val_lower in {'does not apply', 'unbranded', 'n/a', 'none'}:
            continue
        
        # Check if already present in title
        val_words = [w.lower().rstrip(',:;-') for w in val_clean.split()]
        if any(w in existing_words for w in val_words):
            continue
        
        # Try appending
        candidate = f"{text} {val_clean}"
        if len(candidate) <= TITLE_MAX_LENGTH:
            text = candidate
            existing_words.update(val_words)

    # 3. Add condition keyword if room and not already present
    if condition and len(text) <= TITLE_MAX_LENGTH - 5:
        cond_str = condition.strip().lower()
        cond_word = "New" if "new" in cond_str else ("Parts" if "parts" in cond_str else "Used")
        if cond_word.lower() not in existing_words:
            if len(f"{text} {cond_word}") <= TITLE_MAX_LENGTH:
                text = f"{text} {cond_word}"

    return clean_title(text)


# ---------------------------------------------------------------------------
# Brand / aspect normalization
# ---------------------------------------------------------------------------

COMMON_CANONICAL_SYNONYMS = {
    'cotton': '100% Cotton',
    'polyester': '100% Polyester',
    'poly': 'Polyester',
    'fleece': 'Fleece',
    'leather': 'Leather',
    'faux leather': 'Faux Leather',
    'wood': 'Wood',
    'plastic': 'Plastic',
    'metal': 'Metal',
    'stainless steel': 'Stainless Steel',
    'aluminum': 'Aluminum',
    'silver': 'Silver',
    'gold': 'Gold',
    'black': 'Black',
    'white': 'White',
    'blue': 'Blue',
    'red': 'Red',
    'green': 'Green',
    'gray': 'Gray',
    'grey': 'Gray',
    'brown': 'Brown',
    'beige': 'Beige',
    'tan': 'Tan',
    'yellow': 'Yellow',
    'orange': 'Orange',
    'purple': 'Purple',
    'pink': 'Pink',
    'men': "Men's",
    'mens': "Men's",
    'women': "Women's",
    'womens': "Women's",
    'unisex': 'Unisex Adults',
    'kids': 'Unisex Kids',
    'boys': "Boys'",
    'girls': "Girls'",
    'wireless': 'Wireless',
    'bluetooth': 'Bluetooth',
    'na': 'Does Not Apply',
    'n/a': 'Does Not Apply',
    'none': 'Does Not Apply',
    'unknown': 'Unbranded',
    'generic': 'Unbranded',
}


def normalize_aspects(specs: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize identity and facet aspects in `specs`.

    - Blocklisted non-brand tokens ("Signed", "Various", "N/A", "Unknown",
      "Unbranded", "Generic") -> "Unbranded" (case-insensitive compare).
    - Blocklisted MPN/UPC tokens ("N/A", "Unknown", "None", "na") -> "Does Not Apply".
    - Canonicalizes common single-word values (e.g. "cotton" -> "100% Cotton", "black" -> "Black").
    - "A / B" style multi-value strings -> first meaningful value ("A").
    - Empty/junk placeholder values ("Varies", "See description") are dropped entirely.

    Returns a (possibly new) dict; safe no-op on clean input.
    """
    if not specs:
        return specs

    result = dict(specs)
    for name in _IDENTITY_ASPECTS:
        if name not in result:
            continue
        raw = result[name]
        value = raw[0] if isinstance(raw, list) else raw
        value = (value or '').strip() if isinstance(value, str) else value

        if not value:
            result.pop(name, None)
            continue

        if isinstance(value, str) and '/' in value:
            first = value.split('/')[0].strip()
            value = first or value

        if isinstance(value, str) and value.lower() in _BRAND_BLOCKLIST_LOWER and value.lower() != 'unbranded':
            value = 'Unbranded'

        if not value:
            result.pop(name, None)
        else:
            result[name] = value

    # Canonicalize and clean standard facet fields
    for k, v in list(result.items()):
        if not isinstance(v, str):
            continue
        v_clean = v.strip()
        v_lower = v_clean.lower()

        # Drop generic placeholder phrases that harm Cassini SEO
        if v_lower in {'varies', 'see description', 'see photos', 'see title', 'check photos', 'unknown/other'}:
            result.pop(k, None)
            continue

        # Standardize MPN / UPC / ISBN / Part Number
        if k in {'MPN', 'UPC', 'ISBN', 'Manufacturer Part Number'} and v_lower in {'na', 'n/a', 'none', 'unknown', 'generic', 'does not apply'}:
            result[k] = 'Does Not Apply'
            continue

        # Apply canonical synonym mapping
        if v_lower in COMMON_CANONICAL_SYNONYMS:
            if k == 'Brand':
                result[k] = 'Unbranded' if v_lower in {'unknown', 'generic'} else COMMON_CANONICAL_SYNONYMS[v_lower]
            elif v_lower in {'unknown', 'generic'}:
                result.pop(k, None)
            else:
                result[k] = COMMON_CANONICAL_SYNONYMS[v_lower]
        elif len(v_clean.split()) == 1 and v_clean.islower() and len(v_clean) > 2:
            result[k] = v_clean.capitalize()

    return result


def calculate_cassini_seo_score(specifics: Dict[str, Any], aspect_schema: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Compute quantified Cassini SEO search readiness score (0-100%) and fill metrics."""
    if not specifics:
        return {
            'seo_score': 0,
            'required_total': 0,
            'required_filled': 0,
            'recommended_total': 0,
            'recommended_filled': 0,
            'total_aspects_count': 0
        }

    clean_specs = {k: v for k, v in specifics.items() if v and str(v).strip() and str(v).strip().lower() not in {'does not apply', 'n/a', 'none', 'varies'}}
    
    if not aspect_schema:
        count = len(clean_specs)
        score = min(100, int((count / 8.0) * 100))
        return {
            'seo_score': score,
            'required_total': 0,
            'required_filled': 0,
            'recommended_total': 8,
            'recommended_filled': count,
            'total_aspects_count': len(clean_specs)
        }

    required_aspects = [a for a in aspect_schema if a.get('isRequired')]
    optional_aspects = [a for a in aspect_schema if not a.get('isRequired')]

    req_total = len(required_aspects)
    req_filled = sum(1 for a in required_aspects if a.get('name') in specifics and str(specifics[a.get('name')]).strip())

    rec_sample = optional_aspects[:12]
    rec_total = max(1, len(rec_sample))
    rec_filled = sum(1 for a in rec_sample if a.get('name') in specifics and str(specifics[a.get('name')]).strip())

    if req_total > 0:
        score = (req_filled / req_total) * 60 + (rec_filled / rec_total) * 40
    else:
        score = (rec_filled / rec_total) * 100

    return {
        'seo_score': max(10, min(100, round(score))),
        'required_total': req_total,
        'required_filled': req_filled,
        'recommended_total': rec_total,
        'recommended_filled': rec_filled,
        'total_aspects_count': len(clean_specs)
    }


# ---------------------------------------------------------------------------
# Photo perceptual hash (dHash) + duplicate finder
# ---------------------------------------------------------------------------

def _dhash(image: Image.Image, hash_size: int = 8) -> str:
    """Compute a difference hash (dHash) for a single PIL image.

    Grayscale -> resize to (hash_size+1) x hash_size -> compare each row's
    adjacent pixels -> hash_size * hash_size bits -> hex string.
    """
    gray = image.convert('L').resize((hash_size + 1, hash_size), Image.LANCZOS)
    bits = []
    for row in range(hash_size):
        for col in range(hash_size):
            left = gray.getpixel((col, row))
            right = gray.getpixel((col + 1, row))
            bits.append('1' if left > right else '0')
    bit_string = ''.join(bits)
    return '%016x' % int(bit_string, 2)


def compute_photo_hashes(image_paths: List[str]) -> List[str]:
    """Compute a 64-bit dHash (as a 16-char hex string) for each readable
    image in `image_paths`. Unreadable/missing images are skipped silently.
    """
    hashes = []
    for path in image_paths or []:
        try:
            with Image.open(path) as img:
                hashes.append(_dhash(img))
        except Exception as e:
            logger.warning(f"Skipping unreadable image for dHash: {path} ({e})")
            continue
    return hashes


def _hamming_distance(hash_a: str, hash_b: str) -> int:
    return bin(int(hash_a, 16) ^ int(hash_b, 16)).count('1')


def _required_matches(num_new: int, min_match_fraction: float) -> int:
    """How many of the new item's photos must match a candidate to call it a
    duplicate. Single-photo items need 1; multi-photo items need a majority
    (>= ceil(fraction * n)), and at least 2 — so one coincidentally-similar
    angle of a different item never trips the guard."""
    if num_new <= 1:
        return 1
    return min(num_new, max(2, math.ceil(min_match_fraction * num_new)))


def find_duplicate(
    new_hashes: List[str],
    recent_jobs: List[Dict[str, Any]],
    max_distance: int,
    min_match_fraction: float = 0.6,
) -> Optional[Dict[str, Any]]:
    """Return {'id', 'listing_id'} for the first recent job that the new item
    duplicates, else None.

    A duplicate requires that ENOUGH of the new item's photos each match some
    stored photo (within `max_distance` Hamming distance), not just one — see
    `_required_matches`. This stops visually-similar-but-different items (e.g.
    different gray printer parts on the same background, where a single angle
    can collide) from being falsely flagged. A genuine re-send matches on all
    its photos and clears the bar easily.

    Hashes of differing length (e.g. an old 64-bit dHash vs a future larger
    one) are never compared, so a hash-size change degrades to "no match"
    rather than to garbage distances.
    """
    if not new_hashes or not recent_jobs:
        return None

    required = _required_matches(len(new_hashes), min_match_fraction)

    for job in recent_jobs:
        stored_hashes = job.get('photo_hashes') or []
        if not stored_hashes:
            continue
        matched = 0
        for new_hash in new_hashes:
            for stored in stored_hashes:
                try:
                    if len(new_hash) == len(stored) and _hamming_distance(new_hash, stored) <= max_distance:
                        matched += 1
                        break  # this new photo is accounted for; move to the next
                except (ValueError, TypeError):
                    continue
        if matched >= required:
            return {'id': job.get('id'), 'listing_id': job.get('listing_id')}
    return None


# ---------------------------------------------------------------------------
# Price sanity
# ---------------------------------------------------------------------------

def check_price_sanity(
    price: float,
    source: Optional[str],
    comps: Optional[List[Dict[str, Any]]],
) -> Optional[str]:
    """Return a human-readable review reason if `price` looks like an outlier:

    (a) `source` is NOT a comp-backed source (does not start with
        "market_data") AND price > PRICE_REVIEW_THRESHOLD, OR
    (b) comps is non-empty AND price > PRICE_COMP_MULTIPLE * median(comp prices)

    Else None.
    """
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None

    source = source or ''
    comps = comps or []

    if comps:
        comp_prices = []
        for comp in comps:
            try:
                comp_prices.append(float(comp.get('price')))
            except (TypeError, ValueError, AttributeError):
                continue
        if comp_prices:
            median_price = statistics.median(comp_prices)
            if median_price > 0 and price > PRICE_COMP_MULTIPLE * median_price:
                return (
                    f"Price ${price:.2f} is more than {PRICE_COMP_MULTIPLE:.0f}x "
                    f"the comp median (${median_price:.2f})"
                )
            # Comp-backed pricing already vetted by the comp-median check above;
            # don't also apply the no-market-data threshold.
            return None

    if not source.startswith('market_data') and price > PRICE_REVIEW_THRESHOLD:
        return (
            f"Price ${price:.2f} exceeds review threshold (${PRICE_REVIEW_THRESHOLD:.2f}) "
            f"with no comp data (source: {source or 'unknown'})"
        )

    return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def apply_pre_listing_guardrails(
    job,
    price: Optional[float] = None,
    source: Optional[str] = None,
    comps: Optional[List[Dict[str, Any]]] = None,
    confidence: Optional[str] = None,
    confidence_reason: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Run the LATE guards (title, brand/aspects, price) against `job`.

    Title and item_specifics are auto-fixed IN PLACE on `job`. Price sanity is
    judgment-call only — it never mutates, it just returns a review_reason if
    the price looks wrong.

    `confidence`/`confidence_reason` come from the pricing engine. 'low' means
    the engine doesn't trust its own number (junk keyword comps, or a
    comps-vs-AI conflict) — that's the under-price guard and it wins over the
    generic price-sanity checks. 'user'/'high'/'medium'/None never gate here.

    If price/source/comps are not passed explicitly, they're read from
    job.ai_data (pricing_comps / pricing_source) when present; price defaults
    to job.price if available.

    Every guard is wrapped so a raise is caught and logged — a guardrail must
    never block a listing by crashing.

    Returns {'review_reason': Optional[str]}.
    """
    review_reason = None

    try:
        specifics = getattr(job, 'item_specifics', None) or {}
        job.item_specifics = normalize_aspects(specifics)
        condition = getattr(job, 'condition', None)
        job.title = optimize_cassini_title(getattr(job, 'title', None), specifics=job.item_specifics, condition=condition)
    except Exception as e:
        logger.error(f"Title/Aspect guardrail failed (job proceeds unmodified): {e}")

    # Under-price guard: engine flagged its own number as untrustworthy.
    if confidence == 'low':
        return {'review_reason': confidence_reason
                or 'Low pricing confidence — check price before listing'}

    try:
        ai_data = getattr(job, 'ai_data', None) or {}
        resolved_price = price if price is not None else getattr(job, 'price', None)
        resolved_source = source if source is not None else ai_data.get('pricing_source')
        resolved_comps = comps if comps is not None else ai_data.get('pricing_comps')
        if resolved_price is not None:
            review_reason = check_price_sanity(resolved_price, resolved_source, resolved_comps)
    except Exception as e:
        logger.error(f"Price sanity guardrail failed (job proceeds unmodified): {e}")

    return {'review_reason': review_reason}
