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


# ---------------------------------------------------------------------------
# Brand / aspect normalization
# ---------------------------------------------------------------------------

def normalize_aspects(specs: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize identity aspects (Brand) in `specs`.

    - Blocklisted non-brand tokens ("Signed", "Various", "N/A", "Unknown",
      "Unbranded") -> "Unbranded" (case-insensitive compare).
    - "A / B" style multi-value strings -> first meaningful value ("A").
    - Empty/junk values are dropped entirely.

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

    return result


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
) -> Dict[str, Optional[str]]:
    """Run the LATE guards (title, brand/aspects, price) against `job`.

    Title and item_specifics are auto-fixed IN PLACE on `job`. Price sanity is
    judgment-call only — it never mutates, it just returns a review_reason if
    the price looks wrong.

    If price/source/comps are not passed explicitly, they're read from
    job.ai_data (pricing_comps / pricing_source) when present; price defaults
    to job.price if available.

    Every guard is wrapped so a raise is caught and logged — a guardrail must
    never block a listing by crashing.

    Returns {'review_reason': Optional[str]}.
    """
    review_reason = None

    try:
        job.title = clean_title(getattr(job, 'title', None))
    except Exception as e:
        logger.error(f"Title guardrail failed (job proceeds unmodified): {e}")

    try:
        specifics = getattr(job, 'item_specifics', None) or {}
        job.item_specifics = normalize_aspects(specifics)
    except Exception as e:
        logger.error(f"Aspect guardrail failed (job proceeds unmodified): {e}")

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
