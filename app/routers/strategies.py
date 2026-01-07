# app\routers\strategies.py

from datetime import datetime  # ✅ صحيح
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, Body, File, Request, UploadFile, Query
from typing import List, Dict, Any, Optional
import json
import tempfile
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
import yaml

from app.database import get_db
from app.services.data_service import DataService
from app.services.strategy import (
    run_strategy,
    validate_strategy_config,
    save_strategy,
    load_strategy_from_file,
    update_strategy,
    get_loaded_strategies,
    reload_strategy
)


import logging

# إنشاء logger خاص لهذا الملف
logger = logging.getLogger(__name__)

router = APIRouter(tags=["strategies"])

# إعداد الـ logger
logger = logging.getLogger(__name__)

@router.post("/run")
async def run_strategy_on_data(
    symbol: str,
    timeframe: str,
    market: str = "crypto",
    strategy_config: Dict[str, Any] = Body(...),
    days: int = 30,
    live_mode: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    تشغيل إستراتيجية على بيانات السوق
    """
    # تسجيل بداية الطلب
    request_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    logger.info(f"[{request_id}] بدء طلب run_strategy_on_data", extra={
        "symbol": symbol,
        "timeframe": timeframe,
        "market": market,
        "days": days,
        "live_mode": live_mode,
        "strategy_name": strategy_config.get("name"),
        "config_keys": list(strategy_config.keys())
    })
    
    # تسجيل config كامل (بحد معقول)
    try:
        config_summary = json.dumps(strategy_config, default=str, ensure_ascii=False)[:500]
        logger.debug(f"[{request_id}] إستراتيجية config (مختصر): {config_summary}")
    except Exception as e:
        logger.warning(f"[{request_id}] فشل في تسجيل config: {str(e)}")
    
    data_service = DataService(db)
    
    try:
        # الحصول على البيانات
        logger.info(f"[{request_id}] جلب البيانات التاريخية...")
        start_time = datetime.now()
        
        dataframe = await data_service.get_historical(
            symbol=symbol,
            timeframe=timeframe,
            market=market,
            days=days
        )
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[{request_id}] تم جلب البيانات بنجاح", extra={
            "data_shape": dataframe.shape if not dataframe.empty else "empty",
            "data_columns": list(dataframe.columns) if not dataframe.empty else [],
            "data_head": dataframe.head(3).to_dict() if not dataframe.empty else {},
            "elapsed_seconds": elapsed_time
        })
        
        if dataframe.empty:
            logger.error(f"[{request_id}] لا توجد بيانات متاحة", extra={
                "symbol": symbol,
                "timeframe": timeframe,
                "market": market,
                "days": days
            })
            raise HTTPException(status_code=404, detail="No data available")
        
        # تشغيل الإستراتيجية
        logger.info(f"[{request_id}] تشغيل الإستراتيجية...")
        strategy_start = datetime.now()
        
        result = await run_strategy(dataframe, strategy_config, live_mode)
        
        strategy_elapsed = (datetime.now() - strategy_start).total_seconds()
        logger.info(f"[{request_id}] تم تشغيل الإستراتيجية بنجاح", extra={
            "total_signals": len(result.signals),
            "filtered_signals": len(result.filtered_signals),
            "strategy_time_seconds": strategy_elapsed,
            "metrics_keys": list(result.metrics.keys()) if result.metrics else []
        })
        
        # تحويل النتيجة إلى قاموس
        result_dict = {
            "signals": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "action": s.action,
                    "price": s.price,
                    "reason": s.reason,
                    "rule_name": s.rule_name,
                    "strength": s.strength,
                    "metadata": s.metadata
                }
                for s in result.signals
            ],
            "filtered_signals": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "action": s.action,
                    "price": s.price,
                    "reason": s.reason,
                    "rule_name": s.rule_name,
                    "strength": s.strength
                }
                for s in result.filtered_signals
            ],
            "metrics": result.metrics,
            "strategy_summary": {
                "name": strategy_config.get("name"),
                "total_indicators": len(strategy_config.get("indicators", [])),
                "total_entry_rules": len(strategy_config.get("entry_rules", [])),
                "total_exit_rules": len(strategy_config.get("exit_rules", []))
            }
        }
        
        # تسجيل النتيجة النهائية
        logger.info(f"[{request_id}] اكتمل الطلب بنجاح", extra={
            "total_signals_count": len(result_dict["signals"]),
            "filtered_signals_count": len(result_dict["filtered_signals"])
        })
        
        return result_dict
        
    except HTTPException as he:
        # إعادة HTTPException كما هي (لأن FastAPI يتعامل معها بشكل خاص)
        logger.error(f"[{request_id}] HTTP Exception: {he.detail}", extra={
            "status_code": he.status_code,
            "detail": he.detail
        })
        raise he
        
    except Exception as e:
        # تسجيل الخطأ بالتفصيل
        logger.error(f"[{request_id}] حدث خطأ غير متوقع", exc_info=True, extra={
            "error_type": type(e).__name__,
            "error_message": str(e),
            "symbol": symbol,
            "timeframe": timeframe,
            "market": market,
            "days": days,
            "live_mode": live_mode
        })
        
        # يمكنك إضافة logging إضافي للـ traceback
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"[{request_id}] Traceback:\n{error_trace}")
        
        raise HTTPException(status_code=500, detail=str(e))
    





    

@router.post("/validate")
async def validate_strategy_config_api(
    strategy_config: Dict[str, Any] = Body(...)
):
    """
    التحقق من صحة تكوين الإستراتيجية
    
    - **strategy_config**: تكوين الإستراتيجية المراد التحقق منها
    """
    validation_result = validate_strategy_config(strategy_config)
    
    if validation_result["valid"]:
        return {
            "valid": True,
            "message": "Strategy configuration is valid",
            "config_summary": {
                "name": validation_result["config"]["name"],
                "version": validation_result["config"]["version"],
                "indicators_count": len(validation_result["config"]["indicators"]),
                "entry_rules_count": len(validation_result["config"]["entry_rules"]),
                "exit_rules_count": len(validation_result["config"]["exit_rules"])
            }
        }
    else:
        return {
            "valid": False,
            "message": "Strategy configuration is invalid",
            "errors": validation_result["errors"]
        }

@router.post("/save")
async def save_strategy_api(
    strategy_config: Dict[str, Any] = Body(...),
    file_name: Optional[str] = None
):
    """
    حفظ إستراتيجية إلى ملف على القرص
    
    - **strategy_config**: تكوين الإستراتيجية
    - **file_name**: اسم الملف (اختياري)
    """
    try:
        file_path = save_strategy(strategy_config, file_name)
        
        return {
            "success": True,
            "message": "Strategy saved successfully",
            "file_path": file_path,
            "strategy_name": strategy_config.get("name")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_strategy_file(
    file: UploadFile = File(...)
):
    """
    رفع ملف إستراتيجية وتحليله
    
    - **file**: ملف الإستراتيجية (JSON أو YAML)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    # التحقق من امتداد الملف
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.json', '.yaml', '.yml']:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Use JSON or YAML"
        )
    
    # قراءة المحتوى
    content = await file.read()
    
    try:
        if file_ext == '.json':
            strategy_config = json.loads(content.decode('utf-8'))
        else:
            
            strategy_config = yaml.safe_load(content.decode('utf-8'))
        
        # التحقق من الصحة
        validation_result = validate_strategy_config(strategy_config)
        
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid strategy configuration: {validation_result['errors']}"
            )
        
        # تحميل الإستراتيجية
        with tempfile.NamedTemporaryFile(mode='w', suffix=file_ext, delete=False) as tmp:
            tmp.write(content.decode('utf-8'))
            tmp_path = tmp.name
        
        try:
            engine = load_strategy_from_file(tmp_path)
            strategy_summary = engine.get_strategy_summary()
            
            return {
                "success": True,
                "message": "Strategy uploaded and validated successfully",
                "strategy_summary": strategy_summary,
                "file_name": file.filename
            }
        finally:
            # تنظيف الملف المؤقت
            Path(tmp_path).unlink(missing_ok=True)
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_loaded_strategies_api(
    active_only: bool = Query(False, description="عرض الإستراتيجيات النشطة فقط")
):
    """
    سرد جميع الإستراتيجيات المحملة في الذاكرة
    
    - **active_only**: عرض الإستراتيجيات النشطة فقط
    """
    strategies = get_loaded_strategies()
    
    if active_only:
        strategies = [s for s in strategies if s.get("is_active", True)]
    
    return {
        "count": len(strategies),
        "strategies": strategies
    }

@router.put("/update/{strategy_name}")
async def update_strategy_api(
    strategy_name: str,
    updates: Dict[str, Any] = Body(...)
):
    """
    تحديث إستراتيجية محملة
    
    - **strategy_name**: اسم الإستراتيجية
    - **updates**: التحديثات المطلوبة
    """
    engine = update_strategy(strategy_name, updates)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
    return {
        "success": True,
        "message": f"Strategy '{strategy_name}' updated successfully",
        "strategy_summary": engine.get_strategy_summary()
    }

@router.post("/reload/{strategy_name}")
async def reload_strategy_api(strategy_name: str):
    """
    إعادة تحميل إستراتيجية من الملف
    
    - **strategy_name**: اسم الإستراتيجية
    """
    engine = reload_strategy(strategy_name)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
    return {
        "success": True,
        "message": f"Strategy '{strategy_name}' reloaded successfully",
        "strategy_summary": engine.get_strategy_summary()
    }

@router.get("/examples/{example_name}")
async def get_strategy_example(example_name: str):
    """
    الحصول على مثال إستراتيجية جاهزة
    
    - **example_name**: اسم المثال (rsi_basic, macd_advanced, trend_following)
    """
    examples = {
        "rsi_basic": {
            "name": "RSI Basic Strategy",
            "description": "استراتيجية RSI بسيطة للدخول عند التشبع بالبيع والخروج عند التشبع بالشراء",
            "indicators": ["rsi"],
            "complexity": "beginner",
            "timeframe": "1h"
        },
        "macd_advanced": {
            "name": "MACD Advanced Strategy",
            "description": "استراتيجية MACD متقدمة مع تأكيد من RSI ومتوسطات متحركة",
            "indicators": ["macd", "rsi", "ema"],
            "complexity": "intermediate",
            "timeframe": "4h"
        },
        "trend_following": {
            "name": "Trend Following Strategy",
            "description": "استراتيجية تتبع الاتجاه باستخدام متوسطات متحركة متعددة",
            "indicators": ["sma", "ema", "atr"],
            "complexity": "advanced",
            "timeframe": "1d"
        }
    }
    
    if example_name not in examples:
        raise HTTPException(status_code=404, detail="Example not found")
    
    # استيراد المثال المطلوب
    try:
        if example_name == "rsi_basic":
            from app.services.strategy.strategys.rsi_strategy import get_rsi_strategy
            strategy_config = get_rsi_strategy()
        elif example_name == "macd_advanced":
            from app.services.strategy.strategys.macd_strategy import get_macd_strategy
            strategy_config = get_macd_strategy()
        else:
            # يمكن إضافة المزيد من الأمثلة هنا
            raise HTTPException(status_code=404, detail="Example implementation not found")
        
        return {
            "example_info": examples[example_name],
            "strategy_config": strategy_config
        }
        
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Could not load example: {str(e)}")
    









# #     # app/routers/strategies.py
# # from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile, Query, status
# # from typing import List, Dict, Any, Optional
# # import json
# # import tempfile
# # from pathlib import Path
# # from sqlalchemy.ext.asyncio import AsyncSession
# # import yaml
# # import asyncio
# # from datetime import datetime, timedelta

# # from app.database import get_db
# # from app.services.data_service import DataService
# # from app.services.strategy import (
# #     run_strategy,
# #     validate_strategy_config,
# #     save_strategy,
# #     load_strategy_from_file,
# #     get_loaded_strategies,
# #     get_strategy_examples,
# #     get_strategy_example_config,
# #     get_strategy_by_hash,
# #     unload_strategy
# # )

# # router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])

# # @router.post("/run", summary="تشغيل إستراتيجية على بيانات السوق")
# # async def run_strategy_on_data(
# #     symbol: str,
# #     timeframe: str = Query("1h", description="الإطار الزمني للبيانات"),
# #     market: str = Query("crypto", description="نوع السوق (crypto/stocks)"),
# #     strategy_config: Dict[str, Any] = Body(...),
# #     days: int = Query(30, description="عدد الأيام التاريخية", ge=1, le=3650),
# #     live_mode: bool = Query(False, description="وضع التشغيل الحي"),
# #     include_indicators: bool = Query(False, description="تضمين بيانات المؤشرات"),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """
# #     تشغيل إستراتيجية على بيانات السوق
    
# #     - **symbol**: رمز السهم أو العملة
# #     - **timeframe**: الإطار الزمني
# #     - **market**: نوع السوق
# #     - **strategy_config**: تكوين الإستراتيجية
# #     - **days**: عدد الأيام التاريخية
# #     - **live_mode**: وضع التشغيل الحي (لآخر نقطة بيانات فقط)
# #     - **include_indicators**: تضمين بيانات المؤشرات في النتيجة
# #     """
# #     try:
# #         data_service = DataService(db)
        
# #         # الحصول على البيانات
# #         print(f"📥 Fetching data for {symbol} ({market}) - {timeframe} - {days} days")
        
# #         dataframe = await data_service.get_historical(
# #             symbol=symbol,
# #             timeframe=timeframe,
# #             market=market,
# #             days=days
# #         )
        
# #         if dataframe.empty:
# #             raise HTTPException(
# #                 status_code=status.HTTP_404_NOT_FOUND,
# #                 detail=f"No data available for {symbol} in {market}"
# #             )
        
# #         print(f"✅ Data retrieved: {len(dataframe)} rows")
        
# #         # تشغيل الإستراتيجية
# #         print(f"🚀 Running strategy: {strategy_config.get('name', 'Unknown')}")
        
# #         result = await run_strategy(
# #             data=dataframe,
# #             strategy_config=strategy_config,
# #             symbol=symbol,
# #             live_mode=live_mode,
# #             use_cache=True
# #         )
        
# #         # تحضير الاستجابة
# #         response = {
# #             "success": True,
# #             "symbol": symbol,
# #             "market": market,
# #             "timeframe": timeframe,
# #             "days": days,
# #             "strategy_name": strategy_config.get("name"),
# #             "execution_time": datetime.utcnow().isoformat(),
# #             "data_info": {
# #                 "rows": len(dataframe),
# #                 "start_date": dataframe.index[0].isoformat() if len(dataframe) > 0 else None,
# #                 "end_date": dataframe.index[-1].isoformat() if len(dataframe) > 0 else None
# #             },
# #             "signals": [
# #                 {
# #                     "timestamp": s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
# #                     "action": s.action,
# #                     "price": s.price,
# #                     "reason": s.reason,
# #                     "rule_name": s.rule_name,
# #                     "strength": s.strength,
# #                     "metadata": s.metadata or {}
# #                 }
# #                 for s in result.signals
# #             ],
# #             "filtered_signals": [
# #                 {
# #                     "timestamp": s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
# #                     "action": s.action,
# #                     "price": s.price,
# #                     "reason": s.reason,
# #                     "rule_name": s.rule_name,
# #                     "strength": s.strength
# #                 }
# #                 for s in result.filtered_signals
# #             ],
# #             "metrics": result.metrics,
# #             "summary": {
# #                 "total_signals": len(result.signals),
# #                 "filtered_signals": len(result.filtered_signals),
# #                 "entry_signals": len([s for s in result.filtered_signals if s.action in ['buy', 'sell']]),
# #                 "exit_signals": len([s for s in result.filtered_signals if s.action == 'close'])
# #             }
# #         }
        
# #         # إضافة بيانات المؤشرات إذا طلب
# #         if include_indicators and hasattr(result, 'indicators'):
# #             response["indicators"] = result.indicators
        
# #         print(f"✅ Strategy completed: {len(result.filtered_signals)} signals generated")
        
# #         return response
        
# #     except HTTPException:
# #         raise
# #     except Exception as e:
# #         print(f"❌ Error running strategy: {e}")
# #         raise HTTPException(
# #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #             detail=f"Error running strategy: {str(e)}"
# #         )

# # @router.post("/validate", summary="التحقق من صحة تكوين الإستراتيجية")
# # async def validate_strategy_config_api(
# #     strategy_config: Dict[str, Any] = Body(...)
# # ):
# #     """
# #     التحقق من صحة تكوين الإستراتيجية
    
# #     - **strategy_config**: تكوين الإستراتيجية المراد التحقق منها
# #     """
# #     validation_result = validate_strategy_config(strategy_config)
    
# #     return validation_result

# # @router.post("/save", summary="حفظ إستراتيجية إلى ملف")
# # async def save_strategy_api(
# #     strategy_config: Dict[str, Any] = Body(...),
# #     file_name: Optional[str] = Query(None, description="اسم الملف (اختياري)")
# # ):
# #     """
# #     حفظ إستراتيجية إلى ملف على القرص
    
# #     - **strategy_config**: تكوين الإستراتيجية
# #     - **file_name**: اسم الملف (اختياري)
# #     """
# #     try:
# #         result = await save_strategy(strategy_config, file_name)
        
# #         if not result["success"]:
# #             raise HTTPException(
# #                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #                 detail=result.get("error", "Unknown error")
# #             )
        
# #         return {
# #             "success": True,
# #             "message": "Strategy saved successfully",
# #             "details": result
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #             detail=str(e)
# #         )

# # @router.post("/upload", summary="رفع ملف إستراتيجية")
# # async def upload_strategy_file(
# #     file: UploadFile = File(...)
# # ):
# #     """
# #     رفع ملف إستراتيجية وتحليله
    
# #     - **file**: ملف الإستراتيجية (JSON أو YAML)
# #     """
# #     if not file.filename:
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail="No file uploaded"
# #         )
    
# #     # التحقق من امتداد الملف
# #     file_ext = Path(file.filename).suffix.lower()
# #     if file_ext not in ['.json', '.yaml', '.yml']:
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail="Unsupported file format. Use JSON or YAML"
# #         )
    
# #     try:
# #         # قراءة المحتوى
# #         content = await file.read()
        
# #         # تحليل المحتوى
# #         if file_ext == '.json':
# #             strategy_config = json.loads(content.decode('utf-8'))
# #         else:
# #             strategy_config = yaml.safe_load(content.decode('utf-8'))
        
# #         # التحقق من الصحة
# #         validation_result = validate_strategy_config(strategy_config)
        
# #         if not validation_result["valid"]:
# #             raise HTTPException(
# #                 status_code=status.HTTP_400_BAD_REQUEST,
# #                 detail=f"Invalid strategy configuration: {validation_result['errors']}"
# #             )
        
# #         # حفظ الملف المؤقت
# #         with tempfile.NamedTemporaryFile(mode='w', suffix=file_ext, delete=False) as tmp:
# #             tmp.write(content.decode('utf-8'))
# #             tmp_path = tmp.name
        
# #         try:
# #             # تحميل الإستراتيجية
# #             load_result = await load_strategy_from_file(tmp_path, load_to_memory=True)
            
# #             if not load_result["success"]:
# #                 raise HTTPException(
# #                     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #                     detail=load_result.get("error", "Failed to load strategy")
# #                 )
            
# #             return {
# #                 "success": True,
# #                 "message": "Strategy uploaded and validated successfully",
# #                 "strategy_info": {
# #                     "name": strategy_config.get("name"),
# #                     "description": strategy_config.get("description"),
# #                     "engine_hash": load_result.get("engine_hash"),
# #                     "indicators_count": len(strategy_config.get("indicators", [])),
# #                     "entry_rules_count": len(strategy_config.get("entry_rules", []))
# #                 },
# #                 "file_info": {
# #                     "original_name": file.filename,
# #                     "size_bytes": len(content)
# #                 }
# #             }
            
# #         finally:
# #             # تنظيف الملف المؤقت
# #             Path(tmp_path).unlink(missing_ok=True)
        
# #     except json.JSONDecodeError as e:
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail=f"Invalid JSON format: {str(e)}"
# #         )
# #     except yaml.YAMLError as e:
# #         raise HTTPException(
# #             status_code=status.HTTP_400_BAD_REQUEST,
# #             detail=f"Invalid YAML format: {str(e)}"
# #         )
# #     except HTTPException:
# #         raise
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #             detail=f"Error processing file: {str(e)}"
# #         )

# # @router.get("/list", summary="قائمة الإستراتيجيات المحملة")
# # async def list_loaded_strategies_api(
# #     include_details: bool = Query(False, description="تضمين التفاصيل الكاملة")
# # ):
# #     """
# #     سرد جميع الإستراتيجيات المحملة في الذاكرة
    
# #     - **include_details**: تضمين التفاصيل الكاملة للإستراتيجيات
# #     """
# #     strategies = get_loaded_strategies()
    
# #     if include_details:
# #         detailed_strategies = []
# #         for strategy in strategies:
# #             engine = get_strategy_by_hash(strategy["hash"])
# #             if engine:
# #                 detailed_strategies.append({
# #                     **strategy,
# #                     "full_config": engine.config.dict() if hasattr(engine.config, 'dict') else None,
# #                     "indicators": [ind.dict() for ind in engine.config.indicators] if hasattr(engine.config, 'indicators') else []
# #                 })
# #             else:
# #                 detailed_strategies.append(strategy)
        
# #         return {
# #             "count": len(detailed_strategies),
# #             "strategies": detailed_strategies
# #         }
    
# #     return {
# #         "count": len(strategies),
# #         "strategies": strategies
# #     }

# # @router.delete("/unload/{strategy_hash}", summary="إزالة إستراتيجية من الذاكرة")
# # async def unload_strategy_api(strategy_hash: str):
# #     """
# #     إزالة إستراتيجية محملة من الذاكرة
    
# #     - **strategy_hash**: الـ hash الخاص بالإستراتيجية
# #     """
# #     success = unload_strategy(strategy_hash)
    
# #     if not success:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail=f"Strategy with hash '{strategy_hash}' not found"
# #         )
    
# #     return {
# #         "success": True,
# #         "message": f"Strategy '{strategy_hash}' unloaded successfully"
# #     }

# # @router.get("/examples", summary="الحصول على أمثلة الإستراتيجيات")
# # async def get_strategy_examples_api():
# #     """
# #     الحصول على قائمة بأمثلة الإستراتيجيات الجاهزة
# #     """
# #     examples = await get_strategy_examples()
    
# #     return {
# #         "success": True,
# #         **examples
# #     }

# # @router.get("/examples/{example_name}", summary="الحصول على تكوين إستراتيجية مثال")
# # async def get_strategy_example_config_api(example_name: str):
# #     """
# #     الحصول على تكوين إستراتيجية مثال جاهزة
    
# #     - **example_name**: اسم المثال (rsi_basic, macd_advanced, trend_following, mean_reversion)
# #     """
# #     try:
# #         config = await get_strategy_example_config(example_name)
        
# #         return {
# #             "success": True,
# #             "example_name": example_name,
# #             "strategy_config": config
# #         }
        
# #     except ValueError as e:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail=str(e)
# #         )
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #             detail=str(e)
# #         )

# # @router.get("/test", summary="اختبار تشغيل إستراتيجية بسيطة")
# # async def test_strategy_api(
# #     symbol: str = Query("AAPL", description="رمز الأصل للاختبار"),
# #     days: int = Query(30, description="عدد الأيام"),
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """
# #     اختبار تشغيل إستراتيجية بسيطة (RSI) على بيانات حقيقية
# #     """
# #     try:
# #         # استخدام إستراتيجية RSI مثال
# #         from app.services.strategy.strategys.rsi_strategy import get_rsi_strategy
# #         strategy_config = get_rsi_strategy()
        
# #         # تشغيل الإستراتيجية
# #         data_service = DataService(db)
        
# #         dataframe = await data_service.get_historical(
# #             symbol=symbol,
# #             timeframe="1d",
# #             market="stocks",
# #             days=days
# #         )
        
# #         if dataframe.empty:
# #             raise HTTPException(
# #                 status_code=status.HTTP_404_NOT_FOUND,
# #                 detail=f"No data available for {symbol}"
# #             )
        
# #         result = await run_strategy(
# #             data=dataframe,
# #             strategy_config=strategy_config,
# #             symbol=symbol,
# #             live_mode=False
# #         )
        
# #         # إعداد تقرير الاختبار
# #         test_report = {
# #             "test_date": datetime.utcnow().isoformat(),
# #             "symbol": symbol,
# #             "strategy": strategy_config["name"],
# #             "data_points": len(dataframe),
# #             "signals_generated": len(result.signals),
# #             "signals_filtered": len(result.filtered_signals),
# #             "metrics": result.metrics,
# #             "sample_signals": [
# #                 {
# #                     "timestamp": s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
# #                     "action": s.action,
# #                     "price": s.price,
# #                     "rule": s.rule_name
# #                 }
# #                 for s in result.filtered_signals[:5]  # أول 5 إشارات فقط
# #             ]
# #         }
        
# #         return {
# #             "success": True,
# #             "message": "Strategy test completed successfully",
# #             "report": test_report
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #             detail=f"Test failed: {str(e)}"
# #         )







# # # app\routers\strategies.py

# # from datetime import datetime  # ✅ صحيح
# # import time
# # import uuid
# # from fastapi import APIRouter, Depends, HTTPException, Body, File, Request, UploadFile, Query
# # from typing import List, Dict, Any, Optional
# # import json
# # import tempfile
# # from pathlib import Path
# # from sqlalchemy.ext.asyncio import AsyncSession
# # import yaml

# # from app.database import get_db
# # from app.services.data_service import DataService
# # from app.services.strategy import (
# #     run_strategy,
# #     validate_strategy_config,
# #     save_strategy,
# #     load_strategy_from_file,
# #     update_strategy,
# #     get_loaded_strategies,
# #     reload_strategy
# # )


# # import logging

# # # إنشاء logger خاص لهذا الملف
# # logger = logging.getLogger(__name__)

# # router = APIRouter(tags=["strategies"])

# # # إعداد الـ logger
# # logger = logging.getLogger(__name__)

# # @router.post("/run")
# # async def run_strategy_on_data(
# #     symbol: str,
# #     timeframe: str,
# #     market: str = "crypto",
# #     strategy_config: Dict[str, Any] = Body(...),
# #     days: int = 30,
# #     live_mode: bool = False,
# #     db: AsyncSession = Depends(get_db)
# # ):
# #     """
# #     تشغيل إستراتيجية على بيانات السوق
# #     """
# #     # تسجيل بداية الطلب
# #     request_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
# #     logger.info(f"[{request_id}] بدء طلب run_strategy_on_data", extra={
# #         "symbol": symbol,
# #         "timeframe": timeframe,
# #         "market": market,
# #         "days": days,
# #         "live_mode": live_mode,
# #         "strategy_name": strategy_config.get("name"),
# #         "config_keys": list(strategy_config.keys())
# #     })
    
# #     # تسجيل config كامل (بحد معقول)
# #     try:
# #         config_summary = json.dumps(strategy_config, default=str, ensure_ascii=False)[:500]
# #         logger.debug(f"[{request_id}] إستراتيجية config (مختصر): {config_summary}")
# #     except Exception as e:
# #         logger.warning(f"[{request_id}] فشل في تسجيل config: {str(e)}")
    
# #     data_service = DataService(db)
    
# #     try:
# #         # الحصول على البيانات
# #         logger.info(f"[{request_id}] جلب البيانات التاريخية...")
# #         start_time = datetime.now()
        
# #         dataframe = await data_service.get_historical(
# #             symbol=symbol,
# #             timeframe=timeframe,
# #             market=market,
# #             days=days
# #         )
        
# #         elapsed_time = (datetime.now() - start_time).total_seconds()
# #         logger.info(f"[{request_id}] تم جلب البيانات بنجاح", extra={
# #             "data_shape": dataframe.shape if not dataframe.empty else "empty",
# #             "data_columns": list(dataframe.columns) if not dataframe.empty else [],
# #             "data_head": dataframe.head(3).to_dict() if not dataframe.empty else {},
# #             "elapsed_seconds": elapsed_time
# #         })
        
# #         if dataframe.empty:
# #             logger.error(f"[{request_id}] لا توجد بيانات متاحة", extra={
# #                 "symbol": symbol,
# #                 "timeframe": timeframe,
# #                 "market": market,
# #                 "days": days
# #             })
# #             raise HTTPException(status_code=404, detail="No data available")
        
# #         # تشغيل الإستراتيجية
# #         logger.info(f"[{request_id}] تشغيل الإستراتيجية...")
# #         strategy_start = datetime.now()
        
# #         result = await run_strategy(dataframe, strategy_config, live_mode)
        
# #         strategy_elapsed = (datetime.now() - strategy_start).total_seconds()
# #         logger.info(f"[{request_id}] تم تشغيل الإستراتيجية بنجاح", extra={
# #             "total_signals": len(result.signals),
# #             "filtered_signals": len(result.filtered_signals),
# #             "strategy_time_seconds": strategy_elapsed,
# #             "metrics_keys": list(result.metrics.keys()) if result.metrics else []
# #         })
        
# #         # تحويل النتيجة إلى قاموس
# #         result_dict = {
# #             "signals": [
# #                 {
# #                     "timestamp": s.timestamp.isoformat(),
# #                     "action": s.action,
# #                     "price": s.price,
# #                     "reason": s.reason,
# #                     "rule_name": s.rule_name,
# #                     "strength": s.strength,
# #                     "metadata": s.metadata
# #                 }
# #                 for s in result.signals
# #             ],
# #             "filtered_signals": [
# #                 {
# #                     "timestamp": s.timestamp.isoformat(),
# #                     "action": s.action,
# #                     "price": s.price,
# #                     "reason": s.reason,
# #                     "rule_name": s.rule_name,
# #                     "strength": s.strength
# #                 }
# #                 for s in result.filtered_signals
# #             ],
# #             "metrics": result.metrics,
# #             "strategy_summary": {
# #                 "name": strategy_config.get("name"),
# #                 "total_indicators": len(strategy_config.get("indicators", [])),
# #                 "total_entry_rules": len(strategy_config.get("entry_rules", [])),
# #                 "total_exit_rules": len(strategy_config.get("exit_rules", []))
# #             }
# #         }
        
# #         # تسجيل النتيجة النهائية
# #         logger.info(f"[{request_id}] اكتمل الطلب بنجاح", extra={
# #             "total_signals_count": len(result_dict["signals"]),
# #             "filtered_signals_count": len(result_dict["filtered_signals"])
# #         })
        
# #         return result_dict
        
# #     except HTTPException as he:
# #         # إعادة HTTPException كما هي (لأن FastAPI يتعامل معها بشكل خاص)
# #         logger.error(f"[{request_id}] HTTP Exception: {he.detail}", extra={
# #             "status_code": he.status_code,
# #             "detail": he.detail
# #         })
# #         raise he
        
# #     except Exception as e:
# #         # تسجيل الخطأ بالتفصيل
# #         logger.error(f"[{request_id}] حدث خطأ غير متوقع", exc_info=True, extra={
# #             "error_type": type(e).__name__,
# #             "error_message": str(e),
# #             "symbol": symbol,
# #             "timeframe": timeframe,
# #             "market": market,
# #             "days": days,
# #             "live_mode": live_mode
# #         })
        
# #         # يمكنك إضافة logging إضافي للـ traceback
# #         import traceback
# #         error_trace = traceback.format_exc()
# #         logger.error(f"[{request_id}] Traceback:\n{error_trace}")
        
# #         raise HTTPException(status_code=500, detail=str(e))
    

# # @router.post("/validate")
# # async def validate_strategy_config_api(
# #     strategy_config: Dict[str, Any] = Body(...)
# # ):
# #     """
# #     التحقق من صحة تكوين الإستراتيجية
    
# #     - **strategy_config**: تكوين الإستراتيجية المراد التحقق منها
# #     """
# #     validation_result = validate_strategy_config(strategy_config)
    
# #     if validation_result["valid"]:
# #         return {
# #             "valid": True,
# #             "message": "Strategy configuration is valid",
# #             "config_summary": {
# #                 "name": validation_result["config"]["name"],
# #                 "version": validation_result["config"]["version"],
# #                 "indicators_count": len(validation_result["config"]["indicators"]),
# #                 "entry_rules_count": len(validation_result["config"]["entry_rules"]),
# #                 "exit_rules_count": len(validation_result["config"]["exit_rules"])
# #             }
# #         }
# #     else:
# #         return {
# #             "valid": False,
# #             "message": "Strategy configuration is invalid",
# #             "errors": validation_result["errors"]
# #         }

# # @router.post("/save")
# # async def save_strategy_api(
# #     strategy_config: Dict[str, Any] = Body(...),
# #     file_name: Optional[str] = None
# # ):
# #     """
# #     حفظ إستراتيجية إلى ملف على القرص
    
# #     - **strategy_config**: تكوين الإستراتيجية
# #     - **file_name**: اسم الملف (اختياري)
# #     """
# #     try:
# #         file_path = save_strategy(strategy_config, file_name)
        
# #         return {
# #             "success": True,
# #             "message": "Strategy saved successfully",
# #             "file_path": file_path,
# #             "strategy_name": strategy_config.get("name")
# #         }
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))

# # @router.post("/upload")
# # async def upload_strategy_file(
# #     file: UploadFile = File(...)
# # ):
# #     """
# #     رفع ملف إستراتيجية وتحليله
    
# #     - **file**: ملف الإستراتيجية (JSON أو YAML)
# #     """
# #     if not file.filename:
# #         raise HTTPException(status_code=400, detail="No file uploaded")
    
# #     # التحقق من امتداد الملف
# #     file_ext = Path(file.filename).suffix.lower()
# #     if file_ext not in ['.json', '.yaml', '.yml']:
# #         raise HTTPException(
# #             status_code=400,
# #             detail="Unsupported file format. Use JSON or YAML"
# #         )
    
# #     # قراءة المحتوى
# #     content = await file.read()
    
# #     try:
# #         if file_ext == '.json':
# #             strategy_config = json.loads(content.decode('utf-8'))
# #         else:
            
# #             strategy_config = yaml.safe_load(content.decode('utf-8'))
        
# #         # التحقق من الصحة
# #         validation_result = validate_strategy_config(strategy_config)
        
# #         if not validation_result["valid"]:
# #             raise HTTPException(
# #                 status_code=400,
# #                 detail=f"Invalid strategy configuration: {validation_result['errors']}"
# #             )
        
# #         # تحميل الإستراتيجية
# #         with tempfile.NamedTemporaryFile(mode='w', suffix=file_ext, delete=False) as tmp:
# #             tmp.write(content.decode('utf-8'))
# #             tmp_path = tmp.name
        
# #         try:
# #             engine = load_strategy_from_file(tmp_path)
# #             strategy_summary = engine.get_strategy_summary()
            
# #             return {
# #                 "success": True,
# #                 "message": "Strategy uploaded and validated successfully",
# #                 "strategy_summary": strategy_summary,
# #                 "file_name": file.filename
# #             }
# #         finally:
# #             # تنظيف الملف المؤقت
# #             Path(tmp_path).unlink(missing_ok=True)
        
# #     except json.JSONDecodeError as e:
# #         raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
# #     except yaml.YAMLError as e:
# #         raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))

# # @router.get("/list")
# # async def list_loaded_strategies_api(
# #     active_only: bool = Query(False, description="عرض الإستراتيجيات النشطة فقط")
# # ):
# #     """
# #     سرد جميع الإستراتيجيات المحملة في الذاكرة
    
# #     - **active_only**: عرض الإستراتيجيات النشطة فقط
# #     """
# #     strategies = get_loaded_strategies()
    
# #     if active_only:
# #         strategies = [s for s in strategies if s.get("is_active", True)]
    
# #     return {
# #         "count": len(strategies),
# #         "strategies": strategies
# #     }

# # @router.put("/update/{strategy_name}")
# # async def update_strategy_api(
# #     strategy_name: str,
# #     updates: Dict[str, Any] = Body(...)
# # ):
# #     """
# #     تحديث إستراتيجية محملة
    
# #     - **strategy_name**: اسم الإستراتيجية
# #     - **updates**: التحديثات المطلوبة
# #     """
# #     engine = update_strategy(strategy_name, updates)
    
# #     if not engine:
# #         raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
# #     return {
# #         "success": True,
# #         "message": f"Strategy '{strategy_name}' updated successfully",
# #         "strategy_summary": engine.get_strategy_summary()
# #     }

# # @router.post("/reload/{strategy_name}")
# # async def reload_strategy_api(strategy_name: str):
# #     """
# #     إعادة تحميل إستراتيجية من الملف
    
# #     - **strategy_name**: اسم الإستراتيجية
# #     """
# #     engine = reload_strategy(strategy_name)
    
# #     if not engine:
# #         raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
# #     return {
# #         "success": True,
# #         "message": f"Strategy '{strategy_name}' reloaded successfully",
# #         "strategy_summary": engine.get_strategy_summary()
# #     }

# # @router.get("/examples/{example_name}")
# # async def get_strategy_example(example_name: str):
# #     """
# #     الحصول على مثال إستراتيجية جاهزة
    
# #     - **example_name**: اسم المثال (rsi_basic, macd_advanced, trend_following)
# #     """
# #     examples = {
# #         "rsi_basic": {
# #             "name": "RSI Basic Strategy",
# #             "description": "استراتيجية RSI بسيطة للدخول عند التشبع بالبيع والخروج عند التشبع بالشراء",
# #             "indicators": ["rsi"],
# #             "complexity": "beginner",
# #             "timeframe": "1h"
# #         },
# #         "macd_advanced": {
# #             "name": "MACD Advanced Strategy",
# #             "description": "استراتيجية MACD متقدمة مع تأكيد من RSI ومتوسطات متحركة",
# #             "indicators": ["macd", "rsi", "ema"],
# #             "complexity": "intermediate",
# #             "timeframe": "4h"
# #         },
# #         "trend_following": {
# #             "name": "Trend Following Strategy",
# #             "description": "استراتيجية تتبع الاتجاه باستخدام متوسطات متحركة متعددة",
# #             "indicators": ["sma", "ema", "atr"],
# #             "complexity": "advanced",
# #             "timeframe": "1d"
# #         }
# #     }
    
# #     if example_name not in examples:
# #         raise HTTPException(status_code=404, detail="Example not found")
    
# #     # استيراد المثال المطلوب
# #     try:
# #         if example_name == "rsi_basic":
# #             from app.services.strategy.strategys.rsi_strategy import get_rsi_strategy
# #             strategy_config = get_rsi_strategy()
# #         elif example_name == "macd_advanced":
# #             from app.services.strategy.strategys.macd_strategy import get_macd_strategy
# #             strategy_config = get_macd_strategy()
# #         else:
# #             # يمكن إضافة المزيد من الأمثلة هنا
# #             raise HTTPException(status_code=404, detail="Example implementation not found")
        
# #         return {
# #             "example_info": examples[example_name],
# #             "strategy_config": strategy_config
# #         }
        
# #     except ImportError as e:
# #         raise HTTPException(status_code=500, detail=f"Could not load example: {str(e)}")
    









# # #     # app/routers/strategies.py
# # # from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile, Query, status
# # # from typing import List, Dict, Any, Optional
# # # import json
# # # import tempfile
# # # from pathlib import Path
# # # from sqlalchemy.ext.asyncio import AsyncSession
# # # import yaml
# # # import asyncio
# # # from datetime import datetime, timedelta

# # # from app.database import get_db
# # # from app.services.data_service import DataService
# # # from app.services.strategy import (
# # #     run_strategy,
# # #     validate_strategy_config,
# # #     save_strategy,
# # #     load_strategy_from_file,
# # #     get_loaded_strategies,
# # #     get_strategy_examples,
# # #     get_strategy_example_config,
# # #     get_strategy_by_hash,
# # #     unload_strategy
# # # )

# # # router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])

# # # @router.post("/run", summary="تشغيل إستراتيجية على بيانات السوق")
# # # async def run_strategy_on_data(
# # #     symbol: str,
# # #     timeframe: str = Query("1h", description="الإطار الزمني للبيانات"),
# # #     market: str = Query("crypto", description="نوع السوق (crypto/stocks)"),
# # #     strategy_config: Dict[str, Any] = Body(...),
# # #     days: int = Query(30, description="عدد الأيام التاريخية", ge=1, le=3650),
# # #     live_mode: bool = Query(False, description="وضع التشغيل الحي"),
# # #     include_indicators: bool = Query(False, description="تضمين بيانات المؤشرات"),
# # #     db: AsyncSession = Depends(get_db)
# # # ):
# # #     """
# # #     تشغيل إستراتيجية على بيانات السوق
    
# # #     - **symbol**: رمز السهم أو العملة
# # #     - **timeframe**: الإطار الزمني
# # #     - **market**: نوع السوق
# # #     - **strategy_config**: تكوين الإستراتيجية
# # #     - **days**: عدد الأيام التاريخية
# # #     - **live_mode**: وضع التشغيل الحي (لآخر نقطة بيانات فقط)
# # #     - **include_indicators**: تضمين بيانات المؤشرات في النتيجة
# # #     """
# # #     try:
# # #         data_service = DataService(db)
        
# # #         # الحصول على البيانات
# # #         print(f"📥 Fetching data for {symbol} ({market}) - {timeframe} - {days} days")
        
# # #         dataframe = await data_service.get_historical(
# # #             symbol=symbol,
# # #             timeframe=timeframe,
# # #             market=market,
# # #             days=days
# # #         )
        
# # #         if dataframe.empty:
# # #             raise HTTPException(
# # #                 status_code=status.HTTP_404_NOT_FOUND,
# # #                 detail=f"No data available for {symbol} in {market}"
# # #             )
        
# # #         print(f"✅ Data retrieved: {len(dataframe)} rows")
        
# # #         # تشغيل الإستراتيجية
# # #         print(f"🚀 Running strategy: {strategy_config.get('name', 'Unknown')}")
        
# # #         result = await run_strategy(
# # #             data=dataframe,
# # #             strategy_config=strategy_config,
# # #             symbol=symbol,
# # #             live_mode=live_mode,
# # #             use_cache=True
# # #         )
        
# # #         # تحضير الاستجابة
# # #         response = {
# # #             "success": True,
# # #             "symbol": symbol,
# # #             "market": market,
# # #             "timeframe": timeframe,
# # #             "days": days,
# # #             "strategy_name": strategy_config.get("name"),
# # #             "execution_time": datetime.utcnow().isoformat(),
# # #             "data_info": {
# # #                 "rows": len(dataframe),
# # #                 "start_date": dataframe.index[0].isoformat() if len(dataframe) > 0 else None,
# # #                 "end_date": dataframe.index[-1].isoformat() if len(dataframe) > 0 else None
# # #             },
# # #             "signals": [
# # #                 {
# # #                     "timestamp": s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
# # #                     "action": s.action,
# # #                     "price": s.price,
# # #                     "reason": s.reason,
# # #                     "rule_name": s.rule_name,
# # #                     "strength": s.strength,
# # #                     "metadata": s.metadata or {}
# # #                 }
# # #                 for s in result.signals
# # #             ],
# # #             "filtered_signals": [
# # #                 {
# # #                     "timestamp": s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
# # #                     "action": s.action,
# # #                     "price": s.price,
# # #                     "reason": s.reason,
# # #                     "rule_name": s.rule_name,
# # #                     "strength": s.strength
# # #                 }
# # #                 for s in result.filtered_signals
# # #             ],
# # #             "metrics": result.metrics,
# # #             "summary": {
# # #                 "total_signals": len(result.signals),
# # #                 "filtered_signals": len(result.filtered_signals),
# # #                 "entry_signals": len([s for s in result.filtered_signals if s.action in ['buy', 'sell']]),
# # #                 "exit_signals": len([s for s in result.filtered_signals if s.action == 'close'])
# # #             }
# # #         }
        
# # #         # إضافة بيانات المؤشرات إذا طلب
# # #         if include_indicators and hasattr(result, 'indicators'):
# # #             response["indicators"] = result.indicators
        
# # #         print(f"✅ Strategy completed: {len(result.filtered_signals)} signals generated")
        
# # #         return response
        
# # #     except HTTPException:
# # #         raise
# # #     except Exception as e:
# # #         print(f"❌ Error running strategy: {e}")
# # #         raise HTTPException(
# # #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # #             detail=f"Error running strategy: {str(e)}"
# # #         )

# # # @router.post("/validate", summary="التحقق من صحة تكوين الإستراتيجية")
# # # async def validate_strategy_config_api(
# # #     strategy_config: Dict[str, Any] = Body(...)
# # # ):
# # #     """
# # #     التحقق من صحة تكوين الإستراتيجية
    
# # #     - **strategy_config**: تكوين الإستراتيجية المراد التحقق منها
# # #     """
# # #     validation_result = validate_strategy_config(strategy_config)
    
# # #     return validation_result

# # # @router.post("/save", summary="حفظ إستراتيجية إلى ملف")
# # # async def save_strategy_api(
# # #     strategy_config: Dict[str, Any] = Body(...),
# # #     file_name: Optional[str] = Query(None, description="اسم الملف (اختياري)")
# # # ):
# # #     """
# # #     حفظ إستراتيجية إلى ملف على القرص
    
# # #     - **strategy_config**: تكوين الإستراتيجية
# # #     - **file_name**: اسم الملف (اختياري)
# # #     """
# # #     try:
# # #         result = await save_strategy(strategy_config, file_name)
        
# # #         if not result["success"]:
# # #             raise HTTPException(
# # #                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # #                 detail=result.get("error", "Unknown error")
# # #             )
        
# # #         return {
# # #             "success": True,
# # #             "message": "Strategy saved successfully",
# # #             "details": result
# # #         }
        
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # #             detail=str(e)
# # #         )

# # # @router.post("/upload", summary="رفع ملف إستراتيجية")
# # # async def upload_strategy_file(
# # #     file: UploadFile = File(...)
# # # ):
# # #     """
# # #     رفع ملف إستراتيجية وتحليله
    
# # #     - **file**: ملف الإستراتيجية (JSON أو YAML)
# # #     """
# # #     if not file.filename:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_400_BAD_REQUEST,
# # #             detail="No file uploaded"
# # #         )
    
# # #     # التحقق من امتداد الملف
# # #     file_ext = Path(file.filename).suffix.lower()
# # #     if file_ext not in ['.json', '.yaml', '.yml']:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_400_BAD_REQUEST,
# # #             detail="Unsupported file format. Use JSON or YAML"
# # #         )
    
# # #     try:
# # #         # قراءة المحتوى
# # #         content = await file.read()
        
# # #         # تحليل المحتوى
# # #         if file_ext == '.json':
# # #             strategy_config = json.loads(content.decode('utf-8'))
# # #         else:
# # #             strategy_config = yaml.safe_load(content.decode('utf-8'))
        
# # #         # التحقق من الصحة
# # #         validation_result = validate_strategy_config(strategy_config)
        
# # #         if not validation_result["valid"]:
# # #             raise HTTPException(
# # #                 status_code=status.HTTP_400_BAD_REQUEST,
# # #                 detail=f"Invalid strategy configuration: {validation_result['errors']}"
# # #             )
        
# # #         # حفظ الملف المؤقت
# # #         with tempfile.NamedTemporaryFile(mode='w', suffix=file_ext, delete=False) as tmp:
# # #             tmp.write(content.decode('utf-8'))
# # #             tmp_path = tmp.name
        
# # #         try:
# # #             # تحميل الإستراتيجية
# # #             load_result = await load_strategy_from_file(tmp_path, load_to_memory=True)
            
# # #             if not load_result["success"]:
# # #                 raise HTTPException(
# # #                     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # #                     detail=load_result.get("error", "Failed to load strategy")
# # #                 )
            
# # #             return {
# # #                 "success": True,
# # #                 "message": "Strategy uploaded and validated successfully",
# # #                 "strategy_info": {
# # #                     "name": strategy_config.get("name"),
# # #                     "description": strategy_config.get("description"),
# # #                     "engine_hash": load_result.get("engine_hash"),
# # #                     "indicators_count": len(strategy_config.get("indicators", [])),
# # #                     "entry_rules_count": len(strategy_config.get("entry_rules", []))
# # #                 },
# # #                 "file_info": {
# # #                     "original_name": file.filename,
# # #                     "size_bytes": len(content)
# # #                 }
# # #             }
            
# # #         finally:
# # #             # تنظيف الملف المؤقت
# # #             Path(tmp_path).unlink(missing_ok=True)
        
# # #     except json.JSONDecodeError as e:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_400_BAD_REQUEST,
# # #             detail=f"Invalid JSON format: {str(e)}"
# # #         )
# # #     except yaml.YAMLError as e:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_400_BAD_REQUEST,
# # #             detail=f"Invalid YAML format: {str(e)}"
# # #         )
# # #     except HTTPException:
# # #         raise
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # #             detail=f"Error processing file: {str(e)}"
# # #         )

# # # @router.get("/list", summary="قائمة الإستراتيجيات المحملة")
# # # async def list_loaded_strategies_api(
# # #     include_details: bool = Query(False, description="تضمين التفاصيل الكاملة")
# # # ):
# # #     """
# # #     سرد جميع الإستراتيجيات المحملة في الذاكرة
    
# # #     - **include_details**: تضمين التفاصيل الكاملة للإستراتيجيات
# # #     """
# # #     strategies = get_loaded_strategies()
    
# # #     if include_details:
# # #         detailed_strategies = []
# # #         for strategy in strategies:
# # #             engine = get_strategy_by_hash(strategy["hash"])
# # #             if engine:
# # #                 detailed_strategies.append({
# # #                     **strategy,
# # #                     "full_config": engine.config.dict() if hasattr(engine.config, 'dict') else None,
# # #                     "indicators": [ind.dict() for ind in engine.config.indicators] if hasattr(engine.config, 'indicators') else []
# # #                 })
# # #             else:
# # #                 detailed_strategies.append(strategy)
        
# # #         return {
# # #             "count": len(detailed_strategies),
# # #             "strategies": detailed_strategies
# # #         }
    
# # #     return {
# # #         "count": len(strategies),
# # #         "strategies": strategies
# # #     }

# # # @router.delete("/unload/{strategy_hash}", summary="إزالة إستراتيجية من الذاكرة")
# # # async def unload_strategy_api(strategy_hash: str):
# # #     """
# # #     إزالة إستراتيجية محملة من الذاكرة
    
# # #     - **strategy_hash**: الـ hash الخاص بالإستراتيجية
# # #     """
# # #     success = unload_strategy(strategy_hash)
    
# # #     if not success:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_404_NOT_FOUND,
# # #             detail=f"Strategy with hash '{strategy_hash}' not found"
# # #         )
    
# # #     return {
# # #         "success": True,
# # #         "message": f"Strategy '{strategy_hash}' unloaded successfully"
# # #     }

# # # @router.get("/examples", summary="الحصول على أمثلة الإستراتيجيات")
# # # async def get_strategy_examples_api():
# # #     """
# # #     الحصول على قائمة بأمثلة الإستراتيجيات الجاهزة
# # #     """
# # #     examples = await get_strategy_examples()
    
# # #     return {
# # #         "success": True,
# # #         **examples
# # #     }

# # # @router.get("/examples/{example_name}", summary="الحصول على تكوين إستراتيجية مثال")
# # # async def get_strategy_example_config_api(example_name: str):
# # #     """
# # #     الحصول على تكوين إستراتيجية مثال جاهزة
    
# # #     - **example_name**: اسم المثال (rsi_basic, macd_advanced, trend_following, mean_reversion)
# # #     """
# # #     try:
# # #         config = await get_strategy_example_config(example_name)
        
# # #         return {
# # #             "success": True,
# # #             "example_name": example_name,
# # #             "strategy_config": config
# # #         }
        
# # #     except ValueError as e:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_404_NOT_FOUND,
# # #             detail=str(e)
# # #         )
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # #             detail=str(e)
# # #         )

# # # @router.get("/test", summary="اختبار تشغيل إستراتيجية بسيطة")
# # # async def test_strategy_api(
# # #     symbol: str = Query("AAPL", description="رمز الأصل للاختبار"),
# # #     days: int = Query(30, description="عدد الأيام"),
# # #     db: AsyncSession = Depends(get_db)
# # # ):
# # #     """
# # #     اختبار تشغيل إستراتيجية بسيطة (RSI) على بيانات حقيقية
# # #     """
# # #     try:
# # #         # استخدام إستراتيجية RSI مثال
# # #         from app.services.strategy.strategys.rsi_strategy import get_rsi_strategy
# # #         strategy_config = get_rsi_strategy()
        
# # #         # تشغيل الإستراتيجية
# # #         data_service = DataService(db)
        
# # #         dataframe = await data_service.get_historical(
# # #             symbol=symbol,
# # #             timeframe="1d",
# # #             market="stocks",
# # #             days=days
# # #         )
        
# # #         if dataframe.empty:
# # #             raise HTTPException(
# # #                 status_code=status.HTTP_404_NOT_FOUND,
# # #                 detail=f"No data available for {symbol}"
# # #             )
        
# # #         result = await run_strategy(
# # #             data=dataframe,
# # #             strategy_config=strategy_config,
# # #             symbol=symbol,
# # #             live_mode=False
# # #         )
        
# # #         # إعداد تقرير الاختبار
# # #         test_report = {
# # #             "test_date": datetime.utcnow().isoformat(),
# # #             "symbol": symbol,
# # #             "strategy": strategy_config["name"],
# # #             "data_points": len(dataframe),
# # #             "signals_generated": len(result.signals),
# # #             "signals_filtered": len(result.filtered_signals),
# # #             "metrics": result.metrics,
# # #             "sample_signals": [
# # #                 {
# # #                     "timestamp": s.timestamp.isoformat() if hasattr(s.timestamp, 'isoformat') else str(s.timestamp),
# # #                     "action": s.action,
# # #                     "price": s.price,
# # #                     "rule": s.rule_name
# # #                 }
# # #                 for s in result.filtered_signals[:5]  # أول 5 إشارات فقط
# # #             ]
# # #         }
        
# # #         return {
# # #             "success": True,
# # #             "message": "Strategy test completed successfully",
# # #             "report": test_report
# # #         }
        
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# # #             detail=f"Test failed: {str(e)}"
# # #         )


# # app/routers/strategies.py
# from datetime import datetime
# import uuid
# from fastapi import (
#     APIRouter, Depends, HTTPException, Body, File,
#     Request, UploadFile, Query, Path as PathParam
# )
# from typing import List, Dict, Any, Optional
# import json
# import tempfile
# from pathlib import Path
# from sqlalchemy.ext.asyncio import AsyncSession
# import yaml

# from app.database import get_db
# from app.services.data_service import DataService

# # ✅ استيراد الدوال المحدثة من الـ strategy package
# from app.services.strategy import (
#     run_strategy,
#     validate_strategy_config,
#     save_strategy,
#     load_strategy_from_file,
#     update_strategy,
#     get_loaded_strategies,
#     reload_strategy,
#     get_strategy,
#     unload_strategy
# )

# import logging

# # إنشاء logger خاص لهذا الملف
# logger = logging.getLogger(__name__)

# router = APIRouter(tags=["strategies"])

# @router.post("/run")
# async def run_strategy_on_data(
#     symbol: str,
#     timeframe: str,
#     market: str = "crypto",
#     strategy_config: Dict[str, Any] = Body(...),
#     days: int = 30,
#     live_mode: bool = False,
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     تشغيل إستراتيجية على بيانات السوق
#     """
#     request_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
#     logger.info(f"[{request_id}] بدء طلب run_strategy_on_data", extra={
#         "symbol": symbol,
#         "timeframe": timeframe,
#         "market": market,
#         "days": days,
#         "live_mode": live_mode,
#         "strategy_name": strategy_config.get("name")
#     })
    
#     data_service = DataService(db)
    
#     try:
#         # الحصول على البيانات
#         logger.info(f"[{request_id}] جلب البيانات التاريخية...")
#         dataframe = await data_service.get_historical(
#             symbol=symbol,
#             timeframe=timeframe,
#             market=market,
#             days=days
#         )
        
#         if dataframe.empty:
#             logger.error(f"[{request_id}] لا توجد بيانات متاحة")
#             raise HTTPException(status_code=404, detail="No data available")
        
#         # تشغيل الإستراتيجية
#         logger.info(f"[{request_id}] تشغيل الإستراتيجية...")
#         result = await run_strategy(dataframe, strategy_config, live_mode)
        
#         # تسجيل النتيجة النهائية
#         logger.info(f"[{request_id}] اكتمل الطلب بنجاح", extra={
#             "total_signals": len(result.signals),
#             "filtered_signals": len(result.filtered_signals)
#         })
        
#         # تحويل النتيجة إلى قاموس
#         return {
#             "success": True,
#             "signals": [
#                 {
#                     "timestamp": s.timestamp.isoformat(),
#                     "action": s.action,
#                     "price": s.price,
#                     "reason": s.reason,
#                     "rule_name": s.rule_name,
#                     "strength": s.strength,
#                     "metadata": s.metadata
#                 }
#                 for s in result.signals
#             ],
#             "filtered_signals": [
#                 {
#                     "timestamp": s.timestamp.isoformat(),
#                     "action": s.action,
#                     "price": s.price,
#                     "reason": s.reason,
#                     "rule_name": s.rule_name,
#                     "strength": s.strength
#                 }
#                 for s in result.filtered_signals
#             ],
#             "metrics": result.metrics,
#             "strategy_summary": {
#                 "name": strategy_config.get("name"),
#                 "total_indicators": len(strategy_config.get("indicators", [])),
#                 "total_entry_rules": len(strategy_config.get("entry_rules", [])),
#                 "total_exit_rules": len(strategy_config.get("exit_rules", []))
#             }
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"[{request_id}] خطأ غير متوقع: {str(e)}", exc_info=True)
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/validate")
# async def validate_strategy_config_api(
#     strategy_config: Dict[str, Any] = Body(...)
# ):
#     """
#     التحقق من صحة تكوين الإستراتيجية
#     """
#     validation_result = validate_strategy_config(strategy_config)
    
#     if validation_result["valid"]:
#         return {
#             "valid": True,
#             "message": "Strategy configuration is valid",
#             "config_summary": {
#                 "name": validation_result["config"]["name"],
#                 "version": validation_result["config"]["version"],
#                 "indicators_count": len(validation_result["config"]["indicators"]),
#                 "entry_rules_count": len(validation_result["config"]["entry_rules"]),
#                 "exit_rules_count": len(validation_result["config"]["exit_rules"])
#             }
#         }
#     else:
#         return {
#             "valid": False,
#             "message": "Strategy configuration is invalid",
#             "errors": validation_result["errors"]
#         }

# @router.post("/save")
# async def save_strategy_api(
#     strategy_config: Dict[str, Any] = Body(...),
#     file_name: Optional[str] = None
# ):
#     """
#     حفظ إستراتيجية إلى ملف على القرص
#     """
#     try:
#         file_path = save_strategy(strategy_config, file_name)
        
#         return {
#             "success": True,
#             "message": "Strategy saved successfully",
#             "file_path": str(file_path),
#             "strategy_name": strategy_config.get("name")
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/upload")
# async def upload_strategy_file(
#     file: UploadFile = File(...)
# ):
#     """
#     رفع ملف إستراتيجية وتحليله
#     """
#     if not file.filename:
#         raise HTTPException(status_code=400, detail="No file uploaded")
    
#     file_ext = Path(file.filename).suffix.lower()
#     if file_ext not in ['.json', '.yaml', '.yml']:
#         raise HTTPException(status_code=400, detail="Unsupported file format")
    
#     content = await file.read()
    
#     try:
#         if file_ext == '.json':
#             strategy_config = json.loads(content.decode('utf-8'))
#         else:
#             strategy_config = yaml.safe_load(content.decode('utf-8'))
        
#         # التحقق من الصحة
#         validation_result = validate_strategy_config(strategy_config)
        
#         if not validation_result["valid"]:
#             raise HTTPException(status_code=400, detail=f"Invalid configuration: {validation_result['errors']}")
        
#         # تحميل الإستراتيجية
#         with tempfile.NamedTemporaryFile(mode='w', suffix=file_ext, delete=False) as tmp:
#             tmp.write(content.decode('utf-8'))
#             tmp_path = tmp.name
        
#         try:
#             engine = load_strategy_from_file(tmp_path)
#             strategy_summary = engine.get_strategy_summary()
            
#             return {
#                 "success": True,
#                 "message": "Strategy uploaded and loaded successfully",
#                 "strategy_summary": strategy_summary,
#                 "file_name": file.filename
#             }
#         finally:
#             Path(tmp_path).unlink(missing_ok=True)
        
#     except json.JSONDecodeError as e:
#         raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
#     except yaml.YAMLError as e:
#         raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/list")
# async def list_loaded_strategies_api(
#     active_only: bool = Query(False, description="عرض الإستراتيجيات النشطة فقط"),
#     detailed: bool = Query(True, description="عرض التفاصيل الكاملة")
# ):
#     """
#     سرد جميع الإستراتيجيات المحملة في الذاكرة
    
#     - **active_only**: عرض الإستراتيجيات النشطة فقط
#     - **detailed**: عرض التفاصيل الكاملة (المؤشرات، القواعد، إدارة المخاطر)
#     """
#     try:
#         strategies = get_loaded_strategies()
        
#         # تصفية الإستراتيجيات النشطة فقط
#         if active_only:
#             strategies = [s for s in strategies if s.get("is_active", True)]
        
#         # تسجيل استدعاء النقطة
#         logger.info(f"تم جلب {len(strategies)} استراتيجية محملة", extra={
#             "active_only": active_only,
#             "detailed": detailed
#         })
        
#         return {
#             "success": True,
#             "count": len(strategies),
#             "timestamp": datetime.now().isoformat(),
#             "strategies": strategies
#         }
        
#     except Exception as e:
#         logger.error(f"خطأ في جلب الاستراتيجيات: {str(e)}", exc_info=True)
#         raise HTTPException(status_code=500, detail=str(e))

# # ✅ إضافة نقطة نهاية جديدة للحصول على استراتيجية واحدة
# @router.get("/{strategy_name}")
# async def get_strategy_api(
#     strategy_name: str = PathParam(..., description="اسم الإستراتيجية")
# ):
#     """
#     الحصول على استراتيجية محددة محملة في الذاكرة
    
#     - **strategy_name**: اسم الإستراتيجية
#     """
#     engine = get_strategy(strategy_name)
    
#     if not engine:
#         raise HTTPException(
#             status_code=404,
#             detail=f"Strategy '{strategy_name}' not found in memory. Load it first using /upload or /save"
#         )
    
#     strategy_data = engine.get_strategy_summary()
    
#     logger.info(f"تم جلب استراتيجية '{strategy_name}' بنجاح")
    
#     return {
#         "success": True,
#         "strategy": strategy_data
#     }

# # ✅ إضافة نقطة نهاية لحذف استراتيجية من الذاكرة
# @router.delete("/{strategy_name}")
# async def delete_strategy_api(
#     strategy_name: str = PathParam(..., description="اسم الإستراتيجية")
# ):
#     """
#     إلغاء تحميل استراتيجية من الذاكرة
    
#     - **strategy_name**: اسم الإستراتيجية
#     """
#     try:
#         success = unload_strategy(strategy_name)
        
#         if not success:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"Strategy '{strategy_name}' not found in memory"
#             )
        
#         logger.info(f"تم إلغاء تحميل استراتيجية '{strategy_name}' من الذاكرة")
        
#         return {
#             "success": True,
#             "message": f"Strategy '{strategy_name}' unloaded from memory"
#         }
        
#     except Exception as e:
#         logger.error(f"خطأ في إلغاء تحميل الاستراتيجية: {str(e)}", exc_info=True)
#         raise HTTPException(status_code=500, detail=str(e))

# @router.put("/update/{strategy_name}")
# async def update_strategy_api(
#     strategy_name: str = PathParam(..., description="اسم الإستراتيجية"),
#     updates: Dict[str, Any] = Body(...)
# ):
#     """
#     تحديث إستراتيجية محملة
    
#     - **strategy_name**: اسم الإستراتيجية
#     - **updates**: التحديثات المطلوبة
#     """
#     engine = update_strategy(strategy_name, updates)
    
#     if not engine:
#         raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
#     return {
#         "success": True,
#         "message": f"Strategy '{strategy_name}' updated successfully",
#         "strategy_summary": engine.get_strategy_summary()
#     }

# @router.post("/reload/{strategy_name}")
# async def reload_strategy_api(
#     strategy_name: str = PathParam(..., description="اسم الإستراتيجية")
# ):
#     """
#     إعادة تحميل إستراتيجية من الملف
    
#     - **strategy_name**: اسم الإستراتيجية
#     """
#     engine = reload_strategy(strategy_name)
    
#     if not engine:
#         raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
#     return {
#         "success": True,
#         "message": f"Strategy '{strategy_name}' reloaded successfully",
#         "strategy_summary": engine.get_strategy_summary()
#     }

# @router.get("/examples/{example_name}")
# async def get_strategy_example(
#     example_name: str = PathParam(..., description="اسم المثال (rsi_basic, macd_advanced, trend_following)")
# ):
#     """
#     الحصول على مثال إستراتيجية جاهزة
#     """
#     examples = {
#         "rsi_basic": {
#             "name": "RSI Basic Strategy",
#             "description": "استراتيجية RSI بسيطة",
#             "indicators": ["rsi"],
#             "complexity": "beginner",
#             "timeframe": "1h"
#         },
#         "macd_advanced": {
#             "name": "MACD Advanced Strategy",
#             "description": "استراتيجية MACD متقدمة",
#             "indicators": ["macd", "rsi", "ema"],
#             "complexity": "intermediate",
#             "timeframe": "4h"
#         },
#         "trend_following": {
#             "name": "Trend Following Strategy",
#             "description": "استراتيجية تتبع الاتجاه",
#             "indicators": ["sma", "ema", "atr"],
#             "complexity": "advanced",
#             "timeframe": "1d"
#         }
#     }
    
#     if example_name not in examples:
#         raise HTTPException(status_code=404, detail="Example not found")
    
#     try:
#         if example_name == "rsi_basic":
#             from app.services.strategy.strategys.rsi_strategy import get_rsi_strategy
#             strategy_config = get_rsi_strategy()
#         elif example_name == "macd_advanced":
#             from app.services.strategy.strategys.macd_strategy import get_macd_strategy
#             strategy_config = get_macd_strategy()
#         elif example_name == "trend_following":
#             from app.services.strategy.strategys.trend_strategy import get_trend_strategy
#             strategy_config = get_trend_strategy()
#         else:
#             raise HTTPException(status_code=404, detail="Example implementation not found")
        
#         return {
#             "success": True,
#             "example_info": examples[example_name],
#             "strategy_config": strategy_config
#         }
        
#     except ImportError as e:
#         raise HTTPException(status_code=500, detail=f"Could not load example: {str(e)}")