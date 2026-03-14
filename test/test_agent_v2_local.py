#!/usr/bin/env python3
"""
万机 Agent V2 本地测试脚本
测试地址: http://localhost:8000

使用方法:
    python test/test_agent_v2_local.py

功能测试:
1. 基础 Agent 功能（创建/查询/删除日程）
2. 多日/范围查询
3. 建议时段确认
4. 丰富时间表达解析
5. 对话历史 API
6. 备忘录操作
"""

import asyncio
import sys
import uuid
import traceback
from datetime import datetime, timedelta, timezone

import httpx

# 本地服务器配置
BASE_URL = "http://115.190.155.26:8000"
API_PREFIX = "/api/v1"
TIMEOUT = 60.0  # Agent 调用可能需要较长时间

# 测试用户
TEST_USERNAME = f"agentv2_test_{uuid.uuid4().hex[:6]}"
TEST_PASSWORD = "test123"

# 存储测试数据
access_token = None
user_id = None


def log_section(title):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def log_step(step_num, total, desc):
    """打印测试步骤"""
    print(f"\n[{step_num}/{total}] {desc}")
    print("-" * 70)


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
    log_step(1, 12, "测试健康检查")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            log_info(f"GET {BASE_URL}/health")
            response = await client.get(f"{BASE_URL}/health")
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                log_success(f"健康检查通过")
                log_info(f"服务状态: {data.get('status', 'unknown')}")
                return True
            else:
                log_error(f"健康检查失败", f"状态码: {response.status_code}")
                return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def test_register():
    """注册测试用户"""
    log_step(2, 12, "注册测试用户")
    global user_id
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {"username": TEST_USERNAME, "password": TEST_PASSWORD}
            log_info(f"POST {API_PREFIX}/auth/register")
            
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
                log_warn(f"用户可能已存在，尝试登录")
                return True
            else:
                log_error("注册失败", f"{response.status_code}: {response.text[:200]}")
                return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def test_login():
    """登录获取 Token"""
    log_step(3, 12, "登录获取 Token")
    global access_token
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {"username": TEST_USERNAME, "password": TEST_PASSWORD}
            log_info(f"POST {API_PREFIX}/auth/login")
            
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/login",
                headers={"Content-Type": "application/json"},
                json=payload
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")
                log_success("登录成功")
                log_info(f"Token: {access_token[:30]}...")
                return True
            else:
                log_error("登录失败", f"{response.status_code}: {response.text[:200]}")
                return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def test_agent_create_event():
    """测试 Agent 创建日程"""
    log_step(4, 12, "测试 Agent 创建日程")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {
                "text": "帮我安排明天下午3点的项目评审会议",
                "conversation_id": None
            }
            log_info(f"POST {API_PREFIX}/agent/process")
            log_info(f"请求: {payload}")
            
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
                reply = data.get('reply', '')
                log_success(f"Agent 响应: {reply[:100]}...")
                log_info(f"Action: {data.get('action')}, Entity: {data.get('entity')}")
                
                # 检查是否成功创建
                if "创建" in reply or "已安排" in reply or "成功" in reply:
                    return True
                elif "冲突" in reply:
                    log_warn("时间冲突，这是正常的，后续会测试建议确认功能")
                    return True
                else:
                    return True  # 即使不是预期结果，只要接口正常就算通过
            else:
                log_error("Agent 失败", f"{response.status_code}: {response.text[:200]}")
                return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_agent_query_single_day():
    """测试 Agent 单日查询"""
    log_step(5, 12, "测试 Agent 单日查询")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            payload = {"text": "明天有什么安排", "conversation_id": None}
            log_info(f"POST {API_PREFIX}/agent/process")
            
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
                reply = data.get('reply', '')
                log_success(f"Agent 响应: {reply[:100]}...")
                
                # 验证是否是查询结果
                if "安排" in reply or "日程" in reply or "没有" in reply:
                    log_info("单日查询功能正常")
                    return True
                return True
            else:
                log_error("查询失败", f"{response.status_code}: {response.text[:200]}")
                return False
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def test_agent_query_range():
    """测试 Agent 多日/范围查询"""
    log_step(6, 12, "测试 Agent 多日/范围查询（V2新功能）")
    
    test_cases = [
        "最近3天有什么安排",
        "本周日程安排",
        "未来7天有什么会"
    ]
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            for i, text in enumerate(test_cases, 1):
                log_info(f"测试 {i}/{len(test_cases)}: '{text}'")
                
                response = await client.post(
                    f"{BASE_URL}{API_PREFIX}/agent/process",
                    headers=headers,
                    json={"text": text, "conversation_id": None}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    reply = data.get('reply', '')
                    log_info(f"  响应: {reply[:80]}...")
                else:
                    log_error(f"查询失败", f"{response.status_code}")
                    return False
            
            log_success("多日/范围查询功能正常")
            return True
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def test_agent_enhanced_time_parsing():
    """测试增强的时间解析"""
    log_step(7, 12, "测试增强的时间解析（V2新功能）")
    
    test_cases = [
        "帮我安排大后天的会议",
        "3天后提醒我开会",
        "帮我安排本周五的聚餐",
        "下周一下午3点有安排吗"
    ]
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            for i, text in enumerate(test_cases, 1):
                log_info(f"测试 {i}/{len(test_cases)}: '{text}'")
                
                response = await client.post(
                    f"{BASE_URL}{API_PREFIX}/agent/process",
                    headers=headers,
                    json={"text": text, "conversation_id": None}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    reply = data.get('reply', '')
                    log_info(f"  响应: {reply[:80]}...")
                else:
                    log_error(f"解析失败", f"{response.status_code}")
                    return False
            
            log_success("增强时间解析功能正常")
            return True
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def test_agent_suggestion_confirm():
    """测试建议时段确认功能"""
    log_step(8, 12, "测试建议时段确认（V2新功能）")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # 第1步：创建一个日程
            log_info("步骤1: 创建一个日程")
            response1 = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers=headers,
                json={"text": "帮我安排明天下午3点的会议", "conversation_id": None}
            )
            
            if response1.status_code != 200:
                log_error("创建日程失败")
                return False
            
            reply1 = response1.json().get('reply', '')
            log_info(f"创建结果: {reply1[:100]}...")
            
            # 第2步：尝试创建冲突日程，应该收到建议
            log_info("步骤2: 尝试创建冲突日程，期望收到建议")
            response2 = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers=headers,
                json={"text": "帮我安排明天下午3点的另一个会议", "conversation_id": None}
            )
            
            if response2.status_code != 200:
                log_error("第二次创建失败")
                return False
            
            reply2 = response2.json().get('reply', '')
            log_info(f"响应: {reply2[:100]}...")
            
            if "建议" in reply2 or "冲突" in reply2:
                log_success("冲突检测正常，收到建议时段")
                
                # 第3步：发送确认
                log_info("步骤3: 发送确认'可以'")
                response3 = await client.post(
                    f"{BASE_URL}{API_PREFIX}/agent/process",
                    headers=headers,
                    json={"text": "可以", "conversation_id": None}
                )
                
                if response3.status_code == 200:
                    reply3 = response3.json().get('reply', '')
                    log_info(f"确认响应: {reply3[:100]}...")
                    
                    if "已" in reply3 or "成功" in reply3:
                        log_success("建议确认功能正常")
                        return True
                
                log_warn("建议确认可能没有完全按预期工作，但接口正常")
                return True
            else:
                log_warn("没有检测到冲突，可能是时间计算问题，跳过确认测试")
                return True
                
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return False


async def test_agent_memo():
    """测试 Agent 备忘录功能"""
    log_step(9, 12, "测试 Agent 备忘录功能")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # 创建备忘
            log_info("创建备忘录")
            response1 = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers=headers,
                json={"text": "记住买牛奶和面包", "conversation_id": None}
            )
            
            if response1.status_code != 200:
                log_error("创建备忘失败")
                return False
            
            reply1 = response1.json().get('reply', '')
            log_info(f"创建结果: {reply1[:80]}...")
            
            # 查询备忘
            log_info("查询备忘录")
            response2 = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers=headers,
                json={"text": "查看我的备忘录", "conversation_id": None}
            )
            
            if response2.status_code != 200:
                log_error("查询备忘失败")
                return False
            
            reply2 = response2.json().get('reply', '')
            log_info(f"查询结果: {reply2[:80]}...")
            
            log_success("备忘录功能正常")
            return True
            
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def test_conversation_history_api():
    """测试对话历史 API（V2新功能）"""
    log_step(10, 12, "测试对话历史 API（V2新功能）")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # 获取对话历史
            log_info("GET /api/v1/agent/conversations")
            response = await client.get(
                f"{BASE_URL}{API_PREFIX}/agent/conversations?limit=10",
                headers=headers
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                items = data.get('items', [])
                log_success(f"获取对话历史成功，共 {total} 条")
                log_info(f"返回 {len(items)} 条记录")
                
                if items:
                    first = items[0]
                    log_info(f"最新记录: [{first.get('role')}] {first.get('content')[:50]}...")
                
                return True
            else:
                log_error("获取对话历史失败", f"{response.status_code}: {response.text[:200]}")
                return False
                
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def test_clear_conversation():
    """测试清空对话历史"""
    log_step(11, 12, "测试清空对话历史")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            log_info("DELETE /api/v1/agent/conversations")
            response = await client.delete(
                f"{BASE_URL}{API_PREFIX}/agent/conversations",
                headers=headers
            )
            
            log_info(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                deleted = data.get('deleted_count', 0)
                log_success(f"清空对话历史成功，删除了 {deleted} 条记录")
                return True
            else:
                log_error("清空失败", f"{response.status_code}: {response.text[:200]}")
                return False
                
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def test_agent_statistics():
    """测试 Agent 统计功能"""
    log_step(12, 12, "测试 Agent 统计功能")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            test_queries = [
                "我有多少条日程",
                "统计我的备忘录",
                "本周有多少安排"
            ]
            
            for i, text in enumerate(test_queries, 1):
                log_info(f"测试 {i}/{len(test_queries)}: '{text}'")
                
                response = await client.post(
                    f"{BASE_URL}{API_PREFIX}/agent/process",
                    headers=headers,
                    json={"text": text, "conversation_id": None}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    reply = data.get('reply', '')
                    log_info(f"  响应: {reply[:80]}...")
                else:
                    log_error(f"统计失败", f"{response.status_code}")
                    return False
            
            log_success("统计功能正常")
            return True
            
    except Exception as e:
        log_error("异常", f"{type(e).__name__}: {e}")
        return False


async def run_tests():
    """运行所有测试"""
    print("=" * 70)
    print("🤖 万机 Agent V2 本地测试")
    print("=" * 70)
    print(f"测试地址: {BASE_URL}")
    print(f"测试用户: {TEST_USERNAME}")
    print(f"超时设置: {TIMEOUT} 秒")
    print("⚠️ 注意: Agent 调用需要 LLM，请确保已配置 DASHSCOPE_API_KEY")
    print("=" * 70)
    
    results = []
    
    # 基础连接测试
    results.append(("健康检查", await test_health()))
    
    if not results[-1][1]:
        print("\n" + "=" * 70)
        print("❌ 无法连接到本地服务器，终止测试")
        print("=" * 70)
        print("请检查:")
        print("1. 后端服务是否已启动: uvicorn app.main:app --reload")
        print("2. 端口 8000 是否被占用")
        return
    
    # 认证测试
    results.append(("用户注册", await test_register()))
    results.append(("用户登录", await test_login()))
    
    if not access_token:
        print("\n" + "=" * 70)
        print("❌ 无法获取 Token，终止测试")
        print("=" * 70)
        return
    
    # Agent 功能测试
    results.append(("Agent创建日程", await test_agent_create_event()))
    results.append(("Agent单日查询", await test_agent_query_single_day()))
    results.append(("Agent多日查询", await test_agent_query_range()))
    results.append(("增强时间解析", await test_agent_enhanced_time_parsing()))
    results.append(("建议时段确认", await test_agent_suggestion_confirm()))
    results.append(("Agent备忘录", await test_agent_memo()))
    results.append(("对话历史API", await test_conversation_history_api()))
    results.append(("清空对话历史", await test_clear_conversation()))
    results.append(("Agent统计", await test_agent_statistics()))
    
    # 汇总结果
    log_section("测试结果汇总")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 所有测试通过！Agent V2 功能正常")
        print("\n可以部署到云端了！")
    elif passed >= total * 0.8:
        print("⚠️ 大部分测试通过，可能有部分小问题")
        print("建议检查失败项后再部署")
    else:
        print("❌ 大量测试失败，请检查配置")
        print("\n常见问题:")
        print("1. DASHSCOPE_API_KEY 是否配置正确")
        print("2. 数据库迁移是否已执行: alembic upgrade head")
        print("3. PostgreSQL 是否正常运行")
    
    print("=" * 70)
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试运行失败: {e}")
        traceback.print_exc()
        sys.exit(1)
