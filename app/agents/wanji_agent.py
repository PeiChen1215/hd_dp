"""
万机 Agent - 深度集成版本
基于 LangChain + DeepSeek，直接调用后端 Service 层
"""

import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dateutil import parser

from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app import schemas
from app.services import event_service, memo_service
from app.agents.base import BaseAgent


class WanjiAgent(BaseAgent):
    """
    万机 - 智能日程助手
    
    功能：
    - 自然语言理解（中英文）
    - 日程管理：创建、查询、修改、删除
    - 备忘录管理：创建、查询、删除
    - 冲突检测和智能建议
    - 多轮对话记忆
    """
    
    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model=settings.DASHSCOPE_MODEL,
            openai_api_key=settings.DASHSCOPE_API_KEY,
            openai_api_base=settings.DASHSCOPE_API_BASE,
            temperature=0,
            timeout=60
        )
        
        # 初始化工具
        self.tools = self._create_tools()
        
        # 系统提示词
        self.system_prompt = """你是一个智能日程助手，名字叫"万机"。

你的能力：
- 理解中英文自然语言
- 自动解析时间（支持相对时间如"明天下午3点"）
- 管理用户的日程和备忘录
- 遇到冲突给出建议
- 可以统计历史行为

工具使用规则：
1. 当用户想要创建日程时，调用 add_schedule 工具
2. 当用户想要删除日程时，调用 delete_schedule 工具
3. 当用户想要修改日程时，调用 update_schedule 工具
4. 当用户想要查询日程时，调用 query_schedule 工具
5. 当用户想要创建备忘录时，调用 add_memo 工具
6. 当用户想要查询备忘录时，调用 query_memo 工具
7. 当用户问统计问题时，调用 statistics 工具

重要：
- 不要要求用户提供 JSON，从自然语言中解析字段
- 时间字段必须是 ISO 8601 格式（如 2026-03-10T14:00:00）
- 如果用户输入的时间不明确，请询问确认
- 日程冲突时，给出替代建议
"""
        
        # 初始化 Agent
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.OPENAI_FUNCTIONS,
            memory=self.memory,
            verbose=True,
            agent_kwargs={"system_message": self.system_prompt},
            handle_parsing_errors=True
        )
    
    def _create_tools(self):
        """创建 Agent 工具集"""
        
        @tool(description="创建日程。示例：'帮我安排明天下午3点的会议'。参数：title(标题), start_time(ISO格式), end_time(ISO格式), description(可选), location(可选)")
        async def add_schedule(data: str) -> str:
            """创建新日程"""
            try:
                params = json.loads(data) if isinstance(data, str) else data
                
                # 构建 EventCreate schema
                event_in = schemas.EventCreate(
                    title=params.get("title", "未命名日程"),
                    description=params.get("description"),
                    start_time=self._parse_time(params.get("start_time")),
                    end_time=self._parse_time(params.get("end_time")) if params.get("end_time") else None,
                    location=params.get("location")
                )
                
                # 检查冲突
                conflicts = await self._detect_conflict(event_in.start_time, event_in.end_time)
                if conflicts:
                    suggestion = await self._find_next_slot(event_in.start_time)
                    return f"⚠️ 时间冲突！已有日程：{conflicts[0].title}。建议改到：{suggestion}"
                
                # 创建日程
                event = await event_service.create_event(self.db, self.user_id, event_in)
                return f"✅ 已创建日程：{event.title}，时间：{event.start_time}"
                
            except Exception as e:
                return f"❌ 创建失败：{str(e)}"
        
        @tool(description="删除日程。示例：'删除明天的会议'。参数：title(日程标题)")
        async def delete_schedule(title: str) -> str:
            """删除指定标题的日程"""
            try:
                # 先查找日程
                events, _ = await event_service.list_events(
                    self.db, self.user_id, page=1, size=100
                )
                
                target = None
                for event in events:
                    if title in event.title or event.title in title:
                        target = event
                        break
                
                if not target:
                    return f"❌ 未找到标题包含 '{title}' 的日程"
                
                # 删除
                success = await event_service.delete_event(
                    self.db, str(target.id), self.user_id
                )
                
                if success:
                    return f"✅ 已删除日程：{target.title}"
                return "❌ 删除失败"
                
            except Exception as e:
                return f"❌ 删除失败：{str(e)}"
        
        @tool(description="修改日程。示例：'把会议改到明天下午4点'。参数：title(原标题), new_start_time(新开始时间), new_end_time(新结束时间)")
        async def update_schedule(data: str) -> str:
            """修改日程时间"""
            try:
                params = json.loads(data) if isinstance(data, str) else data
                title = params.get("title")
                
                # 查找日程
                events, _ = await event_service.list_events(
                    self.db, self.user_id, page=1, size=100
                )
                
                target = None
                for event in events:
                    if title in event.title or event.title in title:
                        target = event
                        break
                
                if not target:
                    return f"❌ 未找到标题包含 '{title}' 的日程"
                
                # 构建更新数据
                update_data = schemas.EventUpdate()
                if params.get("new_start_time"):
                    update_data.start_time = self._parse_time(params["new_start_time"])
                if params.get("new_end_time"):
                    update_data.end_time = self._parse_time(params["new_end_time"])
                if params.get("new_title"):
                    update_data.title = params["new_title"]
                
                # 更新
                updated = await event_service.update_event(
                    self.db, str(target.id), self.user_id, update_data
                )
                
                if updated:
                    return f"✅ 已更新日程：{updated.title}，新时间：{updated.start_time}"
                return "❌ 更新失败"
                
            except Exception as e:
                return f"❌ 更新失败：{str(e)}"
        
        @tool(description="查询日程。示例：'明天有什么安排' 或 '查询下周的日程'。参数：date(日期描述，如'明天'、'2026-03-10')")
        async def query_schedule(date: str) -> str:
            """查询某天的日程"""
            try:
                # 解析日期
                start, end = self._parse_date_range(date)
                
                # 查询
                events, total = await event_service.list_events(
                    self.db, self.user_id, start_date=start, end_date=end
                )
                
                if not events:
                    return f"📭 {date} 没有安排"
                
                lines = [f"📅 {date} 共有 {total} 项安排："]
                for i, event in enumerate(events, 1):
                    status_icon = "✅" if event.status == "completed" else "⏳"
                    lines.append(f"{i}. {status_icon} {event.title} ({event.start_time.strftime('%H:%M')}-{event.end_time.strftime('%H:%M') if event.end_time else '?'})"
                
                return "\n".join(lines)
                
            except Exception as e:
                return f"❌ 查询失败：{str(e)}"
        
        @tool(description="创建备忘录。示例：'记住买牛奶'。参数：content(内容), tags(标签列表，可选)")
        async def add_memo(data: str) -> str:
            """创建备忘录"""
            try:
                params = json.loads(data) if isinstance(data, str) else data
                
                memo_in = schemas.MemoCreate(
                    content=params.get("content", ""),
                    tags=params.get("tags", [])
                )
                
                memo = await memo_service.create_memo(self.db, self.user_id, memo_in)
                return f"📝 已创建备忘录：{memo.content[:30]}..."
                
            except Exception as e:
                return f"❌ 创建失败：{str(e)}"
        
        @tool(description="查询备忘录。示例：'查看我的备忘录'")
        async def query_memo() -> str:
            """查询备忘录列表"""
            try:
                memos, total = await memo_service.list_memos(self.db, self.user_id)
                
                if not memos:
                    return "📭 暂无备忘录"
                
                lines = [f"📝 共有 {total} 条备忘录："]
                for i, memo in enumerate(memos[:5], 1):  # 只显示前5条
                    tags = f" [{', '.join(memo.tags)}]" if memo.tags else ""
                    lines.append(f"{i}. {memo.content[:40]}...{tags}")
                
                if total > 5:
                    lines.append(f"... 还有 {total - 5} 条")
                
                return "\n".join(lines)
                
            except Exception as e:
                return f"❌ 查询失败：{str(e)}"
        
        @tool(description="统计信息。示例：'我这周有多少会议' 或 '统计日程数量'")
        async def statistics(query: str) -> str:
            """统计日程/备忘录"""
            try:
                if "日程" in query or "会议" in query or "安排" in query:
                    events, total = await event_service.list_events(self.db, self.user_id)
                    return f"📊 您共有 {total} 条日程记录"
                
                elif "备忘" in query or "笔记" in query:
                    memos, total = await memo_service.list_memos(self.db, self.user_id)
                    return f"📊 您共有 {total} 条备忘录"
                
                else:
                    events, event_total = await event_service.list_events(self.db, self.user_id)
                    memos, memo_total = await memo_service.list_memos(self.db, self.user_id)
                    return f"📊 您共有 {event_total} 条日程，{memo_total} 条备忘录"
                    
            except Exception as e:
                return f"❌ 统计失败：{str(e)}"
        
        return [
            add_schedule,
            delete_schedule,
            update_schedule,
            query_schedule,
            add_memo,
            query_memo,
            statistics
        ]
    
    def _parse_time(self, time_str: str) -> datetime:
        """解析各种时间格式为 datetime"""
        if isinstance(time_str, datetime):
            return time_str
        if not time_str:
            return datetime.now()
        
        # 处理相对时间
        now = datetime.now()
        time_str = str(time_str).strip()
        
        # 替换相对时间描述
        replacements = {
            r"明天": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
            r"后天": (now + timedelta(days=2)).strftime("%Y-%m-%d"),
            r"今天": now.strftime("%Y-%m-%d"),
            r"下周": (now + timedelta(days=7)).strftime("%Y-%m-%d"),
        }
        
        for pattern, replacement in replacements.items():
            time_str = re.sub(pattern, replacement, time_str)
        
        return parser.parse(time_str, fuzzy=True)
    
    def _parse_date_range(self, date_desc: str) -> tuple:
        """解析日期描述为时间范围"""
        now = datetime.now()
        date_desc = str(date_desc).strip()
        
        # 相对日期映射
        if "明天" in date_desc:
            start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        elif "后天" in date_desc:
            start = (now + timedelta(days=2)).replace(hour=0, minute=0, second=0)
        elif "今天" in date_desc:
            start = now.replace(hour=0, minute=0, second=0)
        elif "下周" in date_desc:
            start = (now + timedelta(days=7)).replace(hour=0, minute=0, second=0)
        else:
            # 尝试解析具体日期
            dt = parser.parse(date_desc, fuzzy=True)
            start = dt.replace(hour=0, minute=0, second=0)
        
        end = start + timedelta(days=1)
        return start, end
    
    async def _detect_conflict(self, start_time: datetime, end_time: Optional[datetime]) -> list:
        """检测时间冲突"""
        if not end_time:
            end_time = start_time + timedelta(hours=1)
        
        # 查询时间范围内的所有日程
        events, _ = await event_service.list_events(
            self.db, self.user_id, 
            start_date=start_time, 
            end_date=end_time
        )
        
        return events
    
    async def _find_next_slot(self, start_time: datetime, duration_minutes: int = 60) -> str:
        """查找下一个可用时间段"""
        for i in range(1, 6):  # 往后找5个时段
            new_start = start_time + timedelta(hours=i)
            new_end = new_start + timedelta(minutes=duration_minutes)
            
            conflicts = await self._detect_conflict(new_start, new_end)
            if not conflicts:
                return new_start.strftime("%Y-%m-%d %H:%M")
        
        return "无法找到可用时间段"
    
    async def process(self, text: str, context: dict) -> dict:
        """
        处理自然语言指令
        
        Args:
            text: 用户输入的自然语言
            context: 上下文信息（如 conversation_id）
            
        Returns:
            标准响应格式
        """
        try:
            # 运行 Agent
            result = await self.agent.arun(text)
            
            return {
                "action": "process",
                "entity": "mixed",
                "data": {},
                "reply": str(result)
            }
            
        except Exception as e:
            return {
                "action": "error",
                "entity": "none",
                "data": {},
                "reply": f"处理出错：{str(e)}"
            }
