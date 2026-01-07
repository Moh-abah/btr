

# app/services/strategy/conditions.py

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from .schemas import Condition, CompositeCondition, Operator, ConditionType
import logging
logger = logging.getLogger(__name__)

class ConditionEvaluator:
    """محرك تقييم الشروط"""
    
    def __init__(self):
        self.operator_functions = {
            Operator.GREATER_THAN: lambda x, y: x > y,
            Operator.GREATER_THAN_EQUAL: lambda x, y: x >= y,
            Operator.LESS_THAN: lambda x, y: x < y,
            Operator.LESS_THAN_EQUAL: lambda x, y: x <= y,
            Operator.EQUAL: lambda x, y: x == y,
            Operator.NOT_EQUAL: lambda x, y: x != y,
            Operator.CROSSOVER_ABOVE: self._crossover_above,
            Operator.CROSSOVER_BELOW: self._crossover_below,
        }

    def set_indicators_data(self, indicators_data):
        if not isinstance(indicators_data, dict):
            logger.warning(f"Expected dict for indicators_data but got {type(indicators_data)}. Using empty dict.")
            indicators_data = {}
        self.indicators_data = indicators_data
        logger.debug(f"Indicators data set: {list(self.indicators_data.keys())}")


    # =============================
    # Evaluate condition
    # =============================
    

    # def evaluate(
    #     self,
    #     condition: Condition,
    #     data: pd.DataFrame,
    #     indicators: dict,  # الآن مؤكد dict[str, pd.Series]
    #     current_index: int
    # ) -> bool:


    #     if not isinstance(indicators, dict):
    #         logger.error(f"Expected indicators to be dict, got {type(indicators)}. Returning False.")
    #         return False


    #     if current_index <= 0:
    #         #logger.debug(f"Index {current_index} is too small, returning False")
    #         return False

    #     left_value = self._get_value(condition.left_value, data, indicators, current_index)
    #     right_value = self._get_value(condition.right_value, data, indicators, current_index)
    #     # logger.debug(f"Left value: {left_value}, Right value: {right_value}")

    #     if left_value is None or right_value is None:
    #         # logger.debug(f"Missing values: left={left_value}, right={right_value}")
    #         return False

    #     operator_func = self.operator_functions.get(condition.operator)
    #     if not operator_func:
    #         raise ValueError(f"Unknown operator: {condition.operator}")

    #     if condition.operator in [Operator.CROSSOVER_ABOVE, Operator.CROSSOVER_BELOW]:
    #         prev_left_value = self._get_value(condition.left_value, data, indicators, current_index - 1)
    #         prev_right_value = self._get_value(condition.right_value, data, indicators, current_index - 1)
    #         if prev_left_value is None or prev_right_value is None:
    #             return False
    #         return operator_func(left_value, right_value, prev_left_value, prev_right_value)
    #     else:
    #         return operator_func(left_value, right_value)

    def evaluate(
        self,
        condition: Union[Condition, CompositeCondition],  # ✅ تقبل كليهما
        data: pd.DataFrame,
        indicators: dict,
        current_index: int
    ) -> bool:
        # 1. إذا كان CompositeCondition
        if isinstance(condition, CompositeCondition):
            if condition.type in ["logical_and", "and"]:
                # جميع الشروط يجب أن تكون True
                for sub_condition in condition.conditions:
                    if not self.evaluate(sub_condition, data, indicators, current_index):
                        return False
                return True
            elif condition.type in ["logical_or", "or"]:
                # يكفي شرط واحد True
                for sub_condition in condition.conditions:
                    if self.evaluate(sub_condition, data, indicators, current_index):
                        return True
                return False
            else:
                logger.error(f"Unknown composite condition type: {condition.type}")
                return False
        
        # 2. إذا كان Condition عادي
        elif isinstance(condition, Condition):
            if current_index <= 0:
                return False

            left_value = self._get_value(condition.left_value, data, indicators, current_index)
            right_value = self._get_value(condition.right_value, data, indicators, current_index)

            if left_value is None or right_value is None:
                return False

            operator_func = self.operator_functions.get(condition.operator)
            if not operator_func:
                raise ValueError(f"Unknown operator: {condition.operator}")

            if condition.operator in [Operator.CROSSOVER_ABOVE, Operator.CROSSOVER_BELOW]:
                prev_left_value = self._get_value(condition.left_value, data, indicators, current_index - 1)
                prev_right_value = self._get_value(condition.right_value, data, indicators, current_index - 1)
                if prev_left_value is None or prev_right_value is None:
                    return False
                return operator_func(left_value, right_value, prev_left_value, prev_right_value)
            else:
                return operator_func(left_value, right_value)
        
        # 3. نوع غير معروف
        else:
            logger.error(f"Unknown condition type: {type(condition)}")
            return False        
        

    def evaluate_composite(
        self,
        composite: CompositeCondition,
        data: pd.DataFrame,
        indicators: Dict[str, pd.Series],
        current_index: int
    ) -> bool:
        """
        تقييم شرط مركب
        
        Args:
            composite: الشرط المركب
            data: بيانات السوق
            indicators: نتائج المؤشرات
            current_index: الفهرس الحالي
            
        Returns:
            bool: نتيجة التقييم
        """
        # logger.debug(f"Evaluating composite condition at index {current_index}")
        results = []
        
        for i, condition in enumerate(composite.conditions):
            if isinstance(condition, Condition):
                result = self.evaluate(condition, data, indicators, current_index)
                # logger.debug(f"Sub-condition {i} result: {result}")
            elif isinstance(condition, CompositeCondition):
                result = self.evaluate_composite(condition, data, indicators, current_index)
            else:
                raise TypeError(f"Unknown condition type: {type(condition)}")
            
            results.append(result)
        
        if composite.type == "and":
            final_result = all(results)
        elif composite.type == "or":
            final_result = any(results)
        else:
            raise ValueError(f"Unknown composite type: {composite.type}")
        
        # logger.debug(f"Composite condition final result: {final_result}")
        return final_result







    def _get_value(
        self,
        value: Any,
        data: pd.DataFrame,
        indicators: Dict[str, Any],
        index: int
    ) -> Optional[float]:
        
        logger.debug(f"=== _get_value START ===")
        logger.debug(f"Value: {value}, Index: {index}")
        logger.debug(f"Data shape: {data.shape}, Data index: {data.index.tolist()[:5]}...")
        
        if isinstance(value, (int, float)):
            logger.debug(f"Returning numeric value: {value}")
            return float(value)
        
        if isinstance(value, str):
            # إذا كانت قيمة مؤشر
            if value.startswith('indicator:'):
                indicator_ref = value.split(':')[1]
                logger.debug(f"Looking for indicator: {indicator_ref}")
                logger.debug(f"Available indicators keys: {list(indicators.keys())}")
                
                # البحث عن المؤشر
                indicator_data = indicators.get(indicator_ref)
                
                if indicator_data is None:
                    logger.warning(f"Indicator '{indicator_ref}' not found in indicators")
                    return None
                
                logger.debug(f"Indicator data type: {type(indicator_data)}")
                
                # **الإصلاح الحاسم: التعامل مع Series بمحاذاة الفهرس**
                if isinstance(indicator_data, pd.Series):
                    logger.debug(f"Series length: {len(indicator_data)}, Series index: {indicator_data.index.tolist()[:5]}...")
                    
                    # الحصول على التاريخ من بيانات الـ DataFrame
                    if index < len(data):
                        current_date = data.index[index]
                        logger.debug(f"Current date at index {index}: {current_date}")
                        
                        # محاولة الوصول باستخدام التاريخ (الفهرس الزمني)
                        if current_date in indicator_data.index:
                            val = indicator_data.loc[current_date]
                            if pd.isna(val):
                                logger.debug(f"Value at date {current_date} is NaN")
                            else:
                                logger.debug(f"✅ SUCCESS: Got value {val} at date {current_date}")
                                return float(val)
                        else:
                            logger.debug(f"Date {current_date} not found in indicator index")
                            
                            # محاولة الوصول باستخدام الفهرس العددي
                            if index < len(indicator_data):
                                val = indicator_data.iloc[index]
                                if pd.isna(val):
                                    logger.debug(f"Value at position {index} is NaN")
                                else:
                                    logger.debug(f"✅ SUCCESS: Got value {val} at position {index}")
                                    return float(val)
                    else:
                        logger.debug(f"Index {index} out of range for data")
                    
                    logger.debug(f"Could not extract value from indicator '{indicator_ref}'")
                    return None
                
                # معالجة dict المؤشرات
                elif isinstance(indicator_data, dict):
                    logger.debug(f"Indicator dict keys: {list(indicator_data.keys())}")
                    
                    # البحث عن Series داخل dict
                    for key, val in indicator_data.items():
                        if isinstance(val, pd.Series):
                            # نفس المنطق كما فوق
                            if index < len(data):
                                current_date = data.index[index]
                                if current_date in val.index:
                                    result = val.loc[current_date]
                                    if not pd.isna(result):
                                        logger.debug(f"✅ SUCCESS: Got value {result} from dict key '{key}' at date {current_date}")
                                        return float(result)
                    
                    logger.debug(f"No valid Series found in indicator dict")
                    return None
                
                logger.debug(f"Unsupported indicator data type")
                return None
            
            # معالجة أسعار البيانات
            elif value.startswith('price.'):
                price_field = value.split('.')[1]
                logger.debug(f"Getting price field: {price_field}")
                
                if price_field in data.columns and index < len(data):
                    val = data[price_field].iloc[index]
                    if pd.isna(val):
                        logger.debug(f"Price value is NaN")
                    else:
                        logger.debug(f"✅ SUCCESS: Got price value {val}")
                        return float(val)
                else:
                    logger.debug(f"Price field '{price_field}' not found or index out of range")
            
            # معالجة الحقول المباشرة
            elif value in data.columns and index < len(data):
                val = data[value].iloc[index]
                if pd.isna(val):
                    logger.debug(f"Column value is NaN")
                else:
                    logger.debug(f"✅ SUCCESS: Got column value {val}")
                    return float(val)
        
        logger.debug(f"=== _get_value END: Could not parse value ===")
        return None






















    
    def _crossover_above(
        self,
        left_value: float,
        right_value: float,
        prev_left_value: float = None,
        prev_right_value: float = None
    ) -> bool:
        """اكتشاف تقاطع من أسفل إلى أعلى"""
        if prev_left_value is None or prev_right_value is None:
            return False
        
        return (left_value > right_value and prev_left_value <= prev_right_value)
    
    def _crossover_below(
        self,
        left_value: float,
        right_value: float,
        prev_left_value: float = None,
        prev_right_value: float = None
    ) -> bool:
        """اكتشاف تقاطع من أعلى إلى أسفل"""
        if prev_left_value is None or prev_right_value is None:
            return False
        
        return (left_value < right_value and prev_left_value >= prev_right_value)
    
    def batch_evaluate(
        self,
        condition: Condition,
        data: pd.DataFrame,
        indicators: Dict[str, pd.Series]
    ) -> pd.Series:
        """
        تقييم شرط على مجموعة بيانات كاملة
        
        Args:
            condition: الشرط
            data: بيانات السوق الكاملة
            indicators: نتائج المؤشرات
            
        Returns:
            pd.Series: نتائج التقييم لكل صف
        """
        results = pd.Series(False, index=data.index)
        
        for i in range(1, len(data)):
            result = self.evaluate(condition, data, indicators, i)
            results.iloc[i] = result
        
        return results
    
    def validate_condition(
        self,
        condition: Condition,
        available_indicators: List[str],
        available_price_fields: List[str] = None
    ) -> Tuple[bool, str]:
        """
        التحقق من صحة الشرط
        
        Args:
            condition: الشرط المراد التحقق منه
            available_indicators: قائمة المؤشرات المتاحة
            available_price_fields: قائمة حقول السعر المتاحة
            
        Returns:
            Tuple[bool, str]: (صالح، رسالة خطأ)
        """
        if available_price_fields is None:
            available_price_fields = ['open', 'high', 'low', 'close', 'volume']
        
        # التحقق من القيم اليسرى
        left_valid, left_msg = self._validate_value(
            condition.left_value, available_indicators, available_price_fields
        )
        if not left_valid:
            return False, f"Left value error: {left_msg}"
        
        # التحقق من القيم اليمنى
        right_valid, right_msg = self._validate_value(
            condition.right_value, available_indicators, available_price_fields
        )
        if not right_valid:
            return False, f"Right value error: {right_msg}"
        
        return True, "Condition is valid"
    
    def _validate_value(
        self,
        value: Any,
        available_indicators: List[str],
        available_price_fields: List[str]
    ) -> Tuple[bool, str]:
        """التحقق من صحة قيمة"""
        if isinstance(value, (int, float)):
            return True, ""
        
        if isinstance(value, str):
            if value.startswith('indicator:'):
                indicator_ref = value.split(':')[1]
                # التحقق من المؤشرات الرئيسية
                for available in available_indicators:
                    if indicator_ref == available or indicator_ref in available:
                        return True, ""
               # return False, f"Indicator '{indicator_ref}' not in available indicators: {available_indicators}"
            
            elif value in available_price_fields:
                return True, ""
            
            elif value in ['price.close', 'price.open', 'price.high', 'price.low', 'price.volume']:
                return True, ""
            
            elif 'hl2' in value.lower() or 'hlc3' in value.lower():
                return True, ""
        
        return False, f"Invalid value format: {value}"