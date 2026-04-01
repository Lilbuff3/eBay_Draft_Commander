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
    'NEW_WITH_DEFECTS': '1500', 
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

# Map internal enum values to display strings for pricing engine
CONDITION_ENUM_TO_DISPLAY = {
    'NEW': 'New',
    'NEW_OTHER': 'New - Open Box',
    'NEW_WITH_DEFECTS': 'New - Open Box',
    'LIKE_NEW': 'Used - Like New',
    'CERTIFIED_REFURBISHED': 'New - Open Box',
    'EXCELLENT_REFURBISHED': 'Used - Like New',
    'VERY_GOOD_REFURBISHED': 'Used - Like New',
    'GOOD_REFURBISHED': 'Used - Good',
    'SELLER_REFURBISHED': 'Used - Like New',
    'USED_EXCELLENT': 'Used - Like New',
    'USED_VERY_GOOD': 'Used - Like New',
    'USED_GOOD': 'Used - Good',
    'USED_ACCEPTABLE': 'Used - Acceptable',
    'FOR_PARTS_OR_NOT_WORKING': 'For Parts or Not Working',
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
DEFAULT_MIN_PRICE = 15.00  # Minimum price to auto-publish

# Token Refresh Configuration
TOKEN_REFRESH_INTERVAL = 1800  # 30 minutes in seconds (eBay tokens expire at 120min)
TOKEN_RETRY_DELAY = 300  # 5 minutes in seconds

# Rate Limiting Configuration (Issue #8)
# Gemini: env-configurable RPM (default 2 for free tier, 60+ for paid)
GEMINI_RPM_LIMIT = int(os.getenv('GEMINI_RPM_LIMIT', '2'))
GEMINI_REQ_INTERVAL = 60 / GEMINI_RPM_LIMIT # Seconds between calls

# eBay API: 5 RPS (Requests Per Second) for burst management
EBAY_BURST_LIMIT = 5
EBAY_REFILL_RATE = 2 # Tokens per second

# AI Models
AI_MODEL_NAME = 'gemini-2.0-flash' # Updated to latest fast model
AI_PRICING_MODEL = os.getenv('AI_PRICING_MODEL', 'gemini-2.0-flash')  # Pricing/grounding model

# --- Pricing Constants ---
EBAY_FINAL_VALUE_FEE_RATE = 0.1325       # 13.25% eBay final value fee
EBAY_PAYMENT_PROCESSING_FEE = 0.30       # $0.30 per-order payment processing
MIN_LISTING_PRICE = 4.99                  # Floor price for any listing
MAX_LISTING_PRICE = 9999.99               # Ceiling price sanity check
DEFAULT_ESTIMATED_SHIPPING_COST = 6.50    # Baked into price (free shipping policy)
RARITY_PERCENTILE_THRESHOLD = 75          # Use 75th percentile for rare items

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


def get_next_optimal_listing_time():
    """Calculate the next optimal eBay listing time based on peak traffic windows.

    Returns an ISO 8601 UTC datetime string for the ScheduleTime field.
    eBay requires schedule times to be at least 1 hour in the future.
    """
    from datetime import datetime, timedelta, timezone
    import pytz

    pt = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.now(timezone.utc)
    now_pt = now_utc.astimezone(pt)

    # Minimum 75 minutes from now (eBay requires 1 hour, add buffer)
    min_time = now_pt + timedelta(minutes=75)

    candidates = []
    for day_offset in range(8):  # Check next 7 days
        check_date = now_pt + timedelta(days=day_offset)
        for dow, hour in PEAK_WINDOWS_PT:
            if check_date.weekday() == dow:
                candidate = check_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                if candidate > min_time:
                    candidates.append(candidate)

    if not candidates:
        # Fallback: next Sunday 6 PM PT
        days_until_sunday = (6 - now_pt.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        fallback = (now_pt + timedelta(days=days_until_sunday)).replace(
            hour=18, minute=0, second=0, microsecond=0
        )
        candidates.append(fallback)

    # Pick the soonest optimal window
    best = min(candidates)
    return best.astimezone(timezone.utc).isoformat()
