#!/usr/bin/env python3
"""
ChronoSync 完整功能烟雾测试
测试内容:
1. HTTP CRUD 操作（带 type/priority 字段）
2. 同步记录功能（验证 HTTP 修改也被记录到 sync_records）
3. 增量同步 API (/sync/pull, /sync/push)
4. 全量同步

使用方法:
    1. 确保后端服务运行: uvicorn app.main:app --reload
    2. 运行测试: python smoke_test_complete.py
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx

# 配置
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

# 测试数据
TEST_USERNAME = f"smoke_complete_{uuid.uuid4().hex[:8]}"
TEST_PASSWORD = "testpass123"

# 存储测试数据
access_token = None
user_id = None
event_id = None
memo_id = None


def log_step(step_num, total, desc):
    """打印测试步骤"""
    print(f"\n[{step_num}/{total}] {desc}")
    print("-" * 60)


def log_success(msg):
    print(f"✅ {msg}")


def log_error(msg):
    print(f"❌ {msg}")


def log_info(msg):
    print(f"ℹ️  {msg}")


# ==================== 基础测试 ====================

async def test_health():
    """测试健康检查"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        log_success(f"健康检查通过")
        log_info(f"服务状态: {data['status']}")
        return True


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
        data = response.json()
        user_id = data.get("id") or data.get("user_id")
        log_success(f"用户注册成功, ID: {user_id}")
        
        # 登录
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"登录失败: {response.text}"
        data = response.json()
        access_token = data["access_token"]
        log_success(f"登录成功")
        return True


# ==================== HTTP CRUD + 同步记录测试 ====================

async def test_create_event_with_new_fields():
    """测试创建日程（带 type 和 priority 字段）"""
    global event_id
    
    async with httpx.AsyncClient() as client:
        start_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        end_time = (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat()
        
        log_info("创建日程（带 type=WORK, priority=3）...")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/events/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "高优先级工作会议",
                "description": "讨论Q2季度计划",
                "start_time": start_time,
                "end_time": end_time,
                "location": "会议室A",
                "type": "WORK",      # 新增字段
                "priority": 3        # 新增字段（高优先级）
            }
        )
        
        assert response.status_code == 201, f"创建失败: {response.text}"
        data = response.json()
        event_id = data["id"]
        
        # 验证返回了 type 和 priority
        assert data.get("type") == "WORK", f"type 字段错误: {data.get('type')}"
        assert data.get("priority") == 3, f"priority 字段错误: {data.get('priority')}"
        
        log_success(f"日程创建成功: {event_id}")
        log_info(f"标题: {data['title']}")
        log_info(f"类型: {data['type']}, 优先级: {data['priority']}")
        return True


async def test_update_event_via_http():
    """测试通过 HTTP 更新日程（验证是否生成同步记录）"""
    async with httpx.AsyncClient() as client:
        log_info("通过 HTTP PUT 更新日程...")
        
        response = await client.put(
            f"{BASE_URL}{API_PREFIX}/events/{event_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "已更新的会议标题",
                "type": "STUDY",      # 修改类型
                "priority": 1          # 修改优先级
            }
        )
        
        assert response.status_code == 200, f"更新失败: {response.text}"
        data = response.json()
        
        assert data["title"] == "已更新的会议标题"
        assert data["type"] == "STUDY"
        assert data["priority"] == 1
        
        log_success(f"日程更新成功")
        log_info(f"新标题: {data['title']}")
        log_info(f"新类型: {data['type']}, 新优先级: {data['priority']}")
        return True


async def test_sync_pull_after_http_update():
    """测试 HTTP 更新后，/sync/pull 能拉取到记录"""
    async with httpx.AsyncClient() as client:
        log_info("调用 /sync/pull 拉取同步记录...")
        
        # 拉取最近1小时的变更
        since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/sync/pull",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"since": since, "limit": 100}
        )
        
        assert response.status_code == 200, f"拉取失败: {response.text}"
        data = response.json()
        
        log_success(f"拉取成功，返回 {len(data['items'])} 条记录")
        
        # 验证包含 HTTP 更新的记录
        found_update = False
        found_create = False
        
        for item in data['items']:
            if item['entity_type'] == 'event':
                if item['action'] == 'create' and item['server_id'] == event_id:
                    found_create = True
                    log_info(f"找到创建记录: {item['action']} at {item['server_modified_at']}")
                if item['action'] == 'update' and item['server_id'] == event_id:
                    found_update = True
                    log_info(f"找到更新记录: {item['action']} at {item['server_modified_at']}")
                    if item.get('payload'):
                        log_info(f"  更新内容: {json.dumps(item['payload'], ensure_ascii=False)[:100]}...")
        
        if not found_create:
            log_error("未找到创建记录！HTTP 操作未正确记录到 sync_records")
            return False
        
        if not found_update:
            log_error("未找到更新记录！HTTP PUT 未正确记录到 sync_records")
            return False
        
        log_success("HTTP 操作正确记录到 sync_records，可被 /sync/pull 拉取")
        return True


async def test_create_memo_and_sync():
    """测试创建备忘录并验证同步记录"""
    global memo_id
    
    async with httpx.AsyncClient() as client:
        log_info("创建备忘录...")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/memos/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "content": "测试备忘录内容",
                "tags": ["测试", "重要"]
            }
        )
        
        assert response.status_code == 201, f"创建失败: {response.text}"
        data = response.json()
        memo_id = data["id"]
        log_success(f"备忘录创建成功: {memo_id}")
        
        # 验证同步记录
        log_info("验证备忘录同步记录...")
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/sync/pull",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"since": since}
        )
        
        data = response.json()
        found_memo = any(
            item['entity_type'] == 'memo' and item['action'] == 'create'
            for item in data['items']
        )
        
        if found_memo:
            log_success("备忘录同步记录正确生成")
        else:
            log_error("未找到备忘录同步记录")
            return False
        
        return True


async def test_delete_event_and_sync():
    """测试删除日程并验证同步记录"""
    async with httpx.AsyncClient() as client:
        # 先创建一个新日程用于删除测试
        log_info("创建待删除的测试日程...")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/events/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "待删除的日程",
                "start_time": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
                "type": "LIFE",
                "priority": 2
            }
        )
        
        temp_event_id = response.json()["id"]
        log_info(f"创建临时日程: {temp_event_id}")
        
        # 删除日程
        log_info("删除日程...")
        response = await client.delete(
            f"{BASE_URL}{API_PREFIX}/events/{temp_event_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 204, f"删除失败: {response.text}"
        log_success(f"日程删除成功")
        
        # 验证删除同步记录
        log_info("验证删除同步记录...")
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/sync/pull",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"since": since}
        )
        
        data = response.json()
        found_delete = any(
            item['entity_type'] == 'event' and 
            item['action'] == 'delete' and 
            item['server_id'] == temp_event_id
            for item in data['items']
        )
        
        if found_delete:
            log_success("删除操作正确记录到 sync_records")
        else:
            log_error("未找到删除同步记录")
            return False
        
        return True


# ==================== 同步推送测试 ====================

async def test_sync_push():
    """测试通过 /sync/push 推送本地变更"""
    async with httpx.AsyncClient() as client:
        log_info("测试 /sync/push 推送本地创建的日程...")
        
        now = datetime.now(timezone.utc).isoformat()
        start_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        
        request_data = {
            "items": [
                {
                    "client_id": "local_test_001",
                    "server_id": None,  # 新建
                    "entity_type": "event",
                    "action": "create",
                    "payload": {
                        "title": "同步推送测试会议",
                        "description": "通过 sync/push 创建",
                        "start_time": start_time,
                        "end_time": (datetime.now(timezone.utc) + timedelta(days=3, hours=1)).isoformat(),
                        "location": "线上会议室",
                        "status": "pending",
                        "type": "WORK",
                        "priority": 2
                    },
                    "modified_at": now
                }
            ],
            "last_synced_at": None
        }
        
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/sync/push",
            headers={"Authorization": f"Bearer {access_token}"},
            json=request_data
        )
        
        assert response.status_code == 200, f"推送失败: {response.text}"
        data = response.json()
        result = data["results"][0]
        
        assert result["status"] == "success", f"推送失败: {result}"
        assert result["server_id"] is not None
        
        log_success(f"推送成功")
        log_info(f"client_id: {result['client_id']}")
        log_info(f"server_id: {result['server_id']}")
        log_info(f"server_modified_at: {result['server_modified_at']}")
        
        return True


async def test_full_sync():
    """测试全量同步"""
    async with httpx.AsyncClient() as client:
        log_info("测试 /sync/full-sync...")
        
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/sync/full-sync",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"items": []}  # 获取服务器全量数据
        )
        
        assert response.status_code == 200, f"全量同步失败: {response.text}"
        data = response.json()
        
        events_count = len(data['server_data'].get('events', []))
        memos_count = len(data['server_data'].get('memos', []))
        
        log_success(f"全量同步成功")
        log_info(f"服务器日程数: {events_count}")
        log_info(f"服务器备忘录数: {memos_count}")
        
        # 验证返回的数据包含 type 和 priority
        if events_count > 0:
            first_event = data['server_data']['events'][0]
            if 'type' in first_event and 'priority' in first_event:
                log_success("返回数据包含 type 和 priority 字段")
            else:
                log_error("返回数据缺少 type 或 priority 字段")
                return False
        
        return True


# ==================== 清理 ====================

async def cleanup():
    """清理测试数据"""
    print("\n" + "=" * 60)
    print("[清理] 删除测试数据...")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            # 删除测试日程
            if event_id:
                await client.delete(
                    f"{BASE_URL}{API_PREFIX}/events/{event_id}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                log_success(f"已删除测试日程: {event_id}")
            
            # 删除测试备忘录
            if memo_id:
                await client.delete(
                    f"{BASE_URL}{API_PREFIX}/memos/{memo_id}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                log_success(f"已删除测试备忘录: {memo_id}")
                
        except Exception as e:
            log_error(f"清理失败: {e}")


# ==================== 主流程 ====================

async def run_tests():
    """运行所有测试"""
    print("=" * 70)
    print(" ChronoSync 完整功能烟雾测试")
    print(" 测试内容: HTTP CRUD + type/priority + 同步记录 + 增量同步")
    print("=" * 70)
    print(f"测试地址: {BASE_URL}")
    print(f"测试用户: {TEST_USERNAME}")
    
    tests = [
        ("健康检查", test_health),
        ("注册登录", test_register_and_login),
        ("创建日程（带 type/priority）", test_create_event_with_new_fields),
        ("HTTP 更新日程", test_update_event_via_http),
        ("验证 HTTP 更新生成同步记录", test_sync_pull_after_http_update),
        ("创建备忘录", test_create_memo_and_sync),
        ("删除日程并验证同步记录", test_delete_event_and_sync),
        ("同步推送 /sync/push", test_sync_push),
        ("全量同步 /sync/full-sync", test_full_sync),
    ]
    
    passed = 0
    failed = 0
    
    for i, (name, test_func) in enumerate(tests, 1):
        log_step(i, len(tests), name)
        try:
            result = await test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except AssertionError as e:
            log_error(f"测试失败: {e}")
            failed += 1
        except Exception as e:
            log_error(f"发生错误: {type(e).__name__}: {e}")
            failed += 1
    
    # 清理
    await cleanup()
    
    # 结果汇总
    print("\n" + "=" * 70)
    print(" 测试结果汇总")
    print("=" * 70)
    print(f"✅ 通过: {passed}/{len(tests)}")
    print(f"❌ 失败: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 所有测试通过！HTTP CRUD + 同步记录功能工作正常")
        print("=" * 70)
        return 0
    else:
        print(f"\n⚠️  {failed} 个测试失败，请检查日志")
        print("=" * 70)
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
        import traceback
        traceback.print_exc()
        sys.exit(1)
