"""Shared pytest fixtures for ACF validation tests."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SEED_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "verified"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def seed_data_dir():
    return SEED_DATA_DIR
