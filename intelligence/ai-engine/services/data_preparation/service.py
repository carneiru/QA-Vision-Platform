"""
Data Preparation Service Implementation
"""
from typing import List, Dict, Any, Optional
import logging

from .repository import DataPreparationRepository


logger = logging.getLogger(__name__)


class DataPreparationService:
    """Service for preparing data for machine learning pipelines."""

    def __init__(self, repository: DataPreparationRepository):
        """Initialize the data preparation service.

        Args:
            repository: Repository for data access operations
        """
        self.repository = repository

    async def prepare_data(self, source: str, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Prepare data from a source for machine learning consumption.

        Args:
            source: Identifier for the data source
            config: Optional configuration for data preparation

        Returns:
            List of prepared data dictionaries
        """
        logger.info(f"Preparing data from source: {source}")

        # Get raw data
        raw_data = await self.repository.get_raw_data(source=source)

        # Apply basic cleaning and transformation
        prepared_data = []
        for record in raw_data:
            # Skip empty records
            if not record:
                continue

            # Basic cleaning: remove None values and empty strings
            cleaned_record = {}
            for key, value in record.items():
                if value is not None and value != "":
                    cleaned_record[key] = str(value).strip() if isinstance(value, str) else value

            if cleaned_record:  # Only add if there's data left after cleaning
                prepared_data.append(cleaned_record)

        logger.info(f"Prepared {len(prepared_data)} records from {len(raw_data)} raw records")
        return prepared_data

    async def validate_data_quality(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate the quality of prepared data.

        Args:
            data: List of data dictionaries to validate

        Returns:
            Dictionary containing validation metrics
        """
        if not data:
            return {
                "total_records": 0,
                "valid_records": 0,
                "completeness_score": 0.0,
                "issues": ["No data to validate"]
            }

        total_records = len(data)
        valid_records = 0
        issues = []

        for i, record in enumerate(data):
            # Basic validation: record should not be empty
            if not record:
                issues.append(f"Record {i} is empty")
                continue

            # Check for completely null/empty values
            has_meaningful_data = any(
                v is not None and v != "" and v != [] and v != {}
                for v in record.values()
            )

            if has_meaningful_data:
                valid_records += 1
            else:
                issues.append(f"Record {i} has no meaningful data")

        completeness_score = (valid_records / total_records) * 100 if total_records > 0 else 0.0

        return {
            "total_records": total_records,
            "valid_records": valid_records,
            "completeness_score": round(completeness_score, 2),
            "issues": issues[:10]  # Limit to first 10 issues
        }