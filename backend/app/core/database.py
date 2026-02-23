from datetime import datetime
import json
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

class JobModel(Base):
    """Database model for queue jobs"""
    __tablename__ = 'jobs'
    
    id = Column(String(10), primary_key=True)
    folder_path = Column(Text, nullable=False)
    folder_name = Column(String(255), nullable=False)
    status = Column(String(20), default='pending')
    
    # Core Listing Data
    title = Column(String(255))  # Final title used for listing
    description = Column(Text)   # Final HTML description
    price = Column(String(20))   # Final price
    condition = Column(String(50))
    condition_description = Column(Text)
    
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
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    timing_json = Column(Text)
    scheduled_time = Column(DateTime)
    
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    use_count = Column(Integer, default=0)
    
    @property
    def data(self):
        return json.loads(self.data_json) if self.data_json else {}
    
    @data.setter
    def data(self, value):
        self.data_json = json.dumps(value)

# Database Setup
def get_db_engine(db_path: Path):
    from sqlalchemy import event
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    
    # Enable WAL mode for better concurrent access from background threads
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    
    return engine

def init_db(db_path: Path):
    engine = get_db_engine(db_path)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
