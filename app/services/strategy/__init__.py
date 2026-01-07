# app\services\strategy\__init__.py
from typing import Dict, List, Any, Optional
import pandas as pd
from .schemas import StrategyConfig
from .core import StrategyEngine, StrategyResult, TradeSignal
from .loader import StrategyLoader
from .conditions import ConditionEvaluator

# إنشاء كائنات عامة
_strategy_loader = StrategyLoader()

def run_strategy(
    data: pd.DataFrame,
    strategy_config: Dict[str, Any],
    live_mode: bool = False,
    use_cache: bool = True
) -> StrategyResult:
    """
    الوظيفة المركزية لتشغيل إستراتيجية على البيانات
    
    Args:
        data: DataFrame يحتوي على بيانات السوق
        strategy_config: تكوين الإستراتيجية (قاموس)
        live_mode: وضع التشغيل الحي (للبيانات المستمرة)
        use_cache: استخدام الكاش (افتراضي: True)
        
    Returns:
        StrategyResult: نتيجة تشغيل الإستراتيجية
        
    Example:
        >>> strategy_config = {
        ...     "name": "RSI Strategy",
        ...     "indicators": [{"name": "rsi", "params": {"period": 14}}],
        ...     "entry_rules": [...],
        ...     "exit_rules": [...]
        ... }
        >>> result = run_strategy(data, strategy_config)
    """
    # تحميل الإستراتيجية
    engine = _strategy_loader.load_strategy_from_dict(strategy_config)
    
    # تشغيل الإستراتيجية
    result = engine.run_strategy(data, live_mode, use_cache)
    
    return result

def validate_strategy_config(strategy_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    التحقق من صحة تكوين الإستراتيجية
    
    Args:
        strategy_config: تكوين الإستراتيجية
        
    Returns:
        Dict: نتيجة التحقق
    """
    try:
        config = StrategyConfig(**strategy_config)
        
        return {
            "valid": True,
            "config": config.dict(),
            "errors": []
        }
    except Exception as e:
        return {
            "valid": False,
            "config": None,
            "errors": [str(e)]
        }

def save_strategy(
    strategy_config: Dict[str, Any],
    file_name: Optional[str] = None
) -> str:
    """
    حفظ إستراتيجية إلى ملف
    
    Args:
        strategy_config: تكوين الإستراتيجية
        file_name: اسم الملف (اختياري)
        
    Returns:
        str: مسار الملف المحفوظ
    """
    config = StrategyConfig(**strategy_config)
    file_path = _strategy_loader.save_strategy_to_file(config, file_name)
    
    return str(file_path)

def load_strategy_from_file(file_path: str) -> StrategyEngine:
    """
    تحميل إستراتيجية من ملف
    
    Args:
        file_path: مسار الملف
        
    Returns:
        StrategyEngine: محرك الإستراتيجية المحملة
    """
    return _strategy_loader.load_strategy_from_file(file_path)

def update_strategy(
    strategy_name: str,
    updates: Dict[str, Any]
) -> Optional[StrategyEngine]:
    """
    تحديث إستراتيجية محملة
    
    Args:
        strategy_name: اسم الإستراتيجية
        updates: التحديثات المطلوبة
        
    Returns:
        StrategyEngine: محرك الإستراتيجية المحدثة
    """
    return _strategy_loader.update_strategy(strategy_name, updates)

def get_loaded_strategies() -> List[Dict[str, Any]]:
    """
    الحصول على قائمة بالإستراتيجيات المحملة
    
    Returns:
        List[Dict]: قائمة بالإستراتيجيات
    """
    return _strategy_loader.list_loaded_strategies()

def reload_strategy(strategy_name: str) -> Optional[StrategyEngine]:
    """
    إعادة تحميل إستراتيجية من الملف
    
    Args:
        strategy_name: اسم الإستراتيجية
        
    Returns:
        StrategyEngine: محرك الإستراتيجية المُعاد تحميله
    """
    return _strategy_loader.reload_strategy(strategy_name)

# تصدير الكلاسات الرئيسية
__all__ = [
    "StrategyConfig",
    "StrategyEngine",
    "StrategyResult",
    "TradeSignal",
    "StrategyLoader",
    "ConditionEvaluator",
    "run_strategy",
    "validate_strategy_config",
    "save_strategy",
    "load_strategy_from_file",
    "update_strategy",
    "get_loaded_strategies",
    "reload_strategy"
]







# # app/services/strategy/__init__.py
# """
# وحدة إدارة الإستراتيجيات الرئيسية

# هذه الوحدة توفر:
# 1. تحميل وتخزين الإستراتيجيات
# 2. تشغيل الإستراتيجيات على البيانات
# 3. إدارة حالات الإستراتيجيات
# 4. التكامل مع باقي النظام
# """

# import asyncio
# from typing import Dict, List, Any, Optional, Union
# import pandas as pd
# import numpy as np
# from datetime import datetime
# import json
# import yaml
# from pathlib import Path
# import hashlib
# import logging

# from .schemas import StrategyConfig, TradeSignal, StrategyResult
# from .core import StrategyEngine
# from .conditions import ConditionEvaluator
# from .loader import StrategyLoader

# logger = logging.getLogger(__name__)

# # إنشاء كائنات عامة
# _strategy_loader = StrategyLoader()

# # كاش للإستراتيجيات المحملة
# _loaded_strategies: Dict[str, StrategyEngine] = {}

# def get_strategy_loader() -> StrategyLoader:
#     """الحصول على محمل الإستراتيجيات"""
#     return _strategy_loader

# async def run_strategy(
#     data: pd.DataFrame,
#     strategy_config: Dict[str, Any],
#     symbol: str = None,
#     live_mode: bool = False,
#     use_cache: bool = True
# ) -> StrategyResult:
#     """
#     تشغيل إستراتيجية على البيانات بشكل غير متزامن
    
#     Args:
#         data: DataFrame يحتوي على بيانات السوق
#         strategy_config: تكوين الإستراتيجية
#         symbol: رمز الأصل (اختياري)
#         live_mode: وضع التشغيل الحي
#         use_cache: استخدام الكاش
        
#     Returns:
#         StrategyResult: نتيجة تشغيل الإستراتيجية
#     """
#     try:
#         # إنشاء hash فريد للإستراتيجية
#         strategy_hash = hashlib.md5(
#             json.dumps(strategy_config, sort_keys=True).encode()
#         ).hexdigest()[:12]
        
#         # التحقق إذا كانت الإستراتيجية محملة مسبقاً
#         if strategy_hash in _loaded_strategies:
#             engine = _loaded_strategies[strategy_hash]
#         else:
#             # تحميل الإستراتيجية
#             config = StrategyConfig(**strategy_config)
#             engine = StrategyEngine(config)
#             _loaded_strategies[strategy_hash] = engine
        
#         # تشغيل الإستراتيجية
#         result = await engine.run_strategy(
#             data=data,
#             symbol=symbol,
#             live_mode=live_mode,
#             use_cache=use_cache
#         )
        
#         return result
        
#     except Exception as e:
#         logger.error(f"Error running strategy: {e}")
#         raise

# def validate_strategy_config(strategy_config: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     التحقق من صحة تكوين الإستراتيجية
    
#     Args:
#         strategy_config: تكوين الإستراتيجية
        
#     Returns:
#         Dict: نتيجة التحقق
#     """
#     try:
#         config = StrategyConfig(**strategy_config)
        
#         return {
#             "valid": True,
#             "config": config.dict(),
#             "errors": [],
#             "warnings": []
#         }
        
#     except Exception as e:
#         return {
#             "valid": False,
#             "config": None,
#             "errors": [str(e)],
#             "warnings": []
#         }

# async def save_strategy(
#     strategy_config: Dict[str, Any],
#     file_name: Optional[str] = None,
#     strategy_dir: str = "strategies"
# ) -> Dict[str, Any]:
#     """
#     حفظ إستراتيجية إلى ملف
    
#     Args:
#         strategy_config: تكوين الإستراتيجية
#         file_name: اسم الملف (اختياري)
#         strategy_dir: مجلد حفظ الإستراتيجيات
        
#     Returns:
#         Dict: معلومات الحفظ
#     """
#     try:
#         # إنشاء مجلد الإستراتيجيات إذا لم يكن موجوداً
#         strategy_path = Path(strategy_dir)
#         strategy_path.mkdir(exist_ok=True)
        
#         if file_name is None:
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             strategy_name = strategy_config.get("name", "strategy").replace(" ", "_").lower()
#             file_name = f"{strategy_name}_{timestamp}.json"
        
#         # إضافة وقت الإنشاء
#         strategy_config["created_at"] = datetime.now().isoformat()
        
#         # حفظ كـ JSON
#         file_path = strategy_path / file_name
        
#         with open(file_path, "w", encoding="utf-8") as f:
#             json.dump(strategy_config, f, indent=2, ensure_ascii=False)
        
#         logger.info(f"Strategy saved to: {file_path}")
        
#         return {
#             "success": True,
#             "file_path": str(file_path),
#             "file_name": file_name,
#             "strategy_name": strategy_config.get("name"),
#             "size_bytes": file_path.stat().st_size
#         }
        
#     except Exception as e:
#         logger.error(f"Error saving strategy: {e}")
#         return {
#             "success": False,
#             "error": str(e)
#         }

# async def load_strategy_from_file(
#     file_path: Union[str, Path],
#     load_to_memory: bool = True
# ) -> Dict[str, Any]:
#     """
#     تحميل إستراتيجية من ملف
    
#     Args:
#         file_path: مسار الملف
#         load_to_memory: تحميل إلى الذاكرة للاستخدام الفوري
        
#     Returns:
#         Dict: معلومات الإستراتيجية المحملة
#     """
#     try:
#         file_path = Path(file_path)
        
#         if not file_path.exists():
#             raise FileNotFoundError(f"Strategy file not found: {file_path}")
        
#         # قراءة الملف
#         if file_path.suffix.lower() == ".json":
#             with open(file_path, "r", encoding="utf-8") as f:
#                 strategy_config = json.load(f)
#         elif file_path.suffix.lower() in [".yaml", ".yml"]:
#             with open(file_path, "r", encoding="utf-8") as f:
#                 strategy_config = yaml.safe_load(f)
#         else:
#             raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
#         # التحقق من الصحة
#         validation = validate_strategy_config(strategy_config)
#         if not validation["valid"]:
#             raise ValueError(f"Invalid strategy config: {validation['errors']}")
        
#         # إذا طلب تحميلها إلى الذاكرة
#         if load_to_memory:
#             config = StrategyConfig(**strategy_config)
#             engine = StrategyEngine(config)
            
#             # تخزين في الكاش
#             strategy_hash = hashlib.md5(
#                 json.dumps(strategy_config, sort_keys=True).encode()
#             ).hexdigest()[:12]
            
#             _loaded_strategies[strategy_hash] = engine
            
#             return {
#                 "success": True,
#                 "strategy_config": strategy_config,
#                 "engine_hash": strategy_hash,
#                 "loaded": True,
#                 "file_info": {
#                     "path": str(file_path),
#                     "name": file_path.name,
#                     "size": file_path.stat().st_size,
#                     "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
#                 }
#             }
#         else:
#             return {
#                 "success": True,
#                 "strategy_config": strategy_config,
#                 "loaded": False,
#                 "file_info": {
#                     "path": str(file_path),
#                     "name": file_path.name
#                 }
#             }
        
#     except Exception as e:
#         logger.error(f"Error loading strategy from file: {e}")
#         return {
#             "success": False,
#             "error": str(e)
#         }

# def get_loaded_strategies() -> List[Dict[str, Any]]:
#     """الحصول على قائمة بالإستراتيجيات المحملة"""
#     strategies = []
    
#     for strategy_hash, engine in _loaded_strategies.items():
#         strategies.append({
#             "hash": strategy_hash,
#             "name": engine.config.name,
#             "description": engine.config.description,
#             "version": engine.config.version,
#             "indicators_count": len(engine.config.indicators),
#             "entry_rules_count": len(engine.config.entry_rules),
#             "created_at": engine.config.created_at.isoformat() if engine.config.created_at else None
#         })
    
#     return strategies

# def get_strategy_by_hash(strategy_hash: str) -> Optional[StrategyEngine]:
#     """الحصول على إستراتيجية بواسطة الـ hash"""
#     return _loaded_strategies.get(strategy_hash)

# def unload_strategy(strategy_hash: str) -> bool:
#     """إزالة إستراتيجية من الذاكرة"""
#     if strategy_hash in _loaded_strategies:
#         del _loaded_strategies[strategy_hash]
#         return True
#     return False

# async def get_strategy_examples() -> Dict[str, Any]:
#     """الحصول على أمثلة للإستراتيجيات الجاهزة"""
    
#     examples = {
#         "rsi_basic": {
#             "name": "RSI Basic Strategy",
#             "description": "استراتيجية RSI بسيطة للدخول عند التشبع بالبيع والخروج عند التشبع بالشراء",
#             "complexity": "beginner",
#             "indicators": ["rsi"],
#             "timeframes": ["1h", "4h", "1d"],
#             "markets": ["crypto", "stocks"]
#         },
#         "macd_advanced": {
#             "name": "MACD Advanced Strategy",
#             "description": "استراتيجية MACD متقدمة مع تأكيد من RSI ومتوسطات متحركة",
#             "complexity": "intermediate",
#             "indicators": ["macd", "rsi", "sma"],
#             "timeframes": ["4h", "1d"],
#             "markets": ["crypto", "stocks"]
#         },
#         "trend_following": {
#             "name": "Trend Following Strategy",
#             "description": "استراتيجية تتبع الاتجاه باستخدام متوسطات متحركة متعددة",
#             "complexity": "advanced",
#             "indicators": ["ema", "atr", "adx"],
#             "timeframes": ["1d", "1w"],
#             "markets": ["crypto", "stocks"]
#         },
#         "mean_reversion": {
#             "name": "Mean Reversion Strategy",
#             "description": "استراتيجية الارتداد المتوسط مع بولينجر باندز",
#             "complexity": "intermediate",
#             "indicators": ["bollinger_bands", "rsi", "stochastic"],
#             "timeframes": ["1h", "4h"],
#             "markets": ["crypto", "stocks"]
#         }
#     }
    
#     return {
#         "count": len(examples),
#         "examples": examples
#     }

# async def get_strategy_example_config(example_name: str) -> Dict[str, Any]:
#     """الحصول على تكوين إستراتيجية مثال"""
    
#     if example_name == "rsi_basic":
#         from .strategys.rsi_strategy import get_rsi_strategy
#         return get_rsi_strategy()
    
#     elif example_name == "macd_advanced":
#         from .strategys.macd_strategy import get_macd_strategy
#         return get_macd_strategy()
    
#     elif example_name == "trend_following":
#         from .strategys.trend_strategy import get_trend_strategy
#         return get_trend_strategy()
    
#     elif example_name == "mean_reversion":
#         from .strategys.mean_reversion_strategy import get_mean_reversion_strategy
#         return get_mean_reversion_strategy()
    
#     else:
#         raise ValueError(f"Unknown example: {example_name}")

# # تصدير الكلاسات والدوال الرئيسية
# __all__ = [
#     "StrategyConfig",
#     "TradeSignal",
#     "StrategyResult",
#     "StrategyEngine",
#     "ConditionEvaluator",
#     "StrategyLoader",
    
#     # الدوال الرئيسية
#     "run_strategy",
#     "validate_strategy_config",
#     "save_strategy",
#     "load_strategy_from_file",
#     "get_loaded_strategies",
#     "get_strategy_by_hash",
#     "unload_strategy",
#     "get_strategy_examples",
#     "get_strategy_example_config"
# ]