from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class InternalListing:
    """
    Single Source of Truth for a listing within the application.
    This model abstracts away the differences between eBay's XML Trading API
    and JSON Inventory API, allowing business logic to operate uniformly.
    """
    sku: str
    title: str
    description: str  # HTML description
    price: str        # e.g., "29.99"
    category_id: str
    condition_id: str
    image_urls: List[str] = field(default_factory=list)
    item_specifics: Dict[str, List[str]] = field(default_factory=dict)
    
    # Policies
    payment_policy_id: Optional[str] = None
    return_policy_id: Optional[str] = None
    fulfillment_policy_id: Optional[str] = None
    
    # Location
    postal_code: Optional[str] = None
    item_location: Optional[str] = None
    
    # Inventory
    quantity: int = 1
    upc: Optional[str] = None  # None means "Does not apply"
    
    # Meta / Sync
    scheduled_time: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easier logging or fallback logic"""
        from dataclasses import asdict
        return asdict(self)
