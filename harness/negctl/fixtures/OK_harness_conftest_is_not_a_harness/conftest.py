import pytest


@pytest.fixture
def db():
    print('connecting')
    return object()
