from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agent import AgentRequest, AgentResponse
from app.agents.factory import get_agent


async def process_nl_instruction(
    db: AsyncSession,
    user_id: str,
    request: AgentRequest,
    provider: str = "wanji"
) -> AgentResponse:
    """
    处理自然语言指令
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        request: Agent 请求（包含用户输入 text）
        provider: 使用的 AI 提供商（默认万机）
        
    Returns:
        Agent 响应
    """
    # 获取 Agent 实例（深度集成的万机）
    agent = get_agent(provider=provider, db=db, user_id=user_id)
    
    # 处理用户输入
    context = {
        "conversation_id": request.conversation_id,
        "user_id": user_id
    }
    
    result = await agent.process(request.text, context)
    
    return AgentResponse(
        action=result.get("action", "noop"),
        entity=result.get("entity", "none"),
        data=result.get("data", {}),
        reply=result.get("reply", "处理完成")
    )
