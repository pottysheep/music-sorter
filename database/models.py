"""SQLAlchemy database models for Music Sorter"""
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class File(Base):
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True)
    source_path = Column(Text, unique=True, nullable=False)
    file_size = Column(Integer)
    modified_date = Column(DateTime)
    file_hash = Column(String(32))  # MD5 hash
    audio_hash = Column(String(64))  # Audio fingerprint
    status = Column(String(20), default='indexed')  # indexed, analyzed, migrated, error
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    file_metadata = relationship("Metadata", back_populates="file", uselist=False, cascade="all, delete-orphan")
    duplicates = relationship("Duplicate", back_populates="file", cascade="all, delete-orphan")
    migration = relationship("Migration", back_populates="file", uselist=False, cascade="all, delete-orphan")
    audio_analysis = relationship("AudioAnalysis", back_populates="file", uselist=False, cascade="all, delete-orphan")
    classification = relationship("Classification", back_populates="file", uselist=False, cascade="all, delete-orphan")

class Metadata(Base):
    __tablename__ = 'metadata'
    
    file_id = Column(Integer, ForeignKey('files.id'), primary_key=True)
    artist = Column(String(255))
    album = Column(String(255))
    title = Column(String(255))
    track_number = Column(Integer)
    year = Column(Integer)
    genre = Column(String(100))
    duration_seconds = Column(Float)
    bitrate = Column(Integer)
    sample_rate = Column(Integer)
    format = Column(String(10))  # mp3, wav, flac, etc.
    fingerprint_id = Column(String(64))  # AcoustID fingerprint
    
    # Relationship
    file = relationship("File", back_populates="file_metadata")

class Duplicate(Base):
    __tablename__ = 'duplicates'
    
    id = Column(Integer, primary_key=True)
    group_id = Column(String(36))  # UUID for duplicate group
    file_id = Column(Integer, ForeignKey('files.id'))
    is_primary = Column(Boolean, default=False)  # Best quality in group
    quality_score = Column(Integer)  # Calculated quality score
    
    # Relationship
    file = relationship("File", back_populates="duplicates")

class Migration(Base):
    __tablename__ = 'migrations'
    
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'))
    source_path = Column(Text)
    target_path = Column(Text)
    status = Column(String(20), default='pending')  # pending, in_progress, completed, failed
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error = Column(Text)
    
    # Relationship
    file = relationship("File", back_populates="migration")

class AudioAnalysis(Base):
    __tablename__ = 'audio_analysis'
    
    file_id = Column(Integer, ForeignKey('files.id'), primary_key=True)
    bpm = Column(Float)
    key_signature = Column(String(10))  # C, C#, D, etc.
    energy = Column(Float)
    danceability = Column(Float)
    loudness_db = Column(Float)
    dynamic_range = Column(Float)
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    file = relationship("File", back_populates="audio_analysis")

class Classification(Base):
    __tablename__ = 'classifications'
    
    file_id = Column(Integer, ForeignKey('files.id'), primary_key=True)
    file_type = Column(String(20))  # song, sample, unknown
    confidence = Column(Float)  # 0.0 to 1.0
    classification_method = Column(String(50))  # size_threshold, ml_model, etc.
    classification_details = Column(JSON)  # Additional details about the classification
    classified_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    file = relationship("File", back_populates="classification")

class Checkpoint(Base):
    __tablename__ = 'checkpoints'
    
    id = Column(Integer, primary_key=True)
    operation = Column(String(50))  # scan, analyze, migrate, etc.
    state = Column(Text)  # Serialized state
    progress = Column(Integer)
    total = Column(Integer)
    checkpoint_data = Column(JSON)  # Additional checkpoint data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)