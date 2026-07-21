import argparse
import asyncio

from sqlalchemy import select

from src.database import SessionLocal
from src.database.models import Admin, AdminRole, AdminRoleAssignment, User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Grant an existing registered user access to the admin panel",
    )
    parser.add_argument("email", help="Email of an existing application user")
    parser.add_argument("--role", default="superadmin", help="Admin role code")
    return parser.parse_args()


async def bootstrap_admin(*, email: str, role_code: str) -> None:
    normalized_email = email.strip().lower()
    normalized_role = role_code.strip().lower()
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == normalized_email))
        ).scalar_one_or_none()
        if user is None:
            raise RuntimeError(f"Registered user not found: {normalized_email}")

        role = (
            await session.execute(select(AdminRole).where(AdminRole.code == normalized_role))
        ).scalar_one_or_none()
        if role is None:
            raise RuntimeError(f"Admin role not found: {normalized_role}. Run migrations first.")

        admin = await session.get(Admin, user.id)
        if admin is None:
            admin = Admin(user_id=user.id, is_active=True)
            session.add(admin)
            await session.flush()
        else:
            admin.is_active = True

        assignment = await session.get(
            AdminRoleAssignment,
            {"admin_user_id": user.id, "role_id": role.id},
        )
        if assignment is None:
            session.add(
                AdminRoleAssignment(
                    admin_user_id=user.id,
                    role_id=role.id,
                    assigned_by_user_id=user.id,
                )
            )
        await session.commit()
        print(f"Admin access enabled for {normalized_email} with role {normalized_role}")


async def main() -> None:
    args = parse_args()
    await bootstrap_admin(email=args.email, role_code=args.role)


if __name__ == "__main__":
    asyncio.run(main())
