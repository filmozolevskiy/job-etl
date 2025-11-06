#!/usr/bin/env python3
"""
Generate Airflow Fernet key and secret key for environment configuration.

This script generates the required encryption keys for Airflow:
- AIRFLOW__CORE__FERNET_KEY: Used for encrypting sensitive data (variables, connections)
- AIRFLOW__WEBSERVER__SECRET_KEY: Used for session management

Usage:
    python scripts/generate_airflow_keys.py
"""

import secrets
import sys

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("Error: cryptography module not installed.")
    print("Install it with: pip install cryptography")
    sys.exit(1)


def generate_fernet_key():
    """Generate a valid Fernet encryption key."""
    return Fernet.generate_key().decode()


def generate_secret_key():
    """Generate a secure random secret key."""
    return secrets.token_urlsafe(32)


def main():
    """Generate and display the keys."""
    print("=" * 70)
    print("Airflow Key Generator")
    print("=" * 70)
    print()

    fernet_key = generate_fernet_key()
    secret_key = generate_secret_key()

    print("Add these to your .env file:")
    print()
    print(f"AIRFLOW__CORE__FERNET_KEY={fernet_key}")
    print(f"AIRFLOW__WEBSERVER__SECRET_KEY={secret_key}")
    print()
    print("=" * 70)
    print()
    print("Or copy-paste this block:")
    print()
    print("# Airflow Encryption Keys")
    print(f"AIRFLOW__CORE__FERNET_KEY={fernet_key}")
    print(f"AIRFLOW__WEBSERVER__SECRET_KEY={secret_key}")
    print()


if __name__ == "__main__":
    main()

