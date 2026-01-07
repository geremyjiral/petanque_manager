"""Dashboard page with tournament overview and statistics."""

from typing import Any

import pandas as pd
import streamlit as st

from app import get_storage
from src.core.stats import get_tournament_summary
from src.infra.auth import show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Dashboard - Pétanque Tournament",
        page_icon="📊",
        layout="wide",
    )

    show_login_form()

    st.title("📊 Tournament Dashboard")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Please configure the tournament on the home page first.")
        st.stop()

    # Get data
    players = storage.get_all_players(active_only=True)
    all_rounds = storage.get_all_rounds()
    all_matches = storage.get_all_matches()

    # Summary statistics
    summary = get_tournament_summary(players, all_matches)

    st.header("📈 Tournament Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Players", summary["total_players"])
        st.metric("Active Players", summary["active_players"])

    with col2:
        st.metric("Total Matches", summary["total_matches"])
        st.metric("Completed Matches", summary["completed_matches"])

    with col3:
        st.metric("Total Rounds", len(all_rounds))
        st.metric("Pending Matches", summary["pending_matches"])

    with col4:
        st.metric("Total Points", summary["total_points_scored"])
        st.metric("Avg Points/Match", summary["avg_points_per_match"])

    # Match format distribution
    st.subheader("🎯 Match Format Distribution")

    format_col1, format_col2 = st.columns(2)

    with format_col1:
        st.metric(
            "Triplette Matches",
            summary["triplette_matches"],
            help="3v3 matches",
        )

    with format_col2:
        st.metric(
            "Doublette Matches",
            summary["doublette_matches"],
            help="2v2 matches",
        )

    # Round-by-round statistics
    if all_rounds:
        st.header("📅 Round-by-Round Progress")

        round_data: list[dict[str, str | int]] = []
        for round_obj in all_rounds:
            completed = sum(1 for m in round_obj.matches if m.is_complete)
            total = len(round_obj.matches)
            completion_pct = (completed / total * 100) if total > 0 else 0

            round_data.append(
                {
                    "Round": f"Round {round_obj.index + 1}",
                    "Total Matches": total,
                    "Completed": completed,
                    "Pending": total - completed,
                    "Completion %": f"{completion_pct:.0f}%",
                    "Players": round_obj.total_players,
                }
            )

        df_rounds = pd.DataFrame(round_data)
        st.dataframe(df_rounds, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

        # Progress bar
        total_matches = summary["total_matches"]
        completed_matches = summary["completed_matches"]
        if total_matches > 0:
            progress = completed_matches / total_matches
            st.progress(progress, text=f"Overall Progress: {progress * 100:.1f}%")

    else:
        st.info("📅 No rounds generated yet. Go to the Schedule page to generate rounds.")

    # Recent activity
    st.header("🕐 Recent Activity")

    if all_matches:
        list_completed_matches = [m for m in all_matches if m.is_complete]

        if list_completed_matches:
            # Show last 5 completed matches
            recent = list_completed_matches[-5:]
            recent_data: list[dict[str, str]] = []
            for match in reversed(recent):
                # Get player names
                team_a_names: list[str] = []
                team_b_names: list[str] = []

                for pid in match.team_a_player_ids:
                    player = storage.get_player(pid)
                    if player:
                        team_a_names.append(player.name)

                for pid in match.team_b_player_ids:
                    player = storage.get_player(pid)
                    if player:
                        team_b_names.append(player.name)

                recent_data.append(
                    {
                        "Round": f"R{match.round_index + 1}",
                        "Terrain": match.terrain_label,
                        "Team A": ", ".join(team_a_names),
                        "Score": f"{match.score_a} - {match.score_b}",
                        "Team B": ", ".join(team_b_names),
                        "Winner": "Team A"
                        if (match.score_a or 0) > (match.score_b or 0)
                        else "Team B"
                        if (match.score_b or 0) > (match.score_a or 0)
                        else "Draw",
                    }
                )

            df_recent = pd.DataFrame(recent_data)
            st.dataframe(df_recent, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]
        else:
            st.info("No completed matches yet.")
    else:
        st.info("No matches generated yet.")

    # Player role distribution
    if players:
        st.header("👥 Player Role Distribution")

        from collections import Counter

        role_counts = Counter(p.role.value for p in players)

        role_data: list[dict[str, Any]] = [
            {"Role": role, "Count": count} for role, count in role_counts.items()
        ]
        df_roles = pd.DataFrame(role_data)

        col1, col2 = st.columns([1, 2])

        with col1:
            st.dataframe(df_roles, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

        with col2:
            # Simple bar chart
            st.bar_chart(df_roles.set_index("Role"))  # pyright: ignore[reportUnknownMemberType]

    st.markdown("---")
    st.caption("Dashboard updates in real-time as matches are completed.")


if __name__ == "__main__":
    main()
