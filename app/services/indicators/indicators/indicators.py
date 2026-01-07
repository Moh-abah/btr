# trading_backend\app\services\indicators\indicators\indicators.py
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List

from app.services.indicators.base import BaseIndicator, IndicatorResult, IndicatorType
from app.services.indicators.registry import IndicatorRegistry









# ====================== مؤشرات متقدمة (Advanced Indicators) ======================

@IndicatorRegistry.register(
    name="supply_demand",
    display_name="Supply & Demand Zones",
    description="تحديد مناطق العرض والطلب بناءً على الشموع الانفجارية",
    category=IndicatorType.SUPPORT_RESISTANCE
)
class SupplyDemandIndicator(BaseIndicator):
    """مؤشر مناطق العرض والطلب"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 20, "threshold": 2.0}

    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['open', 'high', 'low', 'close']

    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 20)
        threshold = self.params.get("threshold", 2.0)

        # حساب حجم جسم الشمعة مقارنة بالمتوسط
        body = (data['close'] - data['open']).abs()
        avg_body = body.rolling(window=period).mean()
        
        # اكتشاف الشموع المتفجرة
        explosive = body > (avg_body * threshold)
        
        zones = []
        for i in range(1, len(data)):
            if explosive.iloc[i]:
                # المنطقة هي الشمعة التي سبقت الانفجار
                base_idx = i - 1
                is_bullish = data['close'].iloc[i] > data['open'].iloc[i]
                
                zones.append({
                    "type": "DZ" if is_bullish else "SZ",
                    "top": float(data['high'].iloc[base_idx]),
                    "bottom": float(data['low'].iloc[base_idx]),
                    "time": data.index[base_idx].isoformat() if hasattr(data.index[base_idx], 'isoformat') else str(data.index[base_idx])
                })

        return IndicatorResult(
            name=self.name,
            values=pd.Series(0, index=data.index),
            metadata={"zones": zones}
        )

@IndicatorRegistry.register(
    name="volume_climax",
    display_name="Volume Climax",
    description="تحديد شموع ذروة الفوليوم (المربعات الحمراء)",
    category=IndicatorType.VOLUME
)

@IndicatorRegistry.register(
    name="vol_climax_30s",
    display_name="Vol Climax 30s",
    category=IndicatorType.VOLUME
)
@IndicatorRegistry.register(
    name="vol_climax_1m",
    display_name="Vol Climax 1m",
    category=IndicatorType.VOLUME
)
@IndicatorRegistry.register(
    name="vol_climax_5m",
    display_name="Vol Climax 5m",
    category=IndicatorType.VOLUME
)
@IndicatorRegistry.register(
    name="vol_climax_15m",
    display_name="Vol Climax 15m",
    category=IndicatorType.VOLUME
)
@IndicatorRegistry.register(
    name="vol_climax_1h",
    display_name="Vol Climax 1h",
    category=IndicatorType.VOLUME
)
class VolumeClimaxIndicator(BaseIndicator):
    """مؤشر فوليوم الذروة"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 20, "std_mult": 2.0}

    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['high', 'low', 'volume']

    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 20)
        std_mult = self.params.get("std_mult", 2.0)

        vol_mean = data['volume'].rolling(window=period).mean()
        vol_std = data['volume'].rolling(window=period).std()
        
        # شرط الذروة: الفوليوم الحالي أكبر من (المتوسط + 2 انحراف معياري)
        climax_mask = data['volume'] > (vol_mean + (std_mult * vol_std))
        
        climax_points = []
        for i in range(len(data)):
            if climax_mask.iloc[i]:
                climax_points.append({
                    "time": data.index[i].isoformat() if hasattr(data.index[i], 'isoformat') else str(data.index[i]),
                    "high": float(data['high'].iloc[i]),
                    "low": float(data['low'].iloc[i])
                })

        return IndicatorResult(
            name=self.name,
            values=climax_mask.astype(int),
            metadata={"climax_points": climax_points}
        )

@IndicatorRegistry.register(
    name="harmonic_patterns",
    display_name="Harmonic Patterns",
    description="اكتشاف نماذج الهارمونيك (Gartley, Bat, etc.)",
    category=IndicatorType.TREND # أو PATTERN_RECOGNITION
)
class HarmonicIndicator(BaseIndicator):
    """مؤشر الهارمونيك المبسط"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"depth": 10, "error_rate": 0.1}

    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['high', 'low']

    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        depth = self.params.get("depth", 10)
        # خوارزمية البحث عن القمم والقيعان (ZigZag)
        pivots = []
        for i in range(depth, len(data) - depth):
            is_high = data['high'].iloc[i] == data['high'].iloc[i-depth:i+depth].max()
            is_low = data['low'].iloc[i] == data['low'].iloc[i-depth:i+depth].min()
            if is_high or is_low:
                pivots.append({
                    "type": "high" if is_high else "low",
                    "price": float(data['high'].iloc[i] if is_high else data['low'].iloc[i]),
                    "time": data.index[i].isoformat() if hasattr(data.index[i], 'isoformat') else str(data.index[i]),
                    "idx": i
                })

        # منطق اكتشاف النماذج (هنا نرسل الـ Pivots للفرونت أند ليرسم الخطوط)
        return IndicatorResult(
            name=self.name,
            values=pd.Series(0, index=data.index),
            metadata={"pivots": pivots}
        )




@IndicatorRegistry.register(
    name="hv_iv_analysis",
    display_name="HV/IV Options Strategy",
    description="تحليل التقلب التاريخي والضمني لاختيار استراتيجية الأوبشن",
    category=IndicatorType.VOLATILITY
)
class HVIVIndicator(BaseIndicator):
    """مؤشر HV/IV مع تقسيم المناطق الخمس"""

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "period": 20,          # فترة حساب HV (غالباً 20 يوم تداول)
            "lookback": 252,       # فترة حساب المستويات (سنة تداول كاملة)
            "current_iv": 25.0     # القيمة المدخلة من المستخدم للـ IV
        }

    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']

    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 20)
        lookback = self.params.get("lookback", 252)
        current_iv = self.params.get("current_iv", 0)

        # 1. حساب العوائد اليومية والتقلب التاريخي (HV)
        log_returns = np.log(data['close'] / data['close'].shift(1))
        hv = log_returns.rolling(window=period).std() * np.sqrt(252) * 100

        # 2. حساب مستويات المناطق (Percentiles) بناءً على التاريخ
        # سنقسم الـ HV التاريخي إلى 5 مناطق
        p20 = hv.rolling(window=lookback).quantile(0.20)
        p40 = hv.rolling(window=lookback).quantile(0.40)
        p60 = hv.rolling(window=lookback).quantile(0.60)
        p80 = hv.rolling(window=lookback).quantile(0.80)
        max_v = hv.rolling(window=lookback).max()

        # 3. تجهيز بيانات المناطق (للتظليل في الفرونت أند)
        areas = {
            "very_low": p20.tolist(),
            "low": p40.tolist(),
            "fair": p60.tolist(),
            "high": p80.tolist(),
            "very_high": max_v.tolist()
        }

        # تحديد مكان الـ IV الحالي بالنسبة للمناطق
        last_hv = hv.iloc[-1]
        status = "Fair"
        if current_iv < p20.iloc[-1]: status = "Very Low"
        elif current_iv < p40.iloc[-1]: status = "Low"
        elif current_iv < p60.iloc[-1]: status = "Fair"
        elif current_iv < p80.iloc[-1]: status = "High"
        else: status = "Very High"

        return IndicatorResult(
            name=self.name,
            values=hv, # الخط الأساسي هو HV
            metadata={
                "areas": areas,
                "current_iv": current_iv,
                "status": status,
                "iv_points": [{"time": data.index[-1].isoformat(), "value": current_iv}] # الدائرة السوداء
            }
        )


# ====================== مؤشرات الاتجاه ======================

# @IndicatorRegistry.register(
#     name="sma",
#     display_name="SMA",
#     description="المتوسط المتحرك البسيط",
#     category=IndicatorType.TREND
# )
# class SMAIndicator(BaseIndicator):
#     """المتوسط المتحرك البسيط"""
    
#     @classmethod
#     def get_default_params(cls) -> Dict[str, Any]:
#         return {"period": 20}
    
#     @classmethod
#     def get_required_columns(cls) -> List[str]:
#         return ['close']
    
#     def calculate(self, data: pd.DataFrame) -> IndicatorResult:
#         period = self.params.get("period", 20)
#         values = data['close'].rolling(window=period).mean()
        
#         return IndicatorResult(
#             name=self.name,
#             values=values,
#             metadata={"period": period}
#         )

@IndicatorRegistry.register(
    name="sma",
    display_name="SMA",
    description="المتوسط المتحرك البسيط",
    category=IndicatorType.TREND
)

@IndicatorRegistry.register(
    name="sma_8_1h",
    display_name="SMA 8 (1H)",
    category=IndicatorType.TREND
)
@IndicatorRegistry.register(
    name="sma_13_1h",
    display_name="SMA 13 (1H)",
    category=IndicatorType.TREND
)
@IndicatorRegistry.register(
    name="sma_21_1h",
    display_name="SMA 21 (1H)",
    category=IndicatorType.TREND
)
@IndicatorRegistry.register(
    name="sma_50_1h",
    display_name="SMA 50 (1H)",
    category=IndicatorType.TREND
)
class SMAIndicator(BaseIndicator):
    """إعدادات SMA المخصصة للـ 1H"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        # سنستخدم اسم الكلاس لاستخراج الفترة (خدعة برمجية)
        return {"period": 20} # سيتم تجاوزها بالمنطق أدناه أو استخدام الافتراضي

    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        # استخراج الفترة من الاسم: "sma_8_1h" -> 8
        try:
            period_str = self.name.split('_')[1]
            period = int(period_str)
        except:
            period = self.params.get("period", 20)
            
        values = data['close'].rolling(window=period).mean()
        
        return IndicatorResult(
            name=self.name,
            values=values,
            metadata={"period": period}
        )


@IndicatorRegistry.register(
    name="sma_fast",
    display_name="SMA Fast",
    description="المتوسط المتحرك البسيط السريع",
    category=IndicatorType.TREND
)
class SMAFastIndicator(BaseIndicator):
    """SMA سريع (فترة قصيرة)"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 10}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 10)
        values = data['close'].rolling(window=period).mean()
        
        return IndicatorResult(
            name=self.name,
            values=values,
            metadata={"period": period}
        )











@IndicatorRegistry.register(
    name="sma_slow",
    display_name="SMA Slow",
    description="المتوسط المتحرك البسيط البطيء",
    category=IndicatorType.TREND
)
class SMASlowIndicator(BaseIndicator):
    """SMA بطيء (فترة طويلة)"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 20}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 20)
        values = data['close'].rolling(window=period).mean()
        
        return IndicatorResult(
            name=self.name,
            values=values,
            metadata={"period": period}
        )










@IndicatorRegistry.register(
    name="ema",
    display_name="EMA",
    description="المتوسط المتحرك الأسي",
    category=IndicatorType.TREND
)
class EMAIndicator(BaseIndicator):
    """المتوسط المتحرك الأسي"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 20}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 20)
        values = data['close'].ewm(span=period, adjust=False).mean()
        
        return IndicatorResult(
            name=self.name,
            values=values,
            metadata={"period": period}
        )



@IndicatorRegistry.register(
    name="ema_21",
    display_name="EMA _9",
    description="المتوسط المتحرك الأسي",
    category=IndicatorType.TREND
)
class EMA21Indicator(BaseIndicator):
    """المتوسط المتحرك الأسي"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 21}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 21)
        values = data['close'].ewm(span=period, adjust=False).mean()
        
        return IndicatorResult(
            name=self.name,
            values=values,
            metadata={"period": period}
        )



@IndicatorRegistry.register(
    name="ema_9",
    display_name="EMA _9",
    description="المتوسط المتحرك الأسي",
    category=IndicatorType.TREND
)
class EMA9Indicator(BaseIndicator):
    """المتوسط المتحرك الأسي"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 9}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 9)
        values = data['close'].ewm(span=period, adjust=False).mean()
        
        return IndicatorResult(
            name=self.name,
            values=values,
            metadata={"period": period}
        )


@IndicatorRegistry.register(
    name="wma",
    display_name="WMA",
    description="المتوسط المتحرك المرجح",
    category=IndicatorType.TREND
)
class WMAIndicator(BaseIndicator):
    """المتوسط المتحرك المرجح"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 20}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 20)
        
        def wma(series):
            weights = np.arange(1, period + 1)
            return np.dot(series[-period:], weights) / weights.sum()
        
        values = data['close'].rolling(window=period).apply(wma, raw=True)
        
        return IndicatorResult(
            name=self.name,
            values=values,
            metadata={"period": period}
        )

# ====================== مؤشرات الزخم ======================





# ====================== مؤشر الزخم الجديد (Momentum) ======================
@IndicatorRegistry.register(
    name="momentum_5m",
    display_name="Momentum 5m (Period 10)",
    category=IndicatorType.MOMENTUM
)
@IndicatorRegistry.register(
    name="momentum_10m",
    display_name="Momentum 10m (Period 10)",
    category=IndicatorType.MOMENTUM
)
@IndicatorRegistry.register(
    name="momentum_15m",
    display_name="Momentum 15m (Period 10)",
    category=IndicatorType.MOMENTUM
)
@IndicatorRegistry.register(
    name="momentum_1h",
    display_name="Momentum 1H (Period 10)",
    category=IndicatorType.MOMENTUM
)
class MomentumIndicator(BaseIndicator):
    """مؤشر الزخم (Momentum Rate of Change)"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 10}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = int(self.params.get("period", 10))
        # Formula: ((Price - Price_N) / Price_N) * 100
        momentum = (data['close'] - data['close'].shift(period)) / data['close'].shift(period) * 100
        
        return IndicatorResult(
            name=self.name,
            values=momentum,
            metadata={"period": period}
        )




logger = logging.getLogger("RSI_DEBUG")

@IndicatorRegistry.register(
    name="rsi",
    display_name="RSI",
    description="مؤشر القوة النسبية",
    category=IndicatorType.MOMENTUM
)

@IndicatorRegistry.register(
    name="rsi_5m",
    display_name="RSI 5m",
    description="مؤشر القوة النسبية",
    category=IndicatorType.MOMENTUM
)

@IndicatorRegistry.register(
    name="rsi_15m",
    display_name="RSI 15m",
    description="مؤشر القوة النسبية",
    category=IndicatorType.MOMENTUM
)

@IndicatorRegistry.register(
    name="rsi_1h",
    display_name="RSI 1h",
    description="مؤشر القوة النسبية",
    category=IndicatorType.MOMENTUM
)

@IndicatorRegistry.register(
    name="rsi_2h",
    display_name="RSI 2h",
    description="مؤشر القوة النسبية",
    category=IndicatorType.MOMENTUM
)

class RSIIndicator(BaseIndicator):
    """مؤشر القوة النسبية"""

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "period": 14,
            "overbought": 70,
            "oversold": 30
        }

    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:

        logger.debug("🔵 [RSI] Starting RSI calculation")
        logger.debug(f"🔹 Prices count: {len(prices)}")
        logger.debug(f"🔹 Using period: {period}")

        # اختلافات الأسعار
        delta = prices.diff()
        logger.debug(f"🔹 Delta head:\n{delta.head(20)}")

        gain = delta.clip(lower=0).fillna(0)
        loss = -delta.clip(upper=0).fillna(0)

        logger.debug(f"🔹 Gain head:\n{gain.head(20)}")
        logger.debug(f"🔹 Loss head:\n{loss.head(20)}")

        # Wilder smoothing
        avg_gain = gain.ewm(alpha=1.0/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0/period, adjust=False).mean()

        logger.debug(f"🔹 Avg Gain head:\n{avg_gain.head(20)}")
        logger.debug(f"🔹 Avg Loss head:\n{avg_loss.head(20)}")

        with np.errstate(divide='ignore', invalid='ignore'):
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        logger.debug(f"🔹 RS head:\n{rs.head(20)}")
        logger.debug(f"🔹 Raw RSI head:\n{rsi.head(20)}")

        # معالجة الحالات الخاصة
        rsi[(avg_loss == 0) & (avg_gain > 0)] = 100
        rsi[(avg_gain == 0) & (avg_loss > 0)] = 0
        rsi[(avg_gain == 0) & (avg_loss == 0)] = 50

        logger.debug(f"🔹 Final RSI head:\n{rsi.head(20)}")

        return rsi

    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = int(self.params.get("period", 14))
        overbought = float(self.params.get("overbought", 70))
        oversold = float(self.params.get("oversold", 30))

        logger.debug("🟣 [RSI] Starting calculation() wrapper")
        logger.debug(f"🔹 Data columns: {data.columns.tolist()}")
        logger.debug(f"🔹 Close head:\n{data['close'].head(20)}")

        rsi_values = self._calculate_rsi(data["close"], period)

        logger.debug(f"🔹 RSI after calculation:\n{rsi_values.head(20)}")

        # الإشارات
        signals = pd.Series(0, index=rsi_values.index, dtype=int)
        signals[rsi_values > overbought] = -1
        signals[rsi_values < oversold] = 1

        logger.debug(f"🔹 Signals head:\n{signals.head(20)}")

        logger.info("✅ [RSI] Calculation completed successfully")

        return IndicatorResult(
            name=self.name,
            values=rsi_values,
            signals=signals,
            metadata={
                "period": period,
                "overbought": overbought,
                "oversold": oversold
            }
        )

@IndicatorRegistry.register(
    name="macd",
    display_name="MACD",
    description="مؤشر التقارب والتباعد للمتوسطات المتحركة",
    category=IndicatorType.MOMENTUM
)

@IndicatorRegistry.register(
    name="macd_5m",
    display_name="frame 5m",
    description="مؤشر التقارب والتباعد للمتوسطات المتحركة",
    category=IndicatorType.MOMENTUM
)

@IndicatorRegistry.register(
    name="macd_15m",
    display_name="frame 15m",
    description="مؤشر التقارب والتباعد للمتوسطات المتحركة",
    category=IndicatorType.MOMENTUM
)

@IndicatorRegistry.register(
    name="macd_1h",
    display_name="frame 1h",
    description="مؤشر التقارب والتباعد للمتوسطات المتحركة",
    category=IndicatorType.MOMENTUM
)

@IndicatorRegistry.register(
    name="macd_2h",
    display_name="frame 2h",
    description="مؤشر التقارب والتباعد للمتوسطات المتحركة",
    category=IndicatorType.MOMENTUM
)


class MACDIndicator(BaseIndicator):
    """مؤشر MACD"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "fast": 12,
            "slow": 26,
            "signal": 9
        }
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        fast_period = self.params.get("fast", 12)
        slow_period = self.params.get("slow", 26)
        signal_period = self.params.get("signal", 9)
        
        # حساب المتوسطات المتحركة الأسية
        ema_fast = data['close'].ewm(span=fast_period, adjust=False).mean()
        ema_slow = data['close'].ewm(span=slow_period, adjust=False).mean()
        
        # حساب MACD وخط الإشارة
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        # توليد إشارات
        signals = pd.Series(0, index=macd_line.index)
        cross_up = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        cross_down = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
        
        signals[cross_up] = 1    # إشارة شراء
        signals[cross_down] = -1 # إشارة بيع
        
        return IndicatorResult(
            name=self.name,
            values=macd_line,
            signals=signals,
            metadata={
                "macd_line": macd_line.tolist(),
                "signal_line": signal_line.tolist(),
                "histogram": histogram.tolist(),
                "fast": fast_period,
                "slow": slow_period,
                "signal": signal_period
            }
        )

@IndicatorRegistry.register(
    name="stochastic",
    display_name="Stochastic",
    description="المؤشر العشوائي",
    category=IndicatorType.MOMENTUM
)
class StochasticIndicator(BaseIndicator):
    """المؤشر العشوائي"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "k_period": 14,
            "d_period": 3,
            "smooth": 3,
            "overbought": 80,
            "oversold": 20
        }
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['high', 'low', 'close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        k_period = self.params.get("k_period", 14)
        d_period = self.params.get("d_period", 3)
        smooth = self.params.get("smooth", 3)
        overbought = self.params.get("overbought", 80)
        oversold = self.params.get("oversold", 20)
        
        # حساب %K
        low_min = data['low'].rolling(window=k_period).min()
        high_max = data['high'].rolling(window=k_period).max()
        
        k_line = 100 * ((data['close'] - low_min) / (high_max - low_min))
        
        # تنعيم %K
        k_smoothed = k_line.rolling(window=smooth).mean()
        
        # حساب %D (متوسط %K)
        d_line = k_smoothed.rolling(window=d_period).mean()
        
        # توليد إشارات
        signals = pd.Series(0, index=k_line.index)
        signals[(k_smoothed < oversold) & (d_line < oversold)] = 1      # شراء
        signals[(k_smoothed > overbought) & (d_line > overbought)] = -1 # بيع
        
        return IndicatorResult(
            name=self.name,
            values=k_smoothed,
            signals=signals,
            metadata={
                "k_line": k_smoothed.tolist(),
                "d_line": d_line.tolist(),
                "k_period": k_period,
                "d_period": d_period,
                "smooth": smooth,
                "overbought": overbought,
                "oversold": oversold
            }
        )

# ====================== مؤشرات التقلب ======================

@IndicatorRegistry.register(
    name="bollinger_bands",
    display_name="Bollinger Bands",
    description="أشرطة بولينجر",
    category=IndicatorType.VOLATILITY
)

@IndicatorRegistry.register(
    name="bollinger_5m",
    display_name="Bollinger Bands 5m",
    category=IndicatorType.VOLATILITY
)
@IndicatorRegistry.register(
    name="bollinger_15m",
    display_name="Bollinger Bands 15m",
    category=IndicatorType.VOLATILITY
)

class BollingerBandsIndicator(BaseIndicator):
    """أشرطة بولينجر"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "period": 20,
            "std": 2
        }
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 20)
        std_dev = self.params.get("std", 2)
        
        # حساب المتوسط المتحرك البسيط
        sma = data['close'].rolling(window=period).mean()
        
        # حساب الانحراف المعياري
        rolling_std = data['close'].rolling(window=period).std()
        
        # حساب النطاقات
        upper_band = sma + (rolling_std * std_dev)
        lower_band = sma - (rolling_std * std_dev)
        
        # حساب عرض النطاق
        band_width = (upper_band - lower_band) / sma
        
        # توليد إشارات
        signals = pd.Series(0, index=data.index)
        signals[data['close'] < lower_band] = 1      # شراء (أسفل النطاق السفلي)
        signals[data['close'] > upper_band] = -1     # بيع (فوق النطاق العلوي)
        
        return IndicatorResult(
            name=self.name,
            values=sma,
            signals=signals,
            metadata={
                "sma": sma.tolist(),
                "upper_band": upper_band.tolist(),
                "lower_band": lower_band.tolist(),
                "band_width": band_width.tolist(),
                "period": period,
                "std": std_dev
            }
        )

@IndicatorRegistry.register(
    name="atr",
    display_name="ATR",
    description="مؤشر المدى الحقيقي المتوسط",
    category=IndicatorType.VOLATILITY
)
class ATRIndicator(BaseIndicator):
    """مؤشر المدى الحقيقي المتوسط"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 14}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['high', 'low', 'close']
    
    def _calculate_true_range(self, data: pd.DataFrame) -> pd.Series:
        """حساب المدى الحقيقي"""
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift(1))
        low_close = abs(data['low'] - data['close'].shift(1))
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1)
        return true_range.max(axis=1)
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 14)
        
        # حساب المدى الحقيقي
        true_range = self._calculate_true_range(data)
        
        # حساب ATR
        atr_values = true_range.rolling(window=period).mean()
        
        return IndicatorResult(
            name=self.name,
            values=atr_values,
            metadata={"period": period}
        )

# ====================== مؤشرات الحجم ======================

@IndicatorRegistry.register(
    name="vwap",
    display_name="VWAP",
    description="متوسط السعر المرجح بالحجم",
    category=IndicatorType.VOLUME
)
class VWAPIndicator(BaseIndicator):
    """متوسط السعر المرجح بالحجم"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"period": 20}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['high', 'low', 'close', 'volume']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        period = self.params.get("period", 20)
        
        # حساب السعر النموذجي
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        
        # حساب VWAP
        vwap = (typical_price * data['volume']).rolling(window=period).sum() / \
               data['volume'].rolling(window=period).sum()
        
        # إشارات عندما يكون السعر تحت/فوق VWAP
        signals = pd.Series(0, index=data.index)
        signals[data['close'] < vwap] = 1    # شراء (السعر تحت VWAP)
        signals[data['close'] > vwap] = -1   # بيع (السعر فوق VWAP)
        
        return IndicatorResult(
            name=self.name,
            values=vwap,
            signals=signals,
            metadata={"period": period}
        )

@IndicatorRegistry.register(
    name="obv",
    display_name="OBV",
    description="مؤشر حجم الرصيد",
    category=IndicatorType.VOLUME
)
class OBVIndicator(BaseIndicator):
    """مؤشر حجم الرصيد"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {}
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['close', 'volume']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        # تحويل البيانات إلى مصفوفات numpy لتجنب مشكلة .iloc
        close_prices = data['close'].values
        volumes = data['volume'].values
        
        obv = np.zeros(len(data))
        
        # حساب OBV باستخدام المصفوفات
        for i in range(1, len(data)):
            if close_prices[i] > close_prices[i-1]:
                obv[i] = obv[i-1] + volumes[i]
            elif close_prices[i] < close_prices[i-1]:
                obv[i] = obv[i-1] - volumes[i]
            else:
                obv[i] = obv[i-1]
        
        # تحويل إلى pandas Series
        obv_series = pd.Series(obv, index=data.index)
        
        # حساب اتجاه OBV
        obv_sma = obv_series.rolling(window=20).mean()
        signals = pd.Series(0, index=data.index)
        signals[obv_series > obv_sma] = 1    # اتجاه صاعد
        signals[obv_series < obv_sma] = -1   # اتجاه هابط
        
        return IndicatorResult(
            name=self.name,
            values=obv_series,
            signals=signals,
            metadata={}
        )

# ====================== مؤشرات دعم ومقاومة ======================

@IndicatorRegistry.register(
    name="pivot_points",
    display_name="Pivot Points",
    description="نقاط المحورية",
    category=IndicatorType.SUPPORT_RESISTANCE
)
class PivotPointsIndicator(BaseIndicator):
    """نقاط المحورية"""
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {"method": "standard"}  # standard, fibonacci, woodie
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        return ['high', 'low', 'close']
    
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:
        method = self.params.get("method", "standard")
        
        # تحويل البيانات إلى مصفوفات numpy
        high_prices = data['high'].values
        low_prices = data['low'].values
        close_prices = data['close'].values
        
        # حساب نقاط المحورية لكل فترة
        pivot_points = np.zeros(len(data))
        resistance1 = np.zeros(len(data))
        support1 = np.zeros(len(data))
        
        for i in range(len(data)):
            if i >= 1:
                prev_high = high_prices[i-1]
                prev_low = low_prices[i-1]
                prev_close = close_prices[i-1]
                
                # نقطة المحورية
                pivot = (prev_high + prev_low + prev_close) / 3
                pivot_points[i] = pivot
                
                # حساب الدعم والمقاومة
                if method == "standard":
                    resistance1[i] = (2 * pivot) - prev_low
                    support1[i] = (2 * pivot) - prev_high
                elif method == "fibonacci":
                    resistance1[i] = pivot + 0.382 * (prev_high - prev_low)
                    support1[i] = pivot - 0.382 * (prev_high - prev_low)
        
        # تحويل إلى pandas Series
        pivot_points_series = pd.Series(pivot_points, index=data.index)
        resistance1_series = pd.Series(resistance1, index=data.index)
        support1_series = pd.Series(support1, index=data.index)
        
        # توليد إشارات بناءً على موقف السعر من نقاط المحورية
        signals = pd.Series(0, index=data.index)
        signals[close_prices < support1] = 1        # شراء عند الدعم
        signals[close_prices > resistance1] = -1    # بيع عند المقاومة
        
        return IndicatorResult(
            name=self.name,
            values=pivot_points_series,
            signals=signals,
            metadata={
                "pivot_points": pivot_points_series.tolist(),
                "resistance1": resistance1_series.tolist(),
                "support1": support1_series.tolist(),
                "method": method
            }
        )