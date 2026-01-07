"""Application Streamlit principale pour la gestion d’un tournoi de pétanque.

Ceci est la page d’accueil et l’interface de configuration.
Lancer avec : streamlit run app.py
"""

import streamlit as st

from src.petanque_manager.core.models import (
    PlayerRole,
    StorageBackend,
    TournamentConfig,
    TournamentMode,
)
from src.petanque_manager.infra.auth import is_authenticated, show_login_form
from src.petanque_manager.infra.storage import TournamentStorage
from src.petanque_manager.infra.storage_json import JSONStorage
from src.petanque_manager.infra.storage_sqlmodel import SQLModelStorage

# Configuration de la page
st.set_page_config(
    page_title="Gestionnaire de tournoi de pétanque",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_storage() -> TournamentStorage:
    """Récupère ou crée une instance de stockage.

    Returns:
        Instance de stockage (mise en cache dans le session state)
    """
    if "storage" not in st.session_state:
        # Charger ou créer la config par défaut
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
    """Charge la configuration existante ou crée une configuration par défaut.

    Returns:
        Configuration du tournoi
    """
    # Essayer les deux backends
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

    # Configuration par défaut
    return TournamentConfig(
        mode=TournamentMode.TRIPLETTE,
        rounds_count=3,
        terrains_count=8,
        storage_backend=StorageBackend.SQLMODEL,
    )


def main() -> None:
    """Point d’entrée principal de l’application."""
    # Formulaire de connexion dans la sidebar
    show_login_form()

    st.title("🎯 Gestionnaire de tournoi de pétanque")

    st.markdown(
        """
    Bienvenue dans le **Gestionnaire de tournoi de pétanque** ! Cette application vous aide à organiser
    et gérer des tournois de pétanque avec deux modes : **Triplette** et **Doublette**.

    ### Fonctionnalités
    - 📋 **Gestion des joueurs** : inscrire les joueurs avec leur rôle
    - 📅 **Planning intelligent** : générer des manches en respectant des contraintes
    - 📊 **Classement en direct** : suivre les victoires, les points et le goal-average
    - 🎲 **Matchmaking équitable** : minimiser les partenaires, adversaires et terrains répétés
    - 🔒 **Consultation publique** : tout le monde peut voir le planning et le classement
    - ✏️ **Édition admin** : connexion requise pour gérer les joueurs et saisir les résultats

    ### Navigation
    Utilisez la barre latérale pour naviguer entre les pages :
    - **Tableau de bord** : aperçu du tournoi et statistiques
    - **Joueurs** : gérer la liste des joueurs (connexion requise)
    - **Planning** : générer et consulter les manches
    - **Résultats** : saisir les résultats des matchs (connexion requise)
    - **Classement** : consulter le classement des joueurs

    ---
    """
    )

    # Section configuration
    st.header("⚙️ Configuration du tournoi")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        config = TournamentConfig()

    # Édition uniquement si authentifié
    can_edit = is_authenticated()

    if not can_edit:
        st.info(
            "🔒 La configuration du tournoi est en lecture seule. Connectez-vous pour modifier les paramètres."
        )

    col1, col2 = st.columns(2)

    with col1:
        mode = TournamentMode(
            st.selectbox(
                "Mode du tournoi",
                options=[TournamentMode.TRIPLETTE.value, TournamentMode.DOUBLETTE.value],
                index=0 if config.mode == TournamentMode.TRIPLETTE else 1,
                help="TRIPLETTE : 3 joueurs par équipe (prioritaire)\n"
                "DOUBLETTE : 2 joueurs par équipe (prioritaire)",
                disabled=not can_edit,
            )
        )

        terrains_count = st.number_input(
            "Nombre de terrains",
            min_value=1,
            max_value=52,
            value=config.terrains_count,
            help="Nombre de terrains disponibles (ex. 8 pour A–H)",
            disabled=not can_edit,
        )

    with col2:
        rounds_count = st.number_input(
            "Nombre de manches",
            min_value=1,
            max_value=10,
            value=config.rounds_count,
            help="Nombre total de manches à jouer",
            disabled=not can_edit,
        )

        # seed = st.number_input(
        #     "Graine aléatoire (optionnel)",
        #     min_value=0,
        #     value=config.seed or 0,
        #     help="Définir une graine pour reproduire la génération des manches (0 = aléatoire)",
        #     disabled=not can_edit,

        # )

    # storage_backend = st.selectbox(
    #     "Backend de stockage",
    #     options=[StorageBackend.SQLMODEL, StorageBackend.JSON],
    #     index=0 if config.storage_backend == StorageBackend.SQLMODEL else 1,
    #     help="SQLModel : base SQLite (recommandé)\nJSON : stockage en fichier (secours)",
    #     disabled=not can_edit,
    # )
    storage_backend = StorageBackend.SQLMODEL
    seed = config.seed or 0
    if can_edit:
        if st.button("💾 Enregistrer la configuration", type="primary"):
            new_config = TournamentConfig(
                mode=mode,
                rounds_count=int(rounds_count),
                terrains_count=int(terrains_count),
                seed=int(seed) if seed > 0 else None,
                storage_backend=storage_backend,
            )

            storage.save_config(new_config)
            st.success("✅ Configuration enregistrée !")
            st.rerun()

    # Affichage configuration actuelle
    st.subheader("Configuration actuelle")
    config_col1, config_col2 = st.columns(2)

    with config_col1:
        st.metric("Mode", config.mode.value)
        st.metric("Terrains", config.terrains_count)

    with config_col2:
        st.metric("Manches", config.rounds_count)
        st.metric("Graine", config.seed or "Aléatoire")

        # with config_col3:
        #     st.metric("Stockage", config.storage_backend.value)

        # Infos stockage
        if config.storage_backend == StorageBackend.SQLMODEL:
            st.caption(f"📁 BD : `{config.db_path}`")
        else:
            st.caption(f"📁 JSON : `{config.json_path}`")

    # Statistiques rapides
    st.header("📊 Statistiques rapides")

    players = storage.get_all_players(active_only=True)
    rounds = storage.get_all_rounds()
    matches = storage.get_all_matches()
    completed_matches = [m for m in matches if m.is_complete]

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

    with stat_col1:
        st.metric("Joueurs actifs", len(players))

    with stat_col2:
        st.metric("Manches générées", len(rounds))

    with stat_col3:
        st.metric("Matchs au total", len(matches))

    with stat_col4:
        st.metric("Matchs terminés", len(completed_matches))

    # Besoins en rôles
    if players:
        from src.petanque_manager.core.scheduler import calculate_role_requirements

        st.subheader("📋 Besoins par rôle")

        requirements = calculate_role_requirements(config.mode, len(players))

        st.markdown(
            f"""
        Pour **{len(players)} joueurs** en mode **{config.mode.value}** :
        """
        )

        req_col1, req_col2, req_col3, req_col4 = st.columns(4)

        with req_col1:
            if config.mode == TournamentMode.TRIPLETTE:
                tireur_count = sum(1 for p in players if p.role == PlayerRole.TIREUR)
                delta = tireur_count - requirements.tireur_needed
                st.metric(
                    PlayerRole.TIREUR.value,
                    f"{tireur_count} / {requirements.tireur_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )

        with req_col2:
            if config.mode == TournamentMode.TRIPLETTE:
                pointeur_count = sum(1 for p in players if p.role == PlayerRole.POINTEUR)
                delta = pointeur_count - requirements.pointeur_needed
                st.metric(
                    PlayerRole.POINTEUR.value,
                    f"{pointeur_count} / {requirements.pointeur_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )

        with req_col3:
            if config.mode == TournamentMode.TRIPLETTE:
                milieu_count = sum(1 for p in players if p.role == PlayerRole.MILIEU)
                delta = milieu_count - requirements.milieu_needed
                st.metric(
                    PlayerRole.MILIEU.value,
                    f"{milieu_count} / {requirements.milieu_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )
            else:
                pointeur_milieu_count = sum(1 for p in players if p.role == PlayerRole.POINTEUR)
                delta = pointeur_milieu_count - requirements.pointeur_milieu_needed
                st.metric(
                    PlayerRole.POINTEUR.value,
                    f"{pointeur_milieu_count} / {requirements.pointeur_milieu_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )

        with req_col4:
            if config.mode == TournamentMode.DOUBLETTE:
                tireur_count = sum(1 for p in players if p.role == PlayerRole.TIREUR)
                delta = tireur_count - requirements.tireur_needed
                st.metric(
                    PlayerRole.TIREUR.value,
                    f"{tireur_count} / {requirements.tireur_needed}",
                    delta=f"{delta:+d}" if delta != 0 else "OK",
                    delta_color="off" if delta == 0 else "normal",
                )

    # Pied de page
    st.markdown("---")
    st.caption(
        "Fait avec ❤️ pour les passionnés de pétanque | 🔓 Consultation publique • 🔒 Édition admin"
    )


if __name__ == "__main__":
    main()
