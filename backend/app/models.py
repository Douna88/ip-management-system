"""SQLAlchemy models for all 19 tables (v3 design)."""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date,
    Float, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from app.database import Base


# ===== 1. sys_user =====
class SysUser(Base):
    __tablename__ = "sys_user"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(50), nullable=False)
    email = Column(String(100))
    role = Column(String(20), nullable=False, default="admin")  # admin/member/viewer
    status = Column(String(10), nullable=False, default="active")  # active/disabled
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(DateTime)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)


# ===== 2. employee =====
class Employee(Base):
    __tablename__ = "employee"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_no = Column(String(20), index=True)
    name = Column(String(50), nullable=False, index=True)
    department = Column(String(100))
    bu = Column(String(50))
    position = Column(String(50))
    email = Column(String(100))
    phone = Column(String(20))
    hire_date = Column(Date)
    status = Column(String(10), default="active")  # active/resigned
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)


# ===== 3. file_storage =====
class FileStorage(Base):
    __tablename__ = "file_storage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    original_name = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf/word/excel/image/other
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100))
    business_type = Column(String(50))  # patent/trademark/agency/bonus/standard
    business_id = Column(Integer)
    uploaded_by = Column(Integer, ForeignKey("sys_user.id"))
    uploaded_at = Column(DateTime, default=datetime.now)
    is_encrypted = Column(Boolean, default=False)
    checksum = Column(String(64))


# ===== 4. audit_log (append-only) =====
class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    user_name = Column(String(50))
    action = Column(String(20), nullable=False)  # create/update/delete/login/export
    business_type = Column(String(50))
    business_id = Column(Integer)
    before_value = Column(Text)  # JSON
    after_value = Column(Text)  # JSON
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    intent = Column(String(200))  # AI reserved
    created_at = Column(DateTime, default=datetime.now)


# ===== 5. reminder =====
class Reminder(Base):
    __tablename__ = "reminder"
    id = Column(Integer, primary_key=True, autoincrement=True)
    business_type = Column(String(50))  # patent_fee / trademark_renewal / bonus_approval
    business_id = Column(Integer)
    remind_type = Column(String(20))  # expiring/overdue/approval
    title = Column(String(200))
    content = Column(Text)
    remind_at = Column(DateTime)
    status = Column(String(20), default="pending")  # pending/sent/read/ignored
    channel = Column(String(20), default="in_app")  # email/in_app
    user_id = Column(Integer)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)


# ===== 6. patent =====
class Patent(Base):
    __tablename__ = "patent"
    id = Column(Integer, primary_key=True, autoincrement=True)
    application_no = Column(String(20), nullable=False, index=True)
    patent_name = Column(String(200), nullable=False, index=True)
    patent_type = Column(String(20), nullable=False)  # 发明/实用新型/外观/软产/软著
    status = Column(String(20), nullable=False, index=True)  # 受理/实质审查/授权/驳回/复审/放弃/已登记
    application_date = Column(Date, index=True)
    authorization_no = Column(String(50))  # 授权号
    authorization_date = Column(Date)
    first_publication_date = Column(Date)
    applicant = Column(String(200), default="示例科技有限公司")
    inventors = Column(Text)  # comma-separated names
    ipc_classification = Column(String(100))
    correspondence_project = Column(String(200))
    correspondence_product = Column(String(200))
    protection_element = Column(Text)
    quick_examination = Column(Boolean, default=False)
    expedited_examination = Column(Boolean, default=False)
    fee_reduction = Column(Boolean, default=False)
    fee_reduction_rate = Column(String(10))  # 85%/70%/none
    official_fee = Column(Float)
    agency_fee = Column(Float)
    pre_examination_fee = Column(Float)
    # Year fees stored in patent_fee table, but also keep summary fields for import
    fee_year1 = Column(Float)
    fee_year2 = Column(Float)
    fee_year3 = Column(Float)
    fee_year4 = Column(Float)
    fee_year5 = Column(Float)
    fee_year6 = Column(Float)
    fee_year7 = Column(Float)
    fee_year8 = Column(Float)
    fee_year9 = Column(Float)
    fee_year10 = Column(Float)
    agency_id = Column(Integer, ForeignKey("agency.id"))
    agency_case_no = Column(String(50))
    is_pct = Column(Boolean, default=False)
    description = Column(Text)  # AI reserved
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer)

    # Relationships
    fees = relationship("PatentFee", back_populates="patent", cascade="all, delete-orphan")
    inventors_rel = relationship("PatentInventor", back_populates="patent", cascade="all, delete-orphan")
    agency = relationship("Agency", back_populates="patents")


# ===== 7. patent_inventor =====
class PatentInventor(Base):
    __tablename__ = "patent_inventor"
    id = Column(Integer, primary_key=True, autoincrement=True)
    patent_id = Column(Integer, ForeignKey("patent.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employee.id"))
    external_name = Column(String(50))
    order_no = Column(Integer, default=1)
    contribution_ratio = Column(Float, default=0)  # 0-100

    patent = relationship("Patent", back_populates="inventors_rel")
    employee = relationship("Employee")


# ===== 8. patent_fee =====
class PatentFee(Base):
    __tablename__ = "patent_fee"
    id = Column(Integer, primary_key=True, autoincrement=True)
    patent_id = Column(Integer, ForeignKey("patent.id"), nullable=False, index=True)
    fee_year = Column(Integer, nullable=False)  # 1-20
    due_date = Column(Date, index=True)
    actual_pay_date = Column(Date)
    standard_amount = Column(Float)
    reduced_amount = Column(Float)
    actual_pay_amount = Column(Float)
    agency_id = Column(Integer, ForeignKey("agency.id"))
    receipt_no = Column(String(50))
    receipt_file_id = Column(Integer, ForeignKey("file_storage.id"))
    status = Column(String(20), default="待缴")  # 待缴/已缴/逾期/滞纳金
    late_fee = Column(Float)
    payment_source = Column(String(20))  # 官费/代理代缴
    imported_from = Column(String(200))
    notes = Column(Text)  # 备注
    created_at = Column(DateTime, default=datetime.now)

    patent = relationship("Patent", back_populates="fees")


# ===== 9. patent_document (uses file_storage, this is a view/link table) =====
# Documents are managed via file_storage with business_type='patent' and business_id=patent.id
# No separate table needed - file_storage handles this.


# ===== 10. trademark =====
class Trademark(Base):
    __tablename__ = "trademark"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trademark_no = Column(String(20), index=True)
    trademark_name = Column(String(200), nullable=False, index=True)
    trademark_type = Column(String(20))  # 文字/图形/文字+图形
    logo_file_id = Column(Integer, ForeignKey("file_storage.id"))
    application_date = Column(Date, index=True)
    registration_date = Column(Date)
    valid_until = Column(Date, nullable=False, index=True)
    nice_class = Column(Text)  # comma-separated class numbers
    scope_group = Column(String(20), index=True)  # 业务线分组，如 精密机械/光学传感/电子控制/其他
    applicant = Column(String(200), default="示例科技有限公司")
    agency_id = Column(Integer, ForeignKey("agency.id"))
    status = Column(String(20), nullable=False, index=True)  # 申请中/已注册/驳回/已续展/已失效/部分授权
    partial_grant_class = Column(Text)  # comma-separated
    renewal_count = Column(Integer, default=0)
    last_renewal_date = Column(Date)
    renewal_deadline = Column(Date)
    grace_period_deadline = Column(Date)
    contact_person = Column(String(50))
    notes = Column(Text)
    description = Column(Text)  # AI reserved
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer)

    agency = relationship("Agency", back_populates="trademarks")
    logo_file = relationship("FileStorage", foreign_keys=[logo_file_id])


# ===== 11. trademark_document =====
# Same as patent_document - handled via file_storage with business_type='trademark'


# ===== 12. agency =====
class Agency(Base):
    __tablename__ = "agency"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_name = Column(String(100), nullable=False, index=True)
    contact_person = Column(String(50))
    contact_phone = Column(String(20))
    email = Column(String(100))
    address = Column(String(200))
    business_scope = Column(Text)  # comma-separated: 专利/商标/PCT
    cooperation_start = Column(Date)
    cooperation_end = Column(Date)
    status = Column(String(20), default="合作中")  # 合作中/暂停/已终止
    notes = Column(Text)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    patents = relationship("Patent", back_populates="agency")
    trademarks = relationship("Trademark", back_populates="agency")
    price_changes = relationship("AgencyPriceChange", back_populates="agency", cascade="all, delete-orphan")


# ===== 13. agency_price_change =====
class AgencyPriceChange(Base):
    __tablename__ = "agency_price_change"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_id = Column(Integer, ForeignKey("agency.id"), nullable=False, index=True)
    change_date = Column(Date, nullable=False)
    service_item = Column(String(100), nullable=False)
    old_price = Column(Float)
    new_price = Column(Float)
    change_reason = Column(Text)
    effective_date = Column(Date)
    new_price_list_file = Column(Integer, ForeignKey("file_storage.id"))
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    agency = relationship("Agency", back_populates="price_changes")


# ===== 14. fee_standard =====
class FeeStandard(Base):
    __tablename__ = "fee_standard"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50))  # 国内/PCT国际/外观设计国际/集成电路
    fee_type = Column(String(100), nullable=False)  # 申请费/实质审查费/年费 etc
    patent_type = Column(String(20))  # 发明/实用新型/外观/全部
    year_start = Column(Integer)
    year_end = Column(Integer)
    standard_amount = Column(Float)
    reduced_85_amount = Column(Float)
    reduced_70_amount = Column(Float)
    unit = Column(String(20), default="元")
    note = Column(Text)
    effective_from = Column(Date)
    source = Column(String(200))
    uploaded_file = Column(Integer, ForeignKey("file_storage.id"))
    created_at = Column(DateTime, default=datetime.now)


# ===== 15. bonus_rule =====
class BonusRule(Base):
    __tablename__ = "bonus_rule"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(100), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_until = Column(Date)
    is_current = Column(Boolean, default=True)
    rules_json = Column(Text)  # JSON: milestone amounts by patent type
    raw_text = Column(Text)  # AI reserved: rule document text
    created_at = Column(DateTime, default=datetime.now)

    batches = relationship("PatentBonusBatch", back_populates="rule")


# ===== 16. patent_bonus_batch =====
class PatentBonusBatch(Base):
    __tablename__ = "patent_bonus_batch"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_code = Column(String(20), nullable=False, unique=True, index=True)
    batch_name = Column(String(100))
    rule_id = Column(Integer, ForeignKey("bonus_rule.id"))
    period_start = Column(Date)
    period_end = Column(Date)
    total_amount = Column(Float, default=0)
    status = Column(String(20), default="草稿")  # 草稿/审批中/已批准/已发放
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    rule = relationship("BonusRule", back_populates="batches")
    items = relationship("PatentBonusItem", back_populates="batch", cascade="all, delete-orphan")


# ===== 17. patent_bonus_item =====
class PatentBonusItem(Base):
    __tablename__ = "patent_bonus_item"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("patent_bonus_batch.id"), nullable=False, index=True)
    patent_id = Column(Integer, ForeignKey("patent.id"))
    patent_type = Column(String(20))  # snapshot
    patent_name = Column(String(200))  # snapshot for display
    milestone = Column(String(20))  # 受理/授权/PCT叠加
    department = Column(String(100))  # 研发部门
    approved_amount = Column(Float, default=0)  # 应发奖金（核定总额）
    received_amount = Column(Float, default=0)  # 已发奖金（累计）
    applied_amount = Column(Float, default=0)  # 本次申请发放
    rule_id = Column(Integer, ForeignKey("bonus_rule.id"))
    base_amount = Column(Float, default=0)
    pct_bonus = Column(Float, default=0)
    total_amount = Column(Float, default=0)
    payment_status = Column(String(20), default="待发")  # 待发/已发
    payment_date = Column(Date)
    source = Column(String(20), default="系统计算")  # 系统计算/Excel导入
    ai_explanation = Column(Text)  # AI reserved
    created_at = Column(DateTime, default=datetime.now)

    batch = relationship("PatentBonusBatch", back_populates="items")
    details = relationship("PatentBonusDetail", back_populates="item", cascade="all, delete-orphan")
    approvals = relationship("PatentBonusApproval", back_populates="item", cascade="all, delete-orphan")


# ===== 18. patent_bonus_detail =====
class PatentBonusDetail(Base):
    __tablename__ = "patent_bonus_detail"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bonus_item_id = Column(Integer, ForeignKey("patent_bonus_item.id"), nullable=False, index=True)
    inventor_id = Column(Integer, ForeignKey("employee.id"))
    external_name = Column(String(50))
    contribution_ratio = Column(Float, default=0)  # 0-100
    amount = Column(Float, default=0)
    milestone_amount = Column(Text)  # JSON: {"受理": 1000, "授权": 2000}
    payment_status = Column(String(20), default="待发")
    created_at = Column(DateTime, default=datetime.now)

    item = relationship("PatentBonusItem", back_populates="details")
    inventor = relationship("Employee")


# ===== 19. patent_bonus_approval =====
class PatentBonusApproval(Base):
    __tablename__ = "patent_bonus_approval"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bonus_item_id = Column(Integer, ForeignKey("patent_bonus_item.id"), nullable=False, index=True)
    step = Column(String(20), nullable=False)  # ip_engineer/rd_director/md
    approver_id = Column(Integer, ForeignKey("sys_user.id"))
    approve_status = Column(String(20), default="待审")  # 待审/通过/驳回
    approve_comment = Column(Text)
    approve_time = Column(DateTime)
    next_approver_id = Column(Integer)

    item = relationship("PatentBonusItem", back_populates="approvals")
    approver = relationship("SysUser")


# ===== 20. trademark_scope (注册范围库) =====
class TrademarkScope(Base):
    __tablename__ = "trademark_scope"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scope_group = Column(String(50), nullable=False, index=True)  # 业务线分组，如 精密机械/光学传感/电子控制
    nice_class = Column(Integer, nullable=False)  # 尼斯分类 1-45
    subclass_code = Column(String(10))  # 细分小类代码，如 0705
    subclass_name = Column(Text)  # 小类名称
    class_name = Column(String(100), nullable=False)  # 类别名称（与大类对应）
    specific_products = Column(Text)  # 具体产品（服务）
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
