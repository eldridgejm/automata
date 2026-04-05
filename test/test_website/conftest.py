"""Shared fixtures for website tests."""

import pathlib

import pytest
from utils.sitebuilder import SiteBuilder


@pytest.fixture
def tmpsite(tmp_path) -> SiteBuilder:
    """Provide a SiteBuilder instance in a temporary directory."""
    return SiteBuilder(pathlib.Path(tmp_path))
