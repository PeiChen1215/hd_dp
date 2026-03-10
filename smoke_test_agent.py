#!/usr/bin/env python3
"""
万机 Agent 烟雾测试
测试 Agent 的自然语言理解和工具调用能力

使用方法:
    1. 确保后端服务已启动: uvicorn app.main:app --reload
    2. 运行测试: python smoke_test_agent.py

注意: 此测试会调用真实的 DeepSeek API，产生少量费用
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta

import httpx

# 配置
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

# 测试用户（随机，避免重复）
TEST_USERNAME = f"agent_{uuid.uuid4().hex[:8]}"
TEST_PASSWORD = "test123"

# 存储测试数据
access_token = None
user_id = None
event_id = None
memo_id = None


async def check_api_key():
    """检查是否配置了 DeepSeek API Key"""
    print("\n[0/7] 检查环境变量...")
    try:
        with open('.env', 'r') as f:
            content = f.read()
            if 'DASHSCOPE_API_KEY' in content and 'sk-' in content:
                print("✅ 找到 DASHSCOPE_API_KEY 配置")
                return True
    except FileNotFoundError:
        pass
    
    print("⚠️ 警告: 未在 .env 中找到 DASHSCOPE_API_KEY")
    print("   Agent 功能可能无法正常工作")
    return False


async def test_register():
    """注册测试用户"""
    print(f"\n[1/7] 注册测试用户 ({TEST_USERNAME})...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/register",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        
        if response.status_code == 201:
            print("✅ 用户注册成功")
            return True
        elif response.status_code == 400 and "already" in response.text.lower():
            print(f"⚠️ 用户 {TEST_USERNAME} 已存在，使用新用户名重试...")
            # 这种情况不应该发生，因为使用了随机用户名
            return False
        else:
            print(f"❌ 注册失败: {response.text}")
            return False


async def test_login():
    """登录获取 Token"""
    print(f"\n[2/7] 登录获取 Token...")
    global access_token, user_id
    
    async with httpx.AsyncClient() as client:
        # 使用 form-data 格式（OAuth2 标准）
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            data={"username": TEST_USERNAME, "password": TEST_PASSWORD}  # 注意是 data 不是 json
        )
        
        if response.status_code == 200:
            data = response.json()
            access_token = data["access_token"]
            print(f"✅ 登录成功")
            print(f"   Token: {access_token[:30]}...")
            return True
        else:
            print(f"❌ 登录失败: {response.text}")
            return False


async def test_agent_create_event():
    """测试 Agent 创建日程"""
    print(f"\n[3/7] 测试 Agent 创建日程...")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/agent/process",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"text": f"帮我安排明天下午3点的会议，标题是项目评审", "conversation_id": None},
            timeout=30.0  # Agent 调用可能需要较长时间
        )
        
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Agent 响应: {data.get('reply', '无回复')[:100]}")
            return True
        else:
            print(f"❌ 请求失败: {response.text[:200]}")
            return False


async def test_agent_query_event():
    """测试 Agent 查询日程"""
    print(f"\n[4/7] 测试 Agent 查询日程...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/agent/process",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"text": "明天有什么安排？", "conversation_id": None},
            timeout=30.0
        )
        
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Agent 响应: {data.get('reply', '无回复')[:100]}")
            return True
        else:
            print(f"❌ 请求失败: {response.text[:200]}")
            return False


async def test_agent_create_memo():
    """测试 Agent 创建备忘录"""
    print(f"\n[5/7] 测试 Agent 创建备忘录...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/agent/process",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"text": "记住买牛奶和鸡蛋", "conversation_id": None},
            timeout=30.0
        )
        
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Agent 响应: {data.get('reply', '无回复')[:100]}")
            return True
        else:
            print(f"❌ 请求失败: {response.text[:200]}")
            return False


async def test_agent_query_memo():
    """测试 Agent 查询备忘录"""
    print(f"\n[6/7] 测试 Agent 查询备忘录...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/agent/process",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"text": "查看我的备忘录", "conversation_id": None},
            timeout=30.0
        )
        
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Agent 响应: {data.get('reply', '无回复')[:100]}")
            return True
        else:
            print(f"❌ 请求失败: {response.text[:200]}")
            return False


async def test_agent_statistics():
    """测试 Agent 统计功能"""
    print(f"\n[7/7] 测试 Agent 统计功能...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/agent/process",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"text": "我有多少条日程？", "conversation_id": None},
            timeout=30.0
        )
        
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Agent 响应: {data.get('reply', '无回复')[:100]}")
            return True
        else:
            print(f"❌ 请求失败: {response.text[:200]}")
            return False


async def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🤖 万机 Agent 烟雾测试")
    print("=" * 60)
    print(f"测试地址: {BASE_URL}")
    print(f"测试用户: {TEST_USERNAME}")
    print("⚠️  注意: 此测试会调用真实的 DeepSeek API")
    print("=" * 60)
    
    results = []
    
    try:
        # 检查配置
        await check_api_key()
        
        # 基础测试
        results.append(("注册", await test_register()))
        
        if not results[-1][1]:
            print("\n❌ 注册失败，终止测试")
            return
        
        results.append(("登录", await test_login()))
        
        if not access_token:
            print("\n❌ 无法获取 Token，终止测试")
            return
        
        # Agent 功能测试
        results.append(("创建日程", await test_agent_create_event()))
        results.append(("查询日程", await test_agent_query_event()))
        results.append(("创建备忘", await test_agent_create_memo()))
        results.append(("查询备忘", await test_agent_query_memo()))
        results.append(("统计功能", await test_agent_statistics()))
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
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
        print("🎉 所有测试通过！Agent 工作正常")
    else:
        print("⚠️  部分测试失败，请检查日志")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
