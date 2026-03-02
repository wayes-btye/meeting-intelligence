import pytest
from fastapi.testclient import TestClient

from src.api.main import app

# Fixed test user ID used across all tests that need auth bypass.
TEST_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    """Bypass JWT auth for all tests by default.

    Tests that specifically test authentication (test_auth.py) must revert
    this override by clearing it within their own scope.  All other tests
    proceed as if a user with TEST_USER_ID is always authenticated, matching
    the pre-#71 behaviour where no auth was required.
    """
    from src.api.auth import get_current_user_id

    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
