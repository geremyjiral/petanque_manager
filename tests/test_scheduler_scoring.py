"""Tests for tournament scheduler and scoring logic."""

import pytest

from src.core.models import (
    Match,
    MatchFormat,
    Player,
    PlayerRole,
    Round,
    TournamentMode,
)
from src.core.scheduler import (
    ConstraintTracker,
    TournamentScheduler,
    calculate_role_requirements,
    validate_team_roles,
)


def test_calculate_role_requirements_triplette() -> None:
    """Test role requirements calculation for TRIPLETTE mode."""
    # 12 players = 4 triplette teams = 2 matches
    req = calculate_role_requirements(TournamentMode.TRIPLETTE, 12)
    assert req.tireur_needed == 4
    assert req.pointeur_needed == 4
    assert req.milieu_needed == 4
    assert req.pointeur_milieu_needed == 0

    # 18 players = 6 triplette teams = 3 matches
    req = calculate_role_requirements(TournamentMode.TRIPLETTE, 18)
    assert req.tireur_needed == 6
    assert req.pointeur_needed == 6
    assert req.milieu_needed == 6

    # 14 players = 4 triplette teams + 1 doublette team (fallback)
    req = calculate_role_requirements(TournamentMode.TRIPLETTE, 14)
    assert req.tireur_needed == 5  # 4 + 1 for doublette
    assert req.pointeur_needed == 4
    assert req.milieu_needed == 4
    assert req.pointeur_milieu_needed == 1


def test_calculate_role_requirements_doublette() -> None:
    """Test role requirements calculation for DOUBLETTE mode."""
    # 8 players = 4 doublette teams = 2 matches
    req = calculate_role_requirements(TournamentMode.DOUBLETTE, 8)
    assert req.tireur_needed == 4
    assert req.pointeur_milieu_needed == 4

    # 12 players = 6 doublette teams = 3 matches
    req = calculate_role_requirements(TournamentMode.DOUBLETTE, 12)
    assert req.tireur_needed == 6
    assert req.pointeur_milieu_needed == 6

    # 11 players = 5 doublette teams + 1 (odd player, would need triplette fallback)
    req = calculate_role_requirements(TournamentMode.DOUBLETTE, 11)
    # 10 players = 5 doublette teams, 1 player unused
    assert req.tireur_needed >= 5
    assert req.pointeur_milieu_needed >= 5


def test_validate_team_roles_triplette_valid() -> None:
    """Test team role validation for valid TRIPLETTE team."""
    team = [
        Player(id=1, name="P1", role=PlayerRole.TIREUR),
        Player(id=2, name="P2", role=PlayerRole.POINTEUR),
        Player(id=3, name="P3", role=PlayerRole.MILIEU),
    ]

    assert validate_team_roles(team, MatchFormat.TRIPLETTE, TournamentMode.TRIPLETTE)


def test_validate_team_roles_triplette_invalid() -> None:
    """Test team role validation for invalid TRIPLETTE team."""
    # Two TIREUR, no MILIEU
    team = [
        Player(id=1, name="P1", role=PlayerRole.TIREUR),
        Player(id=2, name="P2", role=PlayerRole.POINTEUR),
        Player(id=3, name="P3", role=PlayerRole.TIREUR),
    ]

    assert not validate_team_roles(team, MatchFormat.TRIPLETTE, TournamentMode.TRIPLETTE)


def test_validate_team_roles_doublette_valid() -> None:
    """Test team role validation for valid DOUBLETTE team."""
    team = [
        Player(id=1, name="P1", role=PlayerRole.TIREUR),
        Player(id=2, name="P2", role=PlayerRole.POINTEUR_MILIEU),
    ]

    assert validate_team_roles(team, MatchFormat.DOUBLETTE, TournamentMode.DOUBLETTE)


def test_validate_team_roles_doublette_invalid() -> None:
    """Test team role validation for invalid DOUBLETTE team."""
    # Two TIREUR
    team = [
        Player(id=1, name="P1", role=PlayerRole.TIREUR),
        Player(id=2, name="P2", role=PlayerRole.TIREUR),
    ]

    assert not validate_team_roles(team, MatchFormat.DOUBLETTE, TournamentMode.DOUBLETTE)


def test_constraint_tracker_partners() -> None:
    """Test constraint tracker records partners correctly."""
    tracker = ConstraintTracker()

    match = Match(
        id=1,
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
        score_a=13,
        score_b=7,
    )

    tracker.add_match(match, TournamentMode.TRIPLETTE)

    # Check partners
    assert 2 in tracker.partners[1]
    assert 3 in tracker.partners[1]
    assert 1 in tracker.partners[2]
    assert 3 in tracker.partners[2]

    # Check opponents
    assert 4 in tracker.opponents[1]
    assert 5 in tracker.opponents[1]
    assert 6 in tracker.opponents[1]


def test_constraint_tracker_scoring() -> None:
    """Test constraint tracker scores violations correctly."""
    tracker = ConstraintTracker()

    # First match
    match1 = Match(
        id=1,
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )
    tracker.add_match(match1, TournamentMode.TRIPLETTE)

    # Second match: players 1 and 2 play together again (repeated partners)
    score = tracker.score_match(
        [1, 2, 7],  # 1 and 2 together again
        [8, 9, 10],
        "B",
        MatchFormat.TRIPLETTE,
        TournamentMode.TRIPLETTE,
    )

    # Should have penalty for repeated partners (1-2 pair)
    assert score > 0


def test_scheduler_generates_valid_round() -> None:
    """Test scheduler generates valid round with correct team compositions."""
    # Create 12 players for TRIPLETTE mode
    players = [
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

    scheduler = TournamentScheduler(
        mode=TournamentMode.TRIPLETTE,
        terrains_count=8,
        seed=42,
    )

    round_obj, quality_report = scheduler.generate_round(
        players=players,
        round_index=0,
        previous_rounds=[],
    )

    # Verify round structure
    assert round_obj.index == 0
    assert len(round_obj.matches) > 0

    # Verify all matches have correct format
    for match in round_obj.matches:
        assert match.format == MatchFormat.TRIPLETTE
        assert len(match.team_a_player_ids) == 3
        assert len(match.team_b_player_ids) == 3

        # Verify no duplicate players in match
        all_players_in_match = set(match.all_player_ids)
        assert len(all_players_in_match) == 6

    # Verify quality report
    assert quality_report.total_score >= 0


def test_scheduler_multiple_rounds_minimize_repetitions() -> None:
    """Test scheduler minimizes repetitions across multiple rounds."""
    # Create 12 players
    players = [
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

    scheduler = TournamentScheduler(
        mode=TournamentMode.TRIPLETTE,
        terrains_count=8,
        seed=42,
    )

    rounds: list[Round] = []

    # Generate 3 rounds
    for i in range(3):
        round_obj, quality_report = scheduler.generate_round(
            players=players,
            round_index=i,
            previous_rounds=rounds,
        )
        rounds.append(round_obj)

        # Quality should not degrade too much
        assert quality_report.quality_grade in ["A+", "A", "B", "C"]

    # Verify each round has matches
    for round_obj in rounds:
        assert len(round_obj.matches) > 0


def test_scheduler_handles_uneven_player_count() -> None:
    """Test scheduler handles player counts that don't divide evenly."""
    # 13 players (not divisible by 3 or 2 cleanly)
    players = [
        Player(id=1, name="T1", role=PlayerRole.TIREUR),
        Player(id=2, name="T2", role=PlayerRole.TIREUR),
        Player(id=3, name="T3", role=PlayerRole.TIREUR),
        Player(id=4, name="P1", role=PlayerRole.POINTEUR),
        Player(id=5, name="P2", role=PlayerRole.POINTEUR),
        Player(id=6, name="P3", role=PlayerRole.POINTEUR),
        Player(id=7, name="M1", role=PlayerRole.MILIEU),
        Player(id=8, name="M2", role=PlayerRole.MILIEU),
        Player(id=9, name="M3", role=PlayerRole.MILIEU),
        Player(id=10, name="PM1", role=PlayerRole.POINTEUR_MILIEU),
        Player(id=11, name="PM2", role=PlayerRole.POINTEUR_MILIEU),
        Player(id=12, name="PM3", role=PlayerRole.POINTEUR_MILIEU),
        Player(id=13, name="PM4", role=PlayerRole.POINTEUR_MILIEU),
    ]

    scheduler = TournamentScheduler(
        mode=TournamentMode.TRIPLETTE,
        terrains_count=8,
        seed=42,
    )

    # Should not raise error
    round_obj, _quality_report = scheduler.generate_round(
        players=players,
        round_index=0,
        previous_rounds=[],
    )

    # Should have generated some matches
    assert len(round_obj.matches) > 0


def test_match_validation() -> None:
    """Test match model validation."""
    # Valid triplette match
    match = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )
    assert match.format == MatchFormat.TRIPLETTE

    # Invalid: player in both teams
    with pytest.raises(ValueError):
        Match(
            round_index=0,
            terrain_label="A",
            format=MatchFormat.TRIPLETTE,
            team_a_player_ids=[1, 2, 3],
            team_b_player_ids=[3, 4, 5],  # Player 3 in both teams
        )

    # Invalid: wrong team size for format
    with pytest.raises(ValueError):
        Match(
            round_index=0,
            terrain_label="A",
            format=MatchFormat.TRIPLETTE,
            team_a_player_ids=[1, 2],  # Only 2 players for triplette
            team_b_player_ids=[4, 5, 6],
        )


def test_round_completion_status() -> None:
    """Test round completion status."""
    match1 = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
        score_a=13,
        score_b=7,
    )

    match2 = Match(
        round_index=0,
        terrain_label="B",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[7, 8, 9],
        team_b_player_ids=[10, 11, 12],
    )

    round_obj = Round(index=0, matches=[match1, match2])

    # Round not complete (match2 has no score)
    assert not round_obj.is_complete

    # Complete match2
    match2.score_a = 10
    match2.score_b = 13

    # Now round should be complete
    assert round_obj.is_complete
