"""Patent router: CRUD, fees, inventors."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Patent, PatentFee, PatentInventor, Agency, AuditLog, FileStorage
from app.schemas import (
    PatentCreate, PatentUpdate, PatentOut,
    PatentFeeCreate, PatentFeeUpdate, PatentFeeOut,
    MessageResponse
)
from app.security import get_current_user
from app.models import SysUser
from app import fee_calculator
import json

router = APIRouter(prefix="/api/patents", tags=["patent"])


def _patent_to_out(p: Patent, db: Session) -> dict:
    """Convert Patent model to dict with agency_name."""
    d = {
        "id": p.id,
        "application_no": p.application_no,
        "patent_name": p.patent_name,
        "patent_type": p.patent_type,
        "status": p.status,
        "application_date": p.application_date,
        "authorization_no": p.authorization_no,
        "authorization_date": p.authorization_date,
        "first_publication_date": p.first_publication_date,
        "applicant": p.applicant,
        "inventors": p.inventors,
        "ipc_classification": p.ipc_classification,
        "correspondence_project": p.correspondence_project,
        "correspondence_product": p.correspondence_product,
        "protection_element": p.protection_element,
        "quick_examination": p.quick_examination,
        "expedited_examination": p.expedited_examination,
        "fee_reduction": p.fee_reduction,
        "fee_reduction_rate": p.fee_reduction_rate,
        "official_fee": p.official_fee,
        "agency_fee": p.agency_fee,
        "pre_examination_fee": p.pre_examination_fee,
        "fee_year1": p.fee_year1,
        "fee_year2": p.fee_year2,
        "fee_year3": p.fee_year3,
        "fee_year4": p.fee_year4,
        "fee_year5": p.fee_year5,
        "fee_year6": p.fee_year6,
        "fee_year7": p.fee_year7,
        "fee_year8": p.fee_year8,
        "fee_year9": p.fee_year9,
        "fee_year10": p.fee_year10,
        "agency_id": p.agency_id,
        "agency_case_no": p.agency_case_no,
        "is_pct": p.is_pct,
        "description": p.description,
        "agency_name": p.agency.agency_name if p.agency else None,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }
    return d


@router.get("")
def list_patents(
    search: str = Query("", description="搜索关键词"),
    patent_type: str = Query("", description="专利类型筛选"),
    status: str = Query("", description="状态筛选"),
    date_from: str = Query("", description="申请日期起始 YYYY-MM-DD"),
    date_to: str = Query("", description="申请日期截止 YYYY-MM-DD"),
    apply_year: str = Query("", description="申请年度筛选，如 2024"),
    grant_year: str = Query("", description="授权年度筛选，如 2024（仅对有授权日的专利生效）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    q = db.query(Patent).filter(Patent.is_deleted == False)

    if search:
        like = f"%{search}%"
        q = q.filter(
            (Patent.patent_name.like(like)) |
            (Patent.application_no.like(like)) |
            (Patent.inventors.like(like)) |
            (Patent.correspondence_project.like(like)) |
            (Patent.correspondence_product.like(like))
        )
    if patent_type:
        q = q.filter(Patent.patent_type == patent_type)
    if status:
        q = q.filter(Patent.status == status)
    if date_from:
        try:
            q = q.filter(Patent.application_date >= datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(Patent.application_date <= datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass
    if apply_year:
        try:
            q = q.filter(extract("year", Patent.application_date) == int(apply_year))
        except (ValueError, TypeError):
            pass
    if grant_year:
        # 授权年度筛选：只匹配有授权日且落在该年度的专利
        try:
            q = q.filter(
                Patent.authorization_date.is_not(None),
                extract("year", Patent.authorization_date) == int(grant_year),
            )
        except (ValueError, TypeError):
            pass

    total = q.count()
    patents = q.order_by(Patent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 年度筛选选项（数据库实际存在的年份，降序；不受当前筛选影响）
    all_years = db.query(Patent.application_date, Patent.authorization_date).filter(
        Patent.is_deleted == False
    ).all()
    apply_years = sorted({d.year for d, _ in all_years if d}, reverse=True)
    grant_years = sorted({d.year for _, d in all_years if d}, reverse=True)

    return {
        "total": total,
        "items": [_patent_to_out(p, db) for p in patents],
        "page": page,
        "page_size": page_size,
        "apply_years": apply_years,
        "grant_years": grant_years
    }


@router.get("/{pid}")
def get_patent(
    pid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    p = db.query(Patent).filter(Patent.id == pid, Patent.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="专利不存在")

    result = _patent_to_out(p, db)

    # Fees
    fees = db.query(PatentFee).filter(PatentFee.patent_id == pid).order_by(PatentFee.fee_year).all()

    # 年费完整性审核（应有年份 vs 实有年份，区分已过期漏写 / 未来未发生 / 重复）
    try:
        result["fee_audit"] = fee_calculator.audit_patent_fees(db, p)
    except Exception:
        result["fee_audit"] = None

    result["fees"] = [{
        "id": f.id, "fee_year": f.fee_year, "due_date": f.due_date,
        "actual_pay_date": f.actual_pay_date, "standard_amount": f.standard_amount,
        "reduced_amount": f.reduced_amount, "actual_pay_amount": f.actual_pay_amount,
        "agency_id": f.agency_id, "receipt_no": f.receipt_no,
        "receipt_file_id": f.receipt_file_id,
        "status": f.status, "late_fee": f.late_fee,
        "payment_source": f.payment_source, "created_at": f.created_at
    } for f in fees]

    # Files
    files = db.query(FileStorage).filter(
        FileStorage.business_type == "patent", FileStorage.business_id == pid
    ).order_by(FileStorage.uploaded_at.desc()).all()
    result["files"] = [{
        "id": f.id, "original_name": f.original_name, "file_type": f.file_type,
        "file_size": f.file_size, "uploaded_at": f.uploaded_at
    } for f in files]

    return result


@router.post("", status_code=201)
def create_patent(
    data: PatentCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    p = Patent(**data.model_dump(), created_by=current_user.id)
    db.add(p)
    db.commit()
    db.refresh(p)

    # 自动生成年费记录（按规则算应缴金额）
    fee_count = 0
    try:
        fees = fee_calculator.generate_patent_fees(db, p, commit=True)
        fee_count = len(fees)
    except Exception:
        db.rollback()

    # Audit
    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="create", business_type="patent", business_id=p.id,
                   after_value=json.dumps(data.model_dump(), default=str, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {"id": p.id, "message": "创建成功", "fee_count": fee_count}


@router.put("/{pid}")
def update_patent(
    pid: int,
    data: PatentUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    p = db.query(Patent).filter(Patent.id == pid, Patent.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="专利不存在")

    before = _patent_to_out(p, db)
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(p, k, v)
    p.updated_at = datetime.now()
    db.commit()
    db.refresh(p)

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="update", business_type="patent", business_id=pid,
                   before_value=json.dumps(before, default=str, ensure_ascii=False),
                   after_value=json.dumps(_patent_to_out(p, db), default=str, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {"message": "更新成功"}


@router.delete("/{pid}")
def delete_patent(
    pid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    p = db.query(Patent).filter(Patent.id == pid, Patent.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="专利不存在")

    p.is_deleted = True
    db.commit()

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="delete", business_type="patent", business_id=pid,
                   before_value=json.dumps({"name": p.patent_name}, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {"message": "已删除"}


# ===== Patent Fees =====
@router.get("/{pid}/fees")
def list_fees(
    pid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    fees = db.query(PatentFee).filter(PatentFee.patent_id == pid).order_by(PatentFee.fee_year).all()
    return [{
        "id": f.id, "patent_id": f.patent_id, "fee_year": f.fee_year,
        "due_date": f.due_date, "actual_pay_date": f.actual_pay_date,
        "standard_amount": f.standard_amount, "reduced_amount": f.reduced_amount,
        "actual_pay_amount": f.actual_pay_amount, "agency_id": f.agency_id,
        "receipt_no": f.receipt_no, "status": f.status, "late_fee": f.late_fee,
        "payment_source": f.payment_source, "created_at": f.created_at
    } for f in fees]


@router.post("/{pid}/fees", status_code=201)
def create_fee(
    pid: int,
    data: PatentFeeCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    if data.patent_id != pid:
        raise HTTPException(status_code=400, detail="patent_id不匹配")
    fee = PatentFee(**data.model_dump())
    db.add(fee)
    db.commit()
    db.refresh(fee)

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="create", business_type="patent_fee", business_id=fee.id,
                   after_value=json.dumps(data.model_dump(), default=str, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {"id": fee.id, "message": "年费记录已添加"}


@router.put("/{pid}/fees/{fid}")
def update_fee(
    pid: int,
    fid: int,
    data: PatentFeeUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    fee = db.query(PatentFee).filter(PatentFee.id == fid, PatentFee.patent_id == pid).first()
    if not fee:
        raise HTTPException(status_code=404, detail="年费记录不存在")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(fee, k, v)
    db.commit()
    db.refresh(fee)

    return {"message": "年费记录已更新"}


@router.delete("/{pid}/fees/{fid}")
def delete_fee(
    pid: int,
    fid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    fee = db.query(PatentFee).filter(PatentFee.id == fid, PatentFee.patent_id == pid).first()
    if not fee:
        raise HTTPException(status_code=404, detail="年费记录不存在")

    db.delete(fee)
    db.commit()

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="delete", business_type="patent_fee", business_id=fid)
    db.add(log)
    db.commit()

    return {"message": "年费记录已删除"}


@router.post("/{pid}/fees/complete")
def complete_fees(
    pid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """年费审核一键补写：只补缺失年份，不覆盖已有记录（保留已缴/凭证）。"""
    p = db.query(Patent).filter(Patent.id == pid, Patent.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="专利不存在")

    audit = fee_calculator.audit_patent_fees(db, p)
    if not audit["has_fee_rule"]:
        return {"message": f"该类型（{p.patent_type}）无年费规则，无需补写",
                "created": [], "fee_audit": audit}
    if not audit["missing"]:
        return {"message": "年费记录完整，无缺失年份", "created": [], "fee_audit": audit}

    created = fee_calculator.fill_missing_fees(db, p, commit=True)
    import json as _json
    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="update", business_type="patent", business_id=pid,
                   before_value=_json.dumps({
                       "op": "年费审核补写",
                       "created_years": [f.fee_year for f in created],
                   }, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {
        "message": f"已补写 {len(created)} 条缺失年份年费记录",
        "created": [
            {"fee_year": f.fee_year, "due_date": f.due_date,
             "standard_amount": f.standard_amount, "status": f.status}
            for f in created
        ],
        "fee_audit": fee_calculator.audit_patent_fees(db, p),
    }
