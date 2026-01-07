"""Player management page."""

import pandas as pd
import streamlit as st

from app import get_storage
from src.core.models import Player, PlayerRole, TournamentMode
from src.core.scheduler import calculate_role_requirements
from src.infra.auth import is_authenticated, show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Players - Pétanque Tournament",
        page_icon="👥",
        layout="wide",
    )

    show_login_form()

    st.title("👥 Player Management")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Please configure the tournament on the home page first.")
        st.stop()

    can_edit = is_authenticated()

    if not can_edit:
        st.info("🔒 Player management requires login. You can view the roster below.")

    # Get all players
    all_players = storage.get_all_players(active_only=False)
    active_players = [p for p in all_players if p.active]

    # Show stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Players", len(all_players))

    with col2:
        st.metric("Active Players", len(active_players))

    with col3:
        st.metric("Inactive Players", len(all_players) - len(active_players))

    # Role requirements
    if active_players:
        st.subheader("📋 Role Requirements")

        requirements = calculate_role_requirements(config.mode, len(active_players))

        st.markdown(
            f"""
        **Current setup**: {len(active_players)} players in **{config.mode.value}** mode

        **Needed counts**:
        """
        )

        req_cols = st.columns(4)

        idx = 0
        if config.mode == TournamentMode.TRIPLETTE:
            roles_to_show = [
                ("TIREUR", requirements.tireur_needed),
                ("POINTEUR", requirements.pointeur_needed),
                ("MILIEU", requirements.milieu_needed),
            ]
        else:
            roles_to_show = [
                ("TIREUR", requirements.tireur_needed),
                ("POINTEUR_MILIEU", requirements.pointeur_milieu_needed),
            ]

        for role_name, needed in roles_to_show:
            with req_cols[idx]:
                current = sum(1 for p in active_players if p.role.value == role_name)
                deficit = needed - current
                st.metric(
                    role_name,
                    f"{current} / {needed}",
                    delta=f"{deficit:+d}" if deficit != 0 else "✓",
                    delta_color="inverse" if deficit > 0 else "off",
                )
            idx += 1

        if any(
            (needed - sum(1 for p in active_players if p.role.value == role)) != 0
            for role, needed in roles_to_show
        ):
            st.warning(
                "⚠️ Role counts don't match requirements. Some matches may use fallback formats."
            )

    st.markdown("---")

    # Add new player section
    if can_edit:
        with st.expander("➕ Add New Player", expanded=False):
            with st.form("add_player_form"):
                col1, col2 = st.columns(2)

                with col1:
                    new_name = st.text_input("Player Name", max_chars=100)

                with col2:
                    if config.mode == TournamentMode.TRIPLETTE:
                        role_options = [
                            PlayerRole.TIREUR,
                            PlayerRole.POINTEUR,
                            PlayerRole.MILIEU,
                            PlayerRole.POINTEUR_MILIEU,
                        ]
                    else:
                        role_options = [
                            PlayerRole.TIREUR,
                            PlayerRole.POINTEUR_MILIEU,
                        ]

                    new_role = st.selectbox(
                        "Role",
                        options=role_options,
                        format_func=lambda x: x.value,
                    )

                submitted = st.form_submit_button("Add Player", type="primary")

                if submitted:
                    if not new_name or not new_name.strip():
                        st.error("❌ Player name cannot be empty")
                    else:
                        try:
                            player = Player(
                                name=new_name.strip(),
                                role=new_role,
                                active=True,
                            )
                            storage.add_player(player)
                            st.success(f"✅ Added player: {new_name}")
                            st.rerun()
                        except ValueError as e:
                            st.error(f"❌ Error: {e}")

    # Player list
    st.subheader("📋 Player Roster")

    # Filters
    filter_col1, filter_col2 = st.columns([2, 1])

    with filter_col1:
        show_inactive = st.checkbox("Show inactive players", value=False)

    with filter_col2:
        search_query = st.text_input("🔍 Search players", "")

    # Filter players
    display_players = active_players if not show_inactive else all_players

    if search_query:
        display_players = [p for p in display_players if search_query.lower() in p.name.lower()]

    if display_players:
        # Create dataframe
        player_data: list[dict[str, str | int]] = []
        for player in display_players:
            player_data.append(
                {
                    "ID": player.id or 0,
                    "Name": player.name,
                    "Role": player.role.value,
                    "Status": "✓ Active" if player.active else "✗ Inactive",
                }
            )

        df_players = pd.DataFrame(player_data)
        st.dataframe(df_players, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

        # Edit/Delete players
        if can_edit:
            st.subheader("✏️ Edit Player")

            selected_player_id = st.selectbox(
                "Select player to edit",
                options=[p.id for p in display_players],
                format_func=lambda pid: next(
                    (p.name for p in display_players if p.id == pid), "Unknown"
                ),
            )

            if selected_player_id:
                player_to_edit = storage.get_player(selected_player_id)

                if player_to_edit:
                    with st.form("edit_player_form"):
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            edit_name = st.text_input(
                                "Name", value=player_to_edit.name, max_chars=100
                            )

                        with col2:
                            if config.mode == TournamentMode.TRIPLETTE:
                                role_options = [
                                    PlayerRole.TIREUR,
                                    PlayerRole.POINTEUR,
                                    PlayerRole.MILIEU,
                                    PlayerRole.POINTEUR_MILIEU,
                                ]
                            else:
                                role_options = [
                                    PlayerRole.TIREUR,
                                    PlayerRole.POINTEUR_MILIEU,
                                ]

                            edit_role = st.selectbox(
                                "Role",
                                options=role_options,
                                index=role_options.index(player_to_edit.role)
                                if player_to_edit.role in role_options
                                else 0,
                                format_func=lambda x: x.value,
                            )

                        with col3:
                            edit_active = st.checkbox("Active", value=player_to_edit.active)

                        col_submit, col_delete = st.columns(2)

                        with col_submit:
                            update_submitted = st.form_submit_button(
                                "💾 Update Player", type="primary"
                            )

                        with col_delete:
                            delete_submitted = st.form_submit_button(
                                "🗑️ Delete Player", type="secondary"
                            )

                        if update_submitted:
                            if not edit_name or not edit_name.strip():
                                st.error("❌ Player name cannot be empty")
                            else:
                                try:
                                    updated_player = Player(
                                        id=player_to_edit.id,
                                        name=edit_name.strip(),
                                        role=edit_role,
                                        active=edit_active,
                                        created_at=player_to_edit.created_at,
                                    )
                                    storage.update_player(updated_player)
                                    st.success(f"✅ Updated player: {edit_name}")
                                    st.rerun()
                                except ValueError as e:
                                    st.error(f"❌ Error: {e}")

                        if delete_submitted:
                            try:
                                storage.delete_player(player_to_edit.id or 0)
                                st.success(f"✅ Deleted player: {player_to_edit.name}")
                                st.rerun()
                            except ValueError as e:
                                st.error(f"❌ Error: {e}")

    else:
        st.info("No players found. Add some players to get started!")

    # Bulk import (optional feature)
    if can_edit:
        with st.expander("📥 Bulk Import (CSV)", expanded=False):
            st.markdown(
                """
            Upload a CSV file with columns: `name`, `role`

            Example:
            ```
            name,role
            John Doe,TIREUR
            Jane Smith,POINTEUR
            Bob Johnson,MILIEU
            ```
            """
            )

            uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])

            if uploaded_file is not None:
                try:
                    df_import = pd.read_csv(uploaded_file)  # pyright: ignore[reportUnknownMemberType]

                    if "name" not in df_import.columns or "role" not in df_import.columns:
                        st.error("❌ CSV must have 'name' and 'role' columns")
                    else:
                        st.dataframe(df_import)  # pyright: ignore[reportUnknownMemberType]

                        if st.button("Import Players", type="primary"):
                            success_count = 0
                            error_count = 0

                            for _, row in df_import.iterrows():
                                try:
                                    player = Player(
                                        name=str(row["name"]).strip(),
                                        role=PlayerRole(row["role"]),
                                        active=True,
                                    )
                                    storage.add_player(player)
                                    success_count += 1
                                except Exception as e:
                                    st.warning(f"⚠️ Skipped {row['name']}: {e}")
                                    error_count += 1

                            st.success(
                                f"✅ Imported {success_count} players ({error_count} errors)"
                            )
                            st.rerun()

                except Exception as e:
                    st.error(f"❌ Error reading CSV: {e}")

    st.markdown("---")
    st.caption("💡 Tip: Ensure you have the right balance of roles before generating rounds.")


if __name__ == "__main__":
    main()
