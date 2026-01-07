#!/usr/bin/env python3
"""Utility script to hash passwords for authentication.

Usage:
    python scripts/hash_password.py [password]

If no password is provided, will prompt for one.
"""

import sys
from getpass import getpass

from src.infra.auth import hash_password


def main() -> None:
    """Hash a password for use in secrets.toml."""
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass("Enter password to hash: ")
        confirm = getpass("Confirm password: ")

        if password != confirm:
            print("❌ Passwords don't match!")
            sys.exit(1)

    hashed = hash_password(password)

    print("\n✅ Hashed password:")
    print(hashed)
    print("\n📝 Add this to .streamlit/secrets.toml:")
    print(f"""
[auth]
admin_username = "admin"
admin_password = "{hashed}"
cookie_key = "change_this_to_a_random_secret"
""")


if __name__ == "__main__":
    main()
