"""
Simple test to verify FeatureStoreService can be imported and instantiated
"""
from ai_engine.services.feature_store.service import FeatureStoreService
from ai_engine.services.feature_store.repository import FeatureStoreRepository


def test_imports_work():
    """Test that we can import the service and repository."""
    assert FeatureStoreService is not None
    assert FeatureStoreRepository is not None


def test_service_can_be_instantiated():
    """Test that we can instantiate the service with a mock repository."""
    # Create a mock repository
    class MockRepository:
        async def get_raw_data(self, source):
            return []
        async def save_prepared_data(self, data, destination):
            return True
        async def get_prepared_data(self, destination):
            return []

    # Instantiate service
    repository = MockRepository()
    service = FeatureStoreService(repository=repository)

    assert service is not None
    assert service.repository == repository


if __name__ == "__main__":
    test_imports_work()
    test_service_can_be_instantiated()
    print("All tests passed!")