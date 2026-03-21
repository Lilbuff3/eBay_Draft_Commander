"""
Listing Results Logger

Appends a structured JSON record to data/listing_results.jsonl every time
a listing is created (published, scheduled, or routed to review).

This builds a dataset over time that can be used to:
  - Compare AI outputs (title, price, category) across runs
  - Detect regressions after prompt or code changes
  - Track pricing accuracy vs actual sales
  - Share listing patterns with other sellers
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.core.logger import get_logger
from backend.app.core.paths import get_data_dir

logger = get_logger('results_logger')

RESULTS_FILE = 'listing_results.jsonl'


def log_listing_result(job_obj, result: dict, analysis: dict,
                       pricing_result: dict, cat_result: dict,
                       condition: str, confidence_score: float):
    """
    Append a listing result record to the JSONL log.

    Called from ProcessorService.create_listing() on both success paths
    (published/scheduled and pending_review).
    """
    try:
        ai_data = job_obj.ai_data or {}
        identification = ai_data.get('identification', {})

        record = {
            # When
            'timestamp': datetime.now(timezone.utc).isoformat(),

            # What happened
            'status': result.get('status', 'unknown'),
            'listing_id': result.get('listing_id'),
            'job_id': job_obj.id,

            # AI outputs (the stuff we want to track over time)
            'title': result.get('title', ''),
            'price': result.get('price', '0'),
            'condition': condition,
            'confidence_score': confidence_score,
            'category_id': cat_result.get('id'),
            'category_name': cat_result.get('name', ''),

            # Identification
            'brand': identification.get('brand'),
            'model': identification.get('model'),
            'mpn': identification.get('mpn'),
            'isbn': identification.get('isbn'),
            'product_type': identification.get('product_type'),

            # Item specifics (flattened)
            'item_specifics': _flatten_specifics(analysis.get('item_specifics', {})),
            'item_specifics_count': len(analysis.get('item_specifics', {})),

            # Images
            'image_count': len(ai_data.get('image_urls', [])),
            'image_urls': ai_data.get('image_urls', []),

            # Pricing details
            'pricing_method': pricing_result.get('method', 'unknown'),
            'shipping_buffer': analysis.get('shipping_cost', 0),

            # Source
            'folder_name': job_obj.folder_name,
            'folder_path': job_obj.folder_path,

            # Performance
            'timing': result.get('timing', {}),

            # User overrides (tracks when humans correct the AI)
            'had_user_price': bool(job_obj.user_price),
            'had_user_condition': bool(job_obj.user_condition),
            'user_price': job_obj.user_price,
            'user_condition': job_obj.user_condition,
        }

        results_path = get_data_dir() / RESULTS_FILE
        with open(results_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

        logger.info(f"Logged result: {record['status']} - {record['title'][:50]}")

    except Exception as e:
        # Never let logging break the pipeline
        logger.warning(f"Failed to log listing result: {e}")


def _flatten_specifics(specifics: dict) -> dict:
    """Flatten item specifics values to strings for consistent storage."""
    flat = {}
    for key, value in specifics.items():
        if isinstance(value, list):
            flat[key] = value[0] if len(value) == 1 else value
        else:
            flat[key] = value
    return flat


def get_results(limit: int = 0, fixture: str = None) -> list:
    """
    Read back logged results for analysis.

    Args:
        limit: Max records to return (0 = all, newest first)
        fixture: Filter by folder_name containing this string
    """
    results_path = get_data_dir() / RESULTS_FILE
    if not results_path.exists():
        return []

    records = []
    with open(results_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if fixture and fixture not in record.get('folder_name', ''):
                    continue
                records.append(record)
            except json.JSONDecodeError:
                continue

    # Newest first
    records.reverse()

    if limit > 0:
        records = records[:limit]

    return records


def compare_last_runs(fixture: str = None) -> dict:
    """
    Compare the two most recent runs for each fixture to spot changes.

    Returns dict of fixture_name -> {field: (old, new)} for changed fields.
    """
    records = get_results()
    if not records:
        return {}

    # Group by folder_name
    by_fixture = {}
    for r in records:
        name = r.get('folder_name', 'unknown')
        if fixture and fixture not in name:
            continue
        by_fixture.setdefault(name, []).append(r)

    changes = {}
    compare_fields = ['title', 'price', 'condition', 'category_id',
                      'category_name', 'confidence_score', 'brand',
                      'model', 'item_specifics_count', 'pricing_method']

    for name, runs in by_fixture.items():
        if len(runs) < 2:
            continue
        latest, previous = runs[0], runs[1]
        diffs = {}
        for field in compare_fields:
            old_val = previous.get(field)
            new_val = latest.get(field)
            if old_val != new_val:
                diffs[field] = {'was': old_val, 'now': new_val}
        if diffs:
            changes[name] = {
                'changes': diffs,
                'latest_timestamp': latest['timestamp'],
                'previous_timestamp': previous['timestamp'],
            }

    return changes
