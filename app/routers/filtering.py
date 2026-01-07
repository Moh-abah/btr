from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Dict, Any, Optional
import json

from app.services.filtering import (
    FilteringEngine, FilterCriteria, FilterResult,
    get_filtering_engine
)
from app.services.data_service import DataService
from app.database import get_db

router = APIRouter(tags=["filtering"])

@router.post("/symbols")
async def filter_symbols(
    market: str = Query("crypto"),
    criteria: FilterCriteria = Body(...),
    use_cache: bool = Query(True)
):
    """
    فلترة الرموز حسب معايير متعددة
    
    - **market**: السوق (crypto, stocks)
    - **criteria**: معايير الفلترة
    - **use_cache**: استخدام الكاش
    
    يمكن الفلترة حسب:
    - نمط الرموز (مثل *USDT)
    - نطاق السعر
    - حجم التداول
    - قيم المؤشرات
    - تفضيلات المستخدم
    """
    filtering_engine = get_filtering_engine()
    
    try:
        result = await filtering_engine.filter_symbols(
            market=market,
            criteria=criteria,
            use_cache=use_cache
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/markets")
async def get_available_markets():
    """
    الحصول على الأسواق المتاحة للفلترة
    """
    return {
        "markets": [
            {"id": "crypto", "name": "Cryptocurrency", "description": "العملات الرقمية"},
            {"id": "stocks", "name": "US Stocks", "description": "الأسهم الأمريكية"},
            {"id": "forex", "name": "Forex", "description": "سوق العملات", "coming_soon": True}
        ]
    }

@router.get("/criteria/examples")
async def get_filter_criteria_examples():
    """
    الحصول على أمثلة لمعايير الفلترة
    """
    examples = {
        "basic_crypto": {
            "name": "فلترة العملات الأساسية",
            "description": "فلترة العملات الرقمية ذات الحجم العالي",
            "criteria": {
                "market": "crypto",
                "symbol_pattern": "*USDT",
                "min_volume_24h": 10000000,
                "limit": 20
            }
        },
        "rsi_oversold": {
            "name": "فلترة RSI التشبع بالبيع",
            "description": "فلترة الرموز ذات RSI أقل من 30 (تشبع بالبيع)",
            "criteria": {
                "market": "crypto",
                "required_indicators": ["rsi"],
                "indicator_filters": {
                    "rsi": {"max": 30}
                },
                "limit": 10
            }
        },
        "trending_stocks": {
            "name": "الأسهم المتصاعدة",
            "description": "فلترة الأسهم ذات الاتجاه الصاعد",
            "criteria": {
                "market": "stocks",
                "min_price": 50,
                "sort_by": "price",
                "sort_order": "desc",
                "limit": 15
            }
        }
    }
    
    return examples

@router.get("/stats")
async def get_filtering_stats():
    """
    الحصول على إحصائيات وحدة الفلترة
    """
    filtering_engine = get_filtering_engine()
    
    return {
        "engine_stats": filtering_engine.get_stats(),
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/bulk")
async def bulk_filter_symbols(
    markets: List[str] = Body(["crypto"]),
    criteria_list: List[FilterCriteria] = Body(...),
    parallel: bool = Query(True)
):
    """
    فلترة الرموز في عدة أسواق دفعة واحدة
    
    - **markets**: قائمة الأسواق
    - **criteria_list**: قائمة معايير الفلترة
    - **parallel**: التشغيل بالتوازي
    """
    filtering_engine = get_filtering_engine()
    
    results = {}
    
    if parallel:
        # فلترة بالتوازي
        import asyncio
        
        tasks = []
        for market in markets:
            for criteria in criteria_list:
                task = filtering_engine.filter_symbols(market, criteria)
                tasks.append((market, criteria, task))
        
        for market, criteria, task in tasks:
            try:
                result = await task
                key = f"{market}_{criteria.json()[:50]}..."
                results[key] = {
                    "symbols": result.symbols,
                    "count": len(result.symbols)
                }
            except Exception as e:
                key = f"{market}_error"
                results[key] = {"error": str(e)}
    else:
        # فلترة تسلسلية
        for market in markets:
            for criteria in criteria_list:
                try:
                    result = await filtering_engine.filter_symbols(market, criteria)
                    key = f"{market}_{criteria.json()[:50]}..."
                    results[key] = {
                        "symbols": result.symbols,
                        "count": len(result.symbols)
                    }
                except Exception as e:
                    key = f"{market}_error"
                    results[key] = {"error": str(e)}
    
    return {
        "total_results": len(results),
        "results": results
    }