# trading_backend\app\routers\api.py
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, logger, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, redis_client
from app.services.data_service import DataService
from app.providers.binance_market_stream import stream_all_market

router = APIRouter(tags=["core"])





@router.websocket("/market-overview")
async def websocket_market_overview(websocket: WebSocket):
    await websocket.accept()
    print("📊 Market overview WS connected")

    try:
        async for payload in stream_all_market():
            await websocket.send_json(payload)
            await asyncio.sleep(7)  # تحكم في الضغط
    except WebSocketDisconnect:
        print("❌ Market overview disconnected")



@router.get("/symbols")
async def get_available_symbols(
    market: str = "crypto",
    db: AsyncSession = Depends(get_db)
):
    print("🔥 ENTER /symbols endpoint", flush=True)
    print("🔥 market =", market, flush=True)

    service = DataService(db)

    try:
        print("🔥 Calling service.get_symbols() ...", flush=True)

        symbols = await service.get_symbols(market)

        print("🔥 service.get_symbols() RETURNED:", len(symbols), "symbols", flush=True)

        response = {
            "market": market,
            "symbols": symbols,
            "count": len(symbols),
            "timestamp": datetime.utcnow().isoformat()
        }

        print("🔥 RESPONSE READY", flush=True)
        return response

    except Exception as e:
        print("🔥 ERROR in endpoint:", e, flush=True)
        print("🔥 FULL TRACEBACK:", flush=True)
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )



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





@router.get("/health")
async def health_check():
    """فحص حالة جميع الخدمات"""
    services_status = {
        "api": "healthy",
        "providers": {},
        "redis": "unknown",
        "database": "unknown"
    }
    
    # فحص Redis
    try:
        await redis_client.ping()
        services_status["redis"] = "healthy"
    except Exception as e:
        services_status["redis"] = f"unhealthy: {str(e)}"
    
    # فحص المزودين
    try:
        from app.providers.binance_provider import BinanceProvider
        provider = BinanceProvider()
        symbols = await provider.get_symbols()
        services_status["providers"]["binance"] = f"healthy ({len(symbols)} symbols)"
    except Exception as e:
        services_status["providers"]["binance"] = f"unhealthy: {str(e)}"
    
    return services_status