"""专利年费自动计算。

规则来源：国知局《专利收费、集成电路布图设计收费标准》+ 企业内部《专利年费缴纳规则》。
- 年费阶梯：专利类型 × 年份档 → 官费金额
- 费减：减免 85%（缴 15%）/ 减免 70%（缴 30%）/ 不减免（缴全额）
"""
from datetime import date

from app.models import PatentFee

# 年费阶梯规则：{专利类型: [(起始年, 结束年, 官费金额), ...]}
ANNUAL_FEE_RULES = {
    "发明": [(1, 3, 900), (4, 6, 1200), (7, 9, 2000),
             (10, 12, 4000), (13, 15, 6000), (16, 20, 8000)],
    "实用新型": [(1, 3, 600), (4, 5, 900), (6, 8, 1200), (9, 10, 2000)],
    "外观": [(1, 3, 600), (4, 5, 900), (6, 8, 1200), (9, 10, 2000), (11, 15, 3000)],
    # 软产 / 软著 无年费
}

# 滞纳金：每超 1 个月，加收当年全额年费的 5%
LATE_FEE_RATE = 0.05


def get_annual_fee_amount(patent_type: str, fee_year: int):
    """返回某专利类型某年度的官费金额（无减免）。无规则时返回 None。"""
    rules = ANNUAL_FEE_RULES.get(patent_type, [])
    for ys, ye, amt in rules:
        if ys <= fee_year <= ye:
            return float(amt)
    return None


def apply_reduction(amount: float, rate: str):
    """应用费减。rate='85%'→缴15%；'70%'→缴30%；其他→全额。"""
    if amount is None:
        return None
    if rate == "85%":
        return round(amount * 0.15, 2)
    if rate == "70%":
        return round(amount * 0.30, 2)
    return round(amount, 2)


def calc_due_date(application_date, fee_year):
    """应缴日 = 申请日期 + N 年（仅参考，用户可手动改）。"""
    if not application_date:
        return None
    try:
        y = application_date.year + fee_year
        return date(y, application_date.month, application_date.day)
    except ValueError:
        # 2/29 等边界
        try:
            return date(application_date.year + fee_year, application_date.month, 28)
        except Exception:
            return None


def audit_patent_fees(db, patent, today=None):
    """审核某专利的年费记录完整性，返回缺失/异常明细（不写库）。

    口径：按类型应有 N 年（发明 20 / 实用新型 10 / 外观 15，软产/软著无年费），
    与库内已有 patent_fee 的 fee_year 集合求差。缺失年份区分两类：
      - overdue：应缴日已过期且记录还没写（真正"漏写/漏缴"风险）
      - future：应缴日在未来的年份（正常未发生）
    另附 duplicate：同一 fee_year 多条记录（重复录入）。
    """
    from datetime import date as _date
    if today is None:
        today = _date.today()

    rules = ANNUAL_FEE_RULES.get(patent.patent_type or "")
    expected_years = [y for ys, ye, _amt in rules for y in range(ys, ye + 1)] if rules else []

    fees = db.query(PatentFee).filter(PatentFee.patent_id == patent.id).all()
    year_set = set()
    dup_years = set()
    for f in fees:
        if f.fee_year in year_set:
            dup_years.add(f.fee_year)
        year_set.add(f.fee_year)

    missing = []
    for y in expected_years:
        if y in year_set:
            continue
        due = calc_due_date(patent.application_date, y)
        amt = get_annual_fee_amount(patent.patent_type, y)
        std = apply_reduction(amt, patent.fee_reduction_rate if patent.fee_reduction else None)
        missing.append({
            "fee_year": y,
            "due_date": due.isoformat() if due else None,
            "amount": std,
            "overdue": bool(due and due < today),
        })

    return {
        "patent_type": patent.patent_type or "",
        "has_fee_rule": bool(expected_years),
        "expected_count": len(expected_years),
        "existing_count": len(fees),
        "missing": missing,
        "overdue_count": sum(1 for m in missing if m["overdue"]),
        "future_count": sum(1 for m in missing if not m["overdue"]),
        "duplicate_years": sorted(dup_years),
        "complete": not missing and not dup_years,
    }


def generate_patent_fees(db, patent, commit=True, force=False):
    """根据专利类型 + 费减比例，生成每年一条 patent_fee 记录（应缴金额自动算）。

    force=True 时先删除已有 fee 记录再重建（用于导入/更新）。
    """
    rules = ANNUAL_FEE_RULES.get(patent.patent_type, [])
    if not rules:
        return []

    if force:
        db.query(PatentFee).filter(PatentFee.patent_id == patent.id).delete()

    rate = patent.fee_reduction_rate if patent.fee_reduction else None
    created = []
    for ys, ye, amt in rules:
        for y in range(ys, ye + 1):
            std = apply_reduction(float(amt), rate)
            fee = PatentFee(
                patent_id=patent.id,
                fee_year=y,
                due_date=calc_due_date(patent.application_date, y),
                standard_amount=std,
                status="待缴",
            )
            db.add(fee)
            created.append(fee)
    if commit:
        db.commit()
    return created


def fill_missing_fees(db, patent, commit=True):
    """只补写缺失的年份（已有 fee_year 的不动，保留已缴状态/凭证）。

    与 generate_patent_fees(force=True) 的区别：不删除任何已有记录，
    仅对 audit_patent_fees 识别出的缺失年份新建"待缴"记录。
    返回新建的 PatentFee 列表。
    """
    audit = audit_patent_fees(db, patent)
    if not audit["missing"]:
        return []
    rate = patent.fee_reduction_rate if patent.fee_reduction else None
    created = []
    for m in audit["missing"]:
        y = m["fee_year"]
        std = apply_reduction(get_annual_fee_amount(patent.patent_type, y), rate)
        fee = PatentFee(
            patent_id=patent.id,
            fee_year=y,
            due_date=calc_due_date(patent.application_date, y),
            standard_amount=std,
            status="待缴",
            notes="系统补写（年费审核）",
        )
        db.add(fee)
        created.append(fee)
    if commit:
        db.commit()
    return created
