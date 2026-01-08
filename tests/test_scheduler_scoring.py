"""Tests for tournament scheduler and scoring logic."""

import pytest

from src.petanque_manager.core.models import (
    Match,
    MatchFormat,
    Player,
    PlayerRole,
    Round,
    TournamentMode,
)
from src.petanque_manager.core.scheduler import (
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

    # 18 players = 6 triplette teams = 3 matches
    req = calculate_role_requirements(TournamentMode.TRIPLETTE, 18)
    assert req.tireur_needed == 6
    assert req.pointeur_needed == 6
    assert req.milieu_needed == 6

    # 14 players = 1x3v3 + 2x2v2 = 2 triplette teams + 4 doublette teams
    req = calculate_role_requirements(TournamentMode.TRIPLETTE, 14)
    assert req.tireur_needed == 6  # 2 (triplette) + 4 (doublette)
    # For doublette teams, we split pointeur/milieu since each needs TIREUR + (POINTEUR or MILIEU)
    assert req.pointeur_needed == 4  # 2 (triplette) + 2 (half of doublette)
    assert req.milieu_needed == 4  # 2 (triplette) + 2 (half of doublette)


def test_calculate_role_requirements_doublette() -> None:
    """Test role requirements calculation for DOUBLETTE mode."""
    # 8 players = 4 doublette teams = 2 matches
    req = calculate_role_requirements(TournamentMode.DOUBLETTE, 8)
    assert req.tireur_needed == 4
    # Doublette teams split between pointeur and milieu
    assert req.pointeur_needed == 2
    assert req.milieu_needed == 2

    # 12 players = 6 doublette teams = 3 matches
    req = calculate_role_requirements(TournamentMode.DOUBLETTE, 12)
    assert req.tireur_needed == 6
    assert req.pointeur_needed == 3
    assert req.milieu_needed == 3

    # 11 players = 1x3v3 + 1x3v2 (hybrid) = 2 trip teams + 1 hybrid
    req = calculate_role_requirements(TournamentMode.DOUBLETTE, 11)
    assert req.tireur_needed == 4  # 2 (trip) + 1 (hybrid trip) + 1 (hybrid doub)
    assert req.pointeur_needed == 4  # 2 (trip) + 1 (hybrid trip) + 1 (hybrid doub)
    assert req.milieu_needed == 3  # 2 (trip) + 1 (hybrid trip) + 0 (hybrid doub)


def test_validate_team_roles_triplette_valid() -> None:
    """Test team role validation for valid TRIPLETTE team."""
    team = [
        Player(id=1, name="P1", roles=[PlayerRole.TIREUR]),
        Player(id=2, name="P2", roles=[PlayerRole.POINTEUR]),
        Player(id=3, name="P3", roles=[PlayerRole.MILIEU]),
    ]

    assert validate_team_roles(team, MatchFormat.TRIPLETTE, TournamentMode.TRIPLETTE)


def test_validate_team_roles_triplette_invalid() -> None:
    """Test team role validation for invalid TRIPLETTE team."""
    # Two TIREUR, no MILIEU
    team = [
        Player(id=1, name="P1", roles=[PlayerRole.TIREUR]),
        Player(id=2, name="P2", roles=[PlayerRole.POINTEUR]),
        Player(id=3, name="P3", roles=[PlayerRole.TIREUR]),
    ]

    assert not validate_team_roles(team, MatchFormat.TRIPLETTE, TournamentMode.TRIPLETTE)


def test_validate_team_roles_doublette_valid() -> None:
    """Test team role validation for valid DOUBLETTE team."""
    team = [
        Player(id=1, name="P1", roles=[PlayerRole.TIREUR]),
        Player(id=2, name="P2", roles=[PlayerRole.POINTEUR, PlayerRole.MILIEU]),
    ]

    assert validate_team_roles(team, MatchFormat.DOUBLETTE, TournamentMode.DOUBLETTE)


def test_validate_team_roles_doublette_invalid() -> None:
    """Test team role validation for invalid DOUBLETTE team."""
    # Two TIREUR
    team = [
        Player(id=1, name="P1", roles=[PlayerRole.TIREUR]),
        Player(id=2, name="P2", roles=[PlayerRole.TIREUR]),
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
        Player(id=1, name="T1", roles=[PlayerRole.TIREUR]),
        Player(id=2, name="T2", roles=[PlayerRole.TIREUR]),
        Player(id=3, name="T3", roles=[PlayerRole.TIREUR]),
        Player(id=4, name="T4", roles=[PlayerRole.TIREUR]),
        Player(id=5, name="P1", roles=[PlayerRole.POINTEUR]),
        Player(id=6, name="P2", roles=[PlayerRole.POINTEUR]),
        Player(id=7, name="P3", roles=[PlayerRole.POINTEUR]),
        Player(id=8, name="P4", roles=[PlayerRole.POINTEUR]),
        Player(id=9, name="M1", roles=[PlayerRole.MILIEU]),
        Player(id=10, name="M2", roles=[PlayerRole.MILIEU]),
        Player(id=11, name="M3", roles=[PlayerRole.MILIEU]),
        Player(id=12, name="M4", roles=[PlayerRole.MILIEU]),
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
        Player(id=1, name="T1", roles=[PlayerRole.TIREUR]),
        Player(id=2, name="T2", roles=[PlayerRole.TIREUR]),
        Player(id=3, name="T3", roles=[PlayerRole.TIREUR]),
        Player(id=4, name="T4", roles=[PlayerRole.TIREUR]),
        Player(id=5, name="P1", roles=[PlayerRole.POINTEUR]),
        Player(id=6, name="P2", roles=[PlayerRole.POINTEUR]),
        Player(id=7, name="P3", roles=[PlayerRole.POINTEUR]),
        Player(id=8, name="P4", roles=[PlayerRole.POINTEUR]),
        Player(id=9, name="M1", roles=[PlayerRole.MILIEU]),
        Player(id=10, name="M2", roles=[PlayerRole.MILIEU]),
        Player(id=11, name="M3", roles=[PlayerRole.MILIEU]),
        Player(id=12, name="M4", roles=[PlayerRole.MILIEU]),
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

        # Quality degrades naturally with more rounds and limited players
        # First round should be excellent, later rounds may have more repetition
        if i == 0:
            assert quality_report.quality_grade in ["A+", "A"]
        else:
            # Later rounds naturally have more repetition with only 12 players
            assert quality_report.quality_grade in ["A+", "A", "B", "C", "D"]

    # Verify each round has matches
    for round_obj in rounds:
        assert len(round_obj.matches) > 0


def test_scheduler_handles_uneven_player_count() -> None:
    """Test scheduler handles player counts that don't divide evenly."""
    # 13 players (not divisible by 3 or 2 cleanly)
    players = [
        Player(id=1, name="T1", roles=[PlayerRole.TIREUR]),
        Player(id=2, name="T2", roles=[PlayerRole.TIREUR]),
        Player(id=3, name="T3", roles=[PlayerRole.TIREUR]),
        Player(id=4, name="P1", roles=[PlayerRole.POINTEUR]),
        Player(id=5, name="P2", roles=[PlayerRole.POINTEUR]),
        Player(id=6, name="P3", roles=[PlayerRole.POINTEUR]),
        Player(id=7, name="M1", roles=[PlayerRole.MILIEU]),
        Player(id=8, name="M2", roles=[PlayerRole.MILIEU]),
        Player(id=9, name="M3", roles=[PlayerRole.MILIEU]),
        Player(id=10, name="PM1", roles=[PlayerRole.POINTEUR, PlayerRole.MILIEU]),
        Player(id=11, name="PM2", roles=[PlayerRole.POINTEUR, PlayerRole.MILIEU]),
        Player(id=12, name="PM3", roles=[PlayerRole.POINTEUR, PlayerRole.MILIEU]),
        Player(id=13, name="PM4", roles=[PlayerRole.POINTEUR, PlayerRole.MILIEU]),
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
