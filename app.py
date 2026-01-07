"""Main Streamlit application for pétanque tournament management.

This is the home page and configuration interface.
Run with: streamlit run app.py
"""

import streamlit as st

from src.core.models import StorageBackend, TournamentConfig, TournamentMode
from src.infra.auth import is_authenticated, show_login_form
from src.infra.storage import TournamentStorage
from src.infra.storage_json import JSONStorage
from src.infra.storage_sqlmodel import SQLModelStorage

# Page config
st.set_page_config(
    page_title="Pétanque Tournament Manager",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_storage() -> TournamentStorage:
    """Get or create storage instance.

    Returns:
        Storage instance (cached in session state)
    """
    if "storage" not in st.session_state:
        # Load or create default config
        config = load_or_create_config()

        if config.storage_backend == StorageBackend.SQLMODEL:
            storage: TournamentStorage = SQLModelStorage(config.db_path)
        else:
            storage = JSONStorage(config.json_path)

        storage.initialize()
        st.session_state.storage = storage
    storage_returned: TournamentStorage = st.session_state.storage
    return storage_returned


def load_or_create_config() -> TournamentConfig:
    """Load existing config or create default.

    Returns:
        Tournament configuration
    """
    # Try both backends
    storages: list[tuple[type[TournamentStorage], str]] = [
        (SQLModelStorage, "tournament.db"),
        (JSONStorage, "tournament_data.json"),
    ]
    for backend_class, path_attr in storages:
        try:
            storage = backend_class(path_attr)  # pyright: ignore[reportCallIssue]
            storage.initialize()
            config = storage.load_config()
            if config:
                return config
        except Exception:
            continue

    # Create default config
    return TournamentConfig(
        mode=TournamentMode.TRIPLETTE,
        rounds_count=3,
        terrains_count=8,
        storage_backend=StorageBackend.SQLMODEL,
    )


def main() -> None:
    """Main application entry point."""
    # Show login form in sidebar
    show_login_form()

    st.title("🎯 Pétanque Tournament Manager")

    st.markdown(
        """
    Welcome to the **Pétanque Tournament Manager**! This application helps you organize
    and manage pétanque tournaments with two modes: **TRIPLETTE** and **DOUBLETTE**.

    ### Features
    - 📋 **Player Management**: Register players with their roles
    - 📅 **Smart Scheduling**: Generate rounds with constraint satisfaction
    - 📊 **Live Rankings**: Track wins, points, and goal averages
    - 🎲 **Fair Matchmaking**: Minimize repeated partners, opponents, and terrains
    - 🔒 **Public Viewing**: Anyone can view schedules and rankings
    - ✏️ **Admin Editing**: Login required for player management and result entry

    ### Navigation
    Use the sidebar to navigate between pages:
    - **Dashboard**: Tournament overview and statistics
    - **Players**: Manage player roster (requires login)
    - **Schedule**: Generate and view rounds
    - **Results**: Enter match results (requires login)
    - **Ranking**: View player standings

    ---
    """
    )

    # Configuration section
    st.header("⚙️ Tournament Configuration")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        config = TournamentConfig()

    # Only allow editing if authenticated
    can_edit = is_authenticated()

    if not can_edit:
        st.info("🔒 Tournament configuration is view-only. Please login to change settings.")

    col1, col2 = st.columns(2)

    with col1:
        mode = st.selectbox(
            "Tournament Mode",
            options=[TournamentMode.TRIPLETTE, TournamentMode.DOUBLETTE],
            index=0 if config.mode == TournamentMode.TRIPLETTE else 1,
            help="TRIPLETTE: 3 players per team (preferred)\n"
            "DOUBLETTE: 2 players per team (preferred)",
            disabled=not can_edit,
        )

        terrains_count = st.number_input(
            "Number of Terrains",
            min_value=1,
            max_value=52,
            value=config.terrains_count,
            help="Number of available playing terrains (e.g., 8 for A-H)",
            disabled=not can_edit,
        )

    with col2:
        rounds_count = st.number_input(
            "Number of Rounds",
            min_value=1,
            max_value=10,
            value=config.rounds_count,
            help="Total number of rounds to play",
            disabled=not can_edit,
        )

        seed = st.number_input(
            "Random Seed (optional)",
            min_value=0,
            value=config.seed or 0,
            help="Set a seed for reproducible round generation (0 = random)",
            disabled=not can_edit,
        )

    storage_backend = st.selectbox(
        "Storage Backend",
        options=[StorageBackend.SQLMODEL, StorageBackend.JSON],
        index=0 if config.storage_backend == StorageBackend.SQLMODEL else 1,
        help="SQLModel: SQLite database (recommended)\nJSON: File-based storage (fallback)",
        disabled=not can_edit,
    )

    if can_edit:
        if st.button("💾 Save Configuration", type="primary"):
            new_config = TournamentConfig(
                mode=mode,
                rounds_count=int(rounds_count),
                terrains_count=int(terrains_count),
                seed=int(seed) if seed > 0 else None,
                storage_backend=storage_backend,
            )

            storage.save_config(new_config)
            st.success("✅ Configuration saved!")
            st.rerun()

    # Display current configuration
    st.subheader("Current Configuration")
    config_col1, config_col2, config_col3 = st.columns(3)

    with config_col1:
        st.metric("Mode", config.mode.value)
        st.metric("Terrains", config.terrains_count)

    with config_col2:
        st.metric("Rounds", config.rounds_count)
        st.metric("Seed", config.seed or "Random")

    with config_col3:
        st.metric("Storage", config.storage_backend.value)

        # Storage info
        if config.storage_backend == StorageBackend.SQLMODEL:
            st.caption(f"📁 DB: `{config.db_path}`")
        else:
            st.caption(f"📁 JSON: `{config.json_path}`")

    # Quick stats
    st.header("📊 Quick Stats")

    players = storage.get_all_players(active_only=True)
    rounds = storage.get_all_rounds()
    matches = storage.get_all_matches()
    completed_matches = [m for m in matches if m.is_complete]

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

    with stat_col1:
        st.metric("Active Players", len(players))

    with stat_col2:
        st.metric("Rounds Generated", len(rounds))

    with stat_col3:
        st.metric("Total Matches", len(matches))

    with stat_col4:
        st.metric("Completed Matches", len(completed_matches))

    # Role requirements
    if players:
        from src.core.scheduler import calculate_role_requirements

        st.subheader("📋 Role Requirements")

        requirements = calculate_role_requirements(config.mode, len(players))

        st.markdown(
            f"""
        For **{len(players)} players** in **{config.mode.value}** mode:
        """
        )

        req_col1, req_col2, req_col3, req_col4 = st.columns(4)

        with req_col1:
            if config.mode == TournamentMode.TRIPLETTE:
                tireur_count = sum(1 for p in players if p.role.value == "TIREUR")
                delta = tireur_count - requirements.tireur_needed
                st.metric(
                    "TIREUR",
                    f"{tireur_count} / {requirements.tireur_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )

        with req_col2:
            if config.mode == TournamentMode.TRIPLETTE:
                pointeur_count = sum(1 for p in players if p.role.value == "POINTEUR")
                delta = pointeur_count - requirements.pointeur_needed
                st.metric(
                    "POINTEUR",
                    f"{pointeur_count} / {requirements.pointeur_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )

        with req_col3:
            if config.mode == TournamentMode.TRIPLETTE:
                milieu_count = sum(1 for p in players if p.role.value == "MILIEU")
                delta = milieu_count - requirements.milieu_needed
                st.metric(
                    "MILIEU",
                    f"{milieu_count} / {requirements.milieu_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )
            else:
                pointeur_milieu_count = sum(1 for p in players if p.role.value == "POINTEUR_MILIEU")
                delta = pointeur_milieu_count - requirements.pointeur_milieu_needed
                st.metric(
                    "POINTEUR_MILIEU",
                    f"{pointeur_milieu_count} / {requirements.pointeur_milieu_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )

        with req_col4:
            if config.mode == TournamentMode.DOUBLETTE:
                tireur_count = sum(1 for p in players if p.role.value == "TIREUR")
                delta = tireur_count - requirements.tireur_needed
                st.metric(
                    "TIREUR",
                    f"{tireur_count} / {requirements.tireur_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )

    # Footer
    st.markdown("---")
    st.caption("Made with ❤️ for pétanque enthusiasts | 🔓 Public viewing • 🔒 Admin editing")


if __name__ == "__main__":
    main()
