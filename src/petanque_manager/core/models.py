"""Domain models for pétanque tournament management.

This module defines the core Pydantic models representing the domain entities.
These models are separate from persistence models for clean architecture.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TournamentMode(str, Enum):
    """Tournament mode: TRIPLETTE or DOUBLETTE priority."""

    TRIPLETTE = "Triplette"
    DOUBLETTE = "Doublette"


class MatchFormat(str, Enum):
    """Match format: triplette (3v3), doublette (2v2), or hybrid (3v2)."""

    TRIPLETTE = "Triplette"
    DOUBLETTE = "Doublette"
    HYBRID = "Hybride (3v2)"


class PlayerRole(str, Enum):
    """Player roles in pétanque."""

    TIREUR = "Tireur"  # Shooter
    POINTEUR = "Pointeur"  # Pointer
    MILIEU = "Milieu"  # Middle player


class StorageBackend(str, Enum):
    """Storage backend type."""

    SQLMODEL = "SQLMODEL"
    JSON = "JSON"


class Player(BaseModel):
    """Represents a player in the tournament."""

    id: int | None = None
    name: str = Field(..., min_length=1, max_length=100)
    roles: list[PlayerRole] = Field(..., min_length=1)
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and normalize player name."""
        return v.strip()

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[PlayerRole]) -> list[PlayerRole]:
        """Validate roles list."""
        if not v:
            raise ValueError("Player must have at least one role")
        # Remove duplicates while preserving order
        seen: set[PlayerRole] = set()
        unique_roles: list[PlayerRole] = []
        for role in v:
            if role not in seen:
                seen.add(role)
                unique_roles.append(role)
        return unique_roles

    def __str__(self) -> str:
        """Return string representation."""
        roles_str = ", ".join(role.value for role in self.roles)
        return f"{self.name} ({roles_str})"


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
        size_a = len(self.team_a_player_ids)
        size_b = len(self.team_b_player_ids)

        if self.format == MatchFormat.TRIPLETTE:
            # Both teams must be 3 players
            if size_a != 3 or size_b != 3:
                raise ValueError(f"Triplette format requires 3v3, got {size_a}v{size_b}")
        elif self.format == MatchFormat.DOUBLETTE:
            # Both teams must be 2 players
            if size_a != 2 or size_b != 2:
                raise ValueError(f"Doublette format requires 2v2, got {size_a}v{size_b}")
        elif self.format == MatchFormat.HYBRID:
            # One team 3, one team 2 (order doesn't matter)
            if not ((size_a == 3 and size_b == 2) or (size_a == 2 and size_b == 3)):
                raise ValueError(f"Hybrid format requires 3v2 or 2v3, got {size_a}v{size_b}")

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
    roles: list[PlayerRole]
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
    """Required player counts by role for a given mode and player count.

    Note: With multiple roles per player, these represent the number of players
    who SHOULD be able to play each role (i.e., have it in their roles list).
    """

    mode: TournamentMode
    total_players: int
    tireur_needed: int  # Players who can play TIREUR
    pointeur_needed: int  # Players who can play POINTEUR
    milieu_needed: int  # Players who can play MILIEU
    triplette_count: int  # Number of triplette teams
    doublette_count: int  # Number of doublette teams
    hybrid_count: int = 0  # Number of hybrid matches (3v2)

    @property
    def total_needed(self) -> int:
        """Get total needed players (sum of all team members)."""
        return self.triplette_count * 3 + self.doublette_count * 2
