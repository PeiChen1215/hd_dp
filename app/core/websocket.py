"""
WebSocket 连接管理模块
支持多设备登录、离线消息队列、心跳检测
"""
import json
import asyncio
from typing import Dict, Set, Optional, List
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from collections import deque
import logging

from app.core.timezone import get_beijing_time

logger = logging.getLogger(__name__)


class ConnectionInfo:
    """单个连接的信息"""
    def __init__(self, websocket: WebSocket, user_id: str, device_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.device_id = device_id
        self.connected_at = get_beijing_time()
        self.last_ping_at = get_beijing_time()
        self.is_alive = True
    
    async def send(self, message: dict) -> bool:
        """发送消息，返回是否成功"""
        try:
            await self.websocket.send_json(message)
            return True
        except Exception:
            self.is_alive = False
            return False
    
    def update_ping(self):
        """更新心跳时间"""
        self.last_ping_at = get_beijing_time()


class WebSocketManager:
    """
    WebSocket 连接管理器
    
    管理功能：
    - 用户多设备连接管理
    - 消息广播和单播
    - 离线消息队列
    - 心跳检测
    """
    
    def __init__(self):
        # 用户ID -> {设备ID -> ConnectionInfo}
        self._connections: Dict[str, Dict[str, ConnectionInfo]] = {}
        # 离线消息队列：用户ID -> deque(消息列表)
        self._offline_messages: Dict[str, deque] = {}
        # 最大离线消息数
        self._max_offline_messages = 100
        # 心跳超时时间（秒）
        self._heartbeat_timeout = 60
        # 后台任务引用
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动管理器，开始后台任务"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("WebSocket manager started")
    
    async def stop(self):
        """停止管理器，清理所有连接"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        for user_id in list(self._connections.keys()):
            for device_id in list(self._connections[user_id].keys()):
                await self.disconnect(user_id, device_id)
        
        logger.info("WebSocket manager stopped")
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        device_id: str
    ) -> ConnectionInfo:
        """
        建立新连接
        
        Args:
            websocket: FastAPI WebSocket 对象
            user_id: 用户ID
            device_id: 设备标识
            
        Returns:
            ConnectionInfo 连接信息对象
        """
        await websocket.accept()
        
        # 如果该设备已有连接，先断开旧的
        if user_id in self._connections and device_id in self._connections[user_id]:
            old_conn = self._connections[user_id][device_id]
            await self._kickout(old_conn, "new_device_login")
        
        # 创建新连接
        conn_info = ConnectionInfo(websocket, user_id, device_id)
        
        if user_id not in self._connections:
            self._connections[user_id] = {}
        self._connections[user_id][device_id] = conn_info
        
        # 发送连接成功消息
        await conn_info.send({
            "type": "connected",
            "data": {
                "server_time": get_beijing_time().isoformat(),
                "device_id": device_id
            }
        })
        
        # 发送离线消息
        await self._send_offline_messages(conn_info)
        
        logger.info(f"User {user_id} connected with device {device_id}")
        return conn_info
    
    async def disconnect(self, user_id: str, device_id: str):
        """断开指定连接"""
        if user_id not in self._connections:
            return
        
        if device_id not in self._connections[user_id]:
            return
        
        conn = self._connections[user_id][device_id]
        try:
            await conn.websocket.close()
        except Exception:
            pass
        
        del self._connections[user_id][device_id]
        if not self._connections[user_id]:
            del self._connections[user_id]
        
        logger.info(f"User {user_id} device {device_id} disconnected")
    
    async def handle_message(self, user_id: str, device_id: str, message: dict):
        """处理客户端消息"""
        msg_type = message.get("type")
        
        if msg_type == "pong":
            # 心跳响应
            if user_id in self._connections and device_id in self._connections[user_id]:
                self._connections[user_id][device_id].update_ping()
        
        elif msg_type == "ack":
            # 消息确认（可扩展用于可靠投递）
            pass
    
    async def broadcast_to_user(
        self,
        user_id: str,
        message: dict,
        exclude_device: Optional[str] = None,
        require_ack: bool = False
    ) -> int:
        """
        向用户的所有设备广播消息
        
        Args:
            user_id: 目标用户ID
            message: 消息内容
            exclude_device: 排除的设备ID（发送者自身）
            require_ack: 是否需要确认
            
        Returns:
            成功发送的设备数
        """
        if user_id not in self._connections:
            # 用户离线，存入离线消息队列
            self._store_offline_message(user_id, message)
            return 0
        
        success_count = 0
        for device_id, conn in list(self._connections[user_id].items()):
            if device_id == exclude_device:
                continue
            
            if await conn.send(message):
                success_count += 1
            else:
                # 发送失败，存入离线消息
                self._store_offline_message(user_id, message)
        
        return success_count
    
    def _store_offline_message(self, user_id: str, message: dict):
        """存储离线消息"""
        if user_id not in self._offline_messages:
            self._offline_messages[user_id] = deque(maxlen=self._max_offline_messages)
        
        # 添加时间戳
        message_with_time = {
            **message,
            "timestamp": get_beijing_time().isoformat()
        }
        self._offline_messages[user_id].append(message_with_time)
    
    async def _send_offline_messages(self, conn: ConnectionInfo):
        """发送离线消息给刚连接的设备"""
        user_id = conn.user_id
        if user_id not in self._offline_messages:
            return
        
        messages = list(self._offline_messages[user_id])
        self._offline_messages[user_id].clear()
        
        for msg in messages:
            await conn.send(msg)
    
    async def _kickout(self, conn: ConnectionInfo, reason: str):
        """踢掉已有连接"""
        try:
            await conn.send({
                "type": "kickout",
                "data": {"reason": reason}
            })
            await conn.websocket.close()
        except Exception:
            pass
    
    async def _cleanup_loop(self):
        """后台清理任务：检测超时连接"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                await self._check_timeouts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def _check_timeouts(self):
        """检查并清理超时连接"""
        now = get_beijing_time()
        timeout_devices = []
        
        for user_id, devices in self._connections.items():
            for device_id, conn in devices.items():
                if (now - conn.last_ping_at).total_seconds() > self._heartbeat_timeout:
                    timeout_devices.append((user_id, device_id))
        
        for user_id, device_id in timeout_devices:
            logger.info(f"Connection timeout: {user_id}/{device_id}")
            await self.disconnect(user_id, device_id)


# 全局管理器实例
manager = WebSocketManager()


def notify_data_change(
    user_id: str,
    change_type: str,  # created, updated, deleted
    entity_type: str,  # event, memo
    data: dict,
    require_ack: bool = True
):
    """
    通知客户端数据变更（异步发送，不阻塞）
    
    Args:
        user_id: 用户ID
        change_type: 变更类型
        entity_type: 实体类型
        data: 变更数据
        require_ack: 是否需要确认
    """
    message = {
        "type": f"{entity_type}_{change_type}",
        "msg_id": str(uuid4()),
        "timestamp": get_beijing_time().isoformat(),
        "require_ack": require_ack,
        "data": data
    }
    
    # 异步发送，不等待
    asyncio.create_task(
        manager.broadcast_to_user(user_id, message)
    )


# 导入 uuid4 用于 notify_data_change
from uuid import uuid4
