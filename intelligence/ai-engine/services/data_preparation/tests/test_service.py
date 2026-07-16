"""
Tests for the Data Preparation service
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from ai_engine.services.data_preparation.service import DataPreparationService
from ai_engine.services.data_preparation.repository import DataPreparationRepository


@pytest.mark.asyncio
async def test_data_preparation_service_initialization():
    """Test that DataPreparationService can be initialized."""
    # Mock dependencies
    mock_repository = AsyncMock(spec=DataPreparationRepository)

    # Initialize service
    service = DataPreparationService(repository=mock_repository)

    # Assertions
    assert service is not None
    assert service.repository == mock_repository


@pytest.mark.asyncio
async def test_data_preparation_service_prepare_data():
    """Test that prepare_data method works correctly."""
    # Mock dependencies
    mock_repository = AsyncMock(spec=DataPreparationRepository)
    mock_repository.get_raw_data.return_value = [
        {"id": 1, "value": "test data 1"},
        {"id": 2, "value": "test data 2"}
    ]

    # Initialize service
    service = DataPreparationService(repository=mock_repository)

    # Call method
    result = await service.prepare_data(source="test_source")

    # Assertions
    assert result is not None
    assert len(result) == 2
    mock_repository.get_raw_data.assert_called_once_with(source="test_source")