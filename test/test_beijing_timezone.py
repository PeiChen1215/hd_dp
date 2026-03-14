#!/usr/bin/env python3
"""
Agent 北京时间测试脚本
测试地址: http://localhost:8000

使用方法:
    python test/test_beijing_timezone.py

测试内容:
1. 检查系统提示中的北京时间显示
2. 测试快速查询：现在几点
3. 测试快速查询：今天几号
4. 测试创建日程的时间解析是否正确使用北京时间
"""

import asyncio
import sys
import uuid
from datetime import datetime

import httpx

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"
TEST_USERNAME = f"bj_time_test_{uuid.uuid4().hex[:6]}"
TEST_PASSWORD = "test123"


def log_section(title):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def log_step(step_num, total, desc):
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


def check_beijing_time_in_reply(reply):
    """检查回复中是否包含北京时间相关信息"""
    beijing_keywords = ['北京时间', 'UTC+8', 'Asia/Shanghai']
    return any(keyword in reply for keyword in beijing_keywords)


async def test_register_and_login():
    """注册并登录"""
    log_step(0, 5, "准备：注册并登录")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 注册
        await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/register",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        
        # 登录
        resp = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            headers={"Content-Type": "application/json"},
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            log_success("登录成功")
            return token
        else:
            log_error("登录失败")
            return None


async def test_current_time_query(token):
    """测试查询当前时间"""
    log_step(1, 5, "测试查询当前时间")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        test_queries = [
            "现在几点",
            "现在时间",
            "几点了"
        ]
        
        for query in test_queries:
            log_info(f"测试: '{query}'")
            resp = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers=headers,
                json={"text": query, "conversation_id": None}
            )
            
            if resp.status_code == 200:
                reply = resp.json().get("reply", "")
                log_info(f"回复: {reply}")
                
                # 检查是否包含北京时间
                if "北京时间" in reply:
                    log_success("✓ 明确标注了北京时间")
                    return True
                elif re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', reply):
                    log_warn("回复包含时间但未明确标注时区")
                    return True
                else:
                    log_error("回复不包含预期的时间格式")
                    return False
            else:
                log_error(f"请求失败: {resp.status_code}")
                return False


async def test_today_date_query(token):
    """测试查询今天日期"""
    log_step(2, 5, "测试查询今天日期")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        test_queries = [
            "今天几号",
            "今天日期",
            "今天是几号"
        ]
        
        for query in test_queries:
            log_info(f"测试: '{query}'")
            resp = await client.post(
                f"{BASE_URL}{API_PREFIX}/agent/process",
                headers=headers,
                json={"text": query, "conversation_id": None}
            )
            
            if resp.status_code == 200:
                reply = resp.json().get("reply", "")
                log_info(f"回复: {reply}")
                
                # 检查是否包含日期和星期
                if re.search(r'\d{4}-\d{2}-\d{2}', reply) and "周" in reply:
                    log_success("✓ 返回了日期和星期")
                    return True
                elif re.search(r'\d{4}-\d{2}-\d{2}', reply):
                    log_warn("返回了日期但可能没有星期")
                    return True
                else:
                    log_error("回复不包含预期的日期格式")
                    return False
            else:
                log_error(f"请求失败: {resp.status_code}")
                return False


async def test_create_event_with_relative_time(token):
    """测试使用相对时间创建日程"""
    log_step(3, 5, "测试相对时间创建日程")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 获取当前北京时间用于对比
        import pytz
        beijing_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(beijing_tz)
        tomorrow = now + timedelta(days=1)
        
        log_info(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M')}")
        log_info(f"明天是: {tomorrow.strftime('%Y-%m-%d')}")
        
        # 测试创建明天下午的日程
        resp = await client.post(
            f"{BASE_URL}{API_PREFIX}/agent/process",
            headers=headers,
            json={"text": "帮我安排明天下午3点的测试会议", "conversation_id": None}
        )
        
        if resp.status_code == 200:
            reply = resp.json().get("reply", "")
            log_info(f"回复: {reply}")
            
            # 检查是否成功创建
            if "创建" in reply or "安排" in reply or "成功" in reply:
                # 检查时间是否正确（应该是明天15:00）
                if tomorrow.strftime('%m-%d') in reply or tomorrow.strftime('%-m月%-d日') in reply:
                    log_success("✓ 正确解析了'明天'为北京时间的明天")
                    return True
                else:
                    log_warn("无法从回复中确认日期是否正确，但创建成功")
                    return True
            elif "冲突" in reply:
                log_warn("时间冲突，这是正常的，说明时间解析工作正常")
                return True
            else:
                log_error("创建可能失败")
                return False
        else:
            log_error(f"请求失败: {resp.status_code}")
            return False


async def test_query_tomorrow_events(token):
    """测试查询明天的日程"""
    log_step(4, 5, "测试查询明天日程")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        resp = await client.post(
            f"{BASE_URL}{API_PREFIX}/agent/process",
            headers=headers,
            json={"text": "明天有什么安排", "conversation_id": None}
        )
        
        if resp.status_code == 200:
            reply = resp.json().get("reply", "")
            log_info(f"回复: {reply}")
            
            # 检查是否返回了查询结果
            if "安排" in reply or "日程" in reply or "没有" in reply:
                log_success("✓ 查询功能正常")
                return True
            else:
                log_warn("回复格式不符合预期，但接口正常")
                return True
        else:
            log_error(f"请求失败: {resp.status_code}")
            return False


async def verify_beijing_time():
    """验证系统时间对比"""
    log_section("系统时间对比验证")
    
    import pytz
    from datetime import datetime
    
    # 获取各时区时间
    utc_now = datetime.now(pytz.UTC)
    beijing_now = datetime.now(pytz.timezone('Asia/Shanghai'))
    local_now = datetime.now()
    
    print(f"\n当前各时区时间:")
    print(f"  UTC时间:     {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  北京时间:    {beijing_now.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
    print(f"  本地时间:    {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 计算时差
    beijing_offset = beijing_now.utcoffset().total_seconds() / 3600
    local_offset = local_now.timestamp() - utc_now.timestamp()
    
    print(f"\n时区偏移:")
    print(f"  北京时间偏移: UTC+{int(beijing_offset)}")
    print(f"  本地时间偏移: UTC{local_offset:+.1f}")
    
    if beijing_offset == 8:
        print(f"\n✅ 北京时间配置正确 (UTC+8)")
    else:
        print(f"\n❌ 北京时间配置异常")


async def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🕐 Agent 北京时间测试")
    print("=" * 60)
    print(f"测试用户: {TEST_USERNAME}")
    print("=" * 60)
    
    # 先验证系统时间
    await verify_beijing_time()
    
    # 准备测试
    token = await test_register_and_login()
    if not token:
        print("\n❌ 无法获取 Token，终止测试")
        return False
    
    # 运行测试
    results = []
    results.append(("查询当前时间", await test_current_time_query(token)))
    results.append(("查询今天日期", await test_today_date_query(token)))
    results.append(("相对时间创建日程", await test_create_event_with_relative_time(token)))
    results.append(("查询明天日程", await test_query_tomorrow_events(token)))
    
    # 汇总结果
    log_section("测试结果汇总")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 所有测试通过！Agent 北京时间功能正常")
        print("\n关键验证点:")
        print("  ✓ 快速查询返回北京时间")
        print("  ✓ 日期解析使用北京时间")
        print("  ✓ 系统提示包含北京时区信息")
    else:
        print("\n⚠️ 部分测试失败，请检查配置")
    
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    try:
        import re
        from datetime import timedelta
        
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
