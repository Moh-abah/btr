


# app\services\indicators\base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, validator
import json

class IndicatorType(Enum):
    """أنواع المؤشرات المتاحة"""
    TREND = "trend"          # اتجاه
    MOMENTUM = "momentum"    # زخم
    VOLATILITY = "volatility" # تقلب
    VOLUME = "volume"        # حجم
    SUPPORT_RESISTANCE = "support_resistance" # دعم ومقاومة
    CUSTOM = "custom"        # مخصص

class Timeframe(Enum):
    """الإطارات الزمنية المدعومة"""
    TICK = "tick"
    MIN1 = "1m"
    MIN5 = "5m"
    MIN15 = "15m"
    MIN30 = "30m"
    HOUR1 = "1h"
    HOUR4 = "4h"
    DAY1 = "1d"
    WEEK1 = "1w"
    MONTH1 = "1M"

@dataclass
class IndicatorResult:
    """نتيجة حساب المؤشر"""
    name: str
    values: pd.Series
    signals: Optional[pd.Series] = None  # إشارات التداول (-1, 0, 1)
    metadata: Dict[str, Any] = field(default_factory=dict)      # بيانات إضافية
    
    def __post_init__(self):
        """تأكيد أن القيم هي Series"""
        if not isinstance(self.values, pd.Series):
            if isinstance(self.values, (list, np.ndarray)):
                # إذا كانت قائمة أو مصفوفة numpy، تحويلها إلى Series
                self.values = pd.Series(self.values)
            else:
                raise TypeError(f"values must be a pandas Series, got {type(self.values)}")
    
    def to_dict(self) -> Dict:

        if not self.values.empty:
            values_dict = {
                "data": self.values.tolist(),
                "index": self.values.index.tolist(),
                "dtype": str(self.values.dtype)
            }
        else:
            values_dict = {"data": [], "index": [], "dtype": "float64"}
  
        signals_dict = None
        if self.signals is not None and not self.signals.empty:
            signals_dict = {
                "data": self.signals.tolist(),
                "index": self.signals.index.tolist(),
                "dtype": str(self.signals.dtype)
            }
        
        return {
            "name": self.name,
            "values": values_dict,
            "signals": signals_dict,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'IndicatorResult':
        """إنشاء IndicatorResult من قاموس"""
        # تحويل القيم إلى Series
        if "values" in data and isinstance(data["values"], dict):
            values_data = data["values"]
            values_series = pd.Series(
                values_data.get("data", []),
                index=pd.to_datetime(values_data.get("index", [])) if values_data.get("index") else None
            )
        else:
            values_series = pd.Series(data.get("values", []))
        
        # تحويل الإشارات إذا وجدت
        signals_series = None
        if data.get("signals") and isinstance(data["signals"], dict):
            signals_data = data["signals"]
            signals_series = pd.Series(
                signals_data.get("data", []),
                index=pd.to_datetime(signals_data.get("index", [])) if signals_data.get("index") else None
            )
        
        return cls(
            name=data["name"],
            values=values_series,
            signals=signals_series,
            metadata=data.get("metadata", {})
        )
    
 
    def to_json(self) -> str:
        """تحويل النتيجة إلى JSON"""
        import json
        from datetime import datetime
        
        def convert_to_serializable(obj):
            if isinstance(obj, (pd.Timestamp, datetime)):
                return obj.isoformat()
            elif isinstance(obj, pd.Series):
                return obj.tolist()
            elif isinstance(obj, pd.Index):
                return obj.tolist()
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.generic):
                return obj.item()
            return obj
        
        return json.dumps(self.to_dict(), default=convert_to_serializable)


    @classmethod
    def from_json(cls, json_str: str) -> 'IndicatorResult':
        """إنشاء IndicatorResult من JSON"""
        return cls.from_dict(json.loads(json_str))


class IndicatorConfig(BaseModel):
    """تكوين المؤشر"""
    name: str
    type: IndicatorType
    params: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    timeframe: Timeframe = Timeframe.MIN15
    display_name: Optional[str] = None
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            pd.Series: lambda v: v.tolist() if not v.empty else []
        }
    )
    
    @field_validator('params')
    @classmethod
    def validate_params(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        """التحقق من صحة المعاملات"""
        # معلومات المجال متاحة في info
        name = info.data.get('name', '').lower() if info.data else ''
        
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
                if param in v:
                    param_value = v[param]
                    if param_value is not None and not min_val <= param_value <= max_val:
                        raise ValueError(
                            f"Parameter {param} for {name} must be between "
                            f"{min_val} and {max_val}"
                        )
        return v
    


    
class BaseIndicator(ABC):

    
    def __init__(self, config: IndicatorConfig):
        self.config = config
        self.name = config.name
        self.params = config.params
        self.timeframe = config.timeframe
        self._validate_params()
        self._last_result: Optional[IndicatorResult] = None
    
    def _validate_params(self):
    
        pass
    
    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> IndicatorResult:

        pass
    
    def calculate_and_cache(self, data: pd.DataFrame) -> IndicatorResult:

        result = self.calculate(data)
        self._last_result = result
        return result
    
    def get_last_result(self) -> Optional[IndicatorResult]:

        return self._last_result
    
    def generate_signals(self, values: pd.Series, data: Optional[pd.DataFrame] = None) -> pd.Series:

    
        return pd.Series([0] * len(values), index=values.index)
    
    @classmethod
    def get_required_columns(cls) -> List[str]:
        """
        الأعمدة المطلوبة من DataFrame
        
        Returns:
            List[str]: قائمة بالأعمدة المطلوبة
        """
        return ['close']  # افتراضياً نحتاج عمود الإغلاق
    
    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        """
        المعاملات الافتراضية للمؤشر
        
        Returns:
            Dict[str, Any]: قاموس بالمعاملات الافتراضية
        """
        return {}


    def validate_data(self, data: pd.DataFrame) -> bool:
        """التحقق من صحة البيانات المدخلة"""
        if data.empty:
            raise ValueError("DataFrame is empty")
        
        required_cols = self.get_required_columns()
        missing_cols = [col for col in required_cols if col not in data.columns]
        
        if missing_cols:
            raise ValueError(
                f"Missing required columns for indicator {self.name}: {missing_cols}"
            )
        
        return True


