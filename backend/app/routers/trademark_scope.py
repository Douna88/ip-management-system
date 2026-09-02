"""Trademark scope library router: CRUD for registration scope reference."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import TrademarkScope, SysUser, AuditLog
from app.security import get_current_user
from pydantic import BaseModel
from typing import Optional
from datetime import date
import json

router = APIRouter(prefix="/api/trademark-scopes", tags=["trademark_scope"])


class ScopeCreate(BaseModel):
    scope_group: str
    nice_class: int
    subclass_code: Optional[str] = None
    subclass_name: Optional[str] = None
    class_name: str
    specific_products: Optional[str] = None
    description: Optional[str] = None


class ScopeUpdate(BaseModel):
    scope_group: Optional[str] = None
    nice_class: Optional[int] = None
    subclass_code: Optional[str] = None
    subclass_name: Optional[str] = None
    class_name: Optional[str] = None
    specific_products: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
def list_scopes(
    scope_group: str = Query(""),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """List all trademark registration scopes, grouped by scope_group."""
    q = db.query(TrademarkScope).filter(TrademarkScope.is_active == True)
    if scope_group:
        q = q.filter(TrademarkScope.scope_group == scope_group)

    scopes = q.order_by(TrademarkScope.scope_group, TrademarkScope.nice_class).all()

    # Group by scope_group
    grouped = {}
    for s in scopes:
        if s.scope_group not in grouped:
            grouped[s.scope_group] = []
        grouped[s.scope_group].append({
            "id": s.id,
            "nice_class": s.nice_class,
            "subclass_code": s.subclass_code,
            "subclass_name": s.subclass_name,
            "class_name": s.class_name,
            "specific_products": s.specific_products,
            "description": s.description
        })

    return {"total": len(scopes), "groups": grouped, "items": [{
        "id": s.id,
        "scope_group": s.scope_group,
        "nice_class": s.nice_class,
        "subclass_code": s.subclass_code,
        "subclass_name": s.subclass_name,
        "class_name": s.class_name,
        "specific_products": s.specific_products,
        "description": s.description,
        "is_active": s.is_active
    } for s in scopes]}


@router.post("", status_code=201)
def create_scope(
    data: ScopeCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    s = TrademarkScope(**data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "message": "创建成功"}


@router.put("/{sid}")
def update_scope(
    sid: int,
    data: ScopeUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    s = db.query(TrademarkScope).filter(TrademarkScope.id == sid).first()
    if not s:
        raise HTTPException(status_code=404, detail="范围记录不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    return {"message": "更新成功"}


@router.delete("/{sid}")
def delete_scope(
    sid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    s = db.query(TrademarkScope).filter(TrademarkScope.id == sid).first()
    if not s:
        raise HTTPException(status_code=404, detail="范围记录不存在")
    s.is_active = False
    db.commit()
    return {"message": "已删除"}
