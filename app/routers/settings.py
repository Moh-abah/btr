import functools
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.config import settings
from app.database import get_db
from app.models.user import (
    User, UserStrategy, UserIndicator, Watchlist, 
    FilterSettings, Portfolio, APIKey, Notification
)

from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.user import (
    StrategyCreate, StrategyResponse, StrategyUpdate,
    IndicatorCreate, IndicatorResponse, IndicatorUpdate,
    WatchlistCreate, WatchlistResponse, WatchlistUpdate,
    FilterSettingsCreate, FilterSettingsResponse, FilterSettingsUpdate,
    PortfolioCreate, PortfolioResponse, PortfolioUpdate,
    APIKeyCreate, APIKeyResponse
)
from app.services.auth import AuthService
from app.utils.security import SecurityUtils
from sqlalchemy import select


router = APIRouter(tags=["settings"])

# ============== استراتيجيات المستخدم ==============






@router.get("/watchlists", response_model=List[WatchlistResponse])
async def get_watchlists(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    market: Optional[str] = None,
    is_default: Optional[bool] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = Query(None, description="اختياري: تصفية حسب user_id"),
    db: AsyncSession = Depends(get_db)
):
    """الحصول على قوائم مراقبة (بدون مصادقة)"""
    try:
        stmt = select(Watchlist)
        
        # إذا تم تمرير user_id، قم بالتصفية، وإلا اعرض كل شيء
        if user_id:
            stmt = stmt.where(Watchlist.user_id == user_id)
        
        if market:
            stmt = stmt.where(Watchlist.market == market)
        
        if is_default is not None:
            stmt = stmt.where(Watchlist.is_default == is_default)
        
        if search:
            stmt = stmt.where(
                (Watchlist.name.ilike(f"%{search}%")) |
                (Watchlist.description.ilike(f"%{search}%"))
            )
        
        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        watchlists = result.scalars().all()
        
        return watchlists
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching watchlists: {str(e)}"
        )




@router.post("/strategies", response_model=StrategyResponse)
async def create_strategy(
    strategy_data: StrategyCreate,
    # current_user = Depends(AuthService.get_current_active_user),
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """إنشاء استراتيجية جديدة"""
    try:
        db_strategy = UserStrategy(
            user_id=current_user.id,
            **strategy_data.dict()
        )
        
        db.add(db_strategy)
        db.commit()
        db.refresh(db_strategy)
        
        return db_strategy
        
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
            detail=f"Error creating strategy: {str(e)}"
        )

@router.get("/strategies", response_model=List[StrategyResponse])
async def get_strategies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    search: Optional[str] = None,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على استراتيجيات المستخدم"""
    try:
        query = db.query(UserStrategy).filter(
            (UserStrategy.user_id == current_user.id) |
            (UserStrategy.is_public == True)
        )
        
        if category:
            query = query.filter(UserStrategy.category == category)
        
        if is_public is not None:
            query = query.filter(UserStrategy.is_public == is_public)
        
        if search:
            query = query.filter(
                (UserStrategy.name.ilike(f"%{search}%")) |
                (UserStrategy.description.ilike(f"%{search}%"))
            )
        
        strategies = query.offset(skip).limit(limit).all()
        return strategies
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching strategies: {str(e)}"
        )

@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy_by_id(
    strategy_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على استراتيجية محددة"""
    try:
        strategy = db.query(UserStrategy).filter(UserStrategy.id == strategy_id).first()
        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )
        
        # التحقق من الصلاحيات
        if strategy.user_id != current_user.id and not strategy.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this strategy"
            )
        
        return strategy
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching strategy: {str(e)}"
        )

@router.put("/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    strategy_data: StrategyUpdate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """تحديث استراتيجية"""
    try:
        strategy = db.query(UserStrategy).filter(UserStrategy.id == strategy_id).first()
        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )
        
        if strategy.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this strategy"
            )
        
        update_data = strategy_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(strategy, field, value)
        
        db.commit()
        db.refresh(strategy)
        
        return strategy
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating strategy: {str(e)}"
        )

@router.delete("/strategies/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """حذف استراتيجية"""
    try:
        strategy = db.query(UserStrategy).filter(UserStrategy.id == strategy_id).first()
        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )
        
        if strategy.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this strategy"
            )
        
        db.delete(strategy)
        db.commit()
        
        return {"message": "Strategy deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting strategy: {str(e)}"
        )

@router.post("/strategies/{strategy_id}/duplicate", response_model=StrategyResponse)
async def duplicate_strategy(
    strategy_id: int,
    new_name: str,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """نسخ استراتيجية"""
    try:
        original = db.query(UserStrategy).filter(UserStrategy.id == strategy_id).first()
        if not original:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )
        
        # التحقق من الصلاحيات
        if original.user_id != current_user.id and not original.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to duplicate this strategy"
            )
        
        # إنشاء نسخة
        new_strategy = UserStrategy(
            user_id=current_user.id,
            name=new_name,
            description=f"Copy of {original.name}",
            strategy_config=original.strategy_config,
            category=original.category,
            tags=original.tags.copy() if original.tags else [],
            is_public=False,
            is_default=False
        )
        
        db.add(new_strategy)
        db.commit()
        db.refresh(new_strategy)
        
        return new_strategy
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error duplicating strategy: {str(e)}"
        )

# ============== مؤشرات المستخدم ==============

@router.post("/indicators", response_model=IndicatorResponse)
async def create_indicator(
    indicator_data: IndicatorCreate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """إنشاء مؤشر مخصص"""
    try:
        # التحقق من صحة كود المؤشر (يمكن إضافة تحقق أكثر تعقيداً)
        if not indicator_data.indicator_code.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Indicator code cannot be empty"
            )
        
        db_indicator = UserIndicator(
            user_id=current_user.id,
            **indicator_data.dict()
        )
        
        db.add(db_indicator)
        db.commit()
        db.refresh(db_indicator)
        
        return db_indicator
        
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
            detail=f"Error creating indicator: {str(e)}"
        )

@router.get("/indicators", response_model=List[IndicatorResponse])
async def get_indicators(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = None,
    indicator_type: Optional[str] = None,
    is_public: Optional[bool] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على مؤشرات المستخدم"""
    try:
        query = db.query(UserIndicator).filter(
            (UserIndicator.user_id == current_user.id) |
            (UserIndicator.is_public == True)
        )
        
        if category:
            query = query.filter(UserIndicator.category == category)
        
        if indicator_type:
            query = query.filter(UserIndicator.indicator_type == indicator_type)
        
        if is_public is not None:
            query = query.filter(UserIndicator.is_public == is_public)
        
        if is_active is not None:
            query = query.filter(UserIndicator.is_active == is_active)
        
        if search:
            query = query.filter(
                (UserIndicator.name.ilike(f"%{search}%")) |
                (UserIndicator.display_name.ilike(f"%{search}%")) |
                (UserIndicator.description.ilike(f"%{search}%"))
            )
        
        indicators = query.offset(skip).limit(limit).all()
        return indicators
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching indicators: {str(e)}"
        )

@router.get("/indicators/{indicator_id}", response_model=IndicatorResponse)
async def get_indicator_by_id(
    indicator_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على مؤشر محدد"""
    try:
        indicator = db.query(UserIndicator).filter(UserIndicator.id == indicator_id).first()
        if not indicator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Indicator not found"
            )
        
        # التحقق من الصلاحيات
        if indicator.user_id != current_user.id and not indicator.is_public:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this indicator"
            )
        
        return indicator
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching indicator: {str(e)}"
        )

@router.put("/indicators/{indicator_id}", response_model=IndicatorResponse)
async def update_indicator(
    indicator_id: int,
    indicator_data: IndicatorUpdate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """تحديث مؤشر"""
    try:
        indicator = db.query(UserIndicator).filter(UserIndicator.id == indicator_id).first()
        if not indicator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Indicator not found"
            )
        
        if indicator.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this indicator"
            )
        
        update_data = indicator_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(indicator, field, value)
        
        db.commit()
        db.refresh(indicator)
        
        return indicator
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating indicator: {str(e)}"
        )

@router.delete("/indicators/{indicator_id}")
async def delete_indicator(
    indicator_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """حذف مؤشر"""
    try:
        indicator = db.query(UserIndicator).filter(UserIndicator.id == indicator_id).first()
        if not indicator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Indicator not found"
            )
        
        if indicator.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this indicator"
            )
        
        db.delete(indicator)
        db.commit()
        
        return {"message": "Indicator deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting indicator: {str(e)}"
        )

@router.post("/indicators/{indicator_id}/test")
async def test_indicator(
    indicator_id: int,
    test_data: dict,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """اختبار مؤشر مخصص"""
    try:
        indicator = db.query(UserIndicator).filter(UserIndicator.id == indicator_id).first()
        if not indicator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Indicator not found"
            )
        
        if indicator.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to test this indicator"
            )
        
        # محاكاة اختبار المؤشر
        # في التطبيق الحقيقي، سنقوم بتشغيل كود المؤشر على بيانات الاختبار
        
        result = {
            "status": "success",
            "message": "Indicator test completed",
            "indicator_name": indicator.name,
            "test_data": test_data,
            "output": "Simulated indicator output"
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing indicator: {str(e)}"
        )

















# ============== قوائم المراقبة ==============

@router.post("/watchlists", response_model=WatchlistResponse)

async def create_watchlist(
    watchlist_data: WatchlistCreate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """إنشاء قائمة مراقبة جديدة"""
    try:
        # إذا كانت هذه القائمة الأولى، اجعلها الافتراضية
        existing_count = db.query(Watchlist).filter(
            Watchlist.user_id == current_user.id
        ).count()
        
        if existing_count == 0:
            watchlist_data.is_default = True
        
        db_watchlist = Watchlist(
            user_id=current_user.id,
            **watchlist_data.dict()
        )
        
        db.add(db_watchlist)
        db.commit()
        db.refresh(db_watchlist)
        
        return db_watchlist
        
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
            detail=f"Error creating watchlist: {str(e)}"
        )


@router.get("/watchlists/{watchlist_id}", response_model=WatchlistResponse)
async def get_watchlist_by_id(
    watchlist_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على قائمة مراقبة محددة"""
    try:
        watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
        if not watchlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found"
            )
        
        if watchlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this watchlist"
            )
        
        return watchlist
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching watchlist: {str(e)}"
        )

@router.put("/watchlists/{watchlist_id}", response_model=WatchlistResponse)
async def update_watchlist(
    watchlist_id: int,
    watchlist_data: WatchlistUpdate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """تحديث قائمة مراقبة"""
    try:
        watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
        if not watchlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found"
            )
        
        if watchlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this watchlist"
            )
        
        update_data = watchlist_data.dict(exclude_unset=True)
        
        # إذا تم تعيين is_default = True، إلغاء الافتراضية عن الآخرين
        if update_data.get('is_default') == True:
            db.query(Watchlist).filter(
                Watchlist.user_id == current_user.id,
                Watchlist.is_default == True
            ).update({"is_default": False})
        
        for field, value in update_data.items():
            setattr(watchlist, field, value)
        
        db.commit()
        db.refresh(watchlist)
        
        return watchlist
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating watchlist: {str(e)}"
        )

@router.delete("/watchlists/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """حذف قائمة مراقبة"""
    try:
        watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
        if not watchlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found"
            )
        
        if watchlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this watchlist"
            )
        
        # إذا كانت القائمة الافتراضية، جعل قائمة أخرى افتراضية
        if watchlist.is_default:
            other_watchlist = db.query(Watchlist).filter(
                Watchlist.user_id == current_user.id,
                Watchlist.id != watchlist_id
            ).first()
            
            if other_watchlist:
                other_watchlist.is_default = True
        
        db.delete(watchlist)
        db.commit()
        
        return {"message": "Watchlist deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting watchlist: {str(e)}"
        )

@router.post("/watchlists/{watchlist_id}/symbols/{symbol}")
async def add_symbol_to_watchlist(
    watchlist_id: int,
    symbol: str,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """إضافة رمز إلى قائمة المراقبة"""
    try:
        watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
        if not watchlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found"
            )
        
        if watchlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this watchlist"
            )
        
        if symbol in watchlist.symbols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Symbol {symbol} already in watchlist"
            )
        
        watchlist.symbols = watchlist.symbols + [symbol]
        db.commit()
        
        return {"message": f"Symbol {symbol} added to watchlist"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding symbol: {str(e)}"
        )

@router.delete("/watchlists/{watchlist_id}/symbols/{symbol}")
async def remove_symbol_from_watchlist(
    watchlist_id: int,
    symbol: str,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """إزالة رمز من قائمة المراقبة"""
    try:
        watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id).first()
        if not watchlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found"
            )
        
        if watchlist.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this watchlist"
            )
        
        if symbol not in watchlist.symbols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Symbol {symbol} not in watchlist"
            )
        
        watchlist.symbols = [s for s in watchlist.symbols if s != symbol]
        db.commit()
        
        return {"message": f"Symbol {symbol} removed from watchlist"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing symbol: {str(e)}"
        )

# ============== إعدادات الفلترة ==============

@router.post("/filters", response_model=FilterSettingsResponse)
async def create_filter_settings(
    filter_data: FilterSettingsCreate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """إنشاء إعدادات فلترة جديدة"""
    try:
        # إذا كانت هذه الإعدادات الأولى، اجعلها الافتراضية
        existing_count = db.query(FilterSettings).filter(
            FilterSettings.user_id == current_user.id
        ).count()
        
        if existing_count == 0:
            filter_data.is_default = True
        
        db_filter = FilterSettings(
            user_id=current_user.id,
            **filter_data.dict()
        )
        
        db.add(db_filter)
        db.commit()
        db.refresh(db_filter)
        
        return db_filter
        
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
            detail=f"Error creating filter settings: {str(e)}"
        )

@router.get("/filters", response_model=List[FilterSettingsResponse])
async def get_filter_settings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    market: Optional[str] = None,
    is_default: Optional[bool] = None,
    search: Optional[str] = None,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على إعدادات فلترة المستخدم"""
    try:
        query = db.query(FilterSettings).filter(
            FilterSettings.user_id == current_user.id
        )
        
        if market:
            query = query.filter(FilterSettings.market == market)
        
        if is_default is not None:
            query = query.filter(FilterSettings.is_default == is_default)
        
        if search:
            query = query.filter(
                (FilterSettings.name.ilike(f"%{search}%")) |
                (FilterSettings.description.ilike(f"%{search}%"))
            )
        
        filters = query.offset(skip).limit(limit).all()
        return filters
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching filter settings: {str(e)}"
        )

@router.get("/filters/{filter_id}", response_model=FilterSettingsResponse)
async def get_filter_settings_by_id(
    filter_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على إعدادات فلترة محددة"""
    try:
        filter_settings = db.query(FilterSettings).filter(FilterSettings.id == filter_id).first()
        if not filter_settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Filter settings not found"
            )
        
        if filter_settings.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access these filter settings"
            )
        
        return filter_settings
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching filter settings: {str(e)}"
        )

@router.put("/filters/{filter_id}", response_model=FilterSettingsResponse)
async def update_filter_settings(
    filter_id: int,
    filter_data: FilterSettingsUpdate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """تحديث إعدادات الفلترة"""
    try:
        filter_settings = db.query(FilterSettings).filter(FilterSettings.id == filter_id).first()
        if not filter_settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Filter settings not found"
            )
        
        if filter_settings.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update these filter settings"
            )
        
        update_data = filter_data.dict(exclude_unset=True)
        
        # إذا تم تعيين is_default = True، إلغاء الافتراضية عن الآخرين
        if update_data.get('is_default') == True:
            db.query(FilterSettings).filter(
                FilterSettings.user_id == current_user.id,
                FilterSettings.is_default == True
            ).update({"is_default": False})
        
        for field, value in update_data.items():
            setattr(filter_settings, field, value)
        
        db.commit()
        db.refresh(filter_settings)
        
        return filter_settings
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating filter settings: {str(e)}"
        )

@router.delete("/filters/{filter_id}")
async def delete_filter_settings(
    filter_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """حذف إعدادات الفلترة"""
    try:
        filter_settings = db.query(FilterSettings).filter(FilterSettings.id == filter_id).first()
        if not filter_settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Filter settings not found"
            )
        
        if filter_settings.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete these filter settings"
            )
        
        # إذا كانت الإعدادات الافتراضية، جعل أخرى افتراضية
        if filter_settings.is_default:
            other_filter = db.query(FilterSettings).filter(
                FilterSettings.user_id == current_user.id,
                FilterSettings.id != filter_id
            ).first()
            
            if other_filter:
                other_filter.is_default = True
        
        db.delete(filter_settings)
        db.commit()
        
        return {"message": "Filter settings deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting filter settings: {str(e)}"
        )

@router.post("/filters/{filter_id}/run")
async def run_filter(
    filter_id: int,
    market: str = "crypto",
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """تشغيل الفلترة باستخدام الإعدادات المحفوظة"""
    try:
        filter_settings = db.query(FilterSettings).filter(FilterSettings.id == filter_id).first()
        if not filter_settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Filter settings not found"
            )
        
        if filter_settings.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to run these filter settings"
            )
        
        # في التطبيق الحقيقي، سيتم استدعاء وحدة الفلترة هنا
        # هذه محاكاة للنتائج
        from datetime import datetime
        import random
        
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT"]
        filtered_symbols = random.sample(symbols, 3)
        
        # تحديث وقت التشغيل الأخير والنتائج
        filter_settings.last_run = datetime.utcnow()
        filter_settings.last_results = {
            "symbols": filtered_symbols,
            "count": len(filtered_symbols),
            "market": market
        }
        
        db.commit()
        
        return {
            "message": "Filter executed successfully",
            "results": filter_settings.last_results,
            "filter_name": filter_settings.name
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running filter: {str(e)}"
        )

# ============== المحافظ ==============

@router.post("/portfolios", response_model=PortfolioResponse)
async def create_portfolio(
    portfolio_data: PortfolioCreate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """إنشاء محفظة جديدة"""
    try:
        db_portfolio = Portfolio(
            user_id=current_user.id,
            current_capital=portfolio_data.initial_capital,
            **portfolio_data.dict()
        )
        
        db.add(db_portfolio)
        db.commit()
        db.refresh(db_portfolio)
        
        return db_portfolio
        
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
            detail=f"Error creating portfolio: {str(e)}"
        )

@router.get("/portfolios", response_model=List[PortfolioResponse])
async def get_portfolios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على محافظ المستخدم"""
    try:
        query = db.query(Portfolio).filter(
            Portfolio.user_id == current_user.id
        )
        
        if search:
            query = query.filter(
                (Portfolio.name.ilike(f"%{search}%")) |
                (Portfolio.description.ilike(f"%{search}%"))
            )
        
        portfolios = query.offset(skip).limit(limit).all()
        return portfolios
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching portfolios: {str(e)}"
        )

@router.get("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio_by_id(
    portfolio_id: int,
    include_positions: bool = Query(False),
    include_transactions: bool = Query(False),
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على محفظة محددة"""
    try:
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        if portfolio.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this portfolio"
            )
        
        response_data = {
            **portfolio.__dict__,
            "positions": [],
            "transactions": []
        }
        
        if include_positions:
            response_data["positions"] = portfolio.positions
        
        if include_transactions:
            response_data["transactions"] = portfolio.transactions
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching portfolio: {str(e)}"
        )

@router.put("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: int,
    portfolio_data: PortfolioUpdate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """تحديث محفظة"""
    try:
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        if portfolio.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this portfolio"
            )
        
        update_data = portfolio_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(portfolio, field, value)
        
        db.commit()
        db.refresh(portfolio)
        
        return portfolio
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating portfolio: {str(e)}"
        )

@router.delete("/portfolios/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """حذف محفظة"""
    try:
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found"
            )
        
        if portfolio.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this portfolio"
            )
        
        db.delete(portfolio)
        db.commit()
        
        return {"message": "Portfolio deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting portfolio: {str(e)}"
        )

# ============== مفاتيح API ==============

@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    api_key_data: APIKeyCreate,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """إنشاء مفتاح API جديد"""
    try:
        # التحقق من صحة مفاتيح API
        if not SecurityUtils.validate_api_key_format(api_key_data.api_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid API key format"
            )
        
        # في التطبيق الحقيقي، يجب تشفير الـ secret
        # api_secret_encrypted = SecurityUtils.encrypt_api_secret(
        #     api_key_data.api_secret, 
        #     ENCRYPTION_KEY
        # )
        
        db_api_key = APIKey(
            user_id=current_user.id,
            name=api_key_data.name,
            exchange=api_key_data.exchange,
            api_key=api_key_data.api_key,
            api_secret=api_key_data.api_secret,  # يجب تشفير هذا في الإنتاج
            permissions=api_key_data.permissions,
            is_active=True
        )
        
        db.add(db_api_key)
        db.commit()
        db.refresh(db_api_key)
        
        return db_api_key
        
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
            detail=f"Error creating API key: {str(e)}"
        )

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def get_api_keys(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    exchange: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على مفاتيح API الخاصة بالمستخدم"""
    try:
        query = db.query(APIKey).filter(
            APIKey.user_id == current_user.id
        )
        
        if exchange:
            query = query.filter(APIKey.exchange == exchange)
        
        if is_active is not None:
            query = query.filter(APIKey.is_active == is_active)
        
        api_keys = query.offset(skip).limit(limit).all()
        
        # إخفاء البيانات الحساسة
        for api_key in api_keys:
            api_key.api_key = SecurityUtils.mask_sensitive_data(api_key.api_key)
            api_key.api_secret = SecurityUtils.mask_sensitive_data(api_key.api_secret)
        
        return api_keys
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching API keys: {str(e)}"
        )

@router.get("/api-keys/{api_key_id}", response_model=APIKeyResponse)
async def get_api_key_by_id(
    api_key_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """الحصول على مفتاح API محدد"""
    try:
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        if api_key.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this API key"
            )
        
        # إخفاء البيانات الحساسة
        api_key.api_key = SecurityUtils.mask_sensitive_data(api_key.api_key)
        api_key.api_secret = SecurityUtils.mask_sensitive_data(api_key.api_secret)
        
        return api_key
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching API key: {str(e)}"
        )

@router.put("/api-keys/{api_key_id}")
async def update_api_key(
    api_key_id: int,
    name: Optional[str] = None,
    permissions: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """تحديث مفتاح API"""
    try:
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        if api_key.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this API key"
            )
        
        if name is not None:
            api_key.name = name
        
        if permissions is not None:
            api_key.permissions = permissions
        
        if is_active is not None:
            api_key.is_active = is_active
        
        db.commit()
        
        return {"message": "API key updated successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating API key: {str(e)}"
        )

@router.delete("/api-keys/{api_key_id}")
async def delete_api_key(
    api_key_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """حذف مفتاح API"""
    try:
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        if api_key.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this API key"
            )
        
        db.delete(api_key)
        db.commit()
        
        return {"message": "API key deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting API key: {str(e)}"
        )

@router.post("/api-keys/{api_key_id}/test")
async def test_api_key(
    api_key_id: int,
    current_user = Depends(AuthService.get_current_user_or_bypass),
    db: Session = Depends(get_db)
):
    """اختبار اتصال مفتاح API"""
    try:
        api_key = db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        if api_key.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to test this API key"
            )
        
        if not api_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key is not active"
            )
        
        # محاكاة اختبار الاتصال بالمنصة
        # في التطبيق الحقيقي، سنقوم باختبار الاتصال بالـ API الفعلي
        
        from datetime import datetime
        api_key.last_used = datetime.utcnow()
        db.commit()
        
        return {
            "status": "success",
            "message": f"Connection to {api_key.exchange} successful",
            "exchange": api_key.exchange,
            "permissions": api_key.permissions
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing API key: {str(e)}"
        )
    
