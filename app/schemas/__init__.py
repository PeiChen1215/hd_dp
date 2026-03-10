"""schemas package - re-export common schema classes for convenience"""
from .auth import UserCreate, UserOut, Token, TokenPayload
from .event import EventCreate, EventUpdate, EventOut, EventList
from .memo import MemoCreate, MemoUpdate, MemoOut, MemoList
from .misc import (
    Provider,
    # 旧版同步
    SyncRequest, 
    SyncResponse,
    # 新版增量同步
    SyncItemPush,
    SyncPushRequest,
    SyncPushResponse,
    SyncResult,
    SyncPullResponse,
    ConflictResolution,
    FullSyncRequest,
    FullSyncResponse,
)

__all__ = [
    "UserCreate",
    "UserOut",
    "Token",
    "TokenPayload",
    "EventCreate",
    "EventUpdate",
    "EventOut",
    "EventList",
    "MemoCreate",
    "MemoUpdate",
    "MemoOut",
    "MemoList",
    "Provider",
    # 同步相关
    "SyncRequest",
    "SyncResponse",
    "SyncItemPush",
    "SyncPushRequest",
    "SyncPushResponse",
    "SyncResult",
    "SyncPullResponse",
    "ConflictResolution",
    "FullSyncRequest",
    "FullSyncResponse",
]
