from datetime import datetime
from app.database.session import get_db
from app.services.data_service import DataService
from fastapi import APIRouter, Depends, HTTPException, WebSocket, Query, logger
from app.websocket.manager import manager
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["market-data"])




@router.get("/status")
async def system_status():
    """حالة النظام"""   
    return {
        "status": "operational",
        "services": {
            "database": "connected",
            "redis": "connected",
            "websocket": "active"
        }
    }


@router.get("/symbols")
async def get_available_symbols(
    market: str = "crypto",
    db: AsyncSession = Depends(get_db)
):
    """الحصول على الرموز المتاحة حسب السوق"""
    try:
        service = DataService(db)
        symbols = await service.get_symbols(market)
        
        if not symbols:
            return {
                "market": market,
                "symbols": [],
                "message": f"No symbols found for market: {market}",
                "count": 0
            }
        
        return {
            "market": market,
            "symbols": symbols,
            "count": len(symbols),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "market": market,
                "message": str(e)
            }
        )

@router.websocket("/ws/live/{market}/{symbol}")
async def websocket_live_data(
    websocket: WebSocket,
    market: str,
    symbol: str,
    timeframe: str = Query("1m", regex="^(1m|5m|15m|1h|4h|1d)$")
):
    """
    WebSocket لبث البيانات الحية
    """
    await manager.handle_subscription(
        websocket=websocket,
        symbol=symbol,
        timeframe=timeframe,
        market=market
    )

# @router.get("/historical/{market}/{symbol}")
# async def get_historical_data(
#     market: str,
#     symbol: str,
#     timeframe: str = "1h",
#     days: int = 30,
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     الحصول على بيانات تاريخية
#     """


#     data_service = DataService(db)
#     df = await data_service.get_historical(
#         symbol=symbol,
#         timeframe=timeframe,
#         market=market,
#         days=days
#     )
    
#     return {
#         "symbol": symbol,
#         "market": market,
#         "timeframe": timeframe,
#         "data": df.to_dict('records')
#     }

@router.get("/historical/{market}/{symbol}")
async def get_historical_data(
    market: str,
    symbol: str,
    timeframe: str = "1h",
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    الحصول على بيانات تاريخية
    """
    try:
        # تحقق من صحة الإدخال
        if days > 3650:  # حد أقصى 10 سنوات
            raise HTTPException(
                status_code=400,
                detail="Days parameter cannot exceed 3650"
            )
        
        data_service = DataService(db)
        
        # دعم اختصارات الأسواق
        market_map = {
            "stock": "stocks",
            "stocks": "stocks",
            "crypto": "crypto",
            "binance": "crypto"
        }
        
        normalized_market = market_map.get(market.lower(), market)
        
        df = await data_service.get_historical(
            symbol=symbol,
            timeframe=timeframe,
            market=normalized_market,
            days=days
        )
        
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for {symbol} in {market}"
            )
        
        # تحويل التاريخ إلى سلسلة نصية
        data_records = []
        for idx, row in df.reset_index().iterrows():
            record = row.to_dict()
            if 'timestamp' in record:
                record['timestamp'] = record['timestamp'].isoformat()
            elif 'index' in record:
                record['timestamp'] = record['index'].isoformat()
            data_records.append(record)
        
        return {
            "symbol": symbol,
            "market": normalized_market,
            "timeframe": timeframe,
            "days": days,
            "row_count": len(df),
            "start_date": df.index[0].isoformat() if len(df) > 0 else None,
            "end_date": df.index[-1].isoformat() if len(df) > 0 else None,
            "data": data_records
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in get_historical_data: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )
    

@router.get("/price/{market}/{symbol}")
async def get_current_price(
    market: str,
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """
    الحصول على السعر الحالي
    """
    data_service = DataService(db)
    price = await data_service.get_live_price(symbol, market)
    
    return price