"""
Offline Sync API Module
Supports incremental sync, conflict resolution, and multi-device data consistency
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from typing import Optional, List
from datetime import datetime
from uuid import uuid4, UUID
import json

from app.db.session import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.event import Event
from app.models.memo import Memo
from app.models.sync_record import SyncRecord
from app import schemas
from app.core.timezone import get_beijing_time

router = APIRouter()


class SyncConflictError(Exception):
    """Sync conflict exception"""
    pass


@router.get("/pull")
async def sync_pull(
    since: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Incremental pull: Get changes from server since `since` timestamp
    
    Args:
        since: Last sync timestamp (ISO format), empty to fetch all
        limit: Max items per request
        
    Returns:
        {
            "items": [...],      # Change records list
            "nextCursor": "...", # Next page cursor, empty if no more
            "hasMore": false,
            "serverTime": "..."  # Server current time for next pull
        }
    """
    user_id = user.id
    
    # Build base query
    query = select(SyncRecord).where(
        SyncRecord.user_id == user_id
    )
    
    # Time filter
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.where(SyncRecord.server_modified_at > since_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid since format")
    
    # Order by server time ascending
    query = query.order_by(SyncRecord.server_modified_at.asc())
    
    # Limit
    query = query.limit(limit + 1)  # Query one more to check has_more
    
    # Execute query
    result = await db.execute(query)
    records = result.scalars().all()
    
    # Check if has more
    has_more = len(records) > limit
    records = records[:limit]  # Take only limit records
    
    # Convert to response format
    items = []
    for record in records:
        items.append({
            "server_id": str(record.entity_id),
            "client_id": record.client_id,
            "entity_type": record.entity_type,
            "action": record.action,
            "payload": record.payload,
            "server_modified_at": record.server_modified_at.isoformat()
        })
    
    # Get next cursor
    next_cursor = None
    if has_more and items:
        next_cursor = items[-1]["server_modified_at"]
    
    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "server_time": get_beijing_time().isoformat()
    }


@router.post("/push")
async def sync_push(
    payload: schemas.SyncPushRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Incremental push: Upload client changes to server
    
    Handles conflict detection and resolution based on last_synced_at
    """
    user_id = user.id
    results = []
    
    for item in payload.items:
        try:
            result = await _process_sync_item(
                db, user_id, item, payload.last_synced_at
            )
            results.append(result)
        except SyncConflictError as e:
            # Conflict: Return server version for client resolution
            results.append({
                "client_id": item.client_id,
                "server_id": None,
                "status": "conflict",
                "message": str(e),
                "server_data": await _get_server_version(
                    db, user_id, item.entity_type, item.client_id
                )
            })
        except Exception as e:
            results.append({
                "client_id": item.client_id,
                "server_id": None,
                "status": "error",
                "message": str(e)
            })
    
    return {
        "results": results,
        "server_time": get_beijing_time().isoformat()
    }


@router.post("/resolve-conflict")
async def resolve_conflict(
    resolution: schemas.ConflictResolution,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Manually resolve sync conflict
    
    Resolution types:
    - client: Use client version (override server)
    - server: Use server version (discard local changes)
    - merge: Merge both versions (reserved)
    """
    user_id = user.id
    
    # Get the conflicting record
    result = await db.execute(
        select(SyncRecord).where(
            and_(
                SyncRecord.user_id == user_id,
                SyncRecord.entity_type == resolution.entity_type,
                SyncRecord.entity_id == UUID(resolution.server_id)
            )
        )
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    if resolution.resolution == "client":
        # Apply client changes
        await _apply_client_changes(
            db, user_id, resolution.entity_type, 
            resolution.server_id, resolution.merged_data
        )
    elif resolution.resolution == "server":
        # Do nothing, keep server version
        pass
    elif resolution.resolution == "merge":
        # Apply merged data
        if resolution.merged_data:
            await _apply_client_changes(
                db, user_id, resolution.entity_type,
                resolution.server_id, resolution.merged_data
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution type")
    
    await db.commit()
    
    return {
        "status": "success",
        "message": f"Conflict resolved with {resolution.resolution}"
    }


@router.post("/full-sync")
async def full_sync(
    request: schemas.FullSyncRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Full sync - used for initial install or data recovery
    
    Client uploads all local data, server merges
    """
    user_id = user.id
    
    # Get server full data
    events_result = await db.execute(
        select(Event).where(Event.user_id == user_id)
    )
    events = events_result.scalars().all()
    
    memos_result = await db.execute(
        select(Memo).where(Memo.user_id == user_id)
    )
    memos = memos_result.scalars().all()
    
    server_data = {
        "events": [_entity_to_dict(e, "event") for e in events],
        "memos": [_entity_to_dict(m, "memo") for m in memos]
    }
    
    # Process client uploaded data
    push_results = []
    if request.items:
        push_response = await sync_push(
            payload=schemas.SyncPushRequest(
                items=request.items,
                last_synced_at=None
            ),
            db=db,
            user=user
        )
        push_results = push_response.get("results", [])
    
    return {
        "server_data": server_data,
        "push_results": push_results,
        "server_time": get_beijing_time().isoformat()
    }


async def _process_sync_item(
    db: AsyncSession,
    user_id: UUID,
    item: schemas.SyncItemPush,
    last_synced_at: Optional[datetime]
) -> dict:
    """Process a single sync item"""
    
    if item.entity_type == "event":
        return await _process_event_sync(db, user_id, item, last_synced_at)
    elif item.entity_type == "memo":
        return await _process_memo_sync(db, user_id, item, last_synced_at)
    else:
        raise ValueError(f"Unknown entity type: {item.entity_type}")


async def _process_event_sync(
    db: AsyncSession,
    user_id: UUID,
    item: schemas.SyncItemPush,
    last_synced_at: Optional[datetime]
) -> dict:
    """Process event sync item"""
    from app.services import event_service
    
    if item.action == "create":
        # Create new event
        event_in = schemas.EventCreate(**item.payload)
        event = await event_service.create_event(db, str(user_id), event_in)
        return {
            "client_id": item.client_id,
            "server_id": str(event.id),
            "status": "success"
        }
    
    elif item.action == "update":
        # Update existing event
        server_id = str(item.server_id) if item.server_id else None
        if not server_id:
            # Try to find by client_id
            record = await _find_record_by_client_id(
                db, user_id, "event", item.client_id
            )
            if record:
                server_id = str(record.entity_id)
        
        if not server_id:
            raise ValueError("Server ID required for update")
        
        # Check conflict
        if await _check_conflict(db, user_id, "event", server_id, last_synced_at):
            raise SyncConflictError("Event has been modified on server")
        
        event_in = schemas.EventUpdate(**item.payload)
        event = await event_service.update_event(db, server_id, str(user_id), event_in)
        
        return {
            "client_id": item.client_id,
            "server_id": server_id,
            "status": "success"
        }
    
    elif item.action == "delete":
        # Delete event
        server_id = str(item.server_id) if item.server_id else None
        if not server_id:
            record = await _find_record_by_client_id(
                db, user_id, "event", item.client_id
            )
            if record:
                server_id = str(record.entity_id)
        
        if server_id:
            await event_service.delete_event(db, server_id, str(user_id))
        
        return {
            "client_id": item.client_id,
            "server_id": server_id,
            "status": "success"
        }
    
    else:
        raise ValueError(f"Unknown action: {item.action}")


async def _process_memo_sync(
    db: AsyncSession,
    user_id: UUID,
    item: schemas.SyncItemPush,
    last_synced_at: Optional[datetime]
) -> dict:
    """Process memo sync item"""
    from app.services import memo_service
    
    if item.action == "create":
        memo_in = schemas.MemoCreate(**item.payload)
        memo = await memo_service.create_memo(db, str(user_id), memo_in)
        return {
            "client_id": item.client_id,
            "server_id": str(memo.id),
            "status": "success"
        }
    
    elif item.action == "update":
        server_id = str(item.server_id) if item.server_id else None
        if not server_id:
            record = await _find_record_by_client_id(
                db, user_id, "memo", item.client_id
            )
            if record:
                server_id = str(record.entity_id)
        
        if not server_id:
            raise ValueError("Server ID required for update")
        
        if await _check_conflict(db, user_id, "memo", server_id, last_synced_at):
            raise SyncConflictError("Memo has been modified on server")
        
        memo_in = schemas.MemoUpdate(**item.payload)
        memo = await memo_service.update_memo(db, server_id, str(user_id), memo_in)
        
        return {
            "client_id": item.client_id,
            "server_id": server_id,
            "status": "success"
        }
    
    elif item.action == "delete":
        server_id = str(item.server_id) if item.server_id else None
        if not server_id:
            record = await _find_record_by_client_id(
                db, user_id, "memo", item.client_id
            )
            if record:
                server_id = str(record.entity_id)
        
        if server_id:
            await memo_service.delete_memo(db, server_id, str(user_id))
        
        return {
            "client_id": item.client_id,
            "server_id": server_id,
            "status": "success"
        }
    
    else:
        raise ValueError(f"Unknown action: {item.action}")


async def _find_record_by_client_id(
    db: AsyncSession,
    user_id: UUID,
    entity_type: str,
    client_id: str
) -> Optional[SyncRecord]:
    """Find sync record by client ID"""
    result = await db.execute(
        select(SyncRecord).where(
            and_(
                SyncRecord.user_id == user_id,
                SyncRecord.entity_type == entity_type,
                SyncRecord.client_id == client_id
            )
        )
    )
    return result.scalar_one_or_none()


async def _check_conflict(
    db: AsyncSession,
    user_id: UUID,
    entity_type: str,
    server_id: str,
    last_synced_at: Optional[datetime]
) -> bool:
    """Check if there's a conflict (server modified after last sync)"""
    if not last_synced_at:
        return False
    
    result = await db.execute(
        select(SyncRecord).where(
            and_(
                SyncRecord.user_id == user_id,
                SyncRecord.entity_type == entity_type,
                SyncRecord.entity_id == UUID(server_id),
                SyncRecord.server_modified_at > last_synced_at
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def _get_server_version(
    db: AsyncSession,
    user_id: UUID,
    entity_type: str,
    client_id: str
) -> Optional[dict]:
    """Get current server version for conflict resolution"""
    record = await _find_record_by_client_id(db, user_id, entity_type, client_id)
    if not record:
        return None
    
    # Get actual entity data
    if entity_type == "event":
        from app.services import event_service
        event = await event_service.get_event_by_id(
            db, str(record.entity_id), str(user_id)
        )
        return _entity_to_dict(event, "event") if event else None
    elif entity_type == "memo":
        from app.services import memo_service
        memo = await memo_service.get_memo_by_id(
            db, str(record.entity_id), str(user_id)
        )
        return _entity_to_dict(memo, "memo") if memo else None
    
    return None


async def _apply_client_changes(
    db: AsyncSession,
    user_id: str,
    entity_type: str,
    server_id: str,
    data: dict
):
    """Apply client changes to server (for conflict resolution)"""
    if entity_type == "event":
        from app.services import event_service
        event_in = schemas.EventUpdate(**data)
        await event_service.update_event(db, server_id, user_id, event_in)
    elif entity_type == "memo":
        from app.services import memo_service
        memo_in = schemas.MemoUpdate(**data)
        await memo_service.update_memo(db, server_id, user_id, memo_in)


def _entity_to_dict(entity, entity_type: str) -> dict:
    """Convert entity to dict (for WebSocket push)"""
    if entity_type == "event":
        return {
            "id": str(entity.id),
            "title": entity.title,
            "description": entity.description,
            "start_time": entity.start_time.isoformat() if entity.start_time else None,
            "end_time": entity.end_time.isoformat() if entity.end_time else None,
            "location": entity.location,
            "status": entity.status,
            "type": entity.type,
            "priority": entity.priority,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None
        }
    elif entity_type == "memo":
        return {
            "id": str(entity.id),
            "content": entity.content,
            "tags": entity.tags or [],
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None
        }
    return {}
