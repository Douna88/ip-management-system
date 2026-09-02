"""Agency router: CRUD, price changes, stats."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Agency, Patent, Trademark, AgencyPriceChange, AuditLog, FileStorage, SysUser, PatentFee
from app.schemas import AgencyCreate, AgencyUpdate, PriceChangeCreate
from app.security import get_current_user
import json

router = APIRouter(prefix="/api/agencies", tags=["agency"])


def _agency_to_out(a: Agency, db: Session) -> dict:
    patent_count = db.query(Patent).filter(Patent.agency_id == a.id, Patent.is_deleted == False).count()
    tm_count = db.query(Trademark).filter(Trademark.agency_id == a.id, Trademark.is_deleted == False).count()

    # Total amount from fees
    total_amount = db.query(func.sum(PatentFee.actual_pay_amount)).filter(
        PatentFee.agency_id == a.id
    ).scalar() or 0

    # This year amount
    from datetime import date
    year_start = date(date.today().year, 1, 1)
    this_year = db.query(func.sum(PatentFee.actual_pay_amount)).filter(
        PatentFee.agency_id == a.id, PatentFee.actual_pay_date >= year_start
    ).scalar() or 0

    last_year_start = date(date.today().year - 1, 1, 1)
    last_year_end = date(date.today().year - 1, 12, 31)
    last_year = db.query(func.sum(PatentFee.actual_pay_amount)).filter(
        PatentFee.agency_id == a.id,
        PatentFee.actual_pay_date >= last_year_start,
        PatentFee.actual_pay_date <= last_year_end
    ).scalar() or 0

    return {
        "id": a.id,
        "agency_name": a.agency_name,
        "contact_person": a.contact_person,
        "contact_phone": a.contact_phone,
        "email": a.email,
        "address": a.address,
        "business_scope": a.business_scope,
        "cooperation_start": a.cooperation_start,
        "cooperation_end": a.cooperation_end,
        "status": a.status,
        "notes": a.notes,
        "patent_count": patent_count,
        "trademark_count": tm_count,
        "total_amount": float(total_amount),
        "this_year_amount": float(this_year),
        "last_year_amount": float(last_year),
        "created_at": a.created_at,
    }


@router.get("")
def list_agencies(
    search: str = Query(""),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    q = db.query(Agency).filter(Agency.is_deleted == False)
    if search:
        like = f"%{search}%"
        q = q.filter(Agency.agency_name.like(like) | Agency.contact_person.like(like))

    agencies = q.order_by(Agency.created_at.desc()).all()
    return {"total": len(agencies), "items": [_agency_to_out(a, db) for a in agencies]}


@router.get("/{aid}")
def get_agency(aid: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    a = db.query(Agency).filter(Agency.id == aid, Agency.is_deleted == False).first()
    if not a:
        raise HTTPException(status_code=404, detail="代理机构不存在")

    result = _agency_to_out(a, db)

    # Price changes
    changes = db.query(AgencyPriceChange).filter(AgencyPriceChange.agency_id == aid).order_by(
        AgencyPriceChange.change_date.desc()
    ).all()
    result["price_changes"] = [{
        "id": c.id, "change_date": c.change_date, "service_item": c.service_item,
        "old_price": c.old_price, "new_price": c.new_price,
        "change_reason": c.change_reason, "effective_date": c.effective_date,
        "created_at": c.created_at
    } for c in changes]

    # Contract files
    files = db.query(FileStorage).filter(
        FileStorage.business_type == "agency", FileStorage.business_id == aid
    ).order_by(FileStorage.uploaded_at.desc()).all()
    result["files"] = [{
        "id": f.id, "original_name": f.original_name, "file_type": f.file_type,
        "file_size": f.file_size, "uploaded_at": f.uploaded_at
    } for f in files]

    # Related patents (summary)
    related_patents = db.query(Patent).filter(
        Patent.agency_id == aid, Patent.is_deleted == False
    ).order_by(Patent.created_at.desc()).limit(20).all()
    result["related_patents"] = [{
        "id": p.id, "application_no": p.application_no, "patent_name": p.patent_name,
        "patent_type": p.patent_type, "status": p.status
    } for p in related_patents]

    return result


@router.post("", status_code=201)
def create_agency(data: AgencyCreate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    a = Agency(**data.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="create", business_type="agency", business_id=a.id,
                   after_value=json.dumps(data.model_dump(), default=str, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {"id": a.id, "message": "创建成功"}


@router.put("/{aid}")
def update_agency(aid: int, data: AgencyUpdate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    a = db.query(Agency).filter(Agency.id == aid, Agency.is_deleted == False).first()
    if not a:
        raise HTTPException(status_code=404, detail="代理机构不存在")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()

    return {"message": "更新成功"}


@router.delete("/{aid}")
def delete_agency(aid: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    a = db.query(Agency).filter(Agency.id == aid, Agency.is_deleted == False).first()
    if not a:
        raise HTTPException(status_code=404, detail="代理机构不存在")

    a.is_deleted = True
    db.commit()

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="delete", business_type="agency", business_id=aid,
                   before_value=json.dumps({"name": a.agency_name}, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {"message": "已删除"}


# ===== Price Changes =====
@router.post("/{aid}/price-changes", status_code=201)
def create_price_change(
    aid: int,
    data: PriceChangeCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    if data.agency_id != aid:
        raise HTTPException(status_code=400, detail="agency_id不匹配")

    pc = AgencyPriceChange(**data.model_dump(), created_by=current_user.id)
    db.add(pc)
    db.commit()
    db.refresh(pc)

    return {"id": pc.id, "message": "价格调整记录已添加"}


@router.delete("/{aid}/price-changes/{pcid}")
def delete_price_change(
    aid: int,
    pcid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    pc = db.query(AgencyPriceChange).filter(AgencyPriceChange.id == pcid, AgencyPriceChange.agency_id == aid).first()
    if not pc:
        raise HTTPException(status_code=404, detail="价格调整记录不存在")

    db.delete(pc)
    db.commit()
    return {"message": "已删除"}
