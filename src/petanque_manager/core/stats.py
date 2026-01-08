"""Statistics and ranking calculation for tournament."""

from collections import defaultdict

from src.petanque_manager.core.models import Match, Player, PlayerStats, TournamentMode


def calculate_player_stats(
    players: list[Player],
    matches: list[Match],
) -> list[PlayerStats]:
    """Calculate statistics for all players based on completed matches.

    Args:
        players: List of all players
        matches: List of all matches (including incomplete ones)

    Returns:
        List of PlayerStats, sorted by ranking (wins desc, goal average desc, points for desc)
    """
    # Initialize stats for all players
    stats_dict: dict[int, PlayerStats] = {}
    for player in players:
        if player.id is not None:
            stats_dict[player.id] = PlayerStats(
                player_id=player.id,
                player_name=player.name,
                roles=player.roles,
            )

    # Process completed matches
    for match in matches:
        if not match.is_complete:
            continue

        assert match.score_a is not None
        assert match.score_b is not None

        # Determine winners
        team_a_won = match.score_a > match.score_b
        team_b_won = match.score_b > match.score_a

        # Update stats for team A
        for player_id in match.team_a_player_ids:
            if player_id in stats_dict:
                stat = stats_dict[player_id]
                stat.matches_played += 1
                stat.points_for += match.score_a
                stat.points_against += match.score_b
                if team_a_won:
                    stat.wins += 1
                elif team_b_won:
                    stat.losses += 1
                # If tie, neither wins nor losses increment

        # Update stats for team B
        for player_id in match.team_b_player_ids:
            if player_id in stats_dict:
                stat = stats_dict[player_id]
                stat.matches_played += 1
                stat.points_for += match.score_b
                stat.points_against += match.score_a
                if team_b_won:
                    stat.wins += 1
                elif team_a_won:
                    stat.losses += 1

    # Convert to list and sort by ranking
    stats_list = list(stats_dict.values())
    stats_list.sort(
        key=lambda s: (
            -s.wins,  # Wins descending
            -s.goal_average,  # Goal average descending
            -s.points_for,  # Points for descending
            s.player_name,  # Name ascending (tie-breaker)
        )
    )

    return stats_list


def get_player_stats(
    player_id: int,
    matches: list[Match],
) -> PlayerStats:
    """Get statistics for a specific player.

    Args:
        player_id: Player ID
        matches: List of all matches

    Returns:
        PlayerStats for the player

    Raises:
        ValueError: If player not found in any match
    """
    stats = PlayerStats(
        player_id=player_id,
        player_name="Unknown",  # Will be set by caller
        roles=[],  # Will be set by caller
    )

    found = False
    for match in matches:
        if not match.is_complete:
            continue

        if player_id not in match.all_player_ids:
            continue

        found = True
        assert match.score_a is not None
        assert match.score_b is not None

        in_team_a = player_id in match.team_a_player_ids
        team_a_won = match.score_a > match.score_b
        team_b_won = match.score_b > match.score_a

        stats.matches_played += 1

        if in_team_a:
            stats.points_for += match.score_a
            stats.points_against += match.score_b
            if team_a_won:
                stats.wins += 1
            elif team_b_won:
                stats.losses += 1
        else:
            stats.points_for += match.score_b
            stats.points_against += match.score_a
            if team_b_won:
                stats.wins += 1
            elif team_a_won:
                stats.losses += 1

    if not found:
        raise ValueError(f"Player {player_id} not found in any match")

    return stats


def get_head_to_head_stats(
    player_id: int,
    opponent_id: int,
    matches: list[Match],
) -> dict[str, int]:
    """Get head-to-head statistics between two players.

    Args:
        player_id: First player ID
        opponent_id: Second player ID
        matches: List of all matches

    Returns:
        Dictionary with keys: matches_played, player_wins, opponent_wins, draws
    """
    h2h = {
        "matches_played": 0,
        "player_wins": 0,
        "opponent_wins": 0,
        "draws": 0,
    }

    for match in matches:
        if not match.is_complete:
            continue

        # Check if both players are in this match on opposite teams
        player_in_a = player_id in match.team_a_player_ids
        player_in_b = player_id in match.team_b_player_ids
        opponent_in_a = opponent_id in match.team_a_player_ids
        opponent_in_b = opponent_id in match.team_b_player_ids

        # They must be on opposite teams
        if not ((player_in_a and opponent_in_b) or (player_in_b and opponent_in_a)):
            continue

        h2h["matches_played"] += 1

        assert match.score_a is not None
        assert match.score_b is not None

        if match.score_a > match.score_b:
            if player_in_a:
                h2h["player_wins"] += 1
            else:
                h2h["opponent_wins"] += 1
        elif match.score_b > match.score_a:
            if player_in_b:
                h2h["player_wins"] += 1
            else:
                h2h["opponent_wins"] += 1
        else:
            h2h["draws"] += 1

    return h2h


def get_partnership_stats(
    player_id: int,
    matches: list[Match],
) -> dict[int, dict[str, int]]:
    """Get statistics for each partner the player has played with.

    Args:
        player_id: Player ID
        matches: List of all matches

    Returns:
        Dictionary mapping partner_id -> {matches_played, wins, losses, draws}
    """
    partnerships: dict[int, dict[str, int]] = defaultdict(
        lambda: {"matches_played": 0, "wins": 0, "losses": 0, "draws": 0}
    )

    for match in matches:
        if not match.is_complete:
            continue

        if player_id not in match.all_player_ids:
            continue

        assert match.score_a is not None
        assert match.score_b is not None

        # Find partners (teammates)
        partners: list[int] = []
        in_team_a = player_id in match.team_a_player_ids

        if in_team_a:
            partners = [pid for pid in match.team_a_player_ids if pid != player_id]
            won = match.score_a > match.score_b
            lost = match.score_a < match.score_b
        else:
            partners = [pid for pid in match.team_b_player_ids if pid != player_id]
            won = match.score_b > match.score_a
            lost = match.score_b < match.score_a

        # Update partnership stats
        for partner_id in partners:
            partnerships[partner_id]["matches_played"] += 1
            if won:
                partnerships[partner_id]["wins"] += 1
            elif lost:
                partnerships[partner_id]["losses"] += 1
            else:
                partnerships[partner_id]["draws"] += 1

    return dict(partnerships)


def get_tournament_summary(
    players: list[Player],
    matches: list[Match],
) -> dict[str, int | float]:
    """Get high-level tournament summary statistics.

    Args:
        players: List of all players
        matches: List of all matches

    Returns:
        Dictionary with summary statistics
    """
    completed_matches = [m for m in matches if m.is_complete]

    total_points = sum((m.score_a or 0) + (m.score_b or 0) for m in completed_matches)

    avg_points_per_match = total_points / len(completed_matches) if completed_matches else 0.0

    # Count formats
    triplette_count = sum(1 for m in matches if m.format == TournamentMode.TRIPLETTE)
    doublette_count = sum(1 for m in matches if m.format == TournamentMode.DOUBLETTE)

    return {
        "total_players": len(players),
        "active_players": sum(1 for p in players if p.active),
        "total_matches": len(matches),
        "completed_matches": len(completed_matches),
        "pending_matches": len(matches) - len(completed_matches),
        "total_points_scored": total_points,
        "avg_points_per_match": round(avg_points_per_match, 2),
        "triplette_matches": triplette_count,
        "doublette_matches": doublette_count,
    }
