"""Tournament scheduler with constraint satisfaction.

This module implements the round generation logic with soft constraints:
- Minimize repeated partners
- Minimize repeated opponents
- Minimize repeated terrain assignments
- Minimize fallback format usage
"""

import random
from collections import defaultdict
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
                    score += 10.0

        for pid in team_b:
            for other in team_b:
                if pid != other and other in self.partners[pid]:
                    score += 10.0

        # Check repeated opponents (medium penalty: 5 points per violation)
        for pid_a in team_a:
            for pid_b in team_b:
                if pid_b in self.opponents[pid_a]:
                    score += 5.0

        # Check repeated terrains (medium penalty: 3 points per violation)
        for pid in team_a + team_b:
            if terrain in self.terrains[pid]:
                score += 3.0

        # Check fallback format (medium penalty: 4 points per player)
        is_fallback = (
            tournament_mode == TournamentMode.TRIPLETTE and match_format == MatchFormat.DOUBLETTE
        ) or (tournament_mode == TournamentMode.DOUBLETTE and match_format == MatchFormat.TRIPLETTE)

        if is_fallback:
            score += 4.0 * len(team_a + team_b)

        return score


def calculate_role_requirements(mode: TournamentMode, player_count: int) -> RoleRequirements:
    """Calculate required player counts by role.

    Args:
        mode: Tournament mode
        player_count: Total number of players

    Returns:
        Role requirements
    """
    if mode == TournamentMode.TRIPLETTE:
        # Prefer triplette: need 1 TIREUR, 1 POINTEUR, 1 MILIEU per team
        # For 6n players: n triplette matches = 2n teams = 2n of each role
        # For 6n+k players: adapt with doublettes

        triplette_teams = player_count // 3  # Max possible triplette teams
        # We need even number of teams
        if triplette_teams % 2 == 1:
            triplette_teams -= 1

        triplette_players = triplette_teams * 3
        remaining = player_count - triplette_players

        # Remaining players form doublette teams (if possible)
        doublette_teams = remaining // 2
        if doublette_teams % 2 == 1:
            doublette_teams -= 1

        # Triplette needs: equal counts of each role
        tireur_needed = triplette_teams
        pointeur_needed = triplette_teams
        milieu_needed = triplette_teams

        # Doublette needs: 1 TIREUR + 1 POINTEUR_MILIEU per team
        tireur_needed += doublette_teams
        pointeur_milieu_needed = doublette_teams

        return RoleRequirements(
            mode=mode,
            total_players=player_count,
            tireur_needed=tireur_needed,
            pointeur_needed=pointeur_needed,
            milieu_needed=milieu_needed,
            pointeur_milieu_needed=pointeur_milieu_needed,
        )
    else:  # DOUBLETTE
        # Prefer doublette: need 1 TIREUR, 1 POINTEUR_MILIEU per team
        # For 4n players: n doublette matches = 2n teams

        doublette_teams = player_count // 2
        if doublette_teams % 2 == 1:
            doublette_teams -= 1

        doublette_players = doublette_teams * 2
        remaining = player_count - doublette_players

        # Remaining players form triplette teams (if possible)
        triplette_teams = remaining // 3
        if triplette_teams % 2 == 1:
            triplette_teams -= 1

        # Doublette needs
        tireur_needed = doublette_teams
        pointeur_milieu_needed = doublette_teams

        # Triplette needs (fallback): map roles
        # For triplette in doublette mode: 1 TIREUR + 2 POINTEUR_MILIEU
        tireur_needed += triplette_teams
        pointeur_milieu_needed += triplette_teams * 2

        return RoleRequirements(
            mode=mode,
            total_players=player_count,
            tireur_needed=tireur_needed,
            pointeur_needed=0,
            milieu_needed=0,
            pointeur_milieu_needed=pointeur_milieu_needed,
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
    roles = [p.role for p in team]

    if match_format == MatchFormat.TRIPLETTE:
        if len(team) != 3:
            return False
        if mode == TournamentMode.TRIPLETTE:
            # Need exactly: 1 TIREUR, 1 POINTEUR, 1 MILIEU
            return (
                roles.count(PlayerRole.TIREUR) == 1
                and roles.count(PlayerRole.POINTEUR) == 1
                and roles.count(PlayerRole.MILIEU) == 1
            )
        else:
            # DOUBLETTE mode with triplette fallback: 1 TIREUR + 2 POINTEUR_MILIEU
            return (
                roles.count(PlayerRole.TIREUR) == 1 and roles.count(PlayerRole.POINTEUR_MILIEU) == 2
            )
    else:  # DOUBLETTE
        if len(team) != 2:
            return False
        if mode == TournamentMode.DOUBLETTE:
            # Need exactly: 1 TIREUR, 1 POINTEUR_MILIEU
            return (
                roles.count(PlayerRole.TIREUR) == 1 and roles.count(PlayerRole.POINTEUR_MILIEU) == 1
            )
        else:
            # TRIPLETTE mode with doublette fallback: 1 TIREUR + 1 POINTEUR (or MILIEU)
            return roles.count(PlayerRole.TIREUR) == 1 and (
                roles.count(PlayerRole.POINTEUR) == 1 or roles.count(PlayerRole.MILIEU) == 1
            )

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
    ) -> tuple[Round, ScheduleQualityReport]:
        """Generate a single round with matches.

        Args:
            players: List of active players
            round_index: Index of this round (0-based)
            previous_rounds: Previously generated rounds

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

        # Shuffle players for variety
        shuffled_players = players.copy()
        random.shuffle(shuffled_players)

        # Try multiple times to find best schedule
        best_matches: list[Match] | None = None
        best_score = float("inf")
        attempts = 50  # Try 50 different arrangements

        for attempt in range(attempts):
            if attempt > 0:
                random.shuffle(shuffled_players)

            try:
                matches = self._generate_matches_for_round(shuffled_players, round_index)
                score = self._score_matches(matches)

                if score < best_score:
                    best_score = score
                    best_matches = matches

                # If we found a perfect score, stop
                if score == 0:
                    break
            except ValueError:
                # This arrangement didn't work, try another
                continue

        if best_matches is None:
            raise ValueError("Unable to generate valid round after multiple attempts")

        # Generate quality report
        quality_report = self._generate_quality_report(best_matches)

        round_obj = Round(index=round_index, matches=best_matches)
        return round_obj, quality_report

    def _generate_matches_for_round(
        self,
        players: list[Player],
        round_index: int,
    ) -> list[Match]:
        """Generate matches for a round.

        Args:
            players: List of players
            round_index: Round index

        Returns:
            List of matches

        Raises:
            ValueError: If unable to form valid teams
        """
        matches: list[Match] = []
        available_players = players.copy()
        terrain_index = 0

        # Determine preferred format
        preferred_format = (
            MatchFormat.TRIPLETTE
            if self.mode == TournamentMode.TRIPLETTE
            else MatchFormat.DOUBLETTE
        )
        team_size = 3 if preferred_format == MatchFormat.TRIPLETTE else 2

        while len(available_players) >= team_size * 2 and terrain_index < self.terrains_count:
            # Try to form two teams with preferred format
            team_a = self._form_team(available_players, team_size, preferred_format)
            if team_a is None:
                # Try fallback format
                fallback_format = (
                    MatchFormat.DOUBLETTE
                    if preferred_format == MatchFormat.TRIPLETTE
                    else MatchFormat.TRIPLETTE
                )
                fallback_size = 2 if fallback_format == MatchFormat.DOUBLETTE else 3

                if len(available_players) >= fallback_size * 2:
                    team_a = self._form_team(available_players, fallback_size, fallback_format)
                    if team_a:
                        team_size = fallback_size
                        preferred_format = fallback_format

            if team_a is None:
                break

            # Remove team_a players
            for player in team_a:
                available_players.remove(player)

            # Form team B
            team_b = self._form_team(available_players, team_size, preferred_format)
            if team_b is None:
                # Can't form second team, put team_a back and stop
                available_players.extend(team_a)
                break

            # Remove team_b players
            for player in team_b:
                available_players.remove(player)

            # Create match
            terrain_label = get_terrain_label(terrain_index)
            match = Match(
                round_index=round_index,
                terrain_label=terrain_label,
                format=preferred_format,
                team_a_player_ids=[p.id for p in team_a if p.id is not None],
                team_b_player_ids=[p.id for p in team_b if p.id is not None],
            )
            matches.append(match)
            terrain_index += 1

            # Reset to preferred format for next match
            preferred_format = (
                MatchFormat.TRIPLETTE
                if self.mode == TournamentMode.TRIPLETTE
                else MatchFormat.DOUBLETTE
            )
            team_size = 3 if preferred_format == MatchFormat.TRIPLETTE else 2

        if not matches:
            raise ValueError("Could not generate any matches")

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
        if match_format == MatchFormat.TRIPLETTE:
            if self.mode == TournamentMode.TRIPLETTE:
                needed_roles = [PlayerRole.TIREUR, PlayerRole.POINTEUR, PlayerRole.MILIEU]
            else:
                needed_roles = [
                    PlayerRole.TIREUR,
                    PlayerRole.POINTEUR_MILIEU,
                    PlayerRole.POINTEUR_MILIEU,
                ]
        else:  # DOUBLETTE
            if self.mode == TournamentMode.DOUBLETTE:
                needed_roles = [PlayerRole.TIREUR, PlayerRole.POINTEUR_MILIEU]
            else:
                # Fallback in TRIPLETTE mode: 1 TIREUR + 1 (POINTEUR or MILIEU)
                needed_roles = [PlayerRole.TIREUR, PlayerRole.POINTEUR]  # Or MILIEU

        # Try to find players matching needed roles
        team: list[Player] = []
        remaining_roles = needed_roles.copy()
        remaining_players = available_players.copy()

        # Special handling for TRIPLETTE mode doublette fallback
        if (
            self.mode == TournamentMode.TRIPLETTE
            and match_format == MatchFormat.DOUBLETTE
            and len(remaining_roles) == 2
        ):
            # Need 1 TIREUR + 1 (POINTEUR or MILIEU)
            # Find TIREUR
            tireur = next((p for p in remaining_players if p.role == PlayerRole.TIREUR), None)
            if tireur is None:
                return None
            team.append(tireur)
            remaining_players.remove(tireur)

            # Find POINTEUR or MILIEU
            second = next(
                (
                    p
                    for p in remaining_players
                    if p.role in (PlayerRole.POINTEUR, PlayerRole.MILIEU)
                ),
                None,
            )
            if second is None:
                return None
            team.append(second)
            return team

        # Standard role matching
        for role in remaining_roles:
            player = next((p for p in remaining_players if p.role == role), None)
            if player is None:
                return None
            team.append(player)
            remaining_players.remove(player)

        return team if len(team) == team_size else None

    def _score_matches(self, matches: list[Match]) -> float:
        """Score a set of matches based on constraint violations.

        Args:
            matches: List of matches to score

        Returns:
            Total penalty score (lower is better)
        """
        total_score = 0.0
        for match in matches:
            score = self.tracker.score_match(
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

            # Check fallback
            is_fallback = (
                self.mode == TournamentMode.TRIPLETTE and match.format == MatchFormat.DOUBLETTE
            ) or (self.mode == TournamentMode.DOUBLETTE and match.format == MatchFormat.TRIPLETTE)

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
