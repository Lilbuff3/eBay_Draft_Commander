import os
import time
import requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape
from datetime import datetime, timedelta, timezone
from backend.app.core.logger import get_logger
from backend.app.core.constants import TRADING_API_TIMEOUT, TRADING_API_MAX_RETRIES, TRADING_API_PAGE_SIZE
from backend.app.services.ebay.policies import load_env
from backend.app.core.token_manager import get_token_manager

logger = get_logger('ebay_trading_service')


def _replace_auth_token(xml_str: str, new_token: str) -> str:
    """Replace eBayAuthToken in XML using proper ElementTree parsing.

    Handles special characters safely (no XML injection risk).
    """
    ns = 'urn:ebay:apis:eBLBaseComponents'
    # Register namespace to avoid ns0: prefix in output
    ET.register_namespace('', ns)

    root = ET.fromstring(xml_str)
    token_elem = root.find('.//{%s}eBayAuthToken' % ns)
    if token_elem is not None:
        token_elem.text = new_token

    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding='unicode')


class TradingService:
    """Service for handling legacy eBay Trading API (XML) interactions"""
    
    def get_active_listings_light(self):
        """
        Use GetSellerList (Trading API) to fetch ALL active items.
        This successfully found 154 items in testing (even if some fields were tricky).
        """
        try:
            from backend.app.core.token_manager import get_token_manager
            tm = get_token_manager()
            token = tm.get_access_token()
            if not token:
                creds = load_env()
                token = creds.get('EBAY_USER_TOKEN')
            if not token: return {'error': 'No token'}, 500

            TRADING_URL = 'https://api.ebay.com/ws/api.dll'
            
            # 120 days future window covers active GTC listings
            now = datetime.now(timezone.utc)
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
                  <DetailLevel>ReturnAll</DetailLevel>
                  <Pagination>
                    <EntriesPerPage>{TRADING_API_PAGE_SIZE}</EntriesPerPage>
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
                  <OutputSelector>ItemArray.Item.PictureDetails.PictureURL</OutputSelector>
                </GetSellerListRequest>"""
                
                headers = {
                    'X-EBAY-API-SITEID': '0',
                    'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
                    'X-EBAY-API-CALL-NAME': 'GetSellerList',
                    'Content-Type': 'text/xml'
                }

                # Retry logic
                retry_count = 0
                max_retries = TRADING_API_MAX_RETRIES
                response = None

                while retry_count <= max_retries:
                    try:
                        response = requests.post(TRADING_URL, headers=headers, data=xml_request, timeout=TRADING_API_TIMEOUT)
                        if response.status_code == 200:
                            break
                        elif response.status_code == 401:
                            logger.warning(f"GetSellerList: Token expired (401), refreshing... (attempt {retry_count + 1}/{max_retries + 1})")
                            from backend.app.core.token_manager import get_token_manager
                            tm = get_token_manager()
                            if tm.force_refresh():
                                token = tm.get_access_token()
                            else:
                                creds = load_env()
                                token = creds.get('EBAY_USER_TOKEN')
                            if not token:
                                logger.error("GetSellerList: No token available after refresh")
                                break
                            # Rebuild XML with refreshed token
                            xml_request = _replace_auth_token(xml_request, token)
                            retry_count += 1
                            time.sleep(1)
                        elif response.status_code == 429:
                            backoff = 2 ** retry_count
                            logger.warning(f"GetSellerList: Rate limited by eBay (429), backing off {backoff}s... (attempt {retry_count + 1}/{max_retries + 1})")
                            retry_count += 1
                            time.sleep(backoff)
                        elif response.status_code == 500:
                            logger.warning(f"GetSellerList: Server error (500), retrying... (attempt {retry_count + 1}/{max_retries + 1})")
                            retry_count += 1
                            time.sleep(1)
                        else:
                            logger.warning(f"GetSellerList: Unexpected HTTP {response.status_code}, not retrying")
                            break
                    except Exception as e:
                        logger.warning(f"GetSellerList: Request exception: {e} (attempt {retry_count + 1}/{max_retries + 1})")
                        retry_count += 1
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

    def add_fixed_price_item(self, item_data: dict, schedule_time: str = None):
        """
        Creates a Fixed Price Listing using the Trading API (AddFixedPriceItem).
        Supports native eBay scheduling via `schedule_time`.

        Args:
            item_data (dict): Dictionary containing item details:
                - title
                - description
                - price
                - category_id
                - condition_id
                - sku
                - image_urls (list)
                - payment_policy_id
                - return_policy_id
                - fulfillment_policy_id
                - paypal_email (optional, legacy requirement)
                - postal_code (optional)
            schedule_time (str, optional): ISO 8601 string for scheduled posting.
        
        Returns:
            dict: {success, item_id, error}
        """
        try:
            from backend.app.core.token_manager import get_token_manager
            tm = get_token_manager()
            token = tm.get_access_token()
            if not token:
                creds = load_env()
                token = creds.get('EBAY_USER_TOKEN')
            if not token: return {'success': False, 'error': 'No eBay User Token found'}

            TRADING_URL = 'https://api.ebay.com/ws/api.dll'

            # Define Namespaces
            xmlns = "urn:ebay:apis:eBLBaseComponents"

            # Construct XML Body
            # Note: We use f-strings for simplicity, but for complex user input, 
            # consider using ElementTree to avoid XML injection issues. 
            # However, our validator sanitizes most inputs.
            
            # Helper for optional tags (XML-safe)
            def tag(name, value, cdata=False):
                if not value: return ""
                val_str = str(value)
                if cdata:
                    # Safely wrap in CDATA, neutralizing any internal CDATA closing tags
                    safe_val = val_str.replace("]]>", "]]]]><![CDATA[>")
                    return f"<{name}><![CDATA[{safe_val}]]></{name}>"
                else:
                    return f"<{name}>{xml_escape(val_str)}</{name}>"

            # Seller Profiles (Business Policies)
            payment_policy_id = item_data.get('payment_policy_id')
            return_policy_id = item_data.get('return_policy_id')
            fulfillment_policy_id = item_data.get('fulfillment_policy_id')
            
            seller_profiles = ""
            if payment_policy_id and return_policy_id and fulfillment_policy_id:
                seller_profiles = f"""<SellerProfiles>
                        <SellerPaymentProfile>
                            <PaymentProfileID>{payment_policy_id}</PaymentProfileID>
                        </SellerPaymentProfile>
                        <SellerReturnProfile>
                            <ReturnProfileID>{return_policy_id}</ReturnProfileID>
                        </SellerReturnProfile>
                        <SellerShippingProfile>
                            <ShippingProfileID>{fulfillment_policy_id}</ShippingProfileID>
                        </SellerShippingProfile>
                    </SellerProfiles>"""

            # Prepare Images
            picture_details = ""
            if item_data.get('image_urls'):
                picture_details = "<PictureDetails><GalleryType>Gallery</GalleryType>"
                for url in item_data['image_urls']:
                    picture_details += f"<PictureURL>{url}</PictureURL>"
                picture_details += "</PictureDetails>"

            # Prepare Schedule Time (must be UTC: YYYY-MM-DDTHH:MM:SS.000Z)
            schedule_tag = ""
            if schedule_time:
                try:
                    from datetime import timezone as tz
                    # Handle both datetime objects and ISO string inputs
                    if isinstance(schedule_time, datetime):
                        parsed = schedule_time
                    else:
                        parsed = datetime.fromisoformat(str(schedule_time).replace('Z', '+00:00'))
                    utc_time = parsed.astimezone(tz.utc)
                    formatted = utc_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                    schedule_tag = f"<ScheduleTime>{formatted}</ScheduleTime>"
                    logger.info(f"Schedule time normalized to UTC: {formatted}")
                except Exception as e:
                    logger.warning(f"Could not parse schedule_time '{schedule_time}': {e}. Skipping schedule.")
                    schedule_tag = ""

            xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
            <AddFixedPriceItemRequest xmlns="{xmlns}">
                <RequesterCredentials>
                    <eBayAuthToken>{token}</eBayAuthToken>
                </RequesterCredentials>
                <ErrorLanguage>en_US</ErrorLanguage>
                <WarningLevel>High</WarningLevel>
                <Item>
                    {schedule_tag}
                    {tag('Title', item_data.get('title'))}
                    {tag('Description', item_data.get('description'), cdata=True)}
                    <PrimaryCategory>
                        <CategoryID>{item_data.get('category_id', '1')}</CategoryID>
                    </PrimaryCategory>
                    <StartPrice currencyID="USD">{item_data.get('price')}</StartPrice>
                    <ConditionID>{item_data.get('condition_id', '3000')}</ConditionID>
                    {tag('SKU', item_data.get('sku'))}
                    <Country>US</Country>
                    <Currency>USD</Currency>
                    <DispatchTimeMax>3</DispatchTimeMax>
                    <ListingDuration>GTC</ListingDuration>
                    <ListingType>FixedPriceItem</ListingType>
                    {picture_details}
                    {seller_profiles}
                    {tag('PostalCode', item_data.get('postal_code'))}
                    {tag('Location', item_data.get('item_location', os.environ.get('EBAY_ITEM_LOCATION', 'Clovis, CA')))}
                    <ItemSpecifics>
                        {self._build_item_specifics_xml(item_data.get('item_specifics', {}))}
                    </ItemSpecifics>
                </Item>
            </AddFixedPriceItemRequest>
            """

            headers = {
                'X-EBAY-API-SITEID': '0',
                'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
                'X-EBAY-API-CALL-NAME': 'AddFixedPriceItem',
                'Content-Type': 'text/xml'
            }

            logger.info(f"Sending AddFixedPriceItem for SKU {item_data.get('sku')}...")

            # Retry logic
            retry_count = 0
            max_retries = TRADING_API_MAX_RETRIES
            response = None

            while retry_count <= max_retries:
                try:
                    response = requests.post(TRADING_URL, headers=headers, data=xml_request.encode('utf-8'), timeout=60)
                    if response.status_code == 200:
                        break
                    elif response.status_code == 401:
                        logger.warning(f"AddFixedPriceItem: Token expired (401), refreshing... (attempt {retry_count + 1}/{max_retries + 1})")
                        tm = get_token_manager()
                        if not tm.force_refresh():
                            logger.error("AddFixedPriceItem: Token refresh failed")
                            break
                        token = tm.get_access_token()
                        if not token:
                            logger.error("AddFixedPriceItem: No token available after refresh")
                            break
                        # Rebuild XML with refreshed token
                        xml_request = _replace_auth_token(xml_request, token)
                        retry_count += 1
                        time.sleep(1)
                    elif response.status_code == 429:
                        backoff = 2 ** retry_count
                        logger.warning(f"AddFixedPriceItem: Rate limited by eBay (429), backing off {backoff}s... (attempt {retry_count + 1}/{max_retries + 1})")
                        retry_count += 1
                        time.sleep(backoff)
                    elif response.status_code == 500:
                        logger.warning(f"AddFixedPriceItem: Server error (500), retrying... (attempt {retry_count + 1}/{max_retries + 1})")
                        retry_count += 1
                        time.sleep(1)
                    else:
                        logger.warning(f"AddFixedPriceItem: Unexpected HTTP {response.status_code}, not retrying")
                        break
                except Exception as e:
                    logger.warning(f"AddFixedPriceItem: Request exception: {e} (attempt {retry_count + 1}/{max_retries + 1})")
                    retry_count += 1
                    time.sleep(1)

            if not response or response.status_code != 200:
                error_detail = response.text[:200] if response else 'No Response'
                logger.error(f"Trading API HTTP Error: {response.status_code if response else 'N/A'} - {error_detail}")
                return {'success': False, 'error': f"HTTP {response.status_code if response else 'No Response'}"}

            # Parse Response
            root = ET.fromstring(response.content)
            ns = {'e': xmlns}
            
            ack = root.find('.//e:Ack', ns).text
            
            if ack in ['Success', 'Warning']:
                item_id = root.find('.//e:ItemID', ns).text
                start_time = root.find('.//e:StartTime', ns).text
                return {
                    'success': True, 
                    'item_id': item_id, 
                    'start_time': start_time,
                    'status': 'Scheduled' if schedule_time else 'Active'
                }
            else:
                # Extract Errors
                errors = []
                for err in root.findall('.//e:Errors', ns):
                    code = err.find('e:ErrorCode', ns).text
                    msg = err.find('e:LongMessage', ns).text
                    errors.append(f"{code}: {msg}")
                
                logger.error(f"Trading API Failure: {errors}")
                return {'success': False, 'error': "; ".join(errors)}

        except Exception as e:
            logger.exception("AddFixedPriceItem Exception")
            return {'success': False, 'error': str(e)}

    def _build_item_specifics_xml(self, specifics):
        """Helper to build ItemSpecifics XML"""
        if not specifics: return ""
        xml = ""
        for name, value in specifics.items():
            val_list = value if isinstance(value, list) else [value]
            for v in val_list:
                xml += f"<NameValueList><Name>{xml_escape(str(name))}</Name><Value>{xml_escape(str(v))}</Value></NameValueList>"
        return xml

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
            if not image_url:
                # Fallback to first PictureURL if GalleryURL not present
                pic_url = picture_details.find('e:PictureURL', ns)
                if pic_url is not None:
                    image_url = pic_url.text
            
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

    def end_fixed_price_item(self, item_id: str, reason: str = 'NotAvailable'):
        """
        End a fixed-price listing using Trading API EndFixedPriceItem.

        Args:
            item_id: The eBay listing ItemID to end.
            reason: EndingReason - NotAvailable, LostOrBroken, Incorrect, OtherListingError

        Returns:
            dict: {success, end_time, error}
        """
        try:
            from backend.app.core.token_manager import get_token_manager
            tm = get_token_manager()
            token = tm.get_access_token()
            if not token:
                creds = load_env()
                token = creds.get('EBAY_USER_TOKEN')
            if not token:
                return {'success': False, 'error': 'No eBay User Token found'}

            xmlns = "urn:ebay:apis:eBLBaseComponents"
            xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
            <EndFixedPriceItemRequest xmlns="{xmlns}">
                <RequesterCredentials>
                    <eBayAuthToken>{token}</eBayAuthToken>
                </RequesterCredentials>
                <ErrorLanguage>en_US</ErrorLanguage>
                <ItemID>{item_id}</ItemID>
                <EndingReason>{reason}</EndingReason>
            </EndFixedPriceItemRequest>"""

            headers = {
                'X-EBAY-API-SITEID': '0',
                'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
                'X-EBAY-API-CALL-NAME': 'EndFixedPriceItem',
                'Content-Type': 'text/xml'
            }

            response = requests.post(
                'https://api.ebay.com/ws/api.dll',
                headers=headers, data=xml_request.encode('utf-8'), timeout=TRADING_API_TIMEOUT
            )

            if response.status_code != 200:
                return {'success': False, 'error': f'HTTP {response.status_code}'}

            root = ET.fromstring(response.content)
            ns = {'e': xmlns}
            ack = root.find('.//e:Ack', ns).text

            if ack in ['Success', 'Warning']:
                end_time_node = root.find('.//e:EndTime', ns)
                end_time = end_time_node.text if end_time_node is not None else None
                logger.info(f"Successfully ended listing {item_id}")
                return {'success': True, 'end_time': end_time}
            else:
                errors = []
                for err in root.findall('.//e:Errors', ns):
                    code = err.find('e:ErrorCode', ns).text
                    msg = err.find('e:LongMessage', ns).text
                    errors.append(f"{code}: {msg}")
                logger.error(f"EndFixedPriceItem failed: {errors}")
                return {'success': False, 'error': '; '.join(errors)}

        except Exception as e:
            logger.exception("EndFixedPriceItem Exception")
            return {'success': False, 'error': str(e)}
