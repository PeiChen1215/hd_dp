from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agent import AgentRequest, AgentResponse
from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import agent_service

router = APIRouter()


@router.post("/process", response_model=AgentResponse)
async def process_agent(
    req: AgentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    处理自然语言指令
    
    示例请求：
    ```json
    {
        "text": "帮我安排明天下午3点的会议",
        "conversation_id": null
    }
    ```
    
    示例响应：
    ```json
    {
        "action": "process",
        "entity": "mixed",
        "data": {},
        "reply": "✅ 已创建日程：会议，时间：2026-03-10 15:00"
    }
    ```
    
    支持的指令：
    - **创建日程**："帮我安排明天下午3点的会议"
    - **查询日程**："明天有什么安排"
    - **修改日程**："把会议改到后天"
    - **删除日程**："删除明天的会议"
    - **创建备忘**："记住买牛奶"
    - **查询备忘**："查看我的备忘录"
    - **统计信息**："我有多少条日程"
    """
    try:
        result = await agent_service.process_nl_instruction(
            db=db,
            user_id=str(current_user.id),
            request=req,
            provider="wanji"
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent 处理失败: {str(e)}"
        )
