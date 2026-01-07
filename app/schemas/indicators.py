"""
مخططات البيانات للشارت والمؤشرات
"""
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator

class Timeframe(str, Enum):
    MIN1 = "1m"
    MIN5 = "5m"
    MIN15 = "15m"
    MIN30 = "30m"
    HOUR1 = "1h"
    HOUR4 = "4h"
    DAY1 = "1d"

class MarketType(str, Enum):
    CRYPTO = "crypto"
    STOCKS = "stocks"
    FOREX = "forex"

class IndicatorType(str, Enum):
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    SUPPORT = "support"

class IndicatorConfig(BaseModel):
    """تكوين المؤشر"""
    name: str = Field(..., description="اسم المؤشر")
    type: IndicatorType = Field(..., description="نوع المؤشر")
    params: Dict[str, Any] = Field(default_factory=dict, description="معاملات المؤشر")
    enabled: bool = Field(default=True, description="تفعيل المؤشر")
    display_name: Optional[str] = Field(None, description="اسم العرض")
    
    @validator('params')
    def validate_params(cls, v, values):
        """التحقق من صحة المعاملات"""
        name = values.get('name', '').lower()
        
        # قيود لكل مؤشر
        constraints = {
            'rsi': {'period': (5, 100), 'overbought': (50, 100), 'oversold': (0, 50)},
            'ema': {'period': (1, 500)},
            'macd': {'fast': (5, 50), 'slow': (10, 100), 'signal': (5, 50)},
            'bb': {'period': (5, 100), 'std': (1, 5)},
            'atr': {'period': (5, 100)},
        }
        
        if name in constraints:
            for param, (min_val, max_val) in constraints[name].items():
                if param in v and v[param] is not None:
                    if not min_val <= v[param] <= max_val:
                        raise ValueError(
                            f"Parameter {param} for {name} must be between {min_val} and {max_val}"
                        )
        return v

class ChartSubscription(BaseModel):
    """اشتراك الشارت"""
    symbol: str = Field(..., description="رمز التداول")
    timeframe: Timeframe = Field(default=Timeframe.MIN15, description="الإطار الزمني")
    market: MarketType = Field(default=MarketType.CRYPTO, description="نوع السوق")
    indicators: List[IndicatorConfig] = Field(default_factory=list, description="قائمة المؤشرات")

class CandleData(BaseModel):
    """بيانات الشمعة"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class IndicatorResult(BaseModel):
    """نتيجة المؤشر"""
    name: str
    values: List[Optional[float]]
    signals: Optional[List[int]] = None
    metadata: Dict[str, Any] = {}

class ChartData(BaseModel):
    """بيانات الشارت الكاملة"""
    symbol: str
    timeframe: Timeframe
    market: MarketType
    candles: List[CandleData]
    indicators: List[IndicatorResult]
    metadata: Dict[str, Any]

class PriceUpdate(BaseModel):
    """تحديث السعر الحي"""
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    change: Optional[float] = None