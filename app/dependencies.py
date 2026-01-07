from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth import AuthService

# اعتمادات المستخدم
def get_current_user(db: Session = Depends(get_db)):
    """الحصول على المستخدم الحالي"""
    return AuthService.get_current_user(db)

def get_current_active_user(current_user = Depends(get_current_user)):
    """الحصول على المستخدم النشط الحالي"""
    return AuthService.get_current_active_user(current_user)

def get_current_superuser(current_user = Depends(get_current_user)):
    """الحصول على المستخدم المميز الحالي"""
    return AuthService.get_current_superuser(current_user)

# اعتمادات الإعدادات
def get_user_settings(current_user = Depends(get_current_active_user)):
    """الحصول على إعدادات المستخدم"""
    # يمكن إضافة منطق إضافي هنا
    return current_user

# اعتمادات المحفظة
def get_user_portfolio(portfolio_id: int, current_user = Depends(get_current_active_user)):
    """الحصول على محفظة محددة للمستخدم"""
    # يمكن إضافة منطق إضافي هنا
    return {"portfolio_id": portfolio_id, "user": current_user}