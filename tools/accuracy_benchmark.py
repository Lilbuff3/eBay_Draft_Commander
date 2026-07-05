"""
Gate B — pricing-accuracy benchmark for the sourcing verdict.

Question it answers: does the engine's estimated sold value (median comp x
ACTIVE_TO_SOLD_FACTOR) actually predict what items REALLY sold for on eBay —
and does the discount beat using the raw comp median? That is the moat test.

Ground truth = your ACTUAL sold prices. Two sources:
  1) live Orders API (last ~90 days)  -> default, no args
  2) --csv PATH  -> an eBay Seller Hub sold-history export (title/ISBN + price),
     for a much larger sample without waiting for new sales.

For each sold item it re-runs the SAME code path the live product uses
(search_sold_listings -> calculate_suggested_price) and compares:
  - est_sold  = median_comp * ACTIVE_TO_SOLD_FACTOR   (what the verdict uses)
  - raw_median = median_comp                          (no-discount baseline)
  - would_list = engine suggested_price               (list-price prediction)
against the real sale price.

CAVEATS (printed in the report): comps are fetched NOW, so a sale from months
ago is scored against today's market (same limitation the live tool has). Free-
shipping listings mean sale total ~= list price. Small samples are noisy — trust
the trend only past ~25-30 items.

Usage:
  python tools/accuracy_benchmark.py                     # live orders
  python tools/accuracy_benchmark.py --csv sold.csv      # exported history
  python tools/accuracy_benchmark.py --books-only        # only rows with an ISBN
  python tools/accuracy_benchmark.py --limit 200
"""
import argparse
import csv
import os
import re
import statistics
import sys
from pathlib import Path

from dotenv import load_dotenv

# --- bootstrap (mirrors tools/debug_mcp.py) ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=PROJECT_ROOT / '.env')
sys.path.append(str(PROJECT_ROOT))

import requests  # noqa: E402
from backend.app.services.pricing_engine import PricingEngine  # noqa: E402
from backend.app.core.constants import ACTIVE_TO_SOLD_FACTOR  # noqa: E402

RESULTS_JSONL = PROJECT_ROOT / 'data' / 'listing_results.jsonl'
API_BASE = os.getenv('BENCH_API_BASE', 'http://127.0.0.1:5000')
SHIP_COST = float(os.getenv('SOURCING_SHIP_COST', '5.00'))
ISBN_RE = re.compile(r'(?<!\d)(97[89]\d{10}|\d{9}[\dX])(?!\d)')


def load_listing_index():
    """listing_id -> {isbn, condition, title} from results_logger, for joins."""
    index = {}
    if not RESULTS_JSONL.exists():
        return index
    import json
    for line in RESULTS_JSONL.read_text(encoding='utf-8').splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        lid = str(rec.get('listing_id') or '')
        if lid:
            index[lid] = {
                'isbn': rec.get('isbn'),
                'condition': rec.get('condition') or 'USED_GOOD',
                'title': rec.get('title', ''),
            }
    return index


def ground_truth_from_orders(index):
    """Pull real sold prices from the live Orders API (loopback-trusted)."""
    try:
        resp = requests.get(f'{API_BASE}/api/orders', timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f'[!] Could not reach {API_BASE}/api/orders: {e}')
        print('    Start the backend, or use --csv with an exported sold history.')
        return []
    orders = data if isinstance(data, list) else (data.get('orders') or data.get('data') or [])
    rows = []
    for o in orders:
        try:
            actual = float(o.get('total') or 0)
        except (TypeError, ValueError):
            continue
        if actual <= 0:
            continue
        title = o.get('itemTitle') or ''
        joined = index.get(str(o.get('legacyItemId') or ''), {})
        isbn = joined.get('isbn') or _isbn_from_title(title)
        rows.append({
            'actual': actual,
            'title': title,
            'isbn': isbn,
            'condition': joined.get('condition', 'USED_GOOD'),
        })
    return rows


def ground_truth_from_csv(path):
    """Parse an eBay Seller Hub sold-history export (flexible columns)."""
    rows = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}

        def pick(*cands):
            for cand in cands:
                for low, orig in cols.items():
                    if cand in low:
                        return orig
            return None

        price_col = pick('sold for', 'sale price', 'total price', 'total', 'price')
        isbn_col = pick('isbn', 'gtin', 'custom label', 'sku', 'product id')
        title_col = pick('item title', 'title', 'item')
        if not price_col:
            print(f'[!] No price column found in {path}. Columns: {list(cols.values())}')
            return []
        for r in reader:
            actual = _money(r.get(price_col))
            if actual <= 0:
                continue
            title = (r.get(title_col) or '').strip() if title_col else ''
            raw_isbn = (r.get(isbn_col) or '').strip() if isbn_col else ''
            isbn = _norm_isbn(raw_isbn) or _isbn_from_title(title)
            rows.append({'actual': actual, 'title': title, 'isbn': isbn, 'condition': 'USED_GOOD'})
    return rows


def _money(s):
    if not s:
        return 0.0
    try:
        return float(re.sub(r'[^0-9.]', '', str(s)) or 0)
    except ValueError:
        return 0.0


def _norm_isbn(s):
    if not s:
        return None
    m = ISBN_RE.search(re.sub(r'[\s-]', '', str(s)).upper())
    return m.group(1) if m else None


def _isbn_from_title(title):
    return _norm_isbn(title or '')


def predict(engine, row):
    """Re-run the live verdict code path (identifier-first + filter_comps)."""
    query = row['isbn'] or row['title']
    if not query:
        return None
    comps = engine.search_sold_listings(query, limit=15, condition=row['condition'])
    if not comps:
        return None
    # Mirror the live engine: drop off-title / price-outlier comps before pricing.
    if row['title']:
        comps = engine.filter_comps(comps, reference_title=row['title'])
    pd = engine.calculate_suggested_price(
        comps, our_condition=row['condition'], shipping_cost=SHIP_COST, availability=None)
    raw_median = pd.get('median_price')
    if not raw_median:
        return None
    return {
        'raw_median': round(raw_median, 2),
        'est_sold': round(raw_median * ACTIVE_TO_SOLD_FACTOR, 2),
        'would_list': pd.get('suggested_price'),
        'comp_count': pd.get('comp_count', 0),
        # exact-ID (ISBN/UPC) = the real product; keyword = the weak fallback.
        'match_type': 'exact-ID' if row['isbn'] else 'keyword',
    }


def _stats(pairs):
    """pairs = [(predicted, actual)] -> MAE, median abs %err, % within 25%."""
    if not pairs:
        return None
    abs_err = [abs(p - a) for p, a in pairs]
    pct_err = [abs(p - a) / a for p, a in pairs if a > 0]
    within = [1 for p, a in pairs if a > 0 and abs(p - a) / a <= 0.25]
    return {
        'n': len(pairs),
        'mae': round(statistics.mean(abs_err), 2),
        'median_pct': round(statistics.median(pct_err) * 100, 1) if pct_err else None,
        'within_25pct': round(100 * len(within) / len(pairs), 0),
        'bias': round(statistics.mean([p - a for p, a in pairs]), 2),  # +over / -under
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', help='eBay sold-history export CSV (bigger ground-truth sample)')
    ap.add_argument('--books-only', action='store_true', help='only rows with an ISBN')
    ap.add_argument('--limit', type=int, default=500)
    args = ap.parse_args()

    index = load_listing_index()
    rows = ground_truth_from_csv(args.csv) if args.csv else ground_truth_from_orders(index)
    if args.books_only:
        rows = [r for r in rows if r['isbn']]
    rows = rows[:args.limit]

    if not rows:
        print('No ground-truth sold items found. Sell some scanned books first (Stage 0a),')
        print('or pass --csv with a Seller Hub sold-history export.')
        return

    print(f'Ground truth: {len(rows)} sold item(s) | ACTIVE_TO_SOLD_FACTOR={ACTIVE_TO_SOLD_FACTOR} | ship=${SHIP_COST}')
    print(f'{"actual":>8} {"est_sold":>9} {"raw_med":>8} {"list":>7} {"n":>3} {"match":>8}  item')
    print('-' * 82)

    engine = PricingEngine()
    scored = []   # (match_type, est_sold, raw_median, would_list|None, actual)
    no_comps = 0
    for r in rows:
        pred = predict(engine, r)
        if not pred:
            no_comps += 1
            print(f'{r["actual"]:>8.2f} {"-- no comps --":>27}          {(r["isbn"] or r["title"])[:30]}')
            continue
        a = r['actual']
        scored.append((pred['match_type'], pred['est_sold'], pred['raw_median'], pred['would_list'], a))
        print(f'{a:>8.2f} {pred["est_sold"]:>9.2f} {pred["raw_median"]:>8.2f} '
              f'{(pred["would_list"] or 0):>7.2f} {pred["comp_count"]:>3} {pred["match_type"]:>8}  '
              f'{(r["isbn"] or r["title"])[:30]}')

    print('-' * 82)
    if not scored:
        print(f'No priceable items ({no_comps} had no comps). Nothing to score.')
        return

    def report(rowset, header):
        est_s = _stats([(e, a) for _, e, _, _, a in rowset])
        raw_s = _stats([(rm, a) for _, _, rm, _, a in rowset])
        list_s = _stats([(lp, a) for _, _, _, lp, a in rowset if lp])
        if not est_s:
            return
        print(f'\n{header} (n={est_s["n"]}) — lower MAE/medErr = better:')
        for name, s in (('est_sold (DISCOUNTED)', est_s), ('raw_median (baseline)', raw_s),
                        ('would_list (list px)', list_s)):
            if s:
                print(f'  {name:<22} MAE=${s["mae"]:<7} medErr={s["median_pct"]}%  '
                      f'within25%={s["within_25pct"]:.0f}%  bias=${s["bias"]:+.2f}')
        if est_s and raw_s:
            delta = round(raw_s['mae'] - est_s['mae'], 2)
            verdict = f'BEATS raw median by ${delta}' if est_s['mae'] < raw_s['mae'] else f'does NOT beat raw median (worse by ${-delta})'
            print(f'  -> discount {verdict} MAE')

    report(scored, 'ALL MATCHES')
    exact = [x for x in scored if x[0] == 'exact-ID']
    keyword = [x for x in scored if x[0] == 'keyword']
    if exact and keyword:
        report(exact, 'EXACT-ID (ISBN/UPC) — judge the thesis HERE')
        report(keyword, 'KEYWORD-ONLY — the weak fallback')
    if no_comps:
        print(f'\n  ({no_comps} item(s) had no comps at all)')

    print('\nMOAT READ:')
    print(f'  Exact-ID matches (the books-first product): {len(exact)} of {len(scored)} scored.')
    if len(exact) < 25:
        print(f'  ! Only {len(exact)} exact-ID items — too few to judge. Export book sales (--csv) for 25-30+.')
    print('  Judge the thesis on the EXACT-ID rows only; keyword rows are the low-confidence fallback the product should flag, not trust.')
    print('\nCaveat: comps fetched now vs past sales; free-shipping total ~= list price.')


if __name__ == '__main__':
    main()
