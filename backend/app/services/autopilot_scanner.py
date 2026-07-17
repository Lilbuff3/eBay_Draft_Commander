"""Daily autopilot: offers to watchers + stale-item markdown ladder (+ relist).

Converts almost-sales and dead stock into cash, unattended:
- listings with watchers get a discounted offer (Negotiation API)
- listings live past MARKDOWN_AFTER_DAYS step down the price ladder
  (price-discovery listings use the aggressive DISCOVERY_* knobs)
- (relist sweep for unsold items plugs in here too)

SAFETY: OFFERS_MARKDOWNS_DRY_RUN defaults to true — cycles compute and RECORD
actions (listing_actions rows, WhatsApp digest) without touching eBay until
the owner flips live in Settings → Autopilot. Idempotency queries only count
live rows, so the dry-run observation window never suppresses the first real
actions.

run_cycle(now) is synchronous and unit-testable; run_forever() is the daemon
loop wired up by queue_manager._init_background_services.
"""
import json
import time
from datetime import datetime, timedelta
from typing import Optional

from backend.app.core.database import ListingActionModel
from backend.app.core.logger import get_logger
from backend.app.services.markdown_engine import compute_markdown

logger = get_logger('autopilot_scanner')


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class AutopilotScanner:
    def __init__(self, queue_manager, trading=None, negotiation=None):
        self.qm = queue_manager
        self._trading = trading
        self._negotiation = negotiation

    # ------------------------------------------------------------ clients

    @property
    def trading(self):
        if self._trading is None:
            from backend.app.services.ebay.trading import TradingService
            self._trading = TradingService()
        return self._trading

    @property
    def negotiation(self):
        if self._negotiation is None:
            from backend.app.services.ebay.negotiation import NegotiationAPI
            self._negotiation = NegotiationAPI()
        return self._negotiation

    # ------------------------------------------------------- action store

    def record_action(self, listing_id: str, action_type: str, dry_run: bool,
                      details: dict, executed_at: float) -> None:
        session = self.qm.SessionFactory()
        try:
            session.add(ListingActionModel(
                listing_id=str(listing_id), action_type=action_type,
                executed_at=executed_at, dry_run=bool(dry_run),
                details_json=json.dumps(details or {})))
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"listing_actions insert failed: {e}")
        finally:
            session.close()

    def _last_live_action(self, listing_id: str, action_type: str):
        """Most recent NON-dry-run action of this type for a listing."""
        session = self.qm.SessionFactory()
        try:
            return (session.query(ListingActionModel)
                    .filter_by(listing_id=str(listing_id),
                               action_type=action_type, dry_run=False)
                    .order_by(ListingActionModel.executed_at.desc())
                    .first())
        finally:
            session.close()

    def count_live_actions(self, listing_id: str, action_type: str) -> int:
        session = self.qm.SessionFactory()
        try:
            return (session.query(ListingActionModel)
                    .filter_by(listing_id=str(listing_id),
                               action_type=action_type, dry_run=False)
                    .count())
        finally:
            session.close()

    # ------------------------------------------------------------- cycle

    def run_cycle(self, now: Optional[float] = None) -> dict:
        now = now if now is not None else time.time()
        from backend.app.core.settings_manager import get_settings_manager
        s = get_settings_manager()

        def flag(key, default):
            return str(s.get(key, default)).lower() == 'true'

        def num(key, default):
            return _to_float(s.get(key, default), _to_float(default))

        dry_run = flag('OFFERS_MARKDOWNS_DRY_RUN', 'true')
        offers_enabled = flag('OFFERS_ENABLED', 'true')
        markdown_enabled = flag('MARKDOWN_ENABLED', 'true')
        offer_discount = num('OFFER_DISCOUNT_PCT', '10')
        offer_min_watchers = int(num('OFFER_MIN_WATCHERS', '1'))
        std_knobs = dict(after_days=num('MARKDOWN_AFTER_DAYS', '14'),
                         step_pct=num('MARKDOWN_STEP_PCT', '5'),
                         floor_pct=num('MARKDOWN_FLOOR_PCT', '70'))
        disc_knobs = dict(after_days=num('DISCOVERY_MARKDOWN_AFTER_DAYS', '7'),
                          step_pct=num('DISCOVERY_MARKDOWN_STEP_PCT', '10'),
                          floor_pct=num('DISCOVERY_MARKDOWN_FLOOR_PCT', '40'))

        result = {'offers': [], 'markdowns': [], 'relists': [],
                  'dry_run': dry_run, 'errors': []}

        try:
            listings_result, status = self.trading.get_active_listings_light()
        except Exception as e:
            logger.error(f"Autopilot: active listings fetch failed: {e}")
            return result
        if status != 200:
            logger.warning(f"Autopilot: active listings fetch returned {status}")
            return result
        listings = listings_result.get('listings', [])

        jobs_by_listing = {}
        try:
            for job in self.qm.get_all_jobs():
                lid = getattr(job, 'listing_id', None)
                if lid:
                    jobs_by_listing[str(lid)] = job
        except Exception as e:
            logger.warning(f"Autopilot: job join failed (using listing prices): {e}")

        for listing in listings:
            listing_id = str(listing.get('listingId') or '')
            if not listing_id:
                continue
            current_price = _to_float(listing.get('price'))
            watch_count = int(_to_float(listing.get('watchCount'), 0))
            job = jobs_by_listing.get(listing_id)
            original_price = _to_float(getattr(job, 'price', None), current_price) \
                if job is not None else current_price
            if original_price <= 0:
                original_price = current_price
            is_discovery = bool(
                (getattr(job, 'job_metadata', None) or {}).get('price_discovery')
            ) if job is not None else False
            knobs = disc_knobs if is_discovery else std_knobs
            days_live = self._days_live(listing.get('startTime'), now)

            # --- offers to watchers: one offer per price point ---
            if offers_enabled and watch_count >= offer_min_watchers and current_price > 0:
                if self._offer_due(listing_id, current_price):
                    entry = {'listing_id': listing_id, 'price': current_price,
                             'discount_pct': offer_discount,
                             'watch_count': watch_count}
                    ok = True
                    if not dry_run:
                        sent = self.negotiation.send_offer(listing_id, offer_discount)
                        ok = bool(sent.get('success'))
                        if not ok:
                            result['errors'].append(
                                {'listing_id': listing_id, 'action': 'offer',
                                 'error': sent.get('error')})
                    if ok:
                        self.record_action(listing_id, 'offer', dry_run, entry, now)
                        result['offers'].append(entry)

            # --- markdown ladder ---
            if markdown_enabled and days_live is not None and current_price > 0:
                if self._markdown_due(listing_id, now, knobs['after_days']):
                    new_price = compute_markdown(
                        original_price, current_price, days_live, **knobs)
                    if new_price is not None:
                        entry = {'listing_id': listing_id,
                                 'from': current_price, 'to': new_price,
                                 'discovery': is_discovery}
                        ok = True
                        if not dry_run:
                            revised = self.trading.revise_fixed_price_item(
                                listing_id, price=new_price)
                            ok = bool(revised.get('success'))
                            if not ok:
                                result['errors'].append(
                                    {'listing_id': listing_id, 'action': 'markdown',
                                     'error': revised.get('error')})
                        if ok:
                            self.record_action(listing_id, 'markdown', dry_run, entry, now)
                            result['markdowns'].append(entry)

        self._run_relist_sweep(result, now, std_knobs, dry_run, s)
        self._send_digest(result)
        return result

    def _run_relist_sweep(self, result, now, knobs, dry_run, settings):
        """Unsold relist sweep — implemented with the B3 task."""
        return

    def _days_live(self, start_time, now: float) -> Optional[float]:
        if not start_time:
            return None
        try:
            dt = datetime.fromisoformat(str(start_time).replace('Z', '+00:00'))
            return max(0.0, (now - dt.timestamp()) / 86400)
        except (ValueError, OSError):
            return None

    def _offer_due(self, listing_id: str, current_price: float) -> bool:
        """Offer eligible when never offered live, or the price has dropped
        since the last live offer (new price point = new offer)."""
        last = self._last_live_action(listing_id, 'offer')
        if last is None:
            return True
        last_price = _to_float((last.details or {}).get('price'))
        return current_price < last_price - 0.009

    def _markdown_due(self, listing_id: str, now: float, spacing_days: float) -> bool:
        """One live step per spacing window."""
        last = self._last_live_action(listing_id, 'markdown')
        if last is None:
            return True
        return (now - last.executed_at) >= spacing_days * 86400

    def _send_digest(self, result: dict) -> None:
        """Best-effort owner text summarizing the cycle. Only when something
        happened (or would have)."""
        total = len(result['offers']) + len(result['markdowns']) + len(result['relists'])
        if not total:
            return
        try:
            from backend.app.services.whatsapp_notify import (
                get_notify_destination, notify_whatsapp,
                build_autopilot_summary_message,
            )
            dest = get_notify_destination(None)  # owner chat
            if not dest:
                return
            notify_whatsapp(dest, build_autopilot_summary_message(
                len(result['offers']), len(result['markdowns']),
                len(result['relists']), dry_run=result['dry_run']))
        except Exception as e:
            logger.warning(f"Autopilot digest failed (non-fatal): {e}")

    # ------------------------------------------------------------- daemon

    def _seconds_until_next_run(self) -> float:
        """Seconds until the next AUTOPILOT_RUN_HOUR local time."""
        try:
            from backend.app.core.settings_manager import get_settings_manager
            hour = int(_to_float(get_settings_manager().get('AUTOPILOT_RUN_HOUR', '9'), 9))
        except Exception:
            hour = 9
        hour = min(23, max(0, hour))
        now = datetime.now()
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return max(1.0, (target - now).total_seconds())

    def run_forever(self):
        logger.info("Autopilot scanner started (daily cycle)")
        while True:
            try:
                time.sleep(self._seconds_until_next_run())
                result = self.run_cycle()
                logger.info(
                    f"Autopilot cycle done (dry_run={result['dry_run']}): "
                    f"{len(result['offers'])} offers, "
                    f"{len(result['markdowns'])} markdowns, "
                    f"{len(result['relists'])} relists")
            except Exception as e:
                logger.error(f"Autopilot cycle failed: {e}")
                time.sleep(3600)
