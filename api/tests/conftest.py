import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    return pool

@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.xread = AsyncMock(return_value=[])
    return r
