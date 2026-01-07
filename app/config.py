from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # الإعدادات الأساسية
    PROJECT_NAME: str = "Trading Backend"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    
    DEBUG: bool = False
    DISABLE_AUTH: bool = False
    # قاعدة البيانات
    DATABASE_URL: str = "postgresql+asyncpg://neondb_owner:npg_SmQ5UA8CGgOo@ep-dry-moon-a4gvc6kp-pooler.us-east-1.aws.neon.tech/neondb?ssl=require"    
    REDIS_URL: str = "redis://default:AbECAAIncDI0Y2IxM2E0ZThmNGE0MjU2OTI0ZGI5Mzc4MzlmNWYwNXAyNDUzMTQ@tops-jawfish-45314.upstash.io:6379"

    
    # مصادر البيانات
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/ws"
    BINANCE_API_URL: str = "https://api.binance.com"
    ALPACA_API_KEY: Optional[str] = None
    ALPACA_SECRET_KEY: Optional[str] = None
    POLYGON_API_KEY: Optional[str] = None
    
    # إعدادات التطبيق
    DEBUG: bool = False
    CORS_ORIGINS: list = ["http://62.169.17.101:3018"]

    
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # إعدادات البريد الإلكتروني (إن وجد)
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = None
    ALPHA_VANTAGE_API_KEY: str = "7A7EBYAVES69E5Y8"
    
    # إعدادات التشفير
    ENCRYPTION_KEY: str = "your-encryption-key-here-change-in-production"    
    class Config:
        # env_file = ".env"

        env_file = ".env.production"
        case_sensitive = True
        extra = "allow"
        
settings = Settings()