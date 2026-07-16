"""
Database models for the Feature Store service.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey, Table, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()

# Association table for many-to-many relationship between FeatureGroups and Features
feature_group_features = Table(
    'feature_group_features',
    Base.metadata,
    Column('feature_group_id', Integer, ForeignKey('feature_groups.id'), primary_key=True),
    Column('feature_id', Integer, ForeignKey('features.id'), primary_key=True)
)


class FeatureGroup(Base):
    """
    Logical grouping of related features.
    """
    __tablename__ = 'feature_groups'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    tags = Column(JSON, nullable=True)  # Store tags as JSON array

    # Indexes for common query patterns
    __table_args__ = (
        Index('idx_feature_group_name', 'name'),
        Index('idx_feature_group_active', 'is_active'),
    )


class Feature(Base):
    """
    Metadata about a feature (name, data type, description, owner).
    """
    __tablename__ = 'features'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    data_type = Column(String(50), nullable=False)  # e.g., 'float', 'int', 'string', 'bool'
    description = Column(Text, nullable=True)
    owner = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    tags = Column(JSON, nullable=True)  # Store tags as JSON array
    # Feature properties/configuration
    properties = Column(JSON, nullable=True)  # Store feature-specific properties

    # Indexes
    __table_args__ = (
        Index('idx_feature_name', 'name'),
        Index('idx_feature_active', 'is_active'),
        Index('idx_feature_data_type', 'data_type'),
    )


class FeatureVersion(Base):
    """
    Specific version of a feature with its schema and source information.
    """
    __tablename__ = 'feature_versions'

    id = Column(Integer, primary_key=True, index=True)
    feature_id = Column(Integer, ForeignKey('features.id'), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    schema_definition = Column(JSON, nullable=False)  # Feature schema/structure
    source_info = Column(JSON, nullable=True)  # Information about the source/data generation
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String(255), nullable=True)  # Who created this version
    is_active = Column(Boolean, default=True)

    # Relationships
    # feature = relationship("Feature", back_populates="versions")

    # Indexes
    __table_args__ = (
        Index('idx_feature_version_feature_id', 'feature_id'),
        Index('idx_feature_version_version', 'feature_id', 'version_number'),
        Index('idx_feature_version_active', 'is_active'),
        # Ensure unique version per feature
        {'sqlite_autoincrement': True}
    )


class FeatureValue(Base):
    """
    Actual feature values for entities at specific timestamps.
    """
    __tablename__ = 'feature_values'

    id = Column(Integer, primary_key=True, index=True)
    feature_version_id = Column(Integer, ForeignKey('feature_versions.id'), nullable=False, index=True)
    entity_id = Column(String(255), nullable=False, index=True)  # Unique identifier for the entity
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    value = Column(JSON, nullable=False)  # The actual feature value (can be any JSON type)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes for common query patterns
    __table_args__ = (
        Index('idx_feature_value_entity_time', 'entity_id', 'timestamp'),
        Index('idx_feature_value_feature_time', 'feature_version_id', 'timestamp'),
        Index('idx_feature_value_entity_feature', 'entity_id', 'feature_version_id'),
    )


class FeatureStatus(Base):
    """
    Track the status/health of features and feature versions.
    """
    __tablename__ = 'feature_status'

    id = Column(Integer, primary_key=True, index=True)
    feature_id = Column(Integer, ForeignKey('features.id'), nullable=False, index=True)
    feature_version_id = Column(Integer, ForeignKey('feature_versions.id'), nullable=True, index=True)
    status = Column(String(50), nullable=False)  # e.g., 'active', 'deprecated', 'failed'
    message = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
    checked_by = Column(String(255), nullable=True)  # What/system checked this

    # Indexes
    __table_args__ = (
        Index('idx_feature_status_feature', 'feature_id'),
        Index('idx_feature_status_checked_at', 'checked_at'),
    )