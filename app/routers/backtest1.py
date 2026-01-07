# app/routers/backtest.py
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from app.backtest.engine1 import BacktestEngine
from app.backtest.reports import ReportGenerator
from app.backtest.schemas import BacktestConfig, BacktestResult
from app.services.data_service import DataService
from app.database import get_db


router = APIRouter(tags=["backtest1"])
logger = logging.getLogger(__name__)

_backtest_engine = None
_report_generator = ReportGenerator()
_backtest_storage = {}  # {backtest_id: BacktestResult}
_engine_cache = None

async def get_backtest_from_db(backtest_id: str) -> Optional[BacktestResult]:
    """استرجاع نتيجة الباك-تست من التخزين المؤقت"""
    return _backtest_storage.get(backtest_id)


def get_backtest_engine(db) -> BacktestEngine:
    """Get or Create BacktestEngine"""
    global _backtest_engine
    if _backtest_engine is None:
        data_service = DataService(db)
        _backtest_engine = BacktestEngine(data_service)
    return _backtest_engine






@router.post("/run")
async def run_backtest(
    config: BacktestConfig = Body(...),
    generate_report: bool = Query(True),
    save_to_file: bool = Query(False),
    db = Depends(get_db)
):
    """
    تشغيل باك-تيست كامل (يعمل الآن كمحرك تنفيذ للقرارات)
    """
    try:
        engine = get_backtest_engine(db)
        
        strategy_name = config.strategy_config.get('name', 'Unknown') if config.strategy_config else 'Default'
        logger.info(f"🚀 Starting Backtest for strategy: {strategy_name}")
        
        # تشغيل المحرك (الذي سيقوم بإنشاء StrategyEngine داخلياً وتنفيذ القرارات)
        result = await engine.run_backtest(config)

        _backtest_storage[result.id] = result

        
        response = {
            "success": True,
            "backtest_id": result.id,
            "summary": {
                "name": config.name,
                "timeframe": config.timeframe,
                "initial_capital": result.initial_capital,
                "final_capital": result.final_capital,
                "total_pnl": result.total_pnl,
                "total_pnl_percent": result.total_pnl_percent,  # ★ الاسم الجديد
                "total_trades": result.total_trades,
                "winning_trades": result.winning_trades,
                "losing_trades": result.losing_trades,
                "win_rate": result.win_rate,
                "max_drawdown_percent": result.max_drawdown_percent,
                "sharpe_ratio": result.sharpe_ratio,
                "sortino_ratio": result.sortino_ratio,
                "calmar_ratio": result.calmar_ratio,
                "profit_factor": result.profit_factor,
                "expectancy": result.expectancy,
                "annual_return_percent": result.annual_return_percent,
                "execution_time_seconds": result.execution_time_seconds,
                "architecture_mode": "Strategy-Decision-Driven"
            },
            # بيانات إضافية يمكن استخدامها لاحقاً
            "advanced_metrics": {
                "volatility_annual": result.volatility_annual,
                "var_95": result.var_95,
                "cvar_95": result.cvar_95,
                "system_quality_number": result.system_quality_number,
                "kelly_criterion": result.kelly_criterion
            }
        }
        
        if hasattr(result, 'visual_candles'):
            response["visual_candles_count"] = len(result.visual_candles)
        if hasattr(result, 'trade_points'):
            response["trade_points_count"] = len(result.trade_points)
        


        if generate_report:
            # التأكد من وجود دالة التوليد
            try:
                report = _report_generator.generate_full_report(result, include_charts=True)
                response["report"] = report
                
                if save_to_file:
                    filepath = _report_generator.save_report_to_file(result)
                    response["report_file"] = filepath
            except Exception as report_err:
                logger.warning(f"Failed to generate detailed report: {report_err}")
                response["report_note"] = "Report generation failed, but data is available in summary."
        
        return response
        
    except Exception as e:
        logger.exception("Backtest execution failed")
        raise HTTPException(status_code=500, detail=str(e))


























# ✅ 1. دالة مساعدة لتفكيك القواميس المتداخلة (مثل Bollinger Bands)
def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """
    يحول قاموس متداخل مثل: {"bb": {"upper": 3000, "lower": 2900}}
    إلى قاموس مسطح مثل: {"bb_upper": 3000, "bb_lower": 2900}
    """
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items

@router.get("/{backtest_id}/chart-data")
async def get_chart_data(
    backtest_id: str,
    start_index: int = Query(None), 
    limit: int = Query(None),
    include_indicators: Optional[List[str]] = Query(None)
):
    """
    جلب كامل بيانات الرسم البياني (Full Dump) - النسخة النهائية المحسنة
    """
    # 1. استرجاع الباك-تست
    backtest = await get_backtest_from_db(backtest_id)
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found or expired")
    
    # 2. التحقق من وجود البيانات
    if not hasattr(backtest, 'visual_candles') or not backtest.visual_candles:
        raise HTTPException(status_code=404, detail="No chart data available")
    
    # 3. جلب البيانات
    all_candles = backtest.visual_candles
    all_trade_points = backtest.trade_points if hasattr(backtest, 'trade_points') else []
    
    # 4. تجهيز الشموع (Candle Processing)
    formatted_candles = []
    
    for candle in all_candles:
        # بناء جسم الشمعة (Basic Fields)
        formatted_candle = {
            "timestamp": candle.timestamp.isoformat() if hasattr(candle.timestamp, 'isoformat') else str(candle.timestamp),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            
            # بيانات الاستراتيجية
            "strategy_decision": candle.strategy_decision,
            "position_state": candle.position_state,
            "triggered_rules": getattr(candle, 'triggered_rules', []),
            "confidence": getattr(candle, 'confidence', None),
            
            # بيانات الصفقة
            "trade_action": getattr(candle, 'trade_action', None),
            "trade_id": getattr(candle, 'trade_id', None),
            "trade_price": getattr(candle, 'trade_price', None),
            "trade_size": getattr(candle, 'trade_size', None),
            
            # البيانات المالية
            "account_balance": getattr(candle, 'account_balance', None),
            "cumulative_pnl": getattr(candle, 'cumulative_pnl', None),
            "position_size": getattr(candle, 'position_size', None),
            "entry_price": getattr(candle, 'entry_price', None),
            "stop_loss": getattr(candle, 'stop_loss', None),
            "take_profit": getattr(candle, 'take_profit', None),
            "risk_reward_ratio": getattr(candle, 'risk_reward_ratio', None),
            "current_pnl": getattr(candle, 'current_pnl', None),
            "unrealized_pnl": getattr(candle, 'unrealized_pnl', None),
            "pnl": getattr(candle, 'pnl', None),
            "pnl_percentage": getattr(candle, 'pnl_percentage', None),
            
            # بيانات إضافية
            "market_condition": getattr(candle, 'market_condition', None),
            "signal_strength": getattr(candle, 'signal_strength', None),
            "price_change_percent": getattr(candle, 'price_change_percent', None),
            "volatility": getattr(candle, 'volatility', None),
            "leverage_used": getattr(candle, 'leverage_used', None),
            "margin_used": getattr(candle, 'margin_used', None),
            "free_margin": getattr(candle, 'free_margin', None),
            "return_on_investment": getattr(candle, 'return_on_investment', None)
        }
        
        # ✅ 5. معالجة المؤشرات (Indicators Handling Logic)
        if hasattr(candle, 'indicators') and candle.indicators:
            # نستخدم دالة flatten_dict لتفكيك أي بيانات متداخلة (مثل BB)
            flat_indicators = flatten_dict(candle.indicators)
            
            for ind_name, ind_value in flat_indicators.items():
                # التحقق من الفلترة
                if include_indicators is None or ind_name in include_indicators:
                    # ✅ التعامل مع أنواع البيانات المختلفة
                    if isinstance(ind_value, (float, int)):
                        formatted_candle[f"ind_{ind_name}"] = float(ind_value)
                    elif ind_value is None:
                        formatted_candle[f"ind_{ind_name}"] = None # سيظهر كـ null في JSON
                    else:
                        # إذا كانت قيمة نصية أو غير عددية (نادر في المؤشرات لكن احتياط)
                        formatted_candle[f"ind_{ind_name}"] = ind_value
        
        formatted_candles.append(formatted_candle)
    
    # 6. معالجة علامات التداول (Trade Markers)
    trade_markers = []
    if all_trade_points:
        for trade_point in all_trade_points:
            # تحديد الفهرس
            point_time = trade_point.get("timestamp")
            point_index = None
            if point_time:
                # بحث بسيط لتحديد مكان النقطة في الشارت
                for idx, candle in enumerate(all_candles):
                    if str(candle.timestamp) == str(point_time):
                        point_index = idx
                        break
            
            marker_data = {
                "timestamp": point_time.isoformat() if hasattr(point_time, 'isoformat') else str(point_time),
                "price": trade_point.get("price"),
                "type": trade_point.get("type"),
                "trade_id": trade_point.get("trade_id"),
                "position_type": trade_point.get("position_type"),
                "position_size": trade_point.get("position_size"),
                "exit_reason": trade_point.get("exit_reason"),
                "pnl": trade_point.get("pnl"),
                "pnl_percentage": trade_point.get("pnl_percentage"),
                "entry_price": trade_point.get("entry_price"),
                "exit_price": trade_point.get("exit_price"),
                "stop_loss": trade_point.get("stop_loss"),
                "take_profit": trade_point.get("take_profit"),
                "holding_period": trade_point.get("holding_period"),
                "risk_reward_ratio": trade_point.get("risk_reward_ratio"),
                "commission": trade_point.get("commission"),
                "account_balance_before": trade_point.get("account_balance_before"),
                "account_balance_after": trade_point.get("account_balance_after"),
                "cumulative_pnl": trade_point.get("cumulative_pnl"),
                "index": point_index,
                "decision_reason": trade_point.get("decision_reason"),
                "confidence": trade_point.get("confidence")
            }
            
            # إضافة صورة المؤشرات
            if "indicators_snapshot" in trade_point:
                marker_data["indicators_snapshot"] = trade_point["indicators_snapshot"]
                
            trade_markers.append(marker_data)
    
    # 7. جمع أسماء المؤشرات المتاحة (باستخدام آخر شمعة كمرجع)
    available_indicators = []
    if formatted_candles:
        available_indicators = [key.replace("ind_", "") for key in formatted_candles[0].keys() if key.startswith("ind_")]

    # 8. بناء الاستجابة النهائية
    response = {
        "backtest_id": backtest_id,
        "metadata": {
            "name": backtest.config.name if hasattr(backtest, 'config') else "Backtest",
            "symbol": backtest.config.symbols[0] if hasattr(backtest, 'config') and backtest.config.symbols else "Unknown",
            "timeframe": backtest.config.timeframe,
            "initial_capital": backtest.initial_capital,
            "final_capital": backtest.final_capital,
            "total_pnl": backtest.total_pnl,
            "total_pnl_percent": backtest.total_pnl_percent,
            "total_trades": backtest.total_trades,
            "win_rate": backtest.win_rate,
            "start_date": formatted_candles[0]['timestamp'] if formatted_candles else None,
            "end_date": formatted_candles[-1]['timestamp'] if formatted_candles else None
        },
        "chart_data": {
            "candles": formatted_candles,
            "trade_markers": trade_markers,
            "available_indicators": available_indicators,
            "total_candles": len(all_candles),
            "total_trades": len(trade_markers)
        },
        "summary": {
            "total_candles": len(all_candles),
            "total_trades": backtest.total_trades,
            "win_rate": backtest.win_rate,
            "total_pnl": backtest.total_pnl,
            "total_pnl_percent": backtest.total_pnl_percent,
            "max_drawdown_percent": backtest.max_drawdown_percent,
            "sharpe_ratio": backtest.sharpe_ratio,
            "sortino_ratio": backtest.sortino_ratio,
            "calmar_ratio": backtest.calmar_ratio,
            "profit_factor": backtest.profit_factor,
            "annual_return_percent": backtest.annual_return_percent,
            "visible_range": f"0-{len(all_candles)}",
            "has_more_data": False
        }
    }
    
    # إضافة البيانات الإضافية
    if hasattr(backtest, 'equity_curve'):
        response["equity_curve"] = backtest.equity_curve
    if hasattr(backtest, 'drawdown_curve'):
        response["drawdown_curve"] = backtest.drawdown_curve
    
    return response


@router.post("/walk-forward")
async def run_walk_forward_analysis(
    config: BacktestConfig = Body(...),
    periods: int = Query(5, ge=2, le=20),
    db = Depends(get_db)
):
    """
    تشغيل تحليل مشي للأمام (يدعمه المحرك الجديد)
    """
    try:
        engine = get_backtest_engine(db)
        logger.info(f"Starting Walk-Forward Analysis ({periods} periods)...")
        
        results = await engine.run_walk_forward_analysis(config, periods)
        
        periods_summary = []
        for i, res in enumerate(results):
            periods_summary.append({
                "period": i + 1,
                "start_date": res.config.start_date.isoformat(),
                "end_date": res.config.end_date.isoformat(),
                "pnl_percent": res.total_pnl_percent,
                "win_rate": res.win_rate
            })
        
        return {
            "success": True,
            "periods_summary": periods_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/monte-carlo")
async def run_monte_carlo_simulation(
    config: BacktestConfig = Body(...),
    simulations: int = Query(1000, ge=100, le=10000),
    db = Depends(get_db)
):
    """
    تشغيل محاكاة مونت كارلو
    """
    try:
        engine = get_backtest_engine(db)
        results = await engine.run_monte_carlo_simulation(config, simulations)
        
        return {
            "success": True,
            "results": results,
            "interpretation": {
                "probability_of_profit": f"{results['probability_profit'] * 100:.1f}%"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics")
async def get_available_metrics():
    """الحصول على مقاييس متاحة"""
    return {
        "return_metrics": ["total_pnl", "sharpe_ratio", "win_rate"],
        "risk_metrics": ["max_drawdown", "volatility"],
        "trade_metrics": ["total_trades", "avg_win", "avg_loss"]
    }