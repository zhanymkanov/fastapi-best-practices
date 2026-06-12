from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.database import close_db, get_database, init_db, is_db_available
from app.plugins.registry import plugin_registry

logger = logging.getLogger(__name__)

# ── Redis 健康检查客户端（懒加载） ──────────────────────────────────
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


# ── Lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：初始化数据库 + 注册 MCP 工具
    await init_db()

    from app.mcp.registry import mcp_registry
    mcp_registry.auto_discover()
    logger.info("MCP 工具已注册: %d 个工具, 分类: %s",
                len(mcp_registry), mcp_registry.categories())

    if not is_db_available():
        logger.warning(
            "⚠️  MongoDB 未连接，运行在 Demo 模式。"
            "Agent / MCP / RAG 接口可用，CRUD 接口将返回 Demo 数据。"
        )

    yield

    # 关闭时：断开数据库连接
    await close_db()


# ── Application ────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# ① 跨域中间件（允许前端跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ② 挂载所有业务路由
app.include_router(api_router, prefix="/api")

# ③ 前端静态页面挂载
app.mount("/static", StaticFiles(directory="app/static", html=True), name="static")


@app.get("/")
async def root():
    """重定向到前端页面"""
    return RedirectResponse(url="/static/index.html")

# ── 加载插件 ──────────────────────────────────────────────────────
# 显式注册内置插件
from app.plugins.sentry_plugin import register_plugin as _sentry
from app.plugins.celery_plugin import register_plugin as _celery

plugin_registry.register("sentry", _sentry)
plugin_registry.register("celery", _celery)

# 从 entry_points 发现外部插件 (group="cyberlife")
plugin_registry.discover_entry_points("cyberlife")

# 激活所有插件（注册路由、中间件等）
plugin_registry.activate_all(app)


# ── Health Check ───────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """基础存活检查（Liveness Probe）"""
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/health/ready")
async def health_ready():
    """就绪检查（Readiness Probe）：验证 MongoDB + Redis 连通性"""
    checks = {}

    # MongoDB
    if is_db_available():
        checks["mongodb"] = "ok"
    else:
        checks["mongodb"] = "unavailable (demo mode)"

    # Redis（Demo 模式下不强制要求）
    try:
        r = _get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable (demo mode)"

    # Demo 模式下 MongoDB 不可用是正常的，仍返回 200
    all_critical_ok = is_db_available()
    status_code = 200 if all_critical_ok else 200  # Demo 模式也返回 200
    return JSONResponse(
        content={
            "status": "ready" if all_critical_ok else "demo",
            "checks": checks,
            "mode": "demo" if not all_critical_ok else "full",
        },
        status_code=status_code,
    )


# ── 全局异常处理器 ────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic 请求校验失败 → 结构化错误"""
    errors = []
    for err in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        })
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "请求参数校验失败",
            "detail": errors,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常 → 统一 JSON 格式"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": exc.detail,
            "status_code": exc.status_code,
        },
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """兜底异常处理器（生产环境不泄露 traceback）"""
    detail = str(exc) if settings.DEPLOY_MODE == "dev" else "服务器内部错误"
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": detail,
        },
    )
