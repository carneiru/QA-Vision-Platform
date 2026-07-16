"""
Pydantic schemas for the Feature Store service.
"""
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from uuid import UUID

# FeatureGroup Schemas
class FeatureGroupBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the feature group")
    description: Optional[str] = Field(None, description="Description of the feature group")
    owner: Optional[str] = Field(None, max_length=255, description="Owner of the feature group")
    tags: Optional[List[str]] = Field(None, description="Tags associated with the feature group")
    is_active: bool = Field(True, description="Whether the feature group is active")


class FeatureGroupCreate(FeatureGroupBase):
    pass


class FeatureGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    owner: Optional[str] = Field(None, max_length=255)
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class FeatureGroupInDBBase(FeatureGroupBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class FeatureGroup(FeatureGroupInDBBase):
    pass


class FeatureGroupWithFeatures(FeatureGroup):
    features: List["Feature"] = []


# Feature Schemas
class FeatureBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the feature")
    data_type: str = Field(..., description="Data type of the feature (e.g., 'float', 'int', 'string', 'bool')")
    description: Optional[str] = Field(None, description="Description of the feature")
    owner: Optional[str] = Field(None, max_length=255, description="Owner of the feature")
    tags: Optional[List[str]] = Field(None, description="Tags associated with the feature")
    properties: Optional[Dict[str, Any]] = Field(None, description="Feature-specific properties")
    is_active: bool = Field(True, description="Whether the feature is active")


class FeatureCreate(FeatureBase):
    pass


class FeatureUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    data_type: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = Field(None, max_length=255)
    tags: Optional[List[str]] = None
    properties: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class FeatureInDBBase(FeatureBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class Feature(FeatureInDBBase):
    pass


class FeatureWithGroups(Feature):
    groups: List[FeatureGroup] = []


# FeatureVersion Schemas
class FeatureVersionBase(BaseModel):
    version_number: int = Field(..., description="Version number of the feature")
    schema_definition: Dict[str, Any] = Field(..., description="Schema definition of the feature")
    source_info: Optional[Dict[str, Any]] = Field(None, description="Information about the source/data generation")
    description: Optional[str] = Field(None, description="Description of this feature version")
    created_by: Optional[str] = Field(None, max_length=255, description="Who created this version")
    is_active: bool = Field(True, description="Whether this feature version is active")


class FeatureVersionCreate(FeatureVersionBase):
    feature_id: int = Field(..., description="ID of the feature this version belongs to")


class FeatureVersionUpdate(BaseModel):
    version_number: Optional[int] = None
    schema_definition: Optional[Dict[str, Any]] = None
    source_info: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    created_by: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class FeatureVersionInDBBase(FeatureVersionBase):
    id: int
    feature_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class FeatureVersion(FeatureVersionInDBBase):
    pass


class FeatureVersionWithFeature(FeatureVersion):
    feature: Feature


# FeatureValue Schemas
class FeatureValueBase(BaseModel):
    entity_id: str = Field(..., description="Unique identifier for the entity")
    timestamp: datetime = Field(..., description="Timestamp when the feature value was recorded")
    value: Any = Field(..., description="The actual feature value")


class FeatureValueCreate(FeatureValueBase):
    feature_version_id: int = Field(..., description="ID of the feature version this value belongs to")


class FeatureValueUpdate(BaseModel):
    entity_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    value: Optional[Any] = None


class FeatureValueInDBBase(FeatureValueBase):
    id: int
    feature_version_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class FeatureValue(FeatureValueInDBBase):
    pass


# FeatureValueWithDetails for responses that include feature information
class FeatureValueWithDetails(FeatureValue):
    feature_version: FeatureVersion
    feature: Feature


# Feature Retrieval Schemas
class FeatureRetrievalRequest(BaseModel):
    entity_ids: List[str] = Field(..., description="List of entity IDs to retrieve features for")
    feature_names: List[str] = Field(..., description="List of feature names to retrieve")
    timestamp: Optional[datetime] = Field(None, description="Timestamp to retrieve feature values for (latest if not specified)")


class FeatureRetrievalResponse(BaseModel):
    entity_id: str
    timestamp: datetime
    features: Dict[str, Any] = Field(..., description="Feature name to value mapping")


class BatchFeatureRetrievalResponse(BaseModel):
    results: List[FeatureRetrievalResponse] = Field(..., description="Retrieved features for each entity")


# Feature Registration Schemas
class FeatureRegistrationRequest(BaseModel):
    feature_group_names: List[str] = Field(..., description="Names of feature groups to associate the feature with")
    feature: FeatureCreate = Field(..., description="Feature definition")
    version: FeatureVersionCreate = Field(..., description="Initial version of the feature")


class FeatureRegistrationResponse(BaseModel):
    feature: Feature
    feature_version: FeatureVersion
    feature_groups: List[FeatureGroup] = []


# Health check schema
class HealthCheck(BaseModel):
    status: str = "healthy"
    service: str = "feature-store"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Update forward references
FeatureGroupWithFeatures.update_forward_refs()
FeatureWithGroups.update_forward_refs()
FeatureVersionWithFeature.update_forward_refs()
FeatureValueWithDetails.update_forward_refs()