import os
import time
import requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape
from datetime import datetime, timedelta, timezone
from backend.app.core.logger import get_logger
from backend.app.core.constants import TRADING_API_TIMEOUT, TRADING_API_MAX_RETRIES, TRADING_API_PAGE_SIZE, DEFAULT_PACKAGE_WEIGHT_LBS


def build_shipping_package_xml(weight_lbs) -> str:
    """ShippingPackageDetails block with a valid package weight. eBay rejects
    Authenticity-Guarantee items (error 717) without one. Falls back to
    DEFAULT_PACKAGE_WEIGHT_LBS when the estimate is missing or non-positive."""
    try:
        w = float(weight_lbs)
    except (TypeError, ValueError):
        w = 0
    if w <= 0:
        w = DEFAULT_PACKAGE_WEIGHT_LBS
    major = int(w)
    minor = int(round((w - major) * 16))
    if minor == 16:  # rounding pushed oz to a full pound
        major += 1
        minor = 0
    # No <MeasurementSystem>: eBay's AddFixedPriceItem schema doesn't declare it here
    # (Trading API warning 21927 — "not a declared element ... will be ignored"). The
    # unit is already carried on the WeightMajor/WeightMinor attributes.
    return (
        "<ShippingPackageDetails>"
        f'<WeightMajor unit="lbs">{major}</WeightMajor>'
        f'<WeightMinor unit="oz">{minor}</WeightMinor>'
        "</ShippingPackageDetails>"
    )


def build_best_offer_xml(item_data) -> tuple:
    """Best Offer blocks for AddFixedPriceItem.

    Returns (best_offer_details_block, listing_details_block); both empty
    strings unless item_data['best_offer_enabled'] is truthy. eBay rejects
    floors >= StartPrice, so amounts are clamped strictly below it, and the
    minimum (auto-decline) never exceeds the auto-accept.
    """
    if not item_data.get('best_offer_enabled'):
        return '', ''
    details = ('<BestOfferDetails>'
               '<BestOfferEnabled>true</BestOfferEnabled>'
               '</BestOfferDetails>')
    try:
        price = float(item_data.get('price') or 0)
    except (TypeError, ValueError):
        price = 0

    def _floor(value):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        if v <= 0:
            return None
        if price > 0 and v >= price:
            v = round(price * 0.99, 2)
        return v

    accept = _floor(item_data.get('best_offer_auto_accept'))
    minimum = _floor(item_data.get('best_offer_minimum'))
    if accept is not None and minimum is not None and minimum > accept:
        minimum = accept
    parts = ''
    if accept is not None:
        parts += f'<BestOfferAutoAcceptPrice currencyID="USD">{accept:.2f}</BestOfferAutoAcceptPrice>'
    if minimum is not None:
        parts += f'<MinimumBestOfferPrice currencyID="USD">{minimum:.2f}</MinimumBestOfferPrice>'
    listing = f'<ListingDetails>{parts}</ListingDetails>' if parts else ''
    return details, listing
from backend.app.services.ebay.policies import load_env
from backend.app.core.token_manager import get_token_manager

logger = get_logger('ebay_trading_service')

TRADING_URL = 'https://api.ebay.com/ws/api.dll'


def _trading_headers(call_name: str) -> dict:
    return {
        'X-EBAY-API-SITEID': '0',
        'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
        'X-EBAY-API-CALL-NAME': call_name,
        'Content-Type': 'text/xml'
    }


def _refresh_trading_token():
    """Refresh the eBay access token, falling back to the .env user token."""
    tm = get_token_manager()
    if tm.force_refresh():
        token = tm.get_access_token()
        if token:
            return token
    creds = load_env()
    return creds.get('EBAY_USER_TOKEN')


def _post_trading_request(call_name: str, xml_request: str, ambiguous_guard=None):
    """POST a Trading API XML request with 401-refresh / 429-backoff / 500-retry.

    ambiguous_guard: optional callable() -> dict|None. Invoked when a request
    may have reached eBay but the outcome is unknown (request exception after
    send, or a 5xx) — eBay may have already committed a mutating call like
    AddFixedPriceItem. A truthy return short-circuits the retry loop so the
    call is never replayed against an already-committed item.

    Returns (response, guard_result): guard_result is non-None only when the
    guard short-circuited; response is the last HTTP response (or None).
    """
    retry_count = 0
    max_retries = TRADING_API_MAX_RETRIES
    response = None

    while retry_count <= max_retries:
        try:
            response = requests.post(
                TRADING_URL, headers=_trading_headers(call_name),
                data=xml_request.encode('utf-8'), timeout=TRADING_API_TIMEOUT
            )
        except Exception as e:
            logger.warning(f"{call_name}: Request exception: {e} (attempt {retry_count + 1}/{max_retries + 1})")
            if ambiguous_guard:
                guard_result = ambiguous_guard()
                if guard_result:
                    return response, guard_result
            retry_count += 1
            time.sleep(1)
            continue

        if response.status_code == 200:
            break
        elif response.status_code == 401:
            logger.warning(f"{call_name}: Token expired (401), refreshing... (attempt {retry_count + 1}/{max_retries + 1})")
            token = _refresh_trading_token()
            if not token:
                logger.error(f"{call_name}: No token available after refresh")
                break
            xml_request = _replace_auth_token(xml_request, token)
            retry_count += 1
            time.sleep(1)
        elif response.status_code == 429:
            backoff = 2 ** retry_count
            logger.warning(f"{call_name}: Rate limited by eBay (429), backing off {backoff}s... (attempt {retry_count + 1}/{max_retries + 1})")
            retry_count += 1
            time.sleep(backoff)
        elif response.status_code >= 500:
            logger.warning(f"{call_name}: Server error ({response.status_code}), retrying... (attempt {retry_count + 1}/{max_retries + 1})")
            if ambiguous_guard:
                guard_result = ambiguous_guard()
                if guard_result:
                    return response, guard_result
            retry_count += 1
            time.sleep(1)
        else:
            logger.warning(f"{call_name}: Unexpected HTTP {response.status_code}, not retrying")
            break

    return response, None


def _extract_trading_errors(root, ns) -> str:
    """Join all <Errors> blocks defensively (nodes may be missing)."""
    errors = []
    for err in root.findall('.//e:Errors', ns):
        code = err.find('e:ErrorCode', ns)
        msg = err.find('e:LongMessage', ns)
        if msg is None:
            msg = err.find('e:ShortMessage', ns)
        errors.append(f"{code.text if code is not None else '?'}: {msg.text if msg is not None else '?'}")
    return '; '.join(errors)


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
                  <IncludeWatchCount>true</IncludeWatchCount>
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
                  <OutputSelector>ItemArray.Item.WatchCount</OutputSelector>
                  <OutputSelector>ItemArray.Item.ListingDetails.StartTime</OutputSelector>
                  <OutputSelector>ItemArray.Item.PictureDetails.GalleryURL</OutputSelector>
                  <OutputSelector>ItemArray.Item.PictureDetails.PictureURL</OutputSelector>
                </GetSellerListRequest>"""
                
                response, _ = _post_trading_request('GetSellerList', xml_request)

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

    def add_fixed_price_item(self, item_data: dict, schedule_time: str = None, verify_only: bool = False):
        """
        Creates a Fixed Price Listing using the Trading API (AddFixedPriceItem).
        Supports native eBay scheduling via `schedule_time`.

        When verify_only=True, calls VerifyAddFixedPriceItem instead: eBay
        validates the exact same listing XML and returns the same fees/errors
        but creates nothing. Use it to dry-run a listing before publishing.

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
                    picture_details += f"<PictureURL>{xml_escape(str(url))}</PictureURL>"
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

            best_offer_details, best_offer_listing_details = build_best_offer_xml(item_data)

            call_name = 'VerifyAddFixedPriceItem' if verify_only else 'AddFixedPriceItem'
            xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
            <{call_name}Request xmlns="{xmlns}">
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
                        <CategoryID>{xml_escape(str(item_data.get('category_id', '1')))}</CategoryID>
                    </PrimaryCategory>
                    <StartPrice currencyID="USD">{xml_escape(str(item_data.get('price')))}</StartPrice>
                    <ConditionID>{xml_escape(str(item_data.get('condition_id', '3000')))}</ConditionID>
                    {tag('SKU', item_data.get('sku'))}
                    <Country>US</Country>
                    <Currency>USD</Currency>
                    <DispatchTimeMax>3</DispatchTimeMax>
                    <ListingDuration>GTC</ListingDuration>
                    <ListingType>FixedPriceItem</ListingType>
                    {best_offer_details}
                    {best_offer_listing_details}
                    {picture_details}
                    {seller_profiles}
                    {tag('PostalCode', item_data.get('postal_code'))}
                    {tag('Location', item_data.get('item_location', os.environ.get('EBAY_ITEM_LOCATION', 'Clovis, CA')))}
                    {build_shipping_package_xml(item_data.get('weight_lbs'))}
                    <ItemSpecifics>
                        {self._build_item_specifics_xml(item_data.get('item_specifics', {}))}
                    </ItemSpecifics>
                </Item>
            </{call_name}Request>
            """

            logger.info(f"Sending {call_name} for SKU {item_data.get('sku')}...")

            # Dedupe guard: a timeout/5xx after eBay committed the item must not
            # trigger a blind retry (that creates a second live listing). Before
            # any ambiguous retry, check whether the SKU already went live.
            ambiguous_guard = None
            if not verify_only:
                def ambiguous_guard():
                    existing = self._find_listing_by_sku(item_data.get('sku'))
                    if existing:
                        logger.warning(
                            f"AddFixedPriceItem: SKU {item_data.get('sku')} already live as item "
                            f"{existing.get('listingId')} after ambiguous failure — recovering, not retrying"
                        )
                        return {
                            'success': True,
                            'item_id': existing.get('listingId'),
                            'start_time': existing.get('startTime'),
                            'status': 'Active',
                            'recovered_duplicate': True,
                        }
                    return None

            response, guard_result = _post_trading_request(call_name, xml_request, ambiguous_guard=ambiguous_guard)
            if guard_result:
                return guard_result

            if not response or response.status_code != 200:
                # Final ambiguity check: retries exhausted, but the item may
                # still have been created by an attempt whose response we lost.
                if ambiguous_guard:
                    guard_result = ambiguous_guard()
                    if guard_result:
                        return guard_result
                error_detail = response.text[:200] if response else 'No Response'
                logger.error(f"Trading API HTTP Error: {response.status_code if response else 'N/A'} - {error_detail}")
                return {'success': False, 'error': f"HTTP {response.status_code if response else 'No Response'}"}

            # Parse Response. A 200 with an unparseable body or no Ack is
            # ambiguous too — eBay may have committed the item.
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError:
                if ambiguous_guard:
                    guard_result = ambiguous_guard()
                    if guard_result:
                        return guard_result
                logger.error(f"Trading API returned unparseable body: {response.text[:200]}")
                return {'success': False, 'error': 'Unparseable Trading API response'}
            ns = {'e': xmlns}

            ack_node = root.find('.//e:Ack', ns)
            if ack_node is None and ambiguous_guard:
                guard_result = ambiguous_guard()
                if guard_result:
                    return guard_result
            ack = ack_node.text if ack_node is not None else 'Failure'

            if ack in ['Success', 'Warning']:
                # Verify responses (and malformed ones) omit ItemID/StartTime —
                # read defensively so parsing never throws on a valid Ack.
                item_id_el = root.find('.//e:ItemID', ns)
                start_time_el = root.find('.//e:StartTime', ns)
                item_id = item_id_el.text if item_id_el is not None else None
                start_time = start_time_el.text if start_time_el is not None else None
                status = 'Verified' if verify_only else ('Scheduled' if schedule_time else 'Active')
                return {
                    'success': True,
                    'item_id': item_id,
                    'start_time': start_time,
                    'status': status
                }
            else:
                error_text = _extract_trading_errors(root, ns)
                if (item_data.get('best_offer_enabled')
                        and 'best offer' in (error_text or '').lower()):
                    # Some categories reject Best Offer outright and fail the
                    # whole Add. Retry once without the Best Offer blocks —
                    # the stripped item_data can't re-enter this branch.
                    logger.warning(
                        f"Category rejected Best Offer for SKU {item_data.get('sku')}; "
                        f"retrying without it: {error_text}")
                    retry_data = {k: v for k, v in item_data.items()
                                  if not k.startswith('best_offer')}
                    retry_result = self.add_fixed_price_item(
                        retry_data, schedule_time=schedule_time, verify_only=verify_only)
                    if retry_result.get('success'):
                        retry_result['best_offer_stripped'] = True
                    return retry_result
                logger.error(f"Trading API Failure: {error_text}")
                return {'success': False, 'error': error_text or 'Unknown Trading API failure'}

        except Exception as e:
            logger.exception("AddFixedPriceItem Exception")
            return {'success': False, 'error': str(e)}

    def _find_listing_by_sku(self, sku):
        """Duplicate-listing guard: return the live listing dict for this SKU,
        or None. Used after an ambiguous AddFixedPriceItem failure — a paginated
        GetSellerList sweep is slow, but this only runs on the failure path and
        SKUs (DC-{hex}) are unique per job."""
        if not sku:
            return None
        try:
            result, status = self.get_active_listings_light()
            if status != 200:
                return None
            for listing in result.get('listings', []):
                if listing.get('sku') == sku:
                    return listing
        except Exception as e:
            logger.warning(f"SKU duplicate-check failed for {sku}: {e}")
        return None

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
            
        # Watchers (dead-stock signal). Requires IncludeWatchCount + DetailLevel ReturnAll.
        watch_count = 0
        wc = get_text(item, 'e:WatchCount')
        if wc:
            try:
                watch_count = int(wc)
            except (ValueError, TypeError):
                watch_count = 0

        # Listing age — StartTime lives under ListingDetails.
        start_time = None
        listing_details = item.find('e:ListingDetails', ns)
        if listing_details is not None:
            start_time = get_text(listing_details, 'e:StartTime')

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
            'condition': 'Used',
            'watchCount': watch_count,
            'startTime': start_time
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
                <ItemID>{xml_escape(str(item_id))}</ItemID>
                <EndingReason>{xml_escape(str(reason))}</EndingReason>
            </EndFixedPriceItemRequest>"""

            response, _ = _post_trading_request('EndFixedPriceItem', xml_request)

            if not response or response.status_code != 200:
                return {'success': False, 'error': f"HTTP {response.status_code if response else 'No Response'}"}

            root = ET.fromstring(response.content)
            ns = {'e': xmlns}
            ack_node = root.find('.//e:Ack', ns)
            ack = ack_node.text if ack_node is not None else 'Failure'

            if ack in ['Success', 'Warning']:
                end_time_node = root.find('.//e:EndTime', ns)
                end_time = end_time_node.text if end_time_node is not None else None
                logger.info(f"Successfully ended listing {item_id}")
                return {'success': True, 'end_time': end_time}
            else:
                error_text = _extract_trading_errors(root, ns)
                logger.error(f"EndFixedPriceItem failed: {error_text}")
                return {'success': False, 'error': error_text or 'End failed'}

        except Exception as e:
            logger.exception("EndFixedPriceItem Exception")
            return {'success': False, 'error': str(e)}

    def revise_fixed_price_item(self, item_id: str, price=None, qty=None):
        """
        Revise a live fixed-price listing's price (and optionally quantity) using
        Trading API ReviseFixedPriceItem. This is the in-place price-drop path for
        Trading-API listings (which are not in the Inventory API).

        Args:
            item_id: The eBay listing ItemID to revise.
            price: New StartPrice (USD). Required for a price drop.
            qty: Optional new Quantity.

        Returns:
            dict: {success, price, error}
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

            if price is None and qty is None:
                return {'success': False, 'error': 'Nothing to revise (price or qty required)'}

            fields = f"<ItemID>{xml_escape(str(item_id))}</ItemID>"
            if price is not None:
                fields += f"<StartPrice>{float(price):.2f}</StartPrice>"
            if qty is not None:
                fields += f"<Quantity>{int(qty)}</Quantity>"

            xmlns = "urn:ebay:apis:eBLBaseComponents"
            xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
            <ReviseFixedPriceItemRequest xmlns="{xmlns}">
                <RequesterCredentials>
                    <eBayAuthToken>{token}</eBayAuthToken>
                </RequesterCredentials>
                <ErrorLanguage>en_US</ErrorLanguage>
                <Item>{fields}</Item>
            </ReviseFixedPriceItemRequest>"""

            response, _ = _post_trading_request('ReviseFixedPriceItem', xml_request)

            if not response or response.status_code != 200:
                return {'success': False, 'error': f"HTTP {response.status_code if response else 'No Response'}"}

            root = ET.fromstring(response.content)
            ns = {'e': xmlns}
            ack_node = root.find('.//e:Ack', ns)
            ack = ack_node.text if ack_node is not None else 'Failure'

            if ack in ['Success', 'Warning']:
                logger.info(f"Revised listing {item_id} (price={price}, qty={qty})")
                return {'success': True, 'price': float(price) if price is not None else None}

            errors = []
            for err in root.findall('.//e:Errors', ns):
                code = err.find('e:ErrorCode', ns)
                msg = err.find('e:LongMessage', ns)
                errors.append(f"{code.text if code is not None else '?'}: {msg.text if msg is not None else '?'}")
            logger.error(f"ReviseFixedPriceItem failed: {errors}")
            return {'success': False, 'error': '; '.join(errors) or 'Revise failed'}

        except Exception as e:
            logger.exception("ReviseFixedPriceItem Exception")
            return {'success': False, 'error': str(e)}
