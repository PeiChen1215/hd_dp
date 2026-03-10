from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1 import api_router
from app.core.websocket import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    - 启动时：初始化 WebSocket 管理器
    - 关闭时：清理所有 WebSocket 连接
    """
    # 启动
    await manager.start()
    yield
    # 关闭
    await manager.stop()


app = FastAPI(
    title="ChronoSync API",
    description="个人智能助手 - 支持离线优先和实时同步",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health():
    """健康检查接口"""
    return {
        "status": "ok",
        "websocket": {
            "online_users": len(manager._connections),
            "total_connections": sum(
                len(devices) for devices in manager._connections.values()
            )
        }
    }


app.include_router(api_router, prefix="/api/v1")
