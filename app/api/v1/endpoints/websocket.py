"""
WebSocket 实时通信接口
提供实时数据同步、消息推送功能
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from fastapi.exceptions import HTTPException
from jose import jwt, JWTError
from typing import Optional
import json
import logging

from app.core.config import settings
from app.core.websocket import manager, ConnectionInfo

router = APIRouter()
logger = logging.getLogger(__name__)


async def verify_ws_token(token: str) -> Optional[dict]:
    """验证 WebSocket 连接的 JWT Token"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return {"user_id": user_id, "payload": payload}
    except JWTError:
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Token"),
    device_id: Optional[str] = Query(None, description="设备标识（可选，如不提供则自动生成）")
):
    """
    WebSocket 实时通信连接
    
    **连接方式:**
    ```
    wss://api.example.com/api/v1/ws?token=eyJhbG...&device_id=android_xxx
    ```
    
    **消息协议:**
    
    1. **连接成功** (服务端 -> 客户端)
    ```json
    {
      "type": "connected",
      "data": {
        "server_time": "2026-03-08T12:00:00Z",
        "device_id": "android_xxx"
      }
    }
    ```
    
    2. **心跳 ping** (服务端 -> 客户端)
    ```json
    {"type": "ping", "data": {"timestamp": "2026-03-08T12:00:30Z"}}
    ```
    
    3. **心跳 pong** (客户端 -> 服务端)
    ```json
    {"type": "pong", "data": {"timestamp": "2026-03-08T12:00:30Z"}}
    ```
    
    4. **数据变更通知** (服务端 -> 客户端)
    ```json
    {
      "type": "event_created",
      "data": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "新项目会议",
        "start_time": "2026-03-09T09:00:00Z",
        ...
      },
      "msg_id": "...",
      "timestamp": "2026-03-08T12:05:00Z",
      "require_ack": true
    }
    ```
    
    5. **消息确认** (客户端 -> 服务端)
    ```json
    {"type": "ack", "data": {"msg_id": "..."}}
    ```
    
    6. **被踢下线** (服务端 -> 客户端)
    ```json
    {
      "type": "kickout",
      "data": {
        "reason": "new_device_login",
        "device_id": "android_xxx"
      }
    }
    ```
    
    **错误码:**
    - `4001`: Token 无效或过期
    - `4002`: 用户被禁用
    - `4003`: 同设备登录被挤下线
    """
    # 先接受连接（WebSocket 握手）
    await websocket.accept()
    
    # 验证 token
    auth_info = await verify_ws_token(token)
    if not auth_info:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    
    user_id = auth_info["user_id"]
    
    # 生成 device_id（如果客户端未提供）
    if not device_id:
        import uuid
        device_id = f"device_{str(uuid.uuid4())[:8]}"
    
    # 建立连接
    conn: Optional[ConnectionInfo] = None
    try:
        conn = await manager.connect(websocket, user_id, device_id)
        
        # 消息处理循环
        while True:
            try:
                # 接收客户端消息
                raw_data = await websocket.receive_text()
                message = json.loads(raw_data)
                
                msg_type = message.get("type")
                msg_data = message.get("data", {})
                
                if msg_type == "pong":
                    # 客户端心跳响应
                    conn.update_ping()
                    
                elif msg_type == "ack":
                    # 客户端确认收到消息
                    ack_msg_id = msg_data.get("msg_id")
                    logger.debug(f"Received ack from {user_id}/{device_id}: {ack_msg_id}")
                    # 可以在这里实现消息确认跟踪
                    
                elif msg_type == "subscribe":
                    # 客户端订阅特定类型的事件
                    # 预留：可以按类型过滤推送
                    await conn.send({
                        "type": "subscribed",
                        "data": {"types": msg_data.get("types", [])}
                    })
                    
                else:
                    # 未知消息类型
                    await conn.send({
                        "type": "error",
                        "data": {"message": f"Unknown message type: {msg_type}"}
                    })
                    
            except json.JSONDecodeError:
                await conn.send({
                    "type": "error",
                    "data": {"message": "Invalid JSON format"}
                })
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling message from {user_id}: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {user_id}/{device_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {user_id}/{device_id}: {e}")
    finally:
        if conn:
            await manager.disconnect(user_id, device_id)


@router.get("/status")
async def get_websocket_status():
    """获取 WebSocket 服务器状态（管理接口）"""
    return {
        "online_users": len(manager._connections),
        "total_connections": sum(
            len(devices) for devices in manager._connections.values()
        ),
        "offline_queues": len(manager._offline_queues),
        "offline_total_messages": sum(
            len(q) for q in manager._offline_queues.values()
        )
    }


@router.post("/broadcast")
async def broadcast_message(message: dict, user_id: Optional[str] = None):
    """
    测试接口：向用户发送广播消息
    
    如果指定 user_id，只发给该用户
    否则广播给所有在线用户
    """
    if user_id:
        success = await manager.send_to_user(user_id, message)
        return {"sent": success, "user_id": user_id}
    else:
        # 广播给所有用户（谨慎使用）
        count = 0
        for uid in list(manager._connections.keys()):
            success = await manager.send_to_user(uid, message)
            if success:
                count += 1
        return {"sent_to": count, "total_online": len(manager._connections)}
