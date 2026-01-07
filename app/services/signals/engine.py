# trading_backend/app/services/signals/engine.py

from typing import Dict, Any
import pandas as pd

from app.services.signals.schemas import SignalResult
from app.services.indicators.calculator import IndicatorCalculator
from app.services.strategy.core import StrategyEngine, TradeSignal
from app.services.strategy.schemas import StrategyConfig



class SignalEngine:
    """
    SignalEngine = Adapter فوق StrategyEngine
    لا يحتوي منطق تداول
    فقط ينسق ويحوّل النتائج إلى SignalResult
    """

    def __init___(self, strategy_config: StrategyConfig):
        self.indicator_calc = IndicatorCalculator()
        self.strategy_engine = StrategyEngine()

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        market: str,
        df: pd.DataFrame,
        indicators_config: list,
        strategy_config: Dict[str, Any]
    ) -> SignalResult:
        """
        تقييم آخر إشارة تداول اعتمادًا على الاستراتيجية
        """

        if df.empty:
            raise ValueError("DataFrame is empty")

        # 1️⃣ تطبيق المؤشرات
        df = self.indicator_calc.apply(df, indicators_config)

        # 2️⃣ تشغيل الاستراتيجية كاملة
        strategy_result = self.strategy_engine.run_strategy(
            dataframe=df,
            strategy_config=strategy_config,
            live_mode=True
        )

        # 3️⃣ استخراج آخر إشارة
        signals: list[TradeSignal] = strategy_result.signals

        if not signals:
            return SignalResult(
                symbol=symbol,
                timeframe=timeframe,
                market=market,
                signal="neutral",
                candle_time=df.index[-1],
                indicators=self._extract_indicators(df.iloc[-1]),
                conditions_met=[]
            )

        last_signal = signals[-1]

        # 4️⃣ بناء SignalResult
        return SignalResult(
            symbol=symbol,
            timeframe=timeframe,
            market=market,
            signal=last_signal.action,
            candle_time=last_signal.time,
            indicators=self._extract_indicators(df.loc[last_signal.time]),
            conditions_met=last_signal.conditions
        )

    @staticmethod
    def _extract_indicators(row: pd.Series) -> Dict[str, float]:
        """
        استخراج المؤشرات فقط من الصف
        """
        excluded = {"time", "open", "high", "low", "close", "volume"}
        indicators = {}

        for key, value in row.items():
            if key not in excluded and value is not None:
                try:
                    indicators[key] = float(value)
                except (TypeError, ValueError):
                    continue

        return indicators
