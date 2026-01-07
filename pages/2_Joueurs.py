"""Page de gestion des joueurs."""

import pandas as pd
import streamlit as st

from Acceuil import get_storage
from src.petanque_manager.core.models import Player, PlayerRole, TournamentMode
from src.petanque_manager.core.scheduler import calculate_role_requirements
from src.petanque_manager.infra.auth import is_authenticated, show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Joueurs - Tournoi de pétanque",
        page_icon="👥",
        layout="wide",
    )

    show_login_form()

    st.title("👥 Gestion des joueurs")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Veuillez d’abord configurer le tournoi sur la page d’accueil.")
        st.stop()

    can_edit = is_authenticated()

    if not can_edit:
        st.info(
            "🔒 La gestion des joueurs nécessite une connexion. "
            "Vous pouvez consulter la liste des joueurs ci-dessous."
        )

    # Récupération des joueurs
    all_players = storage.get_all_players(active_only=False)
    active_players = [p for p in all_players if p.active]

    # Statistiques joueurs
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Nombre total de joueurs", len(all_players))

    with col2:
        st.metric("Joueurs actifs", len(active_players))

    with col3:
        st.metric("Joueurs inactifs", len(all_players) - len(active_players))

    # Besoins en rôles
    if active_players:
        st.subheader("📋 Besoins par rôle")

        requirements = calculate_role_requirements(config.mode, len(active_players))

        st.markdown(
            f"""
        **Configuration actuelle** :
        {len(active_players)} joueurs au total
        - {requirements.triplette_count} donc {requirements.triplette_count * 3} joueurs en équipes de triplette
        - {requirements.doublette_count} donc {requirements.doublette_count * 2} joueurs en équipes de doublette

        **Effectifs requis** :
        """
        )

        req_cols = st.columns(4)

        idx = 0
        roles_to_show = [
            (PlayerRole.TIREUR, requirements.tireur_needed),
            (PlayerRole.POINTEUR, requirements.pointeur_needed),
            (PlayerRole.MILIEU, requirements.milieu_needed),
            (PlayerRole.POINTEUR_MILIEU, requirements.pointeur_milieu_needed),
        ]

        for role, needed in roles_to_show:
            with req_cols[idx]:
                current = sum(1 for p in active_players if p.role == role)
                deficit = needed - current
                st.metric(
                    role.value,
                    f"{current} présents / {needed} requis",
                    delta_arrow="down" if deficit > 0 else "off",
                    delta=f"{deficit:+d}" if deficit != 0 else "✓",
                    delta_color="inverse" if deficit > 0 else "normal",
                )
            idx += 1

        if any(
            (needed - sum(1 for p in active_players if p.role.value == role)) != 0
            for role, needed in roles_to_show
        ):
            st.warning(
                "⚠️ Le nombre de joueurs par rôle ne correspond pas aux besoins. "
                "Certaines parties pourront utiliser des formats alternatifs."
            )

    st.markdown("---")

    # Ajout d’un joueur
    if can_edit:
        with st.expander("➕ Ajouter un joueur", expanded=False):
            with st.form("add_player_form"):
                col1, col2 = st.columns(2)

                with col1:
                    new_name = st.text_input("Nom du joueur", max_chars=100)

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
                        "Rôle",
                        options=role_options,
                        format_func=lambda x: x.value,
                    )

                submitted = st.form_submit_button("Ajouter le joueur", type="primary")

                if submitted:
                    if not new_name or not new_name.strip():
                        st.error("❌ Le nom du joueur ne peut pas être vide")
                    else:
                        try:
                            player = Player(
                                name=new_name.strip(),
                                role=new_role,
                                active=True,
                            )
                            storage.add_player(player)
                            st.success(f"✅ Joueur ajouté : {new_name}")
                            st.rerun()
                        except ValueError as e:
                            st.error(f"❌ Erreur : {e}")

    # Liste des joueurs
    st.subheader("📋 Liste des joueurs")

    # Filtres
    filter_col1, filter_col2 = st.columns([2, 1])

    with filter_col1:
        show_inactive = st.checkbox("Afficher les joueurs inactifs", value=False)

    with filter_col2:
        search_query = st.text_input("🔍 Rechercher un joueur", "")

    display_players = active_players if not show_inactive else all_players

    if search_query:
        display_players = [p for p in display_players if search_query.lower() in p.name.lower()]

    if display_players:
        player_data: list[dict[str, str | int]] = []
        for player in display_players:
            player_data.append(
                {
                    "ID": player.id or 0,
                    "Nom": player.name,
                    "Rôle": player.role.value,
                    "Statut": "✓ Actif" if player.active else "✗ Inactif",
                }
            )

        df_players = pd.DataFrame(player_data)
        st.dataframe(df_players, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

        # Édition / suppression
        if can_edit:
            st.subheader("✏️ Modifier un joueur")

            selected_player_id = st.selectbox(
                "Sélectionner un joueur",
                options=[p.id for p in display_players],
                format_func=lambda pid: next(
                    (p.name for p in display_players if p.id == pid), "Inconnu"
                ),
            )

            if selected_player_id:
                player_to_edit = storage.get_player(selected_player_id)

                if player_to_edit:
                    with st.form("edit_player_form"):
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            edit_name = st.text_input(
                                "Nom",
                                value=player_to_edit.name,
                                max_chars=100,
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
                                "Rôle",
                                options=role_options,
                                index=role_options.index(player_to_edit.role)
                                if player_to_edit.role in role_options
                                else 0,
                                format_func=lambda x: x.value,
                            )

                        with col3:
                            edit_active = st.checkbox(
                                "Actif",
                                value=player_to_edit.active,
                            )

                        col_submit, col_delete = st.columns(2)

                        with col_submit:
                            update_submitted = st.form_submit_button(
                                "💾 Mettre à jour", type="primary"
                            )

                        with col_delete:
                            delete_submitted = st.form_submit_button(
                                "🗑️ Supprimer", type="secondary"
                            )

                        if update_submitted:
                            if not edit_name or not edit_name.strip():
                                st.error("❌ Le nom du joueur ne peut pas être vide")
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
                                    st.success(f"✅ Joueur mis à jour : {edit_name}")
                                    st.rerun()
                                except ValueError as e:
                                    st.error(f"❌ Erreur : {e}")

                        if delete_submitted:
                            try:
                                storage.delete_player(player_to_edit.id or 0)
                                st.success(f"✅ Joueur supprimé : {player_to_edit.name}")
                                st.rerun()
                            except ValueError as e:
                                st.error(f"❌ Erreur : {e}")

    else:
        st.info("Aucun joueur trouvé. Ajoutez des joueurs pour commencer !")

    # Import en masse
    if can_edit:
        with st.expander("📥 Import en masse (CSV)", expanded=False):
            st.markdown(
                """
            Téléversez un fichier CSV avec les colonnes : `name`, `role`

            Exemple :
            ```
            name,role
            Jean Dupont,TIREUR
            Marie Martin,POINTEUR
            Paul Durand,MILIEU
            ```
            """
            )

            uploaded_file = st.file_uploader("Choisir un fichier CSV", type=["csv"])

            if uploaded_file is not None:
                try:
                    df_import = pd.read_csv(uploaded_file)  # pyright: ignore[reportUnknownMemberType]

                    if "name" not in df_import.columns or "role" not in df_import.columns:
                        st.error("❌ Le CSV doit contenir les colonnes 'name' et 'role'")
                    else:
                        st.dataframe(df_import)  # pyright: ignore[reportUnknownMemberType]

                        if st.button("Importer les joueurs", type="primary"):
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
                                    st.warning(f"⚠️ Joueur ignoré ({row['name']}) : {e}")
                                    error_count += 1

                            st.success(
                                f"✅ {success_count} joueurs importés ({error_count} erreurs)"
                            )
                            st.rerun()

                except Exception as e:
                    st.error(f"❌ Erreur lors de la lecture du CSV : {e}")

    st.markdown("---")
    st.caption(
        "💡 Astuce : assurez-vous d’avoir un bon équilibre des rôles avant de générer les manches."
    )


if __name__ == "__main__":
    main()
