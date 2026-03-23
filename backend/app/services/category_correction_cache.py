"""
Category Correction Cache
Stores human-corrected category mappings (title_hash -> category) so
future items with similar titles can skip the expensive API+AI pipeline.
"""
import hashlib
import sqlite3
import threading
import time
from backend.app.core.logger import get_logger

logger = get_logger('category_correction_cache')

_instance = None
_instance_lock = threading.Lock()


def get_correction_cache():
    """Module-level singleton accessor (thread-safe)."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CategoryCorrectionCache()
    return _instance


class CategoryCorrectionCache:
    def __init__(self):
        from backend.app.core.paths import get_data_dir
        self._db_path = str(get_data_dir() / "commander.db")

    @staticmethod
    def _normalize_title(title: str) -> str:
        return ' '.join(title.lower().strip().split())

    @staticmethod
    def _hash_title(normalized: str) -> str:
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def lookup(self, title: str) -> dict | None:
        """
        Check if we have a human-corrected category for this title.
        Returns {'id': ..., 'name': ..., 'source': 'correction_cache'} or None.
        """
        normalized = self._normalize_title(title)
        title_hash = self._hash_title(normalized)

        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT category_id, category_name FROM category_corrections WHERE title_hash = ?",
                (title_hash,)
            )
            row = cursor.fetchone()

            if row:
                # Increment use_count
                conn.execute(
                    "UPDATE category_corrections SET use_count = use_count + 1, updated_at = ? WHERE title_hash = ?",
                    (time.time(), title_hash)
                )
                conn.commit()
                conn.close()
                logger.info(f"Correction cache hit for: {title[:50]}")
                return {
                    'id': row[0],
                    'name': row[1],
                    'source': 'correction_cache'
                }

            conn.close()
        except Exception as e:
            logger.warning(f"Correction cache lookup error: {e}")

        return None

    def record(self, title: str, category_id: str, category_name: str = ''):
        """Store a human-corrected category mapping."""
        normalized = self._normalize_title(title)
        title_hash = self._hash_title(normalized)
        now = time.time()

        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """INSERT INTO category_corrections
                   (title_hash, original_title, category_id, category_name, use_count, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?)
                   ON CONFLICT(title_hash) DO UPDATE SET
                   category_id = excluded.category_id,
                   category_name = excluded.category_name,
                   updated_at = excluded.updated_at""",
                (title_hash, title[:500], category_id, category_name, now, now)
            )
            conn.commit()
            conn.close()
            logger.info(f"Recorded category correction: '{title[:50]}' -> {category_id} ({category_name})")
        except Exception as e:
            logger.warning(f"Failed to record correction: {e}")

    def get_stats(self) -> dict:
        """Return cache statistics."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(use_count), 0) FROM category_corrections")
            row = cursor.fetchone()
            conn.close()
            return {'corrections': row[0], 'total_uses': row[1]}
        except Exception as e:
            logger.warning(f"Failed to get correction stats: {e}")
            return {'corrections': 0, 'total_uses': 0}

    def clear(self):
        """Delete all corrections."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("DELETE FROM category_corrections")
            conn.commit()
            conn.close()
            logger.info("Category correction cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear correction cache: {e}")
