"""
Global Constants for eBay Draft Commander
"""
import os

# Condition Mapping from Folder Names/User Input to eBay Enum
CONDITION_MAP = {
    'New': 'NEW',
    'New Open Box': 'NEW_OTHER',
    'New With Defects': 'NEW_WITH_DEFECTS',
    'New Old Stock': 'NEW_OTHER', # Special handling for NOS
    'Like New': 'LIKE_NEW',
    'Certified Refurbished': 'CERTIFIED_REFURBISHED',
    'Excellent Refurbished': 'EXCELLENT_REFURBISHED',
    'Very Good Refurbished': 'VERY_GOOD_REFURBISHED',
    'Good Refurbished': 'GOOD_REFURBISHED',
    'Seller Refurbished': 'SELLER_REFURBISHED',
    'Used Excellent': 'USED_EXCELLENT',
    'Used Very Good': 'USED_VERY_GOOD',
    'Used Good': 'USED_GOOD',
    'Used Acceptable': 'USED_ACCEPTABLE',
    'Used': 'USED_GOOD',
    'For Parts': 'FOR_PARTS_OR_NOT_WORKING'
}

# eBay Trading API Condition IDs
CONDITION_ID_MAP = {
    'NEW': '1000',
    'NEW_OTHER': '1500',
    'NEW_WITH_DEFECTS': '1750', 
    'LIKE_NEW': '3000', # Used (Excellent)
    'CERTIFIED_REFURBISHED': '2000',
    'EXCELLENT_REFURBISHED': '2500',
    'VERY_GOOD_REFURBISHED': '2500',
    'GOOD_REFURBISHED': '2500',
    'SELLER_REFURBISHED': '2500',
    'USED_EXCELLENT': '3000', # Used
    'USED_VERY_GOOD': '4000', # Very Good
    'USED_GOOD': '5000', # Good
    'USED_ACCEPTABLE': '6000', # Acceptable
    'FOR_PARTS_OR_NOT_WORKING': '7000'
}

# Supported Image Formats
SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.tif'}

# eBay API Limits and Defaults
DEFAULT_CATEGORY_ID = "170599"  # Other > Everything Else (fallback category)
MAX_IMAGES_PER_LISTING = 12  # eBay allows max 12 images per listing
DEFAULT_CONDITION = os.getenv('DEFAULT_CONDITION', 'USED_EXCELLENT')  # Default if no condition specified
TITLE_MAX_LENGTH = 80  # eBay title character limit
ASPECT_VALUE_MAX_LENGTH = 65  # eBay item specific value character limit

# AI Analysis Configuration
MAX_AI_IMAGES = 8  # Gemini API limit per request
AI_REQUIRED_KEYS = ['identification', 'listing']  # Required response fields

# Auto-Publish Configuration
DEFAULT_CONFIDENCE_THRESHOLD = 85  # Minimum AI confidence % to auto-publish
DEFAULT_MIN_PRICE = 10.00  # Minimum price to auto-publish

# Token Refresh Configuration
TOKEN_REFRESH_INTERVAL = 1800  # 30 minutes in seconds (eBay tokens expire at 120min)
TOKEN_RETRY_DELAY = 300  # 5 minutes in seconds

# Rate Limiting Configuration (Issue #8)
# Gemini: env-configurable RPM (default 60 for paid tier, set to 2 for free tier)
GEMINI_RPM_LIMIT = int(os.getenv('GEMINI_RPM_LIMIT', '60'))
GEMINI_REQ_INTERVAL = 60 / GEMINI_RPM_LIMIT # Seconds between calls

# eBay API: 5 RPS (Requests Per Second) for burst management
EBAY_BURST_LIMIT = 5
EBAY_REFILL_RATE = 2 # Tokens per second

# AI Models
AI_MODEL_NAME = 'gemini-3-flash-preview' # Upgraded: frontier vision + reasoning (was 2.0-flash)
AI_PRICING_MODEL = os.getenv('AI_PRICING_MODEL', 'gemini-3-flash-preview')  # Pricing/grounding model

# No-blocks engine: minimum confidence to accept a model-guessed required aspect.
# Deliberately low — a best-guess on an editable/scheduled listing beats blocking.
ASPECT_RESOLVE_CONFIDENCE_FLOOR = 0.65

# --- Pricing Constants ---
EBAY_FINAL_VALUE_FEE_RATE = 0.1325       # 13.25% eBay final value fee
EBAY_PAYMENT_PROCESSING_FEE = 0.30       # $0.30 per-order payment processing
MIN_LISTING_PRICE = 4.99                  # Floor price for any listing
MAX_LISTING_PRICE = 9999.99               # Ceiling price sanity check
RARITY_PERCENTILE_THRESHOLD = 75          # Use 75th percentile for rare items
ACTIVE_TO_SOLD_FACTOR = float(os.getenv('ACTIVE_TO_SOLD_FACTOR', '0.87'))  # comps are ACTIVE asking prices; discount toward estimated sold value

# --- Trading API Constants ---
TRADING_API_TIMEOUT = 30                  # seconds
TRADING_API_MAX_RETRIES = 2
TRADING_API_PAGE_SIZE = 200               # GetSellerList entries per page

# --- Shipping Tiers ---
SHIPPING_LOOKUP = {
    'small': 4.50,   # < 1lb (USPS Ground Advantage)
    'medium': 6.50,  # 1-3lb
    'large': 10.00,  # 3-10lb
    'heavy': 15.00,  # 10+lb
}
MEDIA_MAIL_COST = 3.50  # USPS Media Mail (books, CDs, DVDs)
DEFAULT_SHIPPING_COST = 6.50
# Package weight fallback for the Trading API. eBay requires a weight on
# Authenticity-Guarantee items (high-value sneakers, handbags, watches) or it
# rejects the listing with error 717. Used when the AI gives no estimate.
DEFAULT_PACKAGE_WEIGHT_LBS = float(os.getenv('DEFAULT_PACKAGE_WEIGHT_LBS', '2'))

# eBay book/media category IDs (top-level and common subcategories)
MEDIA_MAIL_CATEGORIES = {
    '267',      # Books
    '261186',   # Books > Nonfiction
    '171228',   # Books > Fiction
    '29223',    # Books > Antiquarian & Collectible
    '2228',     # Books > Textbooks
    '11104',    # Cookbooks
    '171243',   # Children's Books
    '176973',   # Audiobooks
    '11232',    # CDs
    '176984',   # DVDs & Blu-ray
    '617',      # Records/Vinyl
    '80183',    # Video Games (disc-based)
}


def get_shipping_cost(
    category_id: str = None,
    isbn: str = None,
    package_size: str = None,
    estimated_weight_lbs: float = None,
) -> float:
    """Calculate shipping cost tier with Media Mail detection.

    Priority:
    1. Media Mail eligible (ISBN present OR book/media category) -> $3.50
    2. AI-detected package size -> tier lookup
    3. AI-estimated weight -> tier by weight bracket
    4. Fallback -> DEFAULT_SHIPPING_COST ($6.50)
    """
    # 1. Media Mail detection
    if isbn:
        return MEDIA_MAIL_COST
    if category_id and str(category_id) in MEDIA_MAIL_CATEGORIES:
        return MEDIA_MAIL_COST

    # 2. Package size from AI
    if package_size and package_size.lower() in SHIPPING_LOOKUP:
        return SHIPPING_LOOKUP[package_size.lower()]

    # 3. Weight-based tier
    if isinstance(estimated_weight_lbs, (int, float)):
        if estimated_weight_lbs < 1:
            return SHIPPING_LOOKUP['small']
        if estimated_weight_lbs <= 3:
            return SHIPPING_LOOKUP['medium']
        if estimated_weight_lbs <= 10:
            return SHIPPING_LOOKUP['large']
        return SHIPPING_LOOKUP['heavy']

    # 4. Fallback
    return DEFAULT_SHIPPING_COST



# --- Optimal Listing Schedule ---
# eBay peak traffic windows (Pacific Time):
#   Sunday 6-9 PM PT (highest traffic)
#   Monday-Thursday 7-9 PM PT (weekday evenings)
#   Saturday 10 AM-12 PM PT (weekend morning)
# Schedule listings to START at these windows for maximum visibility.
# eBay ScheduleTime must be 1+ hour in the future and within 21 days.

PEAK_WINDOWS_PT = [
    # (day_of_week, hour_start) — 0=Monday, 6=Sunday
    (6, 18),  # Sunday 6 PM PT — highest traffic
    (6, 19),  # Sunday 7 PM PT
    (6, 20),  # Sunday 8 PM PT
    (0, 19),  # Monday 7 PM PT
    (1, 19),  # Tuesday 7 PM PT
    (2, 19),  # Wednesday 7 PM PT
    (3, 19),  # Thursday 7 PM PT
    (5, 10),  # Saturday 10 AM PT
    (5, 11),  # Saturday 11 AM PT
    (4, 19),  # Friday 7 PM PT (lower but still decent)
]


def get_next_optimal_listing_time(exclude_times=None):
    """Next optimal eBay listing time (ISO 8601 UTC), >= 75 min ahead, within 21 days.

    exclude_times: optional iterable of ISO-8601-UTC strings already booked. The
    soonest peak window NOT in this set is returned, so concurrent items stagger
    across distinct windows instead of colliding on one time.
    """
    from datetime import datetime, timedelta, timezone
    import pytz

    exclude = set(exclude_times or [])
    pt = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.now(timezone.utc)
    now_pt = now_utc.astimezone(pt)
    min_time = now_pt + timedelta(minutes=75)  # eBay requires >= 1h; add buffer

    candidates = []
    for day_offset in range(22):  # today .. 21 days ahead (eBay cap)
        check_date = now_pt + timedelta(days=day_offset)
        for dow, hour in PEAK_WINDOWS_PT:
            if check_date.weekday() == dow:
                # Construct naive local datetime for the peak window time
                naive_cand = datetime(check_date.year, check_date.month, check_date.day, hour, 0, 0, 0)
                # Localize properly using America/Los_Angeles timezone to correctly calculate DST offset
                try:
                    cand = pt.localize(naive_cand, is_dst=None)
                except pytz.InvalidTimeError:
                    # Fallback for invalid or ambiguous local times (e.g. spring forward skipped hour)
                    cand = pt.localize(naive_cand, is_dst=False)
                
                if cand > min_time:
                    candidates.append(cand)
    candidates.sort()

    for cand in candidates:
        iso = cand.astimezone(timezone.utc).isoformat()
        if iso not in exclude:
            return iso

    # Every peak window within 21 days is booked: stagger off the soonest window
    # in deterministic 20-minute steps so no two items collide.
    base = candidates[0] if candidates else min_time
    staggered = base + timedelta(minutes=20 * (len(exclude) + 1))
    return staggered.astimezone(timezone.utc).isoformat()
