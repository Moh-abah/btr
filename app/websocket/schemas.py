from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import json

class StreamDataType(str, Enum):
    """أنواع البيانات في البث اللحظي"""
    PRICE = "price"              # بيانات السعر
    INDICATOR = "indicator"      # بيانات المؤشر
    CONDITION = "condition"      # حالة الشرط
    SIGNAL = "signal"            # إشارة تداول
    ENTRY_POINT = "entry_point"  # نقطة دخول
    STATUS = "status"           # حالة النظام
    FILTER = "filter"           # نتيجة فلترة

class StreamMessage(BaseModel):
    """رسالة البث اللحظي"""
    type: StreamDataType
    symbol: str
    timeframe: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_json(self) -> str:
        """تحويل الرسالة إلى JSON"""
        return json.dumps({
            "type": self.type,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata
        })

class PriceStreamData(BaseModel):
    """بيانات السعر للبث"""
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None  # متوسط السعر المرجح بالحجم
    timestamp: datetime

class IndicatorStreamData(BaseModel):
    """بيانات المؤشر للبث"""
    name: str
    value: float
    previous_value: Optional[float] = None
    values: Optional[List[float]] = None  # آخر 20 قيمة للرسم
    metadata: Optional[Dict[str, Any]] = None
    signal: Optional[int] = None  # -1, 0, 1

class ConditionStreamData(BaseModel):
    """حالة شرط للبث"""
    name: str
    is_met: bool
    description: str
    current_value: float
    threshold: float
    conditions: List[Dict[str, Any]]  # الشروط الفرعية
    confidence: float = 1.0

class SignalStreamData(BaseModel):
    """إشارة تداول للبث"""
    type: str  # entry, exit
    action: str  # buy, sell, close
    strength: float
    price: float
    timestamp: datetime
    conditions: List[ConditionStreamData]
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class EntryPointStreamData(BaseModel):
    """نقطة دخول للبث"""
    price: float
    stop_loss: float
    take_profit: float
    confidence: float
    risk_reward_ratio: float
    position_size: float  # نسبة من رأس المال
    timestamp: datetime