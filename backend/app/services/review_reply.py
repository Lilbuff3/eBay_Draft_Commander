"""WhatsApp reply-to-review.

When the pipeline holds a job in pending_review it texts the owner (or the
originating chat). This module lets that person resolve the review by TEXTING
BACK instead of opening the web app:

    "ok"      -> approve at the pre-filled price
    "25"      -> set $25 as the price, then approve
    "skip"    -> skip the job

Flow: processor writes a marker file <captures>/.review_pending/<safe_chat>
when it sends a review text; the Hermes plugin only intercepts ok/number/skip
while a marker exists (so normal chat is never hijacked) and forwards the text
to POST /api/review/reply, which lands here.

Resolution: FIFO-oldest pending_review job whose origin chat matches. The
owner chat (WHATSAPP_NOTIFY_CHAT_ID) additionally covers origin-less web jobs.
"""
import re
from pathlib import Path
from typing import Any, Optional, Tuple, Union

from backend.app.core.logger import get_logger
from backend.app.services.queue_job import JobStatus

logger = get_logger('review_reply')

_OK_WORDS = frozenset({'ok', 'okay', 'yes', 'approve'})
_PRICE_RE = re.compile(r'^\$?(\d+(?:\.\d{1,2})?)$')


def parse_review_reply(text: Any) -> Union[str, Tuple[str, float], None]:
    """'ok' | 'skip' | ('price', float) | None (not a review reply)."""
    if not text:
        return None
    t = str(text).strip().lower()
    if t in _OK_WORDS:
        return 'ok'
    if t == 'skip':
        return 'skip'
    m = _PRICE_RE.match(t)
    if m:
        return ('price', float(m.group(1)))
    return None


# ---------------------------------------------------------------- markers

def _safe_chat(chat_id: Any) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(chat_id))
    return re.sub(r"\.{2,}", "_", safe)


def review_marker_path(captures_dir: str, chat_id: Any) -> Path:
    return Path(captures_dir) / '.review_pending' / _safe_chat(chat_id)


def append_review_marker(captures_dir: Optional[str], chat_id: Any, job_id: str) -> None:
    """Record that `chat_id` has a review text outstanding for `job_id`.
    Best-effort: marker failures must never affect the pipeline."""
    try:
        if not captures_dir or not chat_id or not job_id:
            return
        path = review_marker_path(captures_dir, chat_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f"{job_id}\n")
    except OSError as e:
        logger.warning(f"Review marker append failed (non-fatal): {e}")


def pop_review_marker(captures_dir: Optional[str], chat_id: Any, job_id: str) -> None:
    """Remove `job_id` from the chat's marker; delete the file when empty."""
    try:
        if not captures_dir:
            return
        path = review_marker_path(captures_dir, chat_id)
        if not path.exists():
            return
        remaining = [line for line in path.read_text(encoding='utf-8').split()
                     if line and line != str(job_id)]
        if remaining:
            path.write_text("\n".join(remaining) + "\n", encoding='utf-8')
        else:
            path.unlink()
    except OSError as e:
        logger.warning(f"Review marker pop failed (non-fatal): {e}")


# ------------------------------------------------------------- resolution

def _status_value(job) -> Optional[str]:
    status = getattr(job, 'status', None)
    return getattr(status, 'value', status)


def _origin_chat(job) -> Optional[str]:
    meta = getattr(job, 'job_metadata', None) or {}
    origin = meta.get('origin') or {}
    return origin.get('chat_id')


def resolve_pending_job(queue_manager, chat_id: str, owner_chat_id: str = ''):
    """FIFO-oldest pending_review job for this chat. The owner chat also
    covers origin-less (web-UI) jobs, since their review texts go there."""
    pending = [j for j in queue_manager.get_all_jobs()
               if _status_value(j) == JobStatus.PENDING_REVIEW.value]
    pending.sort(key=lambda j: str(getattr(j, 'created_at', '') or ''))
    mine = [j for j in pending if _origin_chat(j) == chat_id]
    if mine:
        return mine[0]
    if owner_chat_id and str(chat_id) == str(owner_chat_id):
        originless = [j for j in pending if not _origin_chat(j)]
        if originless:
            return originless[0]
    return None


# ----------------------------------------------------------------- actions

def approve_job(queue_manager, job_id: str, user_price: Optional[float] = None) -> bool:
    """Approve a held job: user_approved metadata (so guardrails don't bounce
    it back), optional price override, back to PENDING. Same semantics as the
    batch-approve endpoint."""
    job = queue_manager.get_job_by_id(job_id)
    if not job:
        return False
    metadata = getattr(job, 'job_metadata', None) or {}
    metadata['user_approved'] = True
    updates = {'status': JobStatus.PENDING, 'job_metadata': metadata}
    if user_price is not None:
        updates['user_price'] = user_price
    return bool(queue_manager.update_job(job_id, updates))


def apply_review_reply(queue_manager, chat_id: str, text: str,
                       owner_chat_id: Optional[str] = None,
                       captures_dir: Optional[str] = None) -> dict:
    """Resolve a WhatsApp review reply. Returns {success, message, job_id}."""
    cmd = parse_review_reply(text)
    if cmd is None:
        return {'success': False, 'job_id': None,
                'message': 'Reply "ok" to approve, a number to set the price, or "skip".'}

    if owner_chat_id is None:
        try:
            from backend.app.core.settings_manager import get_settings_manager
            owner_chat_id = (get_settings_manager().get(
                'WHATSAPP_NOTIFY_CHAT_ID', '') or '').strip()
        except Exception as e:
            logger.warning(f"Could not read WHATSAPP_NOTIFY_CHAT_ID: {e}")
            owner_chat_id = ''

    job = resolve_pending_job(queue_manager, chat_id, owner_chat_id)
    if not job:
        return {'success': False, 'job_id': None,
                'message': 'No listing waiting for review.'}

    title = (getattr(job, 'user_title', None) or getattr(job, 'title', None)
             or 'your item')
    if cmd == 'skip':
        ok = bool(queue_manager.update_job(job.id, {'status': JobStatus.SKIPPED}))
        message = f'Skipped "{title}".'
    else:
        price = cmd[1] if isinstance(cmd, tuple) else None
        ok = approve_job(queue_manager, job.id, user_price=price)
        message = (f'Set ${price:.2f} on "{title}" — approving and listing now.'
                   if price is not None else f'Approved "{title}" — listing now.')
        if ok:
            try:
                if not queue_manager.is_processing() and not queue_manager.is_paused():
                    queue_manager.start_processing()
            except Exception as e:
                logger.warning(f"Queue restart after approve failed: {e}")

    if not ok:
        return {'success': False, 'job_id': job.id,
                'message': 'Update failed — approve in the app.'}
    pop_review_marker(captures_dir, chat_id, job.id)
    return {'success': True, 'job_id': job.id, 'message': message}
