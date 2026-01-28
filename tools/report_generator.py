"""
Report Generator for eBay Draft Commander
Generates summary reports after batch processing.
"""
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Optional


def generate_batch_report(jobs: list, output_dir: Path = None) -> Path:
    """
    Generate a CSV report of batch processing results.
    
    Args:
        jobs: List of QueueJob objects (or dicts with same fields)
        output_dir: Directory to save report (default: data/reports)
    
    Returns:
        Path to generated report file
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "data" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = output_dir / f"batch_report_{timestamp}.csv"
    
    # Calculate summary stats
    total = len(jobs)
    completed = sum(1 for j in jobs if _get_status(j) == 'completed')
    failed = sum(1 for j in jobs if _get_status(j) == 'failed')
    skipped = sum(1 for j in jobs if _get_status(j) == 'skipped')
    pending = total - completed - failed - skipped
    
    total_time = 0
    for j in jobs:
        timing = _get_timing(j)
        if timing and 'total' in timing:
            total_time += timing['total']
    
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header section with summary
        writer.writerow(['eBay Draft Commander - Batch Report'])
        writer.writerow([f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        writer.writerow([])
        writer.writerow(['Summary'])
        writer.writerow(['Total Items', total])
        writer.writerow(['Completed', completed])
        writer.writerow(['Failed', failed])
        writer.writerow(['Skipped', skipped])
        writer.writerow(['Pending', pending])
        writer.writerow([f'Total Time', f'{total_time:.1f}s'])
        if completed > 0:
            writer.writerow(['Avg Time per Item', f'{total_time/completed:.1f}s'])
        writer.writerow([])
        
        # Detailed results
        writer.writerow(['Details'])
        writer.writerow([
            'Folder', 'Status', 'Listing ID', 'Offer ID', 
            'Error Type', 'Error Message', 'Time (s)', 'eBay URL'
        ])
        
        for job in jobs:
            folder_name = _get_field(job, 'folder_name')
            status = _get_status(job)
            listing_id = _get_field(job, 'listing_id') or ''
            offer_id = _get_field(job, 'offer_id') or ''
            error_type = _get_field(job, 'error_type') or ''
            error_message = _get_field(job, 'error_message') or ''
            
            timing = _get_timing(job)
            time_str = f"{timing.get('total', 0):.1f}" if timing else ''
            
            ebay_url = f'https://www.ebay.com/itm/{listing_id}' if listing_id else ''
            
            writer.writerow([
                folder_name, status, listing_id, offer_id,
                error_type, error_message, time_str, ebay_url
            ])
    
    return report_path


def generate_summary_text(jobs: list) -> str:
    """
    Generate a text summary of batch results.
    
    Args:
        jobs: List of QueueJob objects or dicts
        
    Returns:
        Formatted text summary
    """
    total = len(jobs)
    completed = sum(1 for j in jobs if _get_status(j) == 'completed')
    failed = sum(1 for j in jobs if _get_status(j) == 'failed')
    
    lines = [
        "=" * 50,
        "📊 BATCH PROCESSING SUMMARY",
        "=" * 50,
        f"✅ Completed:  {completed}/{total}",
        f"❌ Failed:     {failed}/{total}",
        ""
    ]
    
    if completed > 0:
        lines.append("🎉 Successfully Listed:")
        for job in jobs:
            if _get_status(job) == 'completed':
                listing_id = _get_field(job, 'listing_id')
                folder = _get_field(job, 'folder_name')
                if listing_id:
                    lines.append(f"   • {folder} → ebay.com/itm/{listing_id}")
                else:
                    offer_id = _get_field(job, 'offer_id')
                    lines.append(f"   • {folder} → Draft: {offer_id}")
        lines.append("")
    
    if failed > 0:
        lines.append("⚠️ Failed Items:")
        for job in jobs:
            if _get_status(job) == 'failed':
                folder = _get_field(job, 'folder_name')
                error = _get_field(job, 'error_type') or 'Unknown'
                lines.append(f"   • {folder}: {error}")
        lines.append("")
    
    lines.append("=" * 50)
    
    return "\n".join(lines)


def _get_field(job, field: str):
    """Helper to get field from job object or dict"""
    if hasattr(job, field):
        return getattr(job, field)
    elif isinstance(job, dict):
        return job.get(field)
    return None


def _get_status(job) -> str:
    """Helper to get status as string"""
    status = _get_field(job, 'status')
    if hasattr(status, 'value'):
        return status.value
    return str(status) if status else 'unknown'


def _get_timing(job) -> Optional[dict]:
    """Helper to get timing dict"""
    timing = _get_field(job, 'timing')
    if isinstance(timing, dict):
        return timing
    return None


# Test
if __name__ == "__main__":
    # Test with mock jobs
    mock_jobs = [
        {
            'folder_name': 'cletop_cleaner',
            'status': 'completed',
            'listing_id': '123456789012',
            'offer_id': 'OFF123',
            'error_type': None,
            'error_message': None,
            'timing': {'total': 15.3}
        },
        {
            'folder_name': 'svbony_scope',
            'status': 'completed',
            'listing_id': '234567890123',
            'offer_id': 'OFF456',
            'error_type': None,
            'error_message': None,
            'timing': {'total': 12.8}
        },
        {
            'folder_name': 'broken_item',
            'status': 'failed',
            'listing_id': None,
            'offer_id': None,
            'error_type': 'NoImages',
            'error_message': 'No images found in folder',
            'timing': {'total': 0.1}
        }
    ]
    
    print(generate_summary_text(mock_jobs))
    
    report_path = generate_batch_report(mock_jobs)
    print(f"\n📁 Report saved: {report_path}")
