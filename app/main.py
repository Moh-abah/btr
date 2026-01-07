import logging
import traceback
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import sys
from app.config import settings
from app.database import close_db, init_db
from app.routers import api
from app.services.signals.engine import SignalEngine
from app.services.strategy.full_strategy import build_full_strategy
from app.services.indicator_state_service import IndicatorStateService
from app.core.managers import chart_manager, live_stream_manager


strategy_config = build_full_strategy()
state_service = IndicatorStateService()
print(">>> main.py loaded")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION
)


# إعداد Logging مفصل
# logging.basicConfig(
#     level=logging.DEBUG,  # غير إلى DEBUG لرؤية المزيد
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(sys.stdout),
#         logging.FileHandler('app.log', encoding='utf-8', mode='a')
#     ]
# )
logger = logging.getLogger(__name__)
from app.routers import stock_analysis  # أضف هذا

# استيراد الرواتر
try:
    from app.routers.api import router as api_router
    # logger.info(">>> Imported api router successfully")
except ImportError as e:
    # logger.error(f"Failed to import api router: {e}")
    api_router = None

try:
    from app.routers.core import router as core_router
    # logger.info(">>> Imported core router successfully")
except ImportError as e:
    logger.error(f"Failed to import core router: {e}")
    core_router = None

try:
    from app.routers.indicators import router as indicators_router
    from app.routers.strategies import router as strategies_router
    from app.routers.strategies1 import router as strategies_router1
    from app.routers.websocket import router as websocket_router
    from app.routers.filtering import router as filtering_router
    from app.routers.backtest import router as backtest_router
  
    from app.routers.users import router as users_router
    from app.routers.settings import router as settings_router
    from app.routers.market_data import router as market_data_router
    logger.info(">>> Imported all routers successfully")
except ImportError as e:
    logger.error(f"Failed to import routers: {e}")
    indicators_router = strategies_router   = websocket_router = None
    filtering_router = backtest_router  = users_router = settings_router = market_data_router = None

try:
    from app.routers.backtest1 import router as backtest_router1
except ImportError as e:
    logger.error(f"Failed to import backtest_router1: {e}")
    backtest_router1 = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    # بدء التشغيل
    # logger.info("🚀 Starting application...")
    try:
   
        await init_db()


        # logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        logger.error(traceback.format_exc())
    
    yield
    
    # إغلاق التشغيل
    # logger.info("🔌 Shutting down application...")
    try:
        await close_db()
        # logger.info("✅ Database connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing database: {e}")


  

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Middleware لتسجيل كل الطلبات
@app.middleware("http")
async def log_request_response(request: Request, call_next):
    # logger.debug(f"➡️  REQUEST: {request.method} {request.url}")
    # logger.debug(f"   Headers: {dict(request.headers)}")
    # logger.debug(f"   Query params: {dict(request.query_params)}")
    
    start_time = datetime.now()
    
    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # logger.debug(f"⬅️  RESPONSE: {response.status_code} ({process_time:.2f}ms)")
        # logger.debug(f"   Headers: {dict(response.headers)}")
        
        return response
        
    except Exception as e:
        process_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"💥 ERROR in {request.method} {request.url}: {str(e)}")
        logger.error(f"   Traceback:\n{traceback.format_exc()}")
        logger.error(f"   Time: {process_time:.2f}ms")
        
        # إرجاع خطأ 500 مع تفاصيل
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal Server Error",
                "error": str(e),
                "path": str(request.url.path),
                "timestamp": datetime.utcnow().isoformat()
            }
        )



@app.middleware("http")
async def simple_debug_middleware(request: Request, call_next):
    # اطبع مباشرة إلى stdout
    # print(f"\n🔴 [SIMPLE DEBUG] REQUEST: {request.method} {request.url}", file=sys.stderr)
    # print(f"   Path: {request.url.path}", file=sys.stderr)
    # print(f"   Query: {dict(request.query_params)}", file=sys.stderr)
    sys.stderr.flush()
    
    try:
        response = await call_next(request)
        # print(f"🟢 [SIMPLE DEBUG] RESPONSE: {response.status_code}", file=sys.stderr)
        sys.stderr.flush()
        return response
    except Exception as e:
        # print(f"🔴 [SIMPLE DEBUG] ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تسجيل الرواتر
# logger.info("📝 Registering routers...")

app.include_router(stock_analysis.router, prefix="/api/v1/stocks", tags=["stocks-analysis"])
# تأكد من أن الرواتر موجودة قبل تسجيلها
if api_router:
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    # logger.info(f"✅ api_router mounted at {settings.API_V1_PREFIX}")

if core_router:
    # سجلها مرة واحدة فقط - اختر إما هذا أو api_router
    app.include_router(core_router, prefix=settings.API_V1_PREFIX)
    # logger.info(f"⚠️  core_router available but not mounted to avoid duplication")

# تسجيل باقي الرواتر
if market_data_router:
    app.include_router(market_data_router, prefix=f"{settings.API_V1_PREFIX}/market")
    # logger.info(f"✅ market_data_router mounted")

if backtest_router:
    app.include_router(backtest_router, prefix=f"{settings.API_V1_PREFIX}/backtest")
    # logger.info(f"✅ backtest_router mounted")

if backtest_router1:
    app.include_router(backtest_router1, prefix=f"{settings.API_V1_PREFIX}/backtest1")
    # logger.info(f"✅ backtest_router mounted")


if indicators_router:
    app.include_router(indicators_router, prefix=f"{settings.API_V1_PREFIX}/indicators")
    # logger.info(f"✅ indicators_router mounted")

if strategies_router:
    app.include_router(strategies_router, prefix=f"{settings.API_V1_PREFIX}/strategies")
    # logger.info(f"✅ strategies_router mounted")

if strategies_router1:
    app.include_router(strategies_router1, prefix=f"{settings.API_V1_PREFIX}/strategies1")
    # logger.info(f"✅ strategies_router mounted")


if websocket_router:
    app.include_router(websocket_router, prefix="/ws")
    # logger.info(f"✅ websocket_router mounted")

if filtering_router:
    app.include_router(filtering_router, prefix=f"{settings.API_V1_PREFIX}/filtering")
    # logger.info(f"✅ filtering_router mounted")

if users_router:
    app.include_router(users_router, prefix=f"{settings.API_V1_PREFIX}/users")
    # logger.info(f"✅ users_router mounted")

if settings_router:
    app.include_router(settings_router, prefix=f"{settings.API_V1_PREFIX}/settings")
    # logger.info(f"✅ settings_router mounted")

# logger.info("✅ All routers mounted successfully")

@app.get("/")
async def root():
    # logger.info("🌐 Root endpoint accessed")
    return {
        "message": "Trading Backend API",
        "version": settings.VERSION,
        "docs": "/docs",
        "websocket": "/ws"
    }

@app.get("/health")
async def health_check():
    logger.info("🩺 Health check endpoint accessed")
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# Endpoint لفحص جميع المسارات المسجلة
@app.get("/debug/routes")
async def debug_routes():
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, 'methods') else []
        })
    return {"routes": routes}













# import logging
# from datetime import datetime
# from fastapi import FastAPI, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from contextlib import asynccontextmanager
# import traceback

# from app.config import settings
# from app.database import close_db, init_db
# from app.routers import api, market_data, backtest

# print(">>> main.py loaded")

# from app.routers.api import router as core_router
# print(">>> imported api router successfully")

# from app.websocket.manager import WebSocketManager
# from app.routers.indicators import router as indicators_router
# from app.routers.strategies import router as strategies_router
# from app.routers.websocket import router as websocket_router
# from app.routers.filtering import router as filtering_router
# from app.routers.backtest import router as backtest_router
# from app.routers.users import router as users_router
# from app.routers.settings import router as settings_router
# from app.routers.core import router as core_router
# print(">>> imported core router successfully")

# # إعداد Logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(),  # للطباعة في الكونسول
#         logging.FileHandler('app.log', encoding='utf-8')  # حفظ في ملف
#     ]
# )
# logger = logging.getLogger(__name__)

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # بدء التشغيل
#     logger.info("🚀 Starting application...")
#     await init_db()
#     logger.info("✅ Database initialized")
    
#     yield
    
#     # إغلاق التشغيل
#     logger.info("🔌 Shutting down application...")
#     await close_db()
#     logger.info("✅ Database connection closed")

# app = FastAPI(
#     title=settings.PROJECT_NAME,
#     version=settings.VERSION,
#     lifespan=lifespan
# )

# # CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Middleware لتسجيل الطلبات
# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     start_time = datetime.now()
    
#     # تسجيل الطلب الوارد
#     logger.info(f"📥 Incoming request: {request.method} {request.url.path}")
#     logger.info(f"   Query params: {dict(request.query_params)}")
#     if request.client:
#         logger.info(f"   Client: {request.client.host}:{request.client.port}")
    
#     try:
#         response = await call_next(request)
#         process_time = (datetime.now() - start_time).total_seconds() * 1000
        
#         # تسجيل الرد
#         logger.info(f"📤 Response: {response.status_code} - {process_time:.2f}ms")
        
#         return response
#     except Exception as e:
#         # تسجيل الأخطاء
#         process_time = (datetime.now() - start_time).total_seconds() * 1000
#         logger.error(f"❌ Error in {request.method} {request.url.path}: {str(e)}")
#         logger.error(f"   Traceback: {traceback.format_exc()}")
#         logger.error(f"   Time: {process_time:.2f}ms")
        
#         # يمكنك إعادة الرد المناسب أو رفع الاستثناء
#         return JSONResponse(
#             status_code=500,
#             content={
#                 "detail": "Internal Server Error",
#                 "error": str(e),
#                 "path": request.url.path
#             }
#         )

# # Exception handler للأخطاء العامة
# @app.exception_handler(Exception)
# async def global_exception_handler(request: Request, exc: Exception):
#     logger.error(f"🔥 Unhandled exception: {str(exc)}")
#     logger.error(f"   Path: {request.url.path}")
#     logger.error(f"   Method: {request.method}")
#     logger.error(f"   Traceback:\n{traceback.format_exc()}")
    
#     return JSONResponse(
#         status_code=500,
#         content={
#             "detail": "Internal Server Error",
#             "error": str(exc),
#             "path": request.url.path
#         }
#     )

# # تسجيل الرواتر
# logger.info("📝 Registering routers...")

# app.include_router(api.router, prefix=settings.API_V1_PREFIX)
# app.include_router(core_router, prefix="/api/v1")
# logger.info("✅ core_router mounted at /api/v1")

# app.include_router(market_data.router, prefix=f"{settings.API_V1_PREFIX}/market")
# app.include_router(backtest.router, prefix=f"{settings.API_V1_PREFIX}/backtest")
# app.include_router(
#     indicators_router, 
#     prefix=f"{settings.API_V1_PREFIX}/indicators"
# )
# app.include_router(
#     strategies_router, 
#     prefix=f"{settings.API_V1_PREFIX}/strategies"
# )
# app.include_router(websocket_router, prefix="/ws")
# app.include_router(filtering_router, prefix=f"{settings.API_V1_PREFIX}/filtering")
# app.include_router(backtest_router, prefix=f"{settings.API_V1_PREFIX}/backtest")
# app.include_router(users_router, prefix=f"{settings.API_V1_PREFIX}/users")
# app.include_router(settings_router, prefix=f"{settings.API_V1_PREFIX}/settings")
# app.include_router(core_router, prefix=f"{settings.API_V1_PREFIX}/ss")

# logger.info("✅ All routers mounted successfully")

# @app.get("/")
# async def root():
#     logger.info("🌐 Root endpoint accessed")
#     return {
#         "message": "Trading Backend API",
#         "version": settings.VERSION,
#         "docs": "/docs",
#         "websocket": "/ws"
#     }

# @app.get("/health")
# async def health_check():
#     logger.info("🩺 Health check endpoint accessed")
#     return {"status": "healthy", "timestamp": datetime.utcnow()}










# import logging
# import traceback
# from datetime import datetime
# from fastapi import FastAPI, Request, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from contextlib import asynccontextmanager
# import sys

# from app.config import settings
# from app.database import close_db, init_db
# from app.routers import api

# print(">>> main.py loaded")


# app = FastAPI(
#     title=settings.PROJECT_NAME,
#     version=settings.VERSION
# )


# # إعداد Logging مفصل
# logging.basicConfig(
#     level=logging.DEBUG,  # غير إلى DEBUG لرؤية المزيد
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(sys.stdout),
#         logging.FileHandler('app.log', encoding='utf-8', mode='a')
#     ]
# )
# logger = logging.getLogger(__name__)

# # استيراد الرواتر
# try:
#     from app.routers.api import router as api_router
#     logger.info(">>> Imported api router successfully")
# except ImportError as e:
#     logger.error(f"Failed to import api router: {e}")
#     api_router = None

# try:
#     from app.routers.core import router as core_router
#     logger.info(">>> Imported core router successfully")
# except ImportError as e:
#     logger.error(f"Failed to import core router: {e}")
#     core_router = None

# try:
#     from app.routers.indicators import router as indicators_router
#     from app.routers.strategies import router as strategies_router
#     from app.routers.websocket import router as websocket_router
#     from app.routers.filtering import router as filtering_router
#     from app.routers.backtest import router as backtest_router
#     from app.routers.users import router as users_router
#     from app.routers.settings import router as settings_router
#     from app.routers.market_data import router as market_data_router
#     logger.info(">>> Imported all routers successfully")
# except ImportError as e:
#     logger.error(f"Failed to import routers: {e}")
#     indicators_router = strategies_router = websocket_router = None
#     filtering_router = backtest_router = users_router = settings_router = market_data_router = None

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # بدء التشغيل
#     logger.info("🚀 Starting application...")
#     try:
#         await init_db()
#         logger.info("✅ Database initialized")
#     except Exception as e:
#         logger.error(f"❌ Failed to initialize database: {e}")
#         logger.error(traceback.format_exc())
    
#     yield
    
#     # إغلاق التشغيل
#     logger.info("🔌 Shutting down application...")
#     try:
#         await close_db()
#         logger.info("✅ Database connection closed")
#     except Exception as e:
#         logger.error(f"❌ Error closing database: {e}")

# app = FastAPI(
#     title=settings.PROJECT_NAME,
#     version=settings.VERSION,
#     lifespan=lifespan
# )

# # Middleware لتسجيل كل الطلبات
# @app.middleware("http")
# async def log_request_response(request: Request, call_next):
#     logger.debug(f"➡️  REQUEST: {request.method} {request.url}")
#     logger.debug(f"   Headers: {dict(request.headers)}")
#     logger.debug(f"   Query params: {dict(request.query_params)}")
    
#     start_time = datetime.now()
    
#     try:
#         response = await call_next(request)
#         process_time = (datetime.now() - start_time).total_seconds() * 1000
        
#         logger.debug(f"⬅️  RESPONSE: {response.status_code} ({process_time:.2f}ms)")
#         logger.debug(f"   Headers: {dict(response.headers)}")
        
#         return response
        
#     except Exception as e:
#         process_time = (datetime.now() - start_time).total_seconds() * 1000
#         logger.error(f"💥 ERROR in {request.method} {request.url}: {str(e)}")
#         logger.error(f"   Traceback:\n{traceback.format_exc()}")
#         logger.error(f"   Time: {process_time:.2f}ms")
        
#         # إرجاع خطأ 500 مع تفاصيل
#         return JSONResponse(
#             status_code=500,
#             content={
#                 "detail": "Internal Server Error",
#                 "error": str(e),
#                 "path": str(request.url.path),
#                 "timestamp": datetime.utcnow().isoformat()
#             }
#         )




# app.include_router(api.router, prefix="/api/v11", tags=["core"])
# @app.middleware("http")
# async def simple_debug_middleware(request: Request, call_next):
#     # اطبع مباشرة إلى stdout
#     print(f"\n🔴 [SIMPLE DEBUG] REQUEST: {request.method} {request.url}", file=sys.stderr)
#     print(f"   Path: {request.url.path}", file=sys.stderr)
#     print(f"   Query: {dict(request.query_params)}", file=sys.stderr)
#     sys.stderr.flush()
    
#     try:
#         response = await call_next(request)
#         print(f"🟢 [SIMPLE DEBUG] RESPONSE: {response.status_code}", file=sys.stderr)
#         sys.stderr.flush()
#         return response
#     except Exception as e:
#         print(f"🔴 [SIMPLE DEBUG] ERROR: {e}", file=sys.stderr)
#         import traceback
#         traceback.print_exc(file=sys.stderr)
#         sys.stderr.flush()
#         raise

# # CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # تسجيل الرواتر
# logger.info("📝 Registering routers...")

# # تأكد من أن الرواتر موجودة قبل تسجيلها
# if api_router:
#     app.include_router(api_router, prefix=settings.API_V1_PREFIX)
#     logger.info(f"✅ api_router mounted at {settings.API_V1_PREFIX}")

# if core_router:
#     # سجلها مرة واحدة فقط - اختر إما هذا أو api_router
#     # app.include_router(core_router, prefix=settings.API_V1_PREFIX)
#     logger.info(f"⚠️  core_router available but not mounted to avoid duplication")

# # تسجيل باقي الرواتر
# if market_data_router:
#     app.include_router(market_data_router, prefix=f"{settings.API_V1_PREFIX}/market")
#     logger.info(f"✅ market_data_router mounted")

# if backtest_router:
#     app.include_router(backtest_router, prefix=f"{settings.API_V1_PREFIX}/backtest")
#     logger.info(f"✅ backtest_router mounted")

# if indicators_router:
#     app.include_router(indicators_router, prefix=f"{settings.API_V1_PREFIX}/indicators")
#     logger.info(f"✅ indicators_router mounted")

# if strategies_router:
#     app.include_router(strategies_router, prefix=f"{settings.API_V1_PREFIX}/strategies")
#     logger.info(f"✅ strategies_router mounted")

# if websocket_router:
#     app.include_router(websocket_router, prefix="/ws")
#     logger.info(f"✅ websocket_router mounted")

# if filtering_router:
#     app.include_router(filtering_router, prefix=f"{settings.API_V1_PREFIX}/filtering")
#     logger.info(f"✅ filtering_router mounted")

# if users_router:
#     app.include_router(users_router, prefix=f"{settings.API_V1_PREFIX}/users")
#     logger.info(f"✅ users_router mounted")

# if settings_router:
#     app.include_router(settings_router, prefix=f"{settings.API_V1_PREFIX}/settings")
#     logger.info(f"✅ settings_router mounted")

# logger.info("✅ All routers mounted successfully")

# @app.get("/")
# async def root():
#     logger.info("🌐 Root endpoint accessed")
#     return {
#         "message": "Trading Backend API",
#         "version": settings.VERSION,
#         "docs": "/docs",
#         "websocket": "/ws"
#     }

# @app.get("/health")
# async def health_check():
#     logger.info("🩺 Health check endpoint accessed")
#     return {"status": "healthy", "timestamp": datetime.utcnow()}

# # Endpoint لفحص جميع المسارات المسجلة
# @app.get("/debug/routes")
# async def debug_routes():
#     routes = []
#     for route in app.routes:
#         routes.append({
#             "path": route.path,
#             "name": route.name,
#             "methods": list(route.methods) if hasattr(route, 'methods') else []
#         })
#     return {"routes": routes}