"""
Feature Store Repository Implementation
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text, select, insert, update, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from ..shared.database import get_async_session
from ..shared.exceptions import DatabaseError
from .models import (
    FeatureGroup, Feature, FeatureVersion, FeatureValue, FeatureStatus,
    feature_group_feature
)

logger = logging.getLogger(__name__)


class FeatureStoreRepository:
    """Repository for feature store data access operations."""

    async def __init__(self):
        """Initialize the repository."""
        pass

    # Feature Group Methods
    async def create_feature_group(self, feature_group_data: dict) -> FeatureGroup:
        """Create a new feature group."""
        try:
            async for session in get_async_session():
                stmt = insert(FeatureGroup).values(**feature_group_data).returning(FeatureGroup)
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one()
        except Exception as e:
            logger.error(f"Error creating feature group: {str(e)}")
            raise DatabaseError(f"Failed to create feature group: {str(e)}")

    async def get_feature_group(self, feature_group_id: int) -> Optional[FeatureGroup]:
        """Get a feature group by ID."""
        try:
            async for session in get_async_session():
                query = select(FeatureGroup).where(FeatureGroup.id == feature_group_id)
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting feature group {feature_group_id}: {str(e)}")
            raise DatabaseError(f"Failed to get feature group: {str(e)}")

    async def get_feature_group_by_name(self, name: str) -> Optional[FeatureGroup]:
        """Get a feature group by name."""
        try:
            async for session in get_async_session():
                query = select(FeatureGroup).where(FeatureGroup.name == name)
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting feature group by name {name}: {str(e)}")
            raise DatabaseError(f"Failed to get feature group by name: {str(e)}")

    async def list_feature_groups(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False
    ) -> List[FeatureGroup]:
        """List feature groups with pagination."""
        try:
            async for session in get_async_session():
                query = select(FeatureGroup)
                if active_only:
                    query = query.where(FeatureGroup.is_active == True)
                query = query.offset(skip).limit(limit).order_by(FeatureGroup.created_at.desc())
                result = await session.execute(query)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error listing feature groups: {str(e)}")
            raise DatabaseError(f"Failed to list feature groups: {str(e)}")

    async def update_feature_group(
        self,
        feature_group_id: int,
        feature_group_data: dict
    ) -> Optional[FeatureGroup]:
        """Update a feature group."""
        try:
            async for session in get_async_session():
                # Add updated_at timestamp
                feature_group_data['updated_at'] = func.now()

                stmt = (
                    update(FeatureGroup)
                    .where(FeatureGroup.id == feature_group_id)
                    .values(**feature_group_data)
                    .returning(FeatureGroup)
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error updating feature group {feature_group_id}: {str(e)}")
            raise DatabaseError(f"Failed to update feature group: {str(e)}")

    async def delete_feature_group(self, feature_group_id: int) -> bool:
        """Delete a feature group (soft delete by setting is_active=False)."""
        try:
            async for session in get_async_session():
                stmt = (
                    update(FeatureGroup)
                    .where(FeatureGroup.id == feature_group_id)
                    .values(is_active=False, updated_at=func.now())
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting feature group {feature_group_id}: {str(e)}")
            raise DatabaseError(f"Failed to delete feature group: {str(e)}")

    # Feature Methods
    async def create_feature(self, feature_data: dict) -> Feature:
        """Create a new feature."""
        try:
            async for session in get_async_session():
                stmt = insert(Feature).values(**feature_data).returning(Feature)
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one()
        except Exception as e:
            logger.error(f"Error creating feature: {str(e)}")
            raise DatabaseError(f"Failed to create feature: {str(e)}")

    async def get_feature(self, feature_id: int) -> Optional[Feature]:
        """Get a feature by ID."""
        try:
            async for session in get_async_session():
                query = select(Feature).where(Feature.id == feature_id)
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting feature {feature_id}: {str(e)}")
            raise DatabaseError(f"Failed to get feature: {str(e)}")

    async def get_feature_by_name(self, name: str) -> Optional[Feature]:
        """Get a feature by name."""
        try:
            async for session in get_async_session():
                query = select(Feature).where(Feature.name == name)
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting feature by name {name}: {str(e)}")
            raise DatabaseError(f"Failed to get feature by name: {str(e)}")

    async def list_features(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
        feature_group_id: Optional[int] = None
    ) -> List[Feature]:
        """List features with pagination and optional filtering."""
        try:
            async for session in get_async_session():
                query = select(Feature)

                if active_only:
                    query = query.where(Feature.is_active == True)

                if feature_group_id is not None:
                    # Join with feature_group_feature association table
                    query = (
                        query
                        .join(feature_group_feature, Feature.id == feature_group_feature.c.feature_id)
                        .where(feature_group_feature.c.feature_group_id == feature_group_id)
                    )

                query = query.offset(skip).limit(limit).order_by(Feature.created_at.desc())
                result = await session.execute(query)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error listing features: {str(e)}")
            raise DatabaseError(f"Failed to list features: {str(e)}")

    async def update_feature(
        self,
        feature_id: int,
        feature_data: dict
    ) -> Optional[Feature]:
        """Update a feature."""
        try:
            async for session in get_async_session():
                # Add updated_at timestamp
                feature_data['updated_at'] = func.now()

                stmt = (
                    update(Feature)
                    .where(Feature.id == feature_id)
                    .values(**feature_data)
                    .returning(Feature)
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error updating feature {feature_id}: {str(e)}")
            raise DatabaseError(f"Failed to update feature: {str(e)}")

    async def delete_feature(self, feature_id: int) -> bool:
        """Delete a feature (soft delete by setting is_active=False)."""
        try:
            async for session in get_async_session():
                stmt = (
                    update(Feature)
                    .where(Feature.id == feature_id)
                    .values(is_active=False, updated_at=func.now())
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting feature {feature_id}: {str(e)}")
            raise DatabaseError(f"Failed to delete feature: {str(e)}")

    # Feature Version Methods
    async def create_feature_version(self, feature_version_data: dict) -> FeatureVersion:
        """Create a new feature version."""
        try:
            async for session in get_async_session():
                stmt = insert(FeatureVersion).values(**feature_version_data).returning(FeatureVersion)
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one()
        except Exception as e:
            logger.error(f"Error creating feature version: {str(e)}")
            raise DatabaseError(f"Failed to create feature version: {str(e)}")

    async def get_feature_version(self, feature_version_id: int) -> Optional[FeatureVersion]:
        """Get a feature version by ID."""
        try:
            async for session in get_async_session():
                query = select(FeatureVersion).where(FeatureVersion.id == feature_version_id)
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting feature version {feature_version_id}: {str(e)}")
            raise DatabaseError(f"Failed to get feature version: {str(e)}")

    async def get_feature_version_by_number(
        self,
        feature_id: int,
        version_number: int
    ) -> Optional[FeatureVersion]:
        """Get a feature version by feature ID and version number."""
        try:
            async for session in get_async_session():
                query = select(FeatureVersion).where(
                    and_(
                        FeatureVersion.feature_id == feature_id,
                        FeatureVersion.version_number == version_number
                    )
                )
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting feature version {feature_id} v{version_number}: {str(e)}")
            raise DatabaseError(f"Failed to get feature version: {str(e)}")

    async def list_feature_versions(
        self,
        feature_id: int,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False
    ) -> List[FeatureVersion]:
        """List versions for a specific feature."""
        try:
            async for session in get_async_session():
                query = select(FeatureVersion).where(FeatureVersion.feature_id == feature_id)

                if active_only:
                    query = query.where(FeatureVersion.is_active == True)

                query = (
                    query
                    .order_by(FeatureVersion.version_number.desc())
                    .offset(skip)
                    .limit(limit)
                )
                result = await session.execute(query)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error listing feature versions for feature {feature_id}: {str(e)}")
            raise DatabaseError(f"Failed to list feature versions: {str(e)}")

    async def get_latest_feature_version(self, feature_id: int) -> Optional[FeatureVersion]:
        """Get the latest active version of a feature."""
        try:
            async for session in get_async_session():
                query = (
                    select(FeatureVersion)
                    .where(
                        and_(
                            FeatureVersion.feature_id == feature_id,
                            FeatureVersion.is_active == True
                        )
                    )
                    .order_by(FeatureVersion.version_number.desc())
                    .limit(1)
                )
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting latest feature version for {feature_id}: {str(e)}")
            raise DatabaseError(f"Failed to get latest feature version: {str(e)}")

    async def update_feature_version(
        self,
        feature_version_id: int,
        feature_version_data: dict
    ) -> Optional[FeatureVersion]:
        """Update a feature version."""
        try:
            async for session in get_async_session():
                stmt = (
                    update(FeatureVersion)
                    .where(FeatureVersion.id == feature_version_id)
                    .values(**feature_version_data)
                    .returning(FeatureVersion)
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error updating feature version {feature_version_id}: {str(e)}")
            raise DatabaseError(f"Failed to update feature version: {str(e)}")

    async def delete_feature_version(self, feature_version_id: int) -> bool:
        """Delete a feature version (soft delete by setting is_active=False)."""
        try:
            async for session in get_async_session():
                stmt = (
                    update(FeatureVersion)
                    .where(FeatureVersion.id == feature_version_id)
                    .values(is_active=False)
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting feature version {feature_version_id}: {str(e)}")
            raise DatabaseError(f"Failed to delete feature version: {str(e)}")

    # Feature Value Methods
    async def create_feature_value(self, feature_value_data: dict) -> FeatureValue:
        """Create a new feature value."""
        try:
            async for session in get_async_session():
                stmt = insert(FeatureValue).values(**feature_value_data).returning(FeatureValue)
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one()
        except Exception as e:
            logger.error(f"Error creating feature value: {str(e)}")
            raise DatabaseError(f"Failed to create feature value: {str(e)}")

    async def create_feature_values_batch(self, feature_values_data: List[dict]) -> List[FeatureValue]:
        """Create multiple feature values in a batch."""
        try:
            async for session in get_async_session():
                stmt = insert(FeatureValue).values(feature_values_data).returning(FeatureValue)
                result = await session.execute(stmt)
                await session.commit()
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error creating feature values batch: {str(e)}")
            raise DatabaseError(f"Failed to create feature values batch: {str(e)}")

    async def get_feature_value(self, feature_value_id: int) -> Optional[FeatureValue]:
        """Get a feature value by ID."""
        try:
            async for session in get_async_session():
                query = select(FeatureValue).where(FeatureValue.id == feature_value_id)
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting feature value {feature_value_id}: {str(e)}")
            raise DatabaseError(f"Failed to get feature value: {str(e)}")

    async def get_feature_values_for_entity(
        self,
        entity_id: str,
        feature_version_ids: Optional[List[int]] = None,
        start_time: Optional[Any] = None,
        end_time: Optional[Any] = None,
        limit: int = 1000
    ) -> List[FeatureValue]:
        """Get feature values for a specific entity."""
        try:
            async for session in get_async_session():
                query = select(FeatureValue).where(FeatureValue.entity_id == entity_id)

                if feature_version_ids:
                    query = query.where(FeatureValue.feature_version_id.in_(feature_version_ids))

                if start_time:
                    query = query.where(FeatureValue.timestamp >= start_time)

                if end_time:
                    query = query.where(FeatureValue.timestamp <= end_time)

                query = query.order_by(FeatureValue.timestamp.desc()).limit(limit)
                result = await session.execute(query)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting feature values for entity {entity_id}: {str(e)}")
            raise DatabaseError(f"Failed to get feature values for entity: {str(e)}")

    async def get_latest_feature_value(
        self,
        entity_id: str,
        feature_version_id: int
    ) -> Optional[FeatureValue]:
        """Get the latest feature value for an entity and feature version."""
        try:
            async for session in get_async_session():
                query = (
                    select(FeatureValue)
                    .where(
                        and_(
                            FeatureValue.entity_id == entity_id,
                            FeatureValue.feature_version_id == feature_version_id
                        )
                    )
                    .order_by(FeatureValue.timestamp.desc())
                    .limit(1)
                )
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting latest feature value for entity {entity_id}, feature version {feature_version_id}: {str(e)}")
            raise DatabaseError(f"Failed to get latest feature value: {str(e)}")

    async def get_feature_values_batch(
        self,
        entity_ids: List[str],
        feature_version_ids: List[int],
        timestamp: Optional[Any] = None
    ) -> List[FeatureValue]:
        """Get feature values for multiple entities and feature versions."""
        try:
            async for session in get_async_session():
                query = select(FeatureValue).where(
                    and_(
                        FeatureValue.entity_id.in_(entity_ids),
                        FeatureValue.feature_version_id.in_(feature_version_ids)
                    )
                )

                if timestamp:
                    # For a specific timestamp, we want the closest value at or before that timestamp
                    # This is a simplified version - in production you might want more complex logic
                    query = query.where(FeatureValue.timestamp <= timestamp)

                query = query.order_by(
                    FeatureValue.entity_id,
                    FeatureValue.feature_version_id,
                    FeatureValue.timestamp.desc()
                )
                result = await session.execute(query)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting feature values batch: {str(e)}")
            raise DatabaseError(f"Failed to get feature values batch: {str(e)}")

    async def delete_feature_values_for_entity(
        self,
        entity_id: str,
        feature_version_ids: Optional[List[int]] = None
    ) -> int:
        """Delete feature values for an entity."""
        try:
            async for session in get_async_session():
                query = delete(FeatureValue).where(FeatureValue.entity_id == entity_id)

                if feature_version_ids:
                    query = query.where(FeatureValue.feature_version_id.in_(feature_version_ids))

                result = await session.execute(query)
                await session.commit()
                return result.rowcount
        except Exception as e:
            logger.error(f"Error deleting feature values for entity {entity_id}: {str(e)}")
            raise DatabaseError(f"Failed to delete feature values for entity: {str(e)}")

    # Feature Group Assignment Methods
    async def add_feature_to_group(self, feature_id: int, feature_group_id: int) -> bool:
        """Add a feature to a feature group."""
        try:
            async for session in get_async_session():
                # Check if the association already exists
                check_query = select(feature_group_feature).where(
                    and_(
                        feature_group_feature.c.feature_id == feature_id,
                        feature_group_feature.c.feature_group_id == feature_group_id
                    )
                )
                existing = await session.execute(check_query)
                if existing.fetchone():
                    # Already associated
                    return True

                # Insert the association
                stmt = insert(feature_group_feature).values(
                    feature_id=feature_id,
                    feature_group_id=feature_group_id
                )
                await session.execute(stmt)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding feature {feature_id} to group {feature_group_id}: {str(e)}")
            raise DatabaseError(f"Failed to add feature to group: {str(e)}")

    async def remove_feature_from_group(self, feature_id: int, feature_group_id: int) -> bool:
        """Remove a feature from a feature group."""
        try:
            async for session in get_async_session():
                stmt = delete(feature_group_feature).where(
                    and_(
                        feature_group_feature.c.feature_id == feature_id,
                        feature_group_feature.c.feature_group_id == feature_group_id
                    )
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing feature {feature_id} from group {feature_group_id}: {str(e)}")
            raise DatabaseError(f"Failed to remove feature from group: {str(e)}")

    async def get_feature_groups_for_feature(self, feature_id: int) -> List[FeatureGroup]:
        """Get all feature groups that a feature belongs to."""
        try:
            async for session in get_async_session():
                query = (
                    select(FeatureGroup)
                    .join(feature_group_feature, FeatureGroup.id == feature_group_feature.c.feature_group_id)
                    .where(feature_group_feature.c.feature_id == feature_id)
                )
                result = await session.execute(query)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting feature groups for feature {feature_id}: {str(e)}")
            raise DatabaseError(f"Failed to get feature groups for feature: {str(e)}")

    async def get_features_in_group(self, feature_group_id: int) -> List[Feature]:
        """Get all features that belong to a feature group."""
        try:
            async for session in get_async_session():
                query = (
                    select(Feature)
                    .join(feature_group_feature, Feature.id == feature_group_feature.c.feature_id)
                    .where(feature_group_feature.c.feature_group_id == feature_group_id)
                )
                result = await session.execute(query)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting features in group {feature_group_id}: {str(e)}")
            raise DatabaseError(f"Failed to get features in group: {str(e)}")

    # Feature Registration Method (combined operation)
    async def register_feature(
        self,
        feature_data: dict,
        feature_version_data: dict,
        feature_group_names: List[str]
    ) -> tuple[Feature, FeatureVersion, List[FeatureGroup]]:
        """Register a new feature with initial version and associate with feature groups."""
        try:
            async for session in get_async_session():
                # Start a transaction
                # Create feature
                feature_stmt = insert(Feature).values(**feature_data).returning(Feature)
                feature_result = await session.execute(feature_stmt)
                feature = feature_result.scalar_one()

                # Create feature version
                feature_version_data['feature_id'] = feature.id
                version_stmt = insert(FeatureVersion).values(**feature_version_data).returning(FeatureVersion)
                version_result = await session.execute(version_stmt)
                feature_version = version_result.scalar_one()

                # Get or create feature groups and associate them
                feature_groups = []
                for group_name in feature_group_names:
                    # Try to get existing group
                    group_query = select(FeatureGroup).where(FeatureGroup.name == group_name)
                    group_result = await session.execute(group_query)
                    group = group_result.scalar_one_or_none()

                    if not group:
                        # Create new group
                        group_data = {
                            "name": group_name,
                            "description": f"Auto-created group for {group_name}",
                            "is_active": True
                        }
                        group_stmt = insert(FeatureGroup).values(**group_data).returning(FeatureGroup)
                        group_result = await session.execute(group_stmt)
                        group = group_result.scalar_one()

                    feature_groups.append(group)

                    # Associate feature with group
                    assoc_stmt = insert(feature_group_feature).values(
                        feature_id=feature.id,
                        feature_group_id=group.id
                    )
                    await session.execute(assoc_stmt)

                await session.commit()
                return feature, feature_version, feature_groups

        except Exception as e:
            logger.error(f"Error registering feature: {str(e)}")
            raise DatabaseError(f"Failed to register feature: {str(e)}")