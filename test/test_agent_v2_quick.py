#!/usr/bin/env python3
"""
万机 Agent V2 快速测试脚本（简化版）
只测试核心功能，快速验证

使用方法:
    python test/test_agent_v2_quick.py
"""

import asyncio
import sys
import uuid
from datetime import datetime

import httpx

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"
TEST_USERNAME = f"quick_test_{uuid.uuid4().hex[:6]}"
TEST_PASSWORD = "test123"


def print_header():
    print("=" * 60)
    print("🤖 万机 Agent V2 快速测试")
    print("=" * 60)


def print_result(name, success, detail=""):
    icon = "✅" if success else "❌"
    print(f"{icon} {name}")
    if detail:
        print(f"   {detail}")


async def quick_test():
    print_header()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 健康检查
        try:
            resp = await client.get(f"{BASE_URL}/health")
            print_result("健康检查", resp.status_code == 200, 
                        f"状态: {resp.json().get('status')}")
        except Exception as e:
            print_result("健康检查", False, str(e))
            print("\n请确保后端已启动: uvicorn app.main:app --reload")
            return False
        
        # 2. 注册
        try:
            resp = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/register",
                json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
            )
            print_result("用户注册", resp.status_code in [201, 400])
        except Exception as e:
            print_result("用户注册", False, str(e))
            return False
        
        # 3. 登录
        token = None
        try:
            resp = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/login",
                headers={"Content-Type": "application/json"},
                json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                print_result("用户登录", True, f"Token: {token[:20]}...")
            else:
                print_result("用户登录", False, f"{resp.status_code}")
                return False
        except Exception as e:
            print_result("用户登录", False, str(e))
            return False
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 4. Agent 创建日程
        try:
            print("\n📝 测试 Agent 创建日程（可能需要 5-10 秒）...")
            resp = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers=headers,
                json={"text": "帮我安排明天下午3点的会议", "conversation_id": None}
            )
            if resp.status_code == 200:
                reply = resp.json().get("reply", "")
                print_result("Agent 创建日程", True, reply[:60])
            else:
                print_result("Agent 创建日程", False, f"{resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print_result("Agent 创建日程", False, str(e))
        
        # 5. Agent 查询日程
        try:
            print("\n📝 测试 Agent 查询日程...")
            resp = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers=headers,
                json={"text": "明天有什么安排", "conversation_id": None}
            )
            if resp.status_code == 200:
                reply = resp.json().get("reply", "")
                print_result("Agent 查询日程", True, reply[:60])
            else:
                print_result("Agent 查询日程", False, f"{resp.status_code}")
        except Exception as e:
            print_result("Agent 查询日程", False, str(e))
        
        # 6. 多日查询（V2新功能）
        try:
            print("\n📝 测试多日查询（V2新功能）...")
            resp = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers=headers,
                json={"text": "最近3天有什么安排", "conversation_id": None}
            )
            if resp.status_code == 200:
                reply = resp.json().get("reply", "")
                print_result("多日查询", True, reply[:60])
            else:
                print_result("多日查询", False, f"{resp.status_code}")
        except Exception as e:
            print_result("多日查询", False, str(e))
        
        # 7. 对话历史 API（V2新功能）
        try:
            print("\n📝 测试对话历史 API...")
            resp = await client.get(
                f"{BASE_URL}{API_PREFIX}/agent/conversations?limit=5",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("total", 0)
                print_result("对话历史 API", True, f"共 {total} 条记录")
            else:
                print_result("对话历史 API", False, f"{resp.status_code}")
        except Exception as e:
            print_result("对话历史 API", False, str(e))
        
        # 8. 清空对话历史
        try:
            resp = await client.delete(
                f"{BASE_URL}{API_PREFIX}/agent/conversations",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 200:
                deleted = resp.json().get("deleted_count", 0)
                print_result("清空对话历史", True, f"删除 {deleted} 条")
            else:
                print_result("清空对话历史", False, f"{resp.status_code}")
        except Exception as e:
            print_result("清空对话历史", False, str(e))
    
    print("\n" + "=" * 60)
    print("🎉 快速测试完成！")
    print("=" * 60)
    print("\n如果以上测试都通过，可以运行完整测试:")
    print("  python test/test_agent_v2_local.py")
    print("\n然后部署到云端:")
    print("  1. git push origin main")
    print("  2. 在服务器执行: alembic upgrade head")
    print("  3. 重启后端服务")
    
    return True


if __name__ == "__main__":
    try:
        asyncio.run(quick_test())
    except KeyboardInterrupt:
        print("\n测试中断")
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)
