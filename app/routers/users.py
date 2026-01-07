from datetime import datetime, timedelta
from typing import List, Optional

from jwt import PyJWTError

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate, UserResponse, UserUpdate, 
    Token, UserInDB
)
from app.services.auth import AuthService
from app.utils.security import SecurityUtils

router = APIRouter(tags=["users"])

def send_welcome_email(email: str, username: str):
    """إرسال بريد ترحيبي (محاكاة)"""
    # في التطبيق الحقيقي، استخدم خدمة بريد إلكتروني
    print(f"Sending welcome email to {email} for user {username}")

@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """تسجيل مستخدم جديد"""
    try:
        # التحقق من وجود المستخدم
        existing_user = db.query(User).filter(
            (User.email == user_data.email) | (User.username == user_data.username)
        ).first()
        
        if existing_user:
            if existing_user.email == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        # إنشاء المستخدم
        hashed_password = AuthService.get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            is_active=True,
            is_verified=False,
            created_at=datetime.utcnow()
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # إرسال بريد ترحيبي في الخلفية
        background_tasks.add_task(
            send_welcome_email, 
            db_user.email, 
            db_user.username
        )
        
        return db_user
        
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )

# @router.post("/login", response_model=Token)
# async def login_user(
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     db: Session = Depends(get_db)
# ):
#     """تسجيل دخول المستخدم"""
#     try:
#         user = AuthService.authenticate_user(
#             db, form_data.username, form_data.password
#         )
        
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Incorrect username or password",
#                 headers={"WWW-Authenticate": "Bearer"},
#             )
        
#         # تحديث وقت آخر دخول
#         user.last_login = datetime.utcnow()
#         db.commit()
        
#         # إنشاء التوكنات
#         access_token_expires = timedelta(minutes=30)
#         access_token = AuthService.create_access_token(
#             data={"sub": user.username, "user_id": user.id},
#             expires_delta=access_token_expires
#         )
        
#         refresh_token = AuthService.create_refresh_token(
#             data={"sub": user.username, "user_id": user.id}
#         )
        
#         return {
#             "access_token": access_token,
#             "token_type": "bearer",
#             "expires_in": int(access_token_expires.total_seconds()),
#             "refresh_token": refresh_token
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Login error: {str(e)}"
#         )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """تحديث توكن الوصول"""
    try:
        payload = AuthService.verify_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        username = payload.get("sub")
        user_id = payload.get("user_id")
        
        if not username or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token data"
            )
        
        # التحقق من وجود المستخدم
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # إنشاء توكن وصول جديد
        access_token_expires = timedelta(minutes=30)
        access_token = AuthService.create_access_token(
            data={"sub": user.username, "user_id": user.id},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": int(access_token_expires.total_seconds()),
            "refresh_token": refresh_token  # نفس التوكن للتحديث
        }
        
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh error: {str(e)}"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(AuthService.get_current_active_user)
):
    """الحصول على معلومات المستخدم الحالي"""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(AuthService.get_current_active_user),
    db: Session = Depends(get_db)
):
    """تحديث معلومات المستخدم الحالي"""
    try:
        update_data = user_data.dict(exclude_unset=True)
        
        # التحقق من تفرد البريد الإلكتروني
        if 'email' in update_data and update_data['email'] != current_user.email:
            existing_user = db.query(User).filter(
                User.email == update_data['email']
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # التحقق من تفرد اسم المستخدم
        if 'username' in update_data and update_data['username'] != current_user.username:
            existing_user = db.query(User).filter(
                User.username == update_data['username']
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        # تحديث البيانات
        for field, value in update_data.items():
            setattr(current_user, field, value)
        
        current_user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(current_user)
        
        return current_user
        
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )

@router.post("/me/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(AuthService.get_current_active_user),
    db: Session = Depends(get_db)
):
    """تغيير كلمة مرور المستخدم"""
    try:
        # التحقق من كلمة المرور القديمة
        if not AuthService.verify_password(old_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Old password is incorrect"
            )
        
        # التحقق من كلمة المرور الجديدة
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters"
            )
        
        # تحديث كلمة المرور
        current_user.hashed_password = AuthService.get_password_hash(new_password)
        current_user.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Password changed successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error changing password: {str(e)}"
        )

@router.delete("/me")
async def delete_account(
    current_user: User = Depends(AuthService.get_current_active_user),
    db: Session = Depends(get_db)
):
    """حذف حساب المستخدم"""
    try:
        # في التطبيق الحقيقي، قد نريد تعطيل الحساب بدلاً من الحذف
        db.delete(current_user)
        db.commit()
        
        return {"message": "Account deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting account: {str(e)}"
        )

@router.get("/verify-email/{token}")
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """التحقق من البريد الإلكتروني"""
    try:
        payload = AuthService.verify_token(token)
        if not payload or payload.get("type") != "email_verification":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token"
            )
        
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token data"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.is_verified:
            return {"message": "Email already verified"}
        
        user.is_verified = True
        user.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Email verified successfully"}
        
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying email: {str(e)}"
        )

@router.post("/request-password-reset")
async def request_password_reset(
    email: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """طلب إعادة تعيين كلمة المرور"""
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            # لأسباب أمنية، لا نكشف إذا كان البريد مسجلاً أم لا
            return {"message": "If your email is registered, you will receive a reset link"}
        
        # إنشاء توكن إعادة تعيين
        reset_token = AuthService.create_access_token(
            data={
                "sub": user.username,
                "user_id": user.id,
                "type": "password_reset"
            },
            expires_delta=timedelta(hours=24)
        )
        
        # في التطبيق الحقيقي، أرسل البريد الإلكتروني
        reset_link = f"https://yourdomain.com/reset-password?token={reset_token}"
        
        def send_reset_email():
            # محاكاة إرسال البريد
            print(f"Password reset link for {email}: {reset_link}")
        
        background_tasks.add_task(send_reset_email)
        
        return {"message": "Password reset link sent to email"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error requesting password reset: {str(e)}"
        )

@router.post("/reset-password")
async def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    """إعادة تعيين كلمة المرور"""
    try:
        payload = AuthService.verify_token(token)
        if not payload or payload.get("type") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )
        
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token data"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters"
            )
        
        user.hashed_password = AuthService.get_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Password reset successfully"}
        
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resetting password: {str(e)}"
        )

# مسارات الإدارة (للمستخدمين المميزين فقط)
@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(AuthService.get_current_superuser),
    db: Session = Depends(get_db)
):
    """الحصول على جميع المستخدمين (للمسؤولين فقط)"""
    try:
        users = db.query(User).offset(skip).limit(limit).all()
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching users: {str(e)}"
        )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(AuthService.get_current_superuser),
    db: Session = Depends(get_db)
):
    """الحصول على مستخدم بواسطة المعرف (للمسؤولين فقط)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user: {str(e)}"
        )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user_by_id(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(AuthService.get_current_superuser),
    db: Session = Depends(get_db)
):
    """تحديث مستخدم بواسطة المعرف (للمسؤولين فقط)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        update_data = user_data.dict(exclude_unset=True)
        
        # تحديث البيانات
        for field, value in update_data.items():
            setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        return user
        
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )

@router.delete("/{user_id}")
async def delete_user_by_id(
    user_id: int,
    current_user: User = Depends(AuthService.get_current_superuser),
    db: Session = Depends(get_db)
):
    """حذف مستخدم بواسطة المعرف (للمسؤولين فقط)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # لا يمكن حذف المستخدم نفسه
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        db.delete(user)
        db.commit()
        
        return {"message": "User deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user: {str(e)}"
        )