"""Abstract storage interface for tournament data.

This module defines the abstract interface that all storage backends must implement.
Follows the Repository pattern for clean architecture.
"""

from abc import ABC, abstractmethod

from src.petanque_manager.core.models import Match, Player, Round, TournamentConfig


class TournamentStorage(ABC):
    """Abstract interface for tournament data storage."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize storage (create tables, files, etc.).

        Raises:
            Exception: If initialization fails
        """
        pass

    @abstractmethod
    def save_config(self, config: TournamentConfig) -> None:
        """Save tournament configuration.

        Args:
            config: Tournament configuration to save
        """
        pass

    @abstractmethod
    def load_config(self) -> TournamentConfig | None:
        """Load tournament configuration.

        Returns:
            Tournament configuration or None if not found
        """
        pass

    @abstractmethod
    def add_player(self, player: Player) -> Player:
        """Add a new player.

        Args:
            player: Player to add (id will be auto-generated)

        Returns:
            Player with id populated

        Raises:
            ValueError: If player with same name already exists
        """
        pass

    @abstractmethod
    def get_player(self, player_id: int) -> Player | None:
        """Get a player by ID.

        Args:
            player_id: Player ID

        Returns:
            Player or None if not found
        """
        pass

    @abstractmethod
    def get_all_players(self, active_only: bool = False) -> list[Player]:
        """Get all players.

        Args:
            active_only: If True, only return active players

        Returns:
            List of players
        """
        pass

    @abstractmethod
    def update_player(self, player: Player) -> Player:
        """Update an existing player.

        Args:
            player: Player with updated data

        Returns:
            Updated player

        Raises:
            ValueError: If player doesn't exist
        """
        pass

    @abstractmethod
    def delete_player(self, player_id: int) -> None:
        """Delete a player.

        Args:
            player_id: Player ID

        Raises:
            ValueError: If player doesn't exist or has played matches
        """
        pass

    @abstractmethod
    def add_round(self, round_obj: Round) -> Round:
        """Add a new round with its matches.

        Args:
            round_obj: Round to add (ids will be auto-generated)

        Returns:
            Round with ids populated

        Raises:
            ValueError: If round with same index already exists
        """
        pass

    @abstractmethod
    def get_round(self, round_id: int) -> Round | None:
        """Get a round by ID.

        Args:
            round_id: Round ID

        Returns:
            Round with matches or None if not found
        """
        pass

    @abstractmethod
    def get_round_by_index(self, round_index: int) -> Round | None:
        """Get a round by its index.

        Args:
            round_index: Round index (0-based)

        Returns:
            Round with matches or None if not found
        """
        pass

    @abstractmethod
    def get_all_rounds(self) -> list[Round]:
        """Get all rounds with their matches.

        Returns:
            List of rounds, sorted by index
        """
        pass

    @abstractmethod
    def update_match(self, match: Match) -> Match:
        """Update an existing match (e.g., to add scores).

        Args:
            match: Match with updated data

        Returns:
            Updated match

        Raises:
            ValueError: If match doesn't exist
        """
        pass

    @abstractmethod
    def get_all_matches(self) -> list[Match]:
        """Get all matches from all rounds.

        Returns:
            List of all matches
        """
        pass

    @abstractmethod
    def delete_all_rounds(self) -> None:
        """Delete all rounds and matches.

        Warning: This is destructive and cannot be undone.
        """
        pass

    @abstractmethod
    def reset_tournament(self) -> None:
        """Reset entire tournament (delete all data).

        Warning: This is destructive and cannot be undone.
        """
        pass
