"""Dashboard router: stats, reminders, audit logs."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Patent, Trademark, PatentFee, AuditLog, SysUser
from app.security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    today = date.today()
    future_90 = today + timedelta(days=90)
    future_365 = today + timedelta(days=365)

    patent_total = db.query(Patent).filter(Patent.is_deleted == False).count()
    patent_active = db.query(Patent).filter(
        Patent.is_deleted == False, Patent.status.in_(["授权", "已登记"])
    ).count()

    tm_total = db.query(Trademark).filter(Trademark.is_deleted == False).count()
    tm_active = db.query(Trademark).filter(
        Trademark.is_deleted == False, Trademark.status.in_(["已注册", "已续展"])
    ).count()

    # Fee reminders: due within 90 days, not paid
    fee_pending = db.query(PatentFee).filter(
        PatentFee.status == "待缴",
        PatentFee.due_date.isnot(None),
        PatentFee.due_date <= future_90
    ).all()
    fee_pending_count = len(fee_pending)
    fee_pending_amount = sum(f.standard_amount or 0 for f in fee_pending)

    # Trademark renewal reminders
    tm_renewal = db.query(Trademark).filter(
        Trademark.is_deleted == False,
        Trademark.status.in_(["已注册", "已续展"]),
        Trademark.valid_until.isnot(None),
        Trademark.valid_until <= future_365
    ).count()

    # Type distribution
    type_dist = {}
    type_rows = db.query(Patent.patent_type, func.count(Patent.id)).filter(
        Patent.is_deleted == False
    ).group_by(Patent.patent_type).all()
    for t, c in type_rows:
        type_dist[t or "未分类"] = c

    # Status distribution
    status_dist = {}
    status_rows = db.query(Patent.status, func.count(Patent.id)).filter(
        Patent.is_deleted == False
    ).group_by(Patent.status).all()
    for s, c in status_rows:
        status_dist[s or "未知"] = c

    return {
        "patent_total": patent_total,
        "patent_active": patent_active,
        "trademark_total": tm_total,
        "trademark_active": tm_active,
        "fee_pending_count": fee_pending_count,
        "fee_pending_amount": float(fee_pending_amount),
        "tm_renewal_count": tm_renewal,
        "patent_type_dist": type_dist,
        "patent_status_dist": status_dist,
    }


@router.get("/reminders")
def get_reminders(
    days: int = Query(90, description="未来N天内的到期提醒"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    today = date.today()
    future = today + timedelta(days=days)

    # Patent fee reminders
    fee_reminders = db.query(PatentFee, Patent).join(
        Patent, PatentFee.patent_id == Patent.id
    ).filter(
        PatentFee.status == "待缴",
        PatentFee.due_date.isnot(None),
        PatentFee.due_date <= future
    ).order_by(PatentFee.due_date).all()

    fee_list = []
    for fee, patent in fee_reminders:
        due = fee.due_date
        days_left = (due - today).days if due else 0
        urgency = "overdue" if days_left < 0 else ("urgent" if days_left <= 30 else ("warning" if days_left <= 60 else "notice"))
        fee_list.append({
            "type": "patent_fee",
            "id": fee.id,
            "patent_id": patent.id,
            "patent_name": patent.patent_name,
            "patent_type": patent.patent_type,
            "application_no": patent.application_no,
            "fee_year": fee.fee_year,
            "due_date": str(due) if due else None,
            "days_left": days_left,
            "standard_amount": fee.standard_amount,
            "reduced_amount": fee.reduced_amount,
            "urgency": urgency,
        })

    # Trademark renewal reminders
    future_365 = today + timedelta(days=365)
    tm_reminders = db.query(Trademark).filter(
        Trademark.is_deleted == False,
        Trademark.status.in_(["已注册", "已续展"]),
        Trademark.valid_until.isnot(None),
        Trademark.valid_until <= future_365
    ).order_by(Trademark.valid_until).all()

    tm_list = []
    for tm in tm_reminders:
        due = tm.valid_until
        days_left = (due - today).days if due else 0
        urgency = "overdue" if days_left < 0 else ("urgent" if days_left <= 30 else ("warning" if days_left <= 90 else "notice"))
        tm_list.append({
            "type": "trademark_renewal",
            "id": tm.id,
            "trademark_name": tm.trademark_name,
            "trademark_no": tm.trademark_no,
            "valid_until": str(due) if due else None,
            "days_left": days_left,
            "scope_group": tm.scope_group,
            "urgency": urgency,
        })

    return {"fee_reminders": fee_list, "tm_reminders": tm_list}


@router.get("/audit-logs")
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    business_type: str = Query(""),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    q = db.query(AuditLog)
    if business_type:
        q = q.filter(AuditLog.business_type == business_type)

    total = q.count()
    logs = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "items": [{
            "id": l.id, "user_id": l.user_id, "user_name": l.user_name,
            "action": l.action, "business_type": l.business_type,
            "business_id": l.business_id, "created_at": l.created_at,
        } for l in logs],
        "page": page,
        "page_size": page_size
    }
