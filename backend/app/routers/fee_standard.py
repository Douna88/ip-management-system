"""Fee standard and patent fee overview router."""
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FeeStandard, PatentFee, Patent, Agency, SysUser, AuditLog
from app.security import get_current_user
import json

router = APIRouter(prefix="/api/fees", tags=["fees"])


# ===== Fee Standards =====

@router.get("/standards")
def list_fee_standards(
    category: str = Query("", description="类别筛选"),
    patent_type: str = Query("", description="专利类型筛选"),
    fee_type: str = Query("", description="费用类型筛选"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    q = db.query(FeeStandard)
    if category:
        q = q.filter(FeeStandard.category == category)
    if patent_type:
        q = q.filter(FeeStandard.patent_type == patent_type)
    if fee_type:
        q = q.filter(FeeStandard.fee_type == fee_type)

    standards = q.order_by(FeeStandard.category, FeeStandard.fee_type, FeeStandard.patent_type).all()
    return [{
        "id": s.id,
        "category": s.category,
        "fee_type": s.fee_type,
        "patent_type": s.patent_type,
        "year_start": s.year_start,
        "year_end": s.year_end,
        "standard_amount": s.standard_amount,
        "reduced_85_amount": s.reduced_85_amount,
        "reduced_70_amount": s.reduced_70_amount,
        "unit": s.unit,
        "note": s.note,
        "effective_from": s.effective_from,
        "source": s.source
    } for s in standards]


# ===== Patent Fee Overview (cross-patent) =====

@router.get("/patent-fees")
def list_all_patent_fees(
    search: str = Query("", description="搜索专利名称/申请号"),
    status: str = Query("", description="状态筛选: 待缴/已缴/逾期/滞纳金"),
    urgency: str = Query("", description="紧急度筛选: overdue/urgent/warning/notice"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """List all patent fees across all patents, joined with patent info."""
    q = db.query(PatentFee, Patent).join(
        Patent, PatentFee.patent_id == Patent.id
    ).filter(Patent.is_deleted == False)

    if search:
        like = f"%{search}%"
        q = q.filter(
            (Patent.patent_name.like(like)) |
            (Patent.application_no.like(like)) |
            (Patent.inventors.like(like))
        )
    # 数据库中 status 只有「待缴/已缴」两个值；「逾期/滞纳金」是计算口径，
    # 不能直接拿去匹配 DB 字段，需放到 items 构建完成后按计算值过滤。
    if status in ("待缴", "已缴"):
        q = q.filter(PatentFee.status == status)

    today = date.today()

    # Build results first (need to compute urgency in Python)
    all_results = q.order_by(PatentFee.due_date.asc()).all()

    items = []
    for fee, patent in all_results:
        days_left = None
        fee_urgency = None
        if fee.due_date:
            delta = (fee.due_date - today).days
            days_left = delta
            if fee.status == "已缴":
                fee_urgency = "paid"
            elif delta < 0:
                fee_urgency = "overdue"
            elif delta <= 7:
                fee_urgency = "urgent"
            elif delta <= 30:
                fee_urgency = "warning"
            elif delta <= 90:
                fee_urgency = "notice"
            else:
                fee_urgency = "normal"

        items.append({
            "id": fee.id,
            "patent_id": fee.patent_id,
            "patent_name": patent.patent_name,
            "application_no": patent.application_no,
            "patent_type": patent.patent_type,
            "patent_status": patent.status,
            "fee_year": fee.fee_year,
            "due_date": fee.due_date,
            "actual_pay_date": fee.actual_pay_date,
            "standard_amount": fee.standard_amount,
            "reduced_amount": fee.reduced_amount,
            "actual_pay_amount": fee.actual_pay_amount,
            "receipt_no": fee.receipt_no,
            "status": fee.status,
            "late_fee": fee.late_fee,
            "payment_source": fee.payment_source,
            "notes": fee.notes,
            "days_left": days_left,
            "urgency": fee_urgency,
            "created_at": fee.created_at
        })

    # Filter by urgency
    if urgency:
        items = [i for i in items if i["urgency"] == urgency]

    # 计算口径状态过滤：逾期=未缴且已过应缴日；滞纳金=备注/收据中提及滞纳金
    if status == "逾期":
        items = [i for i in items if i["urgency"] == "overdue"]
    elif status == "滞纳金":
        items = [i for i in items if "滞纳金" in (i.get("notes") or "") or (i.get("late_fee") or 0) > 0]

    total = len(items)
    start = (page - 1) * page_size
    paged = items[start:start + page_size]

    return {
        "total": total,
        "items": paged,
        "page": page,
        "page_size": page_size
    }


@router.put("/patent-fees/{fid}/pay")
def mark_fee_paid(
    fid: int,
    pay_date: str = Query("", description="实际缴费日期 YYYY-MM-DD"),
    pay_amount: float = Query(0, description="实际缴费金额"),
    receipt_no: str = Query("", description="收据编号"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Mark a patent fee as paid."""
    fee = db.query(PatentFee).filter(PatentFee.id == fid).first()
    if not fee:
        raise HTTPException(status_code=404, detail="年费记录不存在")

    old_status = fee.status
    fee.status = "已缴"
    # Parse string date to Python date object (SQLite Date type requirement)
    if pay_date:
        try:
            fee.actual_pay_date = datetime.strptime(pay_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            fee.actual_pay_date = date.today()
    else:
        fee.actual_pay_date = date.today()
    if pay_amount > 0:
        fee.actual_pay_amount = pay_amount
    if receipt_no:
        fee.receipt_no = receipt_no
    db.commit()

    patent = db.query(Patent).filter(Patent.id == fee.patent_id).first()

    log = AuditLog(
        user_id=current_user.id, user_name=current_user.display_name,
        action="update", business_type="patent_fee", business_id=fid,
        before_value=json.dumps({"status": old_status}, ensure_ascii=False),
        after_value=json.dumps({
            "status": "已缴",
            "pay_date": str(fee.actual_pay_date),
            "pay_amount": fee.actual_pay_amount,
            "patent_name": patent.patent_name if patent else None,
            "fee_year": fee.fee_year
        }, ensure_ascii=False)
    )
    db.add(log)
    db.commit()

    return {"message": f"已标记为已缴: {patent.patent_name if patent else ''} 第{fee.fee_year}年费"}


class FeeNotesUpdate(BaseModel):
    notes: str = ""


@router.put("/patent-fees/{fid}/notes")
def update_fee_notes(
    fid: int,
    body: FeeNotesUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """更新专利年费备注"""
    fee = db.query(PatentFee).filter(PatentFee.id == fid).first()
    if not fee:
        raise HTTPException(status_code=404, detail="年费记录不存在")
    fee.notes = (body.notes or "").strip() or None
    db.commit()
    return {"message": "备注已更新", "notes": fee.notes}


@router.delete("/patent-fees/{fid}")
def delete_fee_record(
    fid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """删除一条年费记录（含审计日志）"""
    fee = db.query(PatentFee).filter(PatentFee.id == fid).first()
    if not fee:
        raise HTTPException(status_code=404, detail="年费记录不存在")

    patent = db.query(Patent).filter(Patent.id == fee.patent_id).first()
    snapshot = {
        "patent_name": patent.patent_name if patent else None,
        "fee_year": fee.fee_year,
        "status": fee.status,
        "standard_amount": fee.standard_amount,
        "actual_pay_amount": fee.actual_pay_amount,
    }

    db.delete(fee)
    db.add(AuditLog(
        user_id=current_user.id, user_name=current_user.display_name,
        action="delete", business_type="patent_fee", business_id=fid,
        before_value=json.dumps(snapshot, ensure_ascii=False),
    ))
    db.commit()
    return {"message": "已删除", "fee_id": fid}
