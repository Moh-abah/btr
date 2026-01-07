# app/routers/stock_analysis.py
import json
import math
from fastapi import APIRouter, Query, HTTPException
from typing import Any, List, Optional, Dict
from datetime import datetime, timedelta
import logging

from app.services.data_service import DataService
from app.database.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks", tags=["stocks-analysis"])

@router.get("/symbols")
async def get_stock_symbols(
    category: Optional[str] = Query(None, description="Category: technology, financial, healthcare, etc."),
    db: AsyncSession = Depends(get_db)
):
    """الحصول على رموز الأسهم حسب الفئة"""
    service = DataService(db)
    provider = service.providers.get("stocks")
    
    if not provider:
        raise HTTPException(status_code=500, detail="Stock provider not available")
    
    symbols = await provider.get_symbols(category)
    
    return {
        "category": category or "all",
        "symbols": symbols,
        "count": len(symbols),
        "timestamp": datetime.utcnow().isoformat()
    }



@router.get("/chart/{symbol}")
async def get_stock_chart(
    symbol: str,
    timeframe: str = Query("1d", description="Timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M"),
    period: str = Query("1mo", description="Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y, max"),
    indicators: Optional[str] = Query(None, description="Indicators in JSON format"),
    db: AsyncSession = Depends(get_db)
):
    """الحصول على بيانات الرسم البياني للأسهم"""
    try:
        service = DataService(db)
        # حاول كلا الاسمين لتجنب مشكلة "stock" vs "stocks"
        provider = service.providers.get("stocks") or service.providers.get("stock")
        
        if not provider:
            raise HTTPException(status_code=500, detail="Stock provider not available")
        
        # تحويل indicators من JSON
        indicators_list = []
        if indicators:
            try:
                indicators_list = json.loads(indicators)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse indicators JSON: {indicators}")
        
        # الحصول على البيانات
        chart_data = await provider.get_chart_data(
            symbol=symbol.upper(),  # تحويل إلى أحرف كبيرة
            timeframe=timeframe,
            period=period,
            indicators=indicators_list
        )
        
        # ======================
        # **الحل: تنظيف البيانات هنا!**
        # ======================
        def clean_json(obj: Any) -> Any:
            """
            دالة متكررة لتنظيف البيانات من القيم غير الصالحة للـ JSON
            """
            if obj is None:
                return None
            
            # إذا كان numpy float
            if hasattr(obj, 'item'):
                obj = obj.item()
            
            # إذا كان float عادي
            if isinstance(obj, float):
                # تحويل NaN و Inf إلى None
                if math.isnan(obj) or math.isinf(obj):
                    return None
                # تقريب الأرقام الطويلة جداً
                if abs(obj) > 1e10:
                    return round(obj, 4)
                return obj
            
            # إذا كان dict
            elif isinstance(obj, dict):
                return {k: clean_json(v) for k, v in obj.items()}
            
            # إذا كان list أو tuple
            elif isinstance(obj, (list, tuple)):
                return [clean_json(item) for item in obj]
            
            # إذا كان pandas Series أو DataFrame
            elif hasattr(obj, 'to_dict'):
                return clean_json(obj.to_dict())
            
            # أنواع أخرى (str, int, bool)
            else:
                return obj
        
        # تنظيف البيانات
        cleaned_data = clean_json(chart_data)
        
        # سجل للتصحيح (اختياري)
        logger.debug(f"Cleaned data for {symbol}: {json.dumps(cleaned_data, default=str)[:200]}...")
        
        return cleaned_data
        
    except Exception as e:
        logger.error(f"Error in get_stock_chart for {symbol}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)[:100]}"
        )
    
    
@router.get("/analysis/{symbol}")
async def get_technical_analysis(
    symbol: str,
    timeframe: str = Query("1d", description="Timeframe: 1d, 1w, 1M"),
    period: str = Query("3mo", description="Period: 1mo, 3mo, 6mo, 1y"),
    db: AsyncSession = Depends(get_db)
):
    """الحصول على التحليل الفني للأسهم"""
    service = DataService(db)
    provider = service.providers.get("stocks")
    
    if not provider:
        raise HTTPException(status_code=500, detail="Stock provider not available")
    
    analysis = await provider.get_technical_analysis(
        symbol=symbol,
        timeframe=timeframe,
        period=period
    )
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "period": period,
        "analysis": analysis,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/company/{symbol}")
async def get_company_profile(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """الحصول على ملف الشركة الكامل"""
    service = DataService(db)
    provider = service.providers.get("stocks")
    
    if not provider:
        raise HTTPException(status_code=500, detail="Stock provider not available")
    
    # معلومات الشركة
    company_info = await provider.get_company_info(symbol)
    
    # البيانات الأساسية
    fundamental_data = await provider.get_fundamental_data(symbol)
    
    # القوائم المالية
    financial_statements = await provider.get_financial_statements(symbol)
    
    return {
        "symbol": symbol,
        "company_info": company_info,
        "fundamental_data": fundamental_data,
        "financial_statements": financial_statements,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/market/summary")
async def get_market_summary(
    db: AsyncSession = Depends(get_db)
):
    """ملخص السوق"""
    service = DataService(db)
    provider = service.providers.get("stocks")
    
    if not provider:
        raise HTTPException(status_code=500, detail="Stock provider not available")
    
    summary = await provider.get_market_summary()
    
    return {
        "market_summary": summary,
        "timestamp": datetime.utcnow().isoformat()
    }








@router.get("/market/top-movers")
async def get_top_movers(
    db: AsyncSession = Depends(get_db)
):
    """أكبر الرابحين والخاسرين"""
    service = DataService(db)
    provider = service.providers.get("stocks")
    
    if not provider:
        raise HTTPException(status_code=500, detail="Stock provider not available")
    
    movers = await provider.get_top_gainers_losers()
    
    return {
        "gainers": movers.get("gainers", []),
        "losers": movers.get("losers", []),
        "timestamp": datetime.utcnow().isoformat()
    }













@router.get("/search")
async def search_stocks(
    query: str = Query(..., description="Search query"),
    db: AsyncSession = Depends(get_db)
):
    """البحث عن الأسهم"""
    service = DataService(db)
    provider = service.providers.get("stocks")
    
    if not provider:
        raise HTTPException(status_code=500, detail="Stock provider not available")
    
    results = await provider.search_stocks(query)
    
    return {
        "query": query,
        "results": results,
        "count": len(results),
        "timestamp": datetime.utcnow().isoformat()
    }












@router.get("/sectors")
async def get_sector_analysis(
    db: AsyncSession = Depends(get_db)
):
    """تحليل القطاعات"""
    service = DataService(db)
    provider = service.providers.get("stocks")
    
    if not provider:
        raise HTTPException(status_code=500, detail="Stock provider not available")
    
    sectors = await provider.get_sector_analysis()
    
    return {
        "sectors": sectors,
        "timestamp": datetime.utcnow().isoformat()
    }