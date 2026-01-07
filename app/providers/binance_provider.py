# trading_backend\app\providers\binance_provider.py

import aiohttp
import httpx
import asyncio
import json
import pandas as pd
from typing import Dict, List
from datetime import datetime, timedelta
from app.config import settings
from ..services.data_provider import MarketDataProvider

class BinanceProvider(MarketDataProvider):
    def __init__(self):
        self.base_url = settings.BINANCE_API_URL
        self.ws_url = settings.BINANCE_WS_URL
        self.session = None
        self.symbols_cache = None
        self.cache_expiry = None
    


    async def _get_session(self):
        if not hasattr(self, "session") or self.session is None:
            self.session = httpx.AsyncClient()
        return self.session

 

 


 
    async def get_live_price(self, symbol: str) -> Dict:
        """الحصول على السعر الحالي لرمز محدد"""
        url = f"{self.base_url}/api/v3/ticker/price"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"symbol": symbol.upper()}) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "symbol": data["symbol"],
                            "price": float(data["price"]),
                            "timestamp": datetime.utcnow(),
                            "source": "binance"
                        }
                    else:
                        raise Exception(f"Binance API error: {response.status}")
        except Exception as e:
            print(f"Error fetching live price: {e}")
            return {}








    async def get_last_closed_candles(self,symbol: str, timeframe: str, limit: int = 200):
        """
        جلب آخر الشموع المغلقة فقط قبل الشمعة الحية (closed candles) 
        بدون استخدام datetime.utcnow().
        """
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "1h", "4h": "4h", "1d": "1d"
        }
        interval = interval_map.get(timeframe, "1h")

        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/api/v3/klines"
            params = {
                "symbol": symbol.upper(),
                "interval": interval,
                "limit": limit + 1  # نأخذ واحدة إضافية لنزيل الشمعة الحالية غير المغلقة
            }
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise Exception(f"Error fetching candles: {resp.status}")
                data = await resp.json()
                
                if not data:
                    return pd.DataFrame()
                
                # تحويل إلى DataFrame
                df = pd.DataFrame(data, columns=[
                    'open_time', 'open', 'high', 'low', 'close',
                    'volume', 'close_time', 'quote_volume',
                    'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
                ])
                numeric_cols = ['open', 'high', 'low', 'close', 'volume']
                df[numeric_cols] = df[numeric_cols].astype(float)
                df['time'] = df['open_time'].astype(int)
                
        
                df = df.iloc[:-1] if len(df) > 1 else df
                
                return df








    async def get_historicalcandl(
        self, 
        symbol: str, 
        timeframe: str,
        start_date: datetime,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """الحصول على كل الشموع التاريخية حتى آخر شمعة حية - مؤكد الجلب"""
        
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1h", "4h": "4h", "1d": "1d"
        }
    
        interval = interval_map.get(timeframe, "1h")
        
        # إذا لم يتم تحديد end_date، استخدم الوقت الحالي
        if end_date is None:
            end_date = datetime.utcnow()
        
        # حساب وقت آخر شمعة مغلقة (الشمعة الحالية لم تغلق بعد)
        # نريد آخر شمعة مغلقة، لذا نرجع خطوة واحدة للخلف
        timeframe_minutes = self._timeframe_to_minutes(timeframe)
        candle_duration = timedelta(minutes=timeframe_minutes)
        last_closed_end_date = end_date - candle_duration
        
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(last_closed_end_date.timestamp() * 1000)
        

        all_candles = []
        current_start = start_ms

        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    url = f"{self.base_url}/api/v3/klines"
                    params = {
                        "symbol": symbol.upper(),
                        "interval": interval,
                        "startTime": current_start,
                        "limit": 1000
                    }
                    
                    # أضف endTime فقط في الطلب الأخير
                    if current_start + (1000 * timeframe_minutes * 60 * 1000) >= end_ms:
                        params["endTime"] = end_ms
                    
                   
                    async with session.get(url, params=params, timeout=30) as response:
                        if response.status != 200:
                           
                            break
                        
                        data = await response.json()
                        if not data:
                            
                            break

                        batch_df = pd.DataFrame(data, columns=[
                            'open_time', 'open', 'high', 'low', 'close',
                            'volume', 'close_time', 'quote_volume',
                            'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
                        ])
                        
                        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
                        batch_df[numeric_cols] = batch_df[numeric_cols].astype(float)
                        batch_df['time'] = batch_df['open_time'].astype(int)
                        
                        # إضافة دفعة الشموع
                        all_candles.append(batch_df[['time', 'open', 'high', 'low', 'close', 'volume']])
                        
                        last_candle_time = batch_df['time'].max()
                        
                        # إذا وصلنا إلى النهاية أو حصلنا على أقل من 1000 شمعة
                        if last_candle_time >= end_ms or len(data) < 1000:
                         
                            break
                        
                        # التالي: ابدأ من آخر شمعة + 1 مللي ثانية
                        current_start = last_candle_time + 1
                        
                        # تأخير لتجنب rate limiting
                        await asyncio.sleep(0.05)

                if all_candles:
                    # دمج كل الدفعات
                    df = pd.concat(all_candles, ignore_index=True)
                    
                    # إزالة التكرارات وترتيب
                    df = df.drop_duplicates(subset=['time']).sort_values('time')
                    
                    # تصفية الشموع بعد end_ms
                    df = df[df['time'] <= end_ms]
                    
                    # تسجيل النتائج
                  
                    if len(df) > 0:
                        first_time = datetime.fromtimestamp(df.iloc[0]['time']/1000)
                        last_time = datetime.fromtimestamp(df.iloc[-1]['time']/1000)
               

                    return df
                else:
                   
                    return pd.DataFrame()

        except asyncio.TimeoutError:
           
            return pd.DataFrame()
        except Exception as e:
           
            return pd.DataFrame()
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """تحويل الإطار الزمني إلى دقائق"""
        if timeframe.endswith('m'):
            return int(timeframe[:-1])
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 24 * 60
        else:
            return 1



    # async def get_historical(
    #     self, 
    #     symbol: str, 
    #     timeframe: str,
    #     start_date: datetime,
    #     end_date: datetime = None
    # ) -> pd.DataFrame:
    #     """الحصول على بيانات تاريخية"""
    #     interval_map = {
    #         "1m": "1m", "5m": "5m", "15m": "15m",
    #         "1h": "1h", "4h": "4h", "1d": "1d"
    #     }
    #     interval = interval_map.get(timeframe, "1h")
    #     url = f"{self.base_url}/api/v3/klines"
        
    #     params = {
    #         "symbol": symbol.upper(),
    #         "interval": interval,
    #         "startTime": int(start_date.timestamp() * 1000),
    #         "limit": 1000
    #     }
    #     if end_date:
    #         params["endTime"] = int(end_date.timestamp() * 1000)

    #     try:
    #         async with aiohttp.ClientSession() as session:
    #             async with session.get(url, params=params) as response:
    #                 if response.status == 200:
    #                     data = await response.json()
    #                     df = pd.DataFrame(data, columns=[
    #                         'open_time', 'open', 'high', 'low', 'close',
    #                         'volume', 'close_time', 'quote_volume',
    #                         'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
    #                     ])
    #                     numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    #                     df[numeric_cols] = df[numeric_cols].astype(float)
    #                     df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
    #                     df.set_index('timestamp', inplace=True)
    #                     return df[['open', 'high', 'low', 'close', 'volume']]
    #                 else:
    #                     raise Exception(f"Binance API error: {response.status}")
    #     except Exception as e:
    #         print(f"Error fetching historical data: {e}")
    #         return pd.DataFrame()







# في BinanceProvider.get_historical()
    async def get_historical(
        self, 
        symbol: str, 
        timeframe: str,
        start_date: datetime,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """الحصول على بيانات تاريخية"""
        # ✅ أضف 30m إلى interval_map
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w"
        }
        
        # تحقق من وجود timeframe مدعوم
        if timeframe not in interval_map:
            raise ValueError(f"Unsupported timeframe for Binance: {timeframe}. "
                            f"Supported: {list(interval_map.keys())}")
        
        interval = interval_map[timeframe]
        
        print(f"📊 BinanceProvider: Requesting {symbol} with interval {interval} "
            f"(timeframe: {timeframe})")
        
        url = f"{self.base_url}/api/v3/klines"
        
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "startTime": int(start_date.timestamp() * 1000),
            "limit": 1000
        }
        if end_date:
            params["endTime"] = int(end_date.timestamp() * 1000)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data:
                            print(f"⚠️ No data returned from Binance for {symbol}")
                            return pd.DataFrame()
                        
                        print(f"✅ Got {len(data)} candles from Binance")
                        
                        df = pd.DataFrame(data, columns=[
                            'open_time', 'open', 'high', 'low', 'close',
                            'volume', 'close_time', 'quote_volume',
                            'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
                        ])
                        
                        # التحقق من الفاصل الزمني
                        if len(data) > 1:
                            time_diff = (pd.to_datetime(data[1][0], unit='ms') - 
                                        pd.to_datetime(data[0][0], unit='ms')).total_seconds() / 60
                            print(f"⏱️ Binance interval: {time_diff} minutes")
                        
                        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
                        df[numeric_cols] = df[numeric_cols].astype(float)
                        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
                        df.set_index('timestamp', inplace=True)
                        return df[['open', 'high', 'low', 'close', 'volume']]
                    else:
                        error_text = await response.text()
                        print(f"❌ Binance API error {response.status}: {error_text}")
                        return pd.DataFrame()
        except Exception as e:
            print(f"❌ Error fetching Binance data: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()


    async def stream_live(self, symbol: str, timeframe: str = "1m"):
        """بث بيانات حية عبر WebSocket"""
        import websockets # type: ignore
        
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "1h", "4h": "4h", "1d": "1d"
        }
        interval = interval_map.get(timeframe, "1m")
        stream_name = f"{symbol.lower()}@kline_{interval}"
        
        async with websockets.connect(f"{self.ws_url}/{stream_name}") as ws:
            async for message in ws:
                data = json.loads(message)
                if 'k' in data:
                    kline = data['k']
                    yield {
                        "symbol": kline['s'],
                        "timeframe": timeframe,
                        "open": float(kline['o']),
                        "high": float(kline['h']),
                        "low": float(kline['l']),
                        "close": float(kline['c']),
                        "volume": float(kline['v']),
                        "is_closed": kline['x'],
                        "timestamp": datetime.utcfromtimestamp(kline['t'] / 1000),
                        "source": "binance"
                    }


                    
    async def get_symbols(self) -> List[str]:
        """الحصول على جميع الرموز المتاحة"""
        # استخدام الكاش لتقليل الطلبات
        if self.symbols_cache and self.cache_expiry > datetime.utcnow():
            return [s for s in self.symbols_cache if s.endswith(("USDT", "USDC"))]
            

        try:
            # إنشاء الجلسة باستخدام aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/api/v3/exchangeInfo"
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to fetch: {response.status}")
                    
                    data = await response.json()
                    symbols = [
                        s['symbol'] 
                        for s in data['symbols'] 
                        if s['status'] == "TRADING"
                    ]

                    # تحديث الكاش
                    self.symbols_cache = symbols
                    self.cache_expiry = datetime.utcnow() + timedelta(hours=1)


                    filtered_symbols = [s for s in symbols if s.endswith(("USDT", "USDC"))]
                    return filtered_symbols

                

        except Exception as e:
            print(f"Failed to get symbols: {e}")
            return []