"""Pytest configuration and shared fixtures."""

import pytest

from src.core.models import Player, PlayerRole


@pytest.fixture
def sample_players_triplette() -> list[Player]:
    """Create sample players for TRIPLETTE mode testing."""
    return [
        Player(id=1, name="T1", role=PlayerRole.TIREUR),
        Player(id=2, name="T2", role=PlayerRole.TIREUR),
        Player(id=3, name="T3", role=PlayerRole.TIREUR),
        Player(id=4, name="T4", role=PlayerRole.TIREUR),
        Player(id=5, name="P1", role=PlayerRole.POINTEUR),
        Player(id=6, name="P2", role=PlayerRole.POINTEUR),
        Player(id=7, name="P3", role=PlayerRole.POINTEUR),
        Player(id=8, name="P4", role=PlayerRole.POINTEUR),
        Player(id=9, name="M1", role=PlayerRole.MILIEU),
        Player(id=10, name="M2", role=PlayerRole.MILIEU),
        Player(id=11, name="M3", role=PlayerRole.MILIEU),
        Player(id=12, name="M4", role=PlayerRole.MILIEU),
    ]


@pytest.fixture
def sample_players_doublette() -> list[Player]:
    """Create sample players for DOUBLETTE mode testing."""
    return [
        Player(id=1, name="T1", role=PlayerRole.TIREUR),
        Player(id=2, name="T2", role=PlayerRole.TIREUR),
        Player(id=3, name="T3", role=PlayerRole.TIREUR),
        Player(id=4, name="T4", role=PlayerRole.TIREUR),
        Player(id=5, name="PM1", role=PlayerRole.POINTEUR_MILIEU),
        Player(id=6, name="PM2", role=PlayerRole.POINTEUR_MILIEU),
        Player(id=7, name="PM3", role=PlayerRole.POINTEUR_MILIEU),
        Player(id=8, name="PM4", role=PlayerRole.POINTEUR_MILIEU),
    ]


@pytest.fixture
def temp_db_path(tmp_path: object) -> str:
    """Create a temporary database path for testing."""
    return str(tmp_path) + "/test_tournament.db"  # type: ignore


@pytest.fixture
def temp_json_path(tmp_path: object) -> str:
    """Create a temporary JSON path for testing."""
    return str(tmp_path) + "/test_tournament.json"  # type: ignore
