"""
Feature Store Service Implementation
"""
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime

from .repository import FeatureStoreRepository
from .models import (
    FeatureGroup, Feature, FeatureVersion, FeatureValue,
    feature_group_feature
)
from .schemas import (
    FeatureGroupCreate, FeatureGroupUpdate,
    FeatureCreate, FeatureUpdate,
    FeatureVersionCreate, FeatureVersionUpdate,
    FeatureValueCreate, FeatureValueUpdate,
    FeatureRegistrationRequest
)

logger = logging.getLogger(__name__)


class FeatureStoreService:
    """Service for feature store management."""

    def __init__(self, repository: FeatureStoreRepository):
        """Initialize the feature store service.

        Args:
            repository: Repository for data access operations
        """
        self.repository = repository

    # Feature Group Methods
    async def create_feature_group(self, feature_group_data: FeatureGroupCreate) -> FeatureGroup:
        """Create a new feature group.

        Args:
            feature_group_data: Feature group creation data

        Returns:
            Created feature group
        """
        logger.info(f"Creating feature group: {feature_group_data.name}")
        return await self.repository.create_feature_group(feature_group_data.dict())

    async def get_feature_group(self, feature_group_id: int) -> Optional[FeatureGroup]:
        """Get a feature group by ID.

        Args:
            feature_group_id: ID of the feature group

        Returns:
            Feature group if found, None otherwise
        """
        logger.debug(f"Getting feature group {feature_group_id}")
        return await self.repository.get_feature_group(feature_group_id)

    async def get_feature_group_by_name(self, name: str) -> Optional[FeatureGroup]:
        """Get a feature group by name.

        Args:
            name: Name of the feature group

        Returns:
            Feature group if found, None otherwise
        """
        logger.debug(f"Getting feature group by name: {name}")
        return await self.repository.get_feature_group_by_name(name)

    async def list_feature_groups(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False
    ) -> List[FeatureGroup]:
        """List feature groups with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Whether to return only active feature groups

        Returns:
            List of feature groups
        """
        logger.debug(f"Listing feature groups (skip={skip}, limit={limit}, active_only={active_only})")
        return await self.repository.list_feature_groups(skip, limit, active_only)

    async def update_feature_group(
        self,
        feature_group_id: int,
        feature_group_data: FeatureGroupUpdate
    ) -> Optional[FeatureGroup]:
        """Update a feature group.

        Args:
            feature_group_id: ID of the feature group to update
            feature_group_data: Update data for the feature group

        Returns:
            Updated feature group if found, None otherwise
        """
        logger.info(f"Updating feature group {feature_group_id}")
        # Remove None values to avoid overwriting with None
        update_data = {k: v for k, v in feature_group_data.dict().items() if v is not None}
        return await self.repository.update_feature_group(feature_group_id, update_data)

    async def delete_feature_group(self, feature_group_id: int) -> bool:
        """Delete a feature group (soft delete).

        Args:
            feature_group_id: ID of the feature group to delete

        Returns:
            True if deleted, False if not found
        """
        logger.info(f"Deleting feature group {feature_group_id}")
        return await self.repository.delete_feature_group(feature_group_id)

    # Feature Methods
    async def create_feature(self, feature_data: FeatureCreate) -> Feature:
        """Create a new feature.

        Args:
            feature_data: Feature creation data

        Returns:
            Created feature
        """
        logger.info(f"Creating feature: {feature_data.name}")
        return await self.repository.create_feature(feature_data.dict())

    async def get_feature(self, feature_id: int) -> Optional[Feature]:
        """Get a feature by ID.

        Args:
            feature_id: ID of the feature

        Returns:
            Feature if found, None otherwise
        """
        logger.debug(f"Getting feature {feature_id}")
        return await self.repository.get_feature(feature_id)

    async def get_feature_by_name(self, name: str) -> Optional[Feature]:
        """Get a feature by name.

        Args:
            name: Name of the feature

        Returns:
            Feature if found, None otherwise
        """
        logger.debug(f"Getting feature by name: {name}")
        return await self.repository.get_feature_by_name(name)

    async def list_features(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
        feature_group_id: Optional[int] = None
    ) -> List[Feature]:
        """List features with pagination and optional filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Whether to return only active features
            feature_group_id: Optional feature group ID to filter by

        Returns:
            List of features
        """
        logger.debug(f"Listing features (skip={skip}, limit={limit}, active_only={active_only}, feature_group_id={feature_group_id})")
        return await self.repository.list_features(skip, limit, active_only, feature_group_id)

    async def update_feature(
        self,
        feature_id: int,
        feature_data: FeatureUpdate
    ) -> Optional[Feature]:
        """Update a feature.

        Args:
            feature_id: ID of the feature to update
            feature_data: Update data for the feature

        Returns:
            Updated feature if found, None otherwise
        """
        logger.info(f"Updating feature {feature_id}")
        # Remove None values to avoid overwriting with None
        update_data = {k: v for k, v in feature_data.dict().items() if v is not None}
        return await self.repository.update_feature(feature_id, update_data)

    async def delete_feature(self, feature_id: int) -> bool:
        """Delete a feature (soft delete).

        Args:
            feature_id: ID of the feature to delete

        Returns:
            True if deleted, False if not found
        """
        logger.info(f"Deleting feature {feature_id}")
        return await self.repository.delete_feature(feature_id)

    # Feature Version Methods
    async def create_feature_version(self, feature_version_data: FeatureVersionCreate) -> FeatureVersion:
        """Create a new feature version.

        Args:
            feature_version_data: Feature version creation data

        Returns:
            Created feature version
        """
        logger.info(f"Creating feature version for feature {feature_version_data.feature_id}")
        return await self.repository.create_feature_version(feature_version_data.dict())

    async def get_feature_version(self, feature_version_id: int) -> Optional[FeatureVersion]:
        """Get a feature version by ID.

        Args:
            feature_version_id:feature_version_id: ID of the feature version

        Returns:
            Feature version if found, None otherwise
        """
        logger.debug(f"Getting feature version {feature_version_id}")
        return await self.repository.get_feature_version(feature_version_id)

    async def get_feature_version_by_number(
        self,
        feature_id: int,
        version_number: int
    ) -> Optional[FeatureVersion]:
        """Get a feature version by feature ID and version number.

        Args:
            feature_id: ID of the feature
            version_number: Version number to retrieve

        Returns:
            Feature version if found, None otherwise
        """
        logger.debug(f"Getting feature version {feature_id} v{version_number}")
        return await self.repository.get_feature_version_by_number(feature_id, version_number)

    async def list_feature_versions(
        self,
        feature_id: int,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False
    ) -> List[FeatureVersion]:
        """List versions for a specific feature.

        Args:
            feature_id: ID of the feature
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Whether to return only active versions

        Returns:
            List of feature versions
        """
        logger.debug(f"Listing feature versions for feature {feature_id} (skip={skip}, limit={limit}, active_only={active_only})")
        return await self.repository.list_feature_versions(feature_id, skip, limit, active_only)

    async def get_latest_feature_version(self, feature_id: int) -> Optional[FeatureVersion]:
        """Get the latest active version of a feature.

        Args:
            feature_id: ID of the feature

        Returns:
            Latest feature version if found, None otherwise
        """
        logger.debug(f"Getting latest feature version for feature {feature_id}")
        return await self.repository.get_latest_feature_version(feature_id)

    async def update_feature_version(
        self,
        feature_version_id: int,
        feature_version_data: FeatureVersionUpdate
    ) -> Optional[FeatureVersion]:
        """Update a feature version.

        Args:
            feature_version_id: ID of the feature version to update
            feature_version_data: Update data for the feature version

        Returns:
            Updated feature version if found, None otherwise
        """
        logger.info(f"Updating feature version {feature_version_id}")
        # Remove None values to avoid overwriting with None
        update_data = {k: v for k, v in feature_version_data.dict().items() if v is not None}
        return await self.repository.update_feature_version(feature_version_id, update_data)

    async def delete_feature_version(self, feature_version_id: int) -> bool:
        """Delete a feature version (soft delete).

        Args:
            feature_version_id: ID of the feature version to delete

        Returns:
            True if deleted, False if not found
        """
        logger.info(f"Deleting feature version {feature_version_id}")
        return await self.repository.delete_feature_version(feature_version_id)

    # Feature Value Methods
    async def create_feature_value(self, feature_value_data: FeatureValueCreate) -> FeatureValue:
        """Create a new feature value.

        Args:
            feature_value_data: Feature value creation data

        Returns:
            Created feature value
        """
        logger.debug(f"Creating feature value for entity {feature_value_data.entity_id}")
        return await self.repository.create_feature_value(feature_value_data.dict())

    async def create_feature_values_batch(self, feature_values_data: List[FeatureValueCreate]) -> List[FeatureValue]:
        """Create multiple feature values in a batch.

        Args:
            feature_values_data: List of feature value creation data

        Returns:
            List of created feature values
        """
        logger.info(f"Creating batch of {len(feature_values_data)} feature values")
        return await self.repository.create_feature_values_batch(
            [fv.dict() for fv in feature_values_data]
        )

    async def get_feature_value(self, feature_value_id: int) -> Optional[FeatureValue]:
        """Get a feature value by ID.

        Args:
            feature_value_id: ID of the feature value

        Returns:
            Feature value if found, None otherwise
        """
        logger.debug(f"Getting feature value {feature_value_id}")
        return await self.repository.get_feature_value(feature_value_id)

    async def get_feature_values_for_entity(
        self,
        entity_id: str,
        feature_version_ids: Optional[List[int]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[FeatureValue]:
        """Get feature values for a specific entity.

        Args:
            entity_id: ID of the entity
            feature_version_ids: Optional list of feature version IDs to filter by
            start_time: Optional start time for filtering
            end_time: Optional end time for filtering
            limit: Maximum number of records to return

        Returns:
            List of feature values for the entity
        """
        logger.debug(f"Getting feature values for entity {entity_id}")
        return await self.repository.get_feature_values_for_entity(
            entity_id, feature_version_ids, start_time, end_time, limit
        )

    async def get_latest_feature_value(
        self,
        entity_id: str,
        feature_version_id: int
    ) -> Optional[FeatureValue]:
        """Get the latest feature value for an entity and feature version.

        Args:
            entity_id: ID of the entity
            feature_version_id: ID of the feature version

        Returns:
            Latest feature value if found, None otherwise
        """
        logger.debug(f"Getting latest feature value for entity {entity_id}, feature version {feature_version_id}")
        return await self.repository.get_latest_feature_value(entity_id, feature_version_id)

    async def get_feature_values_batch(
        self,
        entity_ids: List[str],
        feature_version_ids: List[int],
        timestamp: Optional[datetime] = None
    ) -> List[FeatureValue]:
        """Get feature values for multiple entities and feature versions.

        Args:
            entity_ids: List of entity IDs
            feature_version_ids: List of feature version IDs
            timestamp: Optional timestamp to get values at or before

        Returns:
            List of feature values
        """
        logger.debug(f"Getting feature values batch for {len(entity_ids)} entities and {len(feature_version_ids)} feature versions")
        return await self.repository.get_feature_values_batch(entity_ids, feature_version_ids, timestamp)

    async def delete_feature_values_for_entity(
        self,
        entity_id: str,
        feature_version_ids: Optional[List[int]] = None
    ) -> int:
        """Delete feature values for an entity.

        Args:
            entity_id: ID of the entity
            feature_version_ids: Optional list of feature version IDs to filter by

        Returns:
            Number of deleted feature values
        """
        logger.info(f"Deleting feature values for entity {entity_id}")
        return await self.repository.delete_feature_values_for_entity(entity_id, feature_version_ids)

    # Feature Group Assignment Methods
    async def add_feature_to_group(self, feature_id: int, feature_group_id: int) -> bool:
        """Add a feature to a feature group.

        Args:
            feature_id: ID of the feature
            feature_group_id: ID of the feature group

        Returns:
            True if successful, False if already associated
        """
        logger.info(f"Adding feature {feature_id} to group {feature_group_id}")
        return await self.repository.add_feature_to_group(feature_id, feature_group_id)

    async def remove_feature_from_group(self, feature_id: int, feature_group_id: int) -> bool:
        """Remove a feature from a feature group.

        Args:
            feature_id: ID of the feature
            feature_group_id: ID of the feature group

        Returns:
            True if removed, False if not associated
        """
        logger.info(f"Removing feature {feature_id} from group {feature_group_id}")
        return await self.repository.remove_feature_from_group(feature_id, feature_group_id)

    async def get_feature_groups_for_feature(self, feature_id: int) -> List[FeatureGroup]:
        """Get all feature groups that a feature belongs to.

        Args:
            feature_id: ID of the feature

        Returns:
            List of feature groups
        """
        logger.debug(f"Getting feature groups for feature {feature_id}")
        return await self.repository.get_feature_groups_for_feature(feature_id)

    async def get_features_in_group(self, feature_group_id: int) -> List[Feature]:
        """Get all features that belong to a feature group.

        Args:
            feature_group_id: ID of the feature group

        Returns:
            List of features
        """
        logger.debug(f"Getting features in group {feature_group_id}")
        return await self.repository.get_features_in_group(feature_group_id)

    # Feature Registration Method
    async def register_feature(
        self,
        registration_request: FeatureRegistrationRequest
    ) -> tuple[Feature, FeatureVersion, List[FeatureGroup]]:
        """Register a new feature with initial version and associate with feature groups.

        Args:
            registration_request: Feature registration request data

        Returns:
            Tuple of (feature, feature_version, feature_groups)
        """
        logger.info(f"Registering new feature: {registration_request.feature.name}")

        # Prepare feature data
        feature_data = registration_request.feature.dict()

        # Prepare feature version data
        version_data = registration_request.version.dict()
        # Remove feature_id from version data as it will be set after feature creation
        version_data.pop('feature_id', None)

        # Get feature group names
        feature_group_names = registration_request.feature_group_names

        # Call repository method to handle the transaction
        return await self.repository.register_feature(
            feature_data, version_data, feature_group_names
        )

    # Feature Retrieval Methods
    async def get_features_for_entities(
        self,
        entity_ids: List[str],
        feature_names: List[str],
        timestamp: Optional[datetime] = None
    ) -> List[dict]:
        """Get feature values for multiple entities and features.

        Args:
            entity_ids: List of entity IDs
            feature_names: List of feature names to retrieve
            timestamp: Optional timestamp to get values at (latest if not specified)

        Returns:
            List of dictionaries containing feature values for each entity
        """
        logger.info(f"Getting features for {len(entity_ids)} entities and {len(feature_names)} features")

        # Get features by name
        features = []
        for feature_name in feature_names:
            feature = await self.get_feature_by_name(feature_name)
            if feature:
                features.append(feature)
            else:
                logger.warning(f"Feature not found: {feature_name}")

        if not features:
            return []

        # Get feature IDs
        feature_ids = [f.id for f in features]

        # Get latest active version for each feature
        feature_versions = []
        for feature in features:
            latest_version = await self.get_latest_feature_version(feature.id)
            if latest_version:
                feature_versions.append(latest_version)

        if not feature_versions:
            return []

        # Get feature version IDs
        feature_version_ids = [fv.id for fv in feature_versions]

        # Get feature values
        feature_values = await self.get_feature_values_batch(
            entity_ids, feature_version_ids, timestamp
        )

        # Organize results by entity
        results = []
        entity_results = {}

        # Group feature values by entity
        for fv in feature_values:
            if fv.entity_id not in entity_results:
                entity_results[fv.entity_id] = {}
            entity_results[fv.entity_id][fv.feature_version_id] = fv.value

        # Build response for each entity
        for entity_id in entity_ids:
            if entity_id in entity_results:
                features_dict = {}
                # Map feature version IDs back to feature names
                fv_id_to_feature = {fv.id: f.name for f, fv in zip(features, feature_versions)}
                for fv_id, value in entity_results[entity_id].items():
                    if fv_id in fv_id_to_feature:
                        features_dict[fv_id_to_feature[fv_id]] = value

                results.append({
                    "entity_id": entity_id,
                    "timestamp": timestamp or datetime.utcnow(),
                    "features": features_dict
                })
            else:
                # Entity not found for any features
                results.append({
                    "entity_id": entity_id,
                    "timestamp": timestamp or datetime.utcnow(),
                    "features": {}
                })

        return results

    # Health check method
    async def health_check(self) -> dict:
        """Check the health of the feature store service.

        Returns:
            Dictionary with health status
        """
        try:
            # Try a simple database operation
            async for session in self.repository.get_async_session():
                await session.execute("SELECT 1")
                break
            return {"status": "healthy", "service": "feature-store", "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {"status": "unhealthy", "service": "feature-store", "error": str(e), "timestamp": datetime.utcnow().isoformat()}