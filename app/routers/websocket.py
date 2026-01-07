# app\routers\websocket.py
import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, Query, WebSocketDisconnect
from typing import Optional
import json

from app.websocket.manager import manager
from app.services.data_service import DataService
from app.services.filtering import FilteringEngine
from app.database import get_db
from app.providers.binance_market_stream import stream_all_market
from app.websocket.signals_ws import signals_websocket
from typing import Dict, List, Optional
from app.websocket.chart_ws import router as chart_router




router = APIRouter(tags=["websocket"])
router.include_router(chart_router)
# متغيرات عامة
_data_service = None
_filtering_engine = None






def initialize_websocket_services():
    """تهيئة خدمات WebSocket"""
    global _data_service, _filtering_engine
    
    if _data_service is None or _filtering_engine is None:
        # في بيئة حقيقية، سنحتاج إلى جلسة قاعدة بيانات
        # هنا نستخدم تهيئة بسيطة
        _data_service = DataService(None)  # سيتم حقن DB session لاحقاً
        _filtering_engine = FilteringEngine()
        manager.initialize(_data_service, _filtering_engine)


















@router.websocket("/ws/indicators/{symbol}")
async def indicators_websocket(websocket: WebSocket, symbol: str):
    await websocket.accept()
    
    
    try:
        # 1. استقبال إعدادات المؤشرات من العميل
        data = await websocket.receive_json()
        indicators_config = data.get('indicators', [])
        
        # 2. إضافة الرمز للمراقبة (إذا لم يكن مضافاً)
        from app.providers.binance_indicators_stream import indicators_manager
        await indicators_manager.add_symbol_monitoring(symbol, indicators_config)
        
        # 3. إضافة العميل لقائمة المشتركين
        indicators_manager.active_symbols[symbol]['clients'].append(websocket)
        
        # 4. إرسال البيانات التاريخية أولاً
        from app.services.data_service import DataService
        data_service = DataService()
        
        historical_data = await data_service.get_data_with_indicators(
            symbol=symbol,
            timeframe=data.get('timeframe', '1m'),
            market="crypto",
            indicators_config=indicators_config,
            days=data.get('days', 1)
        )
        
        await websocket.send_json({
            "type": "historical_data",
            "data": historical_data
        })
        
        # 5. الانتظار للاتصال المستمر
        while True:
            # مجرد الانتظار - التحديثات تأتي من indicators_manager
            await websocket.receive_text()  # أو يمكن استخدام ping/pong
            
    except WebSocketDisconnect:
        print(f"Client disconnected for {symbol}")
    except Exception as e:
        print(f"Error in WebSocket: {e}")





@router.websocket("/market-overview")
async def websocket_market_overview(websocket: WebSocket):
    await websocket.accept()
    print("📊 Market overview WS connected")

    # إرسال رسالة تأكيد الاتصال
    try:
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to market data stream",
            "timestamp": datetime.utcnow().isoformat()
        })
    except:
        print("❌ Failed to send connection confirmation")
        return

    try:
        async for payload in stream_all_market():
            try:
                # فلترة الرموز: فقط USDT/USDC
                filtered_data = [d for d in payload["data"] if d["symbol"].endswith(("USDT", "USDC"))]

                # إرسال البيانات المفلترة فقط
                await websocket.send_json({
                    "type": payload.get("type", "market_overview"),
                    "timestamp": payload.get("timestamp", datetime.utcnow().isoformat()),
                    "data": filtered_data,
                    "count": len(filtered_data)
                })

            except WebSocketDisconnect:
                print("👋 Client disconnected")
                break
            except Exception as e:
                print(f"Error sending data: {e}")
                break

            await asyncio.sleep(7)

    except Exception as e:
        print(f"❌ Market overview WS error: {e}")
    finally:
        print("🔌 Market overview WS closed")





@router.websocket("/signals")
async def ws_signals(websocket: WebSocket):
    await signals_websocket(websocket)



@router.websocket("/market-overviewalls")
async def websocket_market_overview(websocket: WebSocket):
    """
    WebSocket لتحديثات السوق الحية (نسخة كاملة للإنتاجية)
    - يرسل فقط الرموز التي تنتهي بـ USDT أو USDC
    - يشمل جميع الحقول المهمة: السعر، الافتتاح، الأعلى، الأدنى، التغير، الحجم، حجم العملة المقابلة، وعدد الصفقات
    """
    await websocket.accept()
    print("📊 Market overview WS connected")

    # إرسال رسالة تأكيد الاتصال
    try:
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to market data stream",
            "timestamp": datetime.utcnow().isoformat()
        })
    except:
        print("❌ Failed to send connection confirmation")
        return

    try:
        async for payload in stream_all_market():
            try:
                # فلترة الرموز: فقط USDT/USDC
                filtered_data = []
                for d in payload["data"]:
                    symbol = d.get("symbol", "")
                    if symbol.endswith(("USDT", "USDC")):
                        filtered_data.append({
                            "symbol": symbol,
                            "price": float(d.get("price", 0)),
                            "open24h": float(d.get("o", 0)),          # سعر الافتتاح خلال 24 ساعة
                            "high24h": float(d.get("h", 0)),          # أعلى سعر خلال 24 ساعة
                            "low24h": float(d.get("l", 0)),           # أقل سعر خلال 24 ساعة
                            "change24h": float(d.get("P", 0)),        # نسبة التغير خلال 24 ساعة
                            "volume": float(d.get("v", 0)),           # حجم التداول 24 ساعة
                            "quoteVolume": float(d.get("q", 0)),      # حجم التداول بالعملة المقابلة
                            "firstTradeId": d.get("F", 0),            # أول trade ID خلال 24 ساعة
                            "lastTradeId": d.get("L", 0),             # آخر trade ID خلال 24 ساعة
                            "numTrades": d.get("n", 0)                # عدد الصفقات خلال 24 ساعة
                        })

                # إرسال البيانات المفلترة
                if filtered_data:
                    await websocket.send_json({
                        "type": payload.get("type", "market_overview"),
                        "timestamp": payload.get("timestamp", datetime.utcnow().isoformat()),
                        "data": filtered_data,
                        "count": len(filtered_data)
                    })

            except WebSocketDisconnect:
                print("👋 Client disconnected")
                break
            except Exception as e:
                print(f"Error sending data: {e}")
                break

            # وقت الانتظار قبل التحديث التالي (يمكن تقليله إلى 3 ثوانٍ إذا أردت تحديث أسرع)
            await asyncio.sleep(7)

    except Exception as e:
        print(f"❌ Market overview WS error: {e}")
    finally:
        print("🔌 Market overview WS closed")




@router.websocket("/market-data_overview")
async def websocket_market_data(websocket: WebSocket):
    """
    WebSocket لتحديثات السوق الحية
    - يرسل فقط الرموز التي تنتهي بـ USDT أو USDC
    - يدعم الاشتراك في رموز محددة حتى 50 رمز
    """
    await websocket.accept()
    print("✅ Market data WebSocket connected")

    subscribed_symbols = []
    market = "crypto"

    # مهمة لتدفق بيانات Binance المباشر
    async def binance_stream_task():
        async for update in stream_all_market():
            if subscribed_symbols:
                filtered_data = [
                    d for d in update["data"]
                    if d["symbol"].endswith(("USDT", "USDC")) and (not subscribed_symbols or d["symbol"] in subscribed_symbols)
                ]
                if filtered_data:
                    await websocket.send_json({
                        "type": "price_update",
                        "payload": filtered_data,
                        "market": market,
                        "timestamp": datetime.utcnow().isoformat(),
                        "count": len(filtered_data)
                    })

    stream_task = asyncio.create_task(binance_stream_task())

    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "subscribe":
                    symbols = [s.upper() for s in message.get("symbols", [])]
                    market = message.get("market", "crypto")
                    # فقط رموز تنتهي بـ USDT أو USDC وحد أقصى 50
                    subscribed_symbols = [s for s in symbols if s.endswith(("USDT", "USDC"))][:5000]
                    print(f"📥 Subscribed to {len(subscribed_symbols)} symbols in {market}: {subscribed_symbols}")

                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})

            except json.JSONDecodeError:
                continue
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        print("❌ Market data WebSocket disconnected")
    finally:
        stream_task.cancel()
        try:
            await websocket.close()
        except:
            pass



# @router.websocket("/market-overview")
# async def websocket_market_overview(websocket: WebSocket):
#     await websocket.accept()
#     print("📊 Market overview WS connected")

#     try:
#         async for payload in stream_all_market():
#             try:
#                 await websocket.send_json(payload)
#             except WebSocketDisconnect:
#                 print("👋 Client disconnected أثناء الإرسال")
#                 break

#             await asyncio.sleep(7)

#     except Exception as e:
#         print("❌ Market overview WS error:", e)

#     finally:
#         print("🔌 Market overview WS closed")



@router.websocket("/stream/{symbol}/{timeframe}")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    symbol: str,
    timeframe: str,
    market: str = Query("crypto"),
    indicators: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None)
):
    """
    WebSocket لبث البيانات اللحظية - شبيه بـ TradingView
    
    - **symbol**: رمز السهم أو العملة
    - **timeframe**: الإطار الزمني (1m, 5m, 15m, 1h, 4h, 1d)
    - **market**: نوع السوق (crypto, stocks)
    - **indicators**: مؤشرات مخصصة (JSON string اختياري)
    - **strategy**: إستراتيجية مخصصة (JSON string اختياري)
    
    البيانات المرسلة:
    - السعر اللحظي (price)
    - قيم المؤشرات (indicator)
    - حالة الشروط (condition)
    - إشارات الدخول/الخروج (signal)
    - نقاط الدخول (entry_point)
    - حالة النظام (status)
    """
    # تهيئة الخدمات
    initialize_websocket_services()
    
    await manager.handle_stream_connection(
        websocket=websocket,
        symbol=symbol,
        timeframe=timeframe,
        market=market,
        indicators_config=indicators,
        strategy_config=strategy
    )

@router.websocket("/filter")
async def websocket_filter_stream(
    websocket: WebSocket,
    market: str = Query("crypto"),
    criteria: str = Query("{}")
):
    """
    WebSocket لبث الرموز المفلترة
    
    - **market**: نوع السوق
    - **criteria**: معايير الفلترة (JSON string)
    """
    initialize_websocket_services()
    
    try:
        await websocket.accept()
        
        # تحويل معايير الفلترة
        filter_criteria = json.loads(criteria) if criteria else {}
        
        while True:
            # الحصول على الرموز المفلترة
            filtered_symbols = await _filtering_engine.filter_symbols(
                market=market,
                criteria=filter_criteria
            )
            
            # إرسال النتيجة
            await websocket.send_json({
                "type": "filter_result",
                "timestamp": datetime.utcnow().isoformat(),
                "data": filtered_symbols,
                "market": market,
                "criteria": filter_criteria
            })
            
            # الانتظار قبل التحديث التالي
            await asyncio.sleep(60)  # تحديث كل دقيقة
            
    except WebSocketDisconnect:
        print("Filter WebSocket disconnected")
    except Exception as e:
        print(f"Error in filter WebSocket: {e}")
        await websocket.close(code=1011, reason=str(e))



@router.websocket("/filters")
async def websocket_filter_streams(
    websocket: WebSocket,
    market: str = Query("crypto"),
    criteria: str = Query("{}")
):
    """WebSocket لبث الرموز المفلترة مع الأسعار"""
    initialize_websocket_services()
    
    try:
        await websocket.accept()
        print(f"✅ Filter WebSocket connected for market: {market}")
        
        # تحويل معايير الفلترة
        filter_criteria = json.loads(criteria) if criteria else {}
        
        while True:
            # 1. الحصول على الرموز المفلترة
            filtered_symbols = await _filtering_engine.filter_symbols(
                market=market,
                criteria=filter_criteria
            )
            
            # 2. جلب الأسعار للرموز المفلترة
            price_updates = []
            if filtered_symbols:
                # استخدام BinanceProvider للحصول على الأسعار
                from app.providers.binance_provider import BinanceProvider
                provider = BinanceProvider()
                
                # جلب الأسعار للرموز (حد أقصى 50 رمز)
                symbols_to_fetch = filtered_symbols[:50]
                
                for symbol in symbols_to_fetch:
                    try:
                        price_data = await provider.get_live_price(symbol)
                        if price_data:
                            price_updates.append({
                                "symbol": symbol,
                                "current": price_data.get("price", 0),
                                "change24h": 0,  # يمكن إضافة حساب التغيير
                                "volume24h": 0,
                                "marketCap": 0,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                    except Exception as e:
                        print(f"Error fetching price for {symbol}: {e}")
            
            # 3. إرسال النتيجة الكاملة
            await websocket.send_json({
                "type": "filter_result",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "symbols": filtered_symbols,
                    "prices": price_updates,
                    "count": len(filtered_symbols)
                },
                "market": market,
                "criteria": filter_criteria
            })
            
            # الانتظار قبل التحديث التالي
            await asyncio.sleep(10)  # تحديث كل 10 ثواني
            
    except WebSocketDisconnect:
        print("Filter WebSocket disconnected")
    except Exception as e:
        print(f"Error in filter WebSocket: {e}")
        await websocket.close(code=1011, reason=str(e))
























@router.get("/stream/active")
async def get_active_streams():
    """الحصول على قائمة البثوث النشطة"""
    initialize_websocket_services()
    
    if manager.stream_handler:
        streams_info = manager.stream_handler.get_stream_info()
        return {
            "success": True,
            "data": streams_info,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    return {
        "success": False,
        "message": "Stream handler not initialized",
        "data": {}
    }






@router.websocket("/stream")
async def stream_endpoint(
    websocket: WebSocket,
    symbol: str,
    timeframe: str = "1m",
    market: str = "crypto",
    indicators: Optional[str] = None,
    strategy: Optional[str] = None,
):
    await manager.handle_stream_connection(
        websocket=websocket,
        symbol=symbol,
        timeframe=timeframe,
        market=market,
        indicators_config=indicators,
        strategy_config=strategy
    )






@router.post("/stream/start")
async def start_stream(
    symbol: str,
    timeframe: str,
    market: str = "crypto",
    indicators: Optional[str] = None,
    strategy: Optional[str] = None
):
    """بدء بث لحظي عبر REST API"""
    initialize_websocket_services()
    
    if not manager.stream_handler:
        return {
            "success": False,
            "message": "Stream handler not initialized"
        }
    
    try:
        indicators_config = json.loads(indicators) if indicators else []
        strategy_config = json.loads(strategy) if strategy else None
        
        stream_id = await manager.stream_handler.start_stream(
            symbol=symbol,
            timeframe=timeframe,
            market=market,
            indicators_config=indicators_config,
            strategy_config=strategy_config
        )
        
        return {
            "success": True,
            "message": f"Stream started for {symbol} ({timeframe})",
            "stream_id": stream_id,
            "info": manager.stream_handler.get_stream_info(stream_id)
        }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "message": f"Invalid JSON: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error starting stream: {str(e)}"
        }

@router.post("/stream/stop/{stream_id}")
async def stop_stream(stream_id: str):
    """إيقاف بث محدد"""
    initialize_websocket_services()
    
    if not manager.stream_handler:
        return {
            "success": False,
            "message": "Stream handler not initialized"
        }
    
    success = await manager.stream_handler.stop_stream(stream_id)
    
    return {
        "success": success,
        "message": f"Stream {stream_id} {'stopped' if success else 'not found'}",
        "stream_id": stream_id
    }