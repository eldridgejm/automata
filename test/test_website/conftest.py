"""Shared fixtures for website tests."""

import pathlib

import pytest
from utils.sitebuilder import SiteBuilder


@pytest.fixture
def tmpsite(tmp_path) -> SiteBuilder:
    """Provide a SiteBuilder instance in a temporary directory.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest's temporary directory fixture.

    Returns
    -------
    SiteBuilder
        A SiteBuilder instance configured in the temporary directory.

    """
    return SiteBuilder(pathlib.Path(tmp_path))
