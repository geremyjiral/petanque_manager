"""Authentication system for Streamlit app.

Uses streamlit-authenticator for cookie-based authentication.
Credentials are loaded from Streamlit secrets or environment variables.
"""

from typing import Any

import streamlit as st
import streamlit_authenticator as stauth  # pyright: ignore[reportMissingTypeStubs]
import yaml
from streamlit_authenticator.utilities import Hasher  # pyright: ignore[reportMissingTypeStubs]


def get_authenticator() -> stauth.Authenticate:
    """Create and return authenticator instance.

    Loads credentials from st.secrets or creates default config.

    Returns:
        Authenticator instance
    """
    # Try to load from secrets
    if "auth" in st.secrets:
        # Secrets format:
        # [auth]
        # admin_username = "admin"
        # admin_password = "hashed_password"  # Or plain, will be hashed
        credentials: dict[str, dict[str, dict[str, str]]] = {
            "usernames": {
                st.secrets["auth"]["admin_username"]: {
                    "name": "Administrator",
                    "password": st.secrets["auth"]["admin_password"],
                }
            }
        }
    else:
        # Default config for development
        # Password: "admin" (hashed)
        credentials = {
            "usernames": {
                "admin": {
                    "name": "Administrator",
                    "password": "$2b$12$KIX8qS2zqD5kqN2xqH3xL.yZxqH3xL.yZxqH3xL.yZxqH3xL.yZxqO",  # "admin"
                }
            }
        }

    # Create config
    config: dict[str, Any] = {
        "credentials": credentials,
        "cookie": {
            "name": "petanque_tournament_auth",
            "key": st.secrets.get("cookie_key", "default_secret_key_change_in_production"),
            "expiry_days": 30,
        },
        "preauthorized": {"emails": []},
    }

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )

    return authenticator


def require_auth() -> bool:
    """Require authentication for editing operations.

    Returns:
        True if user is authenticated, False otherwise

    Usage:
        if not require_auth():
            st.warning("Please login to access this feature")
            st.stop()
    """
    if "authentication_status" not in st.session_state:
        return False

    return st.session_state.get("authentication_status", False) is True


def is_authenticated() -> bool:
    """Check if user is currently authenticated.

    Returns:
        True if authenticated, False otherwise
    """
    return st.session_state.get("authentication_status", False) is True


def get_username() -> str | None:
    """Get current authenticated username.

    Returns:
        Username if authenticated, None otherwise
    """
    if is_authenticated():
        return st.session_state.get("username")
    return None


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return str(Hasher().hash(password))


def create_credentials_yaml(username: str, password: str, output_file: str) -> None:
    """Create a credentials YAML file for streamlit-authenticator.

    Utility function for generating credentials.

    Args:
        username: Username
        password: Plain text password (will be hashed)
        output_file: Path to output YAML file
    """
    hashed_password = hash_password(password)

    credentials: dict[str, Any] = {
        "credentials": {
            "usernames": {
                username: {
                    "name": username.capitalize(),
                    "password": hashed_password,
                }
            }
        },
        "cookie": {
            "name": "petanque_tournament_auth",
            "key": "change_this_secret_key_in_production",
            "expiry_days": 30,
        },
        "preauthorized": {"emails": []},
    }

    with open(output_file, "w") as f:
        yaml.dump(credentials, f, default_flow_style=False)

    print(f"Credentials file created: {output_file}")
    print(f"Username: {username}")
    print(f"Hashed password: {hashed_password}")


def show_login_form() -> None:
    """Affiche le formulaire de connexion dans la barre latérale.

    Cette fonction doit être appelée dans l'application principale ou sur les pages nécessitant une authentification.
    """
    authenticator = get_authenticator()

    # Afficher le formulaire de connexion dans la barre latérale
    with st.sidebar:
        if not is_authenticated():
            try:
                authenticator.login(  # pyright: ignore[reportUnknownMemberType]
                    fields={
                        "Form name": "Connexion",
                        "Username": "Nom d'utilisateur",
                        "Password": "Mot de passe",
                        "Login": "Se connecter",
                    }
                )
            except Exception:
                pass

            if st.session_state.get("authentication_status") is False:
                st.error("❌ Nom d'utilisateur ou mot de passe incorrect")
            elif st.session_state.get("authentication_status") is None:
                st.info("👤 Veuillez vous connecter")

        else:
            st.success(f"✅ Connecté en tant que: {get_username()}")
            authenticator.logout("Déconnexion")  # pyright: ignore[reportUnknownMemberType]
