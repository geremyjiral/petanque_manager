"""SQLModel storage backend using SQLite."""

import json
from datetime import datetime

import streamlit as st
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from src.petanque_manager.core.models import (
    Match,
    MatchFormat,
    Player,
    PlayerRole,
    Round,
    StorageBackend,
    TournamentConfig,
    TournamentMode,
)
from src.petanque_manager.infra.storage import TournamentStorage

SQLModel.__table_args__ = {"extend_existing": True}


# Database models (SQLModel ORM)
class PlayerDB(SQLModel, table=True):
    """Player database model."""

    __tablename__ = "players"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    roles: str  # Store as JSON string
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)


class MatchDB(SQLModel, table=True):
    """Match database model."""

    __tablename__ = "matches"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    round_id: int = Field(foreign_key="rounds.id", index=True)
    round_index: int = Field(index=True)
    terrain_label: str
    format: str  # Store as string
    team_a_player_ids: str  # Store as JSON string
    team_b_player_ids: str  # Store as JSON string
    score_a: int | None = None
    score_b: int | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class RoundDB(SQLModel, table=True):
    """Round database model."""

    __tablename__ = "rounds"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    index: int = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.now)


class ConfigDB(SQLModel, table=True):
    """Tournament configuration database model."""

    __tablename__ = "config"  # pyright: ignore[reportAssignmentType]

    id: int = Field(default=1, primary_key=True)  # Always use id=1 (single row)
    mode: str
    rounds_count: int
    terrains_count: int
    seed: int | None = None
    storage_backend: str
    db_path: str
    json_path: str


class SQLModelStorage(TournamentStorage):
    """SQLModel storage implementation using SQLite."""

    def __init__(self, db_path: str = "tournament.db"):
        """Initialize storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        if "db" in st.secrets:
            self.engine = create_engine(st.secrets["db"]["database_url"])
        else:
            self.engine = create_engine(f"sqlite:///{db_path}")

    def initialize(self) -> None:
        """Initialize database tables."""
        SQLModel.metadata.create_all(self.engine)

    def save_config(self, config: TournamentConfig) -> None:
        """Save tournament configuration."""
        with Session(self.engine) as session:
            # Delete existing config
            existing = session.get(ConfigDB, 1)
            if existing:
                session.delete(existing)

            # Create new config
            config_db = ConfigDB(
                id=1,
                mode=config.mode.value,
                rounds_count=config.rounds_count,
                terrains_count=config.terrains_count,
                seed=config.seed,
                storage_backend=config.storage_backend.value,
                db_path=config.db_path,
                json_path=config.json_path,
            )
            session.add(config_db)
            session.commit()

    def load_config(self) -> TournamentConfig | None:
        """Load tournament configuration."""
        with Session(self.engine) as session:
            config_db = session.get(ConfigDB, 1)
            if not config_db:
                return None

            return TournamentConfig(
                mode=TournamentMode(config_db.mode),
                rounds_count=config_db.rounds_count,
                terrains_count=config_db.terrains_count,
                seed=config_db.seed,
                storage_backend=StorageBackend(config_db.storage_backend),
                db_path=config_db.db_path,
                json_path=config_db.json_path,
            )

    def add_player(self, player: Player) -> Player:
        """Add a new player."""
        with Session(self.engine) as session:
            # Check for duplicate name
            existing = session.exec(select(PlayerDB).where(PlayerDB.name == player.name)).first()
            if existing:
                raise ValueError(f"Player with name '{player.name}' already exists")

            player_db = PlayerDB(
                name=player.name,
                roles=json.dumps([role.value for role in player.roles]),
                active=player.active,
                created_at=player.created_at,
            )
            session.add(player_db)
            session.commit()
            session.refresh(player_db)

            # Return domain model
            return Player(
                id=player_db.id,
                name=player_db.name,
                roles=[PlayerRole(role) for role in player_db.roles],
                active=player_db.active,
                created_at=player_db.created_at,
            )

    def get_player(self, player_id: int) -> Player | None:
        """Get a player by ID."""
        with Session(self.engine) as session:
            player_db = session.get(PlayerDB, player_id)
            if not player_db:
                return None

            return Player(
                id=player_db.id,
                name=player_db.name,
                roles=[PlayerRole(role) for role in player_db.roles],
                active=player_db.active,
                created_at=player_db.created_at,
            )

    def get_all_players(self, active_only: bool = False) -> list[Player]:
        """Get all players."""
        with Session(self.engine) as session:
            query = select(PlayerDB)
            if active_only:
                query = query.where(PlayerDB.active == True)  # noqa: E712

            players_db = session.exec(query).all()

            return [
                Player(
                    id=p.id,
                    name=p.name,
                    roles=[PlayerRole(role) for role in p.roles],
                    active=p.active,
                    created_at=p.created_at,
                )
                for p in players_db
            ]

    def update_player(self, player: Player) -> Player:
        """Update an existing player."""
        if player.id is None:
            raise ValueError("Player must have an ID")

        with Session(self.engine) as session:
            player_db = session.get(PlayerDB, player.id)
            if not player_db:
                raise ValueError(f"Player with ID {player.id} not found")

            player_db.name = player.name
            player_db.roles = json.dumps([role.value for role in player.roles])
            player_db.active = player.active

            session.add(player_db)
            session.commit()
            session.refresh(player_db)

            return Player(
                id=player_db.id,
                name=player_db.name,
                roles=[PlayerRole(role) for role in player_db.roles],
                active=player_db.active,
                created_at=player_db.created_at,
            )

    def delete_player(self, player_id: int) -> None:
        """Delete a player."""
        with Session(self.engine) as session:
            player_db = session.get(PlayerDB, player_id)
            if not player_db:
                raise ValueError(f"Player with ID {player_id} not found")

            # Check if player has played any matches
            matches = session.exec(select(MatchDB)).all()
            for match in matches:
                team_a = json.loads(match.team_a_player_ids)
                team_b = json.loads(match.team_b_player_ids)
                if player_id in team_a or player_id in team_b:
                    raise ValueError(f"Cannot delete player {player_id}: has played matches")

            session.delete(player_db)
            session.commit()

    def add_round(self, round_obj: Round) -> Round:
        """Add a new round with its matches."""
        with Session(self.engine) as session:
            # Check for duplicate index
            existing = session.exec(select(RoundDB).where(RoundDB.index == round_obj.index)).first()
            if existing:
                raise ValueError(f"Round with index {round_obj.index} already exists")

            # Create round
            round_db = RoundDB(
                index=round_obj.index,
                created_at=round_obj.created_at,
            )
            session.add(round_db)
            session.commit()
            session.refresh(round_db)

            # Create matches
            matches: list[Match] = []
            for match in round_obj.matches:
                match_db = MatchDB(
                    round_id=round_db.id or 0,
                    round_index=round_obj.index,
                    terrain_label=match.terrain_label,
                    format=match.format.value,
                    team_a_player_ids=json.dumps(match.team_a_player_ids),
                    team_b_player_ids=json.dumps(match.team_b_player_ids),
                    score_a=match.score_a,
                    score_b=match.score_b,
                    created_at=match.created_at,
                )
                session.add(match_db)
                session.commit()
                session.refresh(match_db)

                matches.append(
                    Match(
                        id=match_db.id,
                        round_index=match_db.round_index,
                        terrain_label=match_db.terrain_label,
                        format=MatchFormat(match_db.format),
                        team_a_player_ids=json.loads(match_db.team_a_player_ids),
                        team_b_player_ids=json.loads(match_db.team_b_player_ids),
                        score_a=match_db.score_a,
                        score_b=match_db.score_b,
                        created_at=match_db.created_at,
                    )
                )

            return Round(
                id=round_db.id,
                index=round_db.index,
                matches=matches,
                created_at=round_db.created_at,
            )

    def get_round(self, round_id: int) -> Round | None:
        """Get a round by ID."""
        with Session(self.engine) as session:
            round_db = session.get(RoundDB, round_id)
            if not round_db:
                return None

            # Get matches
            matches_db = session.exec(select(MatchDB).where(MatchDB.round_id == round_id)).all()

            matches = [
                Match(
                    id=m.id,
                    round_index=m.round_index,
                    terrain_label=m.terrain_label,
                    format=MatchFormat(m.format),
                    team_a_player_ids=json.loads(m.team_a_player_ids),
                    team_b_player_ids=json.loads(m.team_b_player_ids),
                    score_a=m.score_a,
                    score_b=m.score_b,
                    created_at=m.created_at,
                )
                for m in matches_db
            ]

            return Round(
                id=round_db.id,
                index=round_db.index,
                matches=matches,
                created_at=round_db.created_at,
            )

    def get_round_by_index(self, round_index: int) -> Round | None:
        """Get a round by its index."""
        with Session(self.engine) as session:
            round_db = session.exec(select(RoundDB).where(RoundDB.index == round_index)).first()
            if not round_db:
                return None

            return self.get_round(round_db.id or 0)

    def get_all_rounds(self) -> list[Round]:
        """Get all rounds with their matches."""
        with Session(self.engine) as session:
            rounds_db = session.exec(select(RoundDB).order_by(col(RoundDB.index))).all()

            rounds: list[Round] = []
            for round_db in rounds_db:
                round_obj = self.get_round(round_db.id or 0)
                if round_obj:
                    rounds.append(round_obj)

            return rounds

    def update_match(self, match: Match) -> Match:
        """Update an existing match."""
        if match.id is None:
            raise ValueError("Match must have an ID")

        with Session(self.engine) as session:
            match_db = session.get(MatchDB, match.id)
            if not match_db:
                raise ValueError(f"Match with ID {match.id} not found")

            match_db.score_a = match.score_a
            match_db.score_b = match.score_b

            session.add(match_db)
            session.commit()
            session.refresh(match_db)

            return Match(
                id=match_db.id,
                round_index=match_db.round_index,
                terrain_label=match_db.terrain_label,
                format=MatchFormat(match_db.format),
                team_a_player_ids=json.loads(match_db.team_a_player_ids),
                team_b_player_ids=json.loads(match_db.team_b_player_ids),
                score_a=match_db.score_a,
                score_b=match_db.score_b,
                created_at=match_db.created_at,
            )

    def get_all_matches(self) -> list[Match]:
        """Get all matches from all rounds."""
        with Session(self.engine) as session:
            matches_db = session.exec(
                select(MatchDB).order_by(col(MatchDB.round_index), col(MatchDB.id))
            ).all()

            return [
                Match(
                    id=m.id,
                    round_index=m.round_index,
                    terrain_label=m.terrain_label,
                    format=MatchFormat(m.format),
                    team_a_player_ids=json.loads(m.team_a_player_ids),
                    team_b_player_ids=json.loads(m.team_b_player_ids),
                    score_a=m.score_a,
                    score_b=m.score_b,
                    created_at=m.created_at,
                )
                for m in matches_db
            ]

    def delete_all_rounds(self) -> None:
        """Delete all rounds and matches."""
        with Session(self.engine) as session:
            # Delete matches first
            matches = session.exec(select(MatchDB)).all()
            for match in matches:
                session.delete(match)

            # Delete rounds
            rounds = session.exec(select(RoundDB)).all()
            for round_obj in rounds:
                session.delete(round_obj)

            session.commit()

    def reset_tournament(self) -> None:
        """Reset entire tournament."""
        with Session(self.engine) as session:
            # Delete all matches
            matches = session.exec(select(MatchDB)).all()
            for match in matches:
                session.delete(match)

            # Delete all rounds
            rounds = session.exec(select(RoundDB)).all()
            for round_obj in rounds:
                session.delete(round_obj)

            # Delete all players
            players = session.exec(select(PlayerDB)).all()
            for player in players:
                session.delete(player)

            # Delete config
            config = session.get(ConfigDB, 1)
            if config:
                session.delete(config)

            session.commit()
