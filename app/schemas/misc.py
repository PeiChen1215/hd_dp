from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class Provider(BaseModel):
    id: str
    name: str
    capabilities: Optional[List[str]] = None


# ============ 同步相关 Schema ============

class SyncItem(BaseModel):
    """通用同步项（旧版，兼容用）"""
    clientId: Optional[int] = None
    serverId: Optional[str] = None
    status: Optional[str] = None
    updated_at: Optional[str] = None


class SyncRequest(BaseModel):
    """同步请求（旧版）"""
    items: List[dict]


class SyncResponse(BaseModel):
    """同步响应（旧版）"""
    items: List[SyncItem]


# ============ 新版增量同步 Schema ============

class SyncItemPush(BaseModel):
    """推送到服务器的单个同步项"""
    client_id: Optional[str] = Field(None, description="客户端本地ID")
    server_id: Optional[str] = Field(None, description="服务器ID，新建时为空")
    entity_type: Literal["event", "memo"] = Field(..., description="实体类型")
    action: Literal["create", "update", "delete"] = Field(..., description="操作类型")
    payload: Optional[Dict[str, Any]] = Field(None, description="实体数据")
    modified_at: str = Field(..., description="客户端修改时间（ISO格式）")


class SyncPushRequest(BaseModel):
    """批量推送请求"""
    items: List[SyncItemPush] = Field(..., description="待同步的变更列表")
    last_synced_at: Optional[str] = Field(None, description="上次同步时间，用于冲突检测")


class SyncResult(BaseModel):
    """单个同步项的处理结果"""
    client_id: Optional[str]
    server_id: Optional[str]
    status: Literal["success", "conflict", "error"]
    message: str
    server_modified_at: Optional[str] = None
    server_data: Optional[Dict[str, Any]] = None  # 冲突时返回服务器数据


class SyncPushResponse(BaseModel):
    """批量推送响应"""
    results: List[SyncResult]
    conflicts: List[SyncResult]  # 冲突列表
    server_time: str


class SyncPullItem(BaseModel):
    """拉取的变更项"""
    server_id: str
    client_id: Optional[str]
    entity_type: Literal["event", "memo"]
    action: Literal["create", "update", "delete"]
    payload: Optional[Dict[str, Any]]
    client_modified_at: Optional[str]
    server_modified_at: str


class SyncPullResponse(BaseModel):
    """增量拉取响应"""
    items: List[SyncPullItem]
    next_cursor: Optional[str] = Field(None, description="下一页游标")
    has_more: bool
    server_time: str


class ConflictResolution(BaseModel):
    """冲突解决请求"""
    client_id: Optional[str]
    server_id: str
    entity_type: Literal["event", "memo"]
    resolution: Literal["client", "server", "merge"] = Field(
        ..., description="解决策略：使用客户端/服务器/合并"
    )
    merged_data: Optional[Dict[str, Any]] = Field(None, description="合并后的数据")


class FullSyncRequest(BaseModel):
    """全量同步请求"""
    items: Optional[List[SyncItemPush]] = Field(
        None, description="客户端所有本地数据"
    )


class FullSyncResponse(BaseModel):
    """全量同步响应"""
    server_data: Dict[str, List[Dict[str, Any]]]  # {events: [...], memos: [...]}
    push_results: List[SyncResult]
    server_time: str
