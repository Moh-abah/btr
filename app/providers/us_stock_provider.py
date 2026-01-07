# app/providers/us_stock_provider.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, AsyncGenerator
import pandas as pd
import numpy as np

from .yahoo_client import YahooFinanceClient
from .alphavantage_client import AlphaVantageClient

logger = logging.getLogger(__name__)

class USStockProvider:
    """المزود الرئيسي للأسهم الأمريكية - TradingView Style"""
    
    def __init__(self, use_alpha_vantage: bool = True):
        self.yahoo = YahooFinanceClient()
        self.alpha_vantage = None
        
        if use_alpha_vantage:
            try:
                self.alpha_vantage = AlphaVantageClient()
                logger.info("✅ AlphaVantageClient initialized")
            except Exception as e:
                logger.warning(f"⚠️ AlphaVantage initialization failed: {e}")
        
        logger.info("✅ USStockProvider initialized successfully")
    
    # ==================== البيانات الأساسية ====================
    


    async def get_symbols(self, category: Optional[str] = None) -> List[str]:
        """الحصول على الرموز حسب الفئة"""
        if category and category in self.yahoo.base_symbols:
            return self.yahoo.base_symbols[category]
        
        return await self.yahoo.get_all_symbols()
    







    async def get_live_price(self, symbol: str) -> Dict:
        """الحصول على السعر الحي"""
        return await self.yahoo.get_live_quote(symbol)




    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1mo",
        start: Optional[str] = None,
        end: Optional[str] = None
    ) -> pd.DataFrame:
        """الحصول على البيانات التاريخية"""
        return await self.yahoo.get_historical_data(symbol, timeframe, period, start, end)
    
# app/providers/us_stock_provider.py
    async def get_historical(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        دالة توافقية مع BinanceProvider للحصول على بيانات تاريخية
        
        Args:
            symbol: رمز السهم
            timeframe: الإطار الزمني (1m, 5m, 15m, 1h, 4h, 1d)
            start_date: تاريخ البداية
            end_date: تاريخ النهاية (اختياري)
        
        Returns:
            DataFrame: البيانات التاريخية
        """
        # تحويل timeframe إلى تنسيق Yahoo Finance
        timeframe_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1h", "4h": "4h", "1d": "1d"
        }
        
        yf_interval = timeframe_map.get(timeframe, "1h")
        
        # تحويل التواريخ إلى strings
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d") if end_date else datetime.utcnow().strftime("%Y-%m-%d")
        
        # حساب عدد الأيام للفترة
        if end_date:
            days_diff = (end_date - start_date).days
        else:
            days_diff = (datetime.utcnow() - start_date).days
        
        period = f"{days_diff}d"
        
        # الحصول على البيانات
        df = await self.get_historical_data(
            symbol=symbol,
            timeframe=yf_interval,
            period=period,
            start=start_str,
            end=end_str
        )
        
        # التأكد من وجود الأعمدة المطلوبة
        if not df.empty:
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df.columns:
                    logger.warning(f"Column {col} not found in data for {symbol}")
            
            # إرجاع الأعمدة المطلوبة فقط
            return df[[col for col in required_columns if col in df.columns]]
        
        return df




    async def get_company_info(self, symbol: str) -> Dict:
        """الحصول على معلومات الشركة"""
        return await self.yahoo.get_company_info(symbol)
    
    # ==================== المؤشرات الفنية ====================
    
    async def calculate_indicators(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1mo",
        indicators: List[Dict] = None
    ) -> Dict:
        """حساب المؤشرات الفنية"""
        if indicators is None:
            indicators = [
                {"name": "sma", "params": {"period": 20}},
                {"name": "rsi", "params": {"period": 14}},
                {"name": "macd", "params": {}},
                {"name": "bollinger_bands", "params": {}}
            ]
        
        # الحصول على البيانات
        df = await self.get_historical_data(symbol, timeframe, period)
        
        if df.empty:
            return {"error": "No data available"}
        
        # حساب المؤشرات
        results = await self.yahoo.calculate_indicators(df, indicators)
        
        # تحويل النتائج إلى تنسيق قابل للتسلسل
        processed_results = {}
        for name, result in results.items():
            if isinstance(result, dict):
                processed_results[name] = {}
                for key, series in result.items():
                    processed_results[name][key] = series.dropna().to_dict()
            elif hasattr(result, 'to_dict'):
                processed_results[name] = result.dropna().to_dict()
            else:
                processed_results[name] = result
        
        # إضافة بيانات الشموع
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "time": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": int(row['volume'])
            })
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": candles,
            "indicators": processed_results,
            "metadata": {
                "start_date": df.index[0].isoformat(),
                "end_date": df.index[-1].isoformat(),
                "rows": len(df)
            }
        }
    
    async def get_technical_analysis(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "3mo"
    ) -> Dict:
        """تحليل فني متكامل"""
        df = await self.get_historical_data(symbol, timeframe, period)
        
        if df.empty:
            return {}
        
        analysis = {
            "trend": await self._analyze_trend(df),
            "momentum": await self._analyze_momentum(df),
            "volatility": await self._analyze_volatility(df),
            "volume": await self._analyze_volume(df),
            "signals": await self._generate_signals(df)
        }
        
        return analysis
    
    async def _analyze_trend(self, df: pd.DataFrame) -> Dict:
        """تحليل الاتجاه"""
        # المتوسطات المتحركة
        sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
        sma_50 = df['close'].rolling(window=50).mean().iloc[-1]
        sma_200 = df['close'].rolling(window=200).mean().iloc[-1]
        
        current_price = df['close'].iloc[-1]
        
        trend = "sideways"
        if current_price > sma_20 > sma_50 > sma_200:
            trend = "strong_uptrend"
        elif current_price > sma_20 > sma_50:
            trend = "uptrend"
        elif current_price < sma_20 < sma_50 < sma_200:
            trend = "strong_downtrend"
        elif current_price < sma_20 < sma_50:
            trend = "downtrend"
        
        return {
            "direction": trend,
            "price_vs_sma20": (current_price / sma_20 - 1) * 100,
            "price_vs_sma50": (current_price / sma_50 - 1) * 100,
            "price_vs_sma200": (current_price / sma_200 - 1) * 100,
            "sma20": float(sma_20),
            "sma50": float(sma_50),
            "sma200": float(sma_200)
        }
    
    async def _analyze_momentum(self, df: pd.DataFrame) -> Dict:
        """تحليل الزخم"""
        # حساب RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # حساب MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        
        # حساب Stochastic
        low_14 = df['low'].rolling(window=14).min()
        high_14 = df['high'].rolling(window=14).max()
        stoch_k = 100 * ((df['close'] - low_14) / (high_14 - low_14))
        stoch_d = stoch_k.rolling(window=3).mean()
        
        return {
            "rsi": float(rsi.iloc[-1]),
            "rsi_status": "oversold" if rsi.iloc[-1] < 30 else "overbought" if rsi.iloc[-1] > 70 else "neutral",
            "macd": float(macd_line.iloc[-1]),
            "signal": float(signal_line.iloc[-1]),
            "macd_histogram": float(macd_line.iloc[-1] - signal_line.iloc[-1]),
            "stochastic_k": float(stoch_k.iloc[-1]),
            "stochastic_d": float(stoch_d.iloc[-1]),
            "momentum": (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100 if len(df) >= 20 else 0
        }
    
    async def _analyze_volatility(self, df: pd.DataFrame) -> Dict:
        """تحليل التقلب"""
        returns = df['close'].pct_change().dropna()
        
        volatility_20 = returns.tail(20).std() * np.sqrt(252) * 100  # سنوي
        volatility_50 = returns.tail(50).std() * np.sqrt(252) * 100
        
        # نطاقات بولينجر
        sma_20 = df['close'].rolling(window=20).mean()
        std_20 = df['close'].rolling(window=20).std()
        upper_band = sma_20 + (std_20 * 2)
        lower_band = sma_20 - (std_20 * 2)
        
        current_price = df['close'].iloc[-1]
        bb_position = (current_price - lower_band.iloc[-1]) / (upper_band.iloc[-1] - lower_band.iloc[-1]) * 100
        
        return {
            "volatility_20d": float(volatility_20),
            "volatility_50d": float(volatility_50),
            "atr": float(self._calculate_atr(df, 14).iloc[-1]),
            "bb_position": float(bb_position),
            "bb_width": float((upper_band.iloc[-1] - lower_band.iloc[-1]) / sma_20.iloc[-1] * 100)
        }
    
    async def _analyze_volume(self, df: pd.DataFrame) -> Dict:
        """تحليل الحجم"""
        avg_volume_20 = df['volume'].tail(20).mean()
        current_volume = df['volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1
        
        # OBV
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        
        return {
            "volume": int(current_volume),
            "avg_volume_20": int(avg_volume_20),
            "volume_ratio": float(volume_ratio),
            "obv": float(obv.iloc[-1]),
            "obv_trend": "up" if obv.iloc[-1] > obv.iloc[-5] else "down",
            "volume_status": "high" if volume_ratio > 1.5 else "low" if volume_ratio < 0.5 else "normal"
        }
    
    async def _generate_signals(self, df: pd.DataFrame) -> List[Dict]:
        """توليد إشارات التداول"""
        signals = []
        
        # إشارات RSI
        rsi = self._calculate_rsi(df, 14)
        if not rsi.empty:
            last_rsi = rsi.iloc[-1]
            if last_rsi < 30:
                signals.append({
                    "type": "buy",
                    "indicator": "rsi",
                    "strength": "strong",
                    "description": "RSI indicates oversold condition"
                })
            elif last_rsi > 70:
                signals.append({
                    "type": "sell",
                    "indicator": "rsi",
                    "strength": "strong",
                    "description": "RSI indicates overbought condition"
                })
        
        # إشارات MACD
        macd_result = self.yahoo._calculate_macd(df)
        if 'macd' in macd_result and 'signal' in macd_result:
            macd_line = macd_result['macd']
            signal_line = macd_result['signal']
            
            if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
                signals.append({
                    "type": "buy",
                    "indicator": "macd",
                    "strength": "medium",
                    "description": "MACD crossover above signal line"
                })
            elif macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2]:
                signals.append({
                    "type": "sell",
                    "indicator": "macd",
                    "strength": "medium",
                    "description": "MACD crossover below signal line"
                })
        
        # إشارات بولينجر
        bb_result = self.yahoo._calculate_bollinger_bands(df)
        if 'upper' in bb_result and 'lower' in bb_result:
            current_price = df['close'].iloc[-1]
            upper_band = bb_result['upper'].iloc[-1]
            lower_band = bb_result['lower'].iloc[-1]
            
            if current_price < lower_band:
                signals.append({
                    "type": "buy",
                    "indicator": "bollinger",
                    "strength": "weak",
                    "description": "Price below lower Bollinger Band"
                })
            elif current_price > upper_band:
                signals.append({
                    "type": "sell",
                    "indicator": "bollinger",
                    "strength": "weak",
                    "description": "Price above upper Bollinger Band"
                })
        
        return signals
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """حساب ATR"""
        return self.yahoo._calculate_atr(df, period)
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """حساب RSI"""
        return self.yahoo._calculate_rsi(df, period)
    
    # ==================== بيانات Alpha Vantage المتقدمة ====================
    
    async def get_fundamental_data(self, symbol: str) -> Dict:
        """الحصول على البيانات الأساسية من Alpha Vantage"""
        if not self.alpha_vantage:
            return {}
        
        try:
            async with self.alpha_vantage as client:
                overview = await client.get_fundamental_data(symbol)
                earnings = await client.get_earnings(symbol)
                
                return {
                    "overview": overview,
                    "earnings": earnings
                }
        except Exception as e:
            logger.error(f"Error fetching fundamental data: {e}")
            return {}
    
    async def get_financial_statements(self, symbol: str) -> Dict:
        """الحصول على القوائم المالية"""
        if not self.alpha_vantage:
            return {}
        
        try:
            async with self.alpha_vantage as client:
                income = await client.get_income_statement(symbol)
                balance = await client.get_balance_sheet(symbol)
                cashflow = await client.get_cash_flow(symbol)
                
                return {
                    "income_statement": income,
                    "balance_sheet": balance,
                    "cash_flow": cashflow
                }
        except Exception as e:
            logger.error(f"Error fetching financial statements: {e}")
            return {}
    
    async def get_sector_analysis(self) -> Dict:
        """تحليل القطاعات"""
        if not self.alpha_vantage:
            return {}
        
        try:
            async with self.alpha_vantage as client:
                return await client.get_sector_performance()
        except Exception as e:
            logger.error(f"Error fetching sector analysis: {e}")
            return {}
    
    async def search_stocks(self, query: str) -> List[Dict]:
        """البحث عن الأسهم"""
        if not self.alpha_vantage:
            return await self.yahoo.search_symbols(query)
        
        try:
            async with self.alpha_vantage as client:
                return await client.search_symbol(query)
        except Exception as e:
            logger.error(f"Error searching stocks: {e}")
            return await self.yahoo.search_symbols(query)
    
    # ==================== بيانات السوق العامة ====================
    
    async def get_market_summary(self) -> Dict:
        """ملخص السوق"""
        indices = ["^GSPC", "^DJI", "^IXIC", "^RUT"]  # S&P 500, Dow Jones, NASDAQ, Russell 2000
        
        summary = {}
        for index in indices:
            try:
                quote = await self.get_live_price(index)
                summary[index] = {
                    "price": quote.get('price', 0),
                    "change": quote.get('change', 0),
                    "change_percent": quote.get('change_percent', 0)
                }
            except:
                pass
        
        return summary
    
    async def get_top_gainers_losers(self) -> Dict:
        """أكبر الرابحين والخاسرين"""
        # يمكن إضافة مصادر بيانات أخرى هنا
        common_symbols = await self.get_symbols()
        
        gainers = []
        losers = []
        
        for symbol in common_symbols[:100]:  
            try:
                quote = await self.get_live_price(symbol)
                change_pct = quote.get('change_percent', 0)
                
                if change_pct > 2:
                    gainers.append({
                        "symbol": symbol,
                        "change": change_pct,
                        "price": quote.get('price', 0)
                    })
                elif change_pct < -2:
                    losers.append({
                        "symbol": symbol,
                        "change": change_pct,
                        "price": quote.get('price', 0)
                    })
            except:
                continue
        
        return {
            "gainers": sorted(gainers, key=lambda x: x['change'], reverse=True)[:10],
            "losers": sorted(losers, key=lambda x: x['change'])[:10]
        }
    
    # ==================== دعم WebSocket ====================
    
    async def stream_live_data(
        self,
        symbol: str,
        interval: int = 5  # تحديث كل 5 ثواني
    ) -> AsyncGenerator[Dict, None]:
        """بث بيانات حية محاكاة"""
        while True:
            try:
                quote = await self.get_live_price(symbol)
                yield quote
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error in live stream: {e}")
                await asyncio.sleep(1)
    
    # ==================== أدوات الرسم البياني ====================
    
    async def get_chart_data(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1mo",
        indicators: List[Dict] = None
    ) -> Dict:
        """الحصول على بيانات الرسم البياني المتكاملة"""
        data = await self.calculate_indicators(symbol, timeframe, period, indicators)
        
        if "error" in data:
            return data
        
        # إعداد بيانات الرسم البياني
        chart_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": data["candles"],
            "indicators": data["indicators"],
            "analysis": await self.get_technical_analysis(symbol, timeframe, period),
            "company_info": await self.get_company_info(symbol),
            "current_quote": await self.get_live_price(symbol)
        }
        
        return chart_data