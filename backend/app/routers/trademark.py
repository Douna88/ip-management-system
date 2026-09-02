"""Trademark router: CRUD."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Trademark, Agency, AuditLog, FileStorage, SysUser
from app.schemas import TrademarkCreate, TrademarkUpdate
from app.security import get_current_user
import json

router = APIRouter(prefix="/api/trademarks", tags=["trademark"])


def _tm_to_out(t: Trademark) -> dict:
    # Build logo URL from logo_file relationship
    logo_url = None
    if t.logo_file and t.logo_file.storage_path:
        # storage_path 可能存绝对路径或仅文件名，取 basename 拼 /uploads/ URL 都兼容
        import os
        filename = os.path.basename(t.logo_file.storage_path)
        logo_url = f"/uploads/{filename}"
    return {
        "id": t.id,
        "trademark_no": t.trademark_no,
        "trademark_name": t.trademark_name,
        "trademark_type": t.trademark_type,
        "logo_file_id": t.logo_file_id,
        "logo_url": logo_url,
        "application_date": t.application_date,
        "registration_date": t.registration_date,
        "valid_until": t.valid_until,
        "nice_class": t.nice_class,
        "scope_group": t.scope_group,
        "applicant": t.applicant,
        "agency_id": t.agency_id,
        "agency_name": t.agency.agency_name if t.agency else None,
        "status": t.status,
        "partial_grant_class": t.partial_grant_class,
        "renewal_count": t.renewal_count,
        "last_renewal_date": t.last_renewal_date,
        "renewal_deadline": t.renewal_deadline,
        "grace_period_deadline": t.grace_period_deadline,
        "contact_person": t.contact_person,
        "notes": t.notes,
        "created_at": t.created_at,
    }


@router.get("")
def list_trademarks(
    search: str = Query(""),
    scope_group: str = Query(""),
    status: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    q = db.query(Trademark).filter(Trademark.is_deleted == False)

    if search:
        like = f"%{search}%"
        q = q.filter(
            (Trademark.trademark_name.like(like)) |
            (Trademark.trademark_no.like(like)) |
            (Trademark.applicant.like(like))
        )
    if scope_group:
        q = q.filter(Trademark.scope_group == scope_group)
    if status:
        q = q.filter(Trademark.status == status)

    total = q.count()
    items = q.order_by(Trademark.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {"total": total, "items": [_tm_to_out(t) for t in items], "page": page, "page_size": page_size}


@router.get("/{tid}")
def get_trademark(tid: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    t = db.query(Trademark).filter(Trademark.id == tid, Trademark.is_deleted == False).first()
    if not t:
        raise HTTPException(status_code=404, detail="商标不存在")

    result = _tm_to_out(t)

    files = db.query(FileStorage).filter(
        FileStorage.business_type == "trademark", FileStorage.business_id == tid
    ).order_by(FileStorage.uploaded_at.desc()).all()
    result["files"] = [{
        "id": f.id, "original_name": f.original_name, "file_type": f.file_type,
        "file_size": f.file_size, "uploaded_at": f.uploaded_at
    } for f in files]

    return result


@router.post("", status_code=201)
def create_trademark(data: TrademarkCreate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    t = Trademark(**data.model_dump(), created_by=current_user.id)
    db.add(t)
    db.commit()
    db.refresh(t)

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="create", business_type="trademark", business_id=t.id,
                   after_value=json.dumps(data.model_dump(), default=str, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {"id": t.id, "message": "创建成功"}


@router.put("/{tid}")
def update_trademark(tid: int, data: TrademarkUpdate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    t = db.query(Trademark).filter(Trademark.id == tid, Trademark.is_deleted == False).first()
    if not t:
        raise HTTPException(status_code=404, detail="商标不存在")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    t.updated_at = datetime.now()
    db.commit()

    return {"message": "更新成功"}


@router.delete("/{tid}")
def delete_trademark(tid: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    t = db.query(Trademark).filter(Trademark.id == tid, Trademark.is_deleted == False).first()
    if not t:
        raise HTTPException(status_code=404, detail="商标不存在")

    t.is_deleted = True
    db.commit()

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="delete", business_type="trademark", business_id=tid,
                   before_value=json.dumps({"name": t.trademark_name}, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {"message": "已删除"}
