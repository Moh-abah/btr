# app/database/__init__.py
from .session import Base, engine, get_db, init_db, close_db
from app.models import user  # استيراد جميع النماذج
from app.models.strategy import Strategy 
async def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول"""
    async with engine.begin() as conn:
        
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    """إغلاق محرك قاعدة البيانات"""
    await engine.dispose()
