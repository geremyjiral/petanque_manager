"""Tests for constraint tracking and violation scoring."""

from src.petanque_manager.core.models import Match, MatchFormat, TournamentMode
from src.petanque_manager.core.scheduler import ConstraintTracker


def test_constraint_tracker_initialization() -> None:
    """Test constraint tracker initializes correctly."""
    tracker = ConstraintTracker()

    assert len(tracker.partners) == 0
    assert len(tracker.opponents) == 0
    assert len(tracker.terrains) == 0
    assert len(tracker.fallback_formats) == 0


def test_track_partners() -> None:
    """Test tracking of player partners."""
    tracker = ConstraintTracker()

    # Players 1, 2, 3 on team A
    match = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )

    tracker.add_match(match, TournamentMode.TRIPLETTE)

    # Player 1's partners should be 2 and 3
    assert tracker.partners[1] == {2, 3}
    assert tracker.partners[2] == {1, 3}
    assert tracker.partners[3] == {1, 2}

    # Player 4's partners should be 5 and 6
    assert tracker.partners[4] == {5, 6}


def test_track_opponents() -> None:
    """Test tracking of player opponents."""
    tracker = ConstraintTracker()

    match = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )

    tracker.add_match(match, TournamentMode.TRIPLETTE)

    # Player 1's opponents should be 4, 5, 6
    assert tracker.opponents[1] == {4, 5, 6}

    # Player 4's opponents should be 1, 2, 3
    assert tracker.opponents[4] == {1, 2, 3}


def test_track_terrains() -> None:
    """Test tracking of terrain usage."""
    tracker = ConstraintTracker()

    match1 = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )

    match2 = Match(
        round_index=1,
        terrain_label="B",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 7, 8],
        team_b_player_ids=[9, 10, 11],
    )

    tracker.add_match(match1, TournamentMode.TRIPLETTE)
    tracker.add_match(match2, TournamentMode.TRIPLETTE)

    # Player 1 has played on terrains A and B
    assert tracker.terrains[1] == {"A", "B"}

    # Player 2 has only played on terrain A
    assert tracker.terrains[2] == {"A"}


def test_track_fallback_formats() -> None:
    """Test tracking of fallback format usage."""
    tracker = ConstraintTracker()

    # Doublette match in TRIPLETTE mode (fallback)
    match1 = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.DOUBLETTE,
        team_a_player_ids=[1, 2],
        team_b_player_ids=[3, 4],
    )

    tracker.add_match(match1, TournamentMode.TRIPLETTE)

    # All 4 players should have fallback count = 1
    assert tracker.fallback_formats[1] == 1
    assert tracker.fallback_formats[2] == 1
    assert tracker.fallback_formats[3] == 1
    assert tracker.fallback_formats[4] == 1

    # Triplette match in TRIPLETTE mode (not fallback)
    match2 = Match(
        round_index=1,
        terrain_label="B",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 5, 6],
        team_b_player_ids=[7, 8, 9],
    )

    tracker.add_match(match2, TournamentMode.TRIPLETTE)

    # Player 1's fallback count should still be 1
    assert tracker.fallback_formats[1] == 1

    # Players 5-9 should have fallback count = 0
    assert tracker.fallback_formats[5] == 0


def test_score_repeated_partners() -> None:
    """Test scoring penalty for repeated partners."""
    tracker = ConstraintTracker()

    # First match: players 1 and 2 together
    match1 = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )
    tracker.add_match(match1, TournamentMode.TRIPLETTE)

    # Score a new match with players 1 and 2 together again
    score = tracker.score_match(
        team_a=[1, 2, 7],
        team_b=[8, 9, 10],
        terrain="B",
        match_format=MatchFormat.TRIPLETTE,
        tournament_mode=TournamentMode.TRIPLETTE,
    )

    # Should have penalty for repeated partner (1-2)
    # Penalty is 10 points per repeated partner
    assert score >= 10.0


def test_score_repeated_opponents() -> None:
    """Test scoring penalty for repeated opponents."""
    tracker = ConstraintTracker()

    # First match: player 1 vs players 4, 5, 6
    match1 = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )
    tracker.add_match(match1, TournamentMode.TRIPLETTE)

    # Score a new match with player 1 vs player 4 again
    score = tracker.score_match(
        team_a=[1, 7, 8],
        team_b=[4, 9, 10],
        terrain="B",
        match_format=MatchFormat.TRIPLETTE,
        tournament_mode=TournamentMode.TRIPLETTE,
    )

    # Should have penalty for repeated opponent (1 vs 4)
    # Penalty is 5 points per repeated opponent pair
    assert score >= 5.0


def test_score_repeated_terrain() -> None:
    """Test scoring penalty for repeated terrain usage."""
    tracker = ConstraintTracker()

    # First match: player 1 on terrain A
    match1 = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )
    tracker.add_match(match1, TournamentMode.TRIPLETTE)

    # Score a new match with player 1 on terrain A again
    score = tracker.score_match(
        team_a=[1, 7, 8],
        team_b=[9, 10, 11],
        terrain="A",  # Same terrain
        match_format=MatchFormat.TRIPLETTE,
        tournament_mode=TournamentMode.TRIPLETTE,
    )

    # Should have penalty for repeated terrain (player 1 on A)
    # Penalty is 3 points per player on repeated terrain
    assert score >= 2.0


def test_score_fallback_format() -> None:
    """Test scoring penalty for fallback format usage."""
    tracker = ConstraintTracker()

    # Score a doublette match in TRIPLETTE mode (fallback)
    score = tracker.score_match(
        team_a=[1, 2],
        team_b=[3, 4],
        terrain="A",
        match_format=MatchFormat.DOUBLETTE,
        tournament_mode=TournamentMode.TRIPLETTE,
    )

    # Should have penalty for fallback format
    # Penalty is 4 points per player in fallback format
    # 4 players * 4 points = 16
    assert score >= 16.0


def test_score_no_violations() -> None:
    """Test scoring with no violations."""
    tracker = ConstraintTracker()

    # First match
    match1 = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )
    tracker.add_match(match1, TournamentMode.TRIPLETTE)

    # Score a completely different match (no repeated players, different terrain)
    score = tracker.score_match(
        team_a=[7, 8, 9],
        team_b=[10, 11, 12],
        terrain="B",
        match_format=MatchFormat.TRIPLETTE,
        tournament_mode=TournamentMode.TRIPLETTE,
    )

    # Should have no penalty
    assert score == 0.0


def test_score_multiple_violations() -> None:
    """Test scoring with multiple types of violations."""
    tracker = ConstraintTracker()

    # First match
    match1 = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )
    tracker.add_match(match1, TournamentMode.TRIPLETTE)

    # Score a match with multiple violations:
    # - Players 1 and 2 together again (repeated partners)
    # - Player 1 on terrain A again (repeated terrain)
    # - Player 1 vs player 4 again (repeated opponents)
    score = tracker.score_match(
        team_a=[1, 2, 7],  # 1 and 2 together again
        team_b=[4, 8, 9],  # 1 vs 4 again
        terrain="A",  # Player 1 on A again
        match_format=MatchFormat.TRIPLETTE,
        tournament_mode=TournamentMode.TRIPLETTE,
    )

    # Should have penalties for all violations
    # Repeated partners: 10
    # Repeated opponents: 5 (1 vs 4)
    # Repeated terrain: 3 (player 1 on A)
    # Total minimum: 18
    assert score >= 18.0


def test_constraint_tracking_across_multiple_rounds() -> None:
    """Test constraint tracking accumulates correctly across multiple rounds."""
    tracker = ConstraintTracker()

    # Round 1
    match1 = Match(
        round_index=0,
        terrain_label="A",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 2, 3],
        team_b_player_ids=[4, 5, 6],
    )
    tracker.add_match(match1, TournamentMode.TRIPLETTE)

    # Round 2
    match2 = Match(
        round_index=1,
        terrain_label="B",
        format=MatchFormat.TRIPLETTE,
        team_a_player_ids=[1, 7, 8],
        team_b_player_ids=[2, 9, 10],
    )
    tracker.add_match(match2, TournamentMode.TRIPLETTE)

    # Player 1 has now:
    # - Played with: 2, 3, 7, 8
    # - Played against: 4, 5, 6, 2, 9, 10 (note: 2 is now opponent)
    # - Played on: A, B

    assert 2 in tracker.partners[1]
    assert 7 in tracker.partners[1]
    assert 2 in tracker.opponents[1]  # Player 2 is both partner and opponent now
    assert tracker.terrains[1] == {"A", "B"}
