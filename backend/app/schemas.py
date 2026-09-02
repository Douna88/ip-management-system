"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, date


# ===== Auth =====
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"

class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    email: Optional[str] = None
    role: str
    model_config = {"from_attributes": True}

class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str
    email: Optional[str] = None
    role: str = "member"

class PasswordChange(BaseModel):
    old_password: str
    new_password: str


# ===== Patent =====
class PatentBase(BaseModel):
    application_no: str
    patent_name: str
    patent_type: str
    status: str
    application_date: Optional[date] = None
    authorization_no: Optional[str] = None
    authorization_date: Optional[date] = None
    first_publication_date: Optional[date] = None
    applicant: Optional[str] = "示例科技有限公司"
    inventors: Optional[str] = None
    ipc_classification: Optional[str] = None
    correspondence_project: Optional[str] = None
    correspondence_product: Optional[str] = None
    protection_element: Optional[str] = None
    quick_examination: Optional[bool] = False
    expedited_examination: Optional[bool] = False
    fee_reduction: Optional[bool] = False
    fee_reduction_rate: Optional[str] = None
    official_fee: Optional[float] = None
    agency_fee: Optional[float] = None
    pre_examination_fee: Optional[float] = None
    fee_year1: Optional[float] = None
    fee_year2: Optional[float] = None
    fee_year3: Optional[float] = None
    fee_year4: Optional[float] = None
    fee_year5: Optional[float] = None
    fee_year6: Optional[float] = None
    fee_year7: Optional[float] = None
    fee_year8: Optional[float] = None
    fee_year9: Optional[float] = None
    fee_year10: Optional[float] = None
    agency_id: Optional[int] = None
    agency_case_no: Optional[str] = None
    is_pct: Optional[bool] = False
    description: Optional[str] = None

class PatentCreate(PatentBase):
    pass

class PatentUpdate(BaseModel):
    application_no: Optional[str] = None
    patent_name: Optional[str] = None
    patent_type: Optional[str] = None
    status: Optional[str] = None
    application_date: Optional[date] = None
    authorization_no: Optional[str] = None
    authorization_date: Optional[date] = None
    first_publication_date: Optional[date] = None
    applicant: Optional[str] = None
    inventors: Optional[str] = None
    ipc_classification: Optional[str] = None
    correspondence_project: Optional[str] = None
    correspondence_product: Optional[str] = None
    protection_element: Optional[str] = None
    quick_examination: Optional[bool] = None
    expedited_examination: Optional[bool] = None
    fee_reduction: Optional[bool] = None
    fee_reduction_rate: Optional[str] = None
    official_fee: Optional[float] = None
    agency_fee: Optional[float] = None
    pre_examination_fee: Optional[float] = None
    agency_id: Optional[int] = None
    agency_case_no: Optional[str] = None
    is_pct: Optional[bool] = None
    description: Optional[str] = None

class PatentOut(PatentBase):
    id: int
    agency_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ===== Patent Fee =====
class PatentFeeBase(BaseModel):
    fee_year: int
    due_date: Optional[date] = None
    actual_pay_date: Optional[date] = None
    standard_amount: Optional[float] = None
    reduced_amount: Optional[float] = None
    actual_pay_amount: Optional[float] = None
    agency_id: Optional[int] = None
    receipt_no: Optional[str] = None
    receipt_file_id: Optional[int] = None
    status: Optional[str] = "待缴"
    late_fee: Optional[float] = None
    payment_source: Optional[str] = None

class PatentFeeCreate(PatentFeeBase):
    patent_id: int

class PatentFeeUpdate(BaseModel):
    fee_year: Optional[int] = None
    due_date: Optional[date] = None
    actual_pay_date: Optional[date] = None
    standard_amount: Optional[float] = None
    reduced_amount: Optional[float] = None
    actual_pay_amount: Optional[float] = None
    status: Optional[str] = None
    late_fee: Optional[float] = None
    receipt_no: Optional[str] = None
    receipt_file_id: Optional[int] = None
    payment_source: Optional[str] = None

class PatentFeeOut(PatentFeeBase):
    id: int
    patent_id: int
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ===== Trademark =====
class TrademarkBase(BaseModel):
    trademark_no: Optional[str] = None
    trademark_name: str
    trademark_type: Optional[str] = None
    logo_file_id: Optional[int] = None
    application_date: Optional[date] = None
    registration_date: Optional[date] = None
    valid_until: date
    nice_class: Optional[str] = None
    scope_group: Optional[str] = None
    applicant: Optional[str] = "示例科技有限公司"
    agency_id: Optional[int] = None
    status: str
    partial_grant_class: Optional[str] = None
    renewal_count: Optional[int] = 0
    last_renewal_date: Optional[date] = None
    renewal_deadline: Optional[date] = None
    grace_period_deadline: Optional[date] = None
    contact_person: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None

class TrademarkCreate(TrademarkBase):
    pass

class TrademarkUpdate(BaseModel):
    trademark_no: Optional[str] = None
    trademark_name: Optional[str] = None
    trademark_type: Optional[str] = None
    logo_file_id: Optional[int] = None
    application_date: Optional[date] = None
    registration_date: Optional[date] = None
    valid_until: Optional[date] = None
    nice_class: Optional[str] = None
    scope_group: Optional[str] = None
    applicant: Optional[str] = None
    agency_id: Optional[int] = None
    status: Optional[str] = None
    partial_grant_class: Optional[str] = None
    renewal_count: Optional[int] = None
    last_renewal_date: Optional[date] = None
    renewal_deadline: Optional[date] = None
    grace_period_deadline: Optional[date] = None
    contact_person: Optional[str] = None
    notes: Optional[str] = None

class TrademarkOut(TrademarkBase):
    id: int
    agency_name: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ===== Agency =====
class AgencyBase(BaseModel):
    agency_name: str
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    business_scope: Optional[str] = None
    cooperation_start: Optional[date] = None
    cooperation_end: Optional[date] = None
    status: Optional[str] = "合作中"
    notes: Optional[str] = None

class AgencyCreate(AgencyBase):
    pass

class AgencyUpdate(BaseModel):
    agency_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    business_scope: Optional[str] = None
    cooperation_start: Optional[date] = None
    cooperation_end: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class AgencyOut(AgencyBase):
    id: int
    patent_count: Optional[int] = 0
    trademark_count: Optional[int] = 0
    total_amount: Optional[float] = 0
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ===== Agency Price Change =====
class PriceChangeBase(BaseModel):
    change_date: date
    service_item: str
    old_price: Optional[float] = None
    new_price: Optional[float] = None
    change_reason: Optional[str] = None
    effective_date: Optional[date] = None

class PriceChangeCreate(PriceChangeBase):
    agency_id: int

class PriceChangeOut(PriceChangeBase):
    id: int
    agency_id: int
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ===== File =====
class FileOut(BaseModel):
    id: int
    original_name: str
    file_type: str
    file_size: int
    business_type: Optional[str] = None
    business_id: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ===== Dashboard =====
class DashboardStats(BaseModel):
    patent_total: int = 0
    patent_active: int = 0
    trademark_total: int = 0
    trademark_active: int = 0
    fee_pending_count: int = 0
    fee_pending_amount: float = 0
    tm_renewal_count: int = 0
    patent_type_dist: dict = {}
    patent_status_dist: dict = {}


# ===== Bonus =====
class BonusRuleOut(BaseModel):
    id: int
    rule_name: str
    effective_from: Optional[date] = None
    effective_until: Optional[date] = None
    is_current: bool = True
    rules_json: Optional[str] = None
    raw_text: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class BonusBatchCreate(BaseModel):
    batch_name: str
    rule_id: int
    period_start: date
    period_end: date

class BonusBatchStatusUpdate(BaseModel):
    status: str  # 草稿/审批中/已批准/已发放

class BonusItemApprove(BaseModel):
    approve_status: str  # 通过/驳回
    approve_comment: Optional[str] = None
    step: str  # ip_engineer/rd_director/md

class BonusItemPaymentUpdate(BaseModel):
    payment_status: str  # 待发/已发
    payment_date: Optional[date] = None


class BonusItemCreate(BaseModel):
    patent_id: Optional[int] = None
    patent_name: str
    patent_type: str = "发明"
    application_no: Optional[str] = None
    department: Optional[str] = None
    milestone: Optional[str] = None
    approved_amount: float = 0
    received_amount: float = 0
    applied_amount: float = 0
    inventor_str: Optional[str] = None
    bonus_status: str = "待发"


class BonusItemUpdate(BaseModel):
    patent_name: Optional[str] = None
    patent_type: Optional[str] = None
    department: Optional[str] = None
    milestone: Optional[str] = None
    approved_amount: Optional[float] = None
    received_amount: Optional[float] = None
    applied_amount: Optional[float] = None
    inventor_str: Optional[str] = None
    bonus_status: Optional[str] = None


# ===== Fee Standard =====
class FeeStandardOut(BaseModel):
    id: int
    category: Optional[str] = None
    fee_type: str
    patent_type: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    standard_amount: Optional[float] = None
    reduced_85_amount: Optional[float] = None
    reduced_70_amount: Optional[float] = None
    unit: Optional[str] = "元"
    note: Optional[str] = None
    model_config = {"from_attributes": True}


# ===== Generic =====
class PaginatedResponse(BaseModel):
    total: int
    items: List[Any]
    page: int = 1
    page_size: int = 20

class MessageResponse(BaseModel):
    message: str
    id: Optional[int] = None

# Update forward refs
TokenResponse.model_rebuild()
