# app/models/__init__.py
from app.models.user import User
from app.models.strategy import Strategy  # ✅ أضف هذا

__all__ = ["User", "Strategy"]  # ✅ أضف Strategy إلى __all__