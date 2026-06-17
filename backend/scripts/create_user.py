"""
Create or reset a user account.

Examples:
  python scripts/create_user.py --email admin@borek.com --password "LongPassword1" --role admin
  python scripts/create_user.py --email finance@borek.com --password "LongPassword1" --reset-password
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

from sqlalchemy import select

from core.roles import is_valid_role
from db.pool import async_session, engine
from models.user import User
from utils.password_hashing import hash_password


async def _run(email: str, password: str, role: str, reset_password: bool) -> int:
    if len(password) < 12:
        print("Password must be at least 12 characters.", file=sys.stderr)
        return 1
    if not is_valid_role(role):
        print("Role must be finance or admin.", file=sys.stderr)
        return 1

    email = email.lower()
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
                must_change_password=False,
                email_verified_at=datetime.now(timezone.utc),
            )
            session.add(user)
            await session.commit()
            print(f"Created {role} user {email}")
            return 0

        if not reset_password:
            print(f"User {email} already exists. Use --reset-password to update it.")
            return 1

        user.password_hash = hash_password(password)
        user.role = role
        user.is_active = True
        user.must_change_password = False
        user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
        await session.commit()
        print(f"Updated password for {email} (role={role})")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or reset a Borek Finance user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", default="admin", choices=["finance", "admin"])
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Update password when the user already exists",
    )
    args = parser.parse_args()

    async def _main() -> int:
        try:
            return await _run(args.email, args.password, args.role, args.reset_password)
        finally:
            await engine.dispose()

    return asyncio.run(_main())


if __name__ == "__main__":
    raise SystemExit(main())
