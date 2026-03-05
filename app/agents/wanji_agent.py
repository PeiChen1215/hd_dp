"""
万机 Agent - 简化版
基于 OpenAI API + Function Calling，直接调用后端 Service 层
兼容性好，无需复杂 LangChain 依赖
"""

import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dateutil import parser
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app import schemas
from app.services import event_service, memo_service
from app.agents.base import BaseAgent


# 工具定义（OpenAI Function Calling 格式）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_schedule",
            "description": "创建新日程。示例：'帮我安排明天下午3点的会议'。参数：title(标题), start_time(时间), end_time(结束时间，可选), description(描述，可选), location(地点，可选)",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "日程标题"},
                    "start_time": {"type": "string", "description": "开始时间，可以是自然语言如'明天下午3点'或ISO格式"},
                    "end_time": {"type": "string", "description": "结束时间，可选"},
                    "description": {"type": "string", "description": "日程描述，可选"},
                    "location": {"type": "string", "description": "地点，可选"}
                },
                "required": ["title", "start_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_schedule",
            "description": "删除日程。示例：'删除明天的会议'。参数：title(日程标题关键词)",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "要删除的日程标题关键词"}
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_schedule",
            "description": "修改日程。示例：'把会议改到后天4点'。参数：title(原标题), new_start_time(新开始时间，可选), new_end_time(新结束时间，可选)",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "要修改的日程标题"},
                    "new_start_time": {"type": "string", "description": "新的开始时间，可选"},
                    "new_end_time": {"type": "string", "description": "新的结束时间，可选"}
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_schedule",
            "description": "查询日程。示例：'明天有什么安排' 或 '下周的日程'。参数：date(日期描述)",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期描述，如'明天'、'2026-03-10'、'下周'"}
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_memo",
            "description": "创建备忘录。示例：'记住买牛奶'。参数：content(内容), tags(标签列表，可选)",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "备忘录内容"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表，可选"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_memo",
            "description": "查询备忘录。示例：'查看我的备忘录'。无需参数",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "statistics",
            "description": "统计信息。示例：'我有多少条日程' 或 '统计数量'。参数：query(统计问题)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "统计问题描述"}
                },
                "required": ["query"]
            }
        }
    }
]


SYSTEM_PROMPT = """你是一个智能日程助手，名字叫"万机"。

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
- 始终以友好的中文回复用户
"""


class WanjiAgent(BaseAgent):
    """
    万机 - 智能日程助手（简化版）
    
    功能：
    - 自然语言理解（中英文）
    - 日程管理：创建、查询、修改、删除
    - 备忘录管理：创建、查询
    - 冲突检测和智能建议
    """
    
    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        
        # 初始化 OpenAI 客户端（使用阿里云 DashScope）
        self.client = AsyncOpenAI(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_API_BASE
        )
        self.model = settings.DASHSCOPE_MODEL
    
    async def _call_llm(self, messages: List[Dict], tools: Optional[List] = None) -> Any:
        """调用 LLM"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message
    
    async def _execute_tool(self, tool_name: str, tool_args: Dict) -> str:
        """执行工具函数"""
        try:
            if tool_name == "add_schedule":
                return await self._add_schedule(**tool_args)
            elif tool_name == "delete_schedule":
                return await self._delete_schedule(**tool_args)
            elif tool_name == "update_schedule":
                return await self._update_schedule(**tool_args)
            elif tool_name == "query_schedule":
                return await self._query_schedule(**tool_args)
            elif tool_name == "add_memo":
                return await self._add_memo(**tool_args)
            elif tool_name == "query_memo":
                return await self._query_memo()
            elif tool_name == "statistics":
                return await self._statistics(**tool_args)
            else:
                return f"未知工具: {tool_name}"
        except Exception as e:
            return f"执行失败: {str(e)}"
    
    async def _add_schedule(self, title: str, start_time: str, end_time: Optional[str] = None,
                           description: Optional[str] = None, location: Optional[str] = None) -> str:
        """创建日程"""
        # 解析时间
        start_dt = self._parse_time(start_time)
        end_dt = self._parse_time(end_time) if end_time else None
        
        # 构建 EventCreate
        event_in = schemas.EventCreate(
            title=title,
            description=description,
            start_time=start_dt,
            end_time=end_dt,
            location=location
        )
        
        # 检查冲突
        conflicts = await self._detect_conflict(start_dt, end_dt)
        if conflicts:
            suggestion = await self._find_next_slot(start_dt)
            return f"⚠️ 时间冲突！已有日程：{conflicts[0].title}。建议改到：{suggestion}"
        
        # 创建
        event = await event_service.create_event(self.db, self.user_id, event_in)
        return f"✅ 已创建日程：{event.title}，时间：{event.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    async def _delete_schedule(self, title: str) -> str:
        """删除日程"""
        events, _ = await event_service.list_events(self.db, self.user_id, page=1, size=100)
        
        target = None
        for event in events:
            if title in event.title or event.title in title:
                target = event
                break
        
        if not target:
            return f"❌ 未找到标题包含 '{title}' 的日程"
        
        success = await event_service.delete_event(self.db, str(target.id), self.user_id)
        return f"✅ 已删除日程：{target.title}" if success else "❌ 删除失败"
    
    async def _update_schedule(self, title: str, new_start_time: Optional[str] = None,
                               new_end_time: Optional[str] = None) -> str:
        """更新日程"""
        events, _ = await event_service.list_events(self.db, self.user_id, page=1, size=100)
        
        target = None
        for event in events:
            if title in event.title or event.title in title:
                target = event
                break
        
        if not target:
            return f"❌ 未找到标题包含 '{title}' 的日程"
        
        update_data = schemas.EventUpdate()
        if new_start_time:
            update_data.start_time = self._parse_time(new_start_time)
        if new_end_time:
            update_data.end_time = self._parse_time(new_end_time)
        
        updated = await event_service.update_event(self.db, str(target.id), self.user_id, update_data)
        return f"✅ 已更新日程：{updated.title}" if updated else "❌ 更新失败"
    
    async def _query_schedule(self, date: str) -> str:
        """查询日程"""
        start, end = self._parse_date_range(date)
        events, total = await event_service.list_events(
            self.db, self.user_id, start_date=start, end_date=end
        )
        
        if not events:
            return f"📭 {date} 没有安排"
        
        lines = [f"📅 {date} 共有 {total} 项安排："]
        for i, event in enumerate(events, 1):
            status_icon = "✅" if event.status == "completed" else "⏳"
            end_str = event.end_time.strftime('%H:%M') if event.end_time else '?'
            lines.append(f"{i}. {status_icon} {event.title} ({event.start_time.strftime('%H:%M')}-{end_str})")
        
        return "\n".join(lines)
    
    async def _add_memo(self, content: str, tags: Optional[List[str]] = None) -> str:
        """创建备忘录"""
        memo_in = schemas.MemoCreate(content=content, tags=tags or [])
        memo = await memo_service.create_memo(self.db, self.user_id, memo_in)
        return f"📝 已创建备忘录：{memo.content[:30]}..."
    
    async def _query_memo(self) -> str:
        """查询备忘录"""
        memos, total = await memo_service.list_memos(self.db, self.user_id)
        
        if not memos:
            return "📭 暂无备忘录"
        
        lines = [f"📝 共有 {total} 条备忘录："]
        for i, memo in enumerate(memos[:5], 1):
            tags_str = f" [{', '.join(memo.tags)}]" if memo.tags else ""
            lines.append(f"{i}. {memo.content[:40]}...{tags_str}")
        
        if total > 5:
            lines.append(f"... 还有 {total - 5} 条")
        
        return "\n".join(lines)
    
    async def _statistics(self, query: str) -> str:
        """统计"""
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
    
    def _parse_time(self, time_str: str) -> datetime:
        """解析时间"""
        if isinstance(time_str, datetime):
            return time_str
        if not time_str:
            return datetime.now()
        
        now = datetime.now()
        time_str = str(time_str).strip()
        
        # 相对时间替换
        replacements = {
            "明天": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
            "后天": (now + timedelta(days=2)).strftime("%Y-%m-%d"),
            "今天": now.strftime("%Y-%m-%d"),
            "下周": (now + timedelta(days=7)).strftime("%Y-%m-%d"),
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
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ]
            
            # 第一次调用：获取工具调用
            response = await self._call_llm(messages, TOOLS)
            
            # 检查是否有工具调用
            if response.tool_calls:
                # 执行工具
                tool_results = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    result = await self._execute_tool(tool_name, tool_args)
                    tool_results.append(result)
                
                # 添加工具结果到对话
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc.model_dump() for tc in response.tool_calls]
                })
                
                for i, tool_call in enumerate(response.tool_calls):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_results[i]
                    })
                
                # 第二次调用：获取最终回复
                final_response = await self._call_llm(messages)
                reply = final_response.content
            else:
                reply = response.content
            
            return {
                "action": "process",
                "entity": "mixed",
                "data": {},
                "reply": reply or "处理完成"
            }
            
        except Exception as e:
            return {
                "action": "error",
                "entity": "none",
                "data": {},
                "reply": f"处理出错：{str(e)}"
            }
