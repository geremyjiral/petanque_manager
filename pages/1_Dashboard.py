"""Page Tableau de bord avec aperçu et statistiques du tournoi."""

from typing import Any

import pandas as pd
import streamlit as st

from Acceuil import get_storage
from src.petanque_manager.core.stats import get_tournament_summary
from src.petanque_manager.infra.auth import show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Tableau de bord - Tournoi de pétanque",
        page_icon="📊",
        layout="wide",
    )

    show_login_form()

    st.title("📊 Tableau de bord du tournoi")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Veuillez d’abord configurer le tournoi sur la page d’accueil.")
        st.stop()

    # Récupération des données
    players = storage.get_all_players(active_only=True)
    all_rounds = storage.get_all_rounds()
    all_matches = storage.get_all_matches()

    # Statistiques de synthèse
    summary = get_tournament_summary(players, all_matches)

    st.header("📈 Vue d’ensemble du tournoi")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Nombre total de joueurs", summary["total_players"])
        st.metric("Joueurs actifs", summary["active_players"])

    with col2:
        st.metric("Matchs au total", summary["total_matches"])
        st.metric("Matchs terminés", summary["completed_matches"])

    with col3:
        st.metric("Nombre de manches", len(all_rounds))
        st.metric("Matchs en attente", summary["pending_matches"])

    with col4:
        st.metric("Total des points marqués", summary["total_points_scored"])
        st.metric("Moyenne de points / match", summary["avg_points_per_match"])

    # Répartition des formats de matchs
    st.subheader("🎯 Répartition des formats de matchs")

    format_col1, format_col2 = st.columns(2)

    with format_col1:
        st.metric(
            "Matchs en triplette",
            summary["triplette_matches"],
            help="Matchs en 3 contre 3",
        )

    with format_col2:
        st.metric(
            "Matchs en doublette",
            summary["doublette_matches"],
            help="Matchs en 2 contre 2",
        )

    # Statistiques manche par manche
    if all_rounds:
        st.header("📅 Avancement par manche")

        round_data: list[dict[str, str | int]] = []
        for round_obj in all_rounds:
            completed = sum(1 for m in round_obj.matches if m.is_complete)
            total = len(round_obj.matches)
            completion_pct = (completed / total * 100) if total > 0 else 0

            round_data.append(
                {
                    "Manche": f"Manche {round_obj.index + 1}",
                    "Matchs au total": total,
                    "Terminés": completed,
                    "En attente": total - completed,
                    "Avancement %": f"{completion_pct:.0f}%",
                    "Joueurs": round_obj.total_players,
                }
            )

        df_rounds = pd.DataFrame(round_data)
        st.dataframe(df_rounds, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

        # Barre de progression globale
        total_matches = summary["total_matches"]
        completed_matches = summary["completed_matches"]
        if total_matches > 0:
            progress = completed_matches / total_matches
            st.progress(progress, text=f"Progression globale : {progress * 100:.1f}%")

    else:
        st.info(
            "📅 Aucune manche générée pour le moment. Allez sur la page Planning pour générer les manches."
        )

    # Activité récente
    st.header("🕐 Activité récente")

    if all_matches:
        list_completed_matches = [m for m in all_matches if m.is_complete]

        if list_completed_matches:
            # Afficher les 5 derniers matchs terminés
            recent = list_completed_matches[-5:]
            recent_data: list[dict[str, str]] = []
            for match in reversed(recent):
                # Noms des joueurs
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
                        "Manche": f"M{match.round_index + 1}",
                        "Terrain": match.terrain_label,
                        "Équipe A": ", ".join(team_a_names),
                        "Score": f"{match.score_a} - {match.score_b}",
                        "Équipe B": ", ".join(team_b_names),
                        "Vainqueur": "Équipe A"
                        if (match.score_a or 0) > (match.score_b or 0)
                        else "Équipe B"
                        if (match.score_b or 0) > (match.score_a or 0)
                        else "Match nul",
                    }
                )

            df_recent = pd.DataFrame(recent_data)
            st.dataframe(df_recent, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]
        else:
            st.info("Aucun match terminé pour le moment.")
    else:
        st.info("Aucun match généré pour le moment.")

    # Répartition des rôles des joueurs
    if players:
        st.header("👥 Répartition des rôles des joueurs")

        from collections import Counter

        # Count all roles (each player can have multiple roles)
        all_roles: list[str] = []
        for player in players:
            all_roles.extend([role.value for role in player.roles])

        role_counts = Counter(all_roles)

        role_data: list[dict[str, Any]] = [
            {"Rôle": role, "Nombre de joueurs": count} for role, count in role_counts.items()
        ]
        df_roles = pd.DataFrame(role_data)

        col1, col2 = st.columns([1, 2])

        with col1:
            st.caption("Note : Un joueur peut avoir plusieurs rôles")
            st.dataframe(df_roles, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

        with col2:
            st.bar_chart(df_roles.set_index("Rôle"))  # pyright: ignore[reportUnknownMemberType]

    st.markdown("---")
    st.caption(
        "Le tableau de bord se met à jour en temps réel à mesure que les matchs sont saisis."
    )


if __name__ == "__main__":
    main()
