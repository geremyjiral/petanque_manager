"""Page de génération et d'affichage du planning."""

import io
from typing import Any

import pandas as pd
import streamlit as st

from Acceuil import get_storage
from src.petanque_manager.core.models import Player, Round, ScheduleQualityReport
from src.petanque_manager.core.scheduler import ConfigScoringMatchs, TournamentScheduler
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
        return

    can_edit = is_authenticated()

    players = storage.get_all_players(active_only=True)
    rounds = storage.get_all_rounds()

    # This prevents repeated database queries when displaying matches
    all_players = storage.get_all_players(
        active_only=False
    )  # Include inactive for historical matches
    players_by_id: dict[int, Player] = {p.id: p for p in all_players if p.id is not None}

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
                expanded=True,
            ):
                if rounds:
                    st.markdown("**📊 Qualité des manches générées**")
                    st.markdown(f"""
                                Voici la méthode du calcul de la qualité utilisée :
                                - En cas de partenaires répétés : pénalité de {ConfigScoringMatchs.repeated_partners_penalty} points par paire
                                - En cas d'adversaires répétés : pénalité de {ConfigScoringMatchs.repeated_opponents_penalty} points par paire
                                - En cas de terrains répétés : pénalité de {ConfigScoringMatchs.repeated_terrains_penalty} points par joueur
                                - En cas de joueurs jouant dans une même partie plus d'une fois : pénalité de {ConfigScoringMatchs.repeated_same_match_penalty} points par paire
                                - En cas de format alternatif : pénalité de {ConfigScoringMatchs.fallback_format_penalty_per_player} points par joueur
                                - Note finale basée sur le score total :
                                    - A+ : 0 points
                                    - A  : 0-20 points
                                    - B  : 21-50 points
                                    - C  : 51-100 points
                                    - D  : 101-300 points
                                    - E  : >300 points
                                """)
                    quality_data: list[dict[str, str | int | float]] = []
                    for r in rounds:
                        if r.quality_report:
                            quality_data.append(
                                {
                                    "Manche": r.index + 1,
                                    "Note": r.quality_report.quality_grade,
                                    "Score": f"{r.quality_report.total_score:.1f}",
                                    "Partenaires répétés": r.quality_report.repeated_partners,
                                    "Adversaires répétés": r.quality_report.repeated_opponents,
                                    "Joueurs présents dans une même partie plus d'une fois": r.quality_report.repeated_games,
                                    "Terrains répétés": r.quality_report.repeated_terrains,
                                    "Format alternatif": r.quality_report.fallback_format_count,
                                }
                            )

                    if quality_data:
                        df_quality = pd.DataFrame(quality_data)
                        st.dataframe(df_quality, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

                        # Average quality
                        avg_score = sum(
                            r.quality_report.total_score for r in rounds if r.quality_report
                        ) / len([r for r in rounds if r.quality_report])
                        st.caption(f"💡 Score moyen : {avg_score:.1f}")
                    else:
                        st.info(
                            "Les manches existantes n'ont pas de rapport de qualité. "
                            "Les nouvelles manches générées incluront automatiquement cette information."
                        )

                    st.markdown("---")
                if "generation_attempts" in st.session_state:
                    attempts_prev: int = st.session_state["generation_attempts"]
                    st.info(f"ℹ️ Dernière génération a pris {attempts_prev} tentatives.")
                if len(rounds) >= config.rounds_count:
                    st.success("✅ Toutes les manches ont été générées !")
                    bag_quality_warning(rounds, players_by_id)
                    st.info(
                        "Pour générer plus de manches, augmentez le champ "
                        "« Nombre de manches » dans la configuration sur la page d'accueil."
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

                    attempts_max = st.number_input(
                        "Nombre de tentatives pour trouver une bonne manche",
                        min_value=100,
                        max_value=10_000,
                        value=500,
                        step=100,
                        help="Plus de tentatives peuvent améliorer la qualité du tirage, mais prendront plus de temps à générer.",
                    )
                    if st.button("🎲 Générer la manche", type="primary"):
                        try:
                            # Create placeholders for progress feedback
                            status_text = st.empty()

                            status_text.text("🔄 Initialisation de la génération...")

                            scheduler = TournamentScheduler(
                                mode=config.mode,
                                terrains_count=config.terrains_count,
                            )

                            chart_placeholder = st.empty()

                            round_obj, quality_report, attempts, score_history, phase_history = (
                                scheduler.generate_round(
                                    players=players,
                                    round_index=next_round_index,
                                    previous_rounds=rounds,
                                    attempts=attempts_max,
                                    on_score=lambda scores, phases: update_chart(
                                        scores, phases, chart_placeholder
                                    ),
                                )
                            )
                            # Final chart update with all data
                            update_chart(score_history, phase_history, chart_placeholder)

                            st.session_state["quality_report"] = quality_report
                            st.session_state["generation_attempts"] = attempts
                            st.session_state["score_history"] = score_history
                            st.session_state["phase_history"] = phase_history

                            # Clear progress indicators
                            status_text.empty()

                            # Sauvegarde
                            storage.add_round(round_obj)

                            st.rerun()

                        except ValueError as e:
                            st.error(f"❌ Erreur lors de la génération : {e}")

                    if "quality_report" in st.session_state:
                        quality_report_prev: ScheduleQualityReport = st.session_state[
                            "quality_report"
                        ]

                        st.success(f"✅ Manche {next_round_index} générée !")

                        # Rapport de qualité
                        st.subheader("📊 Rapport de qualité")

                        (
                            quality_col1,
                            quality_col2,
                            quality_col3,
                            quality_col4,
                            quality_col5,
                            quality_col6,
                        ) = st.columns(6)

                        with quality_col1:
                            st.metric("Note", quality_report_prev.quality_grade)

                        with quality_col2:
                            st.metric(
                                "Partenaires répétés",
                                quality_report_prev.repeated_partners,
                                help="Paires de joueurs jouant ensemble plus d’une fois",
                            )

                        with quality_col3:
                            st.metric(
                                "Adversaires répétés",
                                quality_report_prev.repeated_opponents,
                                help="Paires de joueurs s’affrontant plus d’une fois",
                            )

                        with quality_col4:
                            st.metric(
                                "Joueurs présents dans une même partie plus d'une fois",
                                quality_report_prev.repeated_games,
                                help="Paires de joueurs jouant dans une même partie plus d'une fois",
                            )

                        with quality_col5:
                            st.metric(
                                "Terrains répétés",
                                quality_report_prev.repeated_terrains,
                                help="Joueurs jouant sur le même terrain plus d’une fois",
                            )

                        with quality_col6:
                            st.metric(
                                "Matchs en format alternatif",
                                quality_report_prev.fallback_format_count,
                                help="Matchs joués dans le format non prioritaire",
                            )

                        if quality_report_prev.quality_grade in ["A+", "A", "B"]:
                            st.success("🎉 Excellente qualité de planning !")
                        elif quality_report_prev.quality_grade == "C":
                            st.info("👍 Bonne qualité de planning")
                        else:
                            st.warning("⚠️ La qualité du planning pourrait être améliorée. ")
                if "score_history" in st.session_state:
                    st.subheader("📈 Historique des scores pendant la génération")
                    score_history_prev: list[float] = st.session_state["score_history"]
                    phase_history_prev: list[str] = st.session_state["phase_history"]
                    update_chart(score_history_prev, phase_history_prev, st.empty())

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

                round_col1, round_col2, round_col3, round_col4 = st.columns(4)

                with round_col1:
                    st.metric("Matchs", total_matches)

                with round_col2:
                    st.metric("Terminés", f"{completed_matches} / {total_matches}")

                with round_col3:
                    st.metric("Avancement", f"{completion_pct:.0f}%")
                with round_col4:
                    if st.button(
                        "Supprimer la manche",
                        type="secondary",
                        key=f"delete_round_{round_obj.id}",
                    ):
                        if round_obj.id:
                            storage.delete_round(round_obj.id)
                            st.rerun()

                # FEATURE: Display quality report for this round (now persisted)
                if round_obj.quality_report:
                    st.subheader("📊 Rapport de qualité")

                    (
                        qr_col1,
                        qr_col2,
                        qr_col3,
                        qr_col4,
                        qr_col5,
                        qr_col6,
                    ) = st.columns(6)

                    with qr_col1:
                        st.metric("Note", round_obj.quality_report.quality_grade)

                    with qr_col2:
                        st.metric(
                            "Partenaires répétés",
                            round_obj.quality_report.repeated_partners,
                            help="Paires de joueurs jouant ensemble plus d'une fois",
                        )

                    with qr_col3:
                        st.metric(
                            "Adversaires répétés",
                            round_obj.quality_report.repeated_opponents,
                            help="Paires de joueurs s'affrontant plus d'une fois",
                        )

                    with qr_col4:
                        st.metric(
                            "Joueurs présents dans une même partie plus d'une fois",
                            round_obj.quality_report.repeated_games,
                            help="Paires de joueurs jouant dans une même partie plus d'une fois",
                        )

                    with qr_col5:
                        st.metric(
                            "Terrains répétés",
                            round_obj.quality_report.repeated_terrains,
                            help="Joueurs jouant sur le même terrain plus d'une fois",
                        )

                    with qr_col6:
                        st.metric(
                            "Matchs en format alternatif",
                            round_obj.quality_report.fallback_format_count,
                            help="Matchs joués dans le format non prioritaire",
                        )

                    st.caption(f"Score total: {round_obj.quality_report.total_score:.1f}")

                # Liste des matchs
                st.subheader("🎯 Liste des matchs")

                for match in round_obj.matches:
                    with st.container(border=True):
                        # OPTIMIZATION: Use pre-loaded player dictionary instead of database queries
                        team_a_players: list[Player] = [
                            players_by_id[pid]
                            for pid in match.team_a_player_ids
                            if pid in players_by_id
                        ]
                        team_b_players: list[Player] = [
                            players_by_id[pid]
                            for pid in match.team_b_player_ids
                            if pid in players_by_id
                        ]

                        team_a_display = " + ".join(
                            [
                                f"{p.name} ({', '.join(r.value for r in p.roles)})"
                                for p in team_a_players
                            ]
                        )
                        team_b_display = " + ".join(
                            [
                                f"{p.name} ({', '.join(r.value for r in p.roles)})"
                                for p in team_b_players
                            ]
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
                        # OPTIMIZATION: Use pre-loaded player dictionary
                        team_a_names: list[str] = [
                            players_by_id[pid].name
                            for pid in match.team_a_player_ids
                            if pid in players_by_id
                        ]
                        team_b_names: list[str] = [
                            players_by_id[pid].name
                            for pid in match.team_b_player_ids
                            if pid in players_by_id
                        ]

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

        st.markdown("---")
        st.subheader("📊 Export complet du programme")

        if st.button("📥 Exporter tout le programme en Excel", type="primary"):
            # Prepare data for all matches across all rounds
            full_schedule_data: list[dict[str, str | int | None]] = []

            for round_obj in rounds:
                for match in round_obj.matches:
                    team_a_players_export: list[str] = [
                        players_by_id[pid].name
                        for pid in match.team_a_player_ids
                        if pid in players_by_id
                    ]
                    team_b_players_export: list[str] = [
                        players_by_id[pid].name
                        for pid in match.team_b_player_ids
                        if pid in players_by_id
                    ]

                    # Pad teams to 3 players with None
                    while len(team_a_players_export) < 3:
                        team_a_players_export.append("")
                    while len(team_b_players_export) < 3:
                        team_b_players_export.append("")

                    full_schedule_data.append(
                        {
                            "Manche": round_obj.index + 1,
                            "Terrain": match.terrain_label,
                            "Équipe A - Joueur 1": team_a_players_export[0],
                            "Équipe A - Joueur 2": team_a_players_export[1],
                            "Équipe A - Joueur 3": team_a_players_export[2]
                            if len(team_a_players_export) > 2
                            else "",
                            "Score A": match.score_a if match.score_a is not None else "",
                            "Score B": match.score_b if match.score_b is not None else "",
                            "Équipe B - Joueur 1": team_b_players_export[0],
                            "Équipe B - Joueur 2": team_b_players_export[1],
                            "Équipe B - Joueur 3": team_b_players_export[2]
                            if len(team_b_players_export) > 2
                            else "",
                        }
                    )

            # Create DataFrame and export to Excel
            df_full = pd.DataFrame(full_schedule_data)

            # Use BytesIO to create Excel file in memory
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_full.to_excel(writer, index=False, sheet_name="Programme complet")  # pyright: ignore[reportUnknownMemberType]

                # Auto-adjust column widths for readability
                worksheet = writer.sheets["Programme complet"]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except Exception:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

            excel_buffer.seek(0)

            st.download_button(
                label="📥 Télécharger le programme complet (Excel)",
                data=excel_buffer,
                file_name="programme_complet_petanque.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            st.success(f"✅ Programme complet prêt ({len(full_schedule_data)} matchs)")

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


def bag_quality_warning(rounds: list[Round], players_by_id: dict[int, Player]) -> None:
    players_partners: dict[int, dict[int, int]] = {}
    players_opponents: dict[int, dict[int, int]] = {}
    players_same_match: dict[int, dict[int, int]] = {}
    for r in rounds:
        for m in r.matches:
            for pid in m.team_a_player_ids:
                if pid not in players_partners:
                    players_partners[pid] = {}
                if pid not in players_opponents:
                    players_opponents[pid] = {}
                if pid not in players_same_match:
                    players_same_match[pid] = {}
                for partner in set(m.team_a_player_ids) - {pid}:
                    players_partners[pid][partner] = players_partners[pid].get(partner, 0) + 1
                for opponent in set(m.team_b_player_ids):
                    players_opponents[pid][opponent] = players_opponents[pid].get(opponent, 0) + 1
                for same in set(m.team_a_player_ids + m.team_b_player_ids) - {pid}:
                    players_same_match[pid][same] = players_same_match[pid].get(same, 0) + 1
            for pid in m.team_b_player_ids:
                if pid not in players_partners:
                    players_partners[pid] = {}
                if pid not in players_opponents:
                    players_opponents[pid] = {}
                if pid not in players_same_match:
                    players_same_match[pid] = {}
                for partner in set(m.team_b_player_ids) - {pid}:
                    players_partners[pid][partner] = players_partners[pid].get(partner, 0) + 1
                for opponent in set(m.team_a_player_ids):
                    players_opponents[pid][opponent] = players_opponents[pid].get(opponent, 0) + 1
                for same in set(m.team_a_player_ids + m.team_b_player_ids) - {pid}:
                    players_same_match[pid][same] = players_same_match[pid].get(same, 0) + 1
    partners_warnings: set[tuple[int, int]] = set()
    for p, partners in players_partners.items():
        for partner, count in partners.items():
            if count > 1:
                if (min(p, partner), max(p, partner)) not in partners_warnings:
                    partners_warnings.add((min(p, partner), max(p, partner)))

    opponents_warnings: set[tuple[int, int]] = set()
    for p, opponents in players_opponents.items():
        for opponent, count in opponents.items():
            if count > 1:
                if (min(p, opponent), max(p, opponent)) not in opponents_warnings:
                    opponents_warnings.add((min(p, opponent), max(p, opponent)))

    same_match_warnings: set[tuple[int, int]] = set()
    for p, same_matches in players_same_match.items():
        for same, count in same_matches.items():
            if count > 1:
                if (min(p, same), max(p, same)) not in same_match_warnings:
                    same_match_warnings.add((min(p, same), max(p, same)))
    if partners_warnings:
        with st.container(border=True):
            st.subheader("**⚠️ Partenaires similaires !**")
            for p1, p2 in partners_warnings:
                name1 = players_by_id[p1].name if p1 in players_by_id else f"Joueur {p1}"
                name2 = players_by_id[p2].name if p2 in players_by_id else f"Joueur {p2}"
                st.warning(f"Les joueurs {name1} et {name2} seront partenaires plusieurs fois.")
    if opponents_warnings:
        with st.container(border=True):
            st.subheader("**⚠️ Adversaires similaires !**")
            for p1, p2 in opponents_warnings:
                name1 = players_by_id[p1].name if p1 in players_by_id else f"Joueur {p1}"
                name2 = players_by_id[p2].name if p2 in players_by_id else f"Joueur {p2}"
                st.warning(f"Les joueurs {name1} et {name2} vont s'affronter plusieurs fois.")

    if same_match_warnings:
        with st.container(border=True):
            st.subheader("**⚠️ Joueurs jouant dans une même partie plusieurs fois !**")
            for p1, p2 in same_match_warnings:
                name1 = players_by_id[p1].name if p1 in players_by_id else f"Joueur {p1}"
                name2 = players_by_id[p2].name if p2 in players_by_id else f"Joueur {p2}"
                st.warning(
                    f"Les joueurs {name1} et {name2} joueront dans une même partie plusieurs fois."
                )


def update_chart(scores: list[float], phases: list[str], chart_placeholder: Any) -> None:
    if len(scores) % 10 == 0 or len(scores) <= 5:
        best_scores: list[float] = []
        current_best = float("inf")
        for s in scores:
            current_best = min(current_best, s)
            best_scores.append(current_best)

        # Build long-format DataFrame: one row per data point
        rows: list[dict[str, object]] = []
        for i, (s, phase) in enumerate(zip(scores, phases, strict=True)):
            rows.append({"Tentative": i, "Score": s, "Type": phase})
        for i, b in enumerate(best_scores):
            rows.append({"Tentative": i, "Score": b, "Type": "Meilleur score"})

        df = pd.DataFrame(rows)

        import altair as alt  # pyright: ignore[reportMissingImports]

        chart = (
            alt.Chart(df)  # pyright: ignore[reportUnknownMemberType]
            .mark_circle(size=20)
            .encode(
                x=alt.X("Tentative:Q"),
                y=alt.Y("Score:Q"),
                color=alt.Color(
                    "Type:N",
                    scale=alt.Scale(
                        domain=["Exploration", "Exploitation", "Meilleur score"],
                        range=["#ff6b6b", "#ffa94d", "#51cf66"],
                    ),
                ),
            )
        )
        chart_placeholder.altair_chart(chart, width="stretch")  # pyright: ignore[reportUnknownMemberType]


if __name__ == "__main__":
    main()
