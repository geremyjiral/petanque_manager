"""Domain models for pétanque tournament management.

This module defines the core Pydantic models representing the domain entities.
These models are separate from persistence models for clean architecture.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TournamentMode(str, Enum):
    """Tournament mode: TRIPLETTE or DOUBLETTE priority."""

    TRIPLETTE = "TRIPLETTE"
    DOUBLETTE = "DOUBLETTE"


class MatchFormat(str, Enum):
    """Match format: triplette (3v3) or doublette (2v2)."""

    TRIPLETTE = "TRIPLETTE"
    DOUBLETTE = "DOUBLETTE"


class PlayerRole(str, Enum):
    """Player roles in pétanque."""

    # Used in TRIPLETTE mode
    TIREUR = "TIREUR"  # Shooter
    POINTEUR = "POINTEUR"  # Pointer
    MILIEU = "MILIEU"  # Middle player

    # Used in DOUBLETTE mode (can also be used as fallback)
    POINTEUR_MILIEU = "POINTEUR_MILIEU"  # Combined pointer/middle role


class StorageBackend(str, Enum):
    """Storage backend type."""

    SQLMODEL = "SQLMODEL"
    JSON = "JSON"


class Player(BaseModel):
    """Represents a player in the tournament."""

    id: int | None = None
    name: str = Field(..., min_length=1, max_length=100)
    role: PlayerRole
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and normalize player name."""
        return v.strip()

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.name} ({self.role.value})"


class Team(BaseModel):
    """Represents a team in a match."""

    player_ids: list[int] = Field(..., min_length=2, max_length=3)
    format: MatchFormat

    @field_validator("player_ids")
    @classmethod
    def validate_player_count(cls, v: list[int]) -> list[int]:
        """Validate player count matches format."""
        # Note: format might not be available during validation
        # This check is supplementary; main validation is in Match
        if len(v) < 2 or len(v) > 3:
            raise ValueError("Team must have 2 or 3 players")
        return v


class Match(BaseModel):
    """Represents a match between two teams."""

    id: int | None = None
    round_index: int = Field(..., ge=0)
    terrain_label: str = Field(..., min_length=1, max_length=10)
    format: MatchFormat
    team_a_player_ids: list[int] = Field(..., min_length=2, max_length=3)
    team_b_player_ids: list[int] = Field(..., min_length=2, max_length=3)
    score_a: int | None = Field(default=None, ge=0, le=13)
    score_b: int | None = Field(default=None, ge=0, le=13)
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("team_a_player_ids", "team_b_player_ids")
    @classmethod
    def validate_team_size(cls, v: list[int]) -> list[int]:
        """Validate team size matches format."""
        # Will be validated more strictly when format is known
        if len(v) < 2 or len(v) > 3:
            raise ValueError("Team must have 2 or 3 players")
        if len(set(v)) != len(v):
            raise ValueError("Team cannot have duplicate players")
        return v

    def model_post_init(self, __context: object) -> None:
        """Validate after model creation."""
        # Check format matches team sizes
        expected_size = 3 if self.format == MatchFormat.TRIPLETTE else 2
        if len(self.team_a_player_ids) != expected_size:
            raise ValueError(
                f"Team A size {len(self.team_a_player_ids)} doesn't match format "
                f"{self.format.value} (expected {expected_size})"
            )
        if len(self.team_b_player_ids) != expected_size:
            raise ValueError(
                f"Team B size {len(self.team_b_player_ids)} doesn't match format "
                f"{self.format.value} (expected {expected_size})"
            )

        # Check no player plays against themselves
        all_players = set(self.team_a_player_ids + self.team_b_player_ids)
        if len(all_players) != len(self.team_a_player_ids) + len(self.team_b_player_ids):
            raise ValueError("A player cannot play against themselves")

    @property
    def is_complete(self) -> bool:
        """Check if match has been played (scores entered)."""
        return self.score_a is not None and self.score_b is not None

    @property
    def all_player_ids(self) -> list[int]:
        """Get all player IDs in this match."""
        return self.team_a_player_ids + self.team_b_player_ids


class Round(BaseModel):
    """Represents a round of matches."""

    id: int | None = None
    index: int = Field(..., ge=0)
    matches: list["Match"] = []
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def is_complete(self) -> bool:
        """Check if all matches in round are complete."""
        return all(match.is_complete for match in self.matches) if self.matches else False

    @property
    def total_players(self) -> int:
        """Get total number of unique players in this round."""
        player_ids: set[int] = set()
        for match in self.matches:
            player_ids.update(match.all_player_ids)
        return len(player_ids)


class TournamentConfig(BaseModel):
    """Tournament configuration."""

    mode: TournamentMode = TournamentMode.TRIPLETTE
    rounds_count: int = Field(default=3, ge=1, le=10)
    terrains_count: int = Field(default=8, ge=1, le=52)  # Support up to ZZ
    seed: int | None = None
    storage_backend: StorageBackend = StorageBackend.SQLMODEL

    # Database path (for SQLModel backend)
    db_path: str = "tournament.db"

    # JSON path (for JSON backend)
    json_path: str = "tournament_data.json"


class PlayerStats(BaseModel):
    """Statistics for a player."""

    player_id: int
    player_name: str
    role: PlayerRole
    matches_played: int = 0
    wins: int = 0
    losses: int = 0
    points_for: int = 0
    points_against: int = 0

    @property
    def goal_average(self) -> int:
        """Calculate goal average (points for - points against)."""
        return self.points_for - self.points_against

    @property
    def win_rate(self) -> float:
        """Calculate win rate as a percentage."""
        if self.matches_played == 0:
            return 0.0
        return (self.wins / self.matches_played) * 100


class ScheduleQualityReport(BaseModel):
    """Quality metrics for a generated schedule."""

    repeated_partners: int = 0  # Count of player pairs playing together >1 time
    repeated_opponents: int = 0  # Count of player pairs playing against each other >1 time
    repeated_terrains: int = 0  # Count of players playing on same terrain >1 time
    fallback_format_count: int = 0  # Count of matches in fallback format
    total_score: float = 0.0  # Lower is better

    @property
    def quality_grade(self) -> str:
        """Return a letter grade for schedule quality."""
        if self.total_score == 0:
            return "A+"
        elif self.total_score < 10:
            return "A"
        elif self.total_score < 25:
            return "B"
        elif self.total_score < 50:
            return "C"
        elif self.total_score < 100:
            return "D"
        else:
            return "F"


class RoleRequirements(BaseModel):
    """Required player counts by role for a given mode and player count."""

    mode: TournamentMode
    total_players: int
    tireur_needed: int
    pointeur_needed: int
    milieu_needed: int
    pointeur_milieu_needed: int

    @property
    def total_needed(self) -> int:
        """Get total needed players."""
        if self.mode == TournamentMode.TRIPLETTE:
            return self.tireur_needed + self.pointeur_needed + self.milieu_needed
        else:
            return self.tireur_needed + self.pointeur_milieu_needed
