from fastapi import APIRouter, Depends
from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone

from app.schemas.misc import SyncRequest, SyncResponse, SyncItem
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.get("/")
async def sync_get(since: Optional[str] = None, user=Depends(get_current_user)):
    """返回自 `since` 以来的更改（目前为占位实现，返回空结果）。

    这是一个可用的占位实现；如需持久化请告知我是否要把结果写入数据库。
    """
    return {"items": [], "cursor": None}


@router.post("/", response_model=SyncResponse)
async def sync_post(payload: SyncRequest, user=Depends(get_current_user)):
    """处理客户端的批量同步请求（临时实现）。

    当前实现会对每个 item 生成 `serverId`（若原数据未提供），
    标记 `status` 为 "ok"，并返回 `updated_at` 时间戳，方便前端进行联调。
    """
    out_items = []
    now = datetime.now(timezone.utc).isoformat()

    for raw in payload.items:
        # 支持 dict 或已含必要字段的对象
        client_id = raw.get("clientId") if isinstance(raw, dict) else None
        server_id = raw.get("serverId") if isinstance(raw, dict) else None
        if not server_id:
            server_id = str(uuid4())

        itm = SyncItem(
            clientId=client_id,
            serverId=server_id,
            status="ok",
            updated_at=now,
        )
        out_items.append(itm)

    return SyncResponse(items=out_items)
