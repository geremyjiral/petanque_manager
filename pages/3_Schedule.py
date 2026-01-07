"""Schedule generation and viewing page."""

import pandas as pd
import streamlit as st

from app import get_storage
from src.core.models import Player
from src.core.scheduler import TournamentScheduler
from src.infra.auth import is_authenticated, show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Schedule - Pétanque Tournament",
        page_icon="📅",
        layout="wide",
    )

    show_login_form()

    st.title("📅 Tournament Schedule")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Please configure the tournament on the home page first.")
        st.stop()

    can_edit = is_authenticated()

    # Get data
    players = storage.get_all_players(active_only=True)
    rounds = storage.get_all_rounds()

    # Summary
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Active Players", len(players))

    with col2:
        st.metric("Generated Rounds", len(rounds))

    with col3:
        st.metric("Target Rounds", config.rounds_count)

    st.markdown("---")

    # Round generation section
    if can_edit:
        st.header("⚙️ Generate Rounds")

        if len(players) < 4:
            st.error("❌ Need at least 4 active players to generate rounds.")
        else:
            with st.expander(
                "🎲 Generate New Round"
                if len(rounds) < config.rounds_count
                else "✅ All rounds generated",
                expanded=len(rounds) < config.rounds_count,
            ):
                if len(rounds) >= config.rounds_count:
                    st.success("✅ All rounds have been generated!")
                    st.info(
                        "To generate more rounds, increase the 'Number of Rounds' "
                        "in the configuration on the home page."
                    )
                else:
                    next_round_index = len(rounds)

                    st.markdown(
                        f"""
                    **Generating Round {next_round_index + 1}** of {config.rounds_count}

                    **Settings:**
                    - Mode: {config.mode.value}
                    - Players: {len(players)}
                    - Terrains: {config.terrains_count}
                    - Seed: {config.seed or "Random"}
                    """
                    )

                    # Generation options
                    use_custom_seed = st.checkbox(
                        "Use custom seed for this round",
                        value=False,
                        help="Override the global seed for this round only",
                    )

                    custom_seed = None
                    if use_custom_seed:
                        custom_seed = st.number_input(
                            "Round seed",
                            min_value=0,
                            value=0,
                        )

                    if st.button("🎲 Generate Round", type="primary"):
                        try:
                            with st.spinner("Generating round..."):
                                scheduler = TournamentScheduler(
                                    mode=config.mode,
                                    terrains_count=config.terrains_count,
                                    seed=custom_seed
                                    if use_custom_seed and custom_seed
                                    else config.seed,
                                )

                                round_obj, quality_report = scheduler.generate_round(
                                    players=players,
                                    round_index=next_round_index,
                                    previous_rounds=rounds,
                                )

                                # Save round
                                storage.add_round(round_obj)

                                st.success(f"✅ Generated Round {next_round_index + 1}!")

                                # Show quality report
                                st.subheader("📊 Quality Report")

                                (
                                    quality_col1,
                                    quality_col2,
                                    quality_col3,
                                    quality_col4,
                                    quality_col5,
                                ) = st.columns(5)

                                with quality_col1:
                                    st.metric("Grade", quality_report.quality_grade)

                                with quality_col2:
                                    st.metric(
                                        "Repeated Partners",
                                        quality_report.repeated_partners,
                                        help="Player pairs playing together >1 time",
                                    )

                                with quality_col3:
                                    st.metric(
                                        "Repeated Opponents",
                                        quality_report.repeated_opponents,
                                        help="Player pairs playing against each other >1 time",
                                    )

                                with quality_col4:
                                    st.metric(
                                        "Repeated Terrains",
                                        quality_report.repeated_terrains,
                                        help="Players playing on same terrain >1 time",
                                    )

                                with quality_col5:
                                    st.metric(
                                        "Fallback Matches",
                                        quality_report.fallback_format_count,
                                        help="Matches in non-preferred format",
                                    )

                                if quality_report.quality_grade in ["A+", "A", "B"]:
                                    st.success("🎉 Excellent schedule quality!")
                                elif quality_report.quality_grade == "C":
                                    st.info("👍 Good schedule quality")
                                else:
                                    st.warning(
                                        "⚠️ Schedule quality could be improved. "
                                        "Consider regenerating with different seed."
                                    )

                                st.rerun()

                        except ValueError as e:
                            st.error(f"❌ Error generating round: {e}")
    else:
        st.info("🔒 Login required to generate rounds. View existing rounds below.")

    # View rounds
    st.header("📋 View Rounds")

    if not rounds:
        st.info("No rounds generated yet. Generate your first round above!")
    else:
        # Round selector
        selected_round_index = st.selectbox(
            "Select Round",
            options=list(range(len(rounds))),
            format_func=lambda i: f"Round {i + 1}",
        )

        selected_round = rounds[selected_round_index]

        st.subheader(f"Round {selected_round.index + 1}")

        # Round info
        completed_matches = sum(1 for m in selected_round.matches if m.is_complete)
        total_matches = len(selected_round.matches)
        completion_pct = (completed_matches / total_matches * 100) if total_matches > 0 else 0

        round_col1, round_col2, round_col3 = st.columns(3)

        with round_col1:
            st.metric("Matches", total_matches)

        with round_col2:
            st.metric("Completed", f"{completed_matches} / {total_matches}")

        with round_col3:
            st.metric("Progress", f"{completion_pct:.0f}%")

        # Match list
        st.subheader("🎯 Matches")

        for match in selected_round.matches:
            with st.container():
                # Get player names
                team_a_players: list[Player] = []
                team_b_players: list[Player] = []

                for pid in match.team_a_player_ids:
                    player = storage.get_player(pid)
                    if player:
                        team_a_players.append(player)

                for pid in match.team_b_player_ids:
                    player = storage.get_player(pid)
                    if player:
                        team_b_players.append(player)

                # Format team display
                team_a_display = " + ".join([f"{p.name} ({p.role.value})" for p in team_a_players])
                team_b_display = " + ".join([f"{p.name} ({p.role.value})" for p in team_b_players])

                # Match header
                match_col1, match_col2, match_col3 = st.columns([1, 2, 1])

                with match_col1:
                    st.markdown(f"**Terrain {match.terrain_label}**")
                    st.caption(f"{match.format.value}")

                with match_col2:
                    if match.is_complete:
                        st.markdown(f"**{team_a_display}**  \n🆚  \n**{team_b_display}**")
                    else:
                        st.markdown(f"{team_a_display}  \n🆚  \n{team_b_display}")

                with match_col3:
                    if match.is_complete:
                        st.markdown(f"### {match.score_a} - {match.score_b}")
                        if (match.score_a or 0) > (match.score_b or 0):
                            st.success("Team A wins!")
                        elif (match.score_b or 0) > (match.score_a or 0):
                            st.info("Team B wins!")
                        else:
                            st.warning("Draw")
                    else:
                        st.markdown("_Pending_")

                st.divider()

        # Export round
        if st.button(f"📥 Export Round {selected_round.index + 1} to CSV"):
            match_data: list[dict[str, str | int]] = []

            for match in selected_round.matches:
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

                match_data.append(
                    {
                        "Terrain": match.terrain_label,
                        "Format": match.format.value,
                        "Team A": " + ".join(team_a_names),
                        "Team B": " + ".join(team_b_names),
                        "Score A": match.score_a or "",
                        "Score B": match.score_b or "",
                        "Status": "Complete" if match.is_complete else "Pending",
                    }
                )

            df_export = pd.DataFrame(match_data)
            csv = df_export.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"round_{selected_round.index + 1}.csv",
                mime="text/csv",
            )

    # Delete rounds (admin only)
    if can_edit and rounds:
        st.markdown("---")

        with st.expander("⚠️ Danger Zone", expanded=False):
            st.warning(
                "⚠️ **Warning**: Deleting rounds will also delete all associated matches and results. "
                "This action cannot be undone!"
            )

            if st.button("🗑️ Delete All Rounds", type="secondary"):
                if st.session_state.get("confirm_delete_rounds"):
                    storage.delete_all_rounds()
                    st.success("✅ All rounds deleted")
                    st.session_state.confirm_delete_rounds = False
                    st.rerun()
                else:
                    st.session_state.confirm_delete_rounds = True
                    st.warning("⚠️ Click again to confirm deletion")

    st.markdown("---")
    st.caption(
        "💡 Tip: Round generation uses smart algorithms to minimize repeated partners and opponents."
    )


if __name__ == "__main__":
    main()
