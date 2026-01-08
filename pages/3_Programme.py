"""Page de génération et d’affichage du planning."""

import pandas as pd
import streamlit as st

from Acceuil import get_storage
from src.petanque_manager.core.models import Player
from src.petanque_manager.core.scheduler import TournamentScheduler
from src.petanque_manager.infra.auth import is_authenticated, show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Création du programme - Tournoi de pétanque",
        page_icon="📅",
        layout="wide",
    )

    show_login_form()

    st.title("📅 Création du programme")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Veuillez d’abord configurer le tournoi sur la page d’accueil.")
        st.stop()

    can_edit = is_authenticated()

    # Données
    players = storage.get_all_players(active_only=True)
    rounds = storage.get_all_rounds()

    # Résumé
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Joueurs actifs", len(players))

    with col2:
        st.metric("Manches générées", len(rounds))

    with col3:
        st.metric("Manches prévues", config.rounds_count)

    st.markdown("---")

    # Génération des manches
    if can_edit:
        st.header("⚙️ Générer des manches")

        if len(players) < 4:
            st.error("❌ Il faut au moins 4 joueurs actifs pour générer des manches.")
        else:
            with st.expander(
                "🎲 Générer une nouvelle manche"
                if len(rounds) < config.rounds_count
                else "✅ Toutes les manches sont générées",
                expanded=len(rounds) < config.rounds_count,
            ):
                if len(rounds) >= config.rounds_count:
                    st.success("✅ Toutes les manches ont été générées !")
                    st.info(
                        "Pour générer plus de manches, augmentez le champ "
                        "« Nombre de manches » dans la configuration sur la page d’accueil."
                    )
                else:
                    next_round_index = len(rounds)

                    st.markdown(
                        f"""
                    **Génération de la manche {next_round_index + 1}** sur {config.rounds_count}

                    **Paramètres :**
                    - Mode : {config.mode.value}
                    - Joueurs : {len(players)}
                    - Terrains : {config.terrains_count}
                    """
                    )

                    # # Options de génération
                    # use_custom_seed = st.checkbox(
                    #     "Utiliser une graine personnalisée pour cette manche",
                    #     value=False,
                    #     help="Remplace la graine globale uniquement pour cette manche",
                    # )

                    custom_seed = None
                    # if use_custom_seed:
                    #     custom_seed = st.number_input(
                    #         "Graine de la manche",
                    #         min_value=0,
                    #         value=0,
                    #     )

                    if st.button("🎲 Générer la manche", type="primary"):
                        try:
                            with st.spinner("Génération de la manche…"):
                                scheduler = TournamentScheduler(
                                    mode=config.mode,
                                    terrains_count=config.terrains_count,
                                    seed=custom_seed if custom_seed else config.seed,
                                )

                                round_obj, quality_report = scheduler.generate_round(
                                    players=players,
                                    round_index=next_round_index,
                                    previous_rounds=rounds,
                                )

                                # Sauvegarde
                                storage.add_round(round_obj)

                                st.success(f"✅ Manche {next_round_index + 1} générée !")

                                # Rapport de qualité
                                st.subheader("📊 Rapport de qualité")

                                (
                                    quality_col1,
                                    quality_col2,
                                    quality_col3,
                                    quality_col4,
                                    quality_col5,
                                ) = st.columns(5)

                                with quality_col1:
                                    st.metric("Note", quality_report.quality_grade)

                                with quality_col2:
                                    st.metric(
                                        "Partenaires répétés",
                                        quality_report.repeated_partners,
                                        help="Paires de joueurs jouant ensemble plus d’une fois",
                                    )

                                with quality_col3:
                                    st.metric(
                                        "Adversaires répétés",
                                        quality_report.repeated_opponents,
                                        help="Paires de joueurs s’affrontant plus d’une fois",
                                    )

                                with quality_col4:
                                    st.metric(
                                        "Terrains répétés",
                                        quality_report.repeated_terrains,
                                        help="Joueurs jouant sur le même terrain plus d’une fois",
                                    )

                                with quality_col5:
                                    st.metric(
                                        "Matchs en format alternatif",
                                        quality_report.fallback_format_count,
                                        help="Matchs joués dans le format non prioritaire",
                                    )

                                if quality_report.quality_grade in ["A+", "A", "B"]:
                                    st.success("🎉 Excellente qualité de planning !")
                                elif quality_report.quality_grade == "C":
                                    st.info("👍 Bonne qualité de planning")
                                else:
                                    st.warning(
                                        "⚠️ La qualité du planning pourrait être améliorée. "
                                        "Essayez de régénérer avec une autre graine (seed)."
                                    )

                                st.rerun()

                        except ValueError as e:
                            st.error(f"❌ Erreur lors de la génération : {e}")
    else:
        st.info(
            "🔒 Connexion requise pour générer des manches. Consultez les manches existantes ci-dessous."
        )

    # Consultation des manches
    st.header("📋 Consulter les manches")

    if not rounds:
        st.info("Aucune manche générée pour le moment. Générez votre première manche ci-dessus !")
    else:
        for round_obj in rounds:
            with st.expander(f"Manche {round_obj.index + 1}"):
                # Infos manche
                completed_matches = sum(1 for m in round_obj.matches if m.is_complete)
                total_matches = len(round_obj.matches)
                completion_pct = (
                    (completed_matches / total_matches * 100) if total_matches > 0 else 0
                )

                round_col1, round_col2, round_col3 = st.columns(3)

                with round_col1:
                    st.metric("Matchs", total_matches)

                with round_col2:
                    st.metric("Terminés", f"{completed_matches} / {total_matches}")

                with round_col3:
                    st.metric("Avancement", f"{completion_pct:.0f}%")

                # Liste des matchs
                st.subheader("🎯 Liste des matchs")

                for match in round_obj.matches:
                    with st.container(border=True):
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

                        team_a_display = " + ".join(
                            [f"{p.name} ({', '.join(r.value for r in p.roles)})" for p in team_a_players]
                        )
                        team_b_display = " + ".join(
                            [f"{p.name} ({', '.join(r.value for r in p.roles)})" for p in team_b_players]
                        )

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
                                    st.success("Victoire de l’équipe A !")
                                elif (match.score_b or 0) > (match.score_a or 0):
                                    st.info("Victoire de l’équipe B !")
                                else:
                                    st.warning("Match nul")
                            else:
                                st.markdown("_En attente_")

                # Export CSV
                if st.button(f"📥 Exporter la manche {round_obj.index + 1} en CSV"):
                    match_data: list[dict[str, str | int]] = []

                    for match in round_obj.matches:
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
                                "Équipe A": " + ".join(team_a_names),
                                "Équipe B": " + ".join(team_b_names),
                                "Score A": match.score_a or "",
                                "Score B": match.score_b or "",
                                "Statut": "Terminé" if match.is_complete else "En attente",
                            }
                        )

                    df_export = pd.DataFrame(match_data)
                    csv = df_export.to_csv(index=False).encode("utf-8")

                    st.download_button(
                        label="Télécharger le CSV",
                        data=csv,
                        file_name=f"manche_{round_obj.index + 1}.csv",
                        mime="text/csv",
                    )

    # Suppression des manches
    if can_edit and rounds:
        st.markdown("---")

        with st.expander("⚠️ Zone dangereuse", expanded=False):
            st.warning(
                "⚠️ **Attention** : supprimer les manches supprimera aussi tous les matchs et résultats associés. "
                "Cette action est irréversible !"
            )

            if st.button("🗑️ Supprimer toutes les manches", type="secondary"):
                if st.session_state.get("confirm_delete_rounds"):
                    storage.delete_all_rounds()
                    st.success("✅ Toutes les manches ont été supprimées")
                    st.session_state.confirm_delete_rounds = False
                    st.rerun()
                else:
                    st.session_state.confirm_delete_rounds = True
                    st.warning("⚠️ Cliquez une seconde fois pour confirmer la suppression")

    st.markdown("---")
    st.caption(
        "💡 Astuce : la génération des manches utilise des algorithmes pour minimiser les partenaires et adversaires répétés."
    )


if __name__ == "__main__":
    main()
