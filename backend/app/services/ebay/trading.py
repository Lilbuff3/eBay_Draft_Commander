import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from backend.app.core.logger import get_logger
from backend.app.services.ebay.policies import load_env

logger = get_logger('ebay_trading_service')

class TradingService:
    """Service for handling legacy eBay Trading API (XML) interactions"""
    
    def get_active_listings_light(self):
        """
        Use GetSellerList (Trading API) to fetch ALL active items.
        This successfully found 154 items in testing (even if some fields were tricky).
        """
        try:
            creds = load_env()
            token = creds.get('EBAY_USER_TOKEN')
            if not token: return {'error': 'No token'}, 500

            TRADING_URL = 'https://api.ebay.com/ws/api.dll'
            
            # 120 days future window covers active GTC listings
            now = datetime.utcnow()
            future = now + timedelta(days=120)
            end_time_to = future.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            end_time_from = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            all_items = []
            page = 1
            has_more = True
            
            while has_more:
                xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
                <GetSellerListRequest xmlns="urn:ebay:apis:eBLBaseComponents">
                  <RequesterCredentials><eBayAuthToken>{token}</eBayAuthToken></RequesterCredentials>
                  <EndTimeFrom>{end_time_from}</EndTimeFrom>
                  <EndTimeTo>{end_time_to}</EndTimeTo>
                  <Sort>2</Sort>
                  <Pagination>
                    <EntriesPerPage>200</EntriesPerPage>
                    <PageNumber>{page}</PageNumber>
                  </Pagination>
                  <OutputSelector>PaginationResult</OutputSelector>
                  <OutputSelector>ItemArray.Item.ItemID</OutputSelector>
                  <OutputSelector>ItemArray.Item.Title</OutputSelector>
                  <OutputSelector>ItemArray.Item.SKU</OutputSelector>
                  <OutputSelector>ItemArray.Item.SellingStatus.CurrentPrice</OutputSelector>
                  <OutputSelector>ItemArray.Item.SellingStatus.ListingStatus</OutputSelector>
                  <OutputSelector>ItemArray.Item.QuantityAvailable</OutputSelector>
                  <OutputSelector>ItemArray.Item.Quantity</OutputSelector>
                  <OutputSelector>ItemArray.Item.PictureDetails.GalleryURL</OutputSelector>
                </GetSellerListRequest>"""
                
                headers = {
                    'X-EBAY-API-SITEID': '0',
                    'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
                    'X-EBAY-API-CALL-NAME': 'GetSellerList',
                    'Content-Type': 'text/xml'
                }

                # Retry logic
                retry_count = 0
                max_retries = 2
                response = None
                
                while retry_count <= max_retries:
                    try:
                        response = requests.post(TRADING_URL, headers=headers, data=xml_request, timeout=30)
                        if response.status_code == 200:
                            break
                        elif response.status_code == 500:
                            retry_count += 1
                            import time
                            time.sleep(1)
                        else:
                            break
                    except Exception:
                        retry_count += 1
                        import time
                        time.sleep(1)

                if not response or response.status_code != 200:
                    logger.error(f"GetSellerList page {page} failed: {response.status_code if response else 'No Response'}")
                    break

                # Parse XML
                root = ET.fromstring(response.content)
                ns = {'e': 'urn:ebay:apis:eBLBaseComponents'}
                
                ack = root.find('.//e:Ack', ns)
                if ack is not None and ack.text == 'Failure':
                    break

                item_array = root.find('e:ItemArray', ns)
                page_items = []
                if item_array is not None:
                    for item in item_array.findall('e:Item', ns):
                        page_items.append(self._parse_item_xml(item, ns))
                
                all_items.extend(page_items)
                
                # Check pagination
                pagination = root.find('e:PaginationResult', ns)
                if pagination is not None:
                    total_pages_node = pagination.find('e:TotalNumberOfPages', ns)
                    total_pages = int(total_pages_node.text) if total_pages_node is not None else 0
                    if page >= total_pages:
                        has_more = False
                    else:
                        page += 1
                else:
                    has_more = False

            if not all_items:
                 return {'error': 'No items found via Trading API'}, 404

            return {
                'listings': all_items,
                'total': len(all_items),
                'source': 'eBay Trading API (GetSellerList)'
            }, 200
            
        except Exception as e:
            logger.error(f"Trading Light Error: {e}")
            return {'error': str(e)}, 500

    def _parse_item_xml(self, item, ns):
        """Helper to parse individual item XML from Trading API"""
        # Safe extraction helper
        def get_text(node, tag):
            n = node.find(tag, ns)
            return n.text if n is not None else None

        listing_id = get_text(item, 'e:ItemID') or 'Unknown'
        sku = get_text(item, 'e:SKU') or ''
        title = get_text(item, 'e:Title')
        
        # Fallback for untitled items
        if not title or title.strip() == "":
            title = f"Legacy Item {listing_id}"
        
        price = 0.0
        currency = 'USD'
        
        selling_status = item.find('e:SellingStatus', ns)
        if selling_status is not None:
            current_price = selling_status.find('e:CurrentPrice', ns)
            if current_price is not None:
                try:
                    price = float(current_price.text)
                except (ValueError, TypeError):
                    price = 0.0
                currency = current_price.get('currencyID', 'USD')
        
        quantity = 0
        quantity_avail = get_text(item, 'e:QuantityAvailable')
        if quantity_avail:
             quantity = int(quantity_avail)
        else:
             q_val = get_text(item, 'e:Quantity')
             if q_val: quantity = int(q_val)

        image_url = None
        picture_details = item.find('e:PictureDetails', ns)
        if picture_details is not None:
            image_url = get_text(picture_details, 'e:GalleryURL')
            
        return {
            'sku': sku,
            'offerId': None,
            'listingId': listing_id,
            'title': title,
            'price': price,
            'currency': currency,
            'availableQuantity': quantity,
            'imageUrl': image_url,
            'status': 'Active',
            'condition': 'Used'
        }
