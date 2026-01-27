"""Tournament scheduler with constraint satisfaction.

This module implements the round generation logic with soft constraints:
- Minimize repeated partners
- Minimize repeated opponents
- Minimize repeated terrain assignments
- Minimize fallback format usage

It also provides a deterministic backtracking algorithm that guarantees
finding a solution if one exists, with progressive constraint relaxation.
"""

import random
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations

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


class ConstraintLevel:
    """Constraint levels for progressive relaxation."""

    STRICT = 0  # No repeated partners, no repeated opponents
    ALLOW_REPEATED_OPPONENTS = 1  # Allow opponents to repeat (max 2 times total)
    ALLOW_REPEATED_PARTNERS = 2  # Allow partners to repeat (max 2 times total)


class ConfigScoringMatchs:
    """Configuration for scoring matches."""

    repeated_partners_penalty: float = 10.0
    repeated_opponents_penalty: float = 5.0
    repeated_terrains_penalty: float = 2.0
    fallback_format_penalty_per_player: float = 1.5


@dataclass
class ConstraintTracker:
    """Tracks constraint violations across rounds."""

    matches: list[Match]

    def __init__(self, tournament_mode: TournamentMode) -> None:
        """Initialize tracker."""
        self.matches = []
        self.tournament_mode: TournamentMode = tournament_mode

    @property
    def partners(self) -> dict[int, set[int]]:
        """Get partners mapping. Set of partners per player."""
        players_id = {p_id for match in self.matches for p_id in match.all_player_ids}
        partners: dict[int, set[int]] = {pid: set() for pid in players_id}
        for match in self.matches:
            for team in [match.team_a_player_ids, match.team_b_player_ids]:
                for i, pid in enumerate(team):
                    for other in team[i + 1 :]:
                        partners[pid].add(other)
                        partners[other].add(pid)
        return partners

    @property
    def opponents(self) -> dict[int, set[int]]:
        """Get opponents mapping. Set of opponents per player."""
        players_id = {p_id for match in self.matches for p_id in match.all_player_ids}
        opponents: dict[int, set[int]] = {pid: set() for pid in players_id}
        for match in self.matches:
            for pid_a in match.team_a_player_ids:
                for pid_b in match.team_b_player_ids:
                    opponents[pid_a].add(pid_b)
                    opponents[pid_b].add(pid_a)
        return opponents

    @property
    def terrains(self) -> dict[int, set[str]]:
        """Get terrains mapping. Set of terrain labels per player."""
        players_id = {p_id for match in self.matches for p_id in match.all_player_ids}
        terrains: dict[int, set[str]] = {pid: set() for pid in players_id}
        for match in self.matches:
            for pid in match.all_player_ids:
                terrains[pid].add(match.terrain_label)
        return terrains

    @property
    def fallback_formats(self) -> dict[int, int]:
        """Get fallback format counts. Count of matches in fallback format per player."""
        players_id = {p_id for match in self.matches for p_id in match.all_player_ids}
        fallback_formats: dict[int, int] = dict.fromkeys(players_id, 0)
        for match in self.matches:
            is_fallback = (
                self.tournament_mode == TournamentMode.TRIPLETTE
                and match.format == MatchFormat.DOUBLETTE
            ) or (
                self.tournament_mode == TournamentMode.DOUBLETTE
                and match.format == MatchFormat.TRIPLETTE
            )

            if is_fallback:
                for pid in match.all_player_ids:
                    fallback_formats[pid] += 1
        return fallback_formats

    @property
    def partner_counts(self) -> dict[tuple[int, int], int]:
        """Get partner counts mapping. Count of times they've been partners (for relaxed constraints)"""
        partner_counts: dict[tuple[int, int], int] = defaultdict(int)
        for match in self.matches:
            for team in [match.team_a_player_ids, match.team_b_player_ids]:
                for i, pid1 in enumerate(team):
                    for pid2 in team[i + 1 :]:
                        pair = (min(pid1, pid2), max(pid1, pid2))
                        partner_counts[pair] += 1
        return partner_counts

    @property
    def opponent_counts(self) -> dict[tuple[int, int], int]:
        """Get opponent counts mapping. Count of times they've been opponents (for relaxed constraints)"""
        opponent_counts: dict[tuple[int, int], int] = defaultdict(int)
        for match in self.matches:
            for pid_a in match.team_a_player_ids:
                for pid_b in match.team_b_player_ids:
                    pair = (min(pid_a, pid_b), max(pid_a, pid_b))
                    opponent_counts[pair] += 1
        return opponent_counts

    def add_match(
        self,
        match: Match,
    ) -> None:
        """Record a match in the tracker.

        Args:
            match: Match to record
        """
        # Record partners (with counts for relaxed constraints)
        # Use indexed iteration to count each pair only once

        self.matches.append(match)

    def get_partner_count(self, pid1: int, pid2: int) -> int:
        """Get number of times two players have been partners."""
        pair = (min(pid1, pid2), max(pid1, pid2))
        return self.partner_counts[pair]

    def get_opponent_count(self, pid1: int, pid2: int) -> int:
        """Get number of times two players have been opponents."""
        pair = (min(pid1, pid2), max(pid1, pid2))
        return self.opponent_counts[pair]

    def score_match(
        self,
        team_a: list[int],
        team_b: list[int],
        terrain: str,
        match_format: MatchFormat,
    ) -> float:
        """Score a potential match based on constraint violations.

        Lower score is better (fewer violations).
        Uses squared counts for partners/opponents to strongly penalize repeated pairings.

        Args:
            team_a: Player IDs for team A
            team_b: Player IDs for team B
            terrain: Terrain label
            match_format: Match format

        Returns:
            Penalty score (lower is better)
        """
        score = 0.0

        # Check repeated partners - use squared count for strong penalty
        # penalty = base_penalty * count^2 (so 2x repeat = 4x penalty, 3x = 9x, etc.)
        for team in [team_a, team_b]:
            for i, pid in enumerate(team):
                for other in team[i + 1 :]:
                    count = self.get_partner_count(pid, other)
                    if count > 0:
                        score += ConfigScoringMatchs.repeated_partners_penalty * (count**2)

        # Check repeated opponents - use squared count
        for pid_a in team_a:
            for pid_b in team_b:
                count = self.get_opponent_count(pid_a, pid_b)
                if count > 0:
                    score += ConfigScoringMatchs.repeated_opponents_penalty * (count**2)

        # Check repeated terrains (medium penalty: 2 points per violation)
        terrains = self.terrains
        for pid in team_a + team_b:
            if pid in terrains and terrain in terrains[pid]:
                score += ConfigScoringMatchs.repeated_terrains_penalty

        # Check fallback format (medium penalty per player)
        is_fallback = (
            self.tournament_mode == TournamentMode.TRIPLETTE
            and match_format == MatchFormat.DOUBLETTE
        ) or (
            self.tournament_mode == TournamentMode.DOUBLETTE
            and match_format == MatchFormat.TRIPLETTE
        )

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
        self.tracker = ConstraintTracker(mode)

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
            self.tracker = ConstraintTracker(self.mode)

        for prev_round in previous_rounds:
            for match in prev_round.matches:
                self.tracker.add_match(match)

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

            temp_tracker = ConstraintTracker(self.mode)
            # Copy previous rounds' constraints
            for prev_round in previous_rounds:
                for match in prev_round.matches:
                    temp_tracker.add_match(match)
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

    def generate_round_deterministic(
        self,
        players: list[Player],
        round_index: int,
        previous_rounds: list[Round],
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> tuple[Round, ScheduleQualityReport, int]:
        """Generate a round using deterministic backtracking algorithm.

        This method guarantees finding a solution if one exists, using progressive
        constraint relaxation:
        1. First try: no repeated partners, no repeated opponents
        2. If fails: allow repeated opponents (max 2 times per pair)
        3. If fails: allow repeated partners (max 2 times per pair)

        Args:
            players: List of active players
            round_index: Index of this round (0-based)
            previous_rounds: Previously generated rounds
            progress_callback: Optional callback(level, message) for progress updates

        Returns:
            Tuple of (generated round, quality report, constraint_level_used)

        Raises:
            ValueError: If unable to generate valid round even with relaxed constraints
        """
        # Always rebuild tracker from scratch based on previous rounds
        # This ensures consistent state regardless of how the function is called
        self.tracker = ConstraintTracker(self.mode)
        for prev_round in previous_rounds:
            for match in prev_round.matches:
                self.tracker.add_match(match)

        player_count = len(players)
        if player_count < 4:
            raise ValueError("Need at least 4 players to generate matches")

        # Get optimal match distribution
        nb_3v3, nb_2v2, nb_3v2 = _find_optimal_match_distribution(player_count, self.mode)

        # Build all valid teams
        all_valid_teams = self._build_all_valid_teams(players)

        # Try each constraint level
        for level in [
            ConstraintLevel.STRICT,
            ConstraintLevel.ALLOW_REPEATED_OPPONENTS,
            ConstraintLevel.ALLOW_REPEATED_PARTNERS,
        ]:
            level_name = [
                "strict (no repeats)",
                "relaxed (allow repeated opponents)",
                "relaxed (allow repeated partners)",
            ][level]

            if progress_callback:
                progress_callback(level, f"Trying {level_name}...")

            matches = self._backtrack_find_matches(
                all_valid_teams=all_valid_teams,
                nb_3v3=nb_3v3,
                nb_2v2=nb_2v2,
                nb_3v2=nb_3v2,
                round_index=round_index,
                constraint_level=level,
            )

            if matches is not None:
                if progress_callback:
                    progress_callback(level, f"Found solution at level: {level_name}")

                # Generate quality report BEFORE updating tracker
                # so it correctly counts repetitions vs existing history
                quality_report = self._generate_quality_report(matches)

                # Now update tracker with the new matches for future rounds
                for match in matches:
                    self.tracker.add_match(match)

                round_obj = Round(index=round_index, matches=matches, quality_report=quality_report)
                return round_obj, quality_report, level

        raise ValueError(
            "Unable to generate valid round even with relaxed constraints. "
            "This may indicate too many rounds for the number of players."
        )

    def _build_all_valid_teams(
        self,
        players: list[Player],
    ) -> dict[MatchFormat, list[tuple[int, ...]]]:
        """Build all valid teams for each match format.

        Args:
            players: All available players

        Returns:
            Dictionary mapping format to list of valid teams (as tuples of player IDs)
        """
        valid_teams: dict[MatchFormat, list[tuple[int, ...]]] = {
            MatchFormat.TRIPLETTE: [],
            MatchFormat.DOUBLETTE: [],
        }

        player_ids = [p.id for p in players if p.id is not None]

        # Generate triplette teams (3 players)
        for combo_3 in combinations(player_ids, 3):
            team_players = [p for p in players if p.id in combo_3]
            if validate_team_roles(team_players, MatchFormat.TRIPLETTE, self.mode):
                valid_teams[MatchFormat.TRIPLETTE].append(combo_3)

        # Generate doublette teams (2 players)
        for combo_2 in combinations(player_ids, 2):
            team_players = [p for p in players if p.id in combo_2]
            if validate_team_roles(team_players, MatchFormat.DOUBLETTE, self.mode):
                valid_teams[MatchFormat.DOUBLETTE].append(combo_2)

        return valid_teams

    def _is_match_valid(
        self,
        team_a: tuple[int, ...],
        team_b: tuple[int, ...],
        constraint_level: int,
    ) -> bool:
        """Check if a match is valid given the constraint level.

        Args:
            team_a: Player IDs for team A
            team_b: Player IDs for team B
            constraint_level: Current constraint level

        Returns:
            True if match is valid, False otherwise
        """
        # Check no player overlap
        if set(team_a) & set(team_b):
            return False

        # Check partner constraints
        for team in [team_a, team_b]:
            for i, pid1 in enumerate(team):
                for pid2 in team[i + 1 :]:
                    count = self.tracker.get_partner_count(pid1, pid2)
                    if constraint_level < ConstraintLevel.ALLOW_REPEATED_PARTNERS:
                        # Strict or allow opponents only: no repeated partners
                        if count > 0:
                            return False
                    else:
                        # Allow repeated partners: max 2 times total
                        if count >= 2:
                            return False

        # Check opponent constraints
        for pid_a in team_a:
            for pid_b in team_b:
                count = self.tracker.get_opponent_count(pid_a, pid_b)
                if constraint_level < ConstraintLevel.ALLOW_REPEATED_OPPONENTS:
                    # Strict: no repeated opponents
                    if count > 0:
                        return False
                else:
                    # Allow repeated opponents: max 2 times total
                    if count >= 2:
                        return False

        return True

    def _backtrack_find_matches(
        self,
        all_valid_teams: dict[MatchFormat, list[tuple[int, ...]]],
        nb_3v3: int,
        nb_2v2: int,
        nb_3v2: int,
        round_index: int,
        constraint_level: int,
    ) -> list[Match] | None:
        """Use backtracking to find a valid set of matches.

        Args:
            all_valid_teams: All valid teams by format
            nb_3v3: Number of 3v3 matches needed
            nb_2v2: Number of 2v2 matches needed
            nb_3v2: Number of 3v2 hybrid matches needed
            round_index: Current round index
            constraint_level: Current constraint level

        Returns:
            List of matches if found, None otherwise
        """
        # Build list of match requirements
        match_requirements: list[tuple[MatchFormat, MatchFormat | None]] = []

        # 3v3 matches: both teams are triplettes
        for _ in range(nb_3v3):
            match_requirements.append((MatchFormat.TRIPLETTE, MatchFormat.TRIPLETTE))

        # 2v2 matches: both teams are doublettes
        for _ in range(nb_2v2):
            match_requirements.append((MatchFormat.DOUBLETTE, MatchFormat.DOUBLETTE))

        # 3v2 hybrid matches: one triplette, one doublette
        for _ in range(nb_3v2):
            match_requirements.append((MatchFormat.TRIPLETTE, MatchFormat.DOUBLETTE))

        if not match_requirements:
            return []

        # Start backtracking
        used_players: set[int] = set()
        matches: list[Match] = []

        # Create a temporary tracker to track constraints within this round
        temp_tracker = ConstraintTracker(self.mode)
        # Copy previous constraints
        temp_tracker.matches = self.tracker.matches.copy()

        result = self._backtrack_recursive(
            match_requirements=match_requirements,
            match_index=0,
            all_valid_teams=all_valid_teams,
            used_players=used_players,
            matches=matches,
            round_index=round_index,
            constraint_level=constraint_level,
            temp_tracker=temp_tracker,
        )

        return result

    def _backtrack_recursive(
        self,
        match_requirements: list[tuple[MatchFormat, MatchFormat | None]],
        match_index: int,
        all_valid_teams: dict[MatchFormat, list[tuple[int, ...]]],
        used_players: set[int],
        matches: list[Match],
        round_index: int,
        constraint_level: int,
        temp_tracker: ConstraintTracker,
    ) -> list[Match] | None:
        """Recursive backtracking to find valid matches.

        Args:
            match_requirements: List of (team_a_format, team_b_format) for each match
            match_index: Current match being filled
            all_valid_teams: All valid teams by format
            used_players: Set of already used player IDs
            matches: Current list of matches
            round_index: Current round index
            constraint_level: Current constraint level
            temp_tracker: Temporary tracker for this round

        Returns:
            List of matches if solution found, None otherwise
        """
        # Base case: all matches filled
        if match_index >= len(match_requirements):
            return matches.copy()

        format_a, format_b = match_requirements[match_index]

        # Get available teams for team A
        teams_a = [t for t in all_valid_teams[format_a] if not (set(t) & used_players)]

        for team_a in teams_a:
            # Mark team A players as used
            used_players.update(team_a)

            # Get available teams for team B
            if format_b is not None:
                teams_b = [t for t in all_valid_teams[format_b] if not (set(t) & used_players)]
            else:
                teams_b = [()]  # Placeholder for single-team formats

            for team_b in teams_b:
                if format_b is None:
                    continue

                # Check if this match is valid with current constraints
                if not self._is_match_valid_with_tracker(
                    team_a, team_b, constraint_level, temp_tracker
                ):
                    continue

                # Mark team B players as used
                used_players.update(team_b)

                # Determine match format
                if format_a == format_b:
                    match_format = format_a
                else:
                    match_format = MatchFormat.HYBRID

                # Create match
                terrain_label = get_terrain_label(match_index)
                match = Match(
                    round_index=round_index,
                    terrain_label=terrain_label,
                    format=match_format,
                    team_a_player_ids=list(team_a),
                    team_b_player_ids=list(team_b),
                )
                matches.append(match)

                # Update temp tracker
                self._add_match_to_temp_tracker(temp_tracker, match)

                # Recurse
                result = self._backtrack_recursive(
                    match_requirements=match_requirements,
                    match_index=match_index + 1,
                    all_valid_teams=all_valid_teams,
                    used_players=used_players,
                    matches=matches,
                    round_index=round_index,
                    constraint_level=constraint_level,
                    temp_tracker=temp_tracker,
                )

                if result is not None:
                    return result

                # Backtrack: remove match and restore tracker
                matches.pop()
                self._remove_match_from_temp_tracker(temp_tracker, match)
                used_players.difference_update(team_b)

            # Backtrack: restore team A players
            used_players.difference_update(team_a)

        return None

    def _is_match_valid_with_tracker(
        self,
        team_a: tuple[int, ...],
        team_b: tuple[int, ...],
        constraint_level: int,
        tracker: ConstraintTracker,
    ) -> bool:
        """Check if a match is valid using a specific tracker.

        Args:
            team_a: Player IDs for team A
            team_b: Player IDs for team B
            constraint_level: Current constraint level
            tracker: Constraint tracker to use

        Returns:
            True if match is valid, False otherwise
        """
        # Check partner constraints
        for team in [team_a, team_b]:
            for i, pid1 in enumerate(team):
                for pid2 in team[i + 1 :]:
                    count = tracker.get_partner_count(pid1, pid2)
                    if constraint_level < ConstraintLevel.ALLOW_REPEATED_PARTNERS:
                        if count > 0:
                            return False
                    else:
                        if count >= 2:
                            return False

        # Check opponent constraints
        for pid_a in team_a:
            for pid_b in team_b:
                count = tracker.get_opponent_count(pid_a, pid_b)
                if constraint_level < ConstraintLevel.ALLOW_REPEATED_OPPONENTS:
                    if count > 0:
                        return False
                else:
                    if count >= 2:
                        return False

        return True

    def _add_match_to_temp_tracker(
        self,
        tracker: ConstraintTracker,
        match: Match,
    ) -> None:
        """Add a match to a temporary tracker."""
        tracker.add_match(match)

    def _remove_match_from_temp_tracker(
        self,
        tracker: ConstraintTracker,
        match: Match,
    ) -> None:
        """Remove a match from a temporary tracker (for backtracking)."""
        tracker.matches.remove(match)

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
            tracker.add_match(match)
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
            tracker.add_match(match)
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
            tracker.add_match(match)
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
        # Count violations using tracker's count methods for accuracy
        repeated_partners = 0
        repeated_opponents = 0
        repeated_terrains = 0
        fallback_count = 0

        # Get cached properties once to avoid recomputing
        partners = self.tracker.partners
        opponents = self.tracker.opponents
        terrains = self.tracker.terrains

        for match in matches:
            # Check partners - count pairs that already exist in tracker
            for team in [match.team_a_player_ids, match.team_b_player_ids]:
                for i, pid in enumerate(team):
                    for other in team[i + 1 :]:
                        # Use get() to handle case where player not yet in tracker
                        if other in partners.get(pid, set()):
                            repeated_partners += 1

            # Check opponents
            for pid_a in match.team_a_player_ids:
                for pid_b in match.team_b_player_ids:
                    if pid_b in opponents.get(pid_a, set()):
                        repeated_opponents += 1

            # Check terrains
            for pid in match.all_player_ids:
                if match.terrain_label in terrains.get(pid, set()):
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

        total_score = self._score_matches(matches)

        return ScheduleQualityReport(
            repeated_partners=repeated_partners,
            repeated_opponents=repeated_opponents,
            repeated_terrains=repeated_terrains,
            fallback_format_count=fallback_count,
            total_score=total_score,
        )
