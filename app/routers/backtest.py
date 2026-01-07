# app\routers\backtest.py
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from app.backtest.engine import BacktestEngine
from app.backtest.reports import ReportGenerator
from app.backtest.schemas import BacktestConfig, BacktestResult
from app.services.data_service import DataService
from app.database import get_db

router = APIRouter(tags=["backtest"])

# إنشاء كائنات عامة
_backtest_engine = None
_report_generator = ReportGenerator()

def get_backtest_engine(db) -> BacktestEngine:
    """الحصول على BacktestEngine"""
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
    تشغيل باك-تيست كامل
    
    - **config**: تكوين الباك-تيست
    - **generate_report**: إنشاء تقرير مفصل
    - **save_to_file**: حفظ النتائج إلى ملف
    """
    try:
        engine = get_backtest_engine(db)
        
        print(f"Starting backtest: {config.name}")


        if config.strategy_config:
            strategy_name = config.strategy_config.get('name', 'Unknown')
            print(f"📊 Using strategy: {strategy_name}")

            
        # تشغيل الباك-تيست
        result = await engine.run_backtest(config)
        
        response = {
            "success": True,
            "backtest_id": result.id,
            "summary": {
                "name": config.name,
                "initial_capital": result.initial_capital,
                "final_capital": result.final_capital,
                "total_pnl": result.total_pnl,
                "total_pnl_percent": result.total_pnl_percent,
                "total_trades": result.total_trades,
                "win_rate": result.win_rate,
                "max_drawdown": result.max_drawdown_percent,
                "sharpe_ratio": result.sharpe_ratio,
                "execution_time_seconds": result.execution_time_seconds
            }
        }
        
        if generate_report:
            report = _report_generator.generate_full_report(result, include_charts=True)
            response["report"] = report
            
            if save_to_file:
                filepath = _report_generator.save_report_to_file(result)
                response["report_file"] = filepath
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/walk-forward")
async def run_walk_forward_analysis(
    config: BacktestConfig = Body(...),
    periods: int = Query(5, ge=2, le=20),
    db = Depends(get_db)
):
    """
    تشغيل تحليل مشي للأمام
    
    - **config**: تكوين الباك-تيست
    - **periods**: عدد الفترات
    """
    try:
        engine = get_backtest_engine(db)
        
        print(f"Starting walk-forward analysis with {periods} periods")
        
        results = await engine.run_walk_forward_analysis(config, periods)
        
        # تحليل النتائج
        periods_summary = []
        for i, result in enumerate(results):
            periods_summary.append({
                "period": i + 1,
                "start_date": result.config.start_date.isoformat(),
                "end_date": result.config.end_date.isoformat(),
                "total_pnl_percent": result.total_pnl_percent,
                "win_rate": result.win_rate,
                "max_drawdown": result.max_drawdown_percent,
                "sharpe_ratio": result.sharpe_ratio,
                "total_trades": result.total_trades
            })
        
        # حساب المتوسطات
        avg_pnl = sum(r.total_pnl_percent for r in results) / len(results)
        avg_win_rate = sum(r.win_rate for r in results) / len(results)
        avg_sharpe = sum(r.sharpe_ratio for r in results) / len(results)
        
        return {
            "success": True,
            "periods": periods,
            "periods_summary": periods_summary,
            "averages": {
                "avg_pnl_percent": avg_pnl,
                "avg_win_rate": avg_win_rate,
                "avg_sharpe_ratio": avg_sharpe
            },
            "consistency": {
                "positive_periods": sum(1 for r in results if r.total_pnl_percent > 0),
                "negative_periods": sum(1 for r in results if r.total_pnl_percent < 0)
            }
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
    
    - **config**: تكوين الباك-تيست
    - **simulations**: عدد المحاكاة
    """
    try:
        engine = get_backtest_engine(db)
        
        print(f"Starting Monte Carlo simulation with {simulations} iterations")
        
        results = await engine.run_monte_carlo_simulation(config, simulations)
        
        return {
            "success": True,
            "simulations": simulations,
            "results": results,
            "interpretation": {
                "probability_of_profit": f"{results['probability_profit'] * 100:.1f}%",
                "probability_of_loss": f"{results['probability_loss'] * 100:.1f}%",
                "expected_return_range": f"{results['percentile_5']:.1f}% to {results['percentile_95']:.1f}%",
                "worst_case_scenario": f"{results['min_return']:.1f}%",
                "best_case_scenario": f"{results['max_return']:.1f}%"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/{backtest_id}")
async def get_backtest_result(backtest_id: str):
    """
    الحصول على نتيجة باك-تيست محفوظة
    
    - **backtest_id**: معرف الباك-تيست
    """
    # في التطبيق الحقيقي، سنقوم بجلب النتائج من قاعدة البيانات
    # هنا نرجع رسالة توضيحية
    
    return {
        "message": "Backtest results retrieval is implemented",
        "backtest_id": backtest_id,
        "note": "In a real implementation, results would be fetched from database"
    }

@router.post("/compare")
async def compare_backtests(
    configs: List[BacktestConfig] = Body(...),
    db = Depends(get_db)
):
    """
    مقارنة عدة باك-تيست
    
    - **configs**: قائمة تكوينات الباك-تيست
    """
    try:
        if len(configs) < 2:
            raise HTTPException(status_code=400, detail="At least 2 configs required for comparison")
        
        engine = get_backtest_engine(db)
        
        print(f"Comparing {len(configs)} backtests")
        
        results = []
        for config in configs:
            result = await engine.run_backtest(config)
            results.append(result)
        
        # إنشاء جدول مقارنة
        comparison = []
        for i, result in enumerate(results):
            comparison.append({
                "name": result.config.name,
                "initial_capital": result.initial_capital,
                "final_capital": result.final_capital,
                "total_pnl_percent": result.total_pnl_percent,
                "annual_return_percent": result.annual_return_percent,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown_percent": result.max_drawdown_percent,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "total_trades": result.total_trades,
                "expectancy": result.expectancy,
                "execution_time_seconds": result.execution_time_seconds
            })
        
        # تحديد الأفضل في كل فئة
        best_performer = max(results, key=lambda x: x.total_pnl_percent)
        best_risk_adjusted = max(results, key=lambda x: x.sharpe_ratio)
        lowest_drawdown = min(results, key=lambda x: x.max_drawdown_percent)
        highest_win_rate = max(results, key=lambda x: x.win_rate)
        
        return {
            "success": True,
            "comparison": comparison,
            "winners": {
                "best_performer": best_performer.config.name,
                "best_risk_adjusted": best_risk_adjusted.config.name,
                "lowest_drawdown": lowest_drawdown.config.name,
                "highest_win_rate": highest_win_rate.config.name
            },
            "statistics": {
                "avg_pnl_percent": sum(r.total_pnl_percent for r in results) / len(results),
                "avg_sharpe_ratio": sum(r.sharpe_ratio for r in results) / len(results),
                "avg_win_rate": sum(r.win_rate for r in results) / len(results)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/report/{backtest_id}")
async def generate_backtest_report(
    backtest_id: str,
    format: str = Query("json", regex="^(json|html)$")
):
    """
    توليد تقرير باك-تيست
    
    - **backtest_id**: معرف الباك-تيست
    - **format**: صيغة التقرير (json, html)
    """
    # في التطبيق الحقيقي، سنقوم بجلب النتائج من قاعدة البيانات
    # هنا نقدم مثالاً
    
    example_report = {
        "backtest_id": backtest_id,
        "summary": {
            "name": "Example Backtest",
            "period": "2023-01-01 to 2023-12-31",
            "initial_capital": 10000,
            "final_capital": 12500,
            "total_return": "25.0%",
            "total_trades": 45,
            "win_rate": "62.2%"
        },
        "note": "This is an example. In real implementation, report would be generated from actual backtest results."
    }
    
    return example_report

@router.get("/available-metrics")
async def get_available_metrics():
    """
    الحصول على قائمة المقاييس المتاحة في التقارير
    """
    return {
        "return_metrics": [
            "total_pnl_percent",
            "annual_return_percent",
            "monthly_return_avg",
            "yearly_return_avg"
        ],
        "risk_metrics": [
            "max_drawdown_percent",
            "max_drawdown_duration_days",
            "volatility_annual",
            "var_95",
            "cvar_95"
        ],
        "risk_adjusted_metrics": [
            "sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "profit_factor",
            "expectancy"
        ],
        "trade_metrics": [
            "total_trades",
            "winning_trades",
            "losing_trades",
            "win_rate",
            "avg_winning_trade",
            "avg_losing_trade",
            "largest_winning_trade",
            "largest_losing_trade",
            "avg_trade_duration_hours"
        ],
        "advanced_metrics": [
            "system_quality_number",
            "kelly_criterion",
            "recovery_factor",
            "ulcer_index"
        ]
    }