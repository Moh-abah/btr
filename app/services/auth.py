from datetime import datetime, timedelta
import functools
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenData

# إعدادات JWT
SECRET_KEY = "your-secret-key-here"  # يجب تغيير هذا في الإنتاج
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")

class AuthService:
    """خدمة المصادقة وإدارة المستخدمين"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """التحقق من كلمة المرور"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """تجزئة كلمة المرور"""
        return pwd_context.hash(password)
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """مصادقة المستخدم"""
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return None
            if not AuthService.verify_password(password, user.hashed_password):
                return None
            return user
        except SQLAlchemyError:
            return None
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """إنشاء توكن وصول"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt


    def bypass_auth_in_dev(func):
        """
        Decorator لتجاوز المصادقة في بيئة التطوير
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # إذا كانت المصادقة معطلة، اجتازها
            if settings.DEBUG and settings.DISABLE_AUTH:
                # إنشاء مستخدم وهمي
                class MockUser:
                    def __init__(self):
                        self.id = 1
                        self.email = "dev@example.com"
                        self.username = "devuser"
                        self.full_name = "Development User"
                        self.is_active = True
                        self.is_verified = True
                
                # استبدل current_user بالمستخدم الوهمي
                if 'current_user' in kwargs:
                    kwargs['current_user'] = MockUser()
                elif len(args) > 1:
                    # إذا كان current_user في args
                    args = list(args)
                    if len(args) > 1:
                        args[1] = MockUser()
                    args = tuple(args)
            
            return await func(*args, **kwargs)
        
        return wrapper


    @staticmethod
    def get_current_user_or_bypass(
        db: Session = Depends(get_db),
        token: Optional[str] = Depends(oauth2_scheme)
    ) -> User:
        """
        دالة مصادقة تسمح بتجاوز المصادقة في بيئة التطوير
        """
        # إذا كانت بيئة التطوير وتعطيل المصادقة مفعل
        if settings.DEBUG and settings.DISABLE_AUTH:
            # إرجاع مستخدم افتراضي للتطوير
            user = db.query(User).filter(User.email == "dev@example.com").first()
            if not user:
                # إنشاء مستخدم تطوير إذا لم يوجد
                user = User(
                    email="dev@example.com",
                    username="devuser",
                    full_name="Development User",
                    is_active=True,
                    is_verified=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            return user
        
        # وإلا استخدم المصادقة العادية
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # التحقق من التوكن
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except JWTError:
            raise credentials_exception
        
        user = db.query(User).filter(User.username == token_data.username).first()
        if user is None:
            raise credentials_exception
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        return user
    
    @staticmethod
    def get_current_active_user_or_bypass(
        current_user: User = Depends(get_current_user_or_bypass)
    ) -> User:
        """التحقق من أن المستخدم نشط (بدون مصادقة في التطوير)"""
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        return current_user

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """إنشاء توكن تحديث"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """التحقق من صحة التوكن"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
    
    @staticmethod
    def get_current_user(
        db: Session = Depends(get_db),
        token: str = Depends(oauth2_scheme)
    ) -> User:
        



        if settings.DEBUG and settings.DISABLE_AUTH:
            # إرجاع مستخدم افتراضي للتطوير
            user = db.query(User).filter(User.email == "dev@example.com").first()
            if not user:
                # إنشاء مستخدم تطوير إذا لم يوجد
                user = User(
                    email="dev@example.com",
                    username="devuser",
                    full_name="Development User",
                    is_active=True,
                    is_verified=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            return user





        """الحصول على المستخدم الحالي من التوكن"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        payload = AuthService.verify_token(token)
        if payload is None:
            raise credentials_exception
        
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        token_data = TokenData(username=username)
        
        user = db.query(User).filter(User.username == token_data.username).first()
        if user is None:
            raise credentials_exception
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        return user



    @staticmethod
    def get_current_user_or_dev(
        db: Session = Depends(get_db),
        token:  Optional[str] = Depends(oauth2_scheme)
    ) -> User:
        """
        دالة تجمع بين المصادقة العادية وتجاوزها في التطوير
        """
        # إذا كانت بيئة التطوير وتعطيل المصادقة مفعل
        if settings.DEBUG and settings.DISABLE_AUTH:
            # إرجاع مستخدم افتراضي للتطوير
            user = db.query(User).filter(User.email == "dev@example.com").first()
            if not user:
                # إنشاء مستخدم تطوير إذا لم يوجد
                user = User(
                    email="dev@example.com",
                    username="devuser",
                    full_name="Development User",
                    is_active=True,
                    is_verified=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            return user
        
        # وإلا استخدم المصادقة العادية
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        if not token:
            raise credentials_exception
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except JWTError:
            raise credentials_exception
        
        user = db.query(User).filter(User.username == token_data.username).first()
        if user is None:
            raise credentials_exception
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        return user






    @staticmethod
    def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
        """التحقق من أن المستخدم نشط"""
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user
    
    @staticmethod
    def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
        """التحقق من أن المستخدم مدير"""
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user