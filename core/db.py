from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

import config


def build_async_database_uri(database_uri: str) -> str:
    return database_uri.replace("postgresql://", "postgresql+asyncpg://", 1)


engine: AsyncEngine = create_async_engine(
    build_async_database_uri(config.DATABASE_URI), pool_pre_ping=True
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()
