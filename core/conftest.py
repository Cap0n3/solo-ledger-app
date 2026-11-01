"""Project-wide pytest fixtures."""

from pathlib import Path

import pytest
from pytest_django.fixtures import Settings


@pytest.fixture(autouse=True)
def media_root(settings: Settings, tmp_path: Path) -> Path:
    """Keep files uploaded by tests out of the real media directory."""
    media_dir = tmp_path / "media"
    settings.MEDIA_ROOT = media_dir
    return media_dir
