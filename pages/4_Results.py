"""Results entry page for match scores."""

import streamlit as st

from app import get_storage
from src.core.models import Player
from src.infra.auth import is_authenticated, show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Results - Pétanque Tournament",
        page_icon="📝",
        layout="wide",
    )

    show_login_form()

    st.title("📝 Match Results Entry")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Please configure the tournament on the home page first.")
        st.stop()

    # Get data
    rounds = storage.get_all_rounds()
    all_matches = storage.get_all_matches()

    if not rounds:
        st.info("📅 No rounds generated yet. Generate rounds on the Schedule page first.")
        st.stop()

    # Require authentication
    can_edit = is_authenticated()

    if not can_edit:
        st.warning("🔒 Please login to enter or edit match results.")
        st.info("You can view existing results, but editing requires authentication.")

    # Summary
    completed_matches = [m for m in all_matches if m.is_complete]
    pending_matches = [m for m in all_matches if not m.is_complete]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Matches", len(all_matches))

    with col2:
        st.metric("Completed", len(completed_matches))

    with col3:
        st.metric("Pending", len(pending_matches))

    st.markdown("---")

    # Select round
    st.header("🎯 Enter Results")

    selected_round_index = st.selectbox(
        "Select Round",
        options=list(range(len(rounds))),
        format_func=lambda i: f"Round {i + 1}",
    )

    selected_round = rounds[selected_round_index]

    st.subheader(f"Round {selected_round.index + 1}")

    # Show matches in this round
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
            st.markdown(f"### Terrain {match.terrain_label}")
            st.caption(f"Format: {match.format.value}")

            # Score entry form
            col1, col2, col3 = st.columns([2, 1, 2])

            with col1:
                st.markdown(f"**Team A**  \n{team_a_display}")

            with col2:
                st.markdown("**VS**")

            with col3:
                st.markdown(f"**Team B**  \n{team_b_display}")

            # Score inputs
            score_col1, score_col2, score_col3 = st.columns([2, 1, 2])

            with score_col1:
                score_a = st.number_input(
                    "Score A",
                    min_value=0,
                    max_value=13,
                    value=match.score_a if match.score_a is not None else 0,
                    key=f"score_a_{match.id}",
                    disabled=not can_edit,
                )

            with score_col2:
                st.markdown("**-**")

            with score_col3:
                score_b = st.number_input(
                    "Score B",
                    min_value=0,
                    max_value=13,
                    value=match.score_b if match.score_b is not None else 0,
                    key=f"score_b_{match.id}",
                    disabled=not can_edit,
                )

            # Save button
            if can_edit:
                col_save, col_clear = st.columns(2)

                with col_save:
                    if st.button(
                        "💾 Save Score",
                        key=f"save_{match.id}",
                        type="primary" if not match.is_complete else "secondary",
                    ):
                        try:
                            match.score_a = int(score_a)
                            match.score_b = int(score_b)
                            storage.update_match(match)
                            st.success("✅ Score saved!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error saving score: {e}")

                with col_clear:
                    if match.is_complete and st.button(
                        "🗑️ Clear Score",
                        key=f"clear_{match.id}",
                    ):
                        try:
                            match.score_a = None
                            match.score_b = None
                            storage.update_match(match)
                            st.success("✅ Score cleared!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error clearing score: {e}")

            # Show current status
            if match.is_complete:
                if (match.score_a or 0) > (match.score_b or 0):
                    st.success(f"✅ Team A wins! ({match.score_a} - {match.score_b})")
                elif (match.score_b or 0) > (match.score_a or 0):
                    st.info(f"✅ Team B wins! ({match.score_a} - {match.score_b})")
                else:
                    st.warning(f"⚖️ Draw ({match.score_a} - {match.score_b})")
            else:
                st.caption("⏳ Pending - No score entered yet")

            st.divider()

    # Quick completion stats for this round
    completed_this_round = sum(1 for m in selected_round.matches if m.is_complete)
    total_this_round = len(selected_round.matches)
    completion_pct = (completed_this_round / total_this_round * 100) if total_this_round > 0 else 0

    st.progress(
        completed_this_round / total_this_round if total_this_round > 0 else 0,
        text=f"Round {selected_round.index + 1} Progress: {completion_pct:.0f}% "
        f"({completed_this_round}/{total_this_round})",
    )

    # Bulk entry helper
    if can_edit and pending_matches:
        st.markdown("---")

        with st.expander("⚡ Quick Entry Tips", expanded=False):
            st.markdown(
                """
            **Tips for faster entry:**

            1. **Tab Navigation**: Use Tab key to move between score inputs quickly
            2. **Enter to Save**: Press Enter after typing a score (if using keyboard)
            3. **Work Round by Round**: Complete one round at a time for better organization
            4. **Check Before Saving**: Verify scores before clicking Save

            **Petanque Scoring Rules:**
            - First team to 13 points wins
            - Maximum score is 13
            - Typical scores: 13-0 to 13-12
            """
            )

    st.markdown("---")
    st.caption("💡 Tip: Results are updated in real-time and reflected in rankings immediately.")


if __name__ == "__main__":
    main()
