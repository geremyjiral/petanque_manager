"""Page de saisie des résultats des matchs."""

import streamlit as st

from Acceuil import get_storage
from src.petanque_manager.core.models import Player
from src.petanque_manager.infra.auth import is_authenticated, show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Résultats - Tournoi de pétanque",
        page_icon="📝",
        layout="wide",
    )

    show_login_form()

    st.title("📝 Saisie des résultats des matchs")

    storage = get_storage()
    config = storage.load_config()

    if config is None:
        st.warning("⚠️ Veuillez d’abord configurer le tournoi sur la page d’accueil.")
        st.stop()

    # Données
    rounds = storage.get_all_rounds()
    all_matches = storage.get_all_matches()

    if not rounds:
        st.info(
            "📅 Aucune manche générée pour le moment. Générez d’abord les manches sur la page Planning."
        )
        st.stop()

    # Connexion requise pour éditer
    can_edit = is_authenticated()

    if not can_edit:
        st.warning("🔒 Veuillez vous connecter pour saisir ou modifier les résultats.")
        st.info(
            "Vous pouvez consulter les résultats existants, mais la modification nécessite une connexion."
        )

    # Résumé
    completed_matches = [m for m in all_matches if m.is_complete]
    pending_matches = [m for m in all_matches if not m.is_complete]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Matchs au total", len(all_matches))

    with col2:
        st.metric("Terminés", len(completed_matches))

    with col3:
        st.metric("En attente", len(pending_matches))

    st.markdown("---")

    # Sélection de la manche
    st.header("🎯 Saisir les résultats")

    for round_obj in rounds:
        with st.expander(f"Manche {round_obj.index + 1}"):
            # Afficher les matchs de la manche
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

                    # En-tête du match
                    st.markdown(f"### Terrain {match.terrain_label}")
                    st.caption(f"Format : {match.format.value}")

                    # Affichage des équipes
                    col1, col2, col3 = st.columns([2, 1, 2])

                    with col1:
                        st.markdown(f"**Équipe A**  \n{team_a_display}")

                    with col2:
                        st.markdown("**VS**")

                    with col3:
                        st.markdown(f"**Équipe B**  \n{team_b_display}")

                    # Saisie des scores
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

                    # Boutons
                    if can_edit:
                        col_save, col_clear = st.columns(2)

                        with col_save:
                            if st.button(
                                "💾 Enregistrer le score",
                                key=f"save_{match.id}",
                                type="primary" if not match.is_complete else "secondary",
                            ):
                                try:
                                    match.score_a = int(score_a)
                                    match.score_b = int(score_b)
                                    storage.update_match(match)
                                    st.success("✅ Score enregistré !")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur lors de l’enregistrement : {e}")

                        with col_clear:
                            if match.is_complete and st.button(
                                "🗑️ Effacer le score",
                                key=f"clear_{match.id}",
                            ):
                                try:
                                    match.score_a = None
                                    match.score_b = None
                                    storage.update_match(match)
                                    st.success("✅ Score effacé !")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur lors de la suppression : {e}")

                    # Statut actuel
                    if match.is_complete:
                        if (match.score_a or 0) > (match.score_b or 0):
                            st.success(
                                f"✅ Victoire de l’équipe A ! ({match.score_a} - {match.score_b})"
                            )
                        elif (match.score_b or 0) > (match.score_a or 0):
                            st.info(
                                f"✅ Victoire de l’équipe B ! ({match.score_a} - {match.score_b})"
                            )
                        else:
                            st.warning(f"⚖️ Match nul ({match.score_a} - {match.score_b})")
                    else:
                        st.caption("⏳ En attente — aucun score saisi pour le moment")

                    st.divider()

            # Avancement de la manche
            completed_this_round = sum(1 for m in round_obj.matches if m.is_complete)
            total_this_round = len(round_obj.matches)
            completion_pct = (
                (completed_this_round / total_this_round * 100) if total_this_round > 0 else 0
            )

            st.progress(
                completed_this_round / total_this_round if total_this_round > 0 else 0,
                text=f"Avancement de la manche {round_obj.index + 1} : {completion_pct:.0f}% "
                f"({completed_this_round}/{total_this_round})",
            )

    # Aide à la saisie
    if can_edit and pending_matches:
        st.markdown("---")

        with st.expander("⚡ Conseils de saisie rapide", expanded=False):
            st.markdown(
                """
            **Conseils pour aller plus vite :**

            1. **Navigation au clavier** : utilisez la touche Tab pour passer rapidement d’un champ à l’autre
            2. **Entrée pour valider** : appuyez sur Entrée après avoir saisi un score (si vous utilisez un clavier)
            3. **Procéder manche par manche** : terminez une manche avant de passer à la suivante
            4. **Vérifier avant d’enregistrer** : contrôlez les scores avant de cliquer sur Enregistrer

            """
            )

    st.markdown("---")
    st.caption(
        "💡 Astuce : les résultats se mettent à jour en temps réel et impactent immédiatement le classement."
    )


if __name__ == "__main__":
    main()
