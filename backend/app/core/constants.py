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
DEFAULT_CONDITION = "USED_EXCELLENT"  # Default if no condition specified
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
