"""JSON file storage backend (fallback option)."""

import json
from pathlib import Path
from typing import Any

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


class JSONStorage(TournamentStorage):
    """JSON file storage implementation."""

    def __init__(self, json_path: str = "tournament_data.json"):
        """Initialize storage.

        Args:
            json_path: Path to JSON file
        """
        self.json_path = Path(json_path)
        self.data: dict[str, Any] = {
            "config": None,
            "players": [],
            "rounds": [],
            "next_player_id": 1,
            "next_round_id": 1,
            "next_match_id": 1,
        }

    def initialize(self) -> None:
        """Initialize storage (load from file if exists)."""
        if self.json_path.exists():
            with open(self.json_path) as f:
                self.data = json.load(f)
        else:
            self._save()

    def _save(self) -> None:
        """Save data to JSON file."""
        with open(self.json_path, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    def save_config(self, config: TournamentConfig) -> None:
        """Save tournament configuration."""
        self.data["config"] = {
            "mode": config.mode.value,
            "rounds_count": config.rounds_count,
            "terrains_count": config.terrains_count,
            "seed": config.seed,
            "storage_backend": config.storage_backend.value,
            "db_path": config.db_path,
            "json_path": config.json_path,
        }
        self._save()

    def load_config(self) -> TournamentConfig | None:
        """Load tournament configuration."""
        config_data = self.data.get("config")
        if not config_data:
            return None

        return TournamentConfig(
            mode=TournamentMode(config_data["mode"]),
            rounds_count=config_data["rounds_count"],
            terrains_count=config_data["terrains_count"],
            seed=config_data.get("seed"),
            storage_backend=StorageBackend(config_data["storage_backend"]),
            db_path=config_data["db_path"],
            json_path=config_data["json_path"],
        )

    def add_player(self, player: Player) -> Player:
        """Add a new player."""
        # Check for duplicate name
        for p in self.data["players"]:
            if p["name"] == player.name and not p.get("deleted", False):
                raise ValueError(f"Player with name '{player.name}' already exists")

        player_id = self.data["next_player_id"]
        self.data["next_player_id"] += 1

        player_data: dict[str, Any] = {
            "id": player_id,
            "name": player.name,
            "roles": [role.value for role in player.roles],
            "active": player.active,
            "created_at": player.created_at.isoformat(),
        }
        self.data["players"].append(player_data)
        self._save()

        return Player(
            id=player_id,
            name=player.name,
            roles=player.roles,
            active=player.active,
            created_at=player.created_at,
        )

    def get_player(self, player_id: int) -> Player | None:
        """Get a player by ID."""
        for p in self.data["players"]:
            if p["id"] == player_id and not p.get("deleted", False):
                # Handle both old format (single role) and new format (multiple roles)
                if "roles" in p:
                    roles = [PlayerRole(role) for role in p["roles"]]
                else:
                    # Backwards compatibility: convert old single role to list
                    roles = [PlayerRole(p["role"])]

                return Player(
                    id=p["id"],
                    name=p["name"],
                    roles=roles,
                    active=p["active"],
                    created_at=p["created_at"],
                )
        return None

    def get_all_players(self, active_only: bool = False) -> list[Player]:
        """Get all players."""
        players: list[Player] = []
        for p in self.data["players"]:
            if p.get("deleted", False):
                continue
            if active_only and not p["active"]:
                continue

            # Handle both old format (single role) and new format (multiple roles)
            if "roles" in p:
                roles = [PlayerRole(role) for role in p["roles"]]
            else:
                # Backwards compatibility: convert old single role to list
                roles = [PlayerRole(p["role"])]

            players.append(
                Player(
                    id=p["id"],
                    name=p["name"],
                    roles=roles,
                    active=p["active"],
                    created_at=p["created_at"],
                )
            )
        return players

    def update_player(self, player: Player) -> Player:
        """Update an existing player."""
        if player.id is None:
            raise ValueError("Player must have an ID")

        for p in self.data["players"]:
            if p["id"] == player.id and not p.get("deleted", False):
                p["name"] = player.name
                p["roles"] = [role.value for role in player.roles]
                # Remove old single role field if it exists
                p.pop("role", None)
                p["active"] = player.active
                self._save()

                return Player(
                    id=p["id"],
                    name=p["name"],
                    roles=player.roles,
                    active=p["active"],
                    created_at=p["created_at"],
                )

        raise ValueError(f"Player with ID {player.id} not found")

    def delete_player(self, player_id: int) -> None:
        """Delete a player."""
        # Check if player exists
        player_found = False
        for p in self.data["players"]:
            if p["id"] == player_id and not p.get("deleted", False):
                player_found = True
                break

        if not player_found:
            raise ValueError(f"Player with ID {player_id} not found")

        # Check if player has played any matches
        for round_data in self.data["rounds"]:
            for match in round_data["matches"]:
                if (
                    player_id in match["team_a_player_ids"]
                    or player_id in match["team_b_player_ids"]
                ):
                    raise ValueError(f"Cannot delete player {player_id}: has played matches")

        # Mark as deleted
        for p in self.data["players"]:
            if p["id"] == player_id:
                p["deleted"] = True
                break

        self._save()

    def add_round(self, round_obj: Round) -> Round:
        """Add a new round with its matches."""
        # Check for duplicate index
        for r in self.data["rounds"]:
            if r["index"] == round_obj.index:
                raise ValueError(f"Round with index {round_obj.index} already exists")

        round_id = self.data["next_round_id"]
        self.data["next_round_id"] += 1

        matches_data: list[dict[str, Any]] = []
        for match in round_obj.matches:
            match_id = self.data["next_match_id"]
            self.data["next_match_id"] += 1

            match_data: dict[str, Any] = {
                "id": match_id,
                "round_index": round_obj.index,
                "terrain_label": match.terrain_label,
                "format": match.format.value,
                "team_a_player_ids": match.team_a_player_ids,
                "team_b_player_ids": match.team_b_player_ids,
                "score_a": match.score_a,
                "score_b": match.score_b,
                "created_at": match.created_at.isoformat(),
            }
            matches_data.append(match_data)

        round_data: dict[str, Any] = {
            "id": round_id,
            "index": round_obj.index,
            "matches": matches_data,
            "created_at": round_obj.created_at.isoformat(),
        }

        self.data["rounds"].append(round_data)
        self._save()

        # Return with IDs populated
        matches = [
            Match(
                id=m["id"],
                round_index=m["round_index"],
                terrain_label=m["terrain_label"],
                format=MatchFormat(m["format"]),
                team_a_player_ids=m["team_a_player_ids"],
                team_b_player_ids=m["team_b_player_ids"],
                score_a=m["score_a"],
                score_b=m["score_b"],
                created_at=m["created_at"],
            )
            for m in matches_data
        ]

        return Round(
            id=round_id,
            index=round_obj.index,
            matches=matches,
            created_at=round_obj.created_at,
        )

    def get_round(self, round_id: int) -> Round | None:
        """Get a round by ID."""
        for r in self.data["rounds"]:
            if r["id"] == round_id:
                matches = [
                    Match(
                        id=m["id"],
                        round_index=m["round_index"],
                        terrain_label=m["terrain_label"],
                        format=MatchFormat(m["format"]),
                        team_a_player_ids=m["team_a_player_ids"],
                        team_b_player_ids=m["team_b_player_ids"],
                        score_a=m["score_a"],
                        score_b=m["score_b"],
                        created_at=m["created_at"],
                    )
                    for m in r["matches"]
                ]

                return Round(
                    id=r["id"],
                    index=r["index"],
                    matches=matches,
                    created_at=r["created_at"],
                )
        return None

    def get_round_by_index(self, round_index: int) -> Round | None:
        """Get a round by its index."""
        for r in self.data["rounds"]:
            if r["index"] == round_index:
                return self.get_round(r["id"])
        return None

    def get_all_rounds(self) -> list[Round]:
        """Get all rounds with their matches."""
        rounds: list[Round] = []
        for r in sorted(self.data["rounds"], key=lambda x: x["index"]):
            round_obj = self.get_round(r["id"])
            if round_obj:
                rounds.append(round_obj)
        return rounds

    def delete_round(self, round_id: int) -> None:
        """Delete a round and its matches."""
        for i, r in enumerate(self.data["rounds"]):
            if r["id"] == round_id:
                del self.data["rounds"][i]
                self._save()
                return

        raise ValueError(f"Round with ID {round_id} not found")

    def update_match(self, match: Match) -> Match:
        """Update an existing match."""
        if match.id is None:
            raise ValueError("Match must have an ID")

        for round_data in self.data["rounds"]:
            for m in round_data["matches"]:
                if m["id"] == match.id:
                    m["score_a"] = match.score_a
                    m["score_b"] = match.score_b
                    self._save()

                    return Match(
                        id=m["id"],
                        round_index=m["round_index"],
                        terrain_label=m["terrain_label"],
                        format=MatchFormat(m["format"]),
                        team_a_player_ids=m["team_a_player_ids"],
                        team_b_player_ids=m["team_b_player_ids"],
                        score_a=m["score_a"],
                        score_b=m["score_b"],
                        created_at=m["created_at"],
                    )

        raise ValueError(f"Match with ID {match.id} not found")

    def get_all_matches(self) -> list[Match]:
        """Get all matches from all rounds."""
        matches: list[Match] = []
        for round_data in sorted(self.data["rounds"], key=lambda x: x["index"]):
            for m in round_data["matches"]:
                matches.append(
                    Match(
                        id=m["id"],
                        round_index=m["round_index"],
                        terrain_label=m["terrain_label"],
                        format=MatchFormat(m["format"]),
                        team_a_player_ids=m["team_a_player_ids"],
                        team_b_player_ids=m["team_b_player_ids"],
                        score_a=m["score_a"],
                        score_b=m["score_b"],
                        created_at=m["created_at"],
                    )
                )
        return matches

    def delete_all_rounds(self) -> None:
        """Delete all rounds and matches."""
        self.data["rounds"] = []
        self._save()

    def reset_tournament(self) -> None:
        """Reset entire tournament."""
        self.data = {
            "config": None,
            "players": [],
            "rounds": [],
            "next_player_id": 1,
            "next_round_id": 1,
            "next_match_id": 1,
        }
        self._save()
