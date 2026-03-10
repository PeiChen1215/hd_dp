#!/usr/bin/env python3
"""
云服务器后端烟雾测试
测试地址: http://115.190.155.26:8000

使用方法:
    python smoke_test_cloud.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta

import httpx

# 云服务器配置
BASE_URL = "http://115.190.155.26:8000"
API_PREFIX = "/api/v1"
TIMEOUT = 30.0  # 云服务器可能需要更长时间

# 测试用户
TEST_USERNAME = f"cloud_test_{uuid.uuid4().hex[:6]}"
TEST_PASSWORD = "test123"

# 存储测试数据
access_token = None


async def test_health():
    """测试健康检查"""
    print("\n[1/8] 测试健康检查...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                print(f"✅ 健康检查通过: {response.json()}")
                return True
            else:
                print(f"❌ 健康检查失败: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False


async def test_register():
    """注册测试用户"""
    print(f"\n[2/8] 注册测试用户 ({TEST_USERNAME})...")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/register",
                json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
            )
            
            if response.status_code == 201:
                print("✅ 用户注册成功")
                return True
            elif response.status_code == 400:
                print(f"⚠️ 注册返回 400: {response.text}")
                # 可能是用户已存在，继续尝试登录
                return True
            else:
                print(f"❌ 注册失败: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        print(f"❌ 注册异常: {e}")
        return False


async def test_login():
    """登录获取 Token"""
    print(f"\n[3/8] 登录获取 Token...")
    global access_token
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/login",
                data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
            )
            
            if response.status_code == 200:
                data = response.json()
                access_token = data["access_token"]
                print(f"✅ 登录成功")
                print(f"   Token: {access_token[:30]}...")
                return True
            else:
                print(f"❌ 登录失败: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return False


async def test_create_event():
    """测试创建日程"""
    print(f"\n[4/8] 测试创建日程...")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/events/",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "title": "云服务器测试会议",
                    "description": "这是从本地发起的测试",
                    "start_time": (datetime.now() + timedelta(days=1)).isoformat(),
                    "end_time": (datetime.now() + timedelta(days=1, hours=1)).isoformat(),
                    "location": "会议室A"
                }
            )
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 201:
                data = response.json()
                print(f"✅ 创建成功: {data.get('title')}")
                return True
            else:
                print(f"❌ 创建失败: {response.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ 创建异常: {e}")
        return False


async def test_list_events():
    """测试查询日程列表"""
    print(f"\n[5/8] 测试查询日程列表...")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"{BASE_URL}{API_PREFIX}/events/",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 查询成功: 共 {data.get('total', 0)} 条日程")
                return True
            else:
                print(f"❌ 查询失败: {response.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ 查询异常: {e}")
        return False


async def test_agent_create_event():
    """测试 Agent 创建日程"""
    print(f"\n[6/8] 测试 Agent 创建日程...")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:  # Agent 需要更长时间
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"text": "帮我安排明天下午3点的项目评审会议", "conversation_id": None}
            )
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                reply = data.get('reply', '无回复')
                print(f"✅ Agent 响应: {reply[:100]}")
                return True
            else:
                print(f"❌ Agent 失败: {response.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ Agent 异常: {e}")
        return False


async def test_create_memo():
    """测试创建备忘录"""
    print(f"\n[7/8] 测试创建备忘录...")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/memos/",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "content": "云服务器测试备忘：记得检查部署状态",
                    "tags": ["测试", "部署"]
                }
            )
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 201:
                data = response.json()
                print(f"✅ 创建成功: {data.get('content', '')[:30]}...")
                return True
            else:
                print(f"❌ 创建失败: {response.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ 创建异常: {e}")
        return False


async def test_list_memos():
    """测试查询备忘录"""
    print(f"\n[8/8] 测试查询备忘录...")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"{BASE_URL}{API_PREFIX}/memos/",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 查询成功: 共 {data.get('total', 0)} 条备忘录")
                return True
            else:
                print(f"❌ 查询失败: {response.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ 查询异常: {e}")
        return False


async def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("☁️ 云服务器后端烟雾测试")
    print("=" * 60)
    print(f"测试地址: {BASE_URL}")
    print(f"测试用户: {TEST_USERNAME}")
    print("⚠️ 注意: 云服务器可能有网络延迟，请耐心等待")
    print("=" * 60)
    
    results = []
    
    # 基础连接测试
    results.append(("健康检查", await test_health()))
    
    if not results[-1][1]:
        print("\n❌ 无法连接到云服务器，终止测试")
        print("请检查：")
        print("1. 云服务器是否已启动 (systemctl status chronosync)")
        print("2. 防火墙是否开放 8000 端口")
        print("3. 安全组是否允许访问")
        return
    
    # 认证测试
    results.append(("用户注册", await test_register()))
    results.append(("用户登录", await test_login()))
    
    if not access_token:
        print("\n❌ 无法获取 Token，终止测试")
        return
    
    # 功能测试
    results.append(("创建日程", await test_create_event()))
    results.append(("查询日程", await test_list_events()))
    results.append(("Agent创建日程", await test_agent_create_event()))
    results.append(("创建备忘录", await test_create_memo()))
    results.append(("查询备忘录", await test_list_memos()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！云服务器后端工作正常")
    elif passed >= total * 0.7:
        print("⚠️ 大部分测试通过，可能有部分功能异常")
    else:
        print("❌ 大量测试失败，请检查服务器配置")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
