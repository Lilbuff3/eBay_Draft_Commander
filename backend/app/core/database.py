from datetime import datetime, timezone
import json
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, Float, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship


class Base(DeclarativeBase):
    pass

class JobModel(Base):
    """Database model for queue jobs"""
    __tablename__ = 'jobs'
    __table_args__ = (
        Index('idx_jobs_status', 'status'),
        Index('idx_jobs_batch_id', 'batch_id'),
        Index('idx_jobs_created_at', 'created_at'),
        Index('idx_jobs_scheduled_time', 'scheduled_time'),
    )

    id = Column(String(10), primary_key=True)
    folder_path = Column(Text, nullable=False)
    folder_name = Column(String(255), nullable=False)
    status = Column(String(20), default='pending')
    batch_id = Column(String(50))
    
    # Core Listing Data
    title = Column(String(255))  # Final title used for listing
    description = Column(Text)   # Final HTML description
    price = Column(String(20))   # Final price
    condition = Column(String(50))
    condition_description = Column(Text)
    confidence_score = Column(Float)
    
    # IDs
    listing_id = Column(String(50))
    offer_id = Column(String(50))
    
    # User Overrides (Source of Truth for edits)
    user_title = Column(String(255))
    user_price = Column(String(20))
    user_description = Column(Text)
    user_condition = Column(String(50))
    
    # AI Analysis Data (Stored as JSON)
    ai_json = Column(Text)
    
    # Item Specifics / Aspects (Stored as JSON)
    item_specifics_json = Column(Text)
    
    # Metadata / Source Info
    source = Column(String(50), default='folder') # folder, metadata_import, ebay_import
    source_url = Column(String(512)) # URL if imported
    note = Column(Text)
    
    # Error Handling
    error_type = Column(String(100))
    error_message = Column(Text)
    
    # Timing & Metrics
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    # default must be a callable — a bare datetime.now() is evaluated once at
    # import and every row would share that timestamp
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    timing_json = Column(Text)
    scheduled_time = Column(DateTime)
    
    # Cached thumbnail filename (avoids filesystem scan on every /jobs request)
    thumbnail_name = Column(String(255))

    # Legacy / Generic Metadata (Keep for backward compatibility during migration)
    metadata_json = Column(Text)

    @property
    def ai_data(self):
        return json.loads(self.ai_json) if self.ai_json else {}
    
    @ai_data.setter
    def ai_data(self, value):
        self.ai_json = json.dumps(value)

    @property
    def item_specifics(self):
        return json.loads(self.item_specifics_json) if self.item_specifics_json else {}
    
    @item_specifics.setter
    def item_specifics(self, value):
        self.item_specifics_json = json.dumps(value)

    @property
    def timing(self):
        return json.loads(self.timing_json) if self.timing_json else {}
    
    @timing.setter
    def timing(self, value):
        self.timing_json = json.dumps(value)

    @property
    def job_metadata(self):
        return json.loads(self.metadata_json) if self.metadata_json else {}
    
    @job_metadata.setter
    def job_metadata(self, value):
        self.metadata_json = json.dumps(value)

class TemplateModel(Base):
    """Database model for listing templates"""
    __tablename__ = 'templates'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    data_json = Column(Text, nullable=False)  # Stores the template configuration
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    use_count = Column(Integer, default=0)
    
    @property
    def data(self):
        return json.loads(self.data_json) if self.data_json else {}
    
    @data.setter
    def data(self, value):
        self.data_json = json.dumps(value)

class AppToken(Base):
    """Database model for application tokens (e.g. eBay access tokens)"""
    __tablename__ = 'app_tokens'

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SaleModel(Base):
    """Local snapshot of a sold eBay order line — accumulates past eBay's 90-day order window.

    One row per order (v1 records the first line item only, matching the shape
    /api/orders already returns; multi-line orders are rare for this seller).
    cogs is frozen here at sweep time from job_metadata['cogs'] and can be
    filled in later from the Profit tab.
    """
    __tablename__ = 'sales'
    __table_args__ = (
        Index('idx_sales_sold_at', 'sold_at'),
        Index('idx_sales_listing_id', 'listing_id'),
    )

    order_id = Column(String(50), primary_key=True)
    listing_id = Column(String(50))          # eBay legacyItemId — join key to jobs
    job_id = Column(String(10))              # local job id if matched, else NULL
    title = Column(String(255))
    quantity = Column(Integer, default=1)
    sale_total = Column(Float, nullable=False)  # order total (item + any buyer-paid extras)
    sold_at = Column(DateTime)               # order creationDate
    paid_at = Column(DateTime)
    fees_est = Column(Float)                 # FVF% * total + payment fee, frozen at sweep
    ship_est = Column(Float)                 # flat ship estimate, frozen at sweep
    cogs = Column(Float)                     # NULL = unknown, first-class state
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ListingActionModel(Base):
    """Autopilot audit + idempotency trail: one row per offer/markdown/relist
    decision. Dry-run cycles write rows too (dry_run=1) — that's the audit
    feed the owner reviews before flipping live; idempotency checks only
    count live rows so an observation window never suppresses real actions.
    action_type 'no_relist' blocklists intentionally-ended listings."""
    __tablename__ = 'listing_actions'
    __table_args__ = (
        Index('idx_listing_actions_listing', 'listing_id'),
        Index('idx_listing_actions_type', 'action_type'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(String(50), nullable=False)
    action_type = Column(String(20), nullable=False)  # offer|markdown|relist|no_relist
    executed_at = Column(Float, nullable=False)       # epoch seconds
    dry_run = Column(Boolean, default=False, nullable=False)
    details_json = Column(Text)

    @property
    def details(self):
        return json.loads(self.details_json) if self.details_json else {}

    @details.setter
    def details(self, value):
        self.details_json = json.dumps(value)


# Database Setup
def get_db_engine(db_path: Path):
    from sqlalchemy import event
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    
    # Enable WAL mode for better concurrent access from background threads
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
    
    return engine

def init_db(db_path: Path):
    engine = get_db_engine(db_path)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
