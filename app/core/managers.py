# \app\core\managers.py
"""
مدير الشارت المركزي مع دعم البث الحي والتحديثات
"""
import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from app.core.live_stream import live_stream_manager
from app.core.indicators import indicator_manager
from app.providers.binance_provider import BinanceProvider

logger = logging.getLogger(__name__)



class Timeframe(Enum):
    """الإطارات الزمنية المدعومة"""
    MIN1 = "1m"
    MIN5 = "5m"
    MIN15 = "15m"
    MIN30 = "30m"
    HOUR1 = "1h"
    HOUR4 = "4h"
    DAY1 = "1d"

@dataclass
class ChartState:
    """حالة الشارت"""
    symbol: str
    timeframe: str
    candles: List[Dict] = field(default_factory=list)
    live_candle: Optional[Dict] = None
    indicators: List[Dict] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.utcnow)
    subscribers: Set[str] = field(default_factory=set)  # Connection IDs
    on_close_callbacks: List[Callable] = field(default_factory=list)

    price_handler: Optional[Callable] = None 
    indicators_results: Dict = field(default_factory=dict)




class ChartManager:
    """مدير الشارت المركزي"""
    
    def __init__(self):
        self.charts: Dict[str, ChartState] = {}  # key = "symbol_timeframe"
        self.candle_locks: Dict[str, asyncio.Lock] = {}
        self.initialized = False
        self.crypto_provider = BinanceProvider()
        self.ws_manager: Optional["WebSocketManager"] = None
      
    def set_ws_manager(self, ws_manager: "WebSocketManager"):
        """ربط WebSocketManager بعد الإنشاء لتجنب circular import"""
        self.ws_manager = ws_manager        
    
    async def initialize(self):
        """تهيئة النظام"""
        if not self.initialized:
            await live_stream_manager.start()
            self.initialized = True
            logger.info("✅ ChartManager initialized")


    def get_chart_key(self, symbol: str, timeframe: Any) -> str:
        """تحويل الـ timeframe إلى نص مهما كان نوعه لضمان دقة المفتاح"""
        if isinstance(timeframe, Timeframe):
            tf_str = timeframe.value
        elif hasattr(timeframe, 'value'): # حماية إضافية لأي Enum آخر
            tf_str = timeframe.value
        else:
            tf_str = str(timeframe)
        
        # التأكد من إزالة أي زوائد مثل "Timeframe.MIN1" وتحويلها لـ "1m"
        if "Timeframe." in tf_str:
            # هذه حالة احترازية إذا مرر النص كـ "Timeframe.MIN1"
            mapping = { "Timeframe.MIN1": "1m", "Timeframe.MIN5": "5m" } # وهكذا..
            tf_str = mapping.get(tf_str, tf_str)

        return f"{symbol}_{tf_str}"
    
    async def get_or_create_chart(
        self,
        symbol: str,
        timeframe: str,
        market: str = "crypto",
        num_last_candles: int = 500,  # آخر 100 شمعة مغلقة
        initial_candles: Optional[List[Dict]] = None
    ) -> ChartState:
        """الحصول على شارت أو إنشاء جديد مع آخر N شموع مغلقة فقط قبل الشمعة الحية."""
        key = self.get_chart_key(symbol, timeframe)
        tf_str = timeframe.value if hasattr(timeframe, 'value') else str(timeframe)

        if key not in self.charts:
            chart = ChartState(symbol=symbol, timeframe=tf_str, candles=initial_candles or [])
            self.charts[key] = chart
            self.candle_locks[key] = asyncio.Lock()

            handler = self._create_price_handler(symbol, tf_str)
            chart.price_handler = handler

            if market == "crypto" and not initial_candles:
                try:
                    # 1️⃣ جلب آخر N شمعة مغلقة فقط
                    df_last_closed = await self.crypto_provider.get_last_closed_candles(
                        symbol=symbol,
                        timeframe=tf_str,
                        limit=num_last_candles
                    )

                    if not df_last_closed.empty:
                        # ترتيب الشموع من الأقدم إلى الأحدث
                        df_last_closed = df_last_closed.sort_values('time')
                        chart.candles = df_last_closed.to_dict('records')

                        # لا نقوم بإنشاء أي شمعة حية مسبقة
                        # البث الحي سيحدث الشمعة الحالية مباشرة عند وصول البيانات الحقيقية

                except Exception as e:
                    logger.error(f"❌ Failed to load last {num_last_candles} closed candles for {key}: {e}")

            # 2️⃣ الاشتراك في البث الحي مباشرة
            await live_stream_manager.subscribe(symbol, handler)
            logger.info(f"📊 Chart {key} created and subscribed to live stream.")

        return self.charts[key]


    def _calculate_lookback(self, timeframe: str, count: int) -> timedelta:
        """دالة مساعدة لحساب الفارق الزمني المطلوب لكل إطار"""
        unit = timeframe[-1] # m, h, d
        try:
            value = int(timeframe[:-1])
        except ValueError:
            value = 1

        if unit == 'm':
            return timedelta(minutes=value * count)
        elif unit == 'h':
            return timedelta(hours=value * count)
        elif unit == 'd':
            return timedelta(days=value * count)
        else:
            return timedelta(days=count) # افتراضي

    def _create_price_handler(self, symbol: str, timeframe: str) -> Callable:
        """إنشاء معالج للبيانات الحية"""
        async def handle_price_update(price_data: Dict):
            key = self.get_chart_key(symbol, timeframe)
            
            if key not in self.charts:
                logger.warning(f"💡 Received price update but chart {key} not ready yet")
                return
            
            chart = self.charts[key]
            
            async with self.candle_locks[key]:
                await self._update_chart_candle(chart, price_data)
        
        return handle_price_update
    
# مع اضافه اخر تحديث للموشر 
    async def _update_chart_candle(self, chart: ChartState, price_data: Dict):
        """تحديث شمعة الشارت"""
        now_ms = self._now_ms()
        tf_min = self._timeframe_to_minutes(chart.timeframe)
        tf_ms = tf_min * 60 * 1000
        candle_time = self._align_time(now_ms, tf_min)
        
        # إذا لم يكن هناك شمعة حية، نبدأ واحدة جديدة
        if chart.live_candle is None:
            chart.live_candle = {
                "time": candle_time,
                "open": price_data["price"],
                "high": price_data["price"],
                "low": price_data["price"],
                "close": price_data["price"],
                "volume": price_data["volume"]
            }
        else:
            # تحديث الشمعة الحالية
            candle = chart.live_candle

            if now_ms - candle["time"] >= tf_ms:
                # إغلاق الشمعة الحالية
                await self._close_current_candle(chart, candle["time"] + tf_ms, price_data)
                new_candle_time = candle["time"] + tf_ms
                # بدء شمعة جديدة
                chart.live_candle = {
                    "time": new_candle_time,
                    "open": price_data["price"],
                    "high": price_data["price"],
                    "low": price_data["price"],
                    "close": price_data["price"],
                    "volume": price_data["volume"]
                }
            else:
                # تحديث الشمعة الحالية
                candle["high"] = max(candle["high"], price_data["price"])
                candle["low"] = min(candle["low"], price_data["price"])
                candle["close"] = price_data["price"]
                candle["volume"] += price_data["volume"]

        # ✅ التعديل هنا: نأخذ القيم الجديدة فقط للمؤشرات
        latest_indicators = {}
        if chart.indicators:
            # ندمج الشموع المغلقة مع الشمعة الحية الحالية للحساب
            temp_candles = chart.candles + [chart.live_candle]
            full_indicators = await indicator_manager.calculate_indicators(
                candles=temp_candles[-100:],
                indicators_config=chart.indicators,
                symbol=chart.symbol,
                timeframe=chart.timeframe,
                on_close=False
            )
            
            # استخراج القيم الجديدة فقط
            latest_indicators = self._extract_latest_indicator_values(full_indicators)

        chart.last_update = datetime.utcnow()
        key = self.get_chart_key(chart.symbol, chart.timeframe)
        message = {
            "type": "price_update",
            "symbol": chart.symbol,
            "timeframe": chart.timeframe,
            "live_candle": chart.live_candle,
            "indicators": latest_indicators,  # ✅ إرسال القيم الجديدة فقط
            "time": now_ms
        }
        await self.ws_manager.broadcast(key, message)



    async def _close_current_candle(
        self,
        chart: ChartState,
        close_time_ms: int,
        price_data: Dict
    ):
        if chart.live_candle is None:return

        chart.live_candle["close"] = price_data["price"]
        chart.live_candle["time"] = close_time_ms

        chart.candles.append(chart.live_candle.copy())

        if len(chart.candles) > 500:chart.candles = chart.candles[-500:]

        # --- تحديث المؤشرات رسمياً عند الإغلاق ---
        await self._calculate_indicators_on_close(chart)


        # ✅ التعديل هنا: نأخذ القيم الجديدة فقط للإرسال
        latest_results = self._extract_latest_indicator_values(chart.indicators_results)
        # بث رسالة إغلاق الشمعة
        key = self.get_chart_key(chart.symbol, chart.timeframe)
        await self.ws_manager.broadcast(key, {
            "type": "candle_close",
            "symbol": chart.symbol,
            "timeframe": chart.timeframe,
            "candle": chart.live_candle,
            "indicators": latest_results,
            # "indicators": chart.indicators_results, # النتائج النهائية المحسوبة
            "time": self._now_ms()
        })
        chart.live_candle = None





    async def _calculate_indicators_on_close(self, chart: ChartState):
        """حساب المؤشرات وتحديث النتائج في حالة الشارت"""
        if not chart.indicators:
            logger.info(f"⚠️ No indicators configured for {chart.symbol}, skipping calculation.")
            return

        if not chart.candles:
            logger.warning(f"⚠️ No candles available for {chart.symbol} to calculate indicators.")
            return

        try:
            logger.info(f"🔄 Calculating {len(chart.indicators)} indicators for {chart.symbol}...")
            
            # نأخذ آخر 100 شمعة للحساب
            calculation_candles = chart.candles[-100:] 
            
            results = await indicator_manager.calculate_indicators(
                candles=calculation_candles,
                indicators_config=chart.indicators,
                symbol=chart.symbol,
                timeframe=chart.timeframe,
                on_close=True
            )
            
            chart.indicators_results = results
            logger.info(f"✅ Calculation successful! Results keys: {list(results.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Indicator calculation error: {e}", exc_info=True)



    async def add_indicator(
        self,
        symbol: str,
        timeframe: Any,
        indicator_config: Dict[str, Any]
    ) -> bool:
        """إضافة مؤشر وحسابه فوراً بناءً على التاريخ المتاح"""
        key = self.get_chart_key(symbol, timeframe)
        
        if key not in self.charts:
            logger.error(f"❌ Chart {key} not found.")
            return False
        
        chart = self.charts[key]
        indicator_name = indicator_config.get('name')

        # 1. التأكد من عدم التكرار وإضافة المؤشر للقائمة أولاً
        exists = any(ind.get('name') == indicator_name for ind in chart.indicators)
        if not exists:
            chart.indicators.append(indicator_config)
            logger.info(f"📌 Indicator {indicator_name} registered for {key}")

        # 2. الحساب الفوري إذا كانت الشموع جاهزة
        if chart.candles and len(chart.candles) > 0:
            try:
                logger.info(f"🔄 Calculating {indicator_name} on {len(chart.candles)} candles...")
                
                # نستخدم دالة الحساب الجماعي (تأكد أنها تعيد نتائج للمؤشر الجديد)
                results = await indicator_manager.calculate_indicators(
                    candles=chart.candles,
                    indicators_config=chart.indicators, # ستحسب الجميع بما فيهم الجديد
                    symbol=symbol,
                    timeframe=timeframe,
                    on_close=True 
                )
                
                if results:
                    chart.indicators_results.update(results)
                    logger.info(f"✅ {indicator_name} values calculated successfully.")
                    return True
            except Exception as e:
                logger.error(f"❌ Error calculating {indicator_name}: {e}")
                return False
        else:
            logger.warning(f"⏳ {indicator_name} added but candles not ready yet.")
            
        return True
   
        
    def add_on_close_callback(
        self,
        symbol: str,
        timeframe: str,
        callback: Callable
    ):
        """إضافة callback عند إغلاق الشمعة"""
        key = self.get_chart_key(symbol, timeframe)
        
        if key in self.charts:
            self.charts[key].on_close_callbacks.append(callback)
    
    async def get_chart_data(
        self,
        symbol: str,
        timeframe: str,
        include_live: bool = True
    ) -> Dict[str, Any]:
        """الحصول على بيانات الشارت"""
        key = self.get_chart_key(symbol, timeframe)
        
        if key not in self.charts:
            return {}
        
        chart = self.charts[key]
        
        # تجهيز البيانات
        candles = chart.candles.copy()
        if include_live and chart.live_candle:
            live_candle = chart.live_candle.copy()
            last_time = candles[-1]["time"] if candles else 0
            
            # ⬅️ تعديل وقت الشمعة الحية إذا كان يساوي أو أقل من آخر شمعة
            if live_candle["time"] <= last_time:
                # إذا كان إطارك بالميلي ثانية
                live_candle["time"] = last_time + 1
            
            candles.append(live_candle)
        
        return {
            "symbol": chart.symbol,
            "timeframe": chart.timeframe,
            "candles": candles[-500:], 
            "indicators": chart.indicators,
            "indicators_results": chart.indicators_results,
            "metadata": {
                "total_candles": len(candles),
                "last_update": int(chart.last_update.timestamp() * 1000),
                "subscribers": len(chart.subscribers)
            }
        }
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """تحويل timeframe إلى دقائق"""
        timeframe_map = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "4h": 240, "1d": 1440
        }
        return timeframe_map.get(timeframe, 1)
    
    async def cleanup(self, symbol: str, timeframe: str):
        """تنظيف الشارت"""
        key = self.get_chart_key(symbol, timeframe)
        
        if key in self.charts:
            chart = self.charts[key]
            # إلغاء الاشتراك من البث الحي
            if chart.price_handler:
                await live_stream_manager.unsubscribe(symbol, chart.price_handler)
            
            # حذف الشارت
            del self.charts[key]
            
            if key in self.candle_locks:
                del self.candle_locks[key]
            logger.info(f"🧹 Cleaned up chart: {key}")    
 




    def _now_ms(self) -> int:
        return int(datetime.utcnow().timestamp() * 1000)

    def _align_time(self, ts_ms: int, timeframe_min: int) -> int:
        tf_ms = timeframe_min * 60 * 1000
        return (ts_ms // tf_ms) * tf_ms


    def _extract_latest_indicator_values(self, full_indicators: Dict) -> Dict:
        """استخراج القيم الجديدة فقط من نتائج المؤشرات الكاملة"""
        latest_indicators = {}
        
        for indicator_name, indicator_data in full_indicators.items():
            latest_indicators[indicator_name] = {
                "name": indicator_name,
                "values": [],
                "signals": {"data": [], "index": [], "dtype": "int64"},
                "metadata": {}
            }
            
            # أخذ آخر قيمة من values
            if indicator_data.get("values") and len(indicator_data["values"]) > 0:
                latest_indicators[indicator_name]["values"] = [indicator_data["values"][-1]]
            
            # أخذ آخر إشارة
            if indicator_data.get("signals"):
                signals = indicator_data["signals"]
                if signals.get("data") and len(signals["data"]) > 0:
                    latest_indicators[indicator_name]["signals"]["data"] = [signals["data"][-1]]
                if signals.get("index") and len(signals["index"]) > 0:
                    latest_indicators[indicator_name]["signals"]["index"] = [signals["index"][-1]]
            
            # ✅ تعديل مهم: إرسال metadata كاملاً للمؤشرات المركبة مثل بولينجر
            if indicator_name == "bb" and indicator_data.get("metadata"):
                metadata = indicator_data["metadata"]
                latest_indicators[indicator_name]["metadata"] = {
                    "sma": [metadata.get("sma", [])[-1]] if metadata.get("sma") else [],
                    "upper_band": [metadata.get("upper_band", [])[-1]] if metadata.get("upper_band") else [],
                    "lower_band": [metadata.get("lower_band", [])[-1]] if metadata.get("lower_band") else [],
                    "band_width": [metadata.get("band_width", [])[-1]] if metadata.get("band_width") else [],
                    "period": metadata.get("period", 20),
                    "std": metadata.get("std", 2)
                }

            if indicator_name == "macd" and indicator_data.get("metadata"):
                meta = indicator_data["metadata"]
                latest_indicators[indicator_name]["metadata"] = {
                    "macd_line": [meta["macd_line"][-1]] if meta.get("macd_line") else [],
                    "signal_line": [meta["signal_line"][-1]] if meta.get("signal_line") else [],
                    "histogram": [meta["histogram"][-1]] if meta.get("histogram") else [],
                    "fast": meta.get("fast"),
                    "slow": meta.get("slow"),
                    "signal": meta.get("signal"),
                }


        return latest_indicators

# المثيل العام
chart_manager = ChartManager()