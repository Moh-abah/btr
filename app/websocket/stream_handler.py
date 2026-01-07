import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Set, Callable
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict

from .schemas import (
    StreamMessage, StreamDataType,
    PriceStreamData, IndicatorStreamData,
    ConditionStreamData, SignalStreamData,
    EntryPointStreamData
)
from app.services.data_service import DataService
from app.services.indicators import apply_indicators
from app.services.strategy import run_strategy
from app.services.filtering import FilteringEngine

class RealTimeStreamHandler:
    """معالج البث اللحظي - شبيه بـ TradingView"""
    
    def __init__(self, data_service: DataService, filtering_engine: FilteringEngine):
        self.data_service = data_service
        self.filtering_engine = filtering_engine
        
        # تخزين البثوث النشطة
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.stream_tasks: Dict[str, asyncio.Task] = {}
        
        # المشتركون حسب الرمز والإطار الزمني
        self.subscribers: Dict[str, Set[Any]] = defaultdict(set)
        
        # كاش للبيانات
        self.price_cache: Dict[str, Dict] = {}
        self.indicator_cache: Dict[str, Dict] = {}
        
        # إحصائيات
        self.stats = {
            "total_messages_sent": 0,
            "active_connections": 0,
            "streams_started": 0,
            "streams_stopped": 0
        }
    
    async def start_stream(
        self,
        symbol: str,
        timeframe: str,
        market: str = "crypto",
        indicators_config: List[Dict[str, Any]] = None,
        strategy_config: Dict[str, Any] = None,
        stream_id: Optional[str] = None
    ) -> str:
        """
        بدء بث لحظي لرمز معين
        
        Args:
            symbol: الرمز
            timeframe: الإطار الزمني
            market: السوق
            indicators_config: تكوين المؤشرات
            strategy_config: تكوين الإستراتيجية
            stream_id: معرف البث (اختياري)
            
        Returns:
            str: معرف البث
        """
        stream_id = stream_id or f"{market}_{symbol}_{timeframe}_{int(time.time())}"
        
        if stream_id in self.active_streams:
            return stream_id
        
        # تهيئة إعدادات البث
        self.active_streams[stream_id] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "market": market,
            "indicators_config": indicators_config or [],
            "strategy_config": strategy_config,
            "start_time": datetime.utcnow(),
            "last_update": None,
            "message_count": 0,
            "status": "running"
        }
        
        # بدء مهمة البث
        # task = asyncio.create_task(self._stream_loop(stream_id))
        task = asyncio.create_task(self._live_stream_loop(stream_id))

        self.stream_tasks[stream_id] = task
        
        self.stats["streams_started"] += 1
        print(f"📡 Stream started: {stream_id}")
        
        return stream_id
    


    async def _live_stream_loop(self, stream_id: str):
        stream = self.active_streams.get(stream_id)
        if not stream:
            return

        symbol = stream["symbol"]
        timeframe = stream["timeframe"]
        market = stream["market"]

        async for tick in self.data_service.stream_live(symbol, timeframe, market):
            if stream_id not in self.active_streams:
                break

            if stream["status"] == "paused":
                await asyncio.sleep(0.5)
                continue

            await self._handle_live_tick(stream_id, tick)







    async def _handle_live_tick(self, stream_id: str, tick: dict):
        stream = self.active_streams[stream_id]
        symbol = stream["symbol"]
        timeframe = stream["timeframe"]

        # 1️⃣ تحديث السعر مباشرة
        price_msg = StreamMessage(
            type=StreamDataType.PRICE,
            symbol=symbol,
            timeframe=timeframe,
            data={
                "open": tick["open"],
                "high": tick["high"],
                "low": tick["low"],
                "close": tick["close"],
                "volume": tick["volume"],
                "timestamp": tick["timestamp"].isoformat()
            }
        )

        await self._broadcast_messages(stream_id, [price_msg])

        # 2️⃣ لا نحسب استراتيجيات إلا إذا الشمعة أغلقت
        if not tick["is_closed"]:
            return

        df = await self.data_service.get_historical(
            symbol=symbol,
            timeframe=timeframe,
            market=stream["market"],
            days=2
        )

        messages = await self._process_stream_data(
            stream_id,
            df,
            stream["indicators_config"],
            stream["strategy_config"]
        )

        await self._broadcast_messages(stream_id, messages)








    async def stop_stream(self, stream_id: str) -> bool:
        """إيقاف بث محدد"""
        if stream_id not in self.active_streams:
            return False
        
        # إيقاف المهمة
        if stream_id in self.stream_tasks:
            self.stream_tasks[stream_id].cancel()
            try:
                await self.stream_tasks[stream_id]
            except asyncio.CancelledError:
                pass
            del self.stream_tasks[stream_id]
        
        # إزالة من السجلات
        del self.active_streams[stream_id]
        
        # إزالة المشتركين
        if stream_id in self.subscribers:
            del self.subscribers[stream_id]
        
        self.stats["streams_stopped"] += 1
        print(f"📡 Stream stopped: {stream_id}")
        
        return True
    
    async def subscribe(self, stream_id: str, websocket) -> bool:
        """اشتراك عميل في بث معين"""
        if stream_id not in self.active_streams:
            return False
        
        self.subscribers[stream_id].add(websocket)
        self.stats["active_connections"] = sum(len(subs) for subs in self.subscribers.values())
        
        # إرسال بيانات أولية للمشترك الجديد
        await self._send_initial_data(stream_id, websocket)
        
        print(f"👥 New subscriber for stream {stream_id}")
        return True
    
    async def unsubscribe(self, stream_id: str, websocket) -> bool:
        """إلغاء اشتراك عميل من بث"""
        if stream_id in self.subscribers and websocket in self.subscribers[stream_id]:
            self.subscribers[stream_id].remove(websocket)
            self.stats["active_connections"] = sum(len(subs) for subs in self.subscribers.values())
            return True
        return False
    
    async def _stream_loop(self, stream_id: str):
        """الحلقة الرئيسية للبث"""
        stream_info = self.active_streams.get(stream_id)
        if not stream_info:
            return
        
        symbol = stream_info["symbol"]
        timeframe = stream_info["timeframe"]
        market = stream_info["market"]
        indicators_config = stream_info["indicators_config"]
        strategy_config = stream_info["strategy_config"]
        
        try:
            while stream_id in self.active_streams:
                # الحصول على أحدث البيانات
                data = await self._fetch_latest_data(symbol, timeframe, market)
                
                if data is not None and not data.empty:
                    # معالجة البيانات وإنشاء الرسائل
                    messages = await self._process_stream_data(
                            stream_id, data, indicators_config, strategy_config
                    )
                    
                    # إرسال الرسائل لجميع المشتركين
                    await self._broadcast_messages(stream_id, messages)
                    
                    # تحديث الإحصائيات
                    stream_info["last_update"] = datetime.utcnow()
                    stream_info["message_count"] += len(messages)
                    self.stats["total_messages_sent"] += len(messages)
                
                # الانتظار حسب الإطار الزمني
                await asyncio.sleep(self._get_stream_interval(timeframe))
                
        except asyncio.CancelledError:
            print(f"Stream {stream_id} cancelled")
        except Exception as e:
            print(f"Error in stream loop {stream_id}: {e}")
            # إعادة المحاولة بعد تأخير
            await asyncio.sleep(5)
            if stream_id in self.active_streams:
                asyncio.create_task(self._stream_loop(stream_id))
    
    async def _fetch_latest_data(
        self,
        symbol: str,
        timeframe: str,
        market: str
    ) -> Optional[pd.DataFrame]:
        """جلب أحدث البيانات"""
        try:
            # الحصول على بيانات تاريخية حديثة
            data = await self.data_service.get_historical(
                symbol=symbol,
                timeframe=timeframe,
                market=market,
                days=2  # يومين للتحليل
            )
            
            if data.empty or len(data) < 10:
                return None
            
            return data.tail(100)  # آخر 100 نقطة للتحليل
            
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None
    
    async def _process_stream_data(
        self,
        stream_id: str,
        data: pd.DataFrame,
        indicators_config: List[Dict[str, Any]],
        strategy_config: Dict[str, Any]
    ) -> List[StreamMessage]:
        """معالجة البيانات وإنشاء رسائل البث"""
        messages = []
        
        if data.empty:
            return messages
        
        stream_info = self.active_streams[stream_id]
        symbol = stream_info["symbol"]
        timeframe = stream_info["timeframe"]
        
        # 1. بيانات السعر
        price_message = await self._create_price_message(data, symbol, timeframe)
        messages.append(price_message)
        
        # 2. بيانات المؤشرات (إذا كانت موجودة)
        if indicators_config:
            indicator_messages = await self._create_indicator_messages(
                data, indicators_config, symbol, timeframe
            )
            messages.extend(indicator_messages)
        
        # 3. بيانات الإستراتيجية والإشارات (إذا كانت موجودة)
        if strategy_config:
            strategy_messages = await self._create_strategy_messages(
                data, strategy_config, symbol, timeframe
            )
            messages.extend(strategy_messages)
        
        # 4. رسالة حالة
        status_message = await self._create_status_message(stream_id, len(messages))
        messages.append(status_message)
        
        return messages
    
    async def _create_price_message(
        self,
        data: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> StreamMessage:
        """إنشاء رسالة بيانات السعر"""
        latest = data.iloc[-1]
        
        price_data = PriceStreamData(
            open=float(latest['open']),
            high=float(latest['high']),
            low=float(latest['low']),
            close=float(latest['close']),
            volume=float(latest['volume']),
            timestamp=latest.name if hasattr(latest, 'name') else datetime.utcnow()
        )
        
        # تخزين في الكاش
        cache_key = f"{symbol}_{timeframe}_price"
        self.price_cache[cache_key] = price_data.dict()
        
        return StreamMessage(
            type=StreamDataType.PRICE,
            symbol=symbol,
            timeframe=timeframe,
            data=price_data.dict()
        )
    
    async def _create_indicator_messages(
        self,
        data: pd.DataFrame,
        indicators_config: List[Dict[str, Any]],
        symbol: str,
        timeframe: str
    ) -> List[StreamMessage]:
        """إنشاء رسائل المؤشرات"""
        messages = []
        
        # حساب المؤشرات
        indicator_results = apply_indicators(
            dataframe=data,
            indicators_config=indicators_config,
            use_cache=True

        )
        
        for name, result in indicator_results.items():
            if result.values.empty:
                continue
            
            latest_value = float(result.values.iloc[-1])
            previous_value = float(result.values.iloc[-2]) if len(result.values) > 1 else None
            
            # توليد إشارة من المؤشر
            signal = 0
            if result.signals is not None and not result.signals.empty:
                signal = int(result.signals.iloc[-1])
            
            indicator_data = IndicatorStreamData(
                name=name,
                value=latest_value,
                previous_value=previous_value,
                values=result.values.tolist()[-20:],  # آخر 20 قيمة للرسم
                metadata=result.metadata,
                signal=signal
            )
            
            message = StreamMessage(
                type=StreamDataType.INDICATOR,
                symbol=symbol,
                timeframe=timeframe,
                data=indicator_data.dict(),
                metadata={"indicator_name": name}
            )
            messages.append(message)
            
            # تخزين في الكاش
            cache_key = f"{symbol}_{timeframe}_{name}"
            self.indicator_cache[cache_key] = indicator_data.dict()
        
        return messages
    
    async def _create_strategy_messages(
        self,
        data: pd.DataFrame,
        strategy_config: Dict[str, Any],
        symbol: str,
        timeframe: str
    ) -> List[StreamMessage]:
        """إنشاء رسائل الإستراتيجية والإشارات"""
        messages = []
        
        try:
            # تشغيل الإستراتيجية
            result = run_strategy(
                data=data,
                strategy_config=strategy_config,
                live_mode=True,
                use_cache=True
            )
            
            # 1. رسائل الشروط
            for signal in result.signals[-5:]:  # آخر 5 إشارات
                condition_data = ConditionStreamData(
                    name=signal.rule_name,
                    is_met=True,
                    description=f"{signal.action.upper()} signal at {signal.price}",
                    current_value=signal.price,
                    threshold=signal.price,
                    conditions=[],  # يمكن إضافة الشروط الفرعية هنا
                    confidence=signal.strength
                )
                
                message = StreamMessage(
                    type=StreamDataType.CONDITION,
                    symbol=symbol,
                    timeframe=timeframe,
                    data=condition_data.dict(),
                    metadata={
                        "rule_name": signal.rule_name,
                        "signal_type": signal.action
                    }
                )
                messages.append(message)
            
            # 2. رسائل الإشارات (المفلترة)
            for signal in result.filtered_signals:
                signal_data = SignalStreamData(
                    type="entry" if signal.action in ["buy", "sell"] else "exit",
                    action=signal.action,
                    strength=signal.strength,
                    price=signal.price,
                    timestamp=signal.timestamp,
                    conditions=[],  # يمكن إضافة الشروط هنا
                    entry_price=signal.price if signal.action == "buy" else None,
                    stop_loss=signal.price * 0.95 if signal.action == "buy" else None,
                    take_profit=signal.price * 1.1 if signal.action == "buy" else None
                )
                
                message = StreamMessage(
                    type=StreamDataType.SIGNAL,
                    symbol=symbol,
                    timeframe=timeframe,
                    data=signal_data.dict(),
                    metadata={
                        "signal_type": signal.action,
                        "rule_name": signal.rule_name
                    }
                )
                messages.append(message)
                
                # 3. إذا كانت إشارة شراء، أضف رسالة نقطة الدخول
                if signal.action == "buy":
                    entry_data = EntryPointStreamData(
                        price=signal.price,
                        stop_loss=signal.price * 0.95,
                        take_profit=signal.price * 1.1,
                        confidence=signal.strength,
                        risk_reward_ratio=3.0,
                        position_size=0.1,  # 10% من رأس المال
                        timestamp=signal.timestamp
                    )
                    
                    message = StreamMessage(
                        type=StreamDataType.ENTRY_POINT,
                        symbol=symbol,
                        timeframe=timeframe,
                        data=entry_data.dict(),
                        metadata={"entry_type": "buy"}
                    )
                    messages.append(message)
                    
        except Exception as e:
            print(f"Error creating strategy messages: {e}")
        
        return messages
    
    async def _create_status_message(self, stream_id: str, messages_count: int) -> StreamMessage:
        """إنشاء رسالة حالة"""
        stream_info = self.active_streams[stream_id]
        
        status_data = {
            "stream_id": stream_id,
            "status": "active",
            "uptime": (datetime.utcnow() - stream_info["start_time"]).total_seconds(),
            "messages_sent": stream_info["message_count"],
            "last_update": stream_info["last_update"].isoformat() if stream_info["last_update"] else None,
            "subscribers_count": len(self.subscribers.get(stream_id, []))
        }
        
        return StreamMessage(
            type=StreamDataType.STATUS,
            symbol=stream_info["symbol"],
            timeframe=stream_info["timeframe"],
            data=status_data
        )
    
    async def _broadcast_messages(self, stream_id: str, messages: List[StreamMessage]):
        """بث الرسائل لجميع المشتركين"""
        if stream_id not in self.subscribers or not self.subscribers[stream_id]:
            return
        
        subscribers = list(self.subscribers[stream_id])
        for message in messages:
            message_json = message.to_json()
            
            for websocket in subscribers:
                try:
                    await websocket.send_text(message_json)
                except Exception as e:
                    print(f"Error broadcasting to websocket: {e}")
                    # إزالة المشترك إذا كان هناك خطأ
                    await self.unsubscribe(stream_id, websocket)
    
    async def _send_initial_data(self, stream_id: str, websocket):
        """إرسال بيانات أولية للمشترك الجديد"""
        stream_info = self.active_streams.get(stream_id)
        if not stream_info:
            return
        
        symbol = stream_info["symbol"]
        timeframe = stream_info["timeframe"]
        
        # إرسال بيانات الكاش المخزنة
        initial_messages = []
        
        # بيانات السعر المخزنة
        price_key = f"{symbol}_{timeframe}_price"
        if price_key in self.price_cache:
            price_message = StreamMessage(
                type=StreamDataType.PRICE,
                symbol=symbol,
                timeframe=timeframe,
                data=self.price_cache[price_key]
            )
            initial_messages.append(price_message)
        
        # بيانات المؤشرات المخزنة
        for key, data in self.indicator_cache.items():
            if key.startswith(f"{symbol}_{timeframe}_"):
                indicator_name = key.replace(f"{symbol}_{timeframe}_", "")
                indicator_message = StreamMessage(
                    type=StreamDataType.INDICATOR,
                    symbol=symbol,
                    timeframe=timeframe,
                    data=data,
                    metadata={"indicator_name": indicator_name}
                )
                initial_messages.append(indicator_message)
        
        # بث الرسائل الأولية
        for message in initial_messages:
            try:
                await websocket.send_text(message.to_json())
            except Exception as e:
                print(f"Error sending initial data: {e}")
                break
    
    def _get_stream_interval(self, timeframe: str) -> int:
        """الحصول على فاصل البث المناسب للإطار الزمني"""
        intervals = {
            "1m": 10,     # 10 ثواني
            "5m": 30,     # 30 ثانية
            "15m": 60,    # دقيقة واحدة
            "30m": 120,   # دقيقتان
            "1h": 300,    # 5 دقائق
            "4h": 900,    # 15 دقيقة
            "1d": 3600,   # ساعة واحدة
            "1w": 7200,   # ساعتان
        }
        
        return intervals.get(timeframe, 60)
    
    def get_stream_info(self, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """الحصول على معلومات البث"""
        if stream_id:
            if stream_id in self.active_streams:
                return {
                    **self.active_streams[stream_id],
                    "subscribers_count": len(self.subscribers.get(stream_id, []))
                }
            return {}
        
        # جميع البثوث
        streams_info = {}
        for sid, info in self.active_streams.items():
            streams_info[sid] = {
                **info,
                "subscribers_count": len(self.subscribers.get(sid, []))
            }
        
        return {
            "active_streams": streams_info,
            "stats": self.stats,
            "total_streams": len(self.active_streams)
        }