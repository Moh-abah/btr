from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.data_service import DataService
from app.services.indicators import (
    apply_indicators,
    get_available_indicators,
    transpile_pine_script,
    create_indicator_from_pine
)
from app.schemas.signals import SignalRequest

router = APIRouter(tags=["indicators"])





@router.post("/apply")
async def apply_indicators_to_data(
    symbol: str,
    timeframe: str,
    market: str = "crypto",
    indicators: List[Dict[str, Any]] = Body(...),
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    تطبيق مؤشرات على بيانات السوق
    
    - **symbol**: رمز السهم أو العملة
    - **timeframe**: الإطار الزمني (1m, 5m, 1h, etc.)
    - **market**: نوع السوق (crypto, stocks)
    - **indicators**: قائمة تكوينات المؤشرات
    - **days**: عدد الأيام التاريخية
    """
    data_service = DataService(db)
    
    try:
        result = await data_service.get_data_with_indicators(
            symbol=symbol,
            timeframe=timeframe,
            market=market,
            indicators_config=indicators,
            days=days
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))







def get_available_indicators(
    category: Optional[str] = None
) -> List[Dict[str, Any]]:

    indicator_category = None

    if category:
        try:
            indicator_category = IndicatorType(category)
        except ValueError:
            return []

    indicators = IndicatorRegistry.list_indicators(indicator_category)

    return [_clean_results(ind) for ind in indicators]







@router.post("/pine/transpile")
async def transpile_pine_code(
    pine_code: str = Body(..., embed=True),
    execute: bool = False
):
    """
    تحويل كود Pine Script إلى Python
    
    - **pine_code**: كود Pine Script الكامل
    - **execute**: إنشاء المؤشر وتنفيذه (اختياري)
    """
    try:
        python_code = transpile_pine_script(pine_code)
        
        result = {
            "success": True,
            "python_code": python_code,
            "message": "تم التحويل بنجاح"
        }
        
        if execute:
            try:
                indicator_class = create_indicator_from_pine(pine_code)
                result["indicator_created"] = True
                result["indicator_name"] = indicator_class.__name__
            except Exception as e:
                result["indicator_created"] = False
                result["error"] = str(e)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))











@router.post("/signals")
async def get_trading_signals(request: SignalRequest, db: AsyncSession = Depends(get_db)):
    """
    الحصول على إشارات التداول من المؤشرات
    
    - **symbol**: رمز السهم أو العملة
    - **timeframe**: الإطار الزمني
    - **market**: نوع السوق
    - **indicators**: قائمة تكوينات المؤشرات
    - **days**: عدد الأيام التاريخية
    """
    data_service = DataService(db)
    
    try:
        signals = await data_service.get_trading_signals(
            symbol=request.symbol,
            timeframe=request.timeframe,
            market=request.market,
            indicators_config=request.indicators,
            days=request.days
        )
        
        return signals
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))









@router.get("/{indicator_name}/params")
async def get_indicator_parameters(
    indicator_name: str
):
    """
    الحصول على المعاملات الافتراضية لمؤشر معين
    
    - **indicator_name**: اسم المؤشر (مثل: rsi, macd, bb)
    """
    from app.services.indicators.registry import IndicatorRegistry
    
    info = IndicatorRegistry.get_indicator_info(indicator_name)
    
    if not info:
        raise HTTPException(status_code=404, detail="Indicator not found")
    
    return {
        "name": indicator_name,
        "display_name": info.display_name,
        "description": info.description,
        "category": info.category.value,
        "default_params": info.default_params,
        "required_columns": info.required_columns
    }