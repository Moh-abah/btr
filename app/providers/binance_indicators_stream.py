# trading_backend/app/providers/binance_indicators_stream.py
import json
import websockets
import asyncio
from datetime import datetime, timedelta
import redis

class IndicatorWebSocketManager:
    def __init__(self):
        self.active_symbols = {}
        self.binance_connections = {}
        # اتصال Redis
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
    
    async def connect_binance_stream(self, symbol: str, timeframe: str = "1m"):
        """الاتصال بـ Binance WebSocket"""
        binance_ws_url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@kline_{timeframe}"
        
        while True:  # إعادة الاتصال تلقائياً
            try:
                async with websockets.connect(binance_ws_url) as ws:
                    async for message in ws:
                        kline_data = json.loads(message)
                        await self.process_new_kline(symbol, kline_data)
            except Exception as e:
                print(f"WebSocket error for {symbol}: {e}, reconnecting in 5s...")
                await asyncio.sleep(5)
    
    async def process_new_kline(self, symbol: str, kline_data: dict):
        """معالجة شمعة جديدة"""
        candle = {
            'timestamp': datetime.fromtimestamp(kline_data['k']['t'] / 1000),
            'open': float(kline_data['k']['o']),
            'high': float(kline_data['k']['h']),
            'low': float(kline_data['k']['l']),
            'close': float(kline_data['k']['c']),
            'volume': float(kline_data['k']['v']),
            'is_closed': kline_data['k']['x']
        }
        
        if candle['is_closed']:
            # تحديث الكاش
            cache_key = f"kline:{symbol}:1m"
            cached = self.redis_client.get(cache_key)
            
            candles = json.loads(cached) if cached else []
            candles.append(candle)
            if len(candles) > 500:
                candles.pop(0)
            
            self.redis_client.setex(cache_key, 3600, json.dumps(candles))
            
            # إعلام جميع المشتركين
            await self.notify_subscribers(symbol, candle)
    
    async def notify_subscribers(self, symbol: str, new_candle: dict):
        """إرسال تحديث للمشتركين"""
        if symbol in self.active_symbols:
            update_msg = json.dumps({
                "type": "new_candle",
                "symbol": symbol,
                "candle": new_candle,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            for client in self.active_symbols[symbol]['clients']:
                try:
                    await client.send_text(update_msg)
                except:
                    self.active_symbols[symbol]['clients'].remove(client)

# إنشاء النسخة الوحيدة
indicators_manager = IndicatorWebSocketManager()