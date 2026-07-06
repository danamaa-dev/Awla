#!/usr/bin/env python
"""Creates a user account -- the only supported way to add one.

There is no self-registration endpoint and no automatic demo-account
seeding. Run this once after a fresh install to create your first manager
account, and again for any other account you need.

Usage:
    python scripts/create_user.py
"""
import getpass
import os
import sqlite3
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv

load_dotenv(os.path.join(_root, ".env"))

from data.database import create_user, init_db


def main():
    init_db()

    name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()
    department = input("Department: ").strip()

    role = ""
    while role not in ("employee", "manager"):
        role = input("Role (employee/manager): ").strip().lower()

    password = getpass.getpass("Password (min 8 characters): ")
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)
    if password != getpass.getpass("Confirm password: "):
        print("Passwords do not match.")
        sys.exit(1)

    try:
        user_id = create_user(name, email, password, role, department)
    except sqlite3.IntegrityError:
        print(f"A user with email {email} already exists.")
        sys.exit(1)

    print(f"Created {role} account for {email} (id={user_id}).")


if __name__ == "__main__":
    main()
