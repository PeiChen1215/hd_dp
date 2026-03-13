#!/usr/bin/env python3
"""
ChronoSync 核心 API 烟雾测试
使用方法: python smoke_test.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta

import httpx

# 配置
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

# 测试数据
TEST_USERNAME = f"smoke_test_{uuid.uuid4().hex[:8]}"
TEST_PASSWORD = "testpass123"

# 存储测试过程中生成的数据
access_token = None
user_id = None
event_id = None
memo_id = None


async def test_health():
    """测试健康检查"""
    print("\n[1/7] 测试健康检查...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        print("✅ 健康检查通过")


async def test_register():
    """测试用户注册"""
    print(f"\n[2/7] 测试用户注册 (用户名: {TEST_USERNAME})...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/register",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        assert response.status_code == 201, f"注册失败: {response.text}"
        data = response.json()
        global user_id
        user_id = data["id"]
        print(f"✅ 用户注册成功, ID: {user_id}")


async def test_login():
    """测试用户登录"""
    print(f"\n[3/7] 测试用户登录...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"登录失败: {response.text}"
        data = response.json()
        global access_token
        access_token = data["access_token"]
        print(f"✅ 登录成功, Token: {access_token[:20]}...")


async def test_create_event():
    """测试创建日程"""
    print(f"\n[4/7] 测试创建日程...")
    start_time = (datetime.now() + timedelta(days=1)).isoformat()
    end_time = (datetime.now() + timedelta(days=1, hours=1)).isoformat()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/events/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "title": "烟雾测试会议",
                "description": "这是一个烟雾测试",
                "start_time": start_time,
                "end_time": end_time,
                "location": "会议室A"
            }
        )
        assert response.status_code == 201, f"创建日程失败: {response.text}"
        data = response.json()
        global event_id
        event_id = data["id"]
        print(f"✅ 日程创建成功, ID: {event_id}")
        print(f"   标题: {data['title']}")
        print(f"   时间: {data['start_time']}")


async def test_list_events():
    """测试查询日程列表"""
    print(f"\n[5/7] 测试查询日程列表...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/events/",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200, f"查询日程失败: {response.text}"
        data = response.json()
        print(f"✅ 查询成功, 共 {data['total']} 条日程")
        for item in data["items"]:
            print(f"   - {item['title']} ({item['status']})")


async def test_create_memo():
    """测试创建备忘录"""
    print(f"\n[6/7] 测试创建备忘录...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/memos/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "content": "记得做烟雾测试",
                "tags": ["测试", "重要"]
            }
        )
        assert response.status_code == 201, f"创建备忘录失败: {response.text}"
        data = response.json()
        global memo_id
        memo_id = data["id"]
        print(f"✅ 备忘录创建成功, ID: {memo_id}")
        print(f"   内容: {data['content']}")


async def test_list_memos():
    """测试查询备忘录列表"""
    print(f"\n[7/7] 测试查询备忘录列表...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/memos/",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200, f"查询备忘录失败: {response.text}"
        data = response.json()
        print(f"✅ 查询成功, 共 {data['total']} 条备忘录")
        for item in data["items"]:
            print(f"   - {item['content'][:30]}...")


async def cleanup():
    """清理测试数据"""
    print(f"\n[清理] 删除测试数据...")
    async with httpx.AsyncClient() as client:
        # 删除日程
        if event_id:
            await client.delete(
                f"{BASE_URL}{API_PREFIX}/events/{event_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            print(f"✅ 已删除测试日程")
        
        # 删除备忘录
        if memo_id:
            await client.delete(
                f"{BASE_URL}{API_PREFIX}/memos/{memo_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            print(f"✅ 已删除测试备忘录")


async def run_tests():
    """运行所有测试"""
    print("=" * 50)
    print("ChronoSync 核心 API 烟雾测试")
    print("=" * 50)
    print(f"测试地址: {BASE_URL}")
    print(f"测试用户: {TEST_USERNAME}")
    
    try:
        await test_health()
        await test_register()
        await test_login()
        await test_create_event()
        await test_list_events()
        await test_create_memo()
        await test_list_memos()
        
        print("\n" + "=" * 50)
        print("🎉 所有测试通过！API 工作正常")
        print("=" * 50)
        
        # 清理测试数据
        await cleanup()
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
