"""
نظام المؤشرات المركزي مع دعم الحساب عند إغلاق الشمعة
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

from app.services.indicators import apply_indicators

logger = logging.getLogger(__name__)

class IndicatorManager:
    """مدير المؤشرات المركزية"""
    
    def __init__(self):
        self.indicators_cache: Dict[str, Dict] = {}
        self.calculation_lock = asyncio.Lock()
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        logger.info("✅ IndicatorManager initialized")
    
    async def calculate_indicators(
        self,
        candles: List[Dict],
        indicators_config: List[Dict[str, Any]],
        symbol: str,
        timeframe: str,
        on_close: bool = True  
    ) -> Dict[str, Any]:
        """
        حساب المؤشرات مع التحسينات للأداء
        
        Args:
            candles: قائمة الشموع
            indicators_config: تكوينات المؤشرات
            symbol: الرمز
            timeframe: الإطار الزمني
            on_close: إذا كان True، يحسب فقط عند إغلاق الشمعة
        """
        if not candles or not indicators_config:
            return {}
        
        # مفتاح التخزين المؤقت
        cache_key = f"{symbol}_{timeframe}_{hash(str(indicators_config))}"
        
        async with self.calculation_lock:
            if on_close: # نستخدم الكاش فقط عند إغلاق الشمعة (البيانات ثابتة)
                if cache_key in self.indicators_cache:
                    cached_data = self.indicators_cache[cache_key]
                    if len(candles) == cached_data.get("candle_count"):
                        return cached_data["results"]
            # 2. تحضير البيانات (تأكد أن الشمعة الحية مدمجة في القائمة الممررة)
            df = self._prepare_dataframe(candles)
            
            # حساب المؤشرات في thread منفصل
            loop = asyncio.get_event_loop()
            try:
                results = await loop.run_in_executor(
                    self.thread_pool,
                    self._calculate_sync,
                    df,
                    indicators_config,
                    on_close
                )


                if on_close:
                    self.indicators_cache[cache_key] = {
                        "results": results,
                        "timestamp": datetime.utcnow().isoformat(),
                        "candle_count": len(candles)
                    }
                


                

                
                return results
                
            except Exception as e:
                logger.error(f"❌ Error calculating indicators for {symbol}: {e}")
                return {}
    
    def _prepare_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """تحضير DataFrame من الشموع"""
        if not candles:
            return pd.DataFrame()
        
        data = []
        for candle in candles:
            data.append({
                "time": pd.Timestamp(candle["time"], unit='ms'),
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle["volume"])
            })
        
        df = pd.DataFrame(data)
        df.set_index("time", inplace=True)
        return df



    def _calculate_sync(
        self,
        df: pd.DataFrame,
        indicators_config: List[Dict[str, Any]],
        on_close: bool
    ) -> Dict[str, Any]:
        """حساب المؤشرات بشكل متزامن"""
        try:
            # تطبيق المؤشرات
            results = apply_indicators(
                dataframe=df,
                indicators_config=indicators_config,
                use_cache=True,
                parallel=True
            )
            
            # تنظيف النتائج
            cleaned_results = {}
            for name, result in results.items():
                try:
                    # 1. إذا كانت النتيجة قائمة (مثل bollinger_bands)
                    if isinstance(result, list):
                        # معالجة كل عنصر في القائمة
                        for i, item in enumerate(result):
                            if isinstance(item, dict):
                                # مؤشرات متعددة مثل bollinger_bands
                                sub_name = f"{name}_{i}"
                                data_list = item.get("values", {}).get("data", [])
                                
                                final_values = []
                                if data_list:
                                    if not on_close:
                                        # للبث الحي: آخر قيمة فقط
                                        last_val = data_list[-1] if data_list else None
                                        if last_val is not None:
                                            final_values = [last_val]
                                    else:
                                        # لإغلاق الشمعة: كل القيم
                                        final_values = data_list
                                
                                cleaned_results[sub_name] = {
                                    "name": sub_name,
                                    "values": final_values,
                                    "signals": item.get("signals"),
                                    "metadata": item.get("metadata", {})
                                }
                    
                    # 2. إذا كانت النتيجة قاموساً
                    elif isinstance(result, dict):
                        # إذا كان لدينا values مباشرة
                        if "values" in result:
                            data_list = result.get("values", {}).get("data", [])
                            
                            final_values = []
                            if data_list:
                                if not on_close:
                                    last_val = data_list[-1] if data_list else None
                                    if last_val is not None:
                                        final_values = [last_val]
                                else:
                                    final_values = data_list
                            
                            cleaned_results[name] = {
                                "name": name,
                                "values": final_values,
                                "signals": result.get("signals"),
                                "metadata": result.get("metadata", {})
                            }
                        # إذا كان dict يحتوي على مؤشرات فرعية (مثل upper, middle, lower)
                        else:
                            for key, sub_result in result.items():
                                if isinstance(sub_result, dict) and "values" in sub_result:
                                    sub_name = f"{name}_{key}"
                                    data_list = sub_result.get("values", {}).get("data", [])
                                    
                                    final_values = []
                                    if data_list:
                                        if not on_close:
                                            last_val = data_list[-1] if data_list else None
                                            if last_val is not None:
                                                final_values = [last_val]
                                        else:
                                            final_values = data_list
                                    
                                    cleaned_results[sub_name] = {
                                        "name": sub_name,
                                        "values": final_values,
                                        "signals": sub_result.get("signals"),
                                        "metadata": sub_result.get("metadata", {})
                                    }
                    
                    # 3. إذا كانت النتيجة Series مباشرة
                    elif isinstance(result, pd.Series):
                        values = result.tolist()
                        final_values = [values[-1]] if not on_close and values else values
                        
                        cleaned_results[name] = {
                            "name": name,
                            "values": final_values,
                            "signals": None,
                            "metadata": {}
                        }
                        
                except Exception as e:
                    logger.error(f"❌ Error processing indicator {name}: {e}")
                    continue
            
            logger.info(f"✅ Cleaned results for {len(indicators_config)} indicators: {list(cleaned_results.keys())}")
            return cleaned_results
            
        except Exception as e:
            logger.error(f"❌ Error in sync calculation: {e}")
            return {}



    # def _calculate_sync(
    #     self,
    #     df: pd.DataFrame,
    #     indicators_config: List[Dict[str, Any]],
    #     on_close: bool
    # ) -> Dict[str, Any]:
    #     """حساب المؤشرات بشكل متزامن"""
    #     try:


    #         # تطبيق المؤشرات
    #         results = apply_indicators(
    #             dataframe=df,
    #             indicators_config=indicators_config,
    #             use_cache=True,
    #             parallel=True
    #         )
            
    #         # تنظيف النتائج
    #         cleaned_results = {}
    #         for name, result in results.items():
    #             # استخراج آخر قيمة فقط للبث الحي، أو المصفوفة كاملة للإغلاق
    #             if isinstance(result, dict):
    #                 data_list = result.get("values", {}).get("data", [])
                    
    #                 # إذا كان بثاً حياً، نأخذ آخر قيمة فقط لتقليل حجم الـ JSON
    #                 final_values = [data_list[-1]] if not on_close and data_list else data_list
                    
    #                 cleaned_results[name] = {
    #                     "name": name,
    #                     "values": final_values,
    #                     "signals": result.get("signals"), # سنعالج الإشارات بنفس الطريقة
    #                     "metadata": result.get("metadata", {})
    #                 }
            
    #         return cleaned_results
            
    #     except Exception as e:
    #         logger.error(f"❌ Error in sync calculation: {e}")
    #         return {}
    
    def _is_last_candle_complete(self, df: pd.DataFrame) -> bool:
        """التحقق إذا كانت آخر شمعة كاملة (مغلقة)"""
        if len(df) < 2:
            return True
        
        # التحقق من الفرق الزمني بين الشمعتين الأخيرتين
        last_time = df.index[-1]
        prev_time = df.index[-2]
        
        # إذا كان الفرق الزمني طبيعي (إطار زمني ثابت)
        time_diff = (last_time - prev_time).total_seconds() / 60
        
        # نعتبرها كاملة إذا مر أكثر من 90% من الوقت
        expected_diff = self._get_timeframe_minutes(df)
        return time_diff >= expected_diff * 0.9
    
    def _get_timeframe_minutes(self, df: pd.DataFrame) -> int:
        """استخراج الإطار الزمني من البيانات"""
        if len(df) < 2:
            return 1
        
        diff = (df.index[1] - df.index[0]).total_seconds() / 60
        return int(diff)
    
    def _get_previous_indicators(
        self,
        df: pd.DataFrame,
        indicators_config: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """الحصول على نتائج المؤشرات السابقة"""
        # استخدام البيانات بدون آخر شمعة
        if len(df) > 1:
            df_previous = df.iloc[:-1]
        else:
            df_previous = df
        
        results = apply_indicators(
            dataframe=df_previous,
            indicators_config=indicators_config,
            use_cache=True,
            parallel=True
        )
        
        # إضافة قيم NaN لآخر شمعة (غير مكتملة)
        for name in results.keys():
            if "values" in results[name] and isinstance(results[name]["values"], dict):
                results[name]["values"]["data"].append(np.nan)
        
        return results
    
    async def _clean_cache(self, max_size: int = 100):
        """تنظيف التخزين المؤقت"""
        if len(self.indicators_cache) > max_size:
            # إزالة أقدم العناصر
            items = sorted(
                self.indicators_cache.items(),
                key=lambda x: x[1]["time"]
            )
            to_remove = items[:len(items) - max_size]
            
            for key, _ in to_remove:
                del self.indicators_cache[key]
            
            logger.debug(f"🧹 Cleaned {len(to_remove)} cached items")









# app/core/indicators.py - إضافة دالة جديدة

    async def calculate_latest_indicators(
        candles: List[Dict],
        indicators_config: List[Dict],
        symbol: str,
        timeframe: str,
        previous_results: Optional[Dict] = None
    ) -> Dict:
        """
        حساب القيم الجديدة فقط للمؤشرات (بدلاً من كل القيم)
        """
        # حساب المؤشرات الكاملة
        full_results = await calculate_indicators(
            candles=candles,
            indicators_config=indicators_config,
            symbol=symbol,
            timeframe=timeframe,
            on_close=False
        )
        
        if not previous_results:
            return full_results
        
        # استخراج القيم الجديدة فقط
        latest_results = {}
        
        for indicator_name, indicator_data in full_results.items():
            latest_results[indicator_name] = {
                "name": indicator_name,
                "values": [],
                "signals": {"data": [], "index": [], "dtype": "int64"},
                "metadata": {}
            }
            
            # أخذ آخر قيمة من values
            if indicator_data.get("values"):
                latest_results[indicator_name]["values"] = [indicator_data["values"][-1]]
            
            # أخذ آخر إشارة
            if indicator_data.get("signals", {}).get("data"):
                signals = indicator_data["signals"]
                latest_results[indicator_name]["signals"] = {
                    "data": [signals["data"][-1]] if signals["data"] else [0],
                    "index": [signals["index"][-1]] if signals["index"] else [],
                    "dtype": "int64"
                }
            
            # أخذ آخر قيمة من كل metadata
            if indicator_data.get("metadata"):
                metadata = {}
                for key, value in indicator_data["metadata"].items():
                    if isinstance(value, list) and value:
                        metadata[key] = [value[-1]]
                    else:
                        metadata[key] = value
                latest_results[indicator_name]["metadata"] = metadata
        
        return latest_results

# المثيل العام
indicator_manager = IndicatorManager()