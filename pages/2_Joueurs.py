"""Page de gestion des joueurs."""

import pandas as pd
import streamlit as st

from Acceuil import get_storage
from src.petanque_manager.core.models import Player, PlayerRole
from src.petanque_manager.core.scheduler import calculate_role_requirements
from src.petanque_manager.infra.auth import is_authenticated, show_login_form


def main() -> None:
    st.set_page_config(
        page_title="Joueurs - Tournoi de pétanque",
        page_icon="👥",
        layout="wide",
    )
    show_info_toast()
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
        requirements = calculate_role_requirements(config.mode, len(active_players))

        st.subheader("🎯 Besoins en formats de matchs")
        mode_col1, mode_col2, mode_col3 = st.columns(3)
        with mode_col1:
            st.metric("Triplette (3v3)", requirements.triplette_count)
        with mode_col2:
            st.metric("Doublette (2v2)", requirements.doublette_count)
        with mode_col3:
            st.metric("Hybride (3v2)", requirements.hybrid_count)

        st.subheader("📋 Besoins par rôle")
        req_cols = st.columns(3)

        idx = 0
        roles_to_show = [
            (PlayerRole.TIREUR, requirements.tireur_needed),
            (PlayerRole.POINTEUR, requirements.pointeur_needed),
            (PlayerRole.MILIEU, requirements.milieu_needed),
        ]

        for role, needed in roles_to_show:
            with req_cols[idx]:
                # Count players who CAN play this role (have it in their roles list)
                current = sum(1 for p in active_players if role in p.roles)
                deficit = needed - current
                st.metric(
                    role.value,
                    f"{current} disponibles / {needed} requis",
                    delta_arrow="down" if deficit > 0 else "off",
                    delta=f"{deficit:+d}" if deficit != 0 else "✓",
                    delta_color="inverse" if deficit > 0 else "normal",
                )
            idx += 1

        if any(
            (needed - sum(1 for p in active_players if role in p.roles)) != 0
            for role, needed in roles_to_show
        ):
            st.warning(
                "⚠️ Le nombre de joueurs disponibles par rôle ne correspond pas aux besoins. "
                "Certaines parties pourront utiliser des formats alternatifs."
            )

    st.markdown("---")

    # Gestion des joueurs avec data_editor
    st.subheader("📋 Gestion des joueurs")

    if can_edit:
        st.info(
            "💡 **Astuce** : Cochez les cases pour définir les rôles de chaque joueur. "
            "Vous pouvez ajouter de nouvelles lignes, modifier les existantes, puis cliquer sur Sauvegarder."
        )

        # Préparer les données pour le data_editor
        player_data_for_editor: list[dict[str, str | int | bool]] = []

        for player in all_players:
            player_data_for_editor.append(
                {
                    "ID": player.id or 0,
                    "Nom": player.name,
                    "Tireur": PlayerRole.TIREUR in player.roles,
                    "Pointeur": PlayerRole.POINTEUR in player.roles,
                    "Milieu": PlayerRole.MILIEU in player.roles,
                    "Actif": player.active,
                }
            )

        # Créer le DataFrame
        df_editor = pd.DataFrame(player_data_for_editor)

        # Si le DataFrame est vide, créer une structure vide avec les colonnes
        if df_editor.empty:
            df_editor = pd.DataFrame(columns=["ID", "Nom", "Tireur", "Pointeur", "Milieu", "Actif"])
            df_editor = df_editor.astype(
                {
                    "ID": "int64",
                    "Nom": "str",
                    "Tireur": "bool",
                    "Pointeur": "bool",
                    "Milieu": "bool",
                    "Actif": "bool",
                }
            )

        # Configuration des colonnes
        column_config = {
            "ID": st.column_config.NumberColumn(
                "ID",
                help="ID du joueur (auto-généré)",
                disabled=True,
                width="small",
            ),
            "Nom": st.column_config.TextColumn(
                "Nom",
                help="Nom du joueur",
                max_chars=100,
                required=True,
                width="medium",
            ),
            "Tireur": st.column_config.CheckboxColumn(
                "Tireur",
                help="Le joueur peut jouer Tireur",
                default=False,
                width="small",
            ),
            "Pointeur": st.column_config.CheckboxColumn(
                "Pointeur",
                help="Le joueur peut jouer Pointeur",
                default=False,
                width="small",
            ),
            "Milieu": st.column_config.CheckboxColumn(
                "Milieu",
                help="Le joueur peut jouer Milieu",
                default=False,
                width="small",
            ),
            "Actif": st.column_config.CheckboxColumn(
                "Actif",
                help="Le joueur est actif dans le tournoi",
                default=True,
                width="small",
            ),
        }

        # Data editor
        edited_df = st.data_editor(
            df_editor,
            column_config=column_config,
            width="stretch",
            num_rows="dynamic",  # Permet d'ajouter/supprimer des lignes
            hide_index=True,
            key="players_editor",
        )

        # Boutons d'action
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            save_button = st.button(
                "💾 Sauvegarder tous les changements", type="primary", width="stretch"
            )

        with col2:
            if st.button("🔄 Annuler", width="stretch"):
                st.rerun()

        with col3:
            nb_changes = len(edited_df) - len(df_editor)
            if nb_changes != 0:
                st.metric("Modifications", f"{nb_changes:+d}")

        # Traitement de la sauvegarde
        if save_button:
            errors: list[str] = []
            success_count = 0
            update_count = 0
            add_count = 0
            delete_count = 0

            try:
                # Valider et sauvegarder chaque ligne
                for idx, row in edited_df.iterrows():
                    line_num = int(idx) + 1  # type: ignore
                    try:
                        # Validation du nom
                        name = str(row["Nom"]).strip()
                        if not name:
                            errors.append(f"Ligne {line_num}: Le nom ne peut pas être vide")
                            continue

                        # Validation des rôles (au moins un coché)
                        roles: list[PlayerRole] = []
                        if row["Tireur"]:
                            roles.append(PlayerRole.TIREUR)
                        if row["Pointeur"]:
                            roles.append(PlayerRole.POINTEUR)
                        if row["Milieu"]:
                            roles.append(PlayerRole.MILIEU)

                        if not roles:
                            errors.append(
                                f"Ligne {line_num} ({name}): Au moins un rôle doit être sélectionné"
                            )
                            continue

                        player_id = int(row["ID"]) if row["ID"] and row["ID"] > 0 else None
                        active = bool(row["Actif"])

                        # Nouveau joueur (ID = 0 ou None)
                        if (
                            player_id is None
                            or player_id == 0
                            or not any(p.id == player_id for p in all_players)
                        ):
                            player = Player(name=name, roles=roles, active=active)
                            if player_id is not None and player_id > 0:
                                player.id = player_id
                            storage.add_player(player)
                            add_count += 1
                        else:
                            # Mise à jour d'un joueur existant
                            existing_player = storage.get_player(player_id)
                            if existing_player:
                                is_update = False
                                if existing_player.name != name:
                                    is_update = True
                                if set(existing_player.roles) != set(roles):
                                    is_update = True
                                if existing_player.active != active:
                                    is_update = True
                                if not is_update:
                                    continue
                                updated_player = Player(
                                    id=player_id,
                                    name=name,
                                    roles=roles,
                                    active=active,
                                    created_at=existing_player.created_at,
                                )
                                storage.update_player(updated_player)
                                update_count += 1
                            else:
                                errors.append(
                                    f"Ligne {line_num}: Joueur ID {player_id} introuvable"
                                )
                                continue

                        success_count += 1

                    except ValueError as e:
                        errors.append(f"Ligne {line_num}: {str(e)}")
                    except Exception as e:
                        errors.append(f"Ligne {line_num}: Erreur inattendue - {str(e)}")
                for player_db in all_players:
                    try:
                        if player_db.id and player_db.id > 0:
                            if not any(
                                int(row["ID"]) == player_db.id
                                for _, row in edited_df.iterrows()
                                if row["ID"] and row["ID"] > 0
                            ):
                                # Supprimer le joueur
                                storage.delete_player(player_db.id)
                                delete_count += 1
                                success_count += 1

                    except ValueError as e:
                        errors.append(f"Suppresion {player_db.name}: {str(e)}")
                    except Exception as e:
                        errors.append(f"Suppresion {player_db.name}: Erreur inattendue - {str(e)}")

                # Afficher les résultats
                if success_count > 0:
                    msg = "Succès :"
                    msgs: list[str] = []
                    if add_count > 0:
                        msgs.append(f" {add_count} ajouté(s)")
                    if update_count > 0:
                        msgs.append(f" {update_count} modifié(s)")
                    if delete_count > 0:
                        msgs.append(f" {delete_count} supprimé(s)")
                    msg += ",".join(msgs)
                    st.success(msg)
                    st.session_state["info_toast"].append({"txt": msg, "ico": "✅"})

                if errors:
                    st.error("❌ Erreurs détectées :")
                    for error in errors:
                        st.write(f"• {error}")
                        st.session_state["info_toast"].append({"txt": error, "ico": "❌"})

                if success_count > 0:
                    st.rerun()

            except Exception as e:
                st.error(f"❌ Erreur lors de la sauvegarde : {e}")

    else:
        # Mode lecture seule pour les non-authentifiés
        st.info("🔒 Connexion requise pour modifier les joueurs")

        player_data_readonly: list[dict[str, str | bool]] = []
        for player in all_players:
            roles_str = ", ".join(role.value for role in player.roles)
            player_data_readonly.append(
                {
                    "Nom": player.name,
                    "Rôles": roles_str,
                    "Actif": "✓" if player.active else "✗",
                }
            )

        df_readonly = pd.DataFrame(player_data_readonly)
        st.dataframe(df_readonly, width="stretch", hide_index=True)  # pyright: ignore[reportUnknownMemberType]

    st.markdown("---")
    st.caption(
        "💡 Astuce : assurez-vous d’avoir un bon équilibre des rôles avant de générer les manches."
    )


def init_toast_workaround() -> None:
    if "info_toast" not in st.session_state:
        st.session_state["info_toast"] = []


def show_info_toast():
    if "info_toast" in st.session_state:
        for info in st.session_state["info_toast"]:
            st.toast(info.get("txt"), icon=info.get("ico"))
        st.session_state["info_toast"] = []


if __name__ == "__main__":
    init_toast_workaround()
    main()
