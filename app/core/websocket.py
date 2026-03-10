"""
WebSocket 连接管理模块
支持多设备登录、离线消息队列、心跳检测
"""
import json
import asyncio
from typing import Dict, Set, Optional, List
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
from collections import deque
import logging

logger = logging.getLogger(__name__)


class ConnectionInfo:
    """单个连接的信息"""
    def __init__(self, websocket: WebSocket, user_id: str, device_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.device_id = device_id
        self.connected_at = datetime.now(timezone.utc)
        self.last_ping_at = datetime.now(timezone.utc)
        self.is_alive = True
    
    async def send(self, message: dict) -> bool:
        """发送消息，返回是否成功"""
        try:
            await self.websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to {self.user_id}/{self.device_id}: {e}")
            self.is_alive = False
            return False
    
    def update_ping(self):
        """更新心跳时间"""
        self.last_ping_at = datetime.now(timezone.utc)
        self.is_alive = True


class ConnectionManager:
    """
    WebSocket 连接管理器
    
    功能：
    1. 按 user_id 管理多个连接（支持多设备同时在线）
    2. 离线消息队列（用户不在线时缓存消息）
    3. 心跳检测（自动清理死连接）
    4. 消息确认机制（确保重要消息送达）
    """
    
    def __init__(
        self,
        offline_queue_size: int = 100,
        heartbeat_interval: int = 30,
        heartbeat_timeout: int = 60
    ):
        # user_id -> {device_id -> ConnectionInfo}
        self._connections: Dict[str, Dict[str, ConnectionInfo]] = {}
        
        # 离线消息队列: user_id -> deque[(timestamp, message)]
        self._offline_queues: Dict[str, deque] = {}
        self._offline_queue_size = offline_queue_size
        
        # 心跳配置
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_timeout = heartbeat_timeout
        
        # 启动心跳检测任务
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动管理器（在应用启动时调用）"""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_checker())
            logger.info("WebSocket heartbeat checker started")
    
    async def stop(self):
        """停止管理器（在应用关闭时调用）"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        close_tasks = []
        for user_conns in self._connections.values():
            for conn in user_conns.values():
                close_tasks.append(
                    conn.websocket.close(code=1001, reason="Server shutdown")
                )
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
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
            user_id: 用户UUID字符串
            device_id: 设备标识（由客户端提供，如 "android_xxx"）
        """
        # 注意：websocket.accept() 已在 endpoint 中调用
        
        # 断开同设备的旧连接
        await self.disconnect_device(user_id, device_id)
        
        # 创建新连接
        conn_info = ConnectionInfo(websocket, user_id, device_id)
        
        if user_id not in self._connections:
            self._connections[user_id] = {}
        self._connections[user_id][device_id] = conn_info
        
        logger.info(f"WebSocket connected: {user_id}/{device_id}")
        
        # 发送连接成功确认
        await conn_info.send({
            "type": "connected",
            "data": {
                "server_time": datetime.now(timezone.utc).isoformat(),
                "device_id": device_id
            }
        })
        
        # 发送离线期间的消息
        await self._send_offline_messages(user_id, conn_info)
        
        return conn_info
    
    async def disconnect(self, user_id: str, device_id: str):
        """断开特定设备的连接"""
        if user_id in self._connections:
            if device_id in self._connections[user_id]:
                conn = self._connections[user_id][device_id]
                try:
                    await conn.websocket.close()
                except:
                    pass
                del self._connections[user_id][device_id]
                logger.info(f"WebSocket disconnected: {user_id}/{device_id}")
                
                # 清理空用户
                if not self._connections[user_id]:
                    del self._connections[user_id]
    
    async def disconnect_device(self, user_id: str, device_id: str):
        """断开同设备的旧连接（挤下线）"""
        if user_id in self._connections and device_id in self._connections[user_id]:
            old_conn = self._connections[user_id][device_id]
            try:
                await old_conn.websocket.send_json({
                    "type": "kickout",
                    "data": {"reason": "new_device_login", "device_id": device_id}
                })
                await asyncio.sleep(0.1)  # 给客户端一点时间处理
                await old_conn.websocket.close(code=4001, reason="New device login")
            except:
                pass
            del self._connections[user_id][device_id]
    
    async def send_to_user(
        self, 
        user_id: str, 
        message: dict,
        require_ack: bool = False,
        msg_id: Optional[str] = None
    ) -> bool:
        """
        向用户的所有设备发送消息
        
        Args:
            user_id: 用户ID
            message: 要发送的消息（会被添加 type/timestamp/msg_id）
            require_ack: 是否需要客户端确认
            msg_id: 消息ID（自动生成）
        
        Returns:
            是否至少有一个设备在线并发送成功
        """
        if msg_id is None:
            msg_id = self._generate_msg_id()
        
        full_message = {
            **message,
            "msg_id": msg_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "require_ack": require_ack
        }
        
        user_online = False
        
        if user_id in self._connections:
            dead_devices = []
            for device_id, conn in self._connections[user_id].items():
                if conn.is_alive:
                    success = await conn.send(full_message)
                    if success:
                        user_online = True
                    else:
                        dead_devices.append(device_id)
                else:
                    dead_devices.append(device_id)
            
            # 清理死连接
            for device_id in dead_devices:
                del self._connections[user_id][device_id]
            
            if not self._connections[user_id]:
                del self._connections[user_id]
        
        # 如果用户不在线，保存到离线队列
        if not user_online:
            self._save_offline_message(user_id, full_message)
        
        return user_online
    
    async def broadcast_to_others(
        self, 
        user_id: str, 
        exclude_device_id: str,
        message: dict
    ):
        """广播给用户的其他设备（多设备同步场景）"""
        if user_id in self._connections:
            for device_id, conn in self._connections[user_id].items():
                if device_id != exclude_device_id and conn.is_alive:
                    await conn.send(message)
    
    def get_user_connections(self, user_id: str) -> int:
        """获取用户的在线设备数"""
        return len(self._connections.get(user_id, {}))
    
    def is_user_online(self, user_id: str) -> bool:
        """检查用户是否在线"""
        return user_id in self._connections and len(self._connections[user_id]) > 0
    
    async def _send_offline_messages(self, user_id: str, conn: ConnectionInfo):
        """发送离线期间的消息"""
        if user_id not in self._offline_queues:
            return
        
        queue = self._offline_queues[user_id]
        messages_to_send = list(queue)
        queue.clear()
        
        for msg in messages_to_send:
            success = await conn.send(msg)
            if not success:
                # 发送失败，放回队列
                queue.append(msg)
                break
    
    def _save_offline_message(self, user_id: str, message: dict):
        """保存离线消息"""
        if user_id not in self._offline_queues:
            self._offline_queues[user_id] = deque(maxlen=self._offline_queue_size)
        
        self._offline_queues[user_id].append(message)
        logger.debug(f"Saved offline message for {user_id}, queue size: {len(self._offline_queues[user_id])}")
    
    async def _heartbeat_checker(self):
        """心跳检测协程"""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                
                now = datetime.now(timezone.utc)
                dead_connections = []
                
                for user_id, devices in list(self._connections.items()):
                    for device_id, conn in list(devices.items()):
                        # 检查是否超时
                        elapsed = (now - conn.last_ping_at).total_seconds()
                        
                        if elapsed > self._heartbeat_timeout:
                            logger.warning(f"Heartbeat timeout: {user_id}/{device_id}")
                            dead_connections.append((user_id, device_id))
                        elif elapsed > self._heartbeat_interval:
                            # 发送 ping
                            try:
                                await conn.websocket.send_json({
                                    "type": "ping",
                                    "data": {"timestamp": now.isoformat()}
                                })
                            except:
                                dead_connections.append((user_id, device_id))
                
                # 清理死连接
                for user_id, device_id in dead_connections:
                    await self.disconnect(user_id, device_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat checker error: {e}")
    
    def _generate_msg_id(self) -> str:
        """生成消息ID"""
        import uuid
        return str(uuid.uuid4())


# 全局单例
manager = ConnectionManager()


# 便捷函数：在业务代码中调用
def notify_data_change(
    user_id: str,
    change_type: str,  # created, updated, deleted
    entity_type: str,  # event, memo
    data: dict,
    require_ack: bool = True
):
    """
    通知用户数据变更（非阻塞，后台发送）
    
    使用示例：
    from app.core.websocket import notify_data_change
    
    await notify_data_change(
        user_id=str(user.id),
        change_type="created",
        entity_type="event",
        data={"id": "...", "title": "Meeting", ...}
    )
    """
    message = {
        "type": f"{entity_type}_{change_type}",
        "data": data
    }
    
    # 异步发送，不阻塞主流程
    asyncio.create_task(
        manager.send_to_user(user_id, message, require_ack=require_ack)
    )
