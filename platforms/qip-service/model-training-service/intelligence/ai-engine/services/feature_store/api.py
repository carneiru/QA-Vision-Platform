"""
API endpoints for the Feature Store service
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from ..service import FeatureStoreService
from ..repository import FeatureStoreRepository
from ..schemas import (
    FeatureGroupCreate, FeatureGroupUpdate, FeatureGroup,
    FeatureCreate, FeatureUpdate, Feature,
    FeatureVersionCreate, FeatureVersionUpdate, FeatureVersion,
    FeatureValueCreate, FeatureValueUpdate, FeatureValue,
    FeatureRegistrationRequest,
    FeatureRetrievalRequest, FeatureRetrievalResponse, BatchFeatureRetrievalResponse,
    HealthCheck
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Simple factory for dependency injection
def get_feature_store_repository() -> FeatureStoreRepository:
    """Get feature store repository instance."""
    return FeatureStoreRepository()


def get_feature_store_service(
    repository: FeatureStoreRepository = Depends(get_feature_store_repository)
) -> FeatureStoreService:
    """Dependency to get feature store service instance."""
    return FeatureStoreService(repository=repository)


# Health check endpoint
@router.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "feature-store", "timestamp": datetime.utcnow()}


# Feature Group endpoints
@router.post("/feature-groups", response_model=FeatureGroup, status_code=status.HTTP_201_CREATED)
async def create_feature_group(
    feature_group: FeatureGroupCreate,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Create a new feature group."""
    try:
        return await service.create_feature_group(feature_group)
    except Exception as e:
        logger.error(f"Error creating feature group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feature-groups/{feature_group_id}", response_model=FeatureGroup)
async def get_feature_group(
    feature_group_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get a feature group by ID."""
    feature_group = await service.get_feature_group(feature_group_id)
    if not feature_group:
        raise HTTPException(status_code=404, detail="Feature group not found")
    return feature_group


@router.get("/feature-groups/name/{name}", response_model=FeatureGroup)
async def get_feature_group_by_name(
    name: str,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get a feature group by name."""
    feature_group = await service.get_feature_group_by_name(name)
    if not feature_group:
        raise HTTPException(status_code=404, detail="Feature group not found")
    return feature_group


@router.get("/feature-groups", response_model=List[FeatureGroup])
async def list_feature_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """List feature groups with pagination."""
    try:
        return await service.list_feature_groups(skip, limit, active_only)
    except Exception as e:
        logger.error(f"Error listing feature groups: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/feature-groups/{feature_group_id}", response_model=FeatureGroup)
async def update_feature_group(
    feature_group_id: int = Path(..., gt=0),
    feature_group: FeatureGroupUpdate = ...,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Update a feature group."""
    try:
        updated_feature_group = await service.update_feature_group(feature_group_id, feature_group)
        if not updated_feature_group:
            raise HTTPException(status_code=404, detail="Feature group not found")
        return updated_feature_group
    except Exception as e:
        logger.error(f"Error updating feature group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/feature-groups/{feature_group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature_group(
    feature_group_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Delete a feature group."""
    try:
        deleted = await service.delete_feature_group(feature_group_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Feature group not found")
        return None
    except Exception as e:
        logger.error(f"Error deleting feature group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Feature endpoints
@router.post("/features", response_model=Feature, status_code=status.HTTP_201_CREATED)
async def create_feature(
    feature: FeatureCreate,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Create a new feature."""
    try:
        return await service.create_feature(feature)
    except Exception as e:
        logger.error(f"Error creating feature: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/{feature_id}", response_model=Feature)
async def get_feature(
    feature_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get a feature by ID."""
    feature = await service.get_feature(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.get("/features/name/{name}", response_model=Feature)
async def get_feature_by_name(
    name: str,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get a feature by name."""
    feature = await service.get_feature_by_name(name)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.get("/features", response_model=List[Feature])
async def list_features(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    feature_group_id: Optional[int] = Query(None, gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """List features with pagination and optional filtering."""
    try:
        return await service.list_features(skip, limit, active_only, feature_group_id)
    except Exception as e:
        logger.error(f"Error listing features: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/features/{feature_id}", response_model=Feature)
async def update_feature(
    feature_id: int = Path(..., gt=0),
    feature: FeatureUpdate = ...,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Update a feature."""
    try:
        updated_feature = await service.update_feature(feature_id, feature)
        if not updated_feature:
            raise HTTPException(status_code=404, detail="Feature not found")
        return updated_feature
    except Exception as e:
        logger.error(f"Error updating feature: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature(
    feature_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Delete a feature."""
    try:
        deleted = await service.delete_feature(feature_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Feature not found")
        return None
    except Exception as e:
        logger.error(f"Error deleting feature: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Feature Version endpoints
@router.post("/features/{feature_id}/versions", response_model=FeatureVersion, status_code=status.HTTP_201_CREATED)
async def create_feature_version(
    feature_id: int = Path(..., gt=0),
    feature_version: FeatureVersionCreate = ...,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Create a new feature version."""
    try:
        # Ensure the feature_id in path matches the one in request body
        if feature_id != feature_version.feature_id:
            raise HTTPException(status_code=400, detail="Feature ID mismatch")
        return await service.create_feature_version(feature_version)
    except Exception as e:
        logger.error(f"Error creating feature version: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/{feature_id}/versions/{version_id}", response_model=FeatureVersion)
async def get_feature_version(
    feature_id: int = Path(..., gt=0),
    version_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get a feature version by ID."""
    feature_version = await service.get_feature_version(version_id)
    if not feature_version:
        raise HTTPException(status_code=404, detail="Feature version not found")
    # Verify that the feature version belongs to the specified feature
    if feature_version.feature_id != feature_id:
        raise HTTPException(status_code=404, detail="Feature version not found for this feature")
    return feature_version


@router.get("/features/{feature_id}/versions/{version_number}", response_model=FeatureVersion)
async def get_feature_version_by_number(
    feature_id: int = Path(..., gt=0),
    version_number: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get a feature version by feature ID and version number."""
    feature_version = await service.get_feature_version_by_number(feature_id, version_number)
    if not feature_version:
        raise HTTPException(status_code=404, detail="Feature version not found")
    return feature_version


@router.get("/features/{feature_id}/versions", response_model=List[FeatureVersion])
async def list_feature_versions(
    feature_id: int = Path(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """List versions for a specific feature."""
    try:
        return await service.list_feature_versions(feature_id, skip, limit, active_only)
    except Exception as e:
        logger.error(f"Error listing feature versions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/{feature_id}/versions/latest", response_model=FeatureVersion)
async def get_latest_feature_version(
    feature_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get the latest active version of a feature."""
    feature_version = await service.get_latest_feature_version(feature_id)
    if not feature_version:
        raise HTTPException(status_code=404, detail="Feature not found or no active versions")
    return feature_version


@router.put("/features/{feature_id}/versions/{version_id}", response_model=FeatureVersion)
async def update_feature_version(
    feature_id: int = Path(..., gt=0),
    version_id: int = Path(..., gt=0),
    feature_version: FeatureVersionUpdate = ...,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Update a feature version."""
    try:
        # Verify that the feature version belongs to the specified feature
        existing_version = await service.get_feature_version(version_id)
        if not existing_version:
            raise HTTPException(status_code=404, detail="Feature version not found")
        if existing_version.feature_id != feature_id:
            raise HTTPException(status_code=404, detail="Feature version not found for this feature")

        updated_feature_version = await service.update_feature_version(version_id, feature_version)
        if not updated_feature_version:
            raise HTTPException(status_code=404, detail="Feature version not found")
        return updated_feature_version
    except Exception as e:
        logger.error(f"Error updating feature version: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/features/{feature_id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature_version(
    feature_id: int = Path(..., gt=0),
    version_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Delete a feature version."""
    try:
        # Verify that the feature version belongs to the specified feature
        existing_version = await service.get_feature_version(version_id)
        if not existing_version:
            raise HTTPException(status_code=404, detail="Feature version not found")
        if existing_version.feature_id != feature_id:
            raise HTTPException(status_code=404, detail="Feature version not found for this feature")

        deleted = await service.delete_feature_version(version_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Feature version not found")
        return None
    except Exception as e:
        logger.error(f"Error deleting feature version: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Feature Value endpoints
@router.post("/feature-values", response_model=FeatureValue, status_code=status.HTTP_201_CREATED)
async def create_feature_value(
    feature_value: FeatureValueCreate,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Create a new feature value."""
    try:
        return await service.create_feature_value(feature_value)
    except Exception as e:
        logger.error(f"Error creating feature value: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feature-values/batch", response_model=List[FeatureValue], status_code=status.HTTP_201_CREATED)
async def create_feature_values_batch(
    feature_values: List[FeatureValueCreate],
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Create multiple feature values in a batch."""
    try:
        return await service.create_feature_values_batch(feature_values)
    except Exception as e:
        logger.error(f"Error creating feature values batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feature-values/{feature_value_id}", response_model=FeatureValue)
async def get_feature_value(
    feature_value_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get a feature value by ID."""
    feature_value = await service.get_feature_value(feature_value_id)
    if not feature_value:
        raise HTTPException(status_code=404, detail="Feature value not found")
    return feature_value


@router.get("/feature-values/entities/{entity_id}", response_model=List[FeatureValue])
async def get_feature_values_for_entity(
    entity_id: str,
    feature_version_ids: Optional[List[int]] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get feature values for a specific entity."""
    try:
        return await service.get_feature_values_for_entity(
            entity_id, feature_version_ids, start_time, end_time, limit
        )
    except Exception as e:
        logger.error(f"Error getting feature values for entity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feature-values/latest/{entity_id}/{feature_version_id}", response_model=FeatureValue)
async def get_latest_feature_value(
    entity_id: str,
    feature_version_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get the latest feature value for an entity and feature version."""
    try:
        feature_value = await service.get_latest_feature_value(entity_id, feature_version_id)
        if not feature_value:
            raise HTTPException(status_code=404, detail="Feature value not found")
        return feature_value
    except Exception as e:
        logger.error(f"Error getting latest feature value: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feature-values/batch", response_model=List[FeatureValue])
async def get_feature_values_batch(
    entity_ids: List[str],
    feature_version_ids: List[int],
    timestamp: Optional[datetime] = Query(None),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get feature values for multiple entities and feature versions."""
    try:
        return await service.get_feature_values_batch(entity_ids, feature_version_ids, timestamp)
    except Exception as e:
        logger.error(f"Error getting feature values batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/feature-values/entities/{entity_id}", status_code=status.HTTP_200_OK)
async def delete_feature_values_for_entity(
    entity_id: str,
    feature_version_ids: Optional[List[int]] = Query(None),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Delete feature values for an entity."""
    try:
        count = await service.delete_feature_values_for_entity(entity_id, feature_version_ids)
        return {"deleted_count": count}
    except Exception as e:
        logger.error(f"Error deleting feature values for entity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Feature Group Assignment endpoints
@router.post("/feature-groups/{feature_group_id}/features/{feature_id}", status_code=status.HTTP_200_OK)
async def add_feature_to_group(
    feature_group_id: int = Path(..., gt=0),
    feature_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Add a feature to a feature group."""
    try:
        success = await service.add_feature_to_group(feature_id, feature_group_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add feature to group")
        return {"message": "Feature added to group successfully"}
    except Exception as e:
        logger.error(f"Error adding feature to group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/feature-groups/{feature_group_id}/features/{feature_id}", status_code=status.HTTP_200_OK)
async def remove_feature_from_group(
    feature_group_id: int = Path(..., gt=0),
    feature_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Remove a feature from a feature group."""
    try:
        success = await service.remove_feature_from_group(feature_id, feature_group_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to remove feature from group")
        return {"message": "Feature removed from group successfully"}
    except Exception as e:
        logger.error(f"Error removing feature from group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/{feature_id}/groups", response_model=List[FeatureGroup])
async def get_feature_groups_for_feature(
    feature_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get all feature groups that a feature belongs to."""
    try:
        return await service.get_feature_groups_for_feature(feature_id)
    except Exception as e:
        logger.error(f"Error getting feature groups for feature: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feature-groups/{feature_group_id}/features", response_model=List[Feature])
async def get_features_in_group(
    feature_group_id: int = Path(..., gt=0),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get all features that belong to a feature group."""
    try:
        return await service.get_features_in_group(feature_group_id)
    except Exception as e:
        logger.error(f"Error getting features in group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Feature Registration endpoint
@router.post("/features/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_feature(
    registration_request: FeatureRegistrationRequest,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Register a new feature with initial version and associate with feature groups."""
    try:
        feature, feature_version, feature_groups = await service.register_feature(registration_request)
        return {
            "feature": feature,
            "feature_version": feature_version,
            "feature_groups": feature_groups
        }
    except Exception as e:
        logger.error(f"Error registering feature: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Feature Retrieval endpoints
@router.post("/feature-values/retrieve", response_model=BatchFeatureRetrievalResponse)
async def retrieve_feature_values(
    retrieval_request: FeatureRetrievalRequest,
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Retrieve feature values for multiple entities and features."""
    try:
        results = await service.get_features_for_entities(
            retrieval_request.entity_ids,
            retrieval_request.feature_names,
            retrieval_request.timestamp
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"Error retrieving feature values: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feature-values/entities/{entity_id}/features", response_model=FeatureRetrievalResponse)
async def get_features_for_entity(
    entity_id: str,
    feature_names: List[str] = Query(...),
    timestamp: Optional[datetime] = Query(None),
    service: FeatureStoreService = Depends(get_feature_store_service)
):
    """Get feature values for a specific entity and list of feature names."""
    try:
        results = await service.get_features_for_entities(
            [entity_id],
            feature_names,
            timestamp
        )
        if not results:
            raise HTTPException(status_code=404, detail="No feature values found")
        return results[0]
    except Exception as e:
        logger.error(f"Error getting features for entity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))