"""Bonus router: rules, batches, items, approvals, payments."""
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    BonusRule, PatentBonusBatch, PatentBonusItem,
    PatentBonusDetail, PatentBonusApproval,
    Patent, PatentInventor, Employee, AuditLog, SysUser
)
from app.schemas import (
    BonusRuleOut, BonusBatchCreate, BonusBatchStatusUpdate,
    BonusItemApprove, BonusItemPaymentUpdate,
    BonusItemCreate, BonusItemUpdate
)
from app.security import get_current_user
import json

router = APIRouter(prefix="/api/bonus", tags=["bonus"])


# ===== Bonus Rules =====

@router.get("/rules")
def list_rules(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    rules = db.query(BonusRule).order_by(BonusRule.effective_from.desc()).all()
    return [{
        "id": r.id,
        "rule_name": r.rule_name,
        "effective_from": r.effective_from,
        "effective_until": r.effective_until,
        "is_current": r.is_current,
        "rules_json": r.rules_json,
        "rules_parsed": json.loads(r.rules_json) if r.rules_json else {},
        "created_at": r.created_at
    } for r in rules]


@router.get("/rules/{rid}")
def get_rule(
    rid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    r = db.query(BonusRule).filter(BonusRule.id == rid).first()
    if not r:
        raise HTTPException(status_code=404, detail="奖金规则不存在")
    return {
        "id": r.id,
        "rule_name": r.rule_name,
        "effective_from": r.effective_from,
        "effective_until": r.effective_until,
        "is_current": r.is_current,
        "rules_json": r.rules_json,
        "rules_parsed": json.loads(r.rules_json) if r.rules_json else {},
        "raw_text": r.raw_text,
        "created_at": r.created_at
    }


# ===== Bonus Batches =====

@router.get("/batches")
def list_batches(
    status: str = Query("", description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    q = db.query(PatentBonusBatch)
    if status:
        q = q.filter(PatentBonusBatch.status == status)

    total = q.count()
    batches = q.order_by(PatentBonusBatch.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{
            "id": b.id,
            "batch_code": b.batch_code,
            "batch_name": b.batch_name,
            "rule_id": b.rule_id,
            "rule_name": b.rule.rule_name if b.rule else None,
            "period_start": b.period_start,
            "period_end": b.period_end,
            "total_amount": b.total_amount,
            "status": b.status,
            "item_count": len(b.items),
            "created_by": b.created_by,
            "created_at": b.created_at,
            "read_only": (b.period_start.year < 2026) if b.period_start else True
        } for b in batches]
    }


@router.post("/batches", status_code=201)
def create_batch(
    data: BonusBatchCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Create a bonus batch — auto-calculates items from patents in the period."""
    rule = db.query(BonusRule).filter(BonusRule.id == data.rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="奖金规则不存在")

    rules = json.loads(rule.rules_json) if rule.rules_json else {}

    # Map patent_type to rule key (handles naming differences)
    def get_type_rules(patent_type, is_pct):
        # Try exact match first
        if patent_type in rules:
            return rules[patent_type]
        # Try aliases
        aliases = {
            "软著": ["软件著作权", "软著"],
            "软产": ["软件著作权", "软产"],
            "发明": ["PCT国际发明专利"] if is_pct else ["发明"],
        }
        for alias in aliases.get(patent_type, []):
            if alias in rules:
                return rules[alias]
        # Try case-insensitive match
        for key in rules:
            if key.lower() == patent_type.lower():
                return rules[key]
        return {}

    # Check if PCT patent gets extra bonus from PCT rule
    def get_pct_bonus(is_pct, milestone_hit):
        if not is_pct:
            return 0.0
        for key in ["PCT叠加", "PCT国际发明专利"]:
            if key in rules:
                pct_rules = rules[key]
                bonus = 0.0
                if "受理" in milestone_hit and "国际阶段" in pct_rules:
                    bonus += pct_rules.get("国际阶段", 0)
                if "授权" in milestone_hit and "国家阶段" in pct_rules:
                    bonus += pct_rules.get("国家阶段", 0)
                # If no stage-specific keys, use 合计
                if bonus == 0 and "合计" in pct_rules:
                    bonus += pct_rules.get("合计", 0)
                return bonus
        return 0.0

    # Generate batch code: BONUS-YYYYMM-XXX
    today_str = datetime.now().strftime("%Y%m")
    existing = db.query(PatentBonusBatch).filter(
        PatentBonusBatch.batch_code.like(f"BONUS-{today_str}%")
    ).count()
    batch_code = f"BONUS-{today_str}-{existing + 1:03d}"

    batch = PatentBonusBatch(
        batch_code=batch_code,
        batch_name=data.batch_name,
        rule_id=data.rule_id,
        period_start=data.period_start,
        period_end=data.period_end,
        status="草稿",
        created_by=current_user.id
    )
    db.add(batch)
    db.flush()

    # Find patents with milestones in the period
    # 受理 milestone: application_date in [period_start, period_end]
    # 授权 milestone: authorization_date in [period_start, period_end]
    patents = db.query(Patent).filter(Patent.is_deleted == False).all()

    total_amount = 0.0
    item_count = 0

    for p in patents:
        milestones = []
        # Check 受理
        if p.application_date and data.period_start <= p.application_date <= data.period_end:
            milestones.append("受理")
        # Check 授权
        if p.authorization_date and data.period_start <= p.authorization_date <= data.period_end:
            milestones.append("授权")

        if not milestones:
            continue

        patent_type = p.patent_type
        type_rules = get_type_rules(patent_type, p.is_pct)

        base_amount = 0.0
        milestone_detail = {}
        for ms in milestones:
            amt = type_rules.get(ms, 0)
            base_amount += amt
            milestone_detail[ms] = amt

        # PCT bonus
        pct_bonus = get_pct_bonus(p.is_pct, milestones)

        total_item_amount = base_amount + pct_bonus
        if total_item_amount == 0:
            continue

        milestone_str = "+".join(milestones)
        item = PatentBonusItem(
            batch_id=batch.id,
            patent_id=p.id,
            patent_type=p.patent_type,
            patent_name=p.patent_name,
            milestone=milestone_str,
            rule_id=rule.id,
            base_amount=base_amount,
            pct_bonus=pct_bonus,
            total_amount=total_item_amount,
            payment_status="待发",
            source="系统计算"
        )
        db.add(item)
        db.flush()

        # Create per-inventor details
        inventors = db.query(PatentInventor).filter(
            PatentInventor.patent_id == p.id
        ).order_by(PatentInventor.order_no).all()

        if not inventors and p.inventors:
            # Fallback: parse comma-separated inventors string
            names = [n.strip() for n in p.inventors.split(",") if n.strip()]
            if names:
                equal_share = total_item_amount / len(names)
                for idx, name in enumerate(names):
                    emp = db.query(Employee).filter(Employee.name == name).first()
                    detail = PatentBonusDetail(
                        bonus_item_id=item.id,
                        inventor_id=emp.id if emp else None,
                        external_name=name if not emp else None,
                        contribution_ratio=round(100.0 / len(names), 2),
                        amount=round(equal_share, 2),
                        milestone_amount=json.dumps(milestone_detail, ensure_ascii=False),
                        payment_status="待发"
                    )
                    db.add(detail)
        else:
            for inv in inventors:
                ratio = (inv.contribution_ratio or 0) / 100.0
                if ratio == 0 and len(inventors) > 0:
                    ratio = 1.0 / len(inventors)
                name = None
                if inv.employee:
                    name = inv.employee.name
                elif inv.external_name:
                    name = inv.external_name
                else:
                    continue

                detail = PatentBonusDetail(
                    bonus_item_id=item.id,
                    inventor_id=inv.employee_id,
                    external_name=inv.external_name,
                    contribution_ratio=inv.contribution_ratio or round(100.0 / len(inventors), 2),
                    amount=round(total_item_amount * ratio, 2),
                    milestone_amount=json.dumps(milestone_detail, ensure_ascii=False),
                    payment_status="待发"
                )
                db.add(detail)

        total_amount += total_item_amount
        item_count += 1

    batch.total_amount = round(total_amount, 2)
    db.commit()

    # Audit log
    log = AuditLog(
        user_id=current_user.id, user_name=current_user.display_name,
        action="create", business_type="bonus_batch", business_id=batch.id,
        after_value=json.dumps({
            "batch_code": batch_code,
            "batch_name": data.batch_name,
            "item_count": item_count,
            "total_amount": round(total_amount, 2)
        }, default=str, ensure_ascii=False)
    )
    db.add(log)
    db.commit()

    return {
        "id": batch.id,
        "batch_code": batch_code,
        "item_count": item_count,
        "total_amount": round(total_amount, 2),
        "message": f"奖金批次已创建，共 {item_count} 项专利，总金额 ¥{total_amount:.2f}"
    }


@router.get("/batches/{bid}")
def get_batch(
    bid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    b = db.query(PatentBonusBatch).filter(PatentBonusBatch.id == bid).first()
    if not b:
        raise HTTPException(status_code=404, detail="奖金批次不存在")

    items = db.query(PatentBonusItem).filter(
        PatentBonusItem.batch_id == bid
    ).order_by(PatentBonusItem.total_amount.desc()).all()

    item_list = []
    for item in items:
        details = db.query(PatentBonusDetail).filter(
            PatentBonusDetail.bonus_item_id == item.id
        ).all()

        detail_list = []
        inventor_names = []
        for d in details:
            inventor_name = None
            if d.inventor:
                inventor_name = d.inventor.name
            elif d.external_name:
                inventor_name = d.external_name
            if inventor_name:
                inventor_names.append(inventor_name)

            detail_list.append({
                "id": d.id,
                "inventor_id": d.inventor_id,
                "inventor_name": inventor_name,
                "contribution_ratio": d.contribution_ratio,
                "amount": d.amount,
                "milestone_amount": d.milestone_amount,
                "payment_status": d.payment_status
            })

        # Get patent fields if linked
        application_no = None
        application_date = None
        authorization_date = None
        if item.patent_id:
            pat = db.query(Patent).filter(Patent.id == item.patent_id).first()
            if pat:
                application_no = pat.application_no
                application_date = pat.application_date
                authorization_date = pat.authorization_date

        # Approvals
        approvals = db.query(PatentBonusApproval).filter(
            PatentBonusApproval.bonus_item_id == item.id
        ).all()

        item_list.append({
            "id": item.id,
            "patent_id": item.patent_id,
            "patent_type": item.patent_type,
            "patent_name": item.patent_name,
            "application_no": application_no,
            "application_date": str(application_date) if application_date else None,
            "issued_date": str(authorization_date) if authorization_date else None,
            "milestone": item.milestone,
            "department": item.department,
            "approved_amount": item.approved_amount,
            "received_amount": item.received_amount,
            "applied_amount": item.applied_amount,
            "base_amount": item.base_amount,
            "pct_bonus": item.pct_bonus,
            "total_amount": item.total_amount,
            "payment_status": item.payment_status,
            "payment_date": str(item.payment_date) if item.payment_date else None,
            "source": item.source,
            "ai_explanation": item.ai_explanation,
            "inventor_str": ", ".join(inventor_names) if inventor_names else "",
            "details": detail_list,
            "approvals": [{
                "id": a.id,
                "step": a.step,
                "approver_id": a.approver_id,
                "approve_status": a.approve_status,
                "approve_comment": a.approve_comment,
                "approve_time": a.approve_time
            } for a in approvals]
        })

    return {
        "id": b.id,
        "batch_code": b.batch_code,
        "batch_name": b.batch_name,
        "rule_id": b.rule_id,
        "rule_name": b.rule.rule_name if b.rule else None,
        "period_start": b.period_start,
        "period_end": b.period_end,
        "total_amount": b.total_amount,
        "status": b.status,
        "created_by": b.created_by,
        "created_at": b.created_at,
        "read_only": (b.period_start.year < 2026) if b.period_start else True,
        "items": item_list
    }


@router.put("/batches/{bid}/status")
def update_batch_status(
    bid: int,
    data: BonusBatchStatusUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    b = db.query(PatentBonusBatch).filter(PatentBonusBatch.id == bid).first()
    if not b:
        raise HTTPException(status_code=404, detail="奖金批次不存在")

    valid_statuses = ["草稿", "审批中", "已批准", "已发放"]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效状态，可选: {', '.join(valid_statuses)}")

    old_status = b.status
    b.status = data.status
    db.commit()

    log = AuditLog(
        user_id=current_user.id, user_name=current_user.display_name,
        action="update", business_type="bonus_batch", business_id=bid,
        before_value=json.dumps({"status": old_status}, ensure_ascii=False),
        after_value=json.dumps({"status": data.status}, ensure_ascii=False)
    )
    db.add(log)
    db.commit()

    return {"message": f"批次状态已更新为: {data.status}"}


# ===== Bonus Item Approvals =====

@router.put("/items/{iid}/approve")
def approve_item(
    iid: int,
    data: BonusItemApprove,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    item = db.query(PatentBonusItem).filter(PatentBonusItem.id == iid).first()
    if not item:
        raise HTTPException(status_code=404, detail="奖金条目不存在")

    approval = PatentBonusApproval(
        bonus_item_id=iid,
        step=data.step,
        approver_id=current_user.id,
        approve_status=data.approve_status,
        approve_comment=data.approve_comment,
        approve_time=datetime.now()
    )
    db.add(approval)
    db.commit()

    return {"message": f"审批已记录: {data.approve_status}"}


@router.put("/items/{iid}/payment")
def update_item_payment(
    iid: int,
    data: BonusItemPaymentUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    item = db.query(PatentBonusItem).filter(PatentBonusItem.id == iid).first()
    if not item:
        raise HTTPException(status_code=404, detail="奖金条目不存在")

    item.payment_status = data.payment_status
    if data.payment_date:
        item.payment_date = data.payment_date
    elif data.payment_status == "已发":
        item.payment_date = date.today()

    # Update all details too
    details = db.query(PatentBonusDetail).filter(
        PatentBonusDetail.bonus_item_id == iid
    ).all()
    for d in details:
        d.payment_status = data.payment_status

    db.commit()

    return {"message": f"发放状态已更新为: {data.payment_status}"}


# ===== Bonus Item CRUD (for editable batches) =====

@router.post("/batches/{bid}/items", status_code=201)
def add_bonus_item(
    bid: int,
    data: BonusItemCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Add a single bonus item to a batch (editable batches only)."""
    batch = db.query(PatentBonusBatch).filter(PatentBonusBatch.id == bid).first()
    if not batch:
        raise HTTPException(status_code=404, detail="奖金批次不存在")

    if batch.period_start and batch.period_start.year < 2026:
        raise HTTPException(status_code=400, detail="历史批次（2026年前）不可修改")

    # Determine total amount: use applied_amount if > 0, else approved_amount
    item_total = data.applied_amount if data.applied_amount and data.applied_amount > 0 else (
        data.approved_amount if data.approved_amount else 0
    )

    # Get patent info if linked
    patent_type = data.patent_type
    patent_name = data.patent_name
    if data.patent_id:
        pat = db.query(Patent).filter(Patent.id == data.patent_id).first()
        if pat:
            patent_type = pat.patent_type or patent_type
            patent_name = pat.patent_name or patent_name

    item = PatentBonusItem(
        batch_id=bid,
        patent_id=data.patent_id,
        patent_type=patent_type,
        patent_name=patent_name,
        milestone=data.milestone or "手动添加",
        department=data.department,
        approved_amount=data.approved_amount or 0,
        received_amount=data.received_amount or 0,
        applied_amount=data.applied_amount or 0,
        rule_id=batch.rule_id,
        base_amount=item_total,
        pct_bonus=0,
        total_amount=item_total,
        payment_status=data.bonus_status or "待发",
        source="手动添加"
    )
    db.add(item)
    db.flush()

    # Create per-inventor details
    if data.inventor_str:
        sep = "," if "," in data.inventor_str else (";" if ";" in data.inventor_str else "、")
        inv_names = [n.strip() for n in data.inventor_str.split(sep) if n.strip()]
        if inv_names:
            ratio = round(100 / len(inv_names), 2)
            per_amount = round(item_total * ratio / 100, 2)
            for inv_name in inv_names:
                emp = db.query(Employee).filter(
                    Employee.name == inv_name, Employee.is_deleted == False
                ).first()
                detail = PatentBonusDetail(
                    bonus_item_id=item.id,
                    inventor_id=emp.id if emp else None,
                    external_name=inv_name if not emp else None,
                    contribution_ratio=ratio,
                    amount=per_amount,
                    payment_status=data.bonus_status or "待发"
                )
                db.add(detail)

    # Recalculate batch total
    all_items = db.query(PatentBonusItem).filter(PatentBonusItem.batch_id == bid).all()
    batch.total_amount = round(sum(i.total_amount or 0 for i in all_items), 2)

    db.commit()

    log = AuditLog(
        user_id=current_user.id, user_name=current_user.display_name,
        action="create", business_type="bonus_item", business_id=item.id,
        after_value=json.dumps({"batch_id": bid, "patent_name": patent_name, "amount": item_total}, ensure_ascii=False)
    )
    db.add(log)
    db.commit()

    return {"message": f"奖金条目已添加: {patent_name}", "item_id": item.id}


@router.put("/items/{iid}")
def update_bonus_item(
    iid: int,
    data: BonusItemUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Update a single bonus item (editable batches only)."""
    item = db.query(PatentBonusItem).filter(PatentBonusItem.id == iid).first()
    if not item:
        raise HTTPException(status_code=404, detail="奖金条目不存在")

    batch = db.query(PatentBonusBatch).filter(PatentBonusBatch.id == item.batch_id).first()
    if batch and batch.period_start and batch.period_start.year < 2026:
        raise HTTPException(status_code=400, detail="历史批次（2026年前）不可修改")

    old_values = {
        "patent_name": item.patent_name,
        "patent_type": item.patent_type,
        "department": item.department,
        "approved_amount": item.approved_amount,
        "received_amount": item.received_amount,
        "applied_amount": item.applied_amount,
        "payment_status": item.payment_status
    }

    if data.patent_name is not None:
        item.patent_name = data.patent_name
    if data.patent_type is not None:
        item.patent_type = data.patent_type
    if data.department is not None:
        item.department = data.department
    if data.milestone is not None:
        item.milestone = data.milestone
    if data.approved_amount is not None:
        item.approved_amount = data.approved_amount
    if data.received_amount is not None:
        item.received_amount = data.received_amount
    if data.applied_amount is not None:
        item.applied_amount = data.applied_amount
        # Update total_amount to match applied_amount
        item.total_amount = data.applied_amount if data.applied_amount > 0 else item.total_amount
        item.base_amount = data.applied_amount if data.applied_amount > 0 else item.base_amount
    if data.bonus_status is not None:
        item.payment_status = data.bonus_status

    # Recalculate total_amount
    item_total = item.applied_amount if item.applied_amount and item.applied_amount > 0 else (
        item.approved_amount if item.approved_amount else 0
    )
    item.total_amount = item_total
    item.base_amount = item_total

    # Update inventor details if inventor_str provided
    if data.inventor_str is not None:
        # Delete existing details
        db.query(PatentBonusDetail).filter(
            PatentBonusDetail.bonus_item_id == iid
        ).delete(synchronize_session=False)

        if data.inventor_str:
            sep = "," if "," in data.inventor_str else (";" if ";" in data.inventor_str else "、")
            inv_names = [n.strip() for n in data.inventor_str.split(sep) if n.strip()]
            if inv_names:
                ratio = round(100 / len(inv_names), 2)
                per_amount = round(item_total * ratio / 100, 2)
                for inv_name in inv_names:
                    emp = db.query(Employee).filter(
                        Employee.name == inv_name, Employee.is_deleted == False
                    ).first()
                    detail = PatentBonusDetail(
                        bonus_item_id=iid,
                        inventor_id=emp.id if emp else None,
                        external_name=inv_name if not emp else None,
                        contribution_ratio=ratio,
                        amount=per_amount,
                        payment_status=item.payment_status
                    )
                    db.add(detail)

    # Recalculate batch total
    all_items = db.query(PatentBonusItem).filter(PatentBonusItem.batch_id == item.batch_id).all()
    batch.total_amount = round(sum(i.total_amount or 0 for i in all_items), 2)

    db.commit()

    log = AuditLog(
        user_id=current_user.id, user_name=current_user.display_name,
        action="update", business_type="bonus_item", business_id=iid,
        before_value=json.dumps(old_values, ensure_ascii=False, default=str),
        after_value=json.dumps({
            "patent_name": item.patent_name,
            "approved_amount": item.approved_amount,
            "applied_amount": item.applied_amount
        }, ensure_ascii=False, default=str)
    )
    db.add(log)
    db.commit()

    return {"message": "奖金条目已更新"}


@router.delete("/items/{iid}")
def delete_bonus_item(
    iid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Delete a single bonus item (editable batches only)."""
    item = db.query(PatentBonusItem).filter(PatentBonusItem.id == iid).first()
    if not item:
        raise HTTPException(status_code=404, detail="奖金条目不存在")

    batch = db.query(PatentBonusBatch).filter(PatentBonusBatch.id == item.batch_id).first()
    if batch and batch.period_start and batch.period_start.year < 2026:
        raise HTTPException(status_code=400, detail="历史批次（2026年前）不可修改")

    batch_id = item.batch_id
    patent_name = item.patent_name

    # Delete details first
    db.query(PatentBonusDetail).filter(
        PatentBonusDetail.bonus_item_id == iid
    ).delete(synchronize_session=False)
    db.delete(item)

    # Recalculate batch total
    all_items = db.query(PatentBonusItem).filter(PatentBonusItem.batch_id == batch_id).all()
    if batch:
        batch.total_amount = round(sum(i.total_amount or 0 for i in all_items), 2)

    db.commit()

    log = AuditLog(
        user_id=current_user.id, user_name=current_user.display_name,
        action="delete", business_type="bonus_item", business_id=iid,
        before_value=json.dumps({"patent_name": patent_name}, ensure_ascii=False)
    )
    db.add(log)
    db.commit()

    return {"message": f"奖金条目已删除: {patent_name}"}


@router.delete("/batches/{bid}")
def delete_batch(
    bid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    b = db.query(PatentBonusBatch).filter(PatentBonusBatch.id == bid).first()
    if not b:
        raise HTTPException(status_code=404, detail="奖金批次不存在")

    if b.status not in ("草稿",):
        raise HTTPException(status_code=400, detail="只有草稿状态的批次可以删除")

    db.delete(b)
    db.commit()

    log = AuditLog(
        user_id=current_user.id, user_name=current_user.display_name,
        action="delete", business_type="bonus_batch", business_id=bid,
        before_value=json.dumps({"batch_code": b.batch_code, "batch_name": b.batch_name}, ensure_ascii=False)
    )
    db.add(log)
    db.commit()

    return {"message": "批次已删除"}


# ===== Patent Bonus History =====

@router.get("/patent/{pid}")
def get_patent_bonus_history(
    pid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Get all bonus items for a specific patent, across all batches."""
    items = db.query(PatentBonusItem).filter(
        PatentBonusItem.patent_id == pid
    ).order_by(PatentBonusItem.id.desc()).all()

    result = []
    for item in items:
        batch = db.query(PatentBonusBatch).filter(
            PatentBonusBatch.id == item.batch_id
        ).first()

        details = db.query(PatentBonusDetail).filter(
            PatentBonusDetail.bonus_item_id == item.id
        ).all()

        detail_list = []
        for d in details:
            inventor_name = d.inventor.name if d.inventor else d.external_name
            detail_list.append({
                "id": d.id,
                "inventor_name": inventor_name,
                "contribution_ratio": d.contribution_ratio,
                "amount": d.amount,
                "payment_status": d.payment_status
            })

        result.append({
            "id": item.id,
            "batch_id": item.batch_id,
            "batch_code": batch.batch_code if batch else None,
            "batch_name": batch.batch_name if batch else None,
            "batch_status": batch.status if batch else None,
            "milestone": item.milestone,
            "department": item.department,
            "approved_amount": item.approved_amount,
            "received_amount": item.received_amount,
            "applied_amount": item.applied_amount,
            "base_amount": item.base_amount,
            "pct_bonus": item.pct_bonus,
            "total_amount": item.total_amount,
            "payment_status": item.payment_status,
            "payment_date": item.payment_date,
            "source": item.source,
            "details": detail_list
        })

    total_amount = sum(i["total_amount"] or 0 for i in result)
    return {
        "patent_id": pid,
        "item_count": len(result),
        "total_amount": total_amount,
        "items": result
    }
