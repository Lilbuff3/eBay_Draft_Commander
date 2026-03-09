from typing import Dict, Any
from backend.app.core.models import InternalListing

# Maps numeric Trading API condition IDs to Inventory API string enums.
# See: https://developer.ebay.com/api-docs/sell/static/metadata/condition-id-values.html
CONDITION_ID_MAP: Dict[str, str] = {
    "1000": "NEW",
    "1500": "NEW_OTHER",
    "1750": "NEW_WITH_DEFECTS",
    "2000": "CERTIFIED_REFURBISHED",
    "2500": "SELLER_REFURBISHED",
    "3000": "USED_EXCELLENT",
    "4000": "USED_VERY_GOOD",
    "5000": "USED_GOOD",
    "6000": "USED_ACCEPTABLE",
    "7000": "FOR_PARTS_OR_NOT_WORKING",
}


class TradingAPIAdapter:
    """
    Adapter to convert the InternalListing model into the dictionary
    payload expected by the legacy XML Trading API 'AddFixedPriceItem' call.
    """
    @staticmethod
    def to_trading_payload(listing: InternalListing) -> Dict[str, Any]:
        return {
            'title': listing.title,
            'description': listing.description,
            'price': listing.price,
            'category_id': listing.category_id,
            'condition_id': listing.condition_id,
            'sku': listing.sku,
            'image_urls': listing.image_urls,
            'payment_policy_id': listing.payment_policy_id,
            'return_policy_id': listing.return_policy_id,
            'fulfillment_policy_id': listing.fulfillment_policy_id,
            'item_specifics': listing.item_specifics,
            'postal_code': listing.postal_code,
            'item_location': listing.item_location
        }


class InventoryAPIAdapter:
    """
    Adapter to convert the InternalListing model into the JSON
    payload expected by the modern REST Inventory API.
    Used for features that require the REST API (e.g. out of stock control).
    """
    @staticmethod
    def to_inventory_payload(listing: InternalListing) -> Dict[str, Any]:
        # Map numeric condition_id to Inventory API enum string
        condition_enum = CONDITION_ID_MAP.get(
            str(listing.condition_id),
            listing.condition_id  # Fallback to raw value if unmapped
        )

        # UPC: use listing value, fall back to "Does not apply"
        upc_value = listing.upc if listing.upc else "Does not apply"

        return {
            "product": {
                "title": listing.title,
                "description": listing.description,
                "aspects": listing.item_specifics,
                "imageUrls": listing.image_urls,
                "upc": [upc_value],
            },
            "condition": condition_enum,
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": listing.quantity
                }
            }
        }
