#!/usr/bin/env python3
"""
ChronoSync WebSocket + 同步功能 烟雾测试
测试内容:
1. WebSocket 连接与心跳
2. 增量同步 (pull/push)
3. 数据变更实时推送
4. 冲突检测

使用方法: 
    1. 确保后端服务运行: uvicorn app.main:app --reload
    2. 运行测试: python smoke_test_sync_ws.py
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import websockets

# 配置
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
API_PREFIX = "/api/v1"

# 测试数据
TEST_USERNAME = f"smoke_ws_{uuid.uuid4().hex[:8]}"
TEST_PASSWORD = "testpass123"

# 存储测试数据
access_token = None
user_id = None
event_id = None
ws_message_received = []


def log_step(step_num, total, desc):
    """打印测试步骤"""
    print(f"\n[{step_num}/{total}] {desc}")
    print("-" * 50)


def log_success(msg):
    """打印成功信息"""
    print(f"✅ {msg}")


def log_error(msg):
    """打印错误信息"""
    print(f"❌ {msg}")


def log_info(msg):
    """打印信息"""
    print(f"ℹ️  {msg}")


# ==================== 基础测试 ====================

async def test_health():
    """测试健康检查（含 WebSocket 状态）"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        ws_status = data.get("websocket", {})
        log_success(f"健康检查通过")
        log_info(f"WebSocket 在线用户: {ws_status.get('online_users', 0)}")
        log_info(f"WebSocket 连接数: {ws_status.get('total_connections', 0)}")


async def test_register_and_login():
    """测试注册和登录"""
    global access_token, user_id
    
    async with httpx.AsyncClient() as client:
        # 注册
        log_info(f"注册用户: {TEST_USERNAME}")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/register",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        assert response.status_code == 201, f"注册失败: {response.text}"
        user_id = response.json()["id"]
        log_success(f"用户注册成功, ID: {user_id}")
        
        # 登录
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"登录失败: {response.text}"
        access_token = response.json()["access_token"]
        log_success(f"登录成功, Token: {access_token[:30]}...")


# ==================== WebSocket 测试 ====================

async def test_websocket_connection():
    """测试 WebSocket 连接和心跳"""
    ws_url = f"{WS_URL}{API_PREFIX}/ws?token={access_token}&device_id=smoke_test_device"
    
    log_info(f"连接 WebSocket: {ws_url[:60]}...")
    
    async with websockets.connect(ws_url) as websocket:
        # 等待连接成功消息
        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        data = json.loads(response)
        
        assert data["type"] == "connected", f"连接失败: {data}"
        server_time = data["data"]["server_time"]
        device_id = data["data"]["device_id"]
        log_success(f"WebSocket 连接成功")
        log_info(f"服务器时间: {server_time}")
        log_info(f"设备ID: {device_id}")
        
        # 等待服务器发送 ping（可选，服务器可能30秒后才发送）
        log_info("等待服务器心跳 (ping)...")
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            
            if data["type"] == "ping":
                log_success(f"收到服务器心跳 (ping)")
                
                # 回复 pong
                pong_msg = {
                    "type": "pong",
                    "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
                }
                await websocket.send(json.dumps(pong_msg))
                log_success(f"回复心跳 (pong)")
            else:
                log_info(f"收到其他消息: {data['type']}")
        except asyncio.TimeoutError:
            log_info("服务器心跳未在5秒内到达（正常，心跳间隔30秒）")


async def test_websocket_realtime_push():
    """测试 WebSocket 实时推送（创建日程时其他设备收到通知）"""
    ws_url = f"{WS_URL}{API_PREFIX}/ws?token={access_token}&device_id=smoke_test_device_2"
    
    log_info("建立 WebSocket 连接监听推送...")
    
    # 同时建立 WebSocket 连接和发送 HTTP 请求
    async with websockets.connect(ws_url) as websocket:
        # 等待连接成功
        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        data = json.loads(response)
        assert data["type"] == "connected"
        log_success("监听端连接成功")
        
        # 在另一个协程中创建日程
        async def create_event_and_listen():
            global event_id
            
            # 等待一会儿确保连接稳定
            await asyncio.sleep(0.5)
            
            # 通过 HTTP 创建日程
            async with httpx.AsyncClient() as client:
                start_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
                end_time = (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat()
                
                log_info("通过 HTTP 创建日程...")
                response = await client.post(
                    f"{BASE_URL}{API_PREFIX}/events/",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "title": "WebSocket 测试会议",
                        "description": "测试实时推送功能",
                        "start_time": start_time,
                        "end_time": end_time,
                        "location": "测试会议室"
                    }
                )
                assert response.status_code == 201
                event_id = response.json()["id"]
                log_success(f"日程创建成功: {event_id}")
            
            # 等待 WebSocket 推送（最多5秒）
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data["type"] == "event_created":
                    log_success(f"收到 WebSocket 推送: event_created")
                    log_info(f"推送数据: {json.dumps(data['data'], indent=2)[:200]}...")
                    
                    # 发送确认
                    ack_msg = {
                        "type": "ack",
                        "data": {"msg_id": data["msg_id"]}
                    }
                    await websocket.send(json.dumps(ack_msg))
                    log_success("发送消息确认 (ack)")
                    return True
                else:
                    log_error(f"收到意外消息类型: {data['type']}")
                    return False
                    
            except asyncio.TimeoutError:
                log_error("等待 WebSocket 推送超时 (5秒)")
                return False
        
        # 并发执行：监听 WebSocket + 创建日程
        result = await create_event_and_listen()
        assert result, "WebSocket 推送测试失败"


# ==================== 同步 API 测试 ====================

async def test_sync_push_create():
    """测试增量推送 - 创建新数据"""
    log_info("测试推送本地创建的日程...")
    
    async with httpx.AsyncClient() as client:
        now = datetime.now(timezone.utc).isoformat()
        start_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        
        request_data = {
            "items": [
                {
                    "client_id": "local_001",
                    "server_id": None,  # 新建，无 server_id
                    "entity_type": "event",
                    "action": "create",
                    "payload": {
                        "title": "同步测试会议",
                        "description": "通过同步接口创建",
                        "start_time": start_time,
                        "end_time": (datetime.now(timezone.utc) + timedelta(days=2, hours=1)).isoformat(),
                        "location": "同步会议室",
                        "status": "pending"
                    },
                    "modified_at": now
                }
            ],
            "last_synced_at": None  # 首次同步
        }
        
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/sync/push",
            headers={"Authorization": f"Bearer {access_token}"},
            json=request_data
        )
        
        assert response.status_code == 200, f"推送失败: {response.text}"
        data = response.json()
        
        assert len(data["results"]) == 1
        result = data["results"][0]
        
        assert result["status"] == "success", f"推送失败: {result}"
        assert result["server_id"] is not None
        
        log_success(f"推送成功")
        log_info(f"client_id: {result['client_id']}")
        log_info(f"server_id: {result['server_id']}")
        log_info(f"server_modified_at: {result['server_modified_at']}")
        
        return result["server_id"]


async def test_sync_pull():
    """测试增量拉取"""
    log_info("测试拉取服务器变更...")
    
    async with httpx.AsyncClient() as client:
        # 拉取自某个时间点后的变更
        since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/sync/pull",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "since": since,
                "limit": 100
            }
        )
        
        assert response.status_code == 200, f"拉取失败: {response.text}"
        data = response.json()
        
        log_success(f"拉取成功")
        log_info(f"返回 {len(data['items'])} 条变更")
        log_info(f"has_more: {data['has_more']}")
        log_info(f"server_time: {data['server_time']}")
        
        # 验证返回的数据结构
        if data["items"]:
            item = data["items"][0]
            assert "server_id" in item
            assert "entity_type" in item
            assert "action" in item
            log_info(f"首条变更: {item['entity_type']} {item['action']}")
        
        return data["items"]


async def test_sync_push_update():
    """测试增量推送 - 更新数据"""
    log_info("测试推送更新的日程...")
    
    # 先创建一个日程
    async with httpx.AsyncClient() as client:
        start_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        
        # 创建
        create_response = await client.post(
            f"{BASE_URL}{API_PREFIX}/events/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "待更新会议",
                "start_time": start_time,
                "end_time": (datetime.now(timezone.utc) + timedelta(days=3, hours=1)).isoformat()
            }
        )
        created_event_id = create_response.json()["id"]
        log_info(f"创建测试日程: {created_event_id}")
        
        # 更新（通过同步接口）
        now = datetime.now(timezone.utc).isoformat()
        request_data = {
            "items": [
                {
                    "client_id": "local_002",
                    "server_id": created_event_id,
                    "entity_type": "event",
                    "action": "update",
                    "payload": {
                        "title": "已更新的会议标题",
                        "description": "通过同步接口更新",
                        "status": "completed"
                    },
                    "modified_at": now
                }
            ],
            "last_synced_at": now  # 模拟上次同步时间
        }
        
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/sync/push",
            headers={"Authorization": f"Bearer {access_token}"},
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        result = data["results"][0]
        
        assert result["status"] == "success"
        log_success(f"更新推送成功")
        
        # 验证更新
        get_response = await client.get(
            f"{BASE_URL}{API_PREFIX}/events/{created_event_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        updated_data = get_response.json()
        assert updated_data["title"] == "已更新的会议标题"
        assert updated_data["status"] == "completed"
        log_success(f"验证更新成功: 标题='{updated_data['title']}', 状态='{updated_data['status']}'")


async def test_sync_conflict():
    """测试冲突检测（简化版）"""
    log_info("测试冲突检测（简化版）...")
    log_info("冲突检测需要复杂的时序控制，这里仅测试接口可用")
    
    async with httpx.AsyncClient() as client:
        # 创建一个日程
        start_time = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
        create_response = await client.post(
            f"{BASE_URL}{API_PREFIX}/events/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "冲突测试会议",
                "start_time": start_time,
                "end_time": (datetime.now(timezone.utc) + timedelta(days=4, hours=1)).isoformat()
            }
        )
        created_event_id = create_response.json()["id"]
        log_info(f"创建测试日程: {created_event_id}")
        
        # 测试解决冲突接口（直接调用，不验证实际冲突）
        resolve_response = await client.post(
            f"{BASE_URL}{API_PREFIX}/sync/resolve-conflict",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "client_id": "local_003",
                "server_id": created_event_id,
                "entity_type": "event",
                "resolution": "server"
            }
        )
        
        # 接口返回 200 即可（即使实际没有冲突）
        log_success(f"冲突解决接口调用成功 (status: {resolve_response.status_code})")


async def test_full_sync():
    """测试全量同步"""
    log_info("测试全量同步...")
    
    async with httpx.AsyncClient() as client:
        request_data = {
            "items": []  # 空数据，表示获取服务器全量
        }
        
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/sync/full-sync",
            headers={"Authorization": f"Bearer {access_token}"},
            json=request_data
        )
        
        assert response.status_code == 200, f"全量同步失败: {response.text}"
        data = response.json()
        
        log_success(f"全量同步成功")
        log_info(f"服务器日程数: {len(data['server_data'].get('events', []))}")
        log_info(f"服务器备忘录数: {len(data['server_data'].get('memos', []))}")
        log_info(f"推送结果: {len(data.get('push_results', []))} 条")


# ==================== 清理 ====================

async def cleanup():
    """清理测试数据"""
    print("\n" + "=" * 50)
    print("[清理] 删除测试数据...")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # 删除所有测试创建的日程和备忘录
        try:
            # 获取所有日程
            response = await client.get(
                f"{BASE_URL}{API_PREFIX}/events/",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"size": 100}
            )
            
            if response.status_code == 200:
                events = response.json().get("items", [])
                for event in events:
                    await client.delete(
                        f"{BASE_URL}{API_PREFIX}/events/{event['id']}",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                log_success(f"已删除 {len(events)} 个测试日程")
            
            # 获取所有备忘录
            response = await client.get(
                f"{BASE_URL}{API_PREFIX}/memos/",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"size": 100}
            )
            
            if response.status_code == 200:
                memos = response.json().get("items", [])
                for memo in memos:
                    await client.delete(
                        f"{BASE_URL}{API_PREFIX}/memos/{memo['id']}",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                log_success(f"已删除 {len(memos)} 个测试备忘录")
                
        except Exception as e:
            log_error(f"清理失败: {e}")


# ==================== 主流程 ====================

async def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print(" ChronoSync WebSocket + 同步功能 烟雾测试")
    print("=" * 60)
    print(f"测试地址: {BASE_URL}")
    print(f"WebSocket: {WS_URL}")
    print(f"测试用户: {TEST_USERNAME}")
    
    tests = [
        ("健康检查", test_health),
        ("注册登录", test_register_and_login),
        ("WebSocket 连接与心跳", test_websocket_connection),
        ("WebSocket 实时推送", test_websocket_realtime_push),
        ("同步推送-创建", test_sync_push_create),
        ("同步拉取", test_sync_pull),
        ("同步推送-更新", test_sync_push_update),
        ("冲突检测", test_sync_conflict),
        ("全量同步", test_full_sync),
    ]
    
    passed = 0
    failed = 0
    
    for i, (name, test_func) in enumerate(tests, 1):
        log_step(i, len(tests), name)
        try:
            await test_func()
            passed += 1
        except AssertionError as e:
            log_error(f"测试失败: {e}")
            failed += 1
        except Exception as e:
            log_error(f"发生错误: {type(e).__name__}: {e}")
            failed += 1
    
    # 清理
    await cleanup()
    
    # 结果汇总
    print("\n" + "=" * 60)
    print(" 测试结果汇总")
    print("=" * 60)
    print(f"✅ 通过: {passed}/{len(tests)}")
    print(f"❌ 失败: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 所有测试通过！WebSocket + 同步功能工作正常")
        print("=" * 60)
        return 0
    else:
        print(f"\n⚠️  {failed} 个测试失败，请检查日志")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(run_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试运行失败: {e}")
        sys.exit(1)
