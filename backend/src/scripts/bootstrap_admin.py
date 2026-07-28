import argparse
import asyncio
from getpass import getpass

from sqlalchemy import select

from src.app.services.security import hash_password
from src.database import SessionLocal
from src.database.models import (
    Admin,
    AdminIdentity,
    AdminRole,
    AdminRoleAssignment,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create an independent admin identity and grant its first role"
        ),
    )
    parser.add_argument("email", help="Administrator email")
    parser.add_argument("--name", required=True, help="Administrator first name")
    parser.add_argument("--surname", required=True, help="Administrator surname")
    parser.add_argument("--role", default="superadmin", help="Admin role code")
    return parser.parse_args()


async def bootstrap_admin(
    *,
    email: str,
    password: str,
    name: str,
    surname: str,
    role_code: str,
) -> None:
    normalized_email = email.strip().lower()
    normalized_role = role_code.strip().lower()
    normalized_name = name.strip()
    normalized_surname = surname.strip()
    if len(password) < 8:
        raise RuntimeError("Admin password must contain at least 8 characters")
    if not normalized_name or not normalized_surname:
        raise RuntimeError("Admin name and surname are required")

    async with SessionLocal() as session:
        role = (
            await session.execute(select(AdminRole).where(AdminRole.code == normalized_role))
        ).scalar_one_or_none()
        if role is None:
            raise RuntimeError(f"Admin role not found: {normalized_role}. Run migrations first.")

        identity = (
            await session.execute(
                select(AdminIdentity).where(
                    AdminIdentity.email == normalized_email
                )
            )
        ).scalar_one_or_none()
        if identity is None:
            identity = AdminIdentity(
                email=normalized_email,
                password_hash=hash_password(password),
                name=normalized_name,
                surname=normalized_surname,
                is_active=True,
            )
            session.add(identity)
            await session.flush()
        else:
            identity.is_active = True
            identity.password_hash = hash_password(password)
            identity.name = normalized_name
            identity.surname = normalized_surname

        admin = await session.get(Admin, identity.id)
        if admin is None:
            admin = Admin(user_id=identity.id, is_active=True)
            session.add(admin)
            await session.flush()
        else:
            admin.is_active = True

        assignment = await session.get(
            AdminRoleAssignment,
            {"admin_user_id": identity.id, "role_id": role.id},
        )
        if assignment is None:
            session.add(
                AdminRoleAssignment(
                    admin_user_id=identity.id,
                    role_id=role.id,
                    assigned_by_user_id=identity.id,
                )
            )
        await session.commit()
        print(f"Admin access enabled for {normalized_email} with role {normalized_role}")


async def main() -> None:
    args = parse_args()
    await bootstrap_admin(
        email=args.email,
        password=getpass("New admin password: "),
        name=args.name,
        surname=args.surname,
        role_code=args.role,
    )


if __name__ == "__main__":
    asyncio.run(main())
