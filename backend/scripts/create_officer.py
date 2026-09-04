"""CLI: create an officer with a hashed password.

Usage (inside the backend container):
    python scripts/create_officer.py --name "Priya Sharma" \
        --email priya@example.gov.in --password secret123 --role inspector
"""
import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session


from app.auth import hash_password
from app.db.models import Officer, OfficerRole
from app.database import engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an officer account")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", choices=["admin", "inspector", "viewer"], default="inspector")
    args = parser.parse_args()

    role = OfficerRole(args.role.upper())

    with Session(engine) as session:
        existing = session.query(Officer).filter_by(email=args.email).first()
        if existing:
            print(f"error: officer with email {args.email} already exists")
            sys.exit(1)

        officer = Officer(
            id=uuid.uuid4(),
            name=args.name,
            email=args.email,
            password_hash=hash_password(args.password),
            role=role,
        )
        session.add(officer)
        session.commit()
        print(f"created officer: {args.email} (role={args.role}, id={officer.id})")


if __name__ == "__main__":
    main()
