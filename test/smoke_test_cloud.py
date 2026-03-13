#!/usr/bin/env python3
"""
云服务器后端烟雾测试
测试地址: http://115.190.155.26:8000

使用方法:
    python test/smoke_test_cloud.py

注意:
    - 云服务器可能有网络延迟，请耐心等待
    - 测试会创建真实数据，测试后会尝试清理
"""

import asyncio
import sys
import uuid
import traceback
from datetime import datetime, timedelta, timezone

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
user_id = None
event_id = None
memo_id = None


def log_section(title):
    """打印章节标题"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def log_step(step_num, total, desc):
    """打印测试步骤"""
    print(f"\n[{step_num}/{total}] {desc}")
    print("-" * 60)


def log_success(msg):
    print(f"✅ {msg}")


def log_error(msg, detail=None):
    print(f"❌ {msg}")
    if detail:
        print(f"   详情: {detail}")


def log_info(msg):
    print(f"ℹ️  {msg}")


def log_warn(msg):
    print(f"⚠️  {msg}")


async def test_health():
    """测试健康检查"""
    log_step(1, 10, "测试健康检查")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            log_info(f"GET {BASE_URL}/health")
            response = await client.get(f"{BASE_URL}/health")
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                log_success(f"健康检查通过")
                log_info(f"服务状态: {data.get('status', 'unknown')}")
                if 'websocket' in data:
                    ws = data['websocket']
                    log_info(f"WebSocket 在线用户: {ws.get('online_users', 0)}")
                    log_info(f"WebSocket 连接数: {ws.get('total_connections', 0)}")
                return True
            else:
                log_error(f"健康检查失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
    except httpx.ConnectError as e:
        log_error("连接失败", f"无法连接到服务器: {e}")
        log_info("请检查:")
        log_info("1. 云服务器是否已启动")
        log_info("2. 防火墙是否开放 8000 端口")
        log_info("3. 安全组是否允许访问")
        return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_register():
    """注册测试用户"""
    log_step(2, 10, "注册测试用户")
    global user_id
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {"username": TEST_USERNAME, "password": TEST_PASSWORD}
            log_info(f"POST {API_PREFIX}/auth/register")
            log_info(f"请求体: {payload}")
            
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/register",
                json=payload
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 201:
                data = response.json()
                user_id = data.get("id") or data.get("user_id")
                log_success(f"用户注册成功: {user_id}")
                return True
            elif response.status_code == 400:
                error_text = response.text
                log_warn(f"注册返回 400: {error_text}")
                if "already" in error_text.lower() or "exists" in error_text.lower():
                    log_info("用户已存在，继续测试登录")
                    return True
                else:
                    log_error("注册失败", error_text[:200])
                    return False
            else:
                log_error("注册失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
    except httpx.TimeoutException as e:
        log_error("请求超时", f"服务器响应时间过长: {e}")
        return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_login():
    """登录获取 Token"""
    log_step(3, 10, "登录获取 Token")
    global access_token
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {"username": TEST_USERNAME, "password": TEST_PASSWORD}
            log_info(f"POST {API_PREFIX}/auth/login")
            log_info(f"请求体: {payload}")
            log_info(f"Content-Type: application/json")
            
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/login",
                headers={"Content-Type": "application/json"},
                json=payload
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")
                if not access_token:
                    log_error("登录响应缺少 access_token", f"响应: {data}")
                    return False
                log_success("登录成功")
                log_info(f"Token: {access_token[:30]}...")
                log_info(f"Token 类型: {data.get('token_type', 'unknown')}")
                log_info(f"过期时间: {data.get('expires_in', 'unknown')} 秒")
                return True
            elif response.status_code == 401:
                log_error("登录失败", "用户名或密码错误")
                return False
            elif response.status_code == 422:
                log_error("请求格式错误", f"响应: {response.text[:200]}")
                log_info("提示: 后端可能仍使用 form-urlencoded 格式")
                return False
            else:
                log_error("登录失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
    except httpx.TimeoutException as e:
        log_error("请求超时", f"服务器响应时间过长: {e}")
        return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_create_event():
    """测试创建日程（带 type/priority 字段）"""
    log_step(4, 10, "测试创建日程（带 type/priority）")
    global event_id
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            start_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            end_time = (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat()
            
            payload = {
                "title": "云服务器测试会议",
                "description": "这是从本地发起的测试",
                "start_time": start_time,
                "end_time": end_time,
                "location": "会议室A",
                "type": "WORK",
                "priority": 3
            }
            
            log_info(f"POST {API_PREFIX}/events/")
            log_info(f"请求体: {payload}")
            
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/events/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 201:
                data = response.json()
                event_id = data.get("id")
                log_success(f"创建成功: {data.get('title')}")
                log_info(f"ID: {event_id}")
                log_info(f"Type: {data.get('type')}, Priority: {data.get('priority')}")
                
                # 验证字段
                if data.get("type") != "WORK":
                    log_warn(f"type 字段可能不正确: 期望 WORK, 得到 {data.get('type')}")
                if data.get("priority") != 3:
                    log_warn(f"priority 字段可能不正确: 期望 3, 得到 {data.get('priority')}")
                
                return True
            elif response.status_code == 401:
                log_error("认证失败", "Token 无效或过期")
                return False
            elif response.status_code == 422:
                log_error("请求格式错误", f"响应: {response.text[:200]}")
                log_info("提示: 检查 type/priority 字段格式")
                return False
            else:
                log_error("创建失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
    except httpx.TimeoutException as e:
        log_error("请求超时", f"服务器响应时间过长: {e}")
        return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_list_events():
    """测试查询日程列表"""
    log_step(5, 10, "测试查询日程列表")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            log_info(f"GET {API_PREFIX}/events/")
            
            response = await client.get(
                f"{BASE_URL}{API_PREFIX}/events/",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                items = data.get('items', [])
                log_success(f"查询成功: 共 {total} 条日程")
                if items:
                    first = items[0]
                    log_info(f"第一条: {first.get('title', 'N/A')}")
                    log_info(f"  Type: {first.get('type', 'N/A')}, Priority: {first.get('priority', 'N/A')}")
                return True
            elif response.status_code == 401:
                log_error("认证失败", "Token 无效或过期")
                return False
            else:
                log_error("查询失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
    except httpx.TimeoutException as e:
        log_error("请求超时", f"服务器响应时间过长: {e}")
        return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_update_event_status():
    """测试更新日程状态（JSON body 格式）"""
    log_step(6, 10, "测试更新日程状态（JSON body）")
    
    if not event_id:
        log_warn("没有可用的日程 ID，跳过此测试")
        return True
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {"status": "completed"}
            log_info(f"PATCH {API_PREFIX}/events/{event_id}/status")
            log_info(f"请求体: {payload}")
            log_info("注意: 使用 JSON body 格式，不是查询参数")
            
            response = await client.patch(
                f"{BASE_URL}{API_PREFIX}/events/{event_id}/status",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                log_success(f"状态更新成功: {data.get('status')}")
                return True
            elif response.status_code == 422:
                log_error("请求格式错误", f"响应: {response.text[:200]}")
                log_info("提示: 后端可能仍使用查询参数格式 (?status=completed)")
                return False
            elif response.status_code == 404:
                log_error("日程不存在", f"ID: {event_id}")
                return False
            else:
                log_error("更新失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
    except httpx.TimeoutException as e:
        log_error("请求超时", f"服务器响应时间过长: {e}")
        return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_agent_create_event():
    """测试 Agent 创建日程"""
    log_step(7, 10, "测试 Agent 创建日程")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:  # Agent 需要更长时间
            payload = {"text": "帮我安排明天下午3点的项目评审会议", "conversation_id": None}
            log_info(f"POST {API_PREFIX}/agent/process")
            log_info(f"请求体: {payload}")
            log_info("注意: 此测试会调用真实的 DeepSeek API，可能需要 10-30 秒")
            
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                reply = data.get('reply', '无回复')
                log_success(f"Agent 响应: {reply[:100]}")
                log_info(f"Action: {data.get('action')}")
                log_info(f"Entity: {data.get('entity')}")
                return True
            elif response.status_code == 401:
                error_text = response.text
                if "API key" in error_text or "api_key" in error_text:
                    log_error("Agent API Key 错误", "服务器未配置 DASHSCOPE_API_KEY")
                    log_info("请检查服务器 .env 文件是否包含:")
                    log_info("  DASHSCOPE_API_KEY=sk-xxxxx")
                else:
                    log_error("认证失败", error_text[:200])
                return False
            else:
                log_error("Agent 失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
    except httpx.TimeoutException as e:
        log_error("请求超时", f"Agent 响应时间过长: {e}")
        log_info("提示: Agent 调用可能需要 10-30 秒，请检查服务器网络连接")
        return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_create_memo():
    """测试创建备忘录"""
    log_step(8, 10, "测试创建备忘录")
    global memo_id
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "content": "云服务器测试备忘：记得检查部署状态",
                "tags": ["测试", "部署"]
            }
            log_info(f"POST {API_PREFIX}/memos/")
            log_info(f"请求体: {payload}")
            
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/memos/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 201:
                data = response.json()
                memo_id = data.get("id")
                log_success(f"创建成功: {data.get('content', '')[:30]}...")
                log_info(f"ID: {memo_id}")
                return True
            elif response.status_code == 401:
                log_error("认证失败", "Token 无效或过期")
                return False
            else:
                log_error("创建失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
    except httpx.TimeoutException as e:
        log_error("请求超时", f"服务器响应时间过长: {e}")
        return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_list_memos():
    """测试查询备忘录"""
    log_step(9, 10, "测试查询备忘录")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            log_info(f"GET {API_PREFIX}/memos/")
            
            response = await client.get(
                f"{BASE_URL}{API_PREFIX}/memos/",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                log_success(f"查询成功: 共 {total} 条备忘录")
                return True
            elif response.status_code == 401:
                log_error("认证失败", "Token 无效或过期")
                return False
            else:
                log_error("查询失败", f"状态码: {response.status_code}, 响应: {response.text[:200]}")
                return False
    except httpx.TimeoutException as e:
        log_error("请求超时", f"服务器响应时间过长: {e}")
        return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def cleanup():
    """清理测试数据"""
    log_section("清理测试数据")
    
    if not access_token:
        log_warn("没有 access_token，跳过清理")
        return
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # 删除测试日程
            if event_id:
                log_info(f"删除测试日程: {event_id}")
                response = await client.delete(
                    f"{BASE_URL}{API_PREFIX}/events/{event_id}",
                    headers=headers
                )
                if response.status_code == 204:
                    log_success("日程已删除")
                else:
                    log_warn(f"删除日程失败: {response.status_code}")
            
            # 删除测试备忘录
            if memo_id:
                log_info(f"删除测试备忘录: {memo_id}")
                response = await client.delete(
                    f"{BASE_URL}{API_PREFIX}/memos/{memo_id}",
                    headers=headers
                )
                if response.status_code == 204:
                    log_success("备忘录已删除")
                else:
                    log_warn(f"删除备忘录失败: {response.status_code}")
    except Exception as e:
        log_warn(f"清理过程中出错: {e}")


async def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("☁️ 云服务器后端烟雾测试")
    print("=" * 60)
    print(f"测试地址: {BASE_URL}")
    print(f"测试用户: {TEST_USERNAME}")
    print(f"超时设置: {TIMEOUT} 秒")
    print("⚠️ 注意: 云服务器可能有网络延迟，请耐心等待")
    print("=" * 60)
    
    results = []
    
    # 基础连接测试
    results.append(("健康检查", await test_health()))
    
    if not results[-1][1]:
        print("\n" + "=" * 60)
        print("❌ 无法连接到云服务器，终止测试")
        print("=" * 60)
        print("请检查:")
        print("1. 云服务器是否已启动")
        print("   systemctl status chronosync 或 docker ps")
        print("2. 防火墙是否开放 8000 端口")
        print("   sudo ufw status 或 sudo iptables -L")
        print("3. 安全组是否允许访问")
        print("   检查云平台控制台的安全组设置")
        print("4. 网络连接是否正常")
        print(f"   ping {BASE_URL.replace('http://', '').replace(':8000', '')}")
        return
    
    # 认证测试
    results.append(("用户注册", await test_register()))
    results.append(("用户登录", await test_login()))
    
    if not access_token:
        print("\n" + "=" * 60)
        print("❌ 无法获取 Token，终止测试")
        print("=" * 60)
        return
    
    # 功能测试
    results.append(("创建日程", await test_create_event()))
    results.append(("查询日程", await test_list_events()))
    results.append(("更新状态", await test_update_event_status()))
    results.append(("Agent创建日程", await test_agent_create_event()))
    results.append(("创建备忘录", await test_create_memo()))
    results.append(("查询备忘录", await test_list_memos()))
    
    # 清理
    await cleanup()
    
    # 汇总结果
    log_section("测试结果汇总")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 所有测试通过！云服务器后端工作正常")
    elif passed >= total * 0.7:
        print("⚠️ 大部分测试通过，可能有部分功能异常")
    else:
        print("❌ 大量测试失败，请检查服务器配置")
    
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试运行失败: {e}")
        traceback.print_exc()
        sys.exit(1)
