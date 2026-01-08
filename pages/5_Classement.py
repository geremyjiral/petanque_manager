"""Page de classement affichant le classement des joueurs."""

from typing import Any

import pandas as pd
import streamlit as st

from Acceuil import get_storage
from src.petanque_manager.core.models import PlayerRole
from src.petanque_manager.core.stats import calculate_player_stats
from src.petanque_manager.infra.auth import show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Classement - Tournoi de pétanque",
        page_icon="🏆",
        layout="wide",
    )

    show_login_form()

    st.title("🏆 Classement des joueurs")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Veuillez d’abord configurer le tournoi sur la page d’accueil.")
        st.stop()

    # Données
    players = storage.get_all_players(active_only=True)
    all_matches = storage.get_all_matches()

    if not players:
        st.info("👥 Aucun joueur inscrit pour le moment. Ajoutez des joueurs sur la page Joueurs.")
        st.stop()

    # Calcul des stats
    player_stats = calculate_player_stats(players, all_matches)

    # Filtres
    st.sidebar.header("🔍 Filtres")

    min_matches = st.sidebar.number_input(
        "Nombre minimum de matchs joués",
        min_value=0,
        max_value=100,
        value=0,
        help="Filtrer les joueurs ayant joué au moins ce nombre de matchs",
    )

    role_filter = st.sidebar.multiselect(
        "Filtrer par rôle",
        options=[r.value for r in PlayerRole],
        default=[],
        help="Sélectionnez les rôles à afficher (vide = tous)",
    )

    search_name = st.sidebar.text_input(
        "Rechercher par nom",
        "",
        help="Filtrer les joueurs par nom",
    )

    # Application des filtres
    filtered_stats = player_stats

    if min_matches > 0:
        filtered_stats = [s for s in filtered_stats if s.matches_played >= min_matches]

    if role_filter:
        filtered_stats = [
            s for s in filtered_stats if any(role.value in role_filter for role in s.roles)
        ]

    if search_name:
        filtered_stats = [s for s in filtered_stats if search_name.lower() in s.player_name.lower()]

    # Indicateurs de synthèse
    st.header("📊 Résumé du tournoi")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Nombre total de joueurs", len(player_stats))

    with col2:
        players_with_matches = sum(1 for s in player_stats if s.matches_played > 0)
        st.metric("Joueurs ayant joué", players_with_matches)

    with col3:
        completed_matches = [m for m in all_matches if m.is_complete]
        st.metric("Matchs terminés", len(completed_matches))

    with col4:
        if player_stats and player_stats[0].matches_played > 0:
            st.metric("Leader", player_stats[0].player_name)

    st.markdown("---")

    # Tableau des classements
    st.header("📋 Classement")

    if not filtered_stats:
        st.info("Aucun joueur ne correspond aux filtres sélectionnés.")
    else:
        ranking_data: list[dict[str, Any]] = []
        for idx, stat in enumerate(filtered_stats, 1):
            ranking_data.append(
                {
                    "Rang": idx,
                    "Joueur": stat.player_name,
                    "Rôle": ", ".join(role.value for role in stat.roles),
                    "Matchs": stat.matches_played,
                    "Victoires": stat.wins,
                    "Défaites": stat.losses,
                    "% Victoires": f"{stat.win_rate:.1f}%",
                    "Points pour": stat.points_for,
                    "Points contre": stat.points_against,
                    "Goal-average": stat.goal_average,
                }
            )

        df_ranking = pd.DataFrame(ranking_data)

        st.dataframe(  # pyright: ignore[reportUnknownMemberType]
            df_ranking,
            width="stretch",
            hide_index=True,
            column_config={
                "Rang": st.column_config.NumberColumn(
                    "Rang",
                    help="Position du joueur au classement",
                    format="%d",
                ),
                "Joueur": st.column_config.TextColumn(
                    "Joueur",
                    help="Nom du joueur",
                    width="medium",
                ),
                "Rôle": st.column_config.TextColumn(
                    "Rôle",
                    help="Rôle du joueur",
                    width="small",
                ),
                "Matchs": st.column_config.NumberColumn(
                    "Matchs",
                    help="Nombre total de matchs joués",
                ),
                "Victoires": st.column_config.NumberColumn(
                    "Victoires",
                    help="Nombre total de victoires",
                ),
                "Défaites": st.column_config.NumberColumn(
                    "Défaites",
                    help="Nombre total de défaites",
                ),
                "% Victoires": st.column_config.TextColumn(
                    "% Victoires",
                    help="Pourcentage de victoires",
                ),
                "Points pour": st.column_config.NumberColumn(
                    "Points pour",
                    help="Total des points marqués",
                ),
                "Points contre": st.column_config.NumberColumn(
                    "Points contre",
                    help="Total des points encaissés",
                ),
                "Goal-average": st.column_config.NumberColumn(
                    "Goal-average",
                    help="Points pour - points contre",
                ),
            },
        )

        # Export
        if st.button("📥 Exporter le classement en CSV"):
            csv = df_ranking.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Télécharger le CSV",
                data=csv,
                file_name="classement_tournoi.csv",
                mime="text/csv",
            )

    # Tops
    st.header("🌟 Meilleures performances")

    if player_stats and player_stats[0].matches_played > 0:
        top_col1, top_col2, top_col3 = st.columns(3)

        with top_col1:
            st.subheader("🥇 Plus grand nombre de victoires")
            top_wins = sorted(
                [s for s in player_stats if s.matches_played >= min_matches],
                key=lambda s: s.wins,
                reverse=True,
            )[:5]

            for idx, stat in enumerate(top_wins, 1):
                st.markdown(
                    f"{idx}. **{stat.player_name}** - {stat.wins} victoire(s) ({stat.matches_played} match(s))"
                )

        with top_col2:
            st.subheader("🎯 Meilleur taux de victoire")
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
            st.subheader("📊 Meilleur goal-average")
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
        st.info(
            "Aucun match terminé pour le moment. Les résultats apparaîtront dès que des matchs seront joués."
        )

    # Classements par rôle
    st.header("👥 Classement par rôle")

    role_tabs = st.tabs([r.value for r in PlayerRole])

    for idx, role in enumerate(PlayerRole):
        with role_tabs[idx]:
            role_stats = [
                s for s in player_stats if any(r == role for r in s.roles) and s.matches_played > 0
            ]

            if not role_stats:
                st.info(f"Aucun joueur {role.value} n’a encore de match terminé.")
            else:
                role_data: list[dict[str, Any]] = []
                for rank_idx, stat in enumerate(role_stats, 1):
                    role_data.append(
                        {
                            "Rang": rank_idx,
                            "Joueur": stat.player_name,
                            "Matchs": stat.matches_played,
                            "Victoires": stat.wins,
                            "% Victoires": f"{stat.win_rate:.1f}%",
                            "Goal-average": stat.goal_average,
                        }
                    )

                df_role = pd.DataFrame(role_data)
                st.dataframe(df_role, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

    # Explication du classement
    with st.expander("ℹ️ Comment fonctionne le classement", expanded=False):
        st.markdown(
            """
        ### Critères de classement

        Les joueurs sont classés selon les critères suivants (dans l’ordre) :

        1. **Victoires** (décroissant) : plus de victoires = meilleur classement
        2. **Goal-average** (décroissant) : Points pour - Points contre
        3. **Points pour** (décroissant) : total des points marqués
        4. **Nom** (ordre alphabétique) : départage final

        ### Explication des indicateurs

        - **Matchs** : nombre total de matchs joués
        - **Victoires** : nombre de matchs gagnés
        - **Défaites** : nombre de matchs perdus
        - **% Victoires** : pourcentage de matchs gagnés (Victoires / Matchs × 100)
        - **Points pour** : total des points marqués sur l’ensemble des matchs
        - **Points contre** : total des points encaissés sur l’ensemble des matchs
        - **Goal-average** : Points pour - Points contre (plus c’est élevé, mieux c’est)

        ### Astuces

        - Utilisez les filtres pour vous concentrer sur un groupe de joueurs
        - Le filtre « nombre minimum de matchs » aide à comparer des joueurs avec une expérience comparable
        - Exportez le classement en CSV pour l’analyser ailleurs
        """
        )

    st.markdown("---")
    st.caption(
        "Le classement se met à jour automatiquement à mesure que les résultats sont saisis."
    )


if __name__ == "__main__":
    main()
