from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_SmQ5UA8CGgOo@ep-dry-moon-a4gvc6kp-pooler.us-east-1.aws.neon.tech/neondb"
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    async with engine.begin() as conn:
        # إنشاء الجداول
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    await engine.dispose()