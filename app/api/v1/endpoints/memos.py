from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app import schemas
from app.services import memo_service
from app.utils.model_converter import memo_to_dict

router = APIRouter()


@router.get("/")
async def list_memos(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的备忘录列表
    
    按更新时间降序排列
    """
    memos, total = await memo_service.list_memos(
        db=db,
        user_id=str(current_user.id),
        page=page,
        size=size
    )
    
    # 转换为字典
    memo_dicts = [memo_to_dict(m) for m in memos]
    
    return {
        "items": memo_dicts,
        "total": total,
        "page": page,
        "size": size
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_memo(
    payload: schemas.MemoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建新备忘录
    
    - **content**: 内容（必填）
    - **tags**: 标签列表（可选）
    """
    memo = await memo_service.create_memo(
        db=db,
        user_id=str(current_user.id),
        memo_in=payload
    )
    return memo_to_dict(memo)


@router.get("/{memo_id}")
async def get_memo(
    memo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取单个备忘录详情
    """
    memo = await memo_service.get_memo_by_id(
        db=db,
        memo_id=memo_id,
        user_id=str(current_user.id)
    )
    
    if not memo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memo not found"
        )
    
    return memo_to_dict(memo)


@router.put("/{memo_id}")
async def update_memo(
    memo_id: str,
    payload: schemas.MemoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新备忘录（全量或部分更新）
    """
    memo = await memo_service.update_memo(
        db=db,
        memo_id=memo_id,
        user_id=str(current_user.id),
        memo_in=payload
    )
    
    if not memo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memo not found"
        )
    
    return memo_to_dict(memo)


@router.delete("/{memo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memo(
    memo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除备忘录
    """
    success = await memo_service.delete_memo(
        db=db,
        memo_id=memo_id,
        user_id=str(current_user.id)
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memo not found"
        )
    
    return None
