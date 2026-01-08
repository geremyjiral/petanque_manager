"""Tests for optimal match distribution algorithm (including hybrid 3v2 matches)."""

import pytest

from src.petanque_manager.core.models import (
    Match,
    MatchFormat,
    Player,
    PlayerRole,
    TournamentMode,
)
from src.petanque_manager.core.scheduler import (
    TournamentScheduler,
    _find_optimal_match_distribution,
    calculate_role_requirements,
)


class TestOptimalMatchDistribution:
    """Test the _find_optimal_match_distribution function."""

    def test_exact_6_players(self):
        """6 players should give 1 triplette match (3v3)."""
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(6, TournamentMode.TRIPLETTE)
        assert nb_3v3 == 1  # 1 match 3v3 = 6 players
        assert nb_2v2 == 0
        assert nb_3v2 == 0

    def test_exact_8_players(self):
        """8 players should give 2 doublette matches (2v2)."""
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(8, TournamentMode.DOUBLETTE)
        assert nb_2v2 == 2  # 2 matchs 2v2 = 8 players
        # In DOUBLETTE mode, prefer 2v2 over 3v3
        assert nb_3v3 + nb_3v2 <= nb_2v2

    def test_5_players_needs_hybrid(self):
        """5 players should require 1 hybrid match (3v2)."""
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(5, TournamentMode.TRIPLETTE)
        assert nb_3v2 == 1  # 1 match 3v2 = 5 players
        assert nb_3v3 == 0
        assert nb_2v2 == 0

    def test_7_players(self):
        """7 players: mathematically impossible without benching.

        Best option: 1x3v3 = 6 players (bench 1).
        Alternative: 1x3v2 = 5 players (bench 2) - worse.
        Combinations: 6, 4, 5 don't sum to 7 without going over.
        """
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(7, TournamentMode.TRIPLETTE)
        total_players = nb_3v3 * 6 + nb_2v2 * 4 + nb_3v2 * 5

        # 7 cannot be perfectly matched, best is 6 (1x3v3)
        assert total_players == 6  # Minimize bench: 1 player benched
        assert nb_3v3 == 1
        assert nb_2v2 == 0
        assert nb_3v2 == 0

    def test_10_players(self):
        """10 players should use optimal combination."""
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(10, TournamentMode.TRIPLETTE)
        total_players = nb_3v3 * 6 + nb_2v2 * 4 + nb_3v2 * 5
        assert total_players == 10  # All players included
        # Possible: 1x3v3 + 1x2v2 = 6 + 4 = 10 ✓
        # Or: 2x3v2 = 10 ✓
        # In TRIPLETTE mode, prefer 3v3, so should be 1x3v3 + 1x2v2
        assert nb_3v3 >= 1 or nb_3v2 == 2

    def test_11_players(self):
        """11 players: 1x3v3 + 1x3v2 = 6 + 5 = 11."""
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(11, TournamentMode.TRIPLETTE)
        total_players = nb_3v3 * 6 + nb_2v2 * 4 + nb_3v2 * 5
        assert total_players == 11  # All players included

    def test_20_players(self):
        """20 players should use optimal combination."""
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(20, TournamentMode.TRIPLETTE)
        total_players = nb_3v3 * 6 + nb_2v2 * 4 + nb_3v2 * 5
        assert total_players == 20  # All players included
        # Possible: 3x3v3 + 1x2v2 = 18 + 2 = 20 (bench 0) wait no, 18+2=20 but needs 4 for 2v2
        # Better: 3x3v3 = 18, 4x3v2 or 2x3v2 or combinations
        # 3x3v3 + 0.5x2v2 impossible
        # 2x3v3 + 2x2v2 = 12 + 8 = 20 ✓
        # Or: 4x3v2 = 20 ✓
        # In TRIPLETTE mode, should prefer 3v3
        assert nb_3v3 >= 2 or nb_3v2 >= 4

    def test_less_than_4_players(self):
        """Less than 4 players: no match possible."""
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(3, TournamentMode.TRIPLETTE)
        assert nb_3v3 == 0
        assert nb_2v2 == 0
        assert nb_3v2 == 0


class TestRoleRequirements:
    """Test role requirements calculation with new distribution."""

    def test_5_players_hybrid(self):
        """5 players requires 1 hybrid match (3v2)."""
        reqs = calculate_role_requirements(TournamentMode.TRIPLETTE, 5)
        # 1 match 3v2 (hybrid)
        assert reqs.hybrid_count == 1
        assert reqs.triplette_count == 0  # No pure 3v3 matches
        assert reqs.doublette_count == 0  # No pure 2v2 matches
        # Needs: 1 tireur for triplette side + 1 tireur for doublette side = 2 tireurs
        assert reqs.tireur_needed == 2

    def test_10_players(self):
        """10 players optimal distribution."""
        reqs = calculate_role_requirements(TournamentMode.TRIPLETTE, 10)
        # Could be 1x3v3 + 1x2v2 = 4 teams total (2 trip + 2 doub)
        # Or 2x3v2 = 4 teams (2 trip + 2 doub)
        assert reqs.triplette_count + reqs.doublette_count >= 2


class TestHybridMatchGeneration:
    """Test generation of hybrid 3v2 matches."""

    def create_players(self, count: int) -> list[Player]:
        """Helper to create test players."""
        players = []
        for i in range(count):
            # Distribute roles to ensure matches can be formed
            if i % 3 == 0:
                roles = [PlayerRole.TIREUR]
            elif i % 3 == 1:
                roles = [PlayerRole.POINTEUR]
            else:
                roles = [PlayerRole.MILIEU]

            players.append(
                Player(
                    id=i + 1,
                    name=f"Player {i+1}",
                    roles=roles,
                    active=True,
                )
            )
        return players

    def test_hybrid_match_creation(self):
        """Test that a hybrid match can be created."""
        match = Match(
            round_index=0,
            terrain_label="A",
            format=MatchFormat.HYBRID,
            team_a_player_ids=[1, 2, 3],  # 3 players
            team_b_player_ids=[4, 5],  # 2 players
        )
        assert match.format == MatchFormat.HYBRID
        assert len(match.team_a_player_ids) == 3
        assert len(match.team_b_player_ids) == 2

    def test_hybrid_match_validation_3v2(self):
        """Test that 3v2 is valid for HYBRID."""
        match = Match(
            round_index=0,
            terrain_label="A",
            format=MatchFormat.HYBRID,
            team_a_player_ids=[1, 2, 3],
            team_b_player_ids=[4, 5],
        )
        # Should not raise
        assert match is not None

    def test_hybrid_match_validation_2v3(self):
        """Test that 2v3 is also valid for HYBRID (teams reversed)."""
        match = Match(
            round_index=0,
            terrain_label="A",
            format=MatchFormat.HYBRID,
            team_a_player_ids=[1, 2],
            team_b_player_ids=[3, 4, 5],
        )
        # Should not raise
        assert match is not None

    def test_hybrid_match_rejects_3v3(self):
        """Test that 3v3 is rejected for HYBRID format."""
        with pytest.raises(ValueError, match="Hybrid format requires"):
            Match(
                round_index=0,
                terrain_label="A",
                format=MatchFormat.HYBRID,
                team_a_player_ids=[1, 2, 3],
                team_b_player_ids=[4, 5, 6],  # Both teams 3 - wrong!
            )

    def test_5_players_generates_hybrid_match(self):
        """Test that 5 players generates a hybrid 3v2 match."""
        players = self.create_players(5)
        scheduler = TournamentScheduler(TournamentMode.TRIPLETTE, terrains_count=5, seed=42)

        round_obj, quality_report = scheduler.generate_round(players, 0, [])

        # Should have 1 match
        assert len(round_obj.matches) == 1

        match = round_obj.matches[0]
        # Should be hybrid
        assert match.format == MatchFormat.HYBRID

        # Should have 3 + 2 = 5 players total
        total_players = len(match.team_a_player_ids) + len(match.team_b_player_ids)
        assert total_players == 5

    def test_10_players_all_play(self):
        """Test that all 10 players are assigned to matches."""
        players = self.create_players(10)
        scheduler = TournamentScheduler(TournamentMode.TRIPLETTE, terrains_count=5, seed=42)

        round_obj, quality_report = scheduler.generate_round(players, 0, [])

        # Count total players in all matches
        all_player_ids = set()
        for match in round_obj.matches:
            all_player_ids.update(match.team_a_player_ids)
            all_player_ids.update(match.team_b_player_ids)

        # All 10 players should play
        assert len(all_player_ids) == 10

    def test_11_players_all_play(self):
        """Test that all 11 players are assigned (likely 1x3v3 + 1x3v2)."""
        players = self.create_players(11)
        scheduler = TournamentScheduler(TournamentMode.TRIPLETTE, terrains_count=5, seed=42)

        round_obj, quality_report = scheduler.generate_round(players, 0, [])

        # Count total players in all matches
        all_player_ids = set()
        for match in round_obj.matches:
            all_player_ids.update(match.team_a_player_ids)
            all_player_ids.update(match.team_b_player_ids)

        # All 11 players should play
        assert len(all_player_ids) == 11


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
