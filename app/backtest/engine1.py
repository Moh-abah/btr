# # app/backtest/engine1.py
# import asyncio
# import numpy as np
# import pandas as pd
# from typing import Dict, List, Any, Optional, Tuple
# from datetime import datetime, timedelta, timezone
# import uuid
# import warnings
# import traceback

# # ✅ تعديل الاستيرادات: استدعاء المحرك الجديد والكيانات المجردة
# from trading_backend.app.services.strategy.strategy_engine1 import StrategyEngine, Decision, DecisionAction
# # نحتفظ بالتقارير القديمة لنفس النتائج
# from .schemas import BacktestConfig, BacktestResult, Trade, PositionType
# from .metrics import PerformanceMetrics
# from app.services.data_service import DataService
# from app.services.strategy.schemas import StrategyConfig as StrategyConfigSchema

# warnings.filterwarnings('ignore')

# class BacktestEngine:
#     """محرك الباك-تيست التاريخي (يعمل الآن كمحرك تنفيذي للقرارات)"""
    
#     def __init__(self, data_service: DataService):
#         self.data_service = data_service
#         self.metrics_calculator = PerformanceMetrics()
        
#     async def run_backtest(self, config: BacktestConfig) -> BacktestResult:
  
#         start_time = datetime.utcnow()
#         print(f"🚀 Starting backtest (Architecture: Strategy-Driven): {config.name}")
        
#         try:
#             # 1. جلب البيانات (نفس المنطق السابق)
#             all_data = {}
#             for symbol in config.symbols:
#                 try:
#                     days_required = (config.end_date - config.start_date).days + 30
#                     data = await self.data_service.get_historical(
#                         symbol=symbol, timeframe=config.timeframe,
#                         market=config.market, days=days_required, use_cache=True
#                     )
                    
#                     if not data.empty:
#                         data.index = pd.to_datetime(data.index, utc=True)
#                         start = config.start_date.astimezone(timezone.utc)
#                         end = config.end_date.astimezone(timezone.utc)
#                         mask = (data.index >= start) & (data.index <= end)
#                         filtered_data = data.loc[mask]
#                         if not filtered_data.empty:
#                             all_data[symbol] = filtered_data
#                 except Exception as e:
#                     print(f"❌ Error fetching data for {symbol}: {str(e)}")
            
#             if not all_data:
#                 raise ValueError("No data available for any symbol")
            
#             # 2. محاكاة التداول
#             trades = []
#             equity_curve = [config.initial_capital]
#             current_capital = config.initial_capital
            
#             for symbol, data in all_data.items():
#                 # ✅ نستدعي الدالة المعدلة بالكامل
#                 symbol_trades, symbol_equity = await self._simulate_with_strategy(
#                     symbol, data, config, current_capital
#                 )
#                 trades.extend(symbol_trades)
#                 # تحديث منحنى الرأس المال
#                 if len(symbol_equity) > 0:
#                     equity_curve.extend(symbol_equity[1:]) # نبدأ من الفهرس 1 لتجنب تكرار رأس المال الأولي
#                     current_capital = symbol_equity[-1]

#             # 3. حساب المقاييس (نفس المنطق السابق)
#             result = await self._create_backtest_result(
#                 config=config, trades=trades, equity_curve=equity_curve, execution_start=start_time
#             )
#             # ... (طباعة النتائج والعودة) ...
#             execution_time = (datetime.utcnow() - start_time).total_seconds()
#             result.execution_time_seconds = execution_time
#             return result

#         except Exception as e:
#             print(f"❌ Backtest failed: {str(e)}")
#             traceback.print_exc()
#             raise

#     async def _simulate_with_strategy(
#         self,
#         symbol: str,
#         data: pd.DataFrame,
#         config: BacktestConfig,
#         initial_capital: float
#     ) -> Tuple[List[Trade], List[float]]:
#         """
#         محاكاة الصفقات باستخدام محرك استراتيجية منفصل (Black Box)
        
#         ملاحظة معمارية:
#         - هذه الدالة تمثل "Execution Engine".
#         - الاستراتيجية (Strategy Engine) لا تعرف حالة الصفقة.
#         - نحن هنا (الـ Backtest) من نحتفظ بالحالة ونتحقق من المخاطر.
#         """
        
#         trades = []
#         equity_curve = [initial_capital]
#         current_capital = initial_capital
        
#         if len(data) < 50: # الحد الأدنى للبيانات لحساب المؤشرات
#             return trades, equity_curve

#         try:
#             # 1. إنشاء محرك الاستراتيجية الجديد
#             strategy_config_obj = StrategyConfigSchema(**config.strategy_config)
#             strategy_engine = StrategyEngine(strategy_config_obj)
#         except Exception as e:
#             print(f"❌ خطأ في تكوين الاستراتيجية: {e}")
#             return trades, equity_curve

#         # حالة المحفظة (Portfolio State) - يدارها الـ Backtest فقط
#         current_state = 'NEUTRAL' # LONG, SHORT, NEUTRAL
#         entry_price = 0.0
#         entry_time = None
#         position_size = 0.0
#         trade_id = None
#         sl_price = 0.0
#         tp_price = 0.0

#         print(f"   📊 بدء المحاكاة لـ {symbol} باستخدام Black Box Strategy...")

#         # 2. حلقة المحاكاة (Bar-by-Bar Simulation)
#         # نقوم بتمرير البيانات تدريجياً للاستراتيجية ونبني القرارات
#         for i in range(len(data)):
#             current_bar = data.iloc[i]
#             current_time = data.index[i]
            
#             # أ) التحقق من إدارة المخاطر (SL/TP) قبل طلب القرار الجديد
#             if current_state != 'NEUTRAL':
#                 # التحقق من وقف الخسارة
#                 if current_state == 'LONG':
#                     if current_bar['low'] <= sl_price:
#                         exit_price = sl_price
#                         reason = "Stop Loss Hit"
#                     elif current_bar['high'] >= tp_price:
#                         exit_price = tp_price
#                         reason = "Take Profit Hit"
#                     else:
#                         exit_price = None
#                 elif current_state == 'SHORT':
#                     if current_bar['high'] >= sl_price:
#                         exit_price = sl_price
#                         reason = "Stop Loss Hit"
#                     elif current_bar['low'] <= tp_price:
#                         exit_price = tp_price
#                         reason = "Take Profit Hit"
#                     else:
#                         exit_price = None
                
#                 # إذا تم تفعيل وقف الخسارة أو الربح
#                 if exit_price is not None:
#                     # حساب الربح/الخسارة
#                     if current_state == 'LONG':
#                         pnl = (exit_price - entry_price) * position_size
#                     else: # SHORT
#                         pnl = (entry_price - exit_price) * position_size
                    
#                     # إغلاق الصفقة
#                     self._close_trade_logic(trades, trade_id, exit_price, current_time, reason, pnl, exit_price * position_size * config.commission_rate)
#                     current_state = 'NEUTRAL'
#                     current_capital += pnl
#                     equity_curve.append(current_capital)
#                     trade_id = None
#                     continue # الانتقال للشريط التالي

#             # ب) طلب قرار من الاستراتيجية (Black Box Call)
#             # نمرر البيانات حتى اللحظة الحالية
#             # ⚠️ ملاحظة أداء: التقطيع (Slicing) في كل مرة مكلف حسابياً، لكنه ضروري للحفاظ على Black Box Interface
#             slice_data = data.iloc[:i+1]
            
#             try:
#                 decision = await strategy_engine.run(slice_data)
#             except Exception as e:
#                 print(f"⚠️ Strategy Error at {current_time}: {e}")
#                 continue

#             # ج) معالجة القرار (Decision Logic)
#             target_state = 'NEUTRAL'
            
#             if decision.action == DecisionAction.BUY:
#                 target_state = 'LONG'
#             elif decision.action == DecisionAction.SELL:
#                 target_state = 'SHORT'
#             else:
#                 target_state = 'NEUTRAL' # HOLD يعني الخروج للحياد أو البقاء عليه

#             # د) تنفيذ الانتقالات (State Transition)
            
#             # الحالة 1: إغلاق مركز (أو عكس الموقف)
#             if target_state != current_state and current_state != 'NEUTRAL':
#                 # نحتاج لإغلاق المركز الحالي أولاً
#                 exit_price = current_bar['close'] # إغلاق عند سعر السوق
                
#                 if current_state == 'LONG':
#                     pnl = (exit_price - entry_price) * position_size
#                 else:
#                     pnl = (entry_price - exit_price) * position_size
                
#                 commission = exit_price * position_size * config.commission_rate
#                 self._close_trade_logic(trades, trade_id, exit_price, current_time, f"Signal: {decision.reason}", pnl, commission)
                
#                 current_capital += pnl
#                 equity_curve.append(current_capital)
#                 current_state = 'NEUTRAL'
#                 trade_id = None

#             # الحالة 2: فتح مركز جديد
#             if target_state != 'NEUTRAL' and current_state == 'NEUTRAL':
#                 entry_price = current_bar['close']
#                 entry_time = current_time
                
#                 # حساب حجم الصفقة (من Backtest Config وليس Strategy)
#                 risk_amount = current_capital * config.position_size_percent
#                 # افتراض بسيط: نستخدم المخاطرة كحجم مباشر، أو يمكن حسابه بناءً على SL
#                 position_size = risk_amount / entry_price 
                
#                 # تحديد مستويات SL/TP
#                 if config.stop_loss_percent:
#                     sl_offset = entry_price * (config.stop_loss_percent / 100)
#                     if target_state == 'LONG':
#                         sl_price = entry_price - sl_offset
#                     else:
#                         sl_price = entry_price + sl_offset
                
#                 if config.take_profit_percent:
#                     tp_offset = entry_price * (config.take_profit_percent / 100)
#                     if target_state == 'LONG':
#                         tp_price = entry_price + tp_offset
#                     else:
#                         tp_price = entry_price - tp_offset

#                 current_state = target_state
#                 trade_id = str(uuid.uuid4())
                
#                 # إنشاء سجل الصفقة
#                 commission = entry_price * position_size * config.commission_rate
#                 trade = Trade(
#                     id=trade_id,
#                     symbol=symbol,
#                     entry_time=entry_time,
#                     exit_time=None,
#                     entry_price=entry_price,
#                     exit_price=None,
#                     position_type='long' if target_state == 'LONG' else 'short',
#                     position_size=position_size,
#                     pnl=None,
#                     pnl_percentage=None,
#                     commission=commission,
#                     slippage=0, # يمكن إضافته لاحقاً
#                     stop_loss=sl_price if config.stop_loss_percent else None,
#                     take_profit=tp_price if config.take_profit_percent else None,
#                     exit_reason=None,
#                     metadata={
#                         'strategy': config.strategy_config.get('name', 'Unknown'),
#                         'decision_reason': decision.reason,
#                         'confidence': decision.confidence
#                     }
#                 )
#                 trades.append(trade)

#         # إغلاق أي مركز مفتوح في نهاية البيانات
#         if current_state != 'NEUTRAL' and trade_id:
#             last_price = data['close'].iloc[-1]
#             if current_state == 'LONG':
#                 pnl = (last_price - entry_price) * position_size
#             else:
#                 pnl = (entry_price - last_price) * position_size
            
#             self._close_trade_logic(trades, trade_id, last_price, data.index[-1], "End of Data", pnl, 0)
#             current_capital += pnl
#             equity_curve.append(current_capital)

#         return trades, equity_curve

#     def _close_trade_logic(self, trades, trade_id, exit_price, exit_time, reason, pnl, commission):
#         """دالة مساعدة لتحديث بيانات الصفقة عند الإغلاق"""
#         for trade in trades:
#             if trade.id == trade_id and trade.exit_time is None:
#                 trade.exit_time = exit_time
#                 trade.exit_price = exit_price
#                 trade.pnl = pnl - commission
#                 if trade.entry_price > 0:
#                     trade.pnl_percentage = (pnl / (trade.entry_price * trade.position_size)) * 100
#                 trade.exit_reason = reason
#                 trade.commission += commission
#                 break

#     async def _create_backtest_result(
#         self,
#         config: BacktestConfig,
#         trades: List[Trade],
#         equity_curve: List[float],
#         execution_start: datetime
#     ) -> BacktestResult:
#         """إنشاء نتيجة الباك-تيست"""
        
#         if not trades:
         
#             return BacktestResult(
#                 id=str(uuid.uuid4()),
#                 config=config,
#                 execution_time_seconds=(datetime.utcnow() - execution_start).total_seconds(),
#                 initial_capital=config.initial_capital,
#                 final_capital=config.initial_capital,
#                 total_pnl=0,
#                 total_pnl_percent=0,
#                 annual_return_percent=0,
#                 sharpe_ratio=0,
#                 sortino_ratio=0,
#                 calmar_ratio=0,
#                 total_trades=0,
#                 winning_trades=0,
#                 losing_trades=0,
#                 win_rate=0,
#                 profit_factor=0,
#                 expectancy=0,
#                 max_drawdown_percent=0,
#                 max_drawdown_duration_days=0,
#                 volatility_annual=0,
#                 var_95=0,
#                 cvar_95=0,
#                 trades=trades,
#                 equity_curve=equity_curve,
#                 drawdown_curve=self._calculate_drawdown_curve(equity_curve),
#                 monthly_returns={},
#                 yearly_returns={},
#                 avg_winning_trade=0,
#                 avg_losing_trade=0,
#                 largest_winning_trade=0,
#                 largest_losing_trade=0,
#                 avg_trade_duration_hours=0,
#                 symbols_performance=self._calculate_symbols_performance(trades),
#                 system_quality_number=0,
#                 kelly_criterion=0
#             )
        
#         # حساب المقاييس الأساسية
#         winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
#         losing_trades = [t for t in trades if t.pnl and t.pnl <= 0]
        
#         win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        
#         total_pnl = sum(t.pnl or 0 for t in trades)
#         total_pnl_percent = (total_pnl / config.initial_capital) * 100
        
#         final_capital = config.initial_capital + total_pnl
        
#         # حساب العائد السنوي
#         days_duration = (config.end_date - config.start_date).days
#         annual_return_percent = 0
#         if days_duration > 0 and config.initial_capital > 0:
#             annual_return_percent = ((final_capital / config.initial_capital) ** (365 / days_duration) - 1) * 100
        
#         # حساب منحنى الانخفاض
#         drawdown_curve = self._calculate_drawdown_curve(equity_curve)
#         max_drawdown_percent = max(drawdown_curve) if drawdown_curve else 0
        
#         # حساب العوائد الشهرية والسنوية
#         monthly_returns, yearly_returns = self._calculate_periodic_returns(equity_curve, config)
        
#         # حساب المقاييس الأخرى
#         sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
#         sortino_ratio = self._calculate_sortino_ratio(equity_curve)
#         calmar_ratio = self._calculate_calmar_ratio(annual_return_percent, max_drawdown_percent)
#         profit_factor = self._calculate_profit_factor(winning_trades, losing_trades)
#         expectancy = self._calculate_expectancy(trades)
        
#         # حساب متوسط مدة الصفقة
#         avg_trade_duration = self._calculate_avg_trade_duration(trades)
#         recovery_factor = (
#             total_pnl / max_drawdown_percent
#             if max_drawdown_percent > 0 else 0
#         )

#         # إنشاء نتيجة الباك-تيست
#         result = BacktestResult(
#             id=str(uuid.uuid4()),
#             config=config,
#             execution_time_seconds=(datetime.utcnow() - execution_start).total_seconds(),
#             initial_capital=config.initial_capital,
#             final_capital=final_capital,
#             total_pnl=total_pnl,
#             total_pnl_percent=total_pnl_percent,
#             annual_return_percent=annual_return_percent,
#             sharpe_ratio=sharpe_ratio,
#             sortino_ratio=sortino_ratio,
#             calmar_ratio=calmar_ratio,
#             total_trades=len(trades),
#             winning_trades=len(winning_trades),
#             losing_trades=len(losing_trades),
#             win_rate=win_rate,
#             profit_factor=profit_factor,
#             expectancy=expectancy,
#             max_drawdown_percent=max_drawdown_percent,
#             max_drawdown_duration_days=self._calculate_max_drawdown_duration(drawdown_curve),
#             volatility_annual=self._calculate_volatility(equity_curve),
#             var_95=self._calculate_var(equity_curve, 95),
#             cvar_95=self._calculate_cvar(equity_curve, 95),
#             trades=trades,
#             equity_curve=equity_curve,
#             drawdown_curve=drawdown_curve,
#             monthly_returns=monthly_returns,
#             yearly_returns=yearly_returns,
#             avg_winning_trade=np.mean([t.pnl for t in winning_trades]) if winning_trades else 0,
#             avg_losing_trade=np.mean([t.pnl for t in losing_trades]) if losing_trades else 0,
#             largest_winning_trade=max([t.pnl for t in winning_trades]) if winning_trades else 0,
#             largest_losing_trade=min([t.pnl for t in losing_trades]) if losing_trades else 0,
#             avg_trade_duration_hours=avg_trade_duration,
#             symbols_performance=self._calculate_symbols_performance(trades),
#             system_quality_number=self._calculate_system_quality_number(trades),
#             kelly_criterion=self._calculate_kelly_criterion(trades)
#         )
        
#         return result
    
#     def _calculate_drawdown_curve(self, equity_curve: List[float]) -> List[float]:
#         """حساب منحنى الانخفاض"""
#         if not equity_curve:
#             return []
        
#         peak = equity_curve[0]
#         drawdowns = []
        
#         for equity in equity_curve:
#             if equity > peak:
#                 peak = equity
#             drawdown = (peak - equity) / peak * 100 if peak > 0 else 0
#             drawdowns.append(drawdown)
        
#         return drawdowns
    
#     def _calculate_symbols_performance(self, trades: List[Trade]) -> Dict[str, Dict[str, float]]:
#         """حساب أداء كل رمز"""
#         symbols = {}
        
#         for trade in trades:
#             if trade.symbol not in symbols:
#                 symbols[trade.symbol] = {
#                     'total_trades': 0,
#                     'winning_trades': 0,
#                     'total_pnl': 0,
#                     'avg_pnl': 0
#                 }
            
#             symbols[trade.symbol]['total_trades'] += 1
#             if trade.pnl and trade.pnl > 0:
#                 symbols[trade.symbol]['winning_trades'] += 1
#             if trade.pnl:
#                 symbols[trade.symbol]['total_pnl'] += trade.pnl
        
#         for symbol, data in symbols.items():
#             if data['total_trades'] > 0:
#                 data['win_rate'] = (data['winning_trades'] / data['total_trades']) * 100
#                 data['avg_pnl'] = data['total_pnl'] / data['total_trades']
        
#         return symbols
    
#     def _calculate_periodic_returns(self, equity_curve: List[float], config: BacktestConfig) -> Tuple[Dict[str, float], Dict[str, float]]:
#         """حساب العوائد الشهرية والسنوية"""
#         # هذا مثال مبسط
#         # في التطبيق الحقيقي، نحتاج إلى تتبع التواريخ
        
#         monthly_returns = {}
#         yearly_returns = {}
        
#         if len(equity_curve) > 30:
#             # عوائد شهرية افتراضية
#             for i in range(min(12, len(equity_curve) // 30)):
#                 start_idx = i * 30
#                 end_idx = min((i + 1) * 30, len(equity_curve) - 1)
                
#                 if end_idx > start_idx:
#                     monthly_return = ((equity_curve[end_idx] - equity_curve[start_idx]) / 
#                                     equity_curve[start_idx]) * 100
#                     monthly_returns[f"Month_{i+1}"] = monthly_return
        
#         # العائد السنوي الإجمالي
#         if len(equity_curve) > 1:
#             yearly_return = ((equity_curve[-1] - equity_curve[0]) / 
#                            equity_curve[0]) * 100
#             yearly_returns["Total_Period"] = yearly_return
        
#         return monthly_returns, yearly_returns
    
#     def _calculate_sharpe_ratio(self, equity_curve: List[float]) -> float:
#         """حساب نسبة شارب"""
#         if len(equity_curve) < 2:
#             return 0.0
        
#         returns = np.diff(equity_curve) / equity_curve[:-1]
#         if returns.std() == 0:
#             return 0.0
        
#         # افتراض معدل خالي من المخاطر 2%
#         risk_free_rate = 0.02 / 252  # معدل يومي
        
#         sharpe = (returns.mean() - risk_free_rate) / returns.std() * np.sqrt(252)
#         return float(sharpe)
    
#     def _calculate_sortino_ratio(self, equity_curve: List[float]) -> float:
#         """حساب نسبة سورتينو"""
#         if len(equity_curve) < 2:
#             return 0.0
        
#         returns = np.diff(equity_curve) / equity_curve[:-1]
#         negative_returns = returns[returns < 0]
        
#         if len(negative_returns) == 0 or negative_returns.std() == 0:
#             return 0.0
        
#         # افتراض معدل خالي من المخاطر 2%
#         risk_free_rate = 0.02 / 252
        
#         sortino = (returns.mean() - risk_free_rate) / negative_returns.std() * np.sqrt(252)
#         return float(sortino)
    
#     def _calculate_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
#         """حساب نسبة كالمار"""
#         if max_drawdown == 0:
#             return 0.0
#         return annual_return / abs(max_drawdown)
    
#     def _calculate_profit_factor(self, winning_trades: List[Trade], losing_trades: List[Trade]) -> float:
#         """حساب عامل الربح"""
#         gross_profit = sum(t.pnl for t in winning_trades if t.pnl)
#         gross_loss = abs(sum(t.pnl for t in losing_trades if t.pnl))
        
#         if gross_loss == 0:
#             return float('inf') if gross_profit > 0 else 0.0
        
#         return gross_profit / gross_loss
    
#     def _calculate_expectancy(self, trades: List[Trade]) -> float:
#         """حساب التوقع"""
#         if not trades:
#             return 0.0
        
#         winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
#         losing_trades = [t for t in trades if t.pnl and t.pnl <= 0]
        
#         win_rate = len(winning_trades) / len(trades)
#         avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
#         avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0
        
#         expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
#         return float(expectancy)
    
#     def _calculate_max_drawdown_duration(self, drawdown_curve: List[float]) -> int:
#         """حساب مدة أقصى انخفاض"""
#         if not drawdown_curve:
#             return 0
        
#         max_duration = 0
#         current_duration = 0
        
#         for dd in drawdown_curve:
#             if dd > 0:
#                 current_duration += 1
#                 max_duration = max(max_duration, current_duration)
#             else:
#                 current_duration = 0
        
#         return max_duration
    
#     def _calculate_volatility(self, equity_curve: List[float]) -> float:
#         """حساب التقلب السنوي"""
#         if len(equity_curve) < 2:
#             return 0.0
        
#         returns = np.diff(equity_curve) / equity_curve[:-1]
#         volatility = returns.std() * np.sqrt(252) * 100  # كنسبة مئوية سنوية
#         return float(volatility)
    
#     def _calculate_var(self, equity_curve: List[float], confidence: float) -> float:
#         """حساب القيمة المعرضة للخطر"""
#         if len(equity_curve) < 2:
#             return 0.0
        
#         returns = np.diff(equity_curve) / equity_curve[:-1]
#         var = np.percentile(returns, 100 - confidence) * 100  # كنسبة مئوية
#         return float(var)
    
#     def _calculate_cvar(self, equity_curve: List[float], confidence: float) -> float:
#         """حساب القيمة المعرضة للخطر الشرطية"""
#         if len(equity_curve) < 2:
#             return 0.0
        
#         returns = np.diff(equity_curve) / equity_curve[:-1]
#         var = np.percentile(returns, 100 - confidence)
#         cvar = returns[returns <= var].mean() * 100  # كنسبة مئوية
#         return float(cvar)
    
#     def _calculate_avg_trade_duration(self, trades: List[Trade]) -> float:
#         """حساب متوسط مدة الصفقة بالساعات"""
#         if not trades:
#             return 0.0
        
#         durations = []
#         for trade in trades:
#             if trade.entry_time and trade.exit_time:
#                 duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600
#                 durations.append(duration)
        
#         return float(np.mean(durations)) if durations else 0.0
    
#     def _calculate_system_quality_number(self, trades: List[Trade]) -> float:
#         """حساب رقم جودة النظام"""
#         if not trades:
#             return 0.0
        
#         pnls = [t.pnl for t in trades if t.pnl is not None]
#         if not pnls:
#             return 0.0
        
#         mean_pnl = np.mean(pnls)
#         std_pnl = np.std(pnls)
        
#         if std_pnl == 0:
#             return 0.0
        
#         sqn = (mean_pnl / std_pnl) * np.sqrt(len(trades))
#         return float(sqn)
    
#     def _calculate_kelly_criterion(self, trades: List[Trade]) -> float:
#         """حساب معيار كيلي"""
#         if not trades:
#             return 0.0
        
#         winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
#         losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
        
#         win_rate = len(winning_trades) / len(trades)
#         avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
#         avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0
        
#         if avg_loss == 0:
#             return 0.0
        
#         kelly = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
#         return float(kelly)
    
#     async def run_walk_forward_analysis(
#         self,
#         config: BacktestConfig,
#         periods: int = 5
#     ) -> List[BacktestResult]:
#         """تشغيل تحليل مشي للأمام"""
#         results = []
        
#         # تقسيم الفترة الزمنية إلى فترات فرعية
#         total_days = (config.end_date - config.start_date).days
#         period_days = total_days // periods
        
#         for i in range(periods):
#             period_start = config.start_date + timedelta(days=i * period_days)
#             period_end = period_start + timedelta(days=period_days)
            
#             if i == periods - 1:
#                 period_end = config.end_date
            
#             print(f"\n🔍 Walk-forward period {i+1}: {period_start.date()} to {period_end.date()}")
            
#             # تحديث التكوين للفترة الحالية
#             period_config = config.copy()
#             period_config.start_date = period_start
#             period_config.end_date = period_end
            
#             # تشغيل الباك-تيست للفترة الحالية
#             try:
#                 result = await self.run_backtest(period_config)
#                 results.append(result)
#                 print(f"✅ Period {i+1} completed: P&L {result.total_pnl_percent:.2f}%, Trades: {result.total_trades}")
#             except Exception as e:
#                 print(f"❌ Error in period {i+1}: {str(e)}")
        
#         return results
    
#     async def run_monte_carlo_simulation(
#         self,
#         config: BacktestConfig,
#         simulations: int = 1000
#     ) -> Dict[str, Any]:
#         """تشغيل محاكاة مونت كارلو"""
#         print(f"\n🎲 Running Monte Carlo simulation ({simulations} iterations)")
        
#         # تشغيل باك-تيست أساسي للحصول على الصفقات
#         print("Running base backtest for simulation data...")
#         base_result = await self.run_backtest(config)
#         base_trades = base_result.trades
        
#         if not base_trades or len(base_trades) < 10:
#             print("⚠️ Not enough trades for Monte Carlo simulation")
#             return {
#                 'simulations': 0,
#                 'mean_return': 0.0,
#                 'std_return': 0.0,
#                 'min_return': 0.0,
#                 'max_return': 0.0,
#                 'percentile_5': 0.0,
#                 'percentile_25': 0.0,
#                 'percentile_50': 0.0,
#                 'percentile_75': 0.0,
#                 'percentile_95': 0.0,
#                 'probability_profit': 0.0,
#                 'probability_loss': 0.0
#             }
        
#         # محاكاة إعادة ترتيب الصفقات
#         simulated_returns = []
#         base_pnls = [t.pnl for t in base_trades if t.pnl is not None]
        
#         print(f"Using {len(base_pnls)} trades for simulation")
        
#         for i in range(simulations):
#             # إعادة ترتيب عشوائي للصفقات
#             shuffled_pnls = np.random.permutation(base_pnls)
            
#             # محاكاة العوائد
#             total_pnl = np.sum(shuffled_pnls)
#             total_return = (total_pnl / config.initial_capital) * 100
#             simulated_returns.append(total_return)
            
#             if (i + 1) % 100 == 0:
#                 print(f"  Completed {i+1}/{simulations} iterations")
        
#         returns_array = np.array(simulated_returns)
        
#         stats = {
#             'simulations': simulations,
#             'mean_return': float(np.mean(returns_array)),
#             'std_return': float(np.std(returns_array)),
#             'min_return': float(np.min(returns_array)),
#             'max_return': float(np.max(returns_array)),
#             'percentile_5': float(np.percentile(returns_array, 5)),
#             'percentile_25': float(np.percentile(returns_array, 25)),
#             'percentile_50': float(np.percentile(returns_array, 50)),
#             'percentile_75': float(np.percentile(returns_array, 75)),
#             'percentile_95': float(np.percentile(returns_array, 95)),
#             'probability_profit': float(np.sum(returns_array > 0) / len(returns_array)),
#             'probability_loss': float(np.sum(returns_array < 0) / len(returns_array))
#         }
        
#         print(f"✅ Monte Carlo simulation completed")
#         print(f"   Mean return: {stats['mean_return']:.2f}%")
#         print(f"   Probability of profit: {stats['probability_profit']*100:.1f}%")
        
#         return stats


import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
import uuid
import warnings
import traceback

# ✅ استيراد محرك الاستراتيجية الجديد (الذي اسمه strategy_engine1)
# تأكد أن المسار صحيح داخل مشروعك
from app.services.strategy.strategy_engine1 import StrategyEngine, Decision, DecisionAction

# استيرادات الـ Schemas والخدمات المساعدة
from app.backtest.schemas import BacktestConfig, BacktestResult, PnlDistribution, Trade, VisualCandle
from app.services.data_service import DataService
from app.services.strategy.schemas import StrategyConfig as StrategyConfigSchema
from app.backtest.metrics import PerformanceMetrics

warnings.filterwarnings('ignore')

class BacktestEngine:
    """محرك الباك-تيست التاريخي (يعمل الآن كمحرك تنفيذي للقرارات)"""
    
    def __init__(self, data_service: DataService):
        self.data_service = data_service
        self.metrics_calculator = PerformanceMetrics()
        
    # async def run_backtest(self, config: BacktestConfig) -> BacktestResult:  
    #     start_time = datetime.utcnow()
    #     print(f"🚀 Starting backtest (Architecture: Strategy-Driven): {config.name}")
        
    #     try:
    #         # 1. جلب البيانات (Data Fetching)
    #         all_data = {}
    #         for symbol in config.symbols:
    #             try:
    #                 days_required = (config.end_date - config.start_date).days + 30
    #                 data = await self.data_service.get_historical(
    #                     symbol=symbol, 
    #                     timeframe=config.timeframe,
    #                     market=config.market, 
    #                     days=days_required, 
    #                     use_cache=True
    #                 )
                    
    #                 if not data.empty:
    #                     data.index = pd.to_datetime(data.index, utc=True)
    #                     print(f"📊 Data for {symbol}:")
    #                     print(f"   First candle: {data.index[0]}")
    #                     print(f"   Last candle: {data.index[-1]}")
    #                     print(f"   Total candles: {len(data)}")
    #                     start = config.start_date.astimezone(timezone.utc)
    #                     end = config.end_date.astimezone(timezone.utc)

    #                     print(f"   Filtering from: {start}")
    #                     print(f"   Filtering to:   {end}")
    #                     mask = (data.index >= start) & (data.index <= end)
    #                     filtered_data = data.loc[mask]
    #                     print(f"   After filtering: {len(filtered_data)} candles")

    #                     if not filtered_data.empty:
    #                         all_data[symbol] = filtered_data
    #                         print(f"✅ Loaded {len(filtered_data)} candles for {symbol}")
    #                     else:
    #                         print(f"⚠️ WARNING: No data after filtering for {symbol}")
    #                         # ✅ عرض عينة من البيانات لفهم المشكلة
    #                         print(f"   Sample timestamps: {data.index[:5].tolist()}")
    #             except Exception as e:
    #                 print(f"❌ Error fetching data for {symbol}: {str(e)}")
                 
    #         if not all_data:
    #             raise ValueError("No data available for any symbol")
            
    #         # 2. محاكاة التداول (Simulation)
    #         trades = []

    #         equity_curve = [config.initial_capital]
    #         visual_candles_all = []
    #         trade_points_all = []

    #         current_capital = config.initial_capital
            
    #         for symbol, data in all_data.items():
    #             # ✅ استدعاء الدالة المعدلة بالكامل
    #             # symbol_trades, symbol_equity, visual_candles, trade_points = await self._simulate_with_strategy(
    #             #     symbol, data, config, current_capital
    #             # )
    #             symbol_trades, symbol_equity, symbol_visual_candles, symbol_trade_points = await self._simulate_with_strategy(
    #                 symbol, data, config, current_capital
    #             )                
    #             trades.extend(symbol_trades)
    #             visual_candles_all.extend(symbol_visual_candles)
    #             trade_points_all.extend(symbol_trade_points)                
    #             # تحديث منحنى رأس المال
    #             if len(symbol_equity) > 0:
    #                 # نبدأ من الفهرس 1 لتجنب تكرار القيمة الأولية
    #                 equity_curve.extend(symbol_equity[1:]) 
    #                 current_capital = symbol_equity[-1]

    #         # 3. حساب المقاييس والنتيجة النهائية (Metrics & Result)
    #         result = await self._create_backtest_result(
    #             config=config, 
    #             trades=trades, 
    #             equity_curve=equity_curve, 
    #             visual_candles=visual_candles_all,  # إضافة البيانات البصرية
    #             trade_points=trade_points_all,                  
    #             execution_start=start_time
    #         )
            
    #         return result

    #     except Exception as e:
    #         print(f"❌ Backtest failed: {str(e)}")
    #         traceback.print_exc()
    #         raise



    
    async def run_backtest(self, config: BacktestConfig) -> BacktestResult:  
        start_time = datetime.utcnow()
        print(f"🚀 Starting backtest (Architecture: Strategy-Driven): {config.name}")
        
        try:
            # 1. جلب البيانات (Data Fetching)
            all_data = {}
            for symbol in config.symbols:
                try:
                   
                    data = await self.data_service.get_historicallastvirsion(
                        symbol=symbol, 
                        timeframe=config.timeframe,
                        market=config.market, 
                        start_date=config.start_date,
                        end_date=config.end_date,
                        use_cache=True
                    )
                    
                    if data.empty:
                        print(f"⚠️ No data returned for {symbol}")
                        continue

                    all_data[symbol] = data
                    print(f"✅ Loaded {len(data)} candles for {symbol}")
                    print(f"   First: {data.index[0]}")
                    print(f"   Last:  {data.index[-1]}")

                except Exception as e:
                    print(f"❌ Error fetching data for {symbol}: {str(e)}")
                 
            if not all_data:
                raise ValueError("No data available for any symbol")
            
            # 2. محاكاة التداول (Simulation)
            trades = []

            equity_curve = [config.initial_capital]
            visual_candles_all = []
            trade_points_all = []

            current_capital = config.initial_capital
            
            for symbol, data in all_data.items():
                # ✅ استدعاء الدالة المعدلة بالكامل
                # symbol_trades, symbol_equity, visual_candles, trade_points = await self._simulate_with_strategy(
                #     symbol, data, config, current_capital
                # )
                symbol_trades, symbol_equity, symbol_visual_candles, symbol_trade_points = await self._simulate_with_strategy(
                    symbol, data, config, current_capital
                )                
                trades.extend(symbol_trades)
                visual_candles_all.extend(symbol_visual_candles)
                trade_points_all.extend(symbol_trade_points)                
                # تحديث منحنى رأس المال
                if len(symbol_equity) > 0:
                    # نبدأ من الفهرس 1 لتجنب تكرار القيمة الأولية
                    equity_curve.extend(symbol_equity[1:]) 
                    current_capital = symbol_equity[-1]

            # 3. حساب المقاييس والنتيجة النهائية (Metrics & Result)
            result = await self._create_backtest_result(
                config=config, 
                trades=trades, 
                equity_curve=equity_curve, 
                visual_candles=visual_candles_all,  # إضافة البيانات البصرية
                trade_points=trade_points_all,                  
                execution_start=start_time
            )
            
            return result

        except Exception as e:
            print(f"❌ Backtest failed: {str(e)}")
            traceback.print_exc()
            raise


    async def _simulate_with_strategy(
        self,
        symbol: str,
        data: pd.DataFrame,
        config: BacktestConfig,
        initial_capital: float
    ) -> Tuple[List[Trade], List[float], List[VisualCandle], List[dict]]:
        """
        محاكاة الصفقات مع تجهيز كامل البيانات للعرض
        """
        trades = []
        equity_curve = [initial_capital]
        current_capital = initial_capital
        visual_candles = []
        trade_points = []
        
        if len(data) < 50:  # الحد الأدنى للمؤشرات
            return trades, equity_curve, visual_candles, trade_points

        try:
            # 1. إنشاء محرك الاستراتيجية
            strategy_config_obj = StrategyConfigSchema(**config.strategy_config)
            strategy_engine = StrategyEngine(strategy_config_obj)
            # ✅ حساب المؤشرات مرة واحدة لكل الشموع
            full_calculated_data = await strategy_engine._prepare_indicators(data)
            # ✅ تخزينها في المحرك لاستخدامها داخل اللوب
            strategy_engine.full_data = full_calculated_data
        except Exception as e:
          
            return trades, equity_curve, visual_candles, trade_points

        # حالة المحفظة (Portfolio State)
        current_state = 'NEUTRAL'  # LONG, SHORT, NEUTRAL
        entry_price = 0.0
        entry_time = None
        position_size = 0.0
        trade_id = None
        sl_price = 0.0
        tp_price = 0.0
        cumulative_pnl = 0.0
        account_balance = initial_capital

      

        # 2. حلقة المحاكاة (Bar-by-Bar Simulation)
        import time

        t_total_start = time.perf_counter()

        t_strategy = 0.0
        t_visual = 0.0
        t_loop = 0.0
        elapsed = 0.0

        for i in range(len(data)):
            t_loop_start = time.perf_counter()

            current_bar = data.iloc[i]
            current_time = data.index[i]
            
            # متغيرات مؤقتة لهذه الشمعة
            entering_trade = False
            exiting_trade = False
            exit_price = None
            exit_reason = None
            pnl = 0.0
            pnl_percentage = 0.0
            
            # حساب الربح غير المتحقق إذا كان هناك مركز مفتوح
            unrealized_pnl = 0.0
            if current_state != 'NEUTRAL' and entry_price > 0:
                if current_state == 'LONG':
                    unrealized_pnl = (current_bar['close'] - entry_price) * position_size
                else:  # SHORT
                    unrealized_pnl = (entry_price - current_bar['close']) * position_size
            
            # حساب رصيد الحساب الحالي (الرصيد + الربح غير المتحقق)
            current_account_balance = account_balance + unrealized_pnl
            
            # أ) التحقق من إدارة المخاطر (SL/TP) قبل طلب القرار الجديد
            if current_state != 'NEUTRAL':
                if current_state == 'LONG':
                    if current_bar['low'] <= sl_price:
                        exit_price = sl_price
                        exit_reason = "Stop Loss Hit"
                    elif current_bar['high'] >= tp_price:
                        exit_price = tp_price
                        exit_reason = "Take Profit Hit"
                elif current_state == 'SHORT':
                    if current_bar['high'] >= sl_price:
                        exit_price = sl_price
                        exit_reason = "Stop Loss Hit"
                    elif current_bar['low'] <= tp_price:
                        exit_price = tp_price
                        exit_reason = "Take Profit Hit"
                
                # إذا تم تفعيل وقف الخسارة أو الربح
                if exit_price is not None:
                    # حساب الربح/الخسارة
                    if current_state == 'LONG':
                        pnl = (exit_price - entry_price) * position_size
                    else:  # SHORT
                        pnl = (entry_price - exit_price) * position_size
                    
                    # حساب النسبة المئوية للربح/الخسارة
                    initial_investment = entry_price * position_size
                    pnl_percentage = (pnl / initial_investment) * 100 if initial_investment != 0 else 0
                    
                    exiting_trade = True
                    
                    # إغلاق الصفقة
                    self._close_trade_logic(trades, trade_id, exit_price, current_time, exit_reason, pnl, pnl_percentage)
                    
                    current_state = 'NEUTRAL'
                    account_balance += pnl
                    cumulative_pnl += pnl
                    equity_curve.append(account_balance)
                    trade_id = None
                    entry_price = 0.0
                    position_size = 0.0
                    sl_price = 0.0
                    tp_price = 0.0

            # ب) طلب قرار من الاستراتيجية (Black Box Call)
            slice_data = data.iloc[:i+1]
            
            try:

                t0 = time.perf_counter()
                decision = await strategy_engine.run(slice_data)
                elapsed = time.perf_counter() - t0
                t_strategy += elapsed


                if i % 50 == 0:
                    print(
                        f"[{symbol}] candle={i+1}/{len(data)} | "
                        f"slice={len(slice_data)} | "
                        f"strategy_time={elapsed:.4f}s"
                    )
                # decision = await strategy_engine.run(slice_data)
            except Exception as inner_e:
              
                decision = None

            # ج) معالجة القرار (Decision Logic)
            target_state = 'NEUTRAL'
            
            if decision and decision.action == DecisionAction.BUY:
                target_state = 'LONG'
            elif decision and decision.action == DecisionAction.SELL:
                target_state = 'SHORT'

            # د) تنفيذ الانتقالات (State Transition)
            
            # الحالة 1: إغلاق مركز (أو عكس الموقف)
            if target_state != 'NEUTRAL' and current_state != 'NEUTRAL' and current_state != target_state:
                # إغلاق المركز الحالي أولاً
                close_price = current_bar['close']
                
                # حساب الربح/الخسارة
                initial_investment = entry_price * position_size
                if current_state == 'LONG':
                    pnl_close = (close_price - entry_price) * position_size
                else:  # SHORT
                    pnl_close = (entry_price - close_price) * position_size
                
                pnl_percentage = (pnl_close / initial_investment) * 100 if initial_investment != 0 else 0
                
                exiting_trade = True
                pnl = pnl_close
                exit_price = close_price
                exit_reason = f"Signal Reversal: {target_state}"
                
                # إغلاق الصفقة
                self._close_trade_logic(trades, trade_id, close_price, current_time, exit_reason, pnl_close, pnl_percentage)
                
                account_balance += pnl_close
                cumulative_pnl += pnl_close
                equity_curve.append(account_balance)
                current_state = 'NEUTRAL'
                trade_id = None
                entry_price = 0.0
                position_size = 0.0
                sl_price = 0.0
                tp_price = 0.0

            # الحالة 2: فتح مركز جديد
            if target_state != 'NEUTRAL' and current_state == 'NEUTRAL':
                entry_price = current_bar['close']
                entry_time = current_time
                
                # حساب حجم الصفقة
                risk_amount = account_balance * config.position_size_percent
                position_size = risk_amount / entry_price 
                
                # تحديد مستويات SL/TP
                if config.stop_loss_percent:
                    sl_offset = entry_price * (config.stop_loss_percent / 100)
                    if target_state == 'LONG':
                        sl_price = entry_price - sl_offset
                    else:
                        sl_price = entry_price + sl_offset
                
                if config.take_profit_percent:
                    tp_offset = entry_price * (config.take_profit_percent / 100)
                    if target_state == 'LONG':
                        tp_price = entry_price + tp_offset
                    else:
                        tp_price = entry_price - tp_offset

                current_state = target_state
                trade_id = str(uuid.uuid4())
                entering_trade = True
                
                # حساب نسبة المخاطرة إلى العائد
                risk_reward_ratio = 0.0
                if sl_price > 0 and tp_price > 0:
                    if target_state == 'LONG':
                        risk = entry_price - sl_price
                        reward = tp_price - entry_price
                    else:
                        risk = sl_price - entry_price
                        reward = entry_price - tp_price
                    risk_reward_ratio = reward / risk if risk != 0 else 0
                
                # إنشاء سجل الصفقة
                commission = entry_price * position_size * config.commission_rate
                trade = Trade(
                    id=trade_id,
                    symbol=symbol,
                    entry_time=entry_time,
                    exit_time=None,
                    entry_price=entry_price,
                    exit_price=None,
                    position_type='long' if target_state == 'LONG' else 'short',
                    position_size=position_size,
                    pnl=None,
                    pnl_percentage=None,
                    commission=commission,
                    slippage=0,
                    stop_loss=sl_price if config.stop_loss_percent else None,
                    take_profit=tp_price if config.take_profit_percent else None,
                    exit_reason=None,
                    metadata={
                        'strategy': config.strategy_config.get('name', 'Unknown'),
                        'decision_reason': decision.reason if decision else None,
                        'confidence': decision.confidence if decision else None,
                        'risk_reward_ratio': risk_reward_ratio
                    }
                )
                trades.append(trade)

            # 3️⃣ إنشاء كائن الشمعة البصرية مع كل البيانات
            # استخراج بيانات المؤشرات من البار الحالي
            indicators = {}
            if hasattr(strategy_engine, 'current_data_frame'):
                processed_df = strategy_engine.current_data_frame
                
                # نتأكد أن هناك بيانات
                if processed_df is not None and len(processed_df) > 0:
                
                    
                    # نأخذ الصف الأخير (لأننا في الشمعة رقم i)
                    last_row = processed_df.iloc[-1]
                    
                    # نملأ قاموس المؤشرات
                   
                    for col in processed_df.columns:
                        # نتجاهل الأعمدة الأساسية
                        if col not in ['open', 'high', 'low', 'close', 'volume']:
                            val = last_row[col]
                            if pd.notna(val):
                                indicators[col] = float(val)
            
            # حساب الربح الحالي إذا كان هناك مركز مفتوح
            current_pnl = 0.0
            if current_state != 'NEUTRAL' and entry_price > 0:
                if current_state == 'LONG':
                    current_pnl = (current_bar['close'] - entry_price) * position_size
                else:  # SHORT
                    current_pnl = (entry_price - current_bar['close']) * position_size
            
            # حساب نسبة المخاطرة إلى العائد الحالية
            current_risk_reward_ratio = 0.0
            if current_state != 'NEUTRAL' and sl_price > 0 and tp_price > 0:
                if current_state == 'LONG':
                    risk = entry_price - sl_price
                    reward = tp_price - entry_price
                else:
                    risk = sl_price - entry_price
                    reward = entry_price - tp_price
                current_risk_reward_ratio = reward / risk if risk != 0 else 0
            
            # إنشاء VisualCandle مع كل البيانات



            t0 = time.perf_counter()

            visual_candle = VisualCandle(
                timestamp=current_time,
                open=float(current_bar['open']),
                high=float(current_bar['high']),
                low=float(current_bar['low']),
                close=float(current_bar['close']),
                volume=float(current_bar['volume']),
                indicators=indicators,
                strategy_decision=decision.action.value if decision else None,
                triggered_rules=getattr(decision, 'triggered_rules', []) if decision else [],
                confidence=decision.confidence if decision else None,
                position_state=current_state,
                # البيانات المالية
                account_balance=current_account_balance,
                cumulative_pnl=cumulative_pnl,
                position_size=position_size,
                entry_price=entry_price,
                stop_loss=sl_price,
                take_profit=tp_price,
                risk_reward_ratio=current_risk_reward_ratio,
                current_pnl=current_pnl,
                unrealized_pnl=unrealized_pnl
            )
            
            # 4️⃣ إضافة بيانات الصفقة إذا كان هناك دخول/خروج في هذه الشمعة
            if entering_trade:
                visual_candle.trade_action = f"ENTRY_{target_state}"
                visual_candle.trade_id = trade_id
                visual_candle.trade_price = float(entry_price)
                visual_candle.trade_size = float(position_size)
                
                # تسجيل نقطة التداول
                trade_points.append({
                    "timestamp": current_time,
                    "type": "entry",
                    "trade_id": trade_id,
                    "price": float(entry_price),
                    "position_type": target_state.lower(),
                    "position_size": float(position_size),
                    "entry_price": float(entry_price),
                    "stop_loss": float(sl_price),
                    "take_profit": float(tp_price),
                    "indicators_snapshot": indicators,
                    "decision_reason": decision.reason if decision else None,
                    "confidence": decision.confidence if decision else None,
                    "account_balance_before": account_balance,
                    "risk_reward_ratio": current_risk_reward_ratio
                })
            
            if exiting_trade:
                visual_candle.trade_action = f"EXIT_{current_state}"
                visual_candle.trade_id = trade_id
                visual_candle.trade_price = float(exit_price)
                visual_candle.pnl = float(pnl)
                visual_candle.pnl_percentage = float(pnl_percentage)
                
                # تسجيل نقطة الخروج
                trade_points.append({
                    "timestamp": current_time,
                    "type": "exit",
                    "trade_id": trade_id,
                    "price": float(exit_price),
                    "exit_reason": exit_reason,
                    "pnl": float(pnl),
                    "pnl_percentage": float(pnl_percentage),
                    "entry_price": float(entry_price),
                    "position_size": float(position_size),
                    "position_type": current_state.lower(),
                    "holding_period": (current_time - entry_time).total_seconds() / 3600 if entry_time else 0,
                    "account_balance_after": account_balance,
                    "cumulative_pnl": cumulative_pnl
                })
            
            visual_candles.append(visual_candle)
            t_visual += time.perf_counter() - t0
            t_loop += time.perf_counter() - t_loop_start



        # إغلاق أي مركز مفتوح في نهاية البيانات
        if current_state != 'NEUTRAL' and trade_id:
            exit_price = data['close'].iloc[-1]
            
            # حساب الربح/الخسارة
            if current_state == 'LONG':
                pnl = (exit_price - entry_price) * position_size
            else:  # SHORT
                pnl = (entry_price - exit_price) * position_size
            
            initial_investment = entry_price * position_size
            pnl_percentage = (pnl / initial_investment) * 100 if initial_investment != 0 else 0
            
            self._close_trade_logic(trades, trade_id, exit_price, data.index[-1], "End of Data", pnl, pnl_percentage)
            account_balance += pnl
            cumulative_pnl += pnl
            equity_curve.append(account_balance)
            
            # تحديث آخر شمعة
            if visual_candles:
                last_candle = visual_candles[-1]
                last_candle.trade_action = f"EXIT_{current_state}"
                last_candle.trade_id = trade_id
                last_candle.trade_price = float(exit_price)
                last_candle.pnl = float(pnl)
                last_candle.pnl_percentage = float(pnl_percentage)
                last_candle.account_balance = account_balance
                last_candle.cumulative_pnl = cumulative_pnl

        print("====== BACKTEST PROFILING ======")
        print(f"🕯️ Candles count: {len(data)}")
        print(f"⏱️ Strategy total time: {t_strategy:.2f}s")
        print(f"📊 VisualCandle total time: {t_visual:.2f}s")
        print(f"🔁 Loop overhead total time: {t_loop:.2f}s")
        print(f"🔥 TOTAL simulate time: {time.perf_counter() - t_total_start:.2f}s")
        print("================================")


        return trades, equity_curve, visual_candles, trade_points


    def _convert_to_serializable(self, obj):
        """تحويل الكائنات إلى صيغة قابلة للتسلسل (لـ JSON)"""
        import numpy as np
        import pandas as pd
        from datetime import datetime
        
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return [self._convert_to_serializable(x) for x in obj.tolist()]
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(x) for x in obj]
        elif pd.isna(obj):  # للتعامل مع NaN
            return None
        else:
            return obj



    def _close_trade_logic(self, trades: List[Trade], trade_id: str, exit_price: float, 
                          exit_time: datetime, reason: str, pnl: float, pnl_percentage: float):
        """دالة مساعدة لتحديث بيانات الصفقة عند الإغلاق"""
        for trade in trades:
            if trade.id == trade_id and trade.exit_time is None:
                trade.exit_time = exit_time
                trade.exit_price = exit_price
                trade.exit_reason = reason
                trade.pnl = pnl
                trade.pnl_percentage = pnl_percentage
                
                # حساب PNL
                if trade.position_type == 'long':
                    trade.pnl = (exit_price - trade.entry_price) * trade.position_size
                else:
                    trade.pnl = (trade.entry_price - exit_price) * trade.position_size
                
                # حساب العمولة النهائية
                commission_exit = exit_price * trade.position_size * 0.001 # (استخدم 0.001 مؤقتاً أو خذها من config)
                trade.commission += commission_exit
                
                # خصم العمولة من الربح
                trade.pnl -= trade.commission
                
                if trade.entry_price > 0:
                    trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.position_size)) * 100
                break






    def _update_capital(self, trades: List[Trade], initial_capital: float) -> float:
        """دالة مساعدة لحساب رأس المال الحالي بناءً على جميع الصفقات المغلقة"""
        current_capital = initial_capital
        for trade in trades:
            # نجمع الربح/الخسارة من الصفقات المغلقة فقط
            if trade.exit_time is not None and trade.pnl is not None:
                current_capital += trade.pnl
        return current_capital











    async def _create_backtest_result(
        self,
        config: BacktestConfig,
        trades: List[Trade],
        equity_curve: List[float],
        visual_candles: List[VisualCandle],
        trade_points: List[Dict[str, Any]],        
        execution_start: datetime
    ) -> BacktestResult:
        """إنشاء كائن النتيجة النهائية وحساب المقاييس"""
        import uuid
        from datetime import datetime
        from typing import Dict
        
        # 1. استخدام حاسبة المقاييس
        metrics = self.metrics_calculator.calculate(trades, config.initial_capital)
        
        execution_time = (datetime.utcnow() - execution_start).total_seconds()
        
        # 2. حساب القيم الأساسية
        final_capital = equity_curve[-1] if equity_curve else config.initial_capital
        total_pnl = final_capital - config.initial_capital
        total_pnl_percent = (total_pnl / config.initial_capital * 100) if config.initial_capital > 0 else 0
        
        # 3. حساب منحنى الانخفاض
        drawdown_curve = self.metrics_calculator._calculate_drawdown_curve(equity_curve)
        
        # 4. حساب الحقول الإضافية المطلوبة
        basic_metrics = self.metrics_calculator._calculate_basic_metrics(trades)
        risk_metrics = self.metrics_calculator._calculate_risk_metrics(equity_curve, drawdown_curve)
        timing_metrics = self.metrics_calculator._calculate_timing_metrics(trades)
        advanced_metrics = self.metrics_calculator._calculate_advanced_metrics(trades, equity_curve)
        
        # 5. حساب العوائد الشهرية والسنوية (مبسطة)
        monthly_returns = self._calculate_monthly_returns(equity_curve, config)
        yearly_returns = self._calculate_yearly_returns(equity_curve, config)
        
        # 6. حساب أداء الرموز
        symbols_performance = self._calculate_symbols_performance(trades, config)

        indicator_data = {}
        if visual_candles:
            # استخراج أسماء جميع المؤشرات من أول شمعة
            first_candle = visual_candles[0]
            for indicator_name in first_candle.indicators.keys():
                indicator_data[indicator_name] = {
                    "values": [candle.indicators.get(indicator_name) for candle in visual_candles],
                    "timestamps": [candle.timestamp for candle in visual_candles]
                }


        # 7. إنشاء BacktestResult الكامل
        return BacktestResult(
            # ★ الحقول الأساسية
            id=str(uuid.uuid4()),
            config=config,
            execution_time_seconds=execution_time,
            timestamp=datetime.utcnow(),


            
            visual_candles=visual_candles,
            trade_points=trade_points,
            indicator_data=indicator_data,
            # ★ الأداء العام
            initial_capital=config.initial_capital,
            final_capital=final_capital,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,  # ★ الاسم الصحيح من schemas.py
            annual_return_percent=metrics.get('annual_return_percent', 0.0),
            
            # ★ العائد المعدل بالمخاطرة
            sharpe_ratio=metrics.get('sharpe_ratio', 0.0),
            sortino_ratio=metrics.get('sortino_ratio', 0.0),
            calmar_ratio=metrics.get('calmar_ratio', 0.0),
            
            # ★ المقاييس الأساسية
            total_trades=len(trades),
            winning_trades=basic_metrics.get('winning_trades', 0),
            losing_trades=basic_metrics.get('losing_trades', 0),
            win_rate=basic_metrics.get('win_rate', 0.0),
            profit_factor=basic_metrics.get('profit_factor', 0.0),
            expectancy=basic_metrics.get('expectancy', 0.0),
            
            # ★ المخاطرة
            max_drawdown_percent=risk_metrics.get('max_drawdown_percent', 0.0),
            max_drawdown_duration_days=risk_metrics.get('max_drawdown_duration_days', 0),
            volatility_annual=risk_metrics.get('volatility_annual', 0.0),
            var_95=risk_metrics.get('var_95', 0.0),
            cvar_95=risk_metrics.get('cvar_95', 0.0),
            
            # ★ التفاصيل
            trades=trades,  # ★ الصفقات نفسها (مهم!)
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            monthly_returns=monthly_returns,
            yearly_returns=yearly_returns,
            
            # ★ تحليل الصفقات
            avg_winning_trade=basic_metrics.get('avg_winning_trade', 0.0),
            avg_losing_trade=basic_metrics.get('avg_losing_trade', 0.0),
            largest_winning_trade=basic_metrics.get('largest_winning_trade', 0.0),
            largest_losing_trade=basic_metrics.get('largest_losing_trade', 0.0),
            avg_trade_duration_hours=timing_metrics.get('avg_trade_duration_hours', 0.0),
            
            # ★ ربحية الرموز
            symbols_performance=symbols_performance,
            
            # ★ الكفاءة
            system_quality_number=advanced_metrics.get('system_quality_number', 0.0),
            kelly_criterion=advanced_metrics.get('kelly_criterion', 0.0),
            
            # ★ الحقول الاختيارية
            recovery_factor=advanced_metrics.get('recovery_factor'),
            ulcer_index=advanced_metrics.get('ulcer_index'),
            raw_data=None
        )



    # async def _create_backtest_result(
    #     self,
    #     config: BacktestConfig,
    #     trades: List[Trade],
    #     equity_curve: List[float],
    #     execution_start: datetime
    # ) -> BacktestResult:
    #     """إنشاء كائن النتيجة النهائية وحساب المقاييس"""
    #     # 1. استخدام حاسبة المقاييس
    #     metrics = self.metrics_calculator.calculate(trades, config.initial_capital)
        
    #     execution_time = (datetime.utcnow() - execution_start).total_seconds()
        
    #     # 2. ملء الـ BacktestResult
    #     return BacktestResult(
    #         strategy_name=config.name,
    #         total_trades=len(trades),
    #         winning_trades=metrics['winning_trades'],
    #         losing_trades=metrics['losing_trades'],
    #         win_rate=metrics['win_rate'],
    #         total_pnl=metrics['total_pnl'],
    #         total_pnl_percentage=metrics['total_pnl_percentage'],
    #         max_drawdown_percent=metrics['max_drawdown_percent'],
    #         sharpe_ratio=metrics['sharpe_ratio'],
    #         equity_curve=equity_curve,
    #         execution_time_seconds=execution_time,
    #         trades_summary=[] # يمكن ملؤها بالتفاصيل إذا أردت
    #     )








    def _calculate_monthly_returns(self, equity_curve: List[float], config: BacktestConfig) -> Dict[str, float]:
        """
        حساب العوائد الشهرية الحقيقية بناءً على منحنى الأسهم والبيانات التاريخية
        
        Args:
            equity_curve: منحنى رأس المال عبر الوقت
            config: إعدادات الباك-تست
        
        Returns:
            Dict[str, float]: قاموس بالعوائد الشهرية بنسبة مئوية {yyyy-mm: return%}
        """
        if len(equity_curve) < 10:  # الحد الأدنى للمعنى الإحصائي
            return {}
        
        try:

            
            # 1. إنشاء تواريخ واقعية بناءً على timeframe
            timeframes = {
                '1m': 'T', '5m': '5T', '15m': '15T', '30m': '30T',
                '1h': 'H', '2h': '2H', '4h': '4H', '6h': '6H', '8h': '8H', '12h': '12H',
                '1d': 'D', '3d': '3D', '1w': 'W', '1M': 'M'
            }
            
            freq = timeframes.get(config.timeframe, 'H')  # افتراضي ساعة
            
            # حساب عدد البارات بناءً على الفترة الزمنية
            start_date = config.start_date
            end_date = config.end_date
            
            # إنشاء التواريخ لكل نقطة في equity_curve
            if len(equity_curve) == 1:
                dates = [start_date]
            else:
                dates = pd.date_range(
                    start=start_date, 
                    end=end_date, 
                    periods=len(equity_curve),
                    tz=start_date.tzinfo
                )
            
            # 2. إنشاء DataFrame للتحليل
            df = pd.DataFrame({
                'date': dates,
                'equity': equity_curve
            })
            df.set_index('date', inplace=True)
            
            # 3. إعادة عينة إلى نهاية كل شهر
            monthly_equity = df['equity'].resample('M').last()
            
            if len(monthly_equity) < 3:  # نحتاج شهرين على الأقل لحساب العائد
                return {}
            
            # 4. حساب العوائد الشهرية
            monthly_returns = {}
            for i in range(1, len(monthly_equity)):
                current_date = monthly_equity.index[i]
                prev_date = monthly_equity.index[i-1]
                
                current_equity = monthly_equity.iloc[i]
                prev_equity = monthly_equity.iloc[i-1]
                
                if prev_equity > 0:
                    monthly_return = ((current_equity - prev_equity) / prev_equity) * 100
                    key = current_date.strftime("%Y-%m")
                    monthly_returns[key] = float(monthly_return)
            
            # 5. إضافة إحصائيات إضافية
            # if monthly_returns:
            #     returns_list = list(monthly_returns.values())
            #     monthly_returns['_stats'] = {
            #         'avg_monthly_return': float(np.mean(returns_list)),
            #         'std_monthly_return': float(np.std(returns_list)),
            #         'best_month': max(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None,
            #         'worst_month': min(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None,
            #         'positive_months': sum(1 for r in returns_list if r > 0),
            #         'negative_months': sum(1 for r in returns_list if r < 0),
            #         'consistency_rate': (sum(1 for r in returns_list if r > 0) / len(returns_list) * 100) if returns_list else 0
            #     }
            
            # return monthly_returns
            
            if monthly_returns:
                returns_list = list(monthly_returns.values())
                stats = {
                    'avg_monthly_return': float(np.mean(returns_list)),
                    'std_monthly_return': float(np.std(returns_list)),
                    'best_month': max(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None,
                    'worst_month': min(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None,
                    'positive_months': int(sum(1 for r in returns_list if r > 0)),
                    'negative_months': int(sum(1 for r in returns_list if r < 0)),
                    'consistency_rate': float((sum(1 for r in returns_list if r > 0) / len(returns_list) * 100) if returns_list else 0)
                }
                
                # تحويل كل القيم إلى Python types
                monthly_returns_clean = {}
                for k, v in monthly_returns.items():
                    monthly_returns_clean[k] = float(v) if isinstance(v, (np.float32, np.float64, float)) else v
                
                monthly_returns_clean['_stats'] = stats
                return self._convert_to_serializable(monthly_returns_clean)
            
            return {}
        

        except Exception as e:
            print(f"❌ خطأ في حساب العوائد الشهرية: {e}")
            traceback.print_exc()
            return {}

    def _calculate_yearly_returns(self, equity_curve: List[float], config: BacktestConfig) -> Dict[str, float]:
        """
        حساب العوائد السنوية الحقيقية بناءً على منحنى الأسهم
        
        Args:
            equity_curve: منحنى رأس المال عبر الوقت
            config: إعدادات الباك-تست
        
        Returns:
            Dict[str, float]: قاموس بالعوائد السنوية بنسبة مئوية {yyyy: return%}
        """
        if len(equity_curve) < 50:  # الحد الأدنى للمعنى الإحصائي
            return {}
        
        try:

            
            # 1. إنشاء تواريخ واقعية
            start_date = config.start_date
            end_date = config.end_date
            
            if len(equity_curve) == 1:
                dates = [start_date]
            else:
                dates = pd.date_range(
                    start=start_date, 
                    end=end_date, 
                    periods=len(equity_curve),
                    tz=start_date.tzinfo
                )
            
            # 2. إنشاء DataFrame
            df = pd.DataFrame({
                'date': dates,
                'equity': equity_curve
            })
            df.set_index('date', inplace=True)
            
            # 3. استخراج السنوات الموجودة في البيانات
            df['year'] = df.index.year
            yearly_data = df.groupby('year')['equity'].agg(['first', 'last'])
            
            yearly_returns = {}
            for year, row in yearly_data.iterrows():
                if row['first'] > 0:
                    yearly_return = ((row['last'] - row['first']) / row['first']) * 100
                    yearly_returns[str(year)] = float(yearly_return)
            
            # 4. حساب العائد السنوي المعدل (Annualized)
            if len(equity_curve) >= 2:
                total_return = ((equity_curve[-1] - equity_curve[0]) / equity_curve[0]) * 100 if equity_curve[0] > 0 else 0
                
                # حساب عدد السنوات الكسرية
                days_diff = (end_date - start_date).days
                years_diff = days_diff / 365.25
                
                if years_diff > 0:
                    annualized_return = ((1 + total_return/100) ** (1/years_diff) - 1) * 100
                    yearly_returns['annualized'] = float(annualized_return)
                    yearly_returns['cagr'] = float(annualized_return)  # معدل النمو السنوي المركب
            
            # 5. إضافة إحصائيات إضافية
            if yearly_returns and len(yearly_returns) > 1:
                # yearly_returns_only = [v for k, v in yearly_returns.items() if k.isdigit()]
                # if yearly_returns_only:
                #     yearly_returns['_stats'] = {
                #         'avg_yearly_return': float(np.mean(yearly_returns_only)),
                #         'std_yearly_return': float(np.std(yearly_returns_only)),
                #         'best_year': max((k for k in yearly_returns if k.isdigit()), 
                #                     key=lambda x: yearly_returns[x]),
                #         'worst_year': min((k for k in yearly_returns if k.isdigit()), 
                #                         key=lambda x: yearly_returns[x]),
                #         'positive_years': sum(1 for r in yearly_returns_only if r > 0),
                #         'max_consecutive_positive': self._max_consecutive_positive(yearly_returns_only),
                #         'max_consecutive_negative': self._max_consecutive_negative(yearly_returns_only)
                #     }

                yearly_returns_only = [v for k, v in yearly_returns.items() if k.isdigit()]
                if yearly_returns_only:
                    stats = {
                        'avg_yearly_return': float(np.mean(yearly_returns_only)),
                        'std_yearly_return': float(np.std(yearly_returns_only)),
                        'best_year': max((k for k in yearly_returns if k.isdigit()), 
                                    key=lambda x: yearly_returns[x]),
                        'worst_year': min((k for k in yearly_returns if k.isdigit()), 
                                        key=lambda x: yearly_returns[x]),
                        'positive_years': int(sum(1 for r in yearly_returns_only if r > 0)),
                        'max_consecutive_positive': int(self._max_consecutive_positive(yearly_returns_only)),
                        'max_consecutive_negative': int(self._max_consecutive_negative(yearly_returns_only))
                    }
                    
                    yearly_returns['_stats'] = stats
            
            # تحويل كل القيم إلى Python types
            yearly_returns_clean = {}
            for k, v in yearly_returns.items():
                if isinstance(v, (np.float32, np.float64, float, int)):
                    yearly_returns_clean[k] = float(v)
                elif isinstance(v, dict):
                    yearly_returns_clean[k] = self._convert_to_serializable(v)
                else:
                    yearly_returns_clean[k] = v
            
            return self._convert_to_serializable(yearly_returns_clean)
            

            
        except Exception as e:
            print(f"❌ خطأ في حساب العوائد السنوية: {e}")
            traceback.print_exc()
            return {}

    def _calculate_symbols_performance(self, trades: List[Trade], config: BacktestConfig) -> Dict[str, Dict[str, Any]]:
        """
        حساب أداء متقدم لكل رمز على حدة
        
        Args:
            trades: قائمة الصفقات
            config: إعدادات الباك-تست
        
        Returns:
            Dict[str, Dict[str, Any]]: قاموس بالأداء التفصيلي لكل رمز
        """
        symbols_performance = {}
        
        for symbol in config.symbols:
            # تصفية صفقات الرمز
            symbol_trades = [t for t in trades if t.symbol == symbol]
            
            if not symbol_trades:
                continue
            
            # الصفقات المكتملة فقط
            completed_trades = [t for t in symbol_trades 
                            if t.exit_time is not None 
                            and t.pnl is not None 
                            and t.entry_price is not None]
            
            if not completed_trades:
                # تحليل الصفقات المفتوحة (إذا وجدت)
                open_trades = [t for t in symbol_trades if t.exit_time is None]
                if open_trades:
                    symbols_performance[symbol] = self._analyze_open_trades(symbol, open_trades, config)
                continue
            
            # 1. المقاييس الأساسية
            total_trades = len(completed_trades)
            winning_trades = [t for t in completed_trades if t.pnl > 0]
            losing_trades = [t for t in completed_trades if t.pnl <= 0]
            breakeven_trades = [t for t in completed_trades if t.pnl == 0]
            
            winning_count = len(winning_trades)
            losing_count = len(losing_trades)
            breakeven_count = len(breakeven_trades)
            
            # 2. إحصائيات الربح/الخسارة
            gross_profit = sum(t.pnl for t in winning_trades)
            gross_loss = abs(sum(t.pnl for t in losing_trades))
            net_profit = gross_profit - gross_loss
            
            # 3. حساب القيمة المستثمرة (مبني على الدخول)
            total_invested = sum(t.entry_price * t.position_size for t in completed_trades)
            avg_position_size = np.mean([t.position_size for t in completed_trades]) if completed_trades else 0
            
            # 4. نسب الأداء
            win_rate = (winning_count / total_trades * 100) if total_trades > 0 else 0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([abs(t.pnl) for t in losing_trades]) if losing_trades else 0
            
            # 5. نسبة المخاطرة/العائد (Risk/Reward Ratio)
            avg_rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            
            # 6. تحليل الصفقات الفردية
            pnls = [t.pnl for t in completed_trades]
            pnl_percentages = [t.pnl_percentage for t in completed_trades if t.pnl_percentage is not None]
            
            # 7. تحليل التوقيت
            durations = []
            for trade in completed_trades:
                if trade.entry_time and trade.exit_time:
                    duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600  # ساعات
                    durations.append(duration)
            
            avg_duration = np.mean(durations) if durations else 0
            
            # 8. تحليل التوزيع الزمني
            monthly_trades = self._analyze_trades_by_month(completed_trades)
            hourly_trades = self._analyze_trades_by_hour(completed_trades)
            
            # 9. حساب الحد الأقصى للانخفاض لكل رمز
            symbol_equity_curve = self._build_symbol_equity_curve(symbol, completed_trades, config.initial_capital)
            symbol_drawdown_curve = self.metrics_calculator._calculate_drawdown_curve(symbol_equity_curve)
            max_drawdown = max(symbol_drawdown_curve) if symbol_drawdown_curve else 0
            
            # 10. حساب تقلبات الرمز
            returns = self.metrics_calculator._calculate_returns(symbol_equity_curve)
            volatility = np.std(returns) * np.sqrt(252) * 100 if returns else 0
            
            # 11. تجميع كل المقاييس
            # symbols_performance[symbol] = {
            #     # الأساسية
            #     'total_trades': total_trades,
            #     'completed_trades': len(completed_trades),
            #     'open_trades': len(symbol_trades) - len(completed_trades),
            #     'winning_trades': winning_count,
            #     'losing_trades': losing_count,
            #     'breakeven_trades': breakeven_count,
                
            #     # الأداء المالي
            #     'gross_profit': float(gross_profit),
            #     'gross_loss': float(gross_loss),
            #     'net_profit': float(net_profit),
            #     'total_invested': float(total_invested),
            #     'avg_position_size': float(avg_position_size),
                
            #     # النسب
            #     'win_rate': float(win_rate),
            #     'profit_factor': float(profit_factor) if profit_factor != float('inf') else None,
            #     'avg_win': float(avg_win),
            #     'avg_loss': float(avg_loss),
            #     'avg_rr_ratio': float(avg_rr_ratio),
                
            #     # الإحصائيات
            #     'best_trade': float(max(pnls)) if pnls else 0,
            #     'worst_trade': float(min(pnls)) if pnls else 0,
            #     'avg_pnl': float(np.mean(pnls)) if pnls else 0,
            #     'std_pnl': float(np.std(pnls)) if len(pnls) > 1 else 0,
            #     'sharpe_ratio': (np.mean(pnls) / np.std(pnls) * np.sqrt(252)) if len(pnls) > 1 and np.std(pnls) > 0 else 0,
                
            #     # التوقيت
            #     'avg_trade_duration_hours': float(avg_duration),
            #     'min_duration': float(min(durations)) if durations else 0,
            #     'max_duration': float(max(durations)) if durations else 0,
                
            #     # المخاطرة
            #     'max_drawdown_percent': float(max_drawdown),
            #     'volatility_percent': float(volatility),
            #     'var_95': self._calculate_symbol_var(completed_trades, 0.95),
            #     'cvar_95': self._calculate_symbol_cvar(completed_trades, 0.95),
                
            #     # تحليل متقدم
            #     'expectancy': float((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)) if avg_loss > 0 else 0,
            #     'kelly_criterion': float(win_rate/100 - ((100-win_rate)/100) / (avg_win/avg_loss)) if avg_loss > 0 and avg_win > 0 else 0,
            #     'system_quality_number': self._calculate_symbol_sqn(completed_trades),
                
            #     # تحليل التوزيع
            #     'monthly_distribution': monthly_trades,
            #     'hourly_distribution': hourly_trades,
            #     'pnl_distribution': self._analyze_pnl_distribution(pnls),
                
            #     # بيانات إضافية للرسم البياني
            #     '_equity_curve': symbol_equity_curve,
            #     '_drawdown_curve': symbol_drawdown_curve
            # }


            performance_data = {
                # الأساسية
                'total_trades': int(len(symbol_trades)),
                'completed_trades': int(len(completed_trades)),
                'open_trades': int(len(symbol_trades) - len(completed_trades)),
                'winning_trades': int(winning_count),
                'losing_trades': int(losing_count),
                'breakeven_trades': int(breakeven_count),
                
                # الأداء المالي
                'gross_profit': float(gross_profit),
                'gross_loss': float(gross_loss),
                'net_profit': float(net_profit),
                'total_invested': float(total_invested),
                'avg_position_size': float(avg_position_size),
                
                # النسب
                'win_rate': float(win_rate),
                'profit_factor': float(profit_factor) if profit_factor != float('inf') else None,
                'avg_win': float(avg_win),
                'avg_loss': float(avg_loss),
                'avg_rr_ratio': float(avg_rr_ratio),
                
                # الإحصائيات
                'best_trade': float(max(pnls)) if pnls else 0.0,
                'worst_trade': float(min(pnls)) if pnls else 0.0,
                'avg_pnl': float(np.mean(pnls)) if pnls else 0.0,
                'std_pnl': float(np.std(pnls)) if len(pnls) > 1 else 0.0,
                'sharpe_ratio': float((np.mean(pnls) / np.std(pnls) * np.sqrt(252)) if len(pnls) > 1 and np.std(pnls) > 0 else 0.0),
                
                # التوقيت
                'avg_trade_duration_hours': float(avg_duration),
                'min_duration': float(min(durations)) if durations else 0.0,
                'max_duration': float(max(durations)) if durations else 0.0,
                
                # المخاطرة
                'max_drawdown_percent': float(max_drawdown),
                'volatility_percent': float(volatility),
                'var_95': float(self._calculate_symbol_var(completed_trades, 0.95)),
                'cvar_95': float(self._calculate_symbol_cvar(completed_trades, 0.95)),
                
                # تحليل متقدم
                'expectancy': float((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)) if avg_loss > 0 else 0.0,
                'kelly_criterion': float(win_rate/100 - ((100-win_rate)/100) / (avg_win/avg_loss)) if avg_loss > 0 and avg_win > 0 else None,
                'system_quality_number': float(self._calculate_symbol_sqn(completed_trades)),
                
                # تحليل التوزيع (تحويل الأنواع)
                'monthly_distribution': {str(k): int(v) for k, v in monthly_trades.items()} if monthly_trades else None,
                'hourly_distribution': {int(k): int(v) for k, v in hourly_trades.items()} if hourly_trades else None,
                'pnl_distribution': self._convert_to_serializable(PnlDistribution) if PnlDistribution else None,
                
                # بيانات إضافية للرسم البياني
                '_equity_curve': [float(x) for x in symbol_equity_curve],
                '_drawdown_curve': [float(x) for x in symbol_drawdown_curve]
            }
            
            symbols_performance[symbol] = self._convert_to_serializable(performance_data)


        return symbols_performance    
    


    def _max_consecutive_positive(self, values: List[float]) -> int:
        """حساب أقصى عدد متتالي من القيم الموجبة"""
        max_streak = 0
        current_streak = 0
        
        for value in values:
            if value > 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak

    def _max_consecutive_negative(self, values: List[float]) -> int:
        """حساب أقصى عدد متتالي من القيم السالبة"""
        max_streak = 0
        current_streak = 0
        
        for value in values:
            if value < 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak

    def _build_symbol_equity_curve(self, symbol: str, trades: List[Trade], initial_capital: float) -> List[float]:
        """بناء منحنى الأسهم لرمز معين"""
        if not trades:
            return [initial_capital]
        
        # ترتيب الصفقات حسب وقت الدخول
        sorted_trades = sorted(trades, key=lambda x: x.entry_time)
        
        curve = [initial_capital]
        current_equity = initial_capital
        
        for trade in sorted_trades:
            # تحديث عند الدخول (العمولة)
            entry_cost = trade.commission if trade.commission else 0
            current_equity -= entry_cost
            curve.append(current_equity)
            
            # تحديث عند الخروج
            if trade.exit_time and trade.pnl is not None:
                current_equity += trade.pnl
                curve.append(current_equity)
        
        return curve

    def _analyze_trades_by_month(self, trades: List[Trade]) -> Dict[str, int]:
        """تحليل الصفقات حسب الشهر"""
        monthly_counts = {}
        
        for trade in trades:
            if trade.entry_time:
                month_key = trade.entry_time.strftime("%Y-%m")
                monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
        
        return monthly_counts

    def _analyze_trades_by_hour(self, trades: List[Trade]) -> Dict[int, int]:
        """تحليل الصفقات حسب ساعة اليوم"""
        hourly_counts = {hour: 0 for hour in range(24)}
        
        for trade in trades:
            if trade.entry_time:
                hour = trade.entry_time.hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        return hourly_counts

    def _calculate_symbol_var(self, trades: List[Trade], confidence_level: float = 0.95) -> float:
        """حساب Value at Risk للرمز"""
        if not trades:
            return 0.0
        
        pnls = [t.pnl_percentage for t in trades if t.pnl_percentage is not None]
        if not pnls:
            return 0.0
        
        sorted_pnls = np.sort(pnls)
        var_index = int((1 - confidence_level) * len(sorted_pnls))
        
        if var_index < len(sorted_pnls):
            return float(-sorted_pnls[var_index])  # نرجع القيمة الإيجابية للخسارة
        else:
            return float(-sorted_pnls[-1] if sorted_pnls else 0)

    def _calculate_symbol_cvar(self, trades: List[Trade], confidence_level: float = 0.95) -> float:
        """حساب Conditional VaR للرمز"""
        if not trades:
            return 0.0
        
        pnls = [t.pnl_percentage for t in trades if t.pnl_percentage is not None]
        if not pnls:
            return 0.0
        
        sorted_pnls = np.sort(pnls)
        var_index = int((1 - confidence_level) * len(sorted_pnls))
        
        if var_index > 0:
            cvar = np.mean(sorted_pnls[:var_index])
            return float(-cvar)  # نرجع القيمة الإيجابية
        else:
            return 0.0

    def _calculate_symbol_sqn(self, trades: List[Trade]) -> float:
        """حساب System Quality Number للرمز"""
        if not trades:
            return 0.0
        
        pnls = [t.pnl_percentage for t in trades if t.pnl_percentage is not None]
        if not pnls or len(pnls) < 2:
            return 0.0
        
        mean_pnl = np.mean(pnls)
        std_pnl = np.std(pnls)
        
        if std_pnl == 0:
            return 0.0
        
        return float((mean_pnl / std_pnl) * np.sqrt(len(pnls)))

    def _analyze_pnl_distribution(self, pnls: List[float]) -> Dict[str, Any]:
        """تحليل توزيع الربح/الخسارة"""
        if not pnls:
            return {}
        
        from scipy import stats
        
        distribution = {
            'mean': float(np.mean(pnls)),
            'median': float(np.median(pnls)),
            'std': float(np.std(pnls)),
            'skewness': float(stats.skew(pnls)) if len(pnls) > 2 else 0,
            'kurtosis': float(stats.kurtosis(pnls)) if len(pnls) > 3 else 0,
            'q1': float(np.percentile(pnls, 25)),
            'q3': float(np.percentile(pnls, 75)),
            'iqr': float(np.percentile(pnls, 75) - np.percentile(pnls, 25)),
            'outliers': self._find_outliers(pnls)
        }
        
        return distribution

    def _find_outliers(self, data: List[float]) -> List[float]:
        """العثور على القيم المتطرفة"""
        if len(data) < 4:
            return []
        
        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        return [float(x) for x in data if x < lower_bound or x > upper_bound]

    def _analyze_open_trades(self, symbol: str, open_trades: List[Trade], config: BacktestConfig) -> Dict[str, Any]:
        """تحليل الصفقات المفتوحة"""
        if not open_trades:
            return {}
        
        current_values = []
        unrealized_pnls = []
        
        for trade in open_trades:
            # في التطبيق الحقيقي، تحتاج إلى سعر السوق الحالي
            # هنا سنفترض سعر الإغلاق الحالي هو نفس سعر الدخول (افتراضي)
            current_price = trade.entry_price
            
            if trade.position_type == 'long':
                unrealized_pnl = (current_price - trade.entry_price) * trade.position_size
            else:  # short
                unrealized_pnl = (trade.entry_price - current_price) * trade.position_size
            
            current_value = trade.entry_price * trade.position_size + unrealized_pnl
            
            current_values.append(current_value)
            unrealized_pnls.append(unrealized_pnl)
        
        total_unrealized_pnl = sum(unrealized_pnls)
        total_current_value = sum(current_values)
        
        return {
            'open_trades_count': len(open_trades),
            'total_unrealized_pnl': float(total_unrealized_pnl),
            'total_current_value': float(total_current_value),
            'avg_unrealized_pnl': float(np.mean(unrealized_pnls)) if unrealized_pnls else 0,
            'max_unrealized_pnl': float(max(unrealized_pnls)) if unrealized_pnls else 0,
            'min_unrealized_pnl': float(min(unrealized_pnls)) if unrealized_pnls else 0,
            'open_positions_summary': [
                {
                    'id': t.id,
                    'entry_price': t.entry_price,
                    'position_size': t.position_size,
                    'position_type': t.position_type,
                    'unrealized_pnl': float((current_price - t.entry_price) * t.position_size 
                                        if t.position_type == 'long' 
                                        else (t.entry_price - current_price) * t.position_size)
                }
                for t in open_trades
            ]
        }




# # # app/backtest/engine1.py
# # import asyncio
# # import numpy as np
# # import pandas as pd
# # from typing import Dict, List, Any, Optional, Tuple
# # from datetime import datetime, timedelta, timezone
# # import uuid
# # import warnings
# # import traceback

# # # ✅ تعديل الاستيرادات: استدعاء المحرك الجديد والكيانات المجردة
# # from trading_backend.app.services.strategy.strategy_engine1 import StrategyEngine, Decision, DecisionAction
# # # نحتفظ بالتقارير القديمة لنفس النتائج
# # from .schemas import BacktestConfig, BacktestResult, Trade, PositionType
# # from .metrics import PerformanceMetrics
# # from app.services.data_service import DataService
# # from app.services.strategy.schemas import StrategyConfig as StrategyConfigSchema

# # warnings.filterwarnings('ignore')

# # class BacktestEngine:
# #     """محرك الباك-تيست التاريخي (يعمل الآن كمحرك تنفيذي للقرارات)"""
    
# #     def __init__(self, data_service: DataService):
# #         self.data_service = data_service
# #         self.metrics_calculator = PerformanceMetrics()
        
# #     async def run_backtest(self, config: BacktestConfig) -> BacktestResult:
  
# #         start_time = datetime.utcnow()
# #         print(f"🚀 Starting backtest (Architecture: Strategy-Driven): {config.name}")
        
# #         try:
# #             # 1. جلب البيانات (نفس المنطق السابق)
# #             all_data = {}
# #             for symbol in config.symbols:
# #                 try:
# #                     days_required = (config.end_date - config.start_date).days + 30
# #                     data = await self.data_service.get_historical(
# #                         symbol=symbol, timeframe=config.timeframe,
# #                         market=config.market, days=days_required, use_cache=True
# #                     )
                    
# #                     if not data.empty:
# #                         data.index = pd.to_datetime(data.index, utc=True)
# #                         start = config.start_date.astimezone(timezone.utc)
# #                         end = config.end_date.astimezone(timezone.utc)
# #                         mask = (data.index >= start) & (data.index <= end)
# #                         filtered_data = data.loc[mask]
# #                         if not filtered_data.empty:
# #                             all_data[symbol] = filtered_data
# #                 except Exception as e:
# #                     print(f"❌ Error fetching data for {symbol}: {str(e)}")
            
# #             if not all_data:
# #                 raise ValueError("No data available for any symbol")
            
# #             # 2. محاكاة التداول
# #             trades = []
# #             equity_curve = [config.initial_capital]
# #             current_capital = config.initial_capital
            
# #             for symbol, data in all_data.items():
# #                 # ✅ نستدعي الدالة المعدلة بالكامل
# #                 symbol_trades, symbol_equity = await self._simulate_with_strategy(
# #                     symbol, data, config, current_capital
# #                 )
# #                 trades.extend(symbol_trades)
# #                 # تحديث منحنى الرأس المال
# #                 if len(symbol_equity) > 0:
# #                     equity_curve.extend(symbol_equity[1:]) # نبدأ من الفهرس 1 لتجنب تكرار رأس المال الأولي
# #                     current_capital = symbol_equity[-1]

# #             # 3. حساب المقاييس (نفس المنطق السابق)
# #             result = await self._create_backtest_result(
# #                 config=config, trades=trades, equity_curve=equity_curve, execution_start=start_time
# #             )
# #             # ... (طباعة النتائج والعودة) ...
# #             execution_time = (datetime.utcnow() - start_time).total_seconds()
# #             result.execution_time_seconds = execution_time
# #             return result

# #         except Exception as e:
# #             print(f"❌ Backtest failed: {str(e)}")
# #             traceback.print_exc()
# #             raise

# #     async def _simulate_with_strategy(
# #         self,
# #         symbol: str,
# #         data: pd.DataFrame,
# #         config: BacktestConfig,
# #         initial_capital: float
# #     ) -> Tuple[List[Trade], List[float]]:
# #         """
# #         محاكاة الصفقات باستخدام محرك استراتيجية منفصل (Black Box)
        
# #         ملاحظة معمارية:
# #         - هذه الدالة تمثل "Execution Engine".
# #         - الاستراتيجية (Strategy Engine) لا تعرف حالة الصفقة.
# #         - نحن هنا (الـ Backtest) من نحتفظ بالحالة ونتحقق من المخاطر.
# #         """
        
# #         trades = []
# #         equity_curve = [initial_capital]
# #         current_capital = initial_capital
        
# #         if len(data) < 50: # الحد الأدنى للبيانات لحساب المؤشرات
# #             return trades, equity_curve

# #         try:
# #             # 1. إنشاء محرك الاستراتيجية الجديد
# #             strategy_config_obj = StrategyConfigSchema(**config.strategy_config)
# #             strategy_engine = StrategyEngine(strategy_config_obj)
# #         except Exception as e:
# #             print(f"❌ خطأ في تكوين الاستراتيجية: {e}")
# #             return trades, equity_curve

# #         # حالة المحفظة (Portfolio State) - يدارها الـ Backtest فقط
# #         current_state = 'NEUTRAL' # LONG, SHORT, NEUTRAL
# #         entry_price = 0.0
# #         entry_time = None
# #         position_size = 0.0
# #         trade_id = None
# #         sl_price = 0.0
# #         tp_price = 0.0

# #         print(f"   📊 بدء المحاكاة لـ {symbol} باستخدام Black Box Strategy...")

# #         # 2. حلقة المحاكاة (Bar-by-Bar Simulation)
# #         # نقوم بتمرير البيانات تدريجياً للاستراتيجية ونبني القرارات
# #         for i in range(len(data)):
# #             current_bar = data.iloc[i]
# #             current_time = data.index[i]
            
# #             # أ) التحقق من إدارة المخاطر (SL/TP) قبل طلب القرار الجديد
# #             if current_state != 'NEUTRAL':
# #                 # التحقق من وقف الخسارة
# #                 if current_state == 'LONG':
# #                     if current_bar['low'] <= sl_price:
# #                         exit_price = sl_price
# #                         reason = "Stop Loss Hit"
# #                     elif current_bar['high'] >= tp_price:
# #                         exit_price = tp_price
# #                         reason = "Take Profit Hit"
# #                     else:
# #                         exit_price = None
# #                 elif current_state == 'SHORT':
# #                     if current_bar['high'] >= sl_price:
# #                         exit_price = sl_price
# #                         reason = "Stop Loss Hit"
# #                     elif current_bar['low'] <= tp_price:
# #                         exit_price = tp_price
# #                         reason = "Take Profit Hit"
# #                     else:
# #                         exit_price = None
                
# #                 # إذا تم تفعيل وقف الخسارة أو الربح
# #                 if exit_price is not None:
# #                     # حساب الربح/الخسارة
# #                     if current_state == 'LONG':
# #                         pnl = (exit_price - entry_price) * position_size
# #                     else: # SHORT
# #                         pnl = (entry_price - exit_price) * position_size
                    
# #                     # إغلاق الصفقة
# #                     self._close_trade_logic(trades, trade_id, exit_price, current_time, reason, pnl, exit_price * position_size * config.commission_rate)
# #                     current_state = 'NEUTRAL'
# #                     current_capital += pnl
# #                     equity_curve.append(current_capital)
# #                     trade_id = None
# #                     continue # الانتقال للشريط التالي

# #             # ب) طلب قرار من الاستراتيجية (Black Box Call)
# #             # نمرر البيانات حتى اللحظة الحالية
# #             # ⚠️ ملاحظة أداء: التقطيع (Slicing) في كل مرة مكلف حسابياً، لكنه ضروري للحفاظ على Black Box Interface
# #             slice_data = data.iloc[:i+1]
            
# #             try:
# #                 decision = await strategy_engine.run(slice_data)
# #             except Exception as e:
# #                 print(f"⚠️ Strategy Error at {current_time}: {e}")
# #                 continue

# #             # ج) معالجة القرار (Decision Logic)
# #             target_state = 'NEUTRAL'
            
# #             if decision.action == DecisionAction.BUY:
# #                 target_state = 'LONG'
# #             elif decision.action == DecisionAction.SELL:
# #                 target_state = 'SHORT'
# #             else:
# #                 target_state = 'NEUTRAL' # HOLD يعني الخروج للحياد أو البقاء عليه

# #             # د) تنفيذ الانتقالات (State Transition)
            
# #             # الحالة 1: إغلاق مركز (أو عكس الموقف)
# #             if target_state != current_state and current_state != 'NEUTRAL':
# #                 # نحتاج لإغلاق المركز الحالي أولاً
# #                 exit_price = current_bar['close'] # إغلاق عند سعر السوق
                
# #                 if current_state == 'LONG':
# #                     pnl = (exit_price - entry_price) * position_size
# #                 else:
# #                     pnl = (entry_price - exit_price) * position_size
                
# #                 commission = exit_price * position_size * config.commission_rate
# #                 self._close_trade_logic(trades, trade_id, exit_price, current_time, f"Signal: {decision.reason}", pnl, commission)
                
# #                 current_capital += pnl
# #                 equity_curve.append(current_capital)
# #                 current_state = 'NEUTRAL'
# #                 trade_id = None

# #             # الحالة 2: فتح مركز جديد
# #             if target_state != 'NEUTRAL' and current_state == 'NEUTRAL':
# #                 entry_price = current_bar['close']
# #                 entry_time = current_time
                
# #                 # حساب حجم الصفقة (من Backtest Config وليس Strategy)
# #                 risk_amount = current_capital * config.position_size_percent
# #                 # افتراض بسيط: نستخدم المخاطرة كحجم مباشر، أو يمكن حسابه بناءً على SL
# #                 position_size = risk_amount / entry_price 
                
# #                 # تحديد مستويات SL/TP
# #                 if config.stop_loss_percent:
# #                     sl_offset = entry_price * (config.stop_loss_percent / 100)
# #                     if target_state == 'LONG':
# #                         sl_price = entry_price - sl_offset
# #                     else:
# #                         sl_price = entry_price + sl_offset
                
# #                 if config.take_profit_percent:
# #                     tp_offset = entry_price * (config.take_profit_percent / 100)
# #                     if target_state == 'LONG':
# #                         tp_price = entry_price + tp_offset
# #                     else:
# #                         tp_price = entry_price - tp_offset

# #                 current_state = target_state
# #                 trade_id = str(uuid.uuid4())
                
# #                 # إنشاء سجل الصفقة
# #                 commission = entry_price * position_size * config.commission_rate
# #                 trade = Trade(
# #                     id=trade_id,
# #                     symbol=symbol,
# #                     entry_time=entry_time,
# #                     exit_time=None,
# #                     entry_price=entry_price,
# #                     exit_price=None,
# #                     position_type='long' if target_state == 'LONG' else 'short',
# #                     position_size=position_size,
# #                     pnl=None,
# #                     pnl_percentage=None,
# #                     commission=commission,
# #                     slippage=0, # يمكن إضافته لاحقاً
# #                     stop_loss=sl_price if config.stop_loss_percent else None,
# #                     take_profit=tp_price if config.take_profit_percent else None,
# #                     exit_reason=None,
# #                     metadata={
# #                         'strategy': config.strategy_config.get('name', 'Unknown'),
# #                         'decision_reason': decision.reason,
# #                         'confidence': decision.confidence
# #                     }
# #                 )
# #                 trades.append(trade)

# #         # إغلاق أي مركز مفتوح في نهاية البيانات
# #         if current_state != 'NEUTRAL' and trade_id:
# #             last_price = data['close'].iloc[-1]
# #             if current_state == 'LONG':
# #                 pnl = (last_price - entry_price) * position_size
# #             else:
# #                 pnl = (entry_price - last_price) * position_size
            
# #             self._close_trade_logic(trades, trade_id, last_price, data.index[-1], "End of Data", pnl, 0)
# #             current_capital += pnl
# #             equity_curve.append(current_capital)

# #         return trades, equity_curve

# #     def _close_trade_logic(self, trades, trade_id, exit_price, exit_time, reason, pnl, commission):
# #         """دالة مساعدة لتحديث بيانات الصفقة عند الإغلاق"""
# #         for trade in trades:
# #             if trade.id == trade_id and trade.exit_time is None:
# #                 trade.exit_time = exit_time
# #                 trade.exit_price = exit_price
# #                 trade.pnl = pnl - commission
# #                 if trade.entry_price > 0:
# #                     trade.pnl_percentage = (pnl / (trade.entry_price * trade.position_size)) * 100
# #                 trade.exit_reason = reason
# #                 trade.commission += commission
# #                 break

# #     async def _create_backtest_result(
# #         self,
# #         config: BacktestConfig,
# #         trades: List[Trade],
# #         equity_curve: List[float],
# #         execution_start: datetime
# #     ) -> BacktestResult:
# #         """إنشاء نتيجة الباك-تيست"""
        
# #         if not trades:
         
# #             return BacktestResult(
# #                 id=str(uuid.uuid4()),
# #                 config=config,
# #                 execution_time_seconds=(datetime.utcnow() - execution_start).total_seconds(),
# #                 initial_capital=config.initial_capital,
# #                 final_capital=config.initial_capital,
# #                 total_pnl=0,
# #                 total_pnl_percent=0,
# #                 annual_return_percent=0,
# #                 sharpe_ratio=0,
# #                 sortino_ratio=0,
# #                 calmar_ratio=0,
# #                 total_trades=0,
# #                 winning_trades=0,
# #                 losing_trades=0,
# #                 win_rate=0,
# #                 profit_factor=0,
# #                 expectancy=0,
# #                 max_drawdown_percent=0,
# #                 max_drawdown_duration_days=0,
# #                 volatility_annual=0,
# #                 var_95=0,
# #                 cvar_95=0,
# #                 trades=trades,
# #                 equity_curve=equity_curve,
# #                 drawdown_curve=self._calculate_drawdown_curve(equity_curve),
# #                 monthly_returns={},
# #                 yearly_returns={},
# #                 avg_winning_trade=0,
# #                 avg_losing_trade=0,
# #                 largest_winning_trade=0,
# #                 largest_losing_trade=0,
# #                 avg_trade_duration_hours=0,
# #                 symbols_performance=self._calculate_symbols_performance(trades),
# #                 system_quality_number=0,
# #                 kelly_criterion=0
# #             )
        
# #         # حساب المقاييس الأساسية
# #         winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
# #         losing_trades = [t for t in trades if t.pnl and t.pnl <= 0]
        
# #         win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        
# #         total_pnl = sum(t.pnl or 0 for t in trades)
# #         total_pnl_percent = (total_pnl / config.initial_capital) * 100
        
# #         final_capital = config.initial_capital + total_pnl
        
# #         # حساب العائد السنوي
# #         days_duration = (config.end_date - config.start_date).days
# #         annual_return_percent = 0
# #         if days_duration > 0 and config.initial_capital > 0:
# #             annual_return_percent = ((final_capital / config.initial_capital) ** (365 / days_duration) - 1) * 100
        
# #         # حساب منحنى الانخفاض
# #         drawdown_curve = self._calculate_drawdown_curve(equity_curve)
# #         max_drawdown_percent = max(drawdown_curve) if drawdown_curve else 0
        
# #         # حساب العوائد الشهرية والسنوية
# #         monthly_returns, yearly_returns = self._calculate_periodic_returns(equity_curve, config)
        
# #         # حساب المقاييس الأخرى
# #         sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
# #         sortino_ratio = self._calculate_sortino_ratio(equity_curve)
# #         calmar_ratio = self._calculate_calmar_ratio(annual_return_percent, max_drawdown_percent)
# #         profit_factor = self._calculate_profit_factor(winning_trades, losing_trades)
# #         expectancy = self._calculate_expectancy(trades)
        
# #         # حساب متوسط مدة الصفقة
# #         avg_trade_duration = self._calculate_avg_trade_duration(trades)
# #         recovery_factor = (
# #             total_pnl / max_drawdown_percent
# #             if max_drawdown_percent > 0 else 0
# #         )

# #         # إنشاء نتيجة الباك-تيست
# #         result = BacktestResult(
# #             id=str(uuid.uuid4()),
# #             config=config,
# #             execution_time_seconds=(datetime.utcnow() - execution_start).total_seconds(),
# #             initial_capital=config.initial_capital,
# #             final_capital=final_capital,
# #             total_pnl=total_pnl,
# #             total_pnl_percent=total_pnl_percent,
# #             annual_return_percent=annual_return_percent,
# #             sharpe_ratio=sharpe_ratio,
# #             sortino_ratio=sortino_ratio,
# #             calmar_ratio=calmar_ratio,
# #             total_trades=len(trades),
# #             winning_trades=len(winning_trades),
# #             losing_trades=len(losing_trades),
# #             win_rate=win_rate,
# #             profit_factor=profit_factor,
# #             expectancy=expectancy,
# #             max_drawdown_percent=max_drawdown_percent,
# #             max_drawdown_duration_days=self._calculate_max_drawdown_duration(drawdown_curve),
# #             volatility_annual=self._calculate_volatility(equity_curve),
# #             var_95=self._calculate_var(equity_curve, 95),
# #             cvar_95=self._calculate_cvar(equity_curve, 95),
# #             trades=trades,
# #             equity_curve=equity_curve,
# #             drawdown_curve=drawdown_curve,
# #             monthly_returns=monthly_returns,
# #             yearly_returns=yearly_returns,
# #             avg_winning_trade=np.mean([t.pnl for t in winning_trades]) if winning_trades else 0,
# #             avg_losing_trade=np.mean([t.pnl for t in losing_trades]) if losing_trades else 0,
# #             largest_winning_trade=max([t.pnl for t in winning_trades]) if winning_trades else 0,
# #             largest_losing_trade=min([t.pnl for t in losing_trades]) if losing_trades else 0,
# #             avg_trade_duration_hours=avg_trade_duration,
# #             symbols_performance=self._calculate_symbols_performance(trades),
# #             system_quality_number=self._calculate_system_quality_number(trades),
# #             kelly_criterion=self._calculate_kelly_criterion(trades)
# #         )
        
# #         return result
    
# #     def _calculate_drawdown_curve(self, equity_curve: List[float]) -> List[float]:
# #         """حساب منحنى الانخفاض"""
# #         if not equity_curve:
# #             return []
        
# #         peak = equity_curve[0]
# #         drawdowns = []
        
# #         for equity in equity_curve:
# #             if equity > peak:
# #                 peak = equity
# #             drawdown = (peak - equity) / peak * 100 if peak > 0 else 0
# #             drawdowns.append(drawdown)
        
# #         return drawdowns
    
# #     def _calculate_symbols_performance(self, trades: List[Trade]) -> Dict[str, Dict[str, float]]:
# #         """حساب أداء كل رمز"""
# #         symbols = {}
        
# #         for trade in trades:
# #             if trade.symbol not in symbols:
# #                 symbols[trade.symbol] = {
# #                     'total_trades': 0,
# #                     'winning_trades': 0,
# #                     'total_pnl': 0,
# #                     'avg_pnl': 0
# #                 }
            
# #             symbols[trade.symbol]['total_trades'] += 1
# #             if trade.pnl and trade.pnl > 0:
# #                 symbols[trade.symbol]['winning_trades'] += 1
# #             if trade.pnl:
# #                 symbols[trade.symbol]['total_pnl'] += trade.pnl
        
# #         for symbol, data in symbols.items():
# #             if data['total_trades'] > 0:
# #                 data['win_rate'] = (data['winning_trades'] / data['total_trades']) * 100
# #                 data['avg_pnl'] = data['total_pnl'] / data['total_trades']
        
# #         return symbols
    
# #     def _calculate_periodic_returns(self, equity_curve: List[float], config: BacktestConfig) -> Tuple[Dict[str, float], Dict[str, float]]:
# #         """حساب العوائد الشهرية والسنوية"""
# #         # هذا مثال مبسط
# #         # في التطبيق الحقيقي، نحتاج إلى تتبع التواريخ
        
# #         monthly_returns = {}
# #         yearly_returns = {}
        
# #         if len(equity_curve) > 30:
# #             # عوائد شهرية افتراضية
# #             for i in range(min(12, len(equity_curve) // 30)):
# #                 start_idx = i * 30
# #                 end_idx = min((i + 1) * 30, len(equity_curve) - 1)
                
# #                 if end_idx > start_idx:
# #                     monthly_return = ((equity_curve[end_idx] - equity_curve[start_idx]) / 
# #                                     equity_curve[start_idx]) * 100
# #                     monthly_returns[f"Month_{i+1}"] = monthly_return
        
# #         # العائد السنوي الإجمالي
# #         if len(equity_curve) > 1:
# #             yearly_return = ((equity_curve[-1] - equity_curve[0]) / 
# #                            equity_curve[0]) * 100
# #             yearly_returns["Total_Period"] = yearly_return
        
# #         return monthly_returns, yearly_returns
    
# #     def _calculate_sharpe_ratio(self, equity_curve: List[float]) -> float:
# #         """حساب نسبة شارب"""
# #         if len(equity_curve) < 2:
# #             return 0.0
        
# #         returns = np.diff(equity_curve) / equity_curve[:-1]
# #         if returns.std() == 0:
# #             return 0.0
        
# #         # افتراض معدل خالي من المخاطر 2%
# #         risk_free_rate = 0.02 / 252  # معدل يومي
        
# #         sharpe = (returns.mean() - risk_free_rate) / returns.std() * np.sqrt(252)
# #         return float(sharpe)
    
# #     def _calculate_sortino_ratio(self, equity_curve: List[float]) -> float:
# #         """حساب نسبة سورتينو"""
# #         if len(equity_curve) < 2:
# #             return 0.0
        
# #         returns = np.diff(equity_curve) / equity_curve[:-1]
# #         negative_returns = returns[returns < 0]
        
# #         if len(negative_returns) == 0 or negative_returns.std() == 0:
# #             return 0.0
        
# #         # افتراض معدل خالي من المخاطر 2%
# #         risk_free_rate = 0.02 / 252
        
# #         sortino = (returns.mean() - risk_free_rate) / negative_returns.std() * np.sqrt(252)
# #         return float(sortino)
    
# #     def _calculate_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
# #         """حساب نسبة كالمار"""
# #         if max_drawdown == 0:
# #             return 0.0
# #         return annual_return / abs(max_drawdown)
    
# #     def _calculate_profit_factor(self, winning_trades: List[Trade], losing_trades: List[Trade]) -> float:
# #         """حساب عامل الربح"""
# #         gross_profit = sum(t.pnl for t in winning_trades if t.pnl)
# #         gross_loss = abs(sum(t.pnl for t in losing_trades if t.pnl))
        
# #         if gross_loss == 0:
# #             return float('inf') if gross_profit > 0 else 0.0
        
# #         return gross_profit / gross_loss
    
# #     def _calculate_expectancy(self, trades: List[Trade]) -> float:
# #         """حساب التوقع"""
# #         if not trades:
# #             return 0.0
        
# #         winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
# #         losing_trades = [t for t in trades if t.pnl and t.pnl <= 0]
        
# #         win_rate = len(winning_trades) / len(trades)
# #         avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
# #         avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0
        
# #         expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
# #         return float(expectancy)
    
# #     def _calculate_max_drawdown_duration(self, drawdown_curve: List[float]) -> int:
# #         """حساب مدة أقصى انخفاض"""
# #         if not drawdown_curve:
# #             return 0
        
# #         max_duration = 0
# #         current_duration = 0
        
# #         for dd in drawdown_curve:
# #             if dd > 0:
# #                 current_duration += 1
# #                 max_duration = max(max_duration, current_duration)
# #             else:
# #                 current_duration = 0
        
# #         return max_duration
    
# #     def _calculate_volatility(self, equity_curve: List[float]) -> float:
# #         """حساب التقلب السنوي"""
# #         if len(equity_curve) < 2:
# #             return 0.0
        
# #         returns = np.diff(equity_curve) / equity_curve[:-1]
# #         volatility = returns.std() * np.sqrt(252) * 100  # كنسبة مئوية سنوية
# #         return float(volatility)
    
# #     def _calculate_var(self, equity_curve: List[float], confidence: float) -> float:
# #         """حساب القيمة المعرضة للخطر"""
# #         if len(equity_curve) < 2:
# #             return 0.0
        
# #         returns = np.diff(equity_curve) / equity_curve[:-1]
# #         var = np.percentile(returns, 100 - confidence) * 100  # كنسبة مئوية
# #         return float(var)
    
# #     def _calculate_cvar(self, equity_curve: List[float], confidence: float) -> float:
# #         """حساب القيمة المعرضة للخطر الشرطية"""
# #         if len(equity_curve) < 2:
# #             return 0.0
        
# #         returns = np.diff(equity_curve) / equity_curve[:-1]
# #         var = np.percentile(returns, 100 - confidence)
# #         cvar = returns[returns <= var].mean() * 100  # كنسبة مئوية
# #         return float(cvar)
    
# #     def _calculate_avg_trade_duration(self, trades: List[Trade]) -> float:
# #         """حساب متوسط مدة الصفقة بالساعات"""
# #         if not trades:
# #             return 0.0
        
# #         durations = []
# #         for trade in trades:
# #             if trade.entry_time and trade.exit_time:
# #                 duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600
# #                 durations.append(duration)
        
# #         return float(np.mean(durations)) if durations else 0.0
    
# #     def _calculate_system_quality_number(self, trades: List[Trade]) -> float:
# #         """حساب رقم جودة النظام"""
# #         if not trades:
# #             return 0.0
        
# #         pnls = [t.pnl for t in trades if t.pnl is not None]
# #         if not pnls:
# #             return 0.0
        
# #         mean_pnl = np.mean(pnls)
# #         std_pnl = np.std(pnls)
        
# #         if std_pnl == 0:
# #             return 0.0
        
# #         sqn = (mean_pnl / std_pnl) * np.sqrt(len(trades))
# #         return float(sqn)
    
# #     def _calculate_kelly_criterion(self, trades: List[Trade]) -> float:
# #         """حساب معيار كيلي"""
# #         if not trades:
# #             return 0.0
        
# #         winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
# #         losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
        
# #         win_rate = len(winning_trades) / len(trades)
# #         avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
# #         avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0
        
# #         if avg_loss == 0:
# #             return 0.0
        
# #         kelly = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
# #         return float(kelly)
    
# #     async def run_walk_forward_analysis(
# #         self,
# #         config: BacktestConfig,
# #         periods: int = 5
# #     ) -> List[BacktestResult]:
# #         """تشغيل تحليل مشي للأمام"""
# #         results = []
        
# #         # تقسيم الفترة الزمنية إلى فترات فرعية
# #         total_days = (config.end_date - config.start_date).days
# #         period_days = total_days // periods
        
# #         for i in range(periods):
# #             period_start = config.start_date + timedelta(days=i * period_days)
# #             period_end = period_start + timedelta(days=period_days)
            
# #             if i == periods - 1:
# #                 period_end = config.end_date
            
# #             print(f"\n🔍 Walk-forward period {i+1}: {period_start.date()} to {period_end.date()}")
            
# #             # تحديث التكوين للفترة الحالية
# #             period_config = config.copy()
# #             period_config.start_date = period_start
# #             period_config.end_date = period_end
            
# #             # تشغيل الباك-تيست للفترة الحالية
# #             try:
# #                 result = await self.run_backtest(period_config)
# #                 results.append(result)
# #                 print(f"✅ Period {i+1} completed: P&L {result.total_pnl_percent:.2f}%, Trades: {result.total_trades}")
# #             except Exception as e:
# #                 print(f"❌ Error in period {i+1}: {str(e)}")
        
# #         return results
    
# #     async def run_monte_carlo_simulation(
# #         self,
# #         config: BacktestConfig,
# #         simulations: int = 1000
# #     ) -> Dict[str, Any]:
# #         """تشغيل محاكاة مونت كارلو"""
# #         print(f"\n🎲 Running Monte Carlo simulation ({simulations} iterations)")
        
# #         # تشغيل باك-تيست أساسي للحصول على الصفقات
# #         print("Running base backtest for simulation data...")
# #         base_result = await self.run_backtest(config)
# #         base_trades = base_result.trades
        
# #         if not base_trades or len(base_trades) < 10:
# #             print("⚠️ Not enough trades for Monte Carlo simulation")
# #             return {
# #                 'simulations': 0,
# #                 'mean_return': 0.0,
# #                 'std_return': 0.0,
# #                 'min_return': 0.0,
# #                 'max_return': 0.0,
# #                 'percentile_5': 0.0,
# #                 'percentile_25': 0.0,
# #                 'percentile_50': 0.0,
# #                 'percentile_75': 0.0,
# #                 'percentile_95': 0.0,
# #                 'probability_profit': 0.0,
# #                 'probability_loss': 0.0
# #             }
        
# #         # محاكاة إعادة ترتيب الصفقات
# #         simulated_returns = []
# #         base_pnls = [t.pnl for t in base_trades if t.pnl is not None]
        
# #         print(f"Using {len(base_pnls)} trades for simulation")
        
# #         for i in range(simulations):
# #             # إعادة ترتيب عشوائي للصفقات
# #             shuffled_pnls = np.random.permutation(base_pnls)
            
# #             # محاكاة العوائد
# #             total_pnl = np.sum(shuffled_pnls)
# #             total_return = (total_pnl / config.initial_capital) * 100
# #             simulated_returns.append(total_return)
            
# #             if (i + 1) % 100 == 0:
# #                 print(f"  Completed {i+1}/{simulations} iterations")
        
# #         returns_array = np.array(simulated_returns)
        
# #         stats = {
# #             'simulations': simulations,
# #             'mean_return': float(np.mean(returns_array)),
# #             'std_return': float(np.std(returns_array)),
# #             'min_return': float(np.min(returns_array)),
# #             'max_return': float(np.max(returns_array)),
# #             'percentile_5': float(np.percentile(returns_array, 5)),
# #             'percentile_25': float(np.percentile(returns_array, 25)),
# #             'percentile_50': float(np.percentile(returns_array, 50)),
# #             'percentile_75': float(np.percentile(returns_array, 75)),
# #             'percentile_95': float(np.percentile(returns_array, 95)),
# #             'probability_profit': float(np.sum(returns_array > 0) / len(returns_array)),
# #             'probability_loss': float(np.sum(returns_array < 0) / len(returns_array))
# #         }
        
# #         print(f"✅ Monte Carlo simulation completed")
# #         print(f"   Mean return: {stats['mean_return']:.2f}%")
# #         print(f"   Probability of profit: {stats['probability_profit']*100:.1f}%")
        
# #         return stats


# import asyncio
# import numpy as np
# import pandas as pd
# from typing import Dict, List, Any, Optional, Tuple
# from datetime import datetime, timedelta, timezone
# import uuid
# import warnings
# import traceback

# # ✅ استيراد محرك الاستراتيجية الجديد (الذي اسمه strategy_engine1)
# # تأكد أن المسار صحيح داخل مشروعك
# from app.services.strategy.strategy_engine1 import StrategyEngine, Decision, DecisionAction

# # استيرادات الـ Schemas والخدمات المساعدة
# from app.backtest.schemas import BacktestConfig, BacktestResult, PnlDistribution, Trade
# from app.services.data_service import DataService
# from app.services.strategy.schemas import StrategyConfig as StrategyConfigSchema
# from app.backtest.metrics import PerformanceMetrics

# warnings.filterwarnings('ignore')

# class BacktestEngine:
#     """محرك الباك-تيست التاريخي (يعمل الآن كمحرك تنفيذي للقرارات)"""
    
#     def __init__(self, data_service: DataService):
#         self.data_service = data_service
#         self.metrics_calculator = PerformanceMetrics()
        
#     async def run_backtest(self, config: BacktestConfig) -> BacktestResult:  
#         start_time = datetime.utcnow()
#         print(f"🚀 Starting backtest (Architecture: Strategy-Driven): {config.name}")
        
#         try:
#             # 1. جلب البيانات (Data Fetching)
#             all_data = {}
#             for symbol in config.symbols:
#                 try:
#                     days_required = (config.end_date - config.start_date).days + 30
#                     data = await self.data_service.get_historical(
#                         symbol=symbol, 
#                         timeframe=config.timeframe,
#                         market=config.market, 
#                         days=days_required, 
#                         use_cache=True
#                     )
                    
#                     if not data.empty:
#                         data.index = pd.to_datetime(data.index, utc=True)
#                         start = config.start_date.astimezone(timezone.utc)
#                         end = config.end_date.astimezone(timezone.utc)
#                         mask = (data.index >= start) & (data.index <= end)
#                         filtered_data = data.loc[mask]
#                         if not filtered_data.empty:
#                             all_data[symbol] = filtered_data
#                 except Exception as e:
#                     print(f"❌ Error fetching data for {symbol}: {str(e)}")
            
#             if not all_data:
#                 raise ValueError("No data available for any symbol")
            
#             # 2. محاكاة التداول (Simulation)
#             trades = []
#             equity_curve = [config.initial_capital]
#             current_capital = config.initial_capital
            
#             for symbol, data in all_data.items():
#                 # ✅ استدعاء الدالة المعدلة بالكامل
#                 symbol_trades, symbol_equity = await self._simulate_with_strategy(
#                     symbol, data, config, current_capital
#                 )
#                 trades.extend(symbol_trades)
                
#                 # تحديث منحنى رأس المال
#                 if len(symbol_equity) > 0:
#                     # نبدأ من الفهرس 1 لتجنب تكرار القيمة الأولية
#                     equity_curve.extend(symbol_equity[1:]) 
#                     current_capital = symbol_equity[-1]

#             # 3. حساب المقاييس والنتيجة النهائية (Metrics & Result)
#             result = await self._create_backtest_result(
#                 config=config, 
#                 trades=trades, 
#                 equity_curve=equity_curve, 
#                 execution_start=start_time
#             )
            
#             return result

#         except Exception as e:
#             print(f"❌ Backtest failed: {str(e)}")
#             traceback.print_exc()
#             raise

#     async def _simulate_with_strategy(
#         self,
#         symbol: str,
#         data: pd.DataFrame,
#         config: BacktestConfig,
#         initial_capital: float
#     ) -> Tuple[List[Trade], List[float]]:
#         """
#         محاكاة الصفقات باستخدام محرك استراتيجية منفصل (Black Box)
#         """
#         trades = []
#         equity_curve = [initial_capital]
#         current_capital = initial_capital
        
#         if len(data) < 50: # الحد الأدنى للمؤشرات
#             return trades, equity_curve

#         try:
#             # 1. إنشاء محرك الاستراتيجية
#             strategy_config_obj = StrategyConfigSchema(**config.strategy_config)
#             strategy_engine = StrategyEngine(strategy_config_obj)
#         except Exception as e:
#             print(f"❌ خطأ في تكوين الاستراتيجية: {e}")
#             return trades, equity_curve

#         # حالة المحفظة (Portfolio State)
#         current_state = 'NEUTRAL' # LONG, SHORT, NEUTRAL
#         entry_price = 0.0
#         entry_time = None
#         position_size = 0.0
#         trade_id = None
#         sl_price = 0.0
#         tp_price = 0.0

#         print(f"   📊 بدء محاكاة {symbol} باستخدام Black Box Strategy...")

#         # 2. حلقة المحاكاة (Bar-by-Bar Simulation)
#         for i in range(len(data)):
#             current_bar = data.iloc[i]
#             current_time = data.index[i]
            
#             # أ) التحقق من إدارة المخاطر (SL/TP) قبل طلب القرار الجديد
#             if current_state != 'NEUTRAL':
#                 exit_price = None
#                 exit_reason = None
                
#                 if current_state == 'LONG':
#                     if current_bar['low'] <= sl_price:
#                         exit_price = sl_price
#                         exit_reason = "Stop Loss Hit"
#                     elif current_bar['high'] >= tp_price:
#                         exit_price = tp_price
#                         exit_reason = "Take Profit Hit"
#                 elif current_state == 'SHORT':
#                     if current_bar['high'] >= sl_price:
#                         exit_price = sl_price
#                         exit_reason = "Stop Loss Hit"
#                     elif current_bar['low'] <= tp_price:
#                         exit_price = tp_price
#                         exit_reason = "Take Profit Hit"
                
#                 # إذا تم تفعيل وقف الخسارة أو الربح
#                 if exit_price is not None:
#                     # حساب الربح/الخسارة
#                     if current_state == 'LONG':
#                         pnl = (exit_price - entry_price) * position_size
#                     else: # SHORT
#                         pnl = (entry_price - exit_price) * position_size
                    
#                     # إغلاق الصفقة
#                     self._close_trade_logic(trades, trade_id, exit_price, current_time, exit_reason)
#                     current_state = 'NEUTRAL'
#                     current_capital += pnl
#                     equity_curve.append(current_capital)
#                     trade_id = None
#                     continue # الانتقال للشريط التالي

#             # ب) طلب قرار من الاستراتيجية (Black Box Call)
#             # نمرر البيانات حتى اللحظة الحالية
#             slice_data = data.iloc[:i+1]
            
#             try:
#                 decision = await strategy_engine.run(slice_data)
#             except Exception as inner_e:
#                 print(f"⚠️ Strategy Error at {current_time}: {inner_e}")
#                 continue

#             # ج) معالجة القرار (Decision Logic)
#             target_state = 'NEUTRAL'
            
#             if decision.action == DecisionAction.BUY:
#                 target_state = 'LONG'
#             elif decision.action == DecisionAction.SELL:
#                 target_state = 'SHORT'
#             else:
#                 target_state = 'NEUTRAL'

#             # د) تنفيذ الانتقالات (State Transition)
            
#             # الحالة 1: إغلاق مركز (أو عكس الموقف)
#             if target_state != 'NEUTRAL' and current_state != 'NEUTRAL':
#                 # نحتاج لإغلاق المركز الحالي أولاً
#                 # إغلاق عند سعر السوق
#                 self._close_trade_logic(trades, trade_id, current_bar['close'], current_time, f"Signal Reversal: {decision.action.value}")
                
#                 current_capital = self._update_capital(trades, initial_capital)
#                 equity_curve.append(current_capital)
#                 current_state = 'NEUTRAL'
#                 trade_id = None

#             # الحالة 2: فتح مركز جديد
#             if target_state != 'NEUTRAL' and current_state == 'NEUTRAL':
#                 entry_price = current_bar['close']
#                 entry_time = current_time
                
#                 # حساب حجم الصفقة
#                 risk_amount = current_capital * config.position_size_percent
#                 position_size = risk_amount / entry_price 
                
#                 # تحديد مستويات SL/TP
#                 if config.stop_loss_percent:
#                     sl_offset = entry_price * (config.stop_loss_percent / 100)
#                     if target_state == 'LONG':
#                         sl_price = entry_price - sl_offset
#                     else:
#                         sl_price = entry_price + sl_offset
                
#                 if config.take_profit_percent:
#                     tp_offset = entry_price * (config.take_profit_percent / 100)
#                     if target_state == 'LONG':
#                         tp_price = entry_price + tp_offset
#                     else:
#                         tp_price = entry_price - tp_offset

#                 current_state = target_state
#                 trade_id = str(uuid.uuid4())
                
#                 # إنشاء سجل الصفقة
#                 commission = entry_price * position_size * config.commission_rate
#                 trade = Trade(
#                     id=trade_id,
#                     symbol=symbol,
#                     entry_time=entry_time,
#                     exit_time=None,
#                     entry_price=entry_price,
#                     exit_price=None,
#                     position_type='long' if target_state == 'LONG' else 'short',
#                     position_size=position_size,
#                     pnl=None,
#                     pnl_percentage=None,
#                     commission=commission,
#                     slippage=0,
#                     stop_loss=sl_price if config.stop_loss_percent else None,
#                     take_profit=tp_price if config.take_profit_percent else None,
#                     exit_reason=None,
#                     metadata={
#                         'strategy': config.strategy_config.get('name', 'Unknown'),
#                         'decision_reason': decision.reason,
#                         'confidence': decision.confidence
#                     }
#                 )
#                 trades.append(trade)

#         # إغلاق أي مركز مفتوح في نهاية البيانات
#         if current_state != 'NEUTRAL' and trade_id:
#             self._close_trade_logic(trades, trade_id, data['close'].iloc[-1], data.index[-1], "End of Data")
#             current_capital = self._update_capital(trades, initial_capital)
#             equity_curve.append(current_capital)

#         return trades, equity_curve







#     def _convert_to_serializable(self, obj):
#         """تحويل الكائنات إلى صيغة قابلة للتسلسل (لـ JSON)"""
#         import numpy as np
#         import pandas as pd
#         from datetime import datetime
        
#         if isinstance(obj, (np.float32, np.float64)):
#             return float(obj)
#         elif isinstance(obj, (np.int32, np.int64)):
#             return int(obj)
#         elif isinstance(obj, np.ndarray):
#             return [self._convert_to_serializable(x) for x in obj.tolist()]
#         elif isinstance(obj, pd.Timestamp):
#             return obj.isoformat()
#         elif isinstance(obj, datetime):
#             return obj.isoformat()
#         elif isinstance(obj, dict):
#             return {k: self._convert_to_serializable(v) for k, v in obj.items()}
#         elif isinstance(obj, list):
#             return [self._convert_to_serializable(x) for x in obj]
#         elif pd.isna(obj):  # للتعامل مع NaN
#             return None
#         else:
#             return obj



#     def _close_trade_logic(self, trades: List[Trade], trade_id: str, exit_price: float, exit_time: datetime, reason: str):
#         """دالة مساعدة لتحديث بيانات الصفقة عند الإغلاق"""
#         for trade in trades:
#             if trade.id == trade_id and trade.exit_time is None:
#                 trade.exit_time = exit_time
#                 trade.exit_price = exit_price
#                 trade.exit_reason = reason
                
#                 # حساب PNL
#                 if trade.position_type == 'long':
#                     trade.pnl = (exit_price - trade.entry_price) * trade.position_size
#                 else:
#                     trade.pnl = (trade.entry_price - exit_price) * trade.position_size
                
#                 # حساب العمولة النهائية
#                 commission_exit = exit_price * trade.position_size * 0.001 # (استخدم 0.001 مؤقتاً أو خذها من config)
#                 trade.commission += commission_exit
                
#                 # خصم العمولة من الربح
#                 trade.pnl -= trade.commission
                
#                 if trade.entry_price > 0:
#                     trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.position_size)) * 100
#                 break

#     def _update_capital(self, trades: List[Trade], initial_capital: float) -> float:
#         """دالة مساعدة لحساب رأس المال الحالي بناءً على جميع الصفقات المغلقة"""
#         current_capital = initial_capital
#         for trade in trades:
#             # نجمع الربح/الخسارة من الصفقات المغلقة فقط
#             if trade.exit_time is not None and trade.pnl is not None:
#                 current_capital += trade.pnl
#         return current_capital











#     async def _create_backtest_result(
#         self,
#         config: BacktestConfig,
#         trades: List[Trade],
#         equity_curve: List[float],
#         execution_start: datetime
#     ) -> BacktestResult:
#         """إنشاء كائن النتيجة النهائية وحساب المقاييس"""
#         import uuid
#         from datetime import datetime
#         from typing import Dict
        
#         # 1. استخدام حاسبة المقاييس
#         metrics = self.metrics_calculator.calculate(trades, config.initial_capital)
        
#         execution_time = (datetime.utcnow() - execution_start).total_seconds()
        
#         # 2. حساب القيم الأساسية
#         final_capital = equity_curve[-1] if equity_curve else config.initial_capital
#         total_pnl = final_capital - config.initial_capital
#         total_pnl_percent = (total_pnl / config.initial_capital * 100) if config.initial_capital > 0 else 0
        
#         # 3. حساب منحنى الانخفاض
#         drawdown_curve = self.metrics_calculator._calculate_drawdown_curve(equity_curve)
        
#         # 4. حساب الحقول الإضافية المطلوبة
#         basic_metrics = self.metrics_calculator._calculate_basic_metrics(trades)
#         risk_metrics = self.metrics_calculator._calculate_risk_metrics(equity_curve, drawdown_curve)
#         timing_metrics = self.metrics_calculator._calculate_timing_metrics(trades)
#         advanced_metrics = self.metrics_calculator._calculate_advanced_metrics(trades, equity_curve)
        
#         # 5. حساب العوائد الشهرية والسنوية (مبسطة)
#         monthly_returns = self._calculate_monthly_returns(equity_curve, config)
#         yearly_returns = self._calculate_yearly_returns(equity_curve, config)
        
#         # 6. حساب أداء الرموز
#         symbols_performance = self._calculate_symbols_performance(trades, config)
        
#         # 7. إنشاء BacktestResult الكامل
#         return BacktestResult(
#             # ★ الحقول الأساسية
#             id=str(uuid.uuid4()),
#             config=config,
#             execution_time_seconds=execution_time,
#             timestamp=datetime.utcnow(),
            
#             # ★ الأداء العام
#             initial_capital=config.initial_capital,
#             final_capital=final_capital,
#             total_pnl=total_pnl,
#             total_pnl_percent=total_pnl_percent,  # ★ الاسم الصحيح من schemas.py
#             annual_return_percent=metrics.get('annual_return_percent', 0.0),
            
#             # ★ العائد المعدل بالمخاطرة
#             sharpe_ratio=metrics.get('sharpe_ratio', 0.0),
#             sortino_ratio=metrics.get('sortino_ratio', 0.0),
#             calmar_ratio=metrics.get('calmar_ratio', 0.0),
            
#             # ★ المقاييس الأساسية
#             total_trades=len(trades),
#             winning_trades=basic_metrics.get('winning_trades', 0),
#             losing_trades=basic_metrics.get('losing_trades', 0),
#             win_rate=basic_metrics.get('win_rate', 0.0),
#             profit_factor=basic_metrics.get('profit_factor', 0.0),
#             expectancy=basic_metrics.get('expectancy', 0.0),
            
#             # ★ المخاطرة
#             max_drawdown_percent=risk_metrics.get('max_drawdown_percent', 0.0),
#             max_drawdown_duration_days=risk_metrics.get('max_drawdown_duration_days', 0),
#             volatility_annual=risk_metrics.get('volatility_annual', 0.0),
#             var_95=risk_metrics.get('var_95', 0.0),
#             cvar_95=risk_metrics.get('cvar_95', 0.0),
            
#             # ★ التفاصيل
#             trades=trades,  # ★ الصفقات نفسها (مهم!)
#             equity_curve=equity_curve,
#             drawdown_curve=drawdown_curve,
#             monthly_returns=monthly_returns,
#             yearly_returns=yearly_returns,
            
#             # ★ تحليل الصفقات
#             avg_winning_trade=basic_metrics.get('avg_winning_trade', 0.0),
#             avg_losing_trade=basic_metrics.get('avg_losing_trade', 0.0),
#             largest_winning_trade=basic_metrics.get('largest_winning_trade', 0.0),
#             largest_losing_trade=basic_metrics.get('largest_losing_trade', 0.0),
#             avg_trade_duration_hours=timing_metrics.get('avg_trade_duration_hours', 0.0),
            
#             # ★ ربحية الرموز
#             symbols_performance=symbols_performance,
            
#             # ★ الكفاءة
#             system_quality_number=advanced_metrics.get('system_quality_number', 0.0),
#             kelly_criterion=advanced_metrics.get('kelly_criterion', 0.0),
            
#             # ★ الحقول الاختيارية
#             recovery_factor=advanced_metrics.get('recovery_factor'),
#             ulcer_index=advanced_metrics.get('ulcer_index'),
#             raw_data=None
#         )



#     # async def _create_backtest_result(
#     #     self,
#     #     config: BacktestConfig,
#     #     trades: List[Trade],
#     #     equity_curve: List[float],
#     #     execution_start: datetime
#     # ) -> BacktestResult:
#     #     """إنشاء كائن النتيجة النهائية وحساب المقاييس"""
#     #     # 1. استخدام حاسبة المقاييس
#     #     metrics = self.metrics_calculator.calculate(trades, config.initial_capital)
        
#     #     execution_time = (datetime.utcnow() - execution_start).total_seconds()
        
#     #     # 2. ملء الـ BacktestResult
#     #     return BacktestResult(
#     #         strategy_name=config.name,
#     #         total_trades=len(trades),
#     #         winning_trades=metrics['winning_trades'],
#     #         losing_trades=metrics['losing_trades'],
#     #         win_rate=metrics['win_rate'],
#     #         total_pnl=metrics['total_pnl'],
#     #         total_pnl_percentage=metrics['total_pnl_percentage'],
#     #         max_drawdown_percent=metrics['max_drawdown_percent'],
#     #         sharpe_ratio=metrics['sharpe_ratio'],
#     #         equity_curve=equity_curve,
#     #         execution_time_seconds=execution_time,
#     #         trades_summary=[] # يمكن ملؤها بالتفاصيل إذا أردت
#     #     )








#     def _calculate_monthly_returns(self, equity_curve: List[float], config: BacktestConfig) -> Dict[str, float]:
#         """
#         حساب العوائد الشهرية الحقيقية بناءً على منحنى الأسهم والبيانات التاريخية
        
#         Args:
#             equity_curve: منحنى رأس المال عبر الوقت
#             config: إعدادات الباك-تست
        
#         Returns:
#             Dict[str, float]: قاموس بالعوائد الشهرية بنسبة مئوية {yyyy-mm: return%}
#         """
#         if len(equity_curve) < 10:  # الحد الأدنى للمعنى الإحصائي
#             return {}
        
#         try:

            
#             # 1. إنشاء تواريخ واقعية بناءً على timeframe
#             timeframes = {
#                 '1m': 'T', '5m': '5T', '15m': '15T', '30m': '30T',
#                 '1h': 'H', '2h': '2H', '4h': '4H', '6h': '6H', '8h': '8H', '12h': '12H',
#                 '1d': 'D', '3d': '3D', '1w': 'W', '1M': 'M'
#             }
            
#             freq = timeframes.get(config.timeframe, 'H')  # افتراضي ساعة
            
#             # حساب عدد البارات بناءً على الفترة الزمنية
#             start_date = config.start_date
#             end_date = config.end_date
            
#             # إنشاء التواريخ لكل نقطة في equity_curve
#             if len(equity_curve) == 1:
#                 dates = [start_date]
#             else:
#                 dates = pd.date_range(
#                     start=start_date, 
#                     end=end_date, 
#                     periods=len(equity_curve),
#                     tz=start_date.tzinfo
#                 )
            
#             # 2. إنشاء DataFrame للتحليل
#             df = pd.DataFrame({
#                 'date': dates,
#                 'equity': equity_curve
#             })
#             df.set_index('date', inplace=True)
            
#             # 3. إعادة عينة إلى نهاية كل شهر
#             monthly_equity = df['equity'].resample('M').last()
            
#             if len(monthly_equity) < 3:  # نحتاج شهرين على الأقل لحساب العائد
#                 return {}
            
#             # 4. حساب العوائد الشهرية
#             monthly_returns = {}
#             for i in range(1, len(monthly_equity)):
#                 current_date = monthly_equity.index[i]
#                 prev_date = monthly_equity.index[i-1]
                
#                 current_equity = monthly_equity.iloc[i]
#                 prev_equity = monthly_equity.iloc[i-1]
                
#                 if prev_equity > 0:
#                     monthly_return = ((current_equity - prev_equity) / prev_equity) * 100
#                     key = current_date.strftime("%Y-%m")
#                     monthly_returns[key] = float(monthly_return)
            
#             # 5. إضافة إحصائيات إضافية
#             # if monthly_returns:
#             #     returns_list = list(monthly_returns.values())
#             #     monthly_returns['_stats'] = {
#             #         'avg_monthly_return': float(np.mean(returns_list)),
#             #         'std_monthly_return': float(np.std(returns_list)),
#             #         'best_month': max(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None,
#             #         'worst_month': min(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None,
#             #         'positive_months': sum(1 for r in returns_list if r > 0),
#             #         'negative_months': sum(1 for r in returns_list if r < 0),
#             #         'consistency_rate': (sum(1 for r in returns_list if r > 0) / len(returns_list) * 100) if returns_list else 0
#             #     }
            
#             # return monthly_returns
            
#             if monthly_returns:
#                 returns_list = list(monthly_returns.values())
#                 stats = {
#                     'avg_monthly_return': float(np.mean(returns_list)),
#                     'std_monthly_return': float(np.std(returns_list)),
#                     'best_month': max(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None,
#                     'worst_month': min(monthly_returns.items(), key=lambda x: x[1])[0] if monthly_returns else None,
#                     'positive_months': int(sum(1 for r in returns_list if r > 0)),
#                     'negative_months': int(sum(1 for r in returns_list if r < 0)),
#                     'consistency_rate': float((sum(1 for r in returns_list if r > 0) / len(returns_list) * 100) if returns_list else 0)
#                 }
                
#                 # تحويل كل القيم إلى Python types
#                 monthly_returns_clean = {}
#                 for k, v in monthly_returns.items():
#                     monthly_returns_clean[k] = float(v) if isinstance(v, (np.float32, np.float64, float)) else v
                
#                 monthly_returns_clean['_stats'] = stats
#                 return self._convert_to_serializable(monthly_returns_clean)
            
#             return {}
        

#         except Exception as e:
#             print(f"❌ خطأ في حساب العوائد الشهرية: {e}")
#             traceback.print_exc()
#             return {}

#     def _calculate_yearly_returns(self, equity_curve: List[float], config: BacktestConfig) -> Dict[str, float]:
#         """
#         حساب العوائد السنوية الحقيقية بناءً على منحنى الأسهم
        
#         Args:
#             equity_curve: منحنى رأس المال عبر الوقت
#             config: إعدادات الباك-تست
        
#         Returns:
#             Dict[str, float]: قاموس بالعوائد السنوية بنسبة مئوية {yyyy: return%}
#         """
#         if len(equity_curve) < 50:  # الحد الأدنى للمعنى الإحصائي
#             return {}
        
#         try:

            
#             # 1. إنشاء تواريخ واقعية
#             start_date = config.start_date
#             end_date = config.end_date
            
#             if len(equity_curve) == 1:
#                 dates = [start_date]
#             else:
#                 dates = pd.date_range(
#                     start=start_date, 
#                     end=end_date, 
#                     periods=len(equity_curve),
#                     tz=start_date.tzinfo
#                 )
            
#             # 2. إنشاء DataFrame
#             df = pd.DataFrame({
#                 'date': dates,
#                 'equity': equity_curve
#             })
#             df.set_index('date', inplace=True)
            
#             # 3. استخراج السنوات الموجودة في البيانات
#             df['year'] = df.index.year
#             yearly_data = df.groupby('year')['equity'].agg(['first', 'last'])
            
#             yearly_returns = {}
#             for year, row in yearly_data.iterrows():
#                 if row['first'] > 0:
#                     yearly_return = ((row['last'] - row['first']) / row['first']) * 100
#                     yearly_returns[str(year)] = float(yearly_return)
            
#             # 4. حساب العائد السنوي المعدل (Annualized)
#             if len(equity_curve) >= 2:
#                 total_return = ((equity_curve[-1] - equity_curve[0]) / equity_curve[0]) * 100 if equity_curve[0] > 0 else 0
                
#                 # حساب عدد السنوات الكسرية
#                 days_diff = (end_date - start_date).days
#                 years_diff = days_diff / 365.25
                
#                 if years_diff > 0:
#                     annualized_return = ((1 + total_return/100) ** (1/years_diff) - 1) * 100
#                     yearly_returns['annualized'] = float(annualized_return)
#                     yearly_returns['cagr'] = float(annualized_return)  # معدل النمو السنوي المركب
            
#             # 5. إضافة إحصائيات إضافية
#             if yearly_returns and len(yearly_returns) > 1:
#                 # yearly_returns_only = [v for k, v in yearly_returns.items() if k.isdigit()]
#                 # if yearly_returns_only:
#                 #     yearly_returns['_stats'] = {
#                 #         'avg_yearly_return': float(np.mean(yearly_returns_only)),
#                 #         'std_yearly_return': float(np.std(yearly_returns_only)),
#                 #         'best_year': max((k for k in yearly_returns if k.isdigit()), 
#                 #                     key=lambda x: yearly_returns[x]),
#                 #         'worst_year': min((k for k in yearly_returns if k.isdigit()), 
#                 #                         key=lambda x: yearly_returns[x]),
#                 #         'positive_years': sum(1 for r in yearly_returns_only if r > 0),
#                 #         'max_consecutive_positive': self._max_consecutive_positive(yearly_returns_only),
#                 #         'max_consecutive_negative': self._max_consecutive_negative(yearly_returns_only)
#                 #     }

#                 yearly_returns_only = [v for k, v in yearly_returns.items() if k.isdigit()]
#                 if yearly_returns_only:
#                     stats = {
#                         'avg_yearly_return': float(np.mean(yearly_returns_only)),
#                         'std_yearly_return': float(np.std(yearly_returns_only)),
#                         'best_year': max((k for k in yearly_returns if k.isdigit()), 
#                                     key=lambda x: yearly_returns[x]),
#                         'worst_year': min((k for k in yearly_returns if k.isdigit()), 
#                                         key=lambda x: yearly_returns[x]),
#                         'positive_years': int(sum(1 for r in yearly_returns_only if r > 0)),
#                         'max_consecutive_positive': int(self._max_consecutive_positive(yearly_returns_only)),
#                         'max_consecutive_negative': int(self._max_consecutive_negative(yearly_returns_only))
#                     }
                    
#                     yearly_returns['_stats'] = stats
            
#             # تحويل كل القيم إلى Python types
#             yearly_returns_clean = {}
#             for k, v in yearly_returns.items():
#                 if isinstance(v, (np.float32, np.float64, float, int)):
#                     yearly_returns_clean[k] = float(v)
#                 elif isinstance(v, dict):
#                     yearly_returns_clean[k] = self._convert_to_serializable(v)
#                 else:
#                     yearly_returns_clean[k] = v
            
#             return self._convert_to_serializable(yearly_returns_clean)
            

            
#         except Exception as e:
#             print(f"❌ خطأ في حساب العوائد السنوية: {e}")
#             traceback.print_exc()
#             return {}

#     def _calculate_symbols_performance(self, trades: List[Trade], config: BacktestConfig) -> Dict[str, Dict[str, Any]]:
#         """
#         حساب أداء متقدم لكل رمز على حدة
        
#         Args:
#             trades: قائمة الصفقات
#             config: إعدادات الباك-تست
        
#         Returns:
#             Dict[str, Dict[str, Any]]: قاموس بالأداء التفصيلي لكل رمز
#         """
#         symbols_performance = {}
        
#         for symbol in config.symbols:
#             # تصفية صفقات الرمز
#             symbol_trades = [t for t in trades if t.symbol == symbol]
            
#             if not symbol_trades:
#                 continue
            
#             # الصفقات المكتملة فقط
#             completed_trades = [t for t in symbol_trades 
#                             if t.exit_time is not None 
#                             and t.pnl is not None 
#                             and t.entry_price is not None]
            
#             if not completed_trades:
#                 # تحليل الصفقات المفتوحة (إذا وجدت)
#                 open_trades = [t for t in symbol_trades if t.exit_time is None]
#                 if open_trades:
#                     symbols_performance[symbol] = self._analyze_open_trades(symbol, open_trades, config)
#                 continue
            
#             # 1. المقاييس الأساسية
#             total_trades = len(completed_trades)
#             winning_trades = [t for t in completed_trades if t.pnl > 0]
#             losing_trades = [t for t in completed_trades if t.pnl <= 0]
#             breakeven_trades = [t for t in completed_trades if t.pnl == 0]
            
#             winning_count = len(winning_trades)
#             losing_count = len(losing_trades)
#             breakeven_count = len(breakeven_trades)
            
#             # 2. إحصائيات الربح/الخسارة
#             gross_profit = sum(t.pnl for t in winning_trades)
#             gross_loss = abs(sum(t.pnl for t in losing_trades))
#             net_profit = gross_profit - gross_loss
            
#             # 3. حساب القيمة المستثمرة (مبني على الدخول)
#             total_invested = sum(t.entry_price * t.position_size for t in completed_trades)
#             avg_position_size = np.mean([t.position_size for t in completed_trades]) if completed_trades else 0
            
#             # 4. نسب الأداء
#             win_rate = (winning_count / total_trades * 100) if total_trades > 0 else 0
#             profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
#             avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
#             avg_loss = np.mean([abs(t.pnl) for t in losing_trades]) if losing_trades else 0
            
#             # 5. نسبة المخاطرة/العائد (Risk/Reward Ratio)
#             avg_rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            
#             # 6. تحليل الصفقات الفردية
#             pnls = [t.pnl for t in completed_trades]
#             pnl_percentages = [t.pnl_percentage for t in completed_trades if t.pnl_percentage is not None]
            
#             # 7. تحليل التوقيت
#             durations = []
#             for trade in completed_trades:
#                 if trade.entry_time and trade.exit_time:
#                     duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600  # ساعات
#                     durations.append(duration)
            
#             avg_duration = np.mean(durations) if durations else 0
            
#             # 8. تحليل التوزيع الزمني
#             monthly_trades = self._analyze_trades_by_month(completed_trades)
#             hourly_trades = self._analyze_trades_by_hour(completed_trades)
            
#             # 9. حساب الحد الأقصى للانخفاض لكل رمز
#             symbol_equity_curve = self._build_symbol_equity_curve(symbol, completed_trades, config.initial_capital)
#             symbol_drawdown_curve = self.metrics_calculator._calculate_drawdown_curve(symbol_equity_curve)
#             max_drawdown = max(symbol_drawdown_curve) if symbol_drawdown_curve else 0
            
#             # 10. حساب تقلبات الرمز
#             returns = self.metrics_calculator._calculate_returns(symbol_equity_curve)
#             volatility = np.std(returns) * np.sqrt(252) * 100 if returns else 0
            
#             # 11. تجميع كل المقاييس
#             # symbols_performance[symbol] = {
#             #     # الأساسية
#             #     'total_trades': total_trades,
#             #     'completed_trades': len(completed_trades),
#             #     'open_trades': len(symbol_trades) - len(completed_trades),
#             #     'winning_trades': winning_count,
#             #     'losing_trades': losing_count,
#             #     'breakeven_trades': breakeven_count,
                
#             #     # الأداء المالي
#             #     'gross_profit': float(gross_profit),
#             #     'gross_loss': float(gross_loss),
#             #     'net_profit': float(net_profit),
#             #     'total_invested': float(total_invested),
#             #     'avg_position_size': float(avg_position_size),
                
#             #     # النسب
#             #     'win_rate': float(win_rate),
#             #     'profit_factor': float(profit_factor) if profit_factor != float('inf') else None,
#             #     'avg_win': float(avg_win),
#             #     'avg_loss': float(avg_loss),
#             #     'avg_rr_ratio': float(avg_rr_ratio),
                
#             #     # الإحصائيات
#             #     'best_trade': float(max(pnls)) if pnls else 0,
#             #     'worst_trade': float(min(pnls)) if pnls else 0,
#             #     'avg_pnl': float(np.mean(pnls)) if pnls else 0,
#             #     'std_pnl': float(np.std(pnls)) if len(pnls) > 1 else 0,
#             #     'sharpe_ratio': (np.mean(pnls) / np.std(pnls) * np.sqrt(252)) if len(pnls) > 1 and np.std(pnls) > 0 else 0,
                
#             #     # التوقيت
#             #     'avg_trade_duration_hours': float(avg_duration),
#             #     'min_duration': float(min(durations)) if durations else 0,
#             #     'max_duration': float(max(durations)) if durations else 0,
                
#             #     # المخاطرة
#             #     'max_drawdown_percent': float(max_drawdown),
#             #     'volatility_percent': float(volatility),
#             #     'var_95': self._calculate_symbol_var(completed_trades, 0.95),
#             #     'cvar_95': self._calculate_symbol_cvar(completed_trades, 0.95),
                
#             #     # تحليل متقدم
#             #     'expectancy': float((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)) if avg_loss > 0 else 0,
#             #     'kelly_criterion': float(win_rate/100 - ((100-win_rate)/100) / (avg_win/avg_loss)) if avg_loss > 0 and avg_win > 0 else 0,
#             #     'system_quality_number': self._calculate_symbol_sqn(completed_trades),
                
#             #     # تحليل التوزيع
#             #     'monthly_distribution': monthly_trades,
#             #     'hourly_distribution': hourly_trades,
#             #     'pnl_distribution': self._analyze_pnl_distribution(pnls),
                
#             #     # بيانات إضافية للرسم البياني
#             #     '_equity_curve': symbol_equity_curve,
#             #     '_drawdown_curve': symbol_drawdown_curve
#             # }


#             performance_data = {
#                 # الأساسية
#                 'total_trades': int(len(symbol_trades)),
#                 'completed_trades': int(len(completed_trades)),
#                 'open_trades': int(len(symbol_trades) - len(completed_trades)),
#                 'winning_trades': int(winning_count),
#                 'losing_trades': int(losing_count),
#                 'breakeven_trades': int(breakeven_count),
                
#                 # الأداء المالي
#                 'gross_profit': float(gross_profit),
#                 'gross_loss': float(gross_loss),
#                 'net_profit': float(net_profit),
#                 'total_invested': float(total_invested),
#                 'avg_position_size': float(avg_position_size),
                
#                 # النسب
#                 'win_rate': float(win_rate),
#                 'profit_factor': float(profit_factor) if profit_factor != float('inf') else None,
#                 'avg_win': float(avg_win),
#                 'avg_loss': float(avg_loss),
#                 'avg_rr_ratio': float(avg_rr_ratio),
                
#                 # الإحصائيات
#                 'best_trade': float(max(pnls)) if pnls else 0.0,
#                 'worst_trade': float(min(pnls)) if pnls else 0.0,
#                 'avg_pnl': float(np.mean(pnls)) if pnls else 0.0,
#                 'std_pnl': float(np.std(pnls)) if len(pnls) > 1 else 0.0,
#                 'sharpe_ratio': float((np.mean(pnls) / np.std(pnls) * np.sqrt(252)) if len(pnls) > 1 and np.std(pnls) > 0 else 0.0),
                
#                 # التوقيت
#                 'avg_trade_duration_hours': float(avg_duration),
#                 'min_duration': float(min(durations)) if durations else 0.0,
#                 'max_duration': float(max(durations)) if durations else 0.0,
                
#                 # المخاطرة
#                 'max_drawdown_percent': float(max_drawdown),
#                 'volatility_percent': float(volatility),
#                 'var_95': float(self._calculate_symbol_var(completed_trades, 0.95)),
#                 'cvar_95': float(self._calculate_symbol_cvar(completed_trades, 0.95)),
                
#                 # تحليل متقدم
#                 'expectancy': float((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)) if avg_loss > 0 else 0.0,
#                 'kelly_criterion': float(win_rate/100 - ((100-win_rate)/100) / (avg_win/avg_loss)) if avg_loss > 0 and avg_win > 0 else None,
#                 'system_quality_number': float(self._calculate_symbol_sqn(completed_trades)),
                
#                 # تحليل التوزيع (تحويل الأنواع)
#                 'monthly_distribution': {str(k): int(v) for k, v in monthly_trades.items()} if monthly_trades else None,
#                 'hourly_distribution': {int(k): int(v) for k, v in hourly_trades.items()} if hourly_trades else None,
#                 'pnl_distribution': self._convert_to_serializable(PnlDistribution) if PnlDistribution else None,
                
#                 # بيانات إضافية للرسم البياني
#                 '_equity_curve': [float(x) for x in symbol_equity_curve],
#                 '_drawdown_curve': [float(x) for x in symbol_drawdown_curve]
#             }
            
#             symbols_performance[symbol] = self._convert_to_serializable(performance_data)


#         return symbols_performance    
    


#     def _max_consecutive_positive(self, values: List[float]) -> int:
#         """حساب أقصى عدد متتالي من القيم الموجبة"""
#         max_streak = 0
#         current_streak = 0
        
#         for value in values:
#             if value > 0:
#                 current_streak += 1
#                 max_streak = max(max_streak, current_streak)
#             else:
#                 current_streak = 0
        
#         return max_streak

#     def _max_consecutive_negative(self, values: List[float]) -> int:
#         """حساب أقصى عدد متتالي من القيم السالبة"""
#         max_streak = 0
#         current_streak = 0
        
#         for value in values:
#             if value < 0:
#                 current_streak += 1
#                 max_streak = max(max_streak, current_streak)
#             else:
#                 current_streak = 0
        
#         return max_streak

#     def _build_symbol_equity_curve(self, symbol: str, trades: List[Trade], initial_capital: float) -> List[float]:
#         """بناء منحنى الأسهم لرمز معين"""
#         if not trades:
#             return [initial_capital]
        
#         # ترتيب الصفقات حسب وقت الدخول
#         sorted_trades = sorted(trades, key=lambda x: x.entry_time)
        
#         curve = [initial_capital]
#         current_equity = initial_capital
        
#         for trade in sorted_trades:
#             # تحديث عند الدخول (العمولة)
#             entry_cost = trade.commission if trade.commission else 0
#             current_equity -= entry_cost
#             curve.append(current_equity)
            
#             # تحديث عند الخروج
#             if trade.exit_time and trade.pnl is not None:
#                 current_equity += trade.pnl
#                 curve.append(current_equity)
        
#         return curve

#     def _analyze_trades_by_month(self, trades: List[Trade]) -> Dict[str, int]:
#         """تحليل الصفقات حسب الشهر"""
#         monthly_counts = {}
        
#         for trade in trades:
#             if trade.entry_time:
#                 month_key = trade.entry_time.strftime("%Y-%m")
#                 monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
        
#         return monthly_counts

#     def _analyze_trades_by_hour(self, trades: List[Trade]) -> Dict[int, int]:
#         """تحليل الصفقات حسب ساعة اليوم"""
#         hourly_counts = {hour: 0 for hour in range(24)}
        
#         for trade in trades:
#             if trade.entry_time:
#                 hour = trade.entry_time.hour
#                 hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
#         return hourly_counts

#     def _calculate_symbol_var(self, trades: List[Trade], confidence_level: float = 0.95) -> float:
#         """حساب Value at Risk للرمز"""
#         if not trades:
#             return 0.0
        
#         pnls = [t.pnl_percentage for t in trades if t.pnl_percentage is not None]
#         if not pnls:
#             return 0.0
        
#         sorted_pnls = np.sort(pnls)
#         var_index = int((1 - confidence_level) * len(sorted_pnls))
        
#         if var_index < len(sorted_pnls):
#             return float(-sorted_pnls[var_index])  # نرجع القيمة الإيجابية للخسارة
#         else:
#             return float(-sorted_pnls[-1] if sorted_pnls else 0)

#     def _calculate_symbol_cvar(self, trades: List[Trade], confidence_level: float = 0.95) -> float:
#         """حساب Conditional VaR للرمز"""
#         if not trades:
#             return 0.0
        
#         pnls = [t.pnl_percentage for t in trades if t.pnl_percentage is not None]
#         if not pnls:
#             return 0.0
        
#         sorted_pnls = np.sort(pnls)
#         var_index = int((1 - confidence_level) * len(sorted_pnls))
        
#         if var_index > 0:
#             cvar = np.mean(sorted_pnls[:var_index])
#             return float(-cvar)  # نرجع القيمة الإيجابية
#         else:
#             return 0.0

#     def _calculate_symbol_sqn(self, trades: List[Trade]) -> float:
#         """حساب System Quality Number للرمز"""
#         if not trades:
#             return 0.0
        
#         pnls = [t.pnl_percentage for t in trades if t.pnl_percentage is not None]
#         if not pnls or len(pnls) < 2:
#             return 0.0
        
#         mean_pnl = np.mean(pnls)
#         std_pnl = np.std(pnls)
        
#         if std_pnl == 0:
#             return 0.0
        
#         return float((mean_pnl / std_pnl) * np.sqrt(len(pnls)))

#     def _analyze_pnl_distribution(self, pnls: List[float]) -> Dict[str, Any]:
#         """تحليل توزيع الربح/الخسارة"""
#         if not pnls:
#             return {}
        
#         from scipy import stats
        
#         distribution = {
#             'mean': float(np.mean(pnls)),
#             'median': float(np.median(pnls)),
#             'std': float(np.std(pnls)),
#             'skewness': float(stats.skew(pnls)) if len(pnls) > 2 else 0,
#             'kurtosis': float(stats.kurtosis(pnls)) if len(pnls) > 3 else 0,
#             'q1': float(np.percentile(pnls, 25)),
#             'q3': float(np.percentile(pnls, 75)),
#             'iqr': float(np.percentile(pnls, 75) - np.percentile(pnls, 25)),
#             'outliers': self._find_outliers(pnls)
#         }
        
#         return distribution

#     def _find_outliers(self, data: List[float]) -> List[float]:
#         """العثور على القيم المتطرفة"""
#         if len(data) < 4:
#             return []
        
#         q1 = np.percentile(data, 25)
#         q3 = np.percentile(data, 75)
#         iqr = q3 - q1
        
#         lower_bound = q1 - 1.5 * iqr
#         upper_bound = q3 + 1.5 * iqr
        
#         return [float(x) for x in data if x < lower_bound or x > upper_bound]

#     def _analyze_open_trades(self, symbol: str, open_trades: List[Trade], config: BacktestConfig) -> Dict[str, Any]:
#         """تحليل الصفقات المفتوحة"""
#         if not open_trades:
#             return {}
        
#         current_values = []
#         unrealized_pnls = []
        
#         for trade in open_trades:
#             # في التطبيق الحقيقي، تحتاج إلى سعر السوق الحالي
#             # هنا سنفترض سعر الإغلاق الحالي هو نفس سعر الدخول (افتراضي)
#             current_price = trade.entry_price
            
#             if trade.position_type == 'long':
#                 unrealized_pnl = (current_price - trade.entry_price) * trade.position_size
#             else:  # short
#                 unrealized_pnl = (trade.entry_price - current_price) * trade.position_size
            
#             current_value = trade.entry_price * trade.position_size + unrealized_pnl
            
#             current_values.append(current_value)
#             unrealized_pnls.append(unrealized_pnl)
        
#         total_unrealized_pnl = sum(unrealized_pnls)
#         total_current_value = sum(current_values)
        
#         return {
#             'open_trades_count': len(open_trades),
#             'total_unrealized_pnl': float(total_unrealized_pnl),
#             'total_current_value': float(total_current_value),
#             'avg_unrealized_pnl': float(np.mean(unrealized_pnls)) if unrealized_pnls else 0,
#             'max_unrealized_pnl': float(max(unrealized_pnls)) if unrealized_pnls else 0,
#             'min_unrealized_pnl': float(min(unrealized_pnls)) if unrealized_pnls else 0,
#             'open_positions_summary': [
#                 {
#                     'id': t.id,
#                     'entry_price': t.entry_price,
#                     'position_size': t.position_size,
#                     'position_type': t.position_type,
#                     'unrealized_pnl': float((current_price - t.entry_price) * t.position_size 
#                                         if t.position_type == 'long' 
#                                         else (t.entry_price - current_price) * t.position_size)
#                 }
#                 for t in open_trades
#             ]
#         }

