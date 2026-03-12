#!/usr/bin/env python3
"""
ChronoSync API 修复验证测试
测试内容:
1. 登录接口 JSON 格式
2. 路径参数统一为 serverId
3. status 更新接口改为 JSON body
4. type/priority 字段验证
5. 同步记录验证

使用方法:
    python test_api_fix.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

TEST_USERNAME = f"test_fix_{uuid.uuid4().hex[:8]}"
TEST_PASSWORD = "testpass123"

access_token = None
user_id = None
event_id = None


def log_step(step_num, total, desc):
    print(f"\n[{step_num}/{total}] {desc}")
    print("-" * 60)


def log_success(msg):
    print(f"✅ {msg}")


def log_error(msg):
    print(f"❌ {msg}")


def log_info(msg):
    print(f"ℹ️  {msg}")


# ==================== 测试 1: 登录接口 JSON 格式 ====================

async def test_login_json_format():
    """测试登录接口使用 JSON 格式"""
    log_step(1, 8, "登录接口 JSON 格式验证")
    
    global access_token, user_id
    
    async with httpx.AsyncClient() as client:
        # 先注册
        log_info("1. 注册用户...")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/register",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        
        if response.status_code != 201:
            log_error(f"注册失败: {response.text}")
            return False
        
        data = response.json()
        user_id = data.get("id") or data.get("user_id")
        log_success(f"注册成功: {user_id}")
        
        # 测试 JSON 格式登录
        log_info("2. 使用 JSON 格式登录...")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            headers={"Content-Type": "application/json"},
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        
        if response.status_code != 200:
            log_error(f"登录失败: {response.text}")
            log_info("注意: 如果返回 422，说明后端仍使用 form-urlencoded")
            return False
        
        data = response.json()
        access_token = data["access_token"]
        
        log_success("JSON 格式登录成功！")
        log_info(f"token_type: {data.get('token_type')}")
        log_info(f"expires_in: {data.get('expires_in')}")
        return True


# ==================== 测试 2: 创建日程（带 type/priority）====================

async def test_create_event_with_fields():
    """测试创建日程，验证 type/priority 字段"""
    log_step(2, 8, "创建日程（带 type/priority）")
    
    global event_id
    
    async with httpx.AsyncClient() as client:
        start_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/events/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "测试会议",
                "description": "验证字段修复",
                "start_time": start_time,
                "end_time": (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat(),
                "location": "会议室A",
                "type": "WORK",
                "priority": 3
            }
        )
        
        if response.status_code != 201:
            log_error(f"创建失败: {response.text}")
            return False
        
        data = response.json()
        event_id = data["id"]
        
        # 验证字段
        if data.get("type") != "WORK":
            log_error(f"type 字段错误: 期望 WORK, 得到 {data.get('type')}")
            return False
        
        if data.get("priority") != 3:
            log_error(f"priority 字段错误: 期望 3, 得到 {data.get('priority')}")
            return False
        
        log_success("日程创建成功！")
        log_info(f"ID: {event_id}")
        log_info(f"Title: {data['title']}")
        log_info(f"Type: {data['type']}, Priority: {data['priority']}")
        return True


# ==================== 测试 3: 获取日程（serverId 路径参数）====================

async def test_get_event_by_serverId():
    """测试使用 serverId 路径参数获取日程"""
    log_step(3, 8, "获取日程（验证 serverId 路径参数）")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/events/{event_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 200:
            log_error(f"获取失败: {response.text}")
            log_info("注意: 如果 404，可能是路径参数名不匹配")
            return False
        
        data = response.json()
        
        if data["id"] != event_id:
            log_error(f"ID 不匹配!")
            return False
        
        log_success(f"成功获取日程: {data['title']}")
        log_info(f"Type: {data['type']}, Priority: {data['priority']}")
        return True


# ==================== 测试 4: 更新日程（serverId 路径参数）====================

async def test_update_event_by_serverId():
    """测试使用 serverId 路径参数更新日程"""
    log_step(4, 8, "更新日程（验证 serverId 路径参数）")
    
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}{API_PREFIX}/events/{event_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={
                "title": "已更新的会议",
                "type": "STUDY",
                "priority": 1
            }
        )
        
        if response.status_code != 200:
            log_error(f"更新失败: {response.text}")
            return False
        
        data = response.json()
        
        if data["title"] != "已更新的会议":
            log_error(f"标题未更新!")
            return False
        
        if data["type"] != "STUDY":
            log_error(f"type 未更新!")
            return False
        
        log_success("日程更新成功！")
        log_info(f"新 Title: {data['title']}")
        log_info(f"新 Type: {data['type']}, 新 Priority: {data['priority']}")
        return True


# ==================== 测试 5: 更新状态（JSON body）====================

async def test_update_status_json_body():
    """测试 status 更新接口使用 JSON body"""
    log_step(5, 8, "更新状态（验证 JSON body 格式）")
    
    async with httpx.AsyncClient() as client:
        # 使用 JSON body 而不是查询参数
        response = await client.patch(
            f"{BASE_URL}{API_PREFIX}/events/{event_id}/status",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={"status": "completed"}  # JSON body
        )
        
        if response.status_code != 200:
            log_error(f"状态更新失败: {response.text}")
            log_info("注意: 如果 422，可能是后端仍使用查询参数格式")
            return False
        
        data = response.json()
        
        if data["status"] != "completed":
            log_error(f"状态未更新: 期望 completed, 得到 {data['status']}")
            return False
        
        log_success("状态更新成功（JSON body）！")
        log_info(f"Status: {data['status']}")
        return True


# ==================== 测试 6: 同步记录验证 ====================

async def test_sync_records():
    """验证操作被记录到 sync_records"""
    log_step(6, 8, "验证同步记录")
    
    async with httpx.AsyncClient() as client:
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/sync/pull",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"since": since, "limit": 100}
        )
        
        if response.status_code != 200:
            log_error(f"拉取失败: {response.text}")
            return False
        
        data = response.json()
        items = data.get("items", [])
        
        log_info(f"找到 {len(items)} 条同步记录")
        
        # 查找与当前日程相关的记录
        event_records = [i for i in items if i.get("entity_type") == "event" and i.get("server_id") == event_id]
        
        actions = [r["action"] for r in event_records]
        log_info(f"当前日程的操作记录: {actions}")
        
        if "create" in actions and "update" in actions:
            log_success("同步记录正确（包含 create 和 update）")
            return True
        else:
            log_error(f"缺少同步记录: 期望 create+update, 得到 {actions}")
            return False


# ==================== 测试 7: 备忘录接口（serverId）====================

async def test_memo_serverId():
    """测试备忘录接口使用 serverId"""
    log_step(7, 8, "备忘录接口（验证 serverId 路径参数）")
    
    async with httpx.AsyncClient() as client:
        # 创建备忘录
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/memos/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"content": "测试备忘录", "tags": ["测试"]}
        )
        
        if response.status_code != 201:
            log_error(f"创建备忘录失败: {response.text}")
            return False
        
        memo_id = response.json()["id"]
        log_success(f"备忘录创建成功: {memo_id}")
        
        # 使用 serverId 获取
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/memos/{memo_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 200:
            log_error(f"获取备忘录失败: {response.text}")
            return False
        
        # 使用 serverId 更新
        response = await client.put(
            f"{BASE_URL}{API_PREFIX}/memos/{memo_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"content": "已更新的备忘录"}
        )
        
        if response.status_code != 200:
            log_error(f"更新备忘录失败: {response.text}")
            return False
        
        # 使用 serverId 删除
        response = await client.delete(
            f"{BASE_URL}{API_PREFIX}/memos/{memo_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 204:
            log_error(f"删除备忘录失败: {response.text}")
            return False
        
        log_success("备忘录 CRUD 全部成功（serverId 路径参数）")
        return True


# ==================== 测试 8: 删除日程（serverId）====================

async def test_delete_event_by_serverId():
    """测试使用 serverId 路径参数删除日程"""
    log_step(8, 8, "删除日程（验证 serverId 路径参数）")
    
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{BASE_URL}{API_PREFIX}/events/{event_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 204:
            log_error(f"删除失败: {response.text}")
            return False
        
        log_success("日程删除成功！")
        
        # 验证已删除
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/events/{event_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code == 404:
            log_success("确认日程已删除（返回 404）")
            return True
        else:
            log_error(f"日程仍能被访问: {response.status_code}")
            return False


# ==================== 主流程 ====================

async def run_tests():
    print("=" * 70)
    print(" ChronoSync API 修复验证测试")
    print("=" * 70)
    print(f"测试用户: {TEST_USERNAME}")
    print(f"测试地址: {BASE_URL}")
    
    tests = [
        ("登录接口 JSON 格式", test_login_json_format),
        ("创建日程（type/priority）", test_create_event_with_fields),
        ("获取日程（serverId）", test_get_event_by_serverId),
        ("更新日程（serverId）", test_update_event_by_serverId),
        ("更新状态（JSON body）", test_update_status_json_body),
        ("验证同步记录", test_sync_records),
        ("备忘录接口（serverId）", test_memo_serverId),
        ("删除日程（serverId）", test_delete_event_by_serverId),
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
        except Exception as e:
            log_error(f"测试异常: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(" 测试结果汇总")
    print("=" * 70)
    print(f"✅ 通过: {passed}/{len(tests)}")
    print(f"❌ 失败: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 所有测试通过！API 修复验证成功")
        print("=" * 70)
        return 0
    else:
        print(f"\n⚠️  {failed} 个测试失败")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(run_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
