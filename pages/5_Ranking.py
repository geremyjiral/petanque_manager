"""Ranking page showing player standings."""

from typing import Any

import pandas as pd
import streamlit as st

from app import get_storage
from src.core.models import PlayerRole
from src.core.stats import calculate_player_stats
from src.infra.auth import show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Ranking - Pétanque Tournament",
        page_icon="🏆",
        layout="wide",
    )

    show_login_form()

    st.title("🏆 Player Rankings")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Please configure the tournament on the home page first.")
        st.stop()

    # Get data
    players = storage.get_all_players(active_only=True)
    all_matches = storage.get_all_matches()

    if not players:
        st.info("👥 No players registered yet. Add players on the Players page.")
        st.stop()

    # Calculate stats
    player_stats = calculate_player_stats(players, all_matches)

    # Filters
    st.sidebar.header("🔍 Filters")

    min_matches = st.sidebar.number_input(
        "Minimum Matches Played",
        min_value=0,
        max_value=100,
        value=0,
        help="Filter players who have played at least this many matches",
    )

    role_filter = st.sidebar.multiselect(
        "Filter by Role",
        options=[r.value for r in PlayerRole],
        default=[],
        help="Select roles to display (empty = all)",
    )

    search_name = st.sidebar.text_input(
        "Search by Name",
        "",
        help="Filter players by name",
    )

    # Apply filters
    filtered_stats = player_stats

    if min_matches > 0:
        filtered_stats = [s for s in filtered_stats if s.matches_played >= min_matches]

    if role_filter:
        filtered_stats = [s for s in filtered_stats if s.role.value in role_filter]

    if search_name:
        filtered_stats = [s for s in filtered_stats if search_name.lower() in s.player_name.lower()]

    # Summary metrics
    st.header("📊 Tournament Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Players", len(player_stats))

    with col2:
        players_with_matches = sum(1 for s in player_stats if s.matches_played > 0)
        st.metric("Players with Matches", players_with_matches)

    with col3:
        completed_matches = [m for m in all_matches if m.is_complete]
        st.metric("Completed Matches", len(completed_matches))

    with col4:
        if player_stats and player_stats[0].matches_played > 0:
            st.metric("Leader", player_stats[0].player_name)

    st.markdown("---")

    # Rankings table
    st.header("📋 Rankings")

    if not filtered_stats:
        st.info("No players match the selected filters.")
    else:
        # Create dataframe
        ranking_data: list[dict[str, Any]] = []
        for idx, stat in enumerate(filtered_stats, 1):
            ranking_data.append(
                {
                    "Rank": idx,
                    "Player": stat.player_name,
                    "Role": stat.role.value,
                    "Matches": stat.matches_played,
                    "Wins": stat.wins,
                    "Losses": stat.losses,
                    "Win %": f"{stat.win_rate:.1f}%",
                    "Points For": stat.points_for,
                    "Points Against": stat.points_against,
                    "Goal Avg": stat.goal_average,
                }
            )

        df_ranking = pd.DataFrame(ranking_data)

        # Style the dataframe
        st.dataframe(  # pyright: ignore[reportUnknownMemberType]
            df_ranking,
            width="stretch",
            hide_index=True,
            column_config={
                "Rank": st.column_config.NumberColumn(
                    "Rank",
                    help="Player ranking position",
                    format="%d",
                ),
                "Player": st.column_config.TextColumn(
                    "Player",
                    help="Player name",
                    width="medium",
                ),
                "Role": st.column_config.TextColumn(
                    "Role",
                    help="Player role",
                    width="small",
                ),
                "Matches": st.column_config.NumberColumn(
                    "Matches",
                    help="Total matches played",
                ),
                "Wins": st.column_config.NumberColumn(
                    "Wins",
                    help="Total wins",
                ),
                "Losses": st.column_config.NumberColumn(
                    "Losses",
                    help="Total losses",
                ),
                "Win %": st.column_config.TextColumn(
                    "Win %",
                    help="Win percentage",
                ),
                "Points For": st.column_config.NumberColumn(
                    "Points For",
                    help="Total points scored",
                ),
                "Points Against": st.column_config.NumberColumn(
                    "Points Against",
                    help="Total points conceded",
                ),
                "Goal Avg": st.column_config.NumberColumn(
                    "Goal Avg",
                    help="Points For - Points Against",
                ),
            },
        )

        # Export rankings
        if st.button("📥 Export Rankings to CSV"):
            csv = df_ranking.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="tournament_rankings.csv",
                mime="text/csv",
            )

    # Top performers
    st.header("🌟 Top Performers")

    if player_stats and player_stats[0].matches_played > 0:
        top_col1, top_col2, top_col3 = st.columns(3)

        with top_col1:
            st.subheader("🥇 Most Wins")
            top_wins = sorted(
                [s for s in player_stats if s.matches_played >= min_matches],
                key=lambda s: s.wins,
                reverse=True,
            )[:5]

            for idx, stat in enumerate(top_wins, 1):
                st.markdown(
                    f"{idx}. **{stat.player_name}** - {stat.wins} wins ({stat.matches_played} matches)"
                )

        with top_col2:
            st.subheader("🎯 Best Win Rate")
            top_win_rate = sorted(
                [s for s in player_stats if s.matches_played >= max(min_matches, 3)],
                key=lambda s: s.win_rate,
                reverse=True,
            )[:5]

            for idx, stat in enumerate(top_win_rate, 1):
                st.markdown(
                    f"{idx}. **{stat.player_name}** - {stat.win_rate:.1f}% "
                    f"({stat.wins}/{stat.matches_played})"
                )

        with top_col3:
            st.subheader("📊 Best Goal Average")
            top_goal_avg = sorted(
                [s for s in player_stats if s.matches_played >= min_matches],
                key=lambda s: s.goal_average,
                reverse=True,
            )[:5]

            for idx, stat in enumerate(top_goal_avg, 1):
                st.markdown(
                    f"{idx}. **{stat.player_name}** - {stat.goal_average:+d} "
                    f"({stat.points_for}/{stat.points_against})"
                )

    else:
        st.info("No completed matches yet. Results will appear once matches are played.")

    # Role-based rankings
    st.header("👥 Rankings by Role")

    role_tabs = st.tabs([r.value for r in PlayerRole])

    for idx, role in enumerate(PlayerRole):
        with role_tabs[idx]:
            role_stats = [s for s in player_stats if s.role == role and s.matches_played > 0]

            if not role_stats:
                st.info(f"No {role.value} players with completed matches yet.")
            else:
                role_data: list[dict[str, Any]] = []
                for rank_idx, stat in enumerate(role_stats, 1):
                    role_data.append(
                        {
                            "Rank": rank_idx,
                            "Player": stat.player_name,
                            "Matches": stat.matches_played,
                            "Wins": stat.wins,
                            "Win %": f"{stat.win_rate:.1f}%",
                            "Goal Avg": stat.goal_average,
                        }
                    )

                df_role = pd.DataFrame(role_data)
                st.dataframe(df_role, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

    # Ranking explanation
    with st.expander("ℹ️ How Rankings Work", expanded=False):
        st.markdown(
            """
        ### Ranking Criteria

        Players are ranked by the following criteria (in order):

        1. **Wins** (descending): Players with more wins rank higher
        2. **Goal Average** (descending): Points For - Points Against
        3. **Points For** (descending): Total points scored
        4. **Name** (alphabetical): Tie-breaker

        ### Metrics Explained

        - **Matches**: Total number of matches played
        - **Wins**: Number of matches won
        - **Losses**: Number of matches lost
        - **Win %**: Percentage of matches won (Wins / Matches × 100)
        - **Points For**: Total points scored across all matches
        - **Points Against**: Total points conceded across all matches
        - **Goal Average**: Points For - Points Against (higher is better)

        ### Tips

        - Use filters to focus on specific player groups
        - Minimum matches filter helps compare players with similar experience
        - Export rankings to CSV for external analysis
        """
        )

    st.markdown("---")
    st.caption("Rankings update automatically as match results are entered.")


if __name__ == "__main__":
    main()
