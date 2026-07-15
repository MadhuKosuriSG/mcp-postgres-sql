from argon2 import PasswordHasher
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User

_password_hasher = PasswordHasher()


async def register(
    session: AsyncSession,
    email: str,
    username: str,
    full_name: str,
    phone_number: str,
    password: str,
) -> User:
    hashed_password = await run_in_threadpool(_password_hasher.hash, password)

    user = User(
        email=email,
        username=username,
        full_name=full_name,
        phone_number=phone_number,
        hashed_password=hashed_password,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
