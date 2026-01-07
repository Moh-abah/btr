# trading_backend\app\services\indicators\__init__.py
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import math
from .base import IndicatorConfig, IndicatorResult, IndicatorType
from .registry import IndicatorFactory, IndicatorRegistry
from .calculator import IndicatorCalculator
from .pine_transpiler import PineScriptTranspiler


from .indicators import *
# إنشاء كائنات عامة
_calculator = IndicatorCalculator()
_transpiler = PineScriptTranspiler()






IndicatorRegistry.register(
    name="rsi",
    display_name="RSI",
    description="مؤشر القوة النسبية",
    category=IndicatorType.MOMENTUM
)(RSIIndicator)

IndicatorRegistry.register(
    name="ema",
    display_name="EMA",
    description="المتوسط المتحرك الأسي",
    category=IndicatorType.TREND
)(EMAIndicator)

IndicatorRegistry.register(
    name="sma",
    display_name="SMA",
    description="المتوسط المتحرك البسيط",
    category=IndicatorType.TREND
)(SMAIndicator)


IndicatorRegistry.register(
    name="sma_fast",
    display_name="sma_fast",
    description="المتوسط المتحرك البسيط",
    category=IndicatorType.TREND
)(SMAFastIndicator)



IndicatorRegistry.register(
    name="sma_slow",
    display_name="sma_slow",
    description="المتوسط المتحرك البسيط",
    category=IndicatorType.TREND
)(SMASlowIndicator)









IndicatorRegistry.register(
    name="macd",
    display_name="MACD",
    description="مؤشر التقارب والتباعد للمتوسطات المتحركة",
    category=IndicatorType.MOMENTUM
)(MACDIndicator)

IndicatorRegistry.register(
    name="bb",
    display_name="Bollinger Bands",
    description="أشرطة بولينجر",
    category=IndicatorType.VOLATILITY
)(BollingerBandsIndicator)

IndicatorRegistry.register(
    name="atr",
    display_name="ATR",
    description="متوسط المدى الحقيقي",
    category=IndicatorType.VOLATILITY
)(ATRIndicator)



def _clean_value(val: Any) -> Any:
    """
    تنظيف قيمة واحدة للتأكد من التوافق مع JSON
    """
    if val is None:
        return None
    
    # تحويل numpy types إلى python types
    if isinstance(val, (np.float32, np.float64)):
        val = float(val)
    elif isinstance(val, (np.int32, np.int64)):
        val = int(val)
    elif isinstance(val, np.ndarray):
        return [_clean_value(v) for v in val.tolist()]
    
    # التعامل مع float
    if isinstance(val, float):
        if math.isinf(val) or math.isnan(val):
            return None
        # تقييد النطاق ليكون ضمن حدود JSON
        if abs(val) > 1e308:
            return None
        # تقريب لتجنب مشاكل الفاصلة العائمة
        return round(val, 8)
    
    # التعامل مع pandas types
    if isinstance(val, pd.Series):
        return _clean_series(val)
    elif isinstance(val, pd.DataFrame):
        return _clean_dataframe(val)
    elif isinstance(val, pd.Timestamp):
        return val.isoformat()
    
    # التعامل مع المجموعات
    if isinstance(val, dict):
        return {k: _clean_value(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [_clean_value(v) for v in val]
    
    return val



def _clean_dataframe(df: pd.DataFrame) -> List[Dict]:
    """تنظيف DataFrame وتحويله إلى قواميس"""
    if df is None or df.empty:
        return []
    
    records = []
    for _, row in df.iterrows():
        record = {}
        for col in row.index:
            record[col] = _clean_value(row[col])
        records.append(record)
    return records



def _clean_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """تنظيف نتائج المؤشرات للتأكد من أنها JSON Serializable"""
    cleaned = {}
    
    for name, result in results.items():
        try:
            if isinstance(result, dict):
                # مؤشر بخطوط متعددة (مثل bollinger_bands)
                if 'upper' in result and 'middle' in result and 'lower' in result:
                    cleaned[name] = [
                        _clean_series(result['upper'], f"{name}_upper"),
                        _clean_series(result['middle'], f"{name}_middle"),
                        _clean_series(result['lower'], f"{name}_lower"),
                    ]
                else:
                    cleaned[name] = result
            elif isinstance(result, list):
                cleaned[name] = [_clean_item(item) for item in result]
            elif isinstance(result, pd.Series):
                cleaned[name] = _clean_series(result, name)
            else:
                cleaned[name] = result
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف نتيجة المؤشر {name}: {e}")
            cleaned[name] = {"error": str(e)}
    
    return cleaned









def _clean_series(series: pd.Series, name: str) -> Dict[str, Any]:
    """تنظيف pandas Series"""
    return {
        "name": name,
        "values": {
            "data": series.tolist(),
            "index": series.index.tolist(),
            "dtype": str(series.dtype)
        },
        "signals": None,
        "metadata": {}
    }

def _clean_item(item):
    """تنظيف عنصر فردي"""
    if isinstance(item, pd.Series):
        return _clean_series(item, "unknown")
    elif isinstance(item, dict):
        return item
    else:
        return item

def apply_indicators(
    dataframe: pd.DataFrame,
    indicators_config: List[Dict[str, Any]],
    use_cache: bool = True,
    return_raw: bool = False,
    parallel: bool = True
    
) -> Dict[str, Any]:
    """
    الوظيفة المركزية لتطبيق المؤشرات على DataFrame
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # تنظيف DataFrame المدخل أولاً
    if dataframe is None or dataframe.empty:
        logger.error("❌ DataFrame فارغ أو None")
        return {}
    
    # نسخة من DataFrame للعمل عليها
    df = dataframe.copy()
    
    # استبدال قيم inf و nan في DataFrame
    df = df.replace([np.inf, -np.inf], np.nan)
    
    # ملء القيم NaN باستخدام forward fill ثم backward fill
    df = df.ffill().bfill()
    
    # تحويل التكوين إلى dicts إذا كان IndicatorConfig
    config_dicts = []
    for config in indicators_config:
        if isinstance(config, dict):
            config_dicts.append(config)
        elif hasattr(config, 'dict'):
            config_dicts.append(config.dict())
        else:
            config_dicts.append(vars(config))
    
    logger.info(f"📊 تطبيق {len(config_dicts)} مؤشر على DataFrame بطول {len(df)}")
    logger.info(f"📄 تكوينات المؤشرات: {[c.get('name', 'unknown') for c in config_dicts]}")

    try:
        results = _calculator.apply_indicators(
            dataframe=df,
            indicators_config=config_dicts,
            use_cache=use_cache,
            parallel=parallel
        )


        if return_raw:
                return results     
        
             
        logger.info(f"✅ تم حساب {len(results)} مؤشر")
        
        # تسجيل تفاصيل المؤشرات المحسوبة
        for name, result in results.items():
            # معالجة خاصة لمؤشر bollinger_bands
            if name == "bollinger_bands":
                if isinstance(result, dict) and 'upper' in result and 'middle' in result and 'lower' in result:
                    # تحويل إلى قائمة من 3 dicts (upper, middle, lower)
                    bands_list = []
                    for band_name in ['upper', 'middle', 'lower']:
                        band_series = result[band_name]
                        if isinstance(band_series, pd.Series):
                            bands_list.append({
                                "name": f"bollinger_{band_name}",
                                "values": {"data": band_series.tolist(), "index": band_series.index.tolist(), "dtype": str(band_series.dtype)},
                                "signals": None,
                                "metadata": {"band": band_name}
                            })
                    results[name] = bands_list
                    logger.info(f"   📊 {name}: تم تحويله إلى 3 خطوط")
                else:
                    logger.warning(f"   ⚠️ {name}: ليس بالشكل المتوقع")
            
            elif isinstance(result, pd.Series):
                non_nan_count = result.notna().sum()
                logger.info(f"   📈 {name}: طول {len(result)}، قيم غير NaN: {non_nan_count}")
                if non_nan_count == 0:
                    logger.warning(f"   ⚠️ المؤشر '{name}' كل قيمه NaN!")
            elif isinstance(result, dict):
                logger.info(f"   📊 {name}: dict ب {len(result)} مفتاح")
            else:
                logger.info(f"   ℹ️ {name}: {type(result).__name__}")
                
    except Exception as e:
        logger.exception(f"❌ خطأ في apply_indicators: {e}")
        results = {}
        
    if return_raw:
        return results      
    # تنظيف النتائج للتأكد من التوافق مع JSON
    cleaned_results = _clean_results(results)
    
    return cleaned_results


def get_available_indicators(
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    الحصول على قائمة بالمؤشرات المتاحة
    
    Args:
        category: تصنيف المؤشر (اختياري)
        
    Returns:
        List[Dict]: قائمة بالمؤشرات المتاحة
    """
    indicators = IndicatorRegistry.list_indicators(category)
    
    # تنظيف النتائج
    cleaned_indicators = []
    for indicator in indicators:
        cleaned = {}
        for key, value in indicator.items():
            cleaned[key] = _clean_value(value)
        cleaned_indicators.append(cleaned)
    
    return cleaned_indicators

def transpile_pine_script(pine_code: str) -> str:
    """
    تحويل كود Pine Script إلى Python
    
    Args:
        pine_code: كود Pine Script
        
    Returns:
        str: كود Python مكافئ
    """
    return _transpiler.transpile_to_python(pine_code)

def create_indicator_from_pine(
    pine_code: str, 
    indicator_name: str = None
):
    """
    إنشاء مؤشر من كود Pine Script
    
    Args:
        pine_code: كود Pine Script
        indicator_name: اسم المؤشر
        
    Returns:
        Type[BaseIndicator]: فئة المؤشر المنشأة
    """
    return _transpiler.create_indicator_from_pine(pine_code, indicator_name)

def calculate_trading_signals(
    dataframe: pd.DataFrame,
    indicator_configs: List[Dict[str, Any]],
    signal_threshold: float = 0.5,
    parallel=True
) -> Dict[str, Any]:
    """
    حساب إشارات التداول من مجموعة مؤشرات
    
    Args:
        dataframe: بيانات السوق
        indicator_configs: تكوينات المؤشرات
        signal_threshold: عتبة الإشارة
        
    Returns:
        Dict: إشارات التداول والتحليل
    """
    # تنظيف DataFrame المدخل
    if dataframe is None or dataframe.empty:
        return {}
    
    dataframe = dataframe.replace([np.inf, -np.inf], np.nan)
    dataframe = dataframe.ffill().bfill()
    
    # تحويل التكوين إلى dicts
    config_dicts = []
    for config in indicator_configs:
        if isinstance(config, dict):
            config_dicts.append(config)
        elif hasattr(config, 'dict'):
            config_dicts.append(config.dict())
        else:
            config_dicts.append(vars(config))
    
    # حساب الإشارات
    signals = _calculator.calculate_trading_signals(
        dataframe=dataframe,
        indicator_configs=config_dicts,
        signal_threshold=signal_threshold
    )
    
    # تنظيف إشارات التداول
    cleaned_signals = _clean_results(signals)
    
    return cleaned_signals

# تصدير الكلاسات الرئيسية
__all__ = [
    "IndicatorConfig",
    "IndicatorResult",
    "BaseIndicator",
    "IndicatorRegistry",
    "IndicatorCalculator",
    "PineScriptTranspiler",
    "apply_indicators",
    "get_available_indicators",
    "transpile_pine_script",
    "create_indicator_from_pine",
    "calculate_trading_signals",

    "IndicatorType",
    "Timeframe",
    "IndicatorFactory",

    "RSIIndicator",
    "MovingAverageIndicator",
    "MACDIndicator",
    "BollingerBandsIndicator",
    "ATRIndicator"

]