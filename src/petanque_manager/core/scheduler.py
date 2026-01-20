"""Tournament scheduler with constraint satisfaction.

This module implements the round generation logic with soft constraints:
- Minimize repeated partners
- Minimize repeated opponents
- Minimize repeated terrain assignments
- Minimize fallback format usage
"""

import random
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from src.petanque_manager.core.models import (
    Match,
    MatchFormat,
    Player,
    PlayerRole,
    RoleRequirements,
    Round,
    ScheduleQualityReport,
    TournamentMode,
)
from src.petanque_manager.utils.seed import set_random_seed
from src.petanque_manager.utils.terrain_labels import get_terrain_label


class ConfigScoringMatchs:
    """Configuration for scoring matches."""

    repeated_partners_penalty: float = 10.0
    repeated_opponents_penalty: float = 5.0
    repeated_terrains_penalty: float = 2.0
    fallback_format_penalty_per_player: float = 1.5


@dataclass
class ConstraintTracker:
    """Tracks constraint violations across rounds."""

    # player_id -> set of player_ids they've played WITH
    partners: dict[int, set[int]]
    # player_id -> set of player_ids they've played AGAINST
    opponents: dict[int, set[int]]
    # player_id -> set of terrain labels they've played on
    terrains: dict[int, set[str]]
    # player_id -> count of matches in fallback format
    fallback_formats: dict[int, int]

    def __init__(self) -> None:
        """Initialize empty tracker."""
        self.partners = defaultdict(set)
        self.opponents = defaultdict(set)
        self.terrains = defaultdict(set)
        self.fallback_formats = defaultdict(int)

    def add_match(
        self,
        match: Match,
        tournament_mode: TournamentMode,
    ) -> None:
        """Record a match in the tracker.

        Args:
            match: Match to record
            tournament_mode: Current tournament mode (to detect fallback format)
        """
        # Record partners
        for pid in match.team_a_player_ids:
            for other in match.team_a_player_ids:
                if pid != other:
                    self.partners[pid].add(other)

        for pid in match.team_b_player_ids:
            for other in match.team_b_player_ids:
                if pid != other:
                    self.partners[pid].add(other)

        # Record opponents
        for pid_a in match.team_a_player_ids:
            for pid_b in match.team_b_player_ids:
                self.opponents[pid_a].add(pid_b)
                self.opponents[pid_b].add(pid_a)

        # Record terrains
        for pid in match.all_player_ids:
            self.terrains[pid].add(match.terrain_label)

        # Record fallback format
        is_fallback = (
            tournament_mode == TournamentMode.TRIPLETTE and match.format == MatchFormat.DOUBLETTE
        ) or (tournament_mode == TournamentMode.DOUBLETTE and match.format == MatchFormat.TRIPLETTE)

        if is_fallback:
            for pid in match.all_player_ids:
                self.fallback_formats[pid] += 1

    def score_match(
        self,
        team_a: list[int],
        team_b: list[int],
        terrain: str,
        match_format: MatchFormat,
        tournament_mode: TournamentMode,
    ) -> float:
        """Score a potential match based on constraint violations.

        Lower score is better (fewer violations).

        Args:
            team_a: Player IDs for team A
            team_b: Player IDs for team B
            terrain: Terrain label
            match_format: Match format
            tournament_mode: Tournament mode

        Returns:
            Penalty score (lower is better)
        """
        score = 0.0

        # Check repeated partners (strong penalty: 10 points per violation)
        for pid in team_a:
            for other in team_a:
                if pid != other and other in self.partners[pid]:
                    score += ConfigScoringMatchs.repeated_partners_penalty

        for pid in team_b:
            for other in team_b:
                if pid != other and other in self.partners[pid]:
                    score += ConfigScoringMatchs.repeated_partners_penalty

        # Check repeated opponents (medium penalty: 5 points per violation)
        for pid_a in team_a:
            for pid_b in team_b:
                if pid_b in self.opponents[pid_a]:
                    score += ConfigScoringMatchs.repeated_opponents_penalty

        # Check repeated terrains (medium penalty: 2 points per violation)
        for pid in team_a + team_b:
            if terrain in self.terrains[pid]:
                score += ConfigScoringMatchs.repeated_terrains_penalty

        # Check fallback format (medium penalty: 4 points per player)
        is_fallback = (
            tournament_mode == TournamentMode.TRIPLETTE and match_format == MatchFormat.DOUBLETTE
        ) or (tournament_mode == TournamentMode.DOUBLETTE and match_format == MatchFormat.TRIPLETTE)

        if is_fallback:
            score += ConfigScoringMatchs.fallback_format_penalty_per_player * len(team_a + team_b)

        return score


def _find_optimal_match_distribution(
    player_count: int, mode: TournamentMode
) -> tuple[int, int, int]:
    """Find the optimal distribution of matches to include ALL players.

    Strategy:
    - Triplette match (3v3): 6 players
    - Doublette match (2v2): 4 players
    - Hybrid match (3v2): 5 players (used when necessary to avoid benching)

    Returns:
        (nb_triplette_matches, nb_doublette_matches, nb_hybrid_matches)
    """
    if player_count < 4:
        # Not enough players for any match
        return (0, 0, 0)

    best_solution: tuple[int, int, int] = (0, 0, 0)
    best_bench = player_count  # Worst case: everyone benched

    # Try all possible combinations
    max_3v3 = player_count // 6
    max_2v2 = player_count // 4
    max_3v2 = player_count // 5

    for nb_3v3 in range(max_3v3 + 1):
        for nb_2v2 in range(max_2v2 + 1):
            for nb_3v2 in range(max_3v2 + 1):
                players_used = nb_3v3 * 6 + nb_2v2 * 4 + nb_3v2 * 5
                bench = player_count - players_used

                if bench < 0:
                    continue

                # Prioritize solutions with fewer benched players
                if bench < best_bench:
                    best_bench = bench
                    best_solution = (nb_3v3, nb_2v2, nb_3v2)
                elif bench == best_bench and best_solution:
                    # Same bench count, choose based on preferences
                    old_3v3, old_2v2, old_3v2 = best_solution

                    if mode == TournamentMode.TRIPLETTE:
                        # Prefer: more 3v3, fewer hybrids, then more 2v2
                        if nb_3v3 > old_3v3:
                            best_solution = (nb_3v3, nb_2v2, nb_3v2)
                        elif nb_3v3 == old_3v3 and nb_3v2 < old_3v2:
                            best_solution = (nb_3v3, nb_2v2, nb_3v2)
                    else:  # DOUBLETTE mode
                        # Prefer: more 2v2, fewer hybrids, then more 3v3
                        if nb_2v2 > old_2v2:
                            best_solution = (nb_3v3, nb_2v2, nb_3v2)
                        elif nb_2v2 == old_2v2 and nb_3v2 < old_3v2:
                            best_solution = (nb_3v3, nb_2v2, nb_3v2)

    return best_solution or (0, 0, 0)


def calculate_role_requirements(mode: TournamentMode, player_count: int) -> RoleRequirements:
    """Calculate required player counts by role.

    New strategy: Find optimal combination to include ALL players.
    Accepts hybrid 3v2 matches if needed to avoid benching players.

    Args:
        mode: Tournament mode
        player_count: Total number of players

    Returns:
        Role requirements
    """
    # Find optimal distribution
    nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(player_count, mode)

    # Calculate team counts (NOT including hybrid teams here, they're separate)
    triplette_teams = nb_3v3 * 2  # Each 3v3 match = 2 triplette teams
    doublette_teams = nb_2v2 * 2  # Each 2v2 match = 2 doublette teams

    # For role calculations, we need to count ALL teams including hybrid
    total_triplette_teams = triplette_teams + nb_3v2  # Hybrid contributes 1 triplette team
    total_doublette_teams = doublette_teams + nb_3v2  # Hybrid contributes 1 doublette team

    tireur_needed = total_doublette_teams + total_triplette_teams
    pointeur_needed = total_doublette_teams + total_triplette_teams
    milieu_needed = total_triplette_teams

    return RoleRequirements(
        mode=mode,
        total_players=player_count,
        tireur_needed=tireur_needed,
        pointeur_needed=pointeur_needed,
        milieu_needed=milieu_needed,
        triplette_count=nb_3v3,
        doublette_count=nb_2v2,
        hybrid_count=nb_3v2,
    )


def validate_team_roles(
    team: list[Player], match_format: MatchFormat, mode: TournamentMode
) -> bool:
    """Validate that a team has the correct role composition.

    Args:
        team: List of players
        match_format: Format of the match
        mode: Tournament mode

    Returns:
        True if valid, False otherwise
    """
    if match_format == MatchFormat.TRIPLETTE:
        if len(team) != 3:
            return False
        if mode == TournamentMode.TRIPLETTE:
            # Need exactly: 1 TIREUR, 1 POINTEUR, 1 MILIEU
            has_tireur = sum(1 for p in team if PlayerRole.TIREUR in p.roles)
            has_pointeur = sum(1 for p in team if PlayerRole.POINTEUR in p.roles)
            has_milieu = sum(1 for p in team if PlayerRole.MILIEU in p.roles)
            return has_tireur >= 1 and has_pointeur >= 1 and has_milieu >= 1
        else:
            # DOUBLETTE mode with triplette fallback: 1 TIREUR + 2 (POINTEUR or MILIEU)
            has_tireur = sum(1 for p in team if PlayerRole.TIREUR in p.roles)
            has_pointeur_or_milieu = sum(
                1 for p in team if PlayerRole.POINTEUR in p.roles or PlayerRole.MILIEU in p.roles
            )
            return has_tireur >= 1 and has_pointeur_or_milieu >= 2
    else:  # DOUBLETTE
        if len(team) != 2:
            return False
        if mode == TournamentMode.DOUBLETTE:
            # Need exactly: 1 TIREUR, 1 (POINTEUR or MILIEU)
            has_tireur = sum(1 for p in team if PlayerRole.TIREUR in p.roles)
            has_pointeur_or_milieu = sum(
                1 for p in team if PlayerRole.POINTEUR in p.roles or PlayerRole.MILIEU in p.roles
            )
            return has_tireur >= 1 and has_pointeur_or_milieu >= 1
        else:
            # TRIPLETTE mode with doublette fallback: 1 TIREUR + 1 (POINTEUR or MILIEU)
            has_tireur = sum(1 for p in team if PlayerRole.TIREUR in p.roles)
            has_pointeur_or_milieu = sum(
                1 for p in team if PlayerRole.POINTEUR in p.roles or PlayerRole.MILIEU in p.roles
            )
            return has_tireur >= 1 and has_pointeur_or_milieu >= 1

    return False


class TournamentScheduler:
    """Generates tournament schedules with constraint satisfaction."""

    def __init__(
        self,
        mode: TournamentMode,
        terrains_count: int,
        seed: int | None = None,
    ):
        """Initialize scheduler.

        Args:
            mode: Tournament mode (TRIPLETTE or DOUBLETTE)
            terrains_count: Number of available terrains
            seed: Random seed for reproducibility
        """
        self.mode = mode
        self.terrains_count = terrains_count
        self.seed = seed
        self.tracker = ConstraintTracker()

        if seed is not None:
            set_random_seed(seed)

    def generate_round(
        self,
        players: list[Player],
        round_index: int,
        previous_rounds: list[Round],
        attempts: int = 500,
        progress_callback: Callable[[int, int, float], None] | None = None,
    ) -> tuple[Round, ScheduleQualityReport, int]:
        """Generate a single round with matches.


        Args:
            players: List of active players
            round_index: Index of this round (0-based)
            previous_rounds: Previously generated rounds
            attempts: Number of shuffles to try (default: 100, balanced for quality/performance)
            progress_callback: Optional callback(attempt, total_attempts, best_score) for progress updates

        Returns:
            Tuple of (generated round, quality report)

        Raises:
            ValueError: If unable to generate valid round
        """
        # Update tracker with previous rounds
        if round_index == 0:
            self.tracker = ConstraintTracker()

        for prev_round in previous_rounds:
            for match in prev_round.matches:
                self.tracker.add_match(match, self.mode)

        # Determine match composition
        player_count = len(players)
        if player_count < 4:
            raise ValueError("Need at least 4 players to generate matches")

        players_by_role: dict[PlayerRole, list[Player]] = {
            PlayerRole.TIREUR: [],
            PlayerRole.POINTEUR: [],
            PlayerRole.MILIEU: [],
        }
        for player in players:
            for role in player.roles:
                players_by_role[role].append(player)

        # Store in instance for use in _form_team
        self._players_by_role = players_by_role

        # Shuffle players for variety
        shuffled_players = players.copy()
        random.shuffle(shuffled_players)

        # Try multiple times to find best schedule
        best_matches: list[Match] | None = None
        best_score = float("inf")

        good_enough_threshold = 10.0
        min_attempts_before_early_stop = 100  # Minimum attempts before considering early stop
        attempt = 0
        for attempt in range(attempts):
            if attempt > 0:
                random.shuffle(shuffled_players)

            temp_tracker = ConstraintTracker()
            # Copy previous rounds' constraints
            for prev_round in previous_rounds:
                for match in prev_round.matches:
                    temp_tracker.add_match(match, self.mode)

            try:
                matches = self._generate_matches_for_round(
                    shuffled_players, round_index, temp_tracker
                )
                score = self._score_matches_with_tracker(matches, temp_tracker)

                if score < best_score:
                    best_score = score
                    best_matches = matches

                    # Call progress callback if provided
                    if progress_callback is not None:
                        progress_callback(attempt + 1, attempts, best_score)

                if score == 0:
                    # Perfect score (A+) - no need to continue
                    break
                if score < good_enough_threshold and attempt >= min_attempts_before_early_stop:
                    # Grade A score after sufficient attempts - good enough
                    break
            except ValueError:
                # This arrangement didn't work, try another
                continue

        if best_matches is None:
            raise ValueError("Unable to generate valid round after multiple attempts")

        # Generate quality report
        quality_report = self._generate_quality_report(best_matches)

        round_obj = Round(index=round_index, matches=best_matches, quality_report=quality_report)
        return round_obj, quality_report, attempt + 1

    def _generate_matches_for_round(
        self,
        players: list[Player],
        round_index: int,
        tracker: ConstraintTracker,
    ) -> list[Match]:
        """Generate matches for a round using optimal distribution.

        New strategy: Use _find_optimal_match_distribution to determine
        the best mix of 3v3, 2v2, and 3v2 matches to include ALL players.

        Args:
            players: List of players
            round_index: Round index
            tracker: Constraint tracker to update as matches are created

        Returns:
            List of matches

        Raises:
            ValueError: If unable to form valid teams
        """
        matches: list[Match] = []
        available_players = players.copy()
        terrain_index = 0

        # Get optimal distribution
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(len(players), self.mode)

        # Generate 3v3 matches
        for _ in range(nb_3v3):
            if len(available_players) < 6:
                break

            team_a = self._form_team(available_players, 3, MatchFormat.TRIPLETTE)
            if team_a is None:
                break

            for player in team_a:
                available_players.remove(player)

            team_b = self._form_team(available_players, 3, MatchFormat.TRIPLETTE)
            if team_b is None:
                # Can't form second team, put team_a back
                available_players.extend(team_a)
                break

            for player in team_b:
                available_players.remove(player)

            terrain_label = get_terrain_label(terrain_index)
            match = Match(
                round_index=round_index,
                terrain_label=terrain_label,
                format=MatchFormat.TRIPLETTE,
                team_a_player_ids=[p.id for p in team_a if p.id is not None],
                team_b_player_ids=[p.id for p in team_b if p.id is not None],
            )
            matches.append(match)
            tracker.add_match(match, self.mode)
            terrain_index += 1

        # Generate 2v2 matches
        for _ in range(nb_2v2):
            if len(available_players) < 4:
                break

            team_a = self._form_team(available_players, 2, MatchFormat.DOUBLETTE)
            if team_a is None:
                break

            for player in team_a:
                available_players.remove(player)

            team_b = self._form_team(available_players, 2, MatchFormat.DOUBLETTE)
            if team_b is None:
                available_players.extend(team_a)
                break

            for player in team_b:
                available_players.remove(player)

            terrain_label = get_terrain_label(terrain_index)
            match = Match(
                round_index=round_index,
                terrain_label=terrain_label,
                format=MatchFormat.DOUBLETTE,
                team_a_player_ids=[p.id for p in team_a if p.id is not None],
                team_b_player_ids=[p.id for p in team_b if p.id is not None],
            )
            matches.append(match)
            tracker.add_match(match, self.mode)
            terrain_index += 1

        # Generate 3v2 hybrid matches
        for _ in range(nb_3v2):
            if len(available_players) < 5:
                break

            # Form triplette team first
            team_3 = self._form_team(available_players, 3, MatchFormat.TRIPLETTE)
            if team_3 is None:
                break

            for player in team_3:
                available_players.remove(player)

            # Form doublette team
            team_2 = self._form_team(available_players, 2, MatchFormat.DOUBLETTE)
            if team_2 is None:
                available_players.extend(team_3)
                break

            for player in team_2:
                available_players.remove(player)

            terrain_label = get_terrain_label(terrain_index)
            match = Match(
                round_index=round_index,
                terrain_label=terrain_label,
                format=MatchFormat.HYBRID,
                team_a_player_ids=[p.id for p in team_3 if p.id is not None],
                team_b_player_ids=[p.id for p in team_2 if p.id is not None],
            )
            matches.append(match)
            tracker.add_match(match, self.mode)
            terrain_index += 1

        if not matches:
            raise ValueError("Could not generate any matches")

        expected_matches = nb_3v3 + nb_2v2 + nb_3v2
        if len(matches) != expected_matches:
            # Log details for debugging
            actual_players_used = sum(len(m.all_player_ids) for m in matches)
            raise ValueError(
                f"Match generation error: Expected {expected_matches} matches "
                f"(3v3={nb_3v3}, 2v2={nb_2v2}, 3v2={nb_3v2}) but generated {len(matches)}. "
                f"Players: {len(players)} total, {actual_players_used} used in matches. "
                f"This may indicate insufficient players with required roles or a logic error."
            )

        return matches

    def _form_team(
        self,
        available_players: list[Player],
        team_size: int,
        match_format: MatchFormat,
    ) -> list[Player] | None:
        """Form a team with correct role composition.

        Args:
            available_players: Players to choose from
            team_size: Size of team (2 or 3)
            match_format: Format of match

        Returns:
            List of players forming a valid team, or None if impossible
        """
        # Required roles based on format and mode
        # Each item is either a single role or a list of alternative roles
        needed_roles: list[PlayerRole | list[PlayerRole]] = []

        if match_format == MatchFormat.TRIPLETTE:
            if self.mode == TournamentMode.TRIPLETTE:
                # Need: 1 TIREUR, 1 POINTEUR, 1 MILIEU
                needed_roles = [PlayerRole.TIREUR, PlayerRole.POINTEUR, PlayerRole.MILIEU]
            else:
                # DOUBLETTE mode with triplette fallback: 1 TIREUR + 2 (POINTEUR or MILIEU)
                needed_roles = [
                    PlayerRole.TIREUR,
                    [PlayerRole.POINTEUR, PlayerRole.MILIEU],
                    [PlayerRole.POINTEUR, PlayerRole.MILIEU],
                ]
        else:  # DOUBLETTE
            if self.mode == TournamentMode.DOUBLETTE:
                # Need: 1 TIREUR, 1 (POINTEUR or MILIEU)
                needed_roles = [PlayerRole.TIREUR, [PlayerRole.POINTEUR, PlayerRole.MILIEU]]
            else:
                # TRIPLETTE mode with doublette fallback: 1 TIREUR + 1 (POINTEUR or MILIEU)
                needed_roles = [PlayerRole.TIREUR, [PlayerRole.POINTEUR, PlayerRole.MILIEU]]

        available_ids = {p.id for p in available_players if p.id is not None}
        team: list[Player] = []
        used_ids: set[int] = set()  # Track used player IDs to avoid duplicates

        for needed_role in needed_roles:
            player = None

            # Handle both single role and list of alternative roles
            if isinstance(needed_role, list):
                # Try each role in priority order
                for role in needed_role:
                    candidates = self._players_by_role.get(role, []).copy()
                    random.shuffle(candidates)

                    for candidate in candidates:
                        if (
                            candidate.id is not None
                            and candidate.id in available_ids
                            and candidate.id not in used_ids
                        ):
                            player = candidate
                            break
                    if player is not None:
                        break
            else:
                # Single specific role
                candidates = self._players_by_role.get(needed_role, []).copy()
                random.shuffle(candidates)

                for candidate in candidates:
                    if (
                        candidate.id is not None
                        and candidate.id in available_ids
                        and candidate.id not in used_ids
                    ):
                        player = candidate
                        break

            if player is None:
                return None

            team.append(player)
            if player.id is not None:
                used_ids.add(player.id)

        return team if len(team) == team_size else None

    def _score_matches(self, matches: list[Match]) -> float:
        """Score a set of matches based on constraint violations.

        Args:
            matches: List of matches to score

        Returns:
            Total penalty score (lower is better)
        """
        return self._score_matches_with_tracker(matches, self.tracker)

    def _score_matches_with_tracker(
        self, matches: list[Match], tracker: ConstraintTracker
    ) -> float:
        """Score a set of matches using a specific tracker.

        Args:
            matches: List of matches to score
            tracker: Constraint tracker to use for scoring

        Returns:
            Total penalty score (lower is better)
        """
        total_score = 0.0
        for match in matches:
            score = tracker.score_match(
                match.team_a_player_ids,
                match.team_b_player_ids,
                match.terrain_label,
                match.format,
                self.mode,
            )
            total_score += score
        return total_score

    def _generate_quality_report(self, matches: list[Match]) -> ScheduleQualityReport:
        """Generate quality report for a round.

        Args:
            matches: Matches in the round

        Returns:
            Quality report
        """
        # Count violations
        repeated_partners = 0
        repeated_opponents = 0
        repeated_terrains = 0
        fallback_count = 0

        for match in matches:
            # Check partners
            for pid in match.team_a_player_ids:
                for other in match.team_a_player_ids:
                    if pid != other and other in self.tracker.partners[pid]:
                        repeated_partners += 1

            for pid in match.team_b_player_ids:
                for other in match.team_b_player_ids:
                    if pid != other and other in self.tracker.partners[pid]:
                        repeated_partners += 1

            # Check opponents
            for pid_a in match.team_a_player_ids:
                for pid_b in match.team_b_player_ids:
                    if pid_b in self.tracker.opponents[pid_a]:
                        repeated_opponents += 1

            # Check terrains
            for pid in match.all_player_ids:
                if match.terrain_label in self.tracker.terrains[pid]:
                    repeated_terrains += 1

            # Check fallback/hybrid
            # Hybrid is always considered a "fallback" (compromise)
            # Pure wrong format is also a fallback
            is_fallback = (
                match.format == MatchFormat.HYBRID
                or (self.mode == TournamentMode.TRIPLETTE and match.format == MatchFormat.DOUBLETTE)
                or (self.mode == TournamentMode.DOUBLETTE and match.format == MatchFormat.TRIPLETTE)
            )

            if is_fallback:
                fallback_count += 1

        # Divide by 2 for partners and opponents (counted twice)
        repeated_partners //= 2
        repeated_opponents //= 2

        total_score = self._score_matches(matches)

        return ScheduleQualityReport(
            repeated_partners=repeated_partners,
            repeated_opponents=repeated_opponents,
            repeated_terrains=repeated_terrains,
            fallback_format_count=fallback_count,
            total_score=total_score,
        )
