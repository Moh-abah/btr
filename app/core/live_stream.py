# \app\core\live_stream.py
"""
نظام البث الحي المحسّن للأداء العالي
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Callable, Any
from contextlib import asynccontextmanager
import logging

from app.providers.binance_market_streamca import stream_all_marketca

logger = logging.getLogger(__name__)

class LiveStreamManager:
    """مدير البث الحي المركزي"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def _now_ms(self) -> int:
        return int(datetime.utcnow().timestamp() * 1000)


    def __init__(self):
        if self._initialized:
            return
        
        self._stream_task = None
        self._subscribers: Dict[str, Set[Callable]] = {}  # symbol -> [callbacks]
        self._active_streams: Set[str] = set()
        self._stream_data: Dict[str, Dict] = {}  # Latest data per symbol
        self._lock = asyncio.Lock()
        self._initialized = True
        logger.info("✅ LiveStreamManager initialized")
    
    async def start(self):
        """بدء النظام الرئيسي للبث الحي"""
        if self._stream_task is None or self._stream_task.done():
            self._stream_task = asyncio.create_task(self._global_stream_loop())
            logger.info("🚀 Global live stream started")





    async def stop(self):
        """إيقاف البث الحي"""
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            self._stream_task = None
            logger.info("🛑 Global live stream stopped")
    
    async def subscribe(self, symbol: str, callback: Callable):
        """اشتراك في رمز معين"""
        async with self._lock:
            if symbol not in self._subscribers:
                self._subscribers[symbol] = set()
            self._subscribers[symbol].add(callback)
            
            # إضافة إلى البث النشط
            self._active_streams.add(symbol)
            logger.debug(f"➕ Subscribed to {symbol}, total subscribers: {len(self._subscribers[symbol])}")
    
    async def unsubscribe(self, symbol: str, callback: Callable):
        """إلغاء الاشتراك"""
        async with self._lock:
            if symbol in self._subscribers and callback in self._subscribers[symbol]:
                self._subscribers[symbol].remove(callback)
                
                if not self._subscribers[symbol]:
                    del self._subscribers[symbol]
                    
                # تحديث البث النشط
                await self._update_active_streams()
                logger.debug(f"➖ Unsubscribed from {symbol}")
    
    async def _update_active_streams(self):
        """تحديث الرموز النشطة بناءً على المشتركين"""
        self._active_streams = set(self._subscribers.keys())
        logger.debug(f"📊 Active streams updated: {len(self._active_streams)} symbols")
    
    async def _global_stream_loop(self):
        """الحلقة الرئيسية للبث الحي"""
        logger.info("🔄 Starting global stream loop...")
        
        while True:
            try:
                async for market_data in stream_all_marketca():
                    if not market_data or "data" not in market_data:
                        continue
                    
                    # معالجة كل عنصر في البيانات
                    for item in market_data["data"]:
                        symbol = item.get("symbol")
                        if not symbol:
                            continue
                        
                        # تحديث أحدث البيانات
                        self._stream_data[symbol] = {
                            "price": float(item.get("price", 0)),
                            "volume": float(item.get("volume", 0)),
                            "time":self._now_ms(),
                            "bid": float(item.get("bid", 0)),
                            "ask": float(item.get("ask", 0)),
                            "change": float(item.get("change", 0))
                        }
                        
                        # إرسال للمشتركين
                        await self._notify_subscribers(symbol, self._stream_data[symbol])
                
                await asyncio.sleep(0.1)  # منع الاستهلاك العالي للـ CPU
                
            except asyncio.CancelledError:
                logger.info("🔴 Global stream cancelled")
                break
            except Exception as e:
                logger.error(f"⚠️ Error in global stream: {e}")
                await asyncio.sleep(5)  # إعادة المحاولة بعد 5 ثواني
    
    async def _notify_subscribers(self, symbol: str, data: Dict):
        """إرسال البيانات للمشتركين"""
        if symbol not in self._subscribers:
            return
        
        callbacks = list(self._subscribers[symbol])  # نسخة للاستخدام
        
        # تشغيل جميع الـ callbacks بشكل متوازي
        tasks = [callback(data) for callback in callbacks]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.error(f"❌ Error in price update callback: {res}")
    
    async def get_latest_price(self, symbol: str) -> Optional[Dict]:
        """الحصول على آخر سعر لرمز معين"""
        return self._stream_data.get(symbol)
    
    def get_active_symbols(self) -> List[str]:
        """الحصول على الرموز النشطة"""
        return list(self._active_streams)



def _now_ms(self) -> int:
    return int(datetime.utcnow().timestamp() * 1000)


# المثيل العام
live_stream_manager = LiveStreamManager()