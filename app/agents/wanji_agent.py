"""
万机 Agent - LangChain 0.2.x + LangGraph 版本（深度集成版）
基于 create_react_agent，直接调用后端 Service 层
整合 wanji_agent2 的增强功能：
- 多日/范围查询
- 建议时段自动应用
- 丰富的日期解析（大后天、N天后等）
- 对话历史持久化
"""

import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dateutil import parser

from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func as sql_func

from app.core.config import settings
from app import schemas
from app.services import event_service, memo_service
from app.agents.base import BaseAgent
from app.models.agent_conversation import AgentConversation


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
    date: str = Field(description="日期描述，如'明天'、'2026-03-10'、'下周'、'这两天'、'最近3天'")


class QueryScheduleRangeInput(BaseModel):
    """查询日程范围输入"""
    start: str = Field(description="开始日期，如'2026-03-10'")
    end: str = Field(description="结束日期，如'2026-03-15'")


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
    万机 - 智能日程助手（LangGraph 深度集成版）
    
    增强功能：
    - 自然语言理解（中英文）
    - 日程管理：创建、查询、修改、删除
    - 备忘录管理：创建、查询
    - 多日/范围查询：这两天、最近N天、本周/下周
    - 冲突检测和智能建议
    - 建议时段自动应用
    - 多轮对话记忆（持久化到数据库）
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
        
        # 内存中的对话历史缓存（最近6条）
        self.chat_history_cache: List[Any] = []
    
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
                end_dt = self._parse_time(end_time) if end_time else (start_dt + timedelta(hours=1))
                
                event_in = schemas.EventCreate(
                    title=title,
                    description=description,
                    start_time=start_dt,
                    end_time=end_dt,
                    location=location
                )
                
                conflicts = await self._detect_conflict(start_dt, end_dt)
                if conflicts:
                    suggestion = await self._find_next_slot(start_dt, int((end_dt - start_dt).total_seconds() / 60))
                    conflict_info = f"时间冲突！已有日程：{conflicts[0].title} ({conflicts[0].start_time.strftime('%m-%d %H:%M')})"
                    if suggestion:
                        conflict_info += f"\n💡 建议改到：{suggestion}\n是否使用建议时间？回复'可以'或'确定'即可安排。"
                    return conflict_info
                
                event = await event_service.create_event(self.db, self.user_id, event_in)
                return f"✅ 已创建日程：{event.title}，时间：{event.start_time.strftime('%Y-%m-%d %H:%M')}"
                
            except Exception as e:
                return f"❌ 创建失败：{str(e)}"
        
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
                    # 尝试模糊匹配
                    for event in events:
                        if any(keyword in event.title for keyword in title.split() if len(keyword) >= 2):
                            target = event
                            break
                
                if not target:
                    return f"❌ 未找到标题包含 '{title}' 的日程"
                
                success = await event_service.delete_event(self.db, str(target.id), self.user_id)
                return f"✅ 已删除日程：{target.title}" if success else "❌ 删除失败"
                
            except Exception as e:
                return f"❌ 删除失败：{str(e)}"
        
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
                    return f"❌ 未找到标题包含 '{title}' 的日程"
                
                update_data = schemas.EventUpdate()
                new_start_dt = None
                new_end_dt = None
                
                if new_start_time:
                    new_start_dt = self._parse_time(new_start_time)
                    update_data.start_time = new_start_dt
                if new_end_time:
                    new_end_dt = self._parse_time(new_end_time)
                    update_data.end_time = new_end_dt
                
                # 冲突检测
                if new_start_dt or new_end_dt:
                    check_start = new_start_dt or target.start_time
                    check_end = new_end_dt or target.end_time
                    conflicts = await self._detect_conflict_excluding(check_start, check_end, str(target.id))
                    if conflicts:
                        suggestion = await self._find_next_slot(check_start, int((check_end - check_start).total_seconds() / 60))
                        conflict_info = f"时间冲突！已有日程：{conflicts[0].title}"
                        if suggestion:
                            conflict_info += f"\n💡 建议改到：{suggestion}\n是否使用建议时间？回复'可以'或'确定'即可修改。"
                        return conflict_info
                
                updated = await event_service.update_event(self.db, str(target.id), self.user_id, update_data)
                return f"✅ 已更新日程：{updated.title}" if updated else "❌ 更新失败"
                
            except Exception as e:
                return f"❌ 更新失败：{str(e)}"
        
        async def query_schedule(date: str) -> str:
            """查询日程（单日）"""
            try:
                start, end = self._parse_date_range(date)
                events, total = await event_service.list_events(
                    self.db, self.user_id, start_date=start, end_date=end
                )
                
                if not events:
                    return f"📅 {self._format_date_desc(date)} 没有安排"
                
                lines = [f"📅 {self._format_date_desc(date)} 共有 {total} 项安排："]
                for i, event in enumerate(events, 1):
                    status_icon = "✅" if event.status == "completed" else "⏳"
                    end_str = event.end_time.strftime('%H:%M') if event.end_time else '?'
                    lines.append(f"{i}. {status_icon} {event.title} ({event.start_time.strftime('%H:%M')}-{end_str})")
                
                return "\n".join(lines)
                
            except Exception as e:
                return f"❌ 查询失败：{str(e)}"
        
        async def query_schedule_range(start: str, end: str) -> str:
            """查询日程范围（多日）"""
            try:
                start_dt = self._parse_time(start)
                end_dt = self._parse_time(end)
                # 包含结束日全天
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                
                events, total = await event_service.list_events(
                    self.db, self.user_id, start_date=start_dt, end_date=end_dt
                )
                
                if not events:
                    return f"📅 {start} 至 {end} 期间没有安排"
                
                # 按日期分组
                grouped: Dict[str, List] = {}
                for event in events:
                    date_key = event.start_time.strftime('%Y-%m-%d')
                    if date_key not in grouped:
                        grouped[date_key] = []
                    grouped[date_key].append(event)
                
                lines = [f"📅 {start} 至 {end} 期间共有 {total} 项安排："]
                for date_key in sorted(grouped.keys()):
                    date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                    weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][date_obj.weekday()]
                    lines.append(f"\n{date_key} ({weekday})：")
                    for event in grouped[date_key]:
                        status_icon = "✅" if event.status == "completed" else "⏳"
                        end_str = event.end_time.strftime('%H:%M') if event.end_time else '?'
                        lines.append(f"  {status_icon} {event.title} ({event.start_time.strftime('%H:%M')}-{end_str})")
                
                return "\n".join(lines)
                
            except Exception as e:
                return f"❌ 查询失败：{str(e)}"
        
        async def add_memo(content: str, tags: Optional[List[str]] = None) -> str:
            """创建备忘录"""
            try:
                memo_in = schemas.MemoCreate(content=content, tags=tags or [])
                memo = await memo_service.create_memo(self.db, self.user_id, memo_in)
                return f"✅ 已创建备忘录：{memo.content[:30]}..."
                
            except Exception as e:
                return f"❌ 创建失败：{str(e)}"
        
        async def query_memo() -> str:
            """查询备忘录"""
            try:
                memos, total = await memo_service.list_memos(self.db, self.user_id)
                
                if not memos:
                    return "📝 暂无备忘录"
                
                lines = [f"📝 共有 {total} 条备忘录："]
                for i, memo in enumerate(memos[:5], 1):
                    tags_str = f" [{', '.join(memo.tags)}]" if memo.tags else ""
                    lines.append(f"{i}. {memo.content[:40]}...{tags_str}")
                
                if total > 5:
                    lines.append(f"... 还有 {total - 5} 条")
                
                return "\n".join(lines)
                
            except Exception as e:
                return f"❌ 查询失败：{str(e)}"
        
        async def statistics(query: str) -> str:
            """统计"""
            try:
                now = datetime.now()
                
                if "上周" in query or "last week" in query.lower():
                    start = now - timedelta(days=now.weekday() + 7)
                    end = start + timedelta(days=7)
                    events, count = await event_service.list_events(
                        self.db, self.user_id, start_date=start, end_date=end
                    )
                    return f"📊 上周共有 {count} 次安排"
                
                elif "本周" in query or "this week" in query.lower():
                    start = now - timedelta(days=now.weekday())
                    end = start + timedelta(days=7)
                    events, count = await event_service.list_events(
                        self.db, self.user_id, start_date=start, end_date=end
                    )
                    return f"📊 本周共有 {count} 次安排"
                
                elif "日程" in query or "会议" in query or "安排" in query:
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
                description="查询日程（单日）。示例：'明天有什么安排'、'这两天有什么安排'",
                args_schema=QueryScheduleInput
            ),
            StructuredTool.from_function(
                coroutine=query_schedule_range,
                name="query_schedule_range",
                description="查询日程范围（多日）。示例：查询本周、最近3天的安排",
                args_schema=QueryScheduleRangeInput
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
                description="统计信息。示例：'我有多少条日程'、'上周几次安排'",
                args_schema=StatisticsInput
            ),
        ]
    
    def _create_agent(self):
        """创建 ReAct Agent（LangGraph）"""
        
        system_prompt = f"""你是一个智能日程助手，名字叫"万机"。

当前系统日期: {datetime.now().strftime('%Y-%m-%d')}

你的能力：
- 理解中英文自然语言
- 自动解析时间（支持相对时间如"明天下午3点"、"大后天"、"3天后"、"本周"、"下周"）
- 管理用户的日程和备忘录
- 冲突检测和智能建议
- 支持单日查询和多日范围查询

工具使用规则：
1. 当用户想要创建日程时，调用 add_schedule 工具
2. 当用户想要删除日程时，调用 delete_schedule 工具
3. 当用户想要修改日程时，调用 update_schedule 工具
4. 当用户想要查询单日日程时，调用 query_schedule 工具
5. 当用户想要查询多日日程（如"这两天"、"最近3天"、"本周"）时，调用 query_schedule_range 工具
6. 当用户想要创建备忘录时，调用 add_memo 工具
7. 当用户想要查询备忘录时，调用 query_memo 工具
8. 当用户问统计问题时，调用 statistics 工具

时间解析增强：
- "明天"、"后天"、"大后天" → 相对今天
- "N天后"、"N天前" → 相对今天加减N天
- "本周" → 本周一至周日
- "下周" → 下周一至周日
- "这两天"、"这几天" → 今天起2-3天

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
    
    # ============ 时间解析工具方法（整合 wanji2 的增强功能） ============
    
    def _parse_time(self, time_str: str) -> datetime:
        """解析时间（增强版）"""
        if isinstance(time_str, datetime):
            return time_str
        if not time_str:
            return datetime.now()
        
        now = datetime.now()
        time_str = str(time_str).strip()
        
        # 处理相对日期词
        ref_date = self._get_reference_date_from_text(time_str)
        
        # 处理时间格式
        time_str = time_str.replace('点', ':').replace('：', ':')
        
        # 处理上午/下午/晚上
        is_pm = False
        if '下午' in time_str or '晚上' in time_str or '晚' in time_str:
            is_pm = True
            time_str = re.sub(r'下午|晚上|晚', '', time_str).strip()
        if '上午' in time_str or '早上' in time_str or '早' in time_str:
            time_str = re.sub(r'上午|早上|早', '', time_str).strip()
        
        # 替换相对日期为具体日期
        replacements = {
            r'今天': now.strftime('%Y-%m-%d'),
            r'明天': (now + timedelta(days=1)).strftime('%Y-%m-%d'),
            r'后天': (now + timedelta(days=2)).strftime('%Y-%m-%d'),
            r'大后天': (now + timedelta(days=3)).strftime('%Y-%m-%d'),
            r'大前天': (now - timedelta(days=3)).strftime('%Y-%m-%d'),
            r'昨天': (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            r'下周': (now + timedelta(days=7)).strftime('%Y-%m-%d'),
        }
        
        for pattern, replacement in replacements.items():
            time_str = re.sub(pattern, replacement, time_str)
        
        # 处理 "N天后/前"
        m_after = re.search(r'(\d+)\s*天后', time_str)
        if m_after:
            days = int(m_after.group(1))
            date_str = (now + timedelta(days=days)).strftime('%Y-%m-%d')
            time_str = re.sub(r'\d+\s*天后', date_str, time_str)
        
        m_before = re.search(r'(\d+)\s*天前', time_str)
        if m_before:
            days = int(m_before.group(1))
            date_str = (now - timedelta(days=days)).strftime('%Y-%m-%d')
            time_str = re.sub(r'\d+\s*天前', date_str, time_str)
        
        # 解析时间
        try:
            if re.search(r'\d{4}[-年]', time_str) or re.search(r'\d{1,2}月', time_str):
                dt = parser.parse(time_str)
            else:
                default_dt = ref_date.replace(hour=0, minute=0, second=0)
                dt = parser.parse(time_str, default=default_dt)
            
            if is_pm and dt.hour < 12:
                dt = dt + timedelta(hours=12)
            
            return dt
        except Exception:
            # 备用解析
            combined = f"{ref_date.date().isoformat()} {time_str}"
            return parser.parse(combined, fuzzy=True)
    
    def _get_reference_date_from_text(self, text: str) -> datetime:
        """从文本中获取参考日期"""
        today = datetime.now()
        if not text:
            return today
        
        if "今天" in text:
            return today
        if "明天" in text:
            return today + timedelta(days=1)
        if "后天" in text:
            return today + timedelta(days=2)
        if "大后天" in text:
            return today + timedelta(days=3)
        if "大前天" in text:
            return today - timedelta(days=3)
        if "昨天" in text:
            return today - timedelta(days=1)
        
        # 匹配 "N天后/前"
        m_after = re.search(r'(\d+)\s*天后', text)
        if m_after:
            return today + timedelta(days=int(m_after.group(1)))
        m_before = re.search(r'(\d+)\s*天前', text)
        if m_before:
            return today - timedelta(days=int(m_before.group(1)))
        
        # 匹配周几
        m = re.search(r'周([一二三四五六日天])', text)
        if m:
            mapping = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}
            target = mapping.get(m.group(1))
            if target is not None:
                today_wd = today.weekday()
                days = (target - today_wd) % 7
                if days == 0:
                    days = 7
                return today + timedelta(days=days)
        
        return today
    
    def _parse_date_range(self, date_desc: str) -> Tuple[datetime, datetime]:
        """解析日期范围（整合 wanji2 的多日查询）"""
        now = datetime.now()
        date_desc = str(date_desc).strip()
        
        # 处理多日表达
        if re.search(r'这\s*两\s*天|这\s*几\s*天', date_desc):
            start = now.replace(hour=0, minute=0, second=0)
            end = start + timedelta(days=2)
            return start, end
        
        m_recent = re.search(r'最近\s*(\d+)\s*天', date_desc)
        if m_recent:
            days = int(m_recent.group(1))
            start = now.replace(hour=0, minute=0, second=0) - timedelta(days=days-1)
            end = now + timedelta(days=1)
            return start, end
        
        m_future = re.search(r'未来\s*(\d+)\s*天|接下来\s*(\d+)\s*天', date_desc)
        if m_future:
            days = int(m_future.group(1) or m_future.group(2))
            start = now.replace(hour=0, minute=0, second=0)
            end = start + timedelta(days=days)
            return start, end
        
        if "本周" in date_desc:
            wd = now.weekday()
            start = now - timedelta(days=wd)
            start = start.replace(hour=0, minute=0, second=0)
            end = start + timedelta(days=7)
            return start, end
        
        if "下周" in date_desc:
            wd = now.weekday()
            start = now - timedelta(days=wd) + timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0)
            end = start + timedelta(days=7)
            return start, end
        
        # 单日查询
        if "明天" in date_desc:
            start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        elif "后天" in date_desc:
            start = (now + timedelta(days=2)).replace(hour=0, minute=0, second=0)
        elif "今天" in date_desc:
            start = now.replace(hour=0, minute=0, second=0)
        elif "大后天" in date_desc:
            start = (now + timedelta(days=3)).replace(hour=0, minute=0, second=0)
        else:
            try:
                dt = parser.parse(date_desc, fuzzy=True)
                start = dt.replace(hour=0, minute=0, second=0)
            except Exception:
                start = now.replace(hour=0, minute=0, second=0)
        
        return start, start + timedelta(days=1)
    
    def _format_date_desc(self, date_desc: str) -> str:
        """格式化日期描述用于显示"""
        if "今天" in date_desc:
            return "今天"
        if "明天" in date_desc:
            return "明天"
        if "后天" in date_desc:
            return "后天"
        return date_desc
    
    async def _detect_conflict(self, start_time: datetime, end_time: Optional[datetime]) -> list:
        """检测冲突"""
        if not end_time:
            end_time = start_time + timedelta(hours=1)
        
        events, _ = await event_service.list_events(
            self.db, self.user_id, start_date=start_time, end_date=end_time
        )
        return events
    
    async def _detect_conflict_excluding(self, start_time: datetime, end_time: Optional[datetime], exclude_id: str) -> list:
        """检测冲突（排除指定事件）"""
        if not end_time:
            end_time = start_time + timedelta(hours=1)
        
        events, _ = await event_service.list_events(
            self.db, self.user_id, start_date=start_time, end_date=end_time
        )
        return [e for e in events if str(e.id) != exclude_id]
    
    async def _find_next_slot(self, start_time: datetime, duration_minutes: int = 60) -> Optional[str]:
        """找下一个可用时段"""
        for i in range(1, 6):
            new_start = start_time + timedelta(hours=i)
            new_end = new_start + timedelta(minutes=duration_minutes)
            conflicts = await self._detect_conflict(new_start, new_end)
            if not conflicts:
                return new_start.strftime("%Y-%m-%d %H:%M")
        return None
    
    # ============ 对话历史持久化 ============
    
    async def _load_conversation_history(self, limit: int = 10) -> List[AgentConversation]:
        """从数据库加载对话历史"""
        result = await self.db.execute(
            select(AgentConversation)
            .where(AgentConversation.user_id == self.user_id)
            .order_by(desc(AgentConversation.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def _save_conversation(self, role: str, content: str):
        """保存对话记录到数据库"""
        conv = AgentConversation(
            user_id=self.user_id,
            role=role,
            content=content
        )
        self.db.add(conv)
        await self.db.commit()
    
    async def _check_pending_suggestion(self, user_input: str) -> Optional[Dict]:
        """检查是否有待处理的建议需要确认"""
        # 检查确认关键词
        if not re.search(r'^\s*(可以|好|行|确定|就这样|安排吧|是的)\s*$', user_input):
            return None
        
        # 获取最近的一条助手消息
        history = await self._load_conversation_history(limit=3)
        for conv in reversed(history):
            if conv.role == "assistant":
                content = conv.content
                # 检查是否包含建议关键词
                if "建议" not in content or "冲突" not in content:
                    continue
                
                # 尝试多种格式匹配建议时间
                # 格式1: ISO格式 2026-03-14 17:00
                suggestion_match = re.search(
                    r'建议(?:改到|将您的会议改到|时间)[：:]\s*(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})',
                    content
                )
                if suggestion_match:
                    suggested_time = suggestion_match.group(1)
                    intent = "add" if "创建" in content or "添加" in content or "安排" in content else "update"
                    return {
                        "suggested_time": suggested_time,
                        "intent": intent,
                        "original_message": content
                    }
                
                # 格式2: 相对时间描述（如"下午5点"），需要进一步解析
                # 暂时不支持，返回None让Agent正常处理
        return None
    
    # ============ 主处理入口 ============
    
    async def process(self, text: str, context: dict) -> dict:
        """处理自然语言指令"""
        try:
            # 检查是否是确认建议
            suggestion = await self._check_pending_suggestion(text)
            if suggestion:
                return await self._apply_suggestion(suggestion, text)
            
            # 快捷路径：当前时间/日期查询
            quick_reply = self._handle_quick_queries(text)
            if quick_reply:
                await self._save_conversation("user", text)
                await self._save_conversation("assistant", quick_reply)
                return {
                    "action": "query",
                    "entity": "time",
                    "data": {},
                    "reply": quick_reply
                }
            
            # 构建消息
            messages = []
            
            # 从数据库加载历史并添加到缓存
            db_history = await self._load_conversation_history(limit=6)
            for conv in reversed(db_history):
                if conv.role == "user":
                    messages.append(HumanMessage(content=conv.content))
                elif conv.role == "assistant":
                    messages.append(AIMessage(content=conv.content))
            
            # 添加当前输入
            messages.append(HumanMessage(content=text))
            
            # 保存用户输入
            await self._save_conversation("user", text)
            
            # 调用 agent
            result = await self.agent.ainvoke({"messages": messages})
            
            # 获取最后一条 AI 消息
            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            reply = ai_messages[-1].content if ai_messages else "处理完成"
            
            # 保存助手回复
            await self._save_conversation("assistant", reply)
            
            # 检测操作类型
            action, entity = self._detect_action_type(reply)
            
            return {
                "action": action,
                "entity": entity,
                "data": {},
                "reply": reply
            }
            
        except Exception as e:
            error_msg = f"处理出错：{str(e)}"
            return {
                "action": "error",
                "entity": "none",
                "data": {},
                "reply": error_msg
            }
    
    async def _apply_suggestion(self, suggestion: Dict, user_input: str) -> dict:
        """应用建议时段"""
        try:
            suggested_time = suggestion["suggested_time"]
            suggested_dt = datetime.strptime(suggested_time, "%Y-%m-%d %H:%M")
            
            # 从原始消息中提取标题
            title_match = re.search(r'日程[：:]\s*([^\n（]+)', suggestion["original_message"])
            if not title_match:
                title_match = re.search(r'已有日程[：:]\s*([^\n（]+)', suggestion["original_message"])
            
            title = title_match.group(1).strip() if title_match else "日程"
            
            if suggestion["intent"] == "add":
                # 创建日程
                event_in = schemas.EventCreate(
                    title=title,
                    start_time=suggested_dt,
                    end_time=suggested_dt + timedelta(hours=1)
                )
                event = await event_service.create_event(self.db, self.user_id, event_in)
                reply = f"✅ 已按建议时间创建日程：{event.title}，时间：{event.start_time.strftime('%Y-%m-%d %H:%M')}"
            else:
                # 修改日程（需要找到原日程）
                reply = "请重新输入完整的修改指令，如：把[日程标题]改到建议时间"
            
            await self._save_conversation("user", user_input)
            await self._save_conversation("assistant", reply)
            
            return {
                "action": "create" if suggestion["intent"] == "add" else "update",
                "entity": "event",
                "data": {},
                "reply": reply
            }
            
        except Exception as e:
            return {
                "action": "error",
                "entity": "none",
                "data": {},
                "reply": f"应用建议时出错：{str(e)}"
            }
    
    def _handle_quick_queries(self, text: str) -> Optional[str]:
        """处理快速查询（不需要调用 LLM）"""
        # 当前时间
        if re.search(r"现在.*(几点|时间)|几点了|现在是几点", text):
            now = datetime.now()
            return f"现在时间是 {now.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 今天日期
        if re.search(r"今天.*(几号|日期)|今天是几号|今天几号", text):
            today = datetime.now()
            weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            wd = weekdays[today.weekday()]
            return f"今天是 {today.strftime('%Y-%m-%d')}（{wd}）"
        
        return None
    
    def _detect_action_type(self, reply: str) -> Tuple[str, str]:
        """从回复中检测操作类型"""
        action = "noop"
        entity = "none"
        
        if "已创建" in reply or "已添加" in reply:
            action = "create"
            entity = "event" if "日程" in reply else "memo"
        elif "已删除" in reply or "已移除" in reply:
            action = "delete"
            entity = "event" if "日程" in reply else "memo"
        elif "已更新" in reply or "已修改" in reply:
            action = "update"
            entity = "event" if "日程" in reply else "memo"
        elif "共有" in reply or "没有安排" in reply or "暂无" in reply:
            action = "query"
            entity = "event" if "日程" in reply or "安排" in reply else "memo"
        
        return action, entity
