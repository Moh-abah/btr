
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime
import pandas as pd
import numpy as np
import logging

# استيراد التكوين والأدوات المساعدة للتفكير فقط
from .schemas import (
    StrategyConfig, Condition, CompositeCondition, PositionSide
)
from .conditions import ConditionEvaluator
from app.services.indicators import apply_indicators

logger = logging.getLogger(__name__)

class DecisionAction(Enum):
    """الأفعال المجردة التي يمكن للقرار اتخاذها"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

@dataclass
class Decision:
    timestamp: datetime
    action: DecisionAction
    confidence: float
    reason: str
    metadata: Dict[str, Any] = None

class StrategyEngine:
    """
    محرك الاستراتيجية (Decision Provider)
    يستخدم منطق استخراج البيانات الموثق من النسخة السابقة.
    """
    
    def __init__(self, strategy_config: StrategyConfig):
        self.config = strategy_config
        self.condition_evaluator = ConditionEvaluator()
        self.current_data_frame = None
        self.full_data = None

    async def run(self, market_context: pd.DataFrame) -> Decision:
        if market_context.empty or len(market_context) < 2:
            return self._create_hold_decision("Insufficient data")

        try:
            # 1. تحضير البيانات باستخدام المنطق القديم (القوي)
            df_clean = await self._prepare_indicators(market_context)
            self.current_data_frame = df_clean
            
            # 2. عملية التفكير
            current_index = len(df_clean) - 1
            
            # التحقق من شروط الخروج
            exit_reason = self._check_exit_conditions(df_clean, current_index)
            if exit_reason:
                return Decision(
                    timestamp=df_clean.index[current_index],
                    action=DecisionAction.HOLD,
                    confidence=1.0,
                    reason=f"Exit Condition: {exit_reason}",
                    metadata={"trigger": "exit_rule"}
                )
            
            # التحقق من شروط الدخول
            decision = self._determine_trend(df_clean, current_index)
            return decision

        except Exception as e:
            logger.exception(f"Strategy Engine Error: {e}")
            return self._create_hold_decision(f"Error: {str(e)}")

    async def _prepare_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        إعداد المؤشرات.
        تم تعديل هذه الدالة لاستخدام منطق الاستخراج من الكود السابق (core.py)
        لأنه الأكثر ثباتاً.
        """
        try:

            if hasattr(self, 'full_data') and self.full_data is not None:
                return self.full_data.iloc[:len(data)]            
            # استدعاء apply_indicators
            all_indicators = apply_indicators(
                dataframe=data,
                indicators_config=self.config.indicators,
                use_cache=False,
                return_raw=True
            )

            # إنشاء نسخة من البيانات لإضافة المؤشرات إليها
            df = data.copy()
            
            # تحديد المؤشرات المطلوبة
            required_indicators = list({cfg.name for cfg in self.config.indicators})
            
            # جلب مؤشرات القواعد أيضاً
            for rule in self.config.entry_rules + self.config.exit_rules + self.config.filter_rules:
                condition = rule.condition
                conditions_list = [condition]
                if isinstance(condition, CompositeCondition):
                    conditions_list = condition.conditions
                for cond in conditions_list:
                    for val in [cond.left_value, cond.right_value]:
                        if isinstance(val, str) and val.startswith("indicator:"):
                            required_indicators.append(val.split(":")[1])

            required_indicators = list(set(required_indicators))
            logger.info(f"📋 Required Indicators: {required_indicators}")

            # حلقة المعالجة (منطق مشابه للكود السابق)
            for ind_name in required_indicators:
                raw_values: list = [None] * len(data)
                
                if ind_name in all_indicators:
                    result = all_indicators[ind_name]
                    
                    # ✅ هنا منطقك السابق: التعامل مع هيكل النتائج المتعدد
                    # معالجة IndicatorResult
                    # (نفترض هنا التعامل مع Dict لأن return_raw=True)
                    
                    if isinstance(result, dict):
                        # محاولة استخراج القائمة من المسارات المتعددة (كما في كودك السابق)
                        raw_values = result.get("values", {}).get("data", [None])
                        
                        # إذا لم تكن قائمة، نحاول استخراجها بطريقة أخرى
                        if not isinstance(raw_values, list):
                             raw_values = result.get("data", [None])
                             
                    elif isinstance(result, list):
                        raw_values = result
                    elif isinstance(result, pd.Series):
                        raw_values = result.tolist()
                
                # Padding لضمان تطابق الطول
                padding_len = max(0, len(data) - len(raw_values))
                series_values = [None] * padding_len + raw_values[:len(data)]
                
                # إضافة العمود للـ DataFrame
                df[ind_name] = pd.Series(series_values, index=data.index)

            return df

        except Exception as e:
            logger.error(f"Indicator preparation failed: {e}")
            return data

    def _check_exit_conditions(self, data: pd.DataFrame, index: int) -> Optional[str]:
        if not self.config.exit_rules:
            return None
        for rule in self.config.exit_rules:
            if not rule.enabled:
                continue
            if self._evaluate_rule_condition(rule.condition, data, index):
                return rule.name
        return None

    def _determine_trend(self, data: pd.DataFrame, index: int) -> Decision:
        long_score = 0.0
        short_score = 0.0
        active_reason = "No clear trend direction"

        for rule in self.config.entry_rules:
            if rule.enabled and rule.position_side in [PositionSide.LONG, PositionSide.BOTH]:
                if self._evaluate_rule_condition(rule.condition, data, index):
                    long_score += rule.weight
                    active_reason = rule.name

        for rule in self.config.entry_rules:
            if rule.enabled and rule.position_side in [PositionSide.SHORT, PositionSide.BOTH]:
                if self._evaluate_rule_condition(rule.condition, data, index):
                    short_score += rule.weight
                    active_reason = rule.name

        if long_score > short_score and long_score > 0:
            return Decision(
                timestamp=data.index[index],
                action=DecisionAction.BUY,
                confidence=min(long_score, 1.0),
                reason=active_reason,
                metadata={"score": long_score}
            )
        elif short_score > long_score and short_score > 0:
            return Decision(
                timestamp=data.index[index],
                action=DecisionAction.SELL,
                confidence=min(short_score, 1.0),
                reason=active_reason,
                metadata={"score": short_score}
            )
        else:
            return self._create_hold_decision("No clear trend direction")

    def _evaluate_rule_condition(self, condition: Any, data: pd.DataFrame, index: int) -> bool:
        """
        تقييم الشرط.
        البيانات الآن موجودة داخل df كأعمدة نظيفة (تم استخراجها في _prepare_indicators)
        """
        try:
            indicators_dict = {}
            indicator_names = [ind.name for ind in self.config.indicators]
            
            for ind_name in indicator_names:
                if ind_name in data.columns:
                    indicators_dict[ind_name] = data[ind_name]
            
            if isinstance(condition, Condition) or isinstance(condition, CompositeCondition):
                return self.condition_evaluator.evaluate(
                    condition,
                    data,
                    indicators_dict,
                    index
                )
            return False
        except Exception as e:
            print(f"[Error] Evaluation Failed: {e}")
            return False

    def _create_hold_decision(self, reason: str) -> Decision:
        return Decision(
            timestamp=datetime.now(),
            action=DecisionAction.HOLD,
            confidence=0.0,
            reason=reason
        )