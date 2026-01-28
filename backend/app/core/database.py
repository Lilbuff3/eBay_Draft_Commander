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
    listing_id = Column(String(50))
    offer_id = Column(String(50))
    price = Column(String(20))
    error_type = Column(String(100))
    error_message = Column(Text)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    timing_json = Column(Text)  # Stores JSON string of timing data
    
    @property
    def timing(self):
        return json.loads(self.timing_json) if self.timing_json else {}
    
    @timing.setter
    def timing(self, value):
        self.timing_json = json.dumps(value)

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
    return create_engine(f"sqlite:///{db_path}")

def init_db(db_path: Path):
    engine = get_db_engine(db_path)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
