from typing import Dict, Any
from backend.app.core.models import InternalListing

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
        # Maps to creating an Inventory Item + Offer structure
        return {
            "product": {
                "title": listing.title,
                "description": listing.description,
                "aspects": listing.item_specifics,
                "imageUrls": listing.image_urls,
                "upc": ["Does not apply"],
            },
            "condition": listing.condition_id, # Might need enum mapping later
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": 1
                }
            }
        }
