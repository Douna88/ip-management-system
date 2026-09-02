"""Settings admin router: user management, fee standard management."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SysUser, Employee, FeeStandard, AuditLog, FileStorage
from app.security import get_current_user, hash_password, verify_password
from app.schemas import UserCreate, UserOut
from pydantic import BaseModel
from typing import Optional
from datetime import date
import json
import bcrypt

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ===== User Management =====
class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class UserPasswordReset(BaseModel):
    new_password: str


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    users = db.query(SysUser).order_by(SysUser.created_at.desc()).all()
    return {
        "total": len(users),
        "items": [{
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "email": u.email,
            "role": u.role,
            "status": u.status,
            "last_login_at": u.last_login_at,
            "created_at": u.created_at
        } for u in users]
    }


@router.post("/users", status_code=201)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    existing = db.query(SysUser).filter(SysUser.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = SysUser(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        email=data.email,
        role=data.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="create", business_type="user", business_id=user.id,
                   after_value=json.dumps({"username": user.username, "role": user.role}))
    db.add(log)
    db.commit()

    return {"id": user.id, "message": "用户创建成功"}


@router.put("/users/{uid}")
def update_user(
    uid: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    if current_user.role != "admin" and current_user.id != uid:
        raise HTTPException(status_code=403, detail="无权限")

    user = db.query(SysUser).filter(SysUser.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return {"message": "更新成功"}


@router.put("/users/{uid}/password")
def reset_password(
    uid: int,
    data: UserPasswordReset,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    if current_user.role != "admin" and current_user.id != uid:
        raise HTTPException(status_code=403, detail="无权限")

    user = db.query(SysUser).filter(SysUser.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.password_hash = hash_password(data.new_password)
    db.commit()

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="update", business_type="user", business_id=uid,
                   after_value=json.dumps({"action": "password_reset"}))
    db.add(log)
    db.commit()

    return {"message": "密码已重置"}


@router.delete("/users/{uid}")
def delete_user(
    uid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    if current_user.id == uid:
        raise HTTPException(status_code=400, detail="不能删除自己")

    user = db.query(SysUser).filter(SysUser.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.status = "disabled"
    db.commit()

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="delete", business_type="user", business_id=uid,
                   before_value=json.dumps({"username": user.username}))
    db.add(log)
    db.commit()

    return {"message": "用户已禁用"}


# ===== Employee Management =====
class EmployeeCreate(BaseModel):
    employee_no: Optional[str] = None
    name: str
    department: Optional[str] = None
    bu: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[date] = None


class EmployeeUpdate(BaseModel):
    employee_no: Optional[str] = None
    name: Optional[str] = None
    department: Optional[str] = None
    bu: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[date] = None
    status: Optional[str] = None


@router.get("/employees")
def list_employees(
    search: str = Query(""),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    q = db.query(Employee).filter(Employee.is_deleted == False)
    if search:
        like = f"%{search}%"
        q = q.filter(Employee.name.like(like) | Employee.employee_no.like(like))
    employees = q.order_by(Employee.name).all()
    return {
        "total": len(employees),
        "items": [{
            "id": e.id,
            "employee_no": e.employee_no,
            "name": e.name,
            "department": e.department,
            "bu": e.bu,
            "position": e.position,
            "email": e.email,
            "phone": e.phone,
            "hire_date": e.hire_date,
            "status": e.status
        } for e in employees]
    }


@router.post("/employees", status_code=201)
def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    emp = Employee(**data.model_dump())
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return {"id": emp.id, "message": "员工添加成功"}


@router.put("/employees/{eid}")
def update_employee(
    eid: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    emp = db.query(Employee).filter(Employee.id == eid, Employee.is_deleted == False).first()
    if not emp:
        raise HTTPException(status_code=404, detail="员工不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(emp, k, v)
    db.commit()
    return {"message": "更新成功"}


@router.delete("/employees/{eid}")
def delete_employee(
    eid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    emp = db.query(Employee).filter(Employee.id == eid, Employee.is_deleted == False).first()
    if not emp:
        raise HTTPException(status_code=404, detail="员工不存在")
    emp.is_deleted = True
    db.commit()
    return {"message": "已删除"}


# ===== Fee Standard Management =====
class FeeStandardCreate(BaseModel):
    category: Optional[str] = "国内"
    fee_type: str
    patent_type: Optional[str] = "全部"
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    standard_amount: Optional[float] = None
    reduced_85_amount: Optional[float] = None
    reduced_70_amount: Optional[float] = None
    unit: Optional[str] = "元"
    note: Optional[str] = None


class FeeStandardUpdate(BaseModel):
    category: Optional[str] = None
    fee_type: Optional[str] = None
    patent_type: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    standard_amount: Optional[float] = None
    reduced_85_amount: Optional[float] = None
    reduced_70_amount: Optional[float] = None
    unit: Optional[str] = None
    note: Optional[str] = None


@router.get("/fee-standards")
def list_fee_standards(
    category: str = Query(""),
    fee_type: str = Query(""),
    patent_type: str = Query(""),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    q = db.query(FeeStandard)
    if category:
        q = q.filter(FeeStandard.category == category)
    if fee_type:
        q = q.filter(FeeStandard.fee_type.like(f"%{fee_type}%"))
    if patent_type:
        q = q.filter(FeeStandard.patent_type == patent_type)

    standards = q.order_by(FeeStandard.category, FeeStandard.fee_type, FeeStandard.year_start).all()
    return {
        "total": len(standards),
        "items": [{
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
    }


@router.post("/fee-standards", status_code=201)
def create_fee_standard(
    data: FeeStandardCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    # Auto-calculate reduced amounts if not provided
    d = data.model_dump()
    if d.get("standard_amount") and not d.get("reduced_85_amount"):
        d["reduced_85_amount"] = round(d["standard_amount"] * 0.15, 2)
    if d.get("standard_amount") and not d.get("reduced_70_amount"):
        d["reduced_70_amount"] = round(d["standard_amount"] * 0.30, 2)

    std = FeeStandard(**d)
    db.add(std)
    db.commit()
    db.refresh(std)
    return {"id": std.id, "message": "费用标准创建成功"}


@router.put("/fee-standards/{sid}")
def update_fee_standard(
    sid: int,
    data: FeeStandardUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    std = db.query(FeeStandard).filter(FeeStandard.id == sid).first()
    if not std:
        raise HTTPException(status_code=404, detail="费用标准不存在")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(std, k, v)
    db.commit()
    return {"message": "更新成功"}


@router.delete("/fee-standards/{sid}")
def delete_fee_standard(
    sid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    std = db.query(FeeStandard).filter(FeeStandard.id == sid).first()
    if not std:
        raise HTTPException(status_code=404, detail="费用标准不存在")
    db.delete(std)
    db.commit()
    return {"message": "已删除"}


# ===== Agency Price Comparison =====
@router.get("/agency-price-compare")
def agency_price_compare(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Compare prices across agencies using price change records."""
    from app.models import Agency, AgencyPriceChange
    agencies = db.query(Agency).filter(Agency.is_deleted == False, Agency.status == "合作中").all()

    # Collect all unique service items
    all_items = set()
    agency_data = {}

    for a in agencies:
        changes = db.query(AgencyPriceChange).filter(
            AgencyPriceChange.agency_id == a.id
        ).order_by(AgencyPriceChange.change_date.desc()).all()

        # Get latest price for each service item
        latest_prices = {}
        for c in changes:
            if c.service_item not in latest_prices:
                latest_prices[c.service_item] = c.new_price
                all_items.add(c.service_item)

        agency_data[a.agency_name] = latest_prices

    # Build comparison matrix
    service_items = sorted(all_items)
    matrix = []
    for item in service_items:
        row = {"service_item": item}
        for a in agencies:
            row[a.agency_name] = agency_data.get(a.agency_name, {}).get(item)
        matrix.append(row)

    return {
        "agencies": [a.agency_name for a in agencies],
        "service_items": service_items,
        "matrix": matrix
    }
