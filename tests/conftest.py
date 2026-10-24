import pytest

from app.repository import InMemoryRepository
from app.services import StartupOpsService


@pytest.fixture
def repo():
    return InMemoryRepository()


@pytest.fixture
def service(repo):
    return StartupOpsService(repo)
