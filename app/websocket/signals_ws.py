from fastapi import WebSocket, WebSocketDisconnect
import asyncio
from app.services.data_service import DataService
from app.services.signals.engine import SignalEngine
from app.services.signals.candle_tracker import CandleStateTracker
from app.services.signals.state import SignalStateManager
from app.database import get_db
from datetime import datetime

signal_engine = SignalEngine()
candle_tracker = CandleStateTracker()
signal_state = SignalStateManager()

async def signals_websocket(websocket: WebSocket):
    await websocket.accept()

    config = await websocket.receive_json()

    symbols = config["symbols"]
    timeframe = config["timeframe"]
    market = config.get("market", "crypto")
    indicators = config["indicators"]
    strategy = config["strategy"]

    db = await get_db().__anext__()
    data_service = DataService(db)

    try:
        while True:
            for symbol in symbols:
                df = await data_service.get_latest_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    market=market,
                    limit=50
                )

                last_time = df.iloc[-1]["time"]

                if not candle_tracker.is_new_candle(symbol, timeframe, last_time):
                    continue

                result = signal_engine.evaluate(
                    symbol,
                    timeframe,
                    market,
                    df,
                    indicators,
                    strategy
                )

                if result.signal and signal_state.should_emit(
                    symbol, result.signal, result.candle_time
                ):
                    await websocket.send_json(result.dict())

            await asyncio.sleep(30)

    except WebSocketDisconnect:
        pass
