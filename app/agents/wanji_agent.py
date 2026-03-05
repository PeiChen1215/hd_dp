"""
万机 Agent - LangChain 0.2.x + LangGraph 版本
基于 create_react_agent，直接调用后端 Service 层
"""

import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dateutil import parser

from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app import schemas
from app.services import event_service, memo_service
from app.agents.base import BaseAgent


# ============ 工具输入模型定义 ============

class AddScheduleInput(BaseModel):
    """创建日程输入"""
    title: str = Field(description="日程标题")
    start_time: str = Field(description="开始时间，可以是自然语言如'明天下午3点'或ISO格式")
    end_time: Optional[str] = Field(default=None, description="结束时间，可选")
    description: Optional[str] = Field(default=None, description="日程描述，可选")
    location: Optional[str] = Field(default=None, description="地点，可选")


class DeleteScheduleInput(BaseModel):
    """删除日程输入"""
    title: str = Field(description="要删除的日程标题关键词")


class UpdateScheduleInput(BaseModel):
    """更新日程输入"""
    title: str = Field(description="要修改的日程标题")
    new_start_time: Optional[str] = Field(default=None, description="新的开始时间，可选")
    new_end_time: Optional[str] = Field(default=None, description="新的结束时间，可选")


class QueryScheduleInput(BaseModel):
    """查询日程输入"""
    date: str = Field(description="日期描述，如'明天'、'2026-03-10'、'下周'")


class AddMemoInput(BaseModel):
    """创建备忘录输入"""
    content: str = Field(description="备忘录内容")
    tags: Optional[List[str]] = Field(default=None, description="标签列表，可选")


class StatisticsInput(BaseModel):
    """统计输入"""
    query: str = Field(description="统计问题描述")


# ============ Agent 主类 ============

class WanjiAgent(BaseAgent):
    """
    万机 - 智能日程助手（LangGraph 版本）
    
    功能：
    - 自然语言理解（中英文）
    - 日程管理：创建、查询、修改、删除
    - 备忘录管理：创建、查询
    - 冲突检测和智能建议
    - 多轮对话记忆
    """
    
    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model=settings.DASHSCOPE_MODEL,
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_API_BASE,
            temperature=0,
            timeout=60
        )
        
        # 创建工具
        self.tools = self._create_tools()
        
        # 创建 ReAct Agent（LangGraph 方式）
        self.agent = self._create_agent()
        
        # 对话历史（简单实现）
        self.chat_history = []
    
    def _create_tools(self) -> List[StructuredTool]:
        """创建工具集"""
        
        async def add_schedule(
            title: str,
            start_time: str,
            end_time: Optional[str] = None,
            description: Optional[str] = None,
            location: Optional[str] = None
        ) -> str:
            """创建新日程"""
            try:
                start_dt = self._parse_time(start_time)
                end_dt = self._parse_time(end_time) if end_time else None
                
                event_in = schemas.EventCreate(
                    title=title,
                    description=description,
                    start_time=start_dt,
                    end_time=end_dt,
                    location=location
                )
                
                conflicts = await self._detect_conflict(start_dt, end_dt)
                if conflicts:
                    suggestion = await self._find_next_slot(start_dt)
                    return f"时间冲突！已有日程：{conflicts[0].title}。建议改到：{suggestion}"
                
                event = await event_service.create_event(self.db, self.user_id, event_in)
                return f"已创建日程：{event.title}，时间：{event.start_time.strftime('%Y-%m-%d %H:%M')}"
                
            except Exception as e:
                return f"创建失败：{str(e)}"
        
        async def delete_schedule(title: str) -> str:
            """删除日程"""
            try:
                events, _ = await event_service.list_events(self.db, self.user_id, page=1, size=100)
                
                target = None
                for event in events:
                    if title in event.title or event.title in title:
                        target = event
                        break
                
                if not target:
                    return f"未找到标题包含 '{title}' 的日程"
                
                success = await event_service.delete_event(self.db, str(target.id), self.user_id)
                return f"已删除日程：{target.title}" if success else "删除失败"
                
            except Exception as e:
                return f"删除失败：{str(e)}"
        
        async def update_schedule(
            title: str,
            new_start_time: Optional[str] = None,
            new_end_time: Optional[str] = None
        ) -> str:
            """更新日程"""
            try:
                events, _ = await event_service.list_events(self.db, self.user_id, page=1, size=100)
                
                target = None
                for event in events:
                    if title in event.title or event.title in title:
                        target = event
                        break
                
                if not target:
                    return f"未找到标题包含 '{title}' 的日程"
                
                update_data = schemas.EventUpdate()
                if new_start_time:
                    update_data.start_time = self._parse_time(new_start_time)
                if new_end_time:
                    update_data.end_time = self._parse_time(new_end_time)
                
                updated = await event_service.update_event(self.db, str(target.id), self.user_id, update_data)
                return f"已更新日程：{updated.title}" if updated else "更新失败"
                
            except Exception as e:
                return f"更新失败：{str(e)}"
        
        async def query_schedule(date: str) -> str:
            """查询日程"""
            try:
                start, end = self._parse_date_range(date)
                events, total = await event_service.list_events(
                    self.db, self.user_id, start_date=start, end_date=end
                )
                
                if not events:
                    return f"{date} 没有安排"
                
                lines = [f"{date} 共有 {total} 项安排："]
                for i, event in enumerate(events, 1):
                    status_icon = "已完成" if event.status == "completed" else "待办"
                    end_str = event.end_time.strftime('%H:%M') if event.end_time else '?'
                    lines.append(f"{i}. [{status_icon}] {event.title} ({event.start_time.strftime('%H:%M')}-{end_str})")
                
                return "\n".join(lines)
                
            except Exception as e:
                return f"查询失败：{str(e)}"
        
        async def add_memo(content: str, tags: Optional[List[str]] = None) -> str:
            """创建备忘录"""
            try:
                memo_in = schemas.MemoCreate(content=content, tags=tags or [])
                memo = await memo_service.create_memo(self.db, self.user_id, memo_in)
                return f"已创建备忘录：{memo.content[:30]}..."
                
            except Exception as e:
                return f"创建失败：{str(e)}"
        
        async def query_memo() -> str:
            """查询备忘录"""
            try:
                memos, total = await memo_service.list_memos(self.db, self.user_id)
                
                if not memos:
                    return "暂无备忘录"
                
                lines = [f"共有 {total} 条备忘录："]
                for i, memo in enumerate(memos[:5], 1):
                    tags_str = f" [{', '.join(memo.tags)}]" if memo.tags else ""
                    lines.append(f"{i}. {memo.content[:40]}...{tags_str}")
                
                if total > 5:
                    lines.append(f"... 还有 {total - 5} 条")
                
                return "\n".join(lines)
                
            except Exception as e:
                return f"查询失败：{str(e)}"
        
        async def statistics(query: str) -> str:
            """统计"""
            try:
                if "日程" in query or "会议" in query or "安排" in query:
                    events, total = await event_service.list_events(self.db, self.user_id)
                    return f"您共有 {total} 条日程记录"
                elif "备忘" in query or "笔记" in query:
                    memos, total = await memo_service.list_memos(self.db, self.user_id)
                    return f"您共有 {total} 条备忘录"
                else:
                    events, event_total = await event_service.list_events(self.db, self.user_id)
                    memos, memo_total = await memo_service.list_memos(self.db, self.user_id)
                    return f"您共有 {event_total} 条日程，{memo_total} 条备忘录"
                    
            except Exception as e:
                return f"统计失败：{str(e)}"
        
        return [
            StructuredTool.from_function(
                coroutine=add_schedule,
                name="add_schedule",
                description="创建新日程。示例：'帮我安排明天下午3点的会议'",
                args_schema=AddScheduleInput
            ),
            StructuredTool.from_function(
                coroutine=delete_schedule,
                name="delete_schedule",
                description="删除日程。示例：'删除明天的会议'",
                args_schema=DeleteScheduleInput
            ),
            StructuredTool.from_function(
                coroutine=update_schedule,
                name="update_schedule",
                description="修改日程。示例：'把会议改到后天4点'",
                args_schema=UpdateScheduleInput
            ),
            StructuredTool.from_function(
                coroutine=query_schedule,
                name="query_schedule",
                description="查询日程。示例：'明天有什么安排'",
                args_schema=QueryScheduleInput
            ),
            StructuredTool.from_function(
                coroutine=add_memo,
                name="add_memo",
                description="创建备忘录。示例：'记住买牛奶'",
                args_schema=AddMemoInput
            ),
            StructuredTool.from_function(
                coroutine=query_memo,
                name="query_memo",
                description="查询备忘录"
            ),
            StructuredTool.from_function(
                coroutine=statistics,
                name="statistics",
                description="统计信息。示例：'我有多少条日程'",
                args_schema=StatisticsInput
            ),
        ]
    
    def _create_agent(self):
        """创建 ReAct Agent（LangGraph）"""
        
        system_prompt = """你是一个智能日程助手，名字叫"万机"。

你的能力：
- 理解中英文自然语言
- 自动解析时间（支持相对时间如"明天下午3点"）
- 管理用户的日程和备忘录
- 遇到冲突给出建议

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
- 时间可以是自然语言（如"明天下午3点"）或 ISO 8601 格式
- 如果用户输入的时间不明确，请询问确认
- 日程冲突时，给出替代建议
"""
        
        # 使用 langgraph 的 create_react_agent
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt
        )
    
    def _parse_time(self, time_str: str) -> datetime:
        """解析时间"""
        if isinstance(time_str, datetime):
            return time_str
        if not time_str:
            return datetime.now()
        
        now = datetime.now()
        time_str = str(time_str).strip()
        
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
        """解析日期范围"""
        now = datetime.now()
        date_desc = str(date_desc).strip()
        
        if "明天" in date_desc:
            start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        elif "后天" in date_desc:
            start = (now + timedelta(days=2)).replace(hour=0, minute=0, second=0)
        elif "今天" in date_desc:
            start = now.replace(hour=0, minute=0, second=0)
        elif "下周" in date_desc:
            start = (now + timedelta(days=7)).replace(hour=0, minute=0, second=0)
        else:
            dt = parser.parse(date_desc, fuzzy=True)
            start = dt.replace(hour=0, minute=0, second=0)
        
        return start, start + timedelta(days=1)
    
    async def _detect_conflict(self, start_time: datetime, end_time: Optional[datetime]) -> list:
        """检测冲突"""
        if not end_time:
            end_time = start_time + timedelta(hours=1)
        
        events, _ = await event_service.list_events(
            self.db, self.user_id, start_date=start_time, end_date=end_time
        )
        return events
    
    async def _find_next_slot(self, start_time: datetime, duration_minutes: int = 60) -> str:
        """找下一个可用时段"""
        for i in range(1, 6):
            new_start = start_time + timedelta(hours=i)
            new_end = new_start + timedelta(minutes=duration_minutes)
            conflicts = await self._detect_conflict(new_start, new_end)
            if not conflicts:
                return new_start.strftime("%Y-%m-%d %H:%M")
        return "无法找到可用时间段"
    
    async def process(self, text: str, context: dict) -> dict:
        """处理自然语言指令"""
        try:
            # 构建消息
            messages = []
            
            # 添加历史记录（如果有）
            for msg in self.chat_history[-6:]:  # 最近3轮
                messages.append(msg)
            
            # 添加当前输入
            messages.append(HumanMessage(content=text))
            
            # 调用 agent
            result = await self.agent.ainvoke({"messages": messages})
            
            # 获取最后一条 AI 消息
            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            reply = ai_messages[-1].content if ai_messages else "处理完成"
            
            # 保存到历史
            self.chat_history.append(HumanMessage(content=text))
            self.chat_history.append(AIMessage(content=reply))
            
            # 限制历史长度
            if len(self.chat_history) > 20:
                self.chat_history = self.chat_history[-20:]
            
            return {
                "action": "process",
                "entity": "mixed",
                "data": {},
                "reply": reply
            }
            
        except Exception as e:
            return {
                "action": "error",
                "entity": "none",
                "data": {},
                "reply": f"处理出错：{str(e)}"
            }
