"""Reports router: multi-dimensional statistics for reports page."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, or_
from app.database import get_db
from app.models import (
    Patent, Trademark, PatentFee, Agency, SysUser,
    PatentBonusBatch, PatentBonusItem, PatentBonusDetail,
    PatentInventor, Employee, AuditLog
)
from app.security import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/overview")
def report_overview(
    year: int = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Overview statistics for reports page."""
    if not year:
        year = date.today().year

    # Patent stats
    patent_total = db.query(Patent).filter(Patent.is_deleted == False).count()
    patent_by_type = {}
    for t in ["发明", "实用新型", "外观", "软产", "软著"]:
        patent_by_type[t] = db.query(Patent).filter(
            Patent.patent_type == t, Patent.is_deleted == False
        ).count()

    patent_by_status = {}
    for s in ["申请中", "受理", "实质审查", "授权", "驳回", "维持中", "失效"]:
        patent_by_status[s] = db.query(Patent).filter(
            Patent.status == s, Patent.is_deleted == False
        ).count()

    # This year new patents
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    new_patents = db.query(Patent).filter(
        Patent.is_deleted == False,
        Patent.application_date >= year_start,
        Patent.application_date <= year_end
    ).count()

    # Trademark stats
    tm_total = db.query(Trademark).filter(Trademark.is_deleted == False).count()
    tm_by_status = {}
    for s in ["申请中", "已注册", "驳回", "已续展", "已失效", "部分授权"]:
        tm_by_status[s] = db.query(Trademark).filter(
            Trademark.status == s, Trademark.is_deleted == False
        ).count()

    tm_by_scope = {}
    for s in ["运动台", "光学传感", "电子", "其他"]:
        tm_by_scope[s] = db.query(Trademark).filter(
            Trademark.scope_group == s, Trademark.is_deleted == False
        ).count()

    new_trademarks = db.query(Trademark).filter(
        Trademark.is_deleted == False,
        Trademark.application_date >= year_start,
        Trademark.application_date <= year_end
    ).count()

    # Fee stats
    fee_total = db.query(func.sum(PatentFee.actual_pay_amount)).scalar() or 0
    fee_this_year = db.query(func.sum(PatentFee.actual_pay_amount)).filter(
        PatentFee.actual_pay_date >= year_start,
        PatentFee.actual_pay_date <= year_end
    ).scalar() or 0
    fee_pending = db.query(PatentFee).filter(PatentFee.status == "待缴").count()
    fee_pending_amount = db.query(func.sum(PatentFee.standard_amount)).filter(
        PatentFee.status == "待缴"
    ).scalar() or 0

    # Monthly fee trend
    monthly_fees = []
    for m in range(1, 13):
        m_start = date(year, m, 1)
        m_end = date(year, m, 28) if m == 2 else date(year, m, 30 if m in [4, 6, 9, 11] else 31)
        amount = db.query(func.sum(PatentFee.actual_pay_amount)).filter(
            PatentFee.actual_pay_date >= m_start,
            PatentFee.actual_pay_date <= m_end
        ).scalar() or 0
        monthly_fees.append({"month": m, "amount": float(amount)})

    # Agency stats
    agencies = db.query(Agency).filter(Agency.is_deleted == False).all()
    agency_stats = []
    for a in agencies:
        p_count = db.query(Patent).filter(Patent.agency_id == a.id, Patent.is_deleted == False).count()
        t_count = db.query(Trademark).filter(Trademark.agency_id == a.id, Trademark.is_deleted == False).count()
        total_amt = db.query(func.sum(PatentFee.actual_pay_amount)).filter(
            PatentFee.agency_id == a.id
        ).scalar() or 0
        agency_stats.append({
            "name": a.agency_name,
            "patent_count": p_count,
            "trademark_count": t_count,
            "total_amount": float(total_amt)
        })

    # Patent application trend (last 5 years)
    patent_trend = []
    for y in range(year - 4, year + 1):
        count = db.query(Patent).filter(
            Patent.is_deleted == False,
            Patent.application_date >= date(y, 1, 1),
            Patent.application_date <= date(y, 12, 31)
        ).count()
        patent_trend.append({"year": y, "count": count})

    return {
        "year": year,
        "patent": {
            "total": patent_total,
            "by_type": patent_by_type,
            "by_status": patent_by_status,
            "new_this_year": new_patents,
            "trend_5yr": patent_trend
        },
        "trademark": {
            "total": tm_total,
            "by_status": tm_by_status,
            "by_scope": tm_by_scope,
            "new_this_year": new_trademarks
        },
        "fee": {
            "total_paid": float(fee_total),
            "this_year_paid": float(fee_this_year),
            "pending_count": fee_pending,
            "pending_amount": float(fee_pending_amount),
            "monthly_trend": monthly_fees
        },
        "agency": agency_stats
    }


# 专利奖金类型归一映射（Excel 导入数据存在混值：发明/发明专利/软著/Soft copyright &Software product 等）
PATENT_TYPE_NORMALIZE = [
    (("发明", "发明专利", "发明专利（发明）"), "发明"),
    (("实用新型",), "实用新型"),
    (("外观", "外观设计", "外观设计专利"), "外观"),
    (("软著", "软件著作权", "Soft copyright &Software product",
      "software copyright", "software product", "软产"), "软著"),
]


def _normalize_patent_bonus_type(raw):
    """将专利奖金条目的 patent_type 快照值归一为 发明/实用新型/外观/软著/其他。"""
    if not raw:
        return "其他"
    s = str(raw).strip()
    low = s.lower()
    for keys, label in PATENT_TYPE_NORMALIZE:
        for k in keys:
            if k.lower() in low:
                return label
    return s


@router.get("/bonus-stats")
def bonus_stats(
    year: int = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Bonus statistics for visualization page.

    year 非空：按「批次所属年份」（period_start 的年份）过滤各项聚合；
    year 为空 / 0 / 'all'：累计口径，不过滤。
    """
    year = year or 0
    cumulative = not year

    # 批次归属年份：period_start 年份；无 period_start 时回落 created_at 年份
    period_year = extract("year", PatentBonusBatch.period_start)
    created_year = extract("year", PatentBonusBatch.created_at)
    batch_year_expr = func.coalesce(period_year, created_year)

    if not cumulative:
        batch_filters = [batch_year_expr == year]
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
    else:
        batch_filters = []
        year_start = None
        year_end = None

    batch_q = db.query(PatentBonusBatch)
    if batch_filters:
        batch_q = batch_q.filter(*batch_filters)
    batches = batch_q.all()
    year_amount = sum(b.total_amount or 0 for b in batches)

    # 全量累计总额（不受年份筛选影响，供「累计奖金总额」指标卡使用）
    grand_total = sum(b.total_amount or 0 for b in db.query(PatentBonusBatch).all())

    # 明细聚合公共过滤（含批次归属年份）
    def items_filter(*conds):
        q = db.query(func.sum(PatentBonusItem.total_amount)).join(PatentBonusBatch)
        q = q.filter(*batch_filters, *conds)
        return q

    # 本年/累计金额（明细口径）
    this_year_amount = items_filter().scalar() or 0

    # 按专利类型（归一后）
    type_stats = db.query(
        PatentBonusItem.patent_type, func.sum(PatentBonusItem.total_amount)
    ).join(PatentBonusBatch).filter(*batch_filters).group_by(
        PatentBonusItem.patent_type
    ).all()
    by_type = {}
    for raw, amt in type_stats:
        label = _normalize_patent_bonus_type(raw)
        by_type[label] = by_type.get(label, 0.0) + float(amt or 0)
    by_type = {k: v for k, v in sorted(by_type.items(), key=lambda x: -x[1])}

    # 发明人（含姓名解析），按批次年份过滤
    inv_q = (
        db.query(
            PatentBonusDetail.external_name,
            Employee.name,
            func.sum(PatentBonusDetail.amount),
        )
        .outerjoin(Employee, PatentBonusDetail.inventor_id == Employee.id)
        .join(PatentBonusItem, PatentBonusDetail.bonus_item_id == PatentBonusItem.id)
        .join(PatentBonusBatch, PatentBonusItem.batch_id == PatentBonusBatch.id)
        .group_by(PatentBonusDetail.external_name, Employee.name)
    )
    if batch_filters:
        inv_q = inv_q.filter(*batch_filters)
    inventor_stats = inv_q.all()

    inventor_list = []
    for ext_name, emp_name, amt in inventor_stats:
        name = emp_name or ext_name or "未知"
        inventor_list.append({"name": name, "amount": float(amt or 0)})
    inventor_list.sort(key=lambda x: x["amount"], reverse=True)
    top10_inventors = inventor_list[:10]

    # 月度发放趋势：基于 payment_date（有值的条目），始终按所选年份的 1-12 月
    trend_year = year if not cumulative else None
    if trend_year:
        monthly_bonus = []
        for m in range(1, 13):
            m_start = date(trend_year, m, 1)
            m_end = date(trend_year, m, 28) if m == 2 else date(trend_year, m, 30 if m in [4, 6, 9, 11] else 31)
            amount = db.query(func.sum(PatentBonusItem.total_amount)).filter(
                PatentBonusItem.payment_date >= m_start,
                PatentBonusItem.payment_date <= m_end
            ).scalar() or 0
            monthly_bonus.append({"month": m, "amount": float(amount)})
    else:
        # 累计口径：按自然月（YYYY-MM）归并
        monthly_stats = db.query(
            func.strftime("%Y-%m", PatentBonusItem.payment_date),
            func.sum(PatentBonusItem.total_amount),
        ).filter(PatentBonusItem.payment_date != None).group_by(
            func.strftime("%Y-%m", PatentBonusItem.payment_date)
        ).all()
        mmap = {ym: float(a or 0) for ym, a in monthly_stats}
        all_months = sorted(mmap.keys())
        monthly_bonus = [
            {"month": int(ym.split("-")[1]), "amount": mmap[ym],
             "label": f"{ym.split('-')[0]}年{int(ym.split('-')[1])}月"}
            for ym in all_months
        ]

    # 按里程碑
    milestone_stats = db.query(
        PatentBonusItem.milestone, func.sum(PatentBonusItem.total_amount)
    ).join(PatentBonusBatch).filter(*batch_filters).group_by(
        PatentBonusItem.milestone
    ).all()
    by_milestone = {m: float(a or 0) for m, a in milestone_stats if m}

    # 按来源（新规则 vs 旧规则）
    source_stats = db.query(
        PatentBonusItem.source, func.sum(PatentBonusItem.total_amount)
    ).join(PatentBonusBatch).filter(*batch_filters).group_by(
        PatentBonusItem.source
    ).all()
    by_source = {s or "未知": float(a or 0) for s, a in source_stats}

    # 按批次状态
    batch_status_q = db.query(
        PatentBonusBatch.status,
        func.count(PatentBonusBatch.id),
        func.sum(PatentBonusBatch.total_amount),
    ).group_by(PatentBonusBatch.status)
    if batch_filters:
        batch_status_q = batch_status_q.filter(*batch_filters)
    status_stats = batch_status_q.all()
    by_batch_status = {s: {"count": c, "amount": float(a or 0)} for s, c, a in status_stats}

    # 按部门
    dept_stats_raw = db.query(
        PatentBonusItem.department,
        func.sum(PatentBonusItem.total_amount),
        func.sum(PatentBonusItem.approved_amount),
        func.sum(PatentBonusItem.received_amount),
        func.sum(PatentBonusItem.applied_amount),
    ).join(PatentBonusBatch).filter(*batch_filters).group_by(
        PatentBonusItem.department
    ).all()

    by_department = {}
    dept_detail = {}
    for dept, total, approved, received, applied in dept_stats_raw:
        dept_name = dept or "未分类"
        by_department[dept_name] = float(total or 0)
        dept_detail[dept_name] = {
            "total": float(total or 0),
            "approved": float(approved or 0),
            "received": float(received or 0),
            "applied": float(applied or 0)
        }

    # 按年份（全年份趋势，始终全量，供趋势图使用）
    yearly_stats = db.query(
        func.extract('year', PatentBonusBatch.period_start),
        func.sum(PatentBonusItem.total_amount),
        func.sum(PatentBonusItem.approved_amount),
        func.sum(PatentBonusItem.received_amount),
        func.sum(PatentBonusItem.applied_amount)
    ).join(PatentBonusItem).group_by(
        func.extract('year', PatentBonusBatch.period_start)
    ).order_by(
        func.extract('year', PatentBonusBatch.period_start)
    ).all()

    by_year = []
    for y, total, approved, received, applied in yearly_stats:
        if y:
            by_year.append({
                "year": int(y),
                "total": float(total or 0),
                "approved": float(approved or 0),
                "received": float(received or 0),
                "applied": float(applied or 0)
            })

    # 汇总（跟随当前筛选口径）
    total_approved = sum(d["approved"] for d in dept_detail.values())
    total_received = sum(d["received"] for d in dept_detail.values())
    total_applied = sum(d["applied"] for d in dept_detail.values())

    return {
        "year": year,
        "cumulative": cumulative,
        "key_metrics": {
            "total_amount": float(grand_total),
            "year_amount": float(year_amount),
            "this_year_amount": float(this_year_amount),
            "batch_count": len(batches),
            "inventor_count": len(inventor_list),
            "total_approved": float(total_approved),
            "total_received": float(total_received),
            "total_applied": float(total_applied)
        },
        "by_type": by_type,
        "top10_inventors": top10_inventors,
        "monthly_trend": monthly_bonus,
        "by_milestone": by_milestone,
        "by_source": by_source,
        "by_batch_status": by_batch_status,
        "by_department": by_department,
        "dept_detail": dept_detail,
        "by_year": by_year,
        "all_inventors": inventor_list
    }


def _blank(col):
    """字段为 NULL 或空串。"""
    return or_(col == None, func.trim(func.coalesce(col, "")) == "")


AUTHORIZED_STATUS = ["授权", "已登记", "维持中"]


@router.get("/data-quality")
def data_quality(
    sample: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """数据质量体检：扫描全库关键字段缺失与逻辑异常，返回可跳转修复的问题清单。"""
    today = date.today()
    checks = []

    def add(code, category, title, severity, hint, route, query, label_fn, fix_field=""):
        """执行一个检查项。query 需返回 ORM 对象列表。"""
        rows = query.all()
        checks.append({
            "code": code,
            "category": category,
            "title": title,
            "severity": severity,          # high / medium / low
            "hint": hint,
            "route": route,                # 前端跳转路由前缀，空则不可跳
            "fix_field": fix_field,
            "count": len(rows),
            "samples": [label_fn(r) for r in rows[:sample]]
        })

    P = db.query(Patent).filter(Patent.is_deleted == False)
    T = db.query(Trademark).filter(Trademark.is_deleted == False)

    def p_label(p):
        return {"id": p.id, "title": p.patent_name or "(未命名)",
                "sub": p.application_no or "无申请号", "route": f"/patent/{p.id}"}

    def t_label(t):
        return {"id": t.id, "title": t.trademark_name or "(未命名)",
                "sub": t.trademark_no or "无注册号", "route": f"/trademark/{t.id}"}

    # ---------- 专利 ----------
    add("P_NO_APPNO", "专利", "缺少申请号", "high",
        "申请号是专利唯一标识，缺失将导致年费匹配、官方查询无法进行。",
        "/patent", P.filter(_blank(Patent.application_no)), p_label, "application_no")

    add("P_NO_APPDATE", "专利", "缺少申请日", "high",
        "申请日决定年费起算年度，缺失会导致年费计划无法生成。",
        "/patent", P.filter(Patent.application_date == None), p_label, "application_date")

    # 无发明人：inventors 文本为空 且 无明细行
    inv_ids = db.query(PatentInventor.patent_id).distinct().subquery()
    add("P_NO_INVENTOR", "专利", "缺少发明人", "high",
        "发明人缺失会导致奖金无法计算与分摊。",
        "/patent", P.filter(_blank(Patent.inventors), ~Patent.id.in_(db.query(inv_ids.c.patent_id))),
        p_label, "inventors")

    add("P_NO_AGENCY", "专利", "未关联代理机构", "medium",
        "未关联代理机构时，费用归集与代理绩效统计会漏算。",
        "/patent", P.filter(Patent.agency_id == None), p_label, "agency_id")

    add("P_AUTH_NO_NUMBER", "专利", "已授权但缺授权号或授权日", "high",
        "授权信息缺失将影响授权奖金触发与年费缴纳节点判定。",
        "/patent",
        P.filter(Patent.status.in_(AUTHORIZED_STATUS),
                 or_(_blank(Patent.authorization_no), Patent.authorization_date == None)),
        p_label, "authorization_no")

    # 已授权但没有任何年费记录
    fee_pids = db.query(PatentFee.patent_id).distinct().subquery()
    add("P_AUTH_NO_FEE", "专利", "已授权但未生成年费计划", "high",
        "缺少年费计划会造成漏缴风险，建议在专利详情页点击「生成年费计划」。",
        "/patent",
        P.filter(Patent.status.in_(AUTHORIZED_STATUS),
                 ~Patent.id.in_(db.query(fee_pids.c.patent_id))),
        p_label)

    add("P_NO_TYPE", "专利", "缺少专利类型", "medium",
        "专利类型决定奖金标准与年费标准，缺失会导致金额计算错误。",
        "/patent", P.filter(_blank(Patent.patent_type)), p_label, "patent_type")

    # 贡献比合计异常（有明细但合计不在 99~101）
    ratio_rows = db.query(
        PatentInventor.patent_id, func.sum(PatentInventor.contribution_ratio)
    ).group_by(PatentInventor.patent_id).all()
    bad_ratio_ids = [pid for pid, s in ratio_rows if s is not None and not (99 <= float(s) <= 101)]
    add("P_BAD_RATIO", "专利", "发明人贡献比合计不等于 100%", "medium",
        "贡献比合计异常会导致奖金分摊金额与核定总额不一致。",
        "/patent",
        P.filter(Patent.id.in_(bad_ratio_ids)) if bad_ratio_ids else P.filter(Patent.id == -1),
        p_label, "contribution_ratio")

    # ---------- 商标 ----------
    add("T_NO_NO", "商标", "缺少注册/申请号", "high",
        "注册号缺失无法与官方数据核对，也无法办理续展。",
        "/trademark", T.filter(_blank(Trademark.trademark_no)), t_label, "trademark_no")

    add("T_REG_NO_DATE", "商标", "已注册但缺注册日期", "high",
        "注册日期缺失会导致有效期与续展截止日推算错误。",
        "/trademark",
        T.filter(Trademark.status.in_(["已注册", "已续展"]), Trademark.registration_date == None),
        t_label, "registration_date")

    add("T_NO_CLASS", "商标", "缺少尼斯分类", "medium",
        "尼斯分类缺失会导致保护范围不明，注册范围库无法比对。",
        "/trademark", T.filter(_blank(Trademark.nice_class)), t_label, "nice_class")

    add("T_NO_SCOPE", "商标", "未归入注册范围分组", "low",
        "未归组的商标在按业务线统计时会落入「其他」。",
        "/trademark", T.filter(_blank(Trademark.scope_group)), t_label, "scope_group")

    add("T_NO_AGENCY", "商标", "未关联代理机构", "low",
        "未关联代理机构时，代理费用归集会漏算。",
        "/trademark", T.filter(Trademark.agency_id == None), t_label, "agency_id")

    add("T_EXPIRING", "商标", "有效期已过但状态未更新", "high",
        "有效期已过却仍为「已注册」，请确认是否已续展或已失效。",
        "/trademark",
        T.filter(Trademark.valid_until < today, Trademark.status.in_(["已注册", "申请中"])),
        t_label, "status")

    # ---------- 年费 ----------
    def f_label(f):
        p = db.query(Patent).filter(Patent.id == f.patent_id).first()
        return {"id": f.id,
                "title": f"{(p.patent_name if p else '未知专利')} · 第{f.fee_year}年",
                "sub": f"到期 {f.due_date}" if f.due_date else "无到期日",
                "route": f"/patent/{f.patent_id}"}

    F = db.query(PatentFee)

    add("F_PAID_NO_RECEIPT", "年费", "已缴但缺缴费凭证", "medium",
        "缺少凭证号与凭证附件，审计与报销时无法追溯。",
        "/patent-fees",
        F.filter(PatentFee.status == "已缴", _blank(PatentFee.receipt_no),
                 PatentFee.receipt_file_id == None),
        f_label, "receipt_no")

    add("F_PAID_NO_AMOUNT", "年费", "已缴但缺实缴金额", "high",
        "实缴金额缺失会导致费用统计与预算对比失真。",
        "/patent-fees",
        F.filter(PatentFee.status == "已缴",
                 or_(PatentFee.actual_pay_amount == None, PatentFee.actual_pay_amount == 0)),
        f_label, "actual_pay_amount")

    add("F_OVERDUE", "年费", "已过期但仍为待缴", "high",
        "已超过到期日仍未缴纳，存在专利失效风险，请立即处理。",
        "/patent-fees",
        F.filter(PatentFee.due_date < today, PatentFee.status == "待缴"),
        f_label, "status")

    add("F_NO_DUEDATE", "年费", "缺少到期日", "medium",
        "无到期日的年费不会进入提醒队列，容易漏缴。",
        "/patent-fees", F.filter(PatentFee.due_date == None), f_label, "due_date")

    # ---------- 奖金 ----------
    def bi_label(i):
        return {"id": i.id, "title": i.patent_name or f"奖金项 #{i.id}",
                "sub": f"{i.milestone or '-'} · {i.department or '无部门'}",
                "route": "/patent-bonus"}

    B = db.query(PatentBonusItem)

    add("B_NO_DEPT", "奖金", "奖金项缺少部门", "medium",
        "部门缺失会让部门奖金分布图出现「未分类」，影响分摊统计。",
        "/patent-bonus", B.filter(_blank(PatentBonusItem.department)), bi_label, "department")

    add("B_NO_PATENT", "奖金", "奖金项未关联专利", "medium",
        "未关联专利的奖金项无法回溯依据，建议补齐关联。",
        "/patent-bonus", B.filter(PatentBonusItem.patent_id == None), bi_label, "patent_id")

    add("B_OVER_PAID", "奖金", "已发金额超过核定金额", "high",
        "已发大于应发说明数据录入有误或存在重复发放。",
        "/patent-bonus",
        B.filter(PatentBonusItem.received_amount > PatentBonusItem.approved_amount,
                 PatentBonusItem.approved_amount > 0),
        bi_label, "received_amount")

    # 奖金明细未匹配到员工（只有外部姓名）
    unmatched = db.query(
        PatentBonusDetail.external_name, func.count(PatentBonusDetail.id),
        func.sum(PatentBonusDetail.amount)
    ).filter(
        PatentBonusDetail.inventor_id == None,
        func.trim(func.coalesce(PatentBonusDetail.external_name, "")) != ""
    ).group_by(PatentBonusDetail.external_name).all()
    checks.append({
        "code": "B_UNMATCHED_INVENTOR",
        "category": "奖金",
        "title": "奖金发明人未匹配到员工档案",
        "severity": "medium",
        "hint": "仅保存了姓名文本未关联员工，无法按部门/在职状态统计，建议在系统设置补建员工。",
        "route": "/settings",
        "fix_field": "inventor_id",
        "count": len(unmatched),
        "samples": [{"id": 0, "title": n, "sub": f"{c} 条明细 · {float(a or 0):,.0f} 元",
                     "route": "/settings"} for n, c, a in unmatched[:sample]]
    })

    # 草稿批次滞留超过 30 天
    stale_cut = today - timedelta(days=30)
    stale = db.query(PatentBonusBatch).filter(
        PatentBonusBatch.status == "草稿",
        PatentBonusBatch.created_at < stale_cut
    ).all()
    checks.append({
        "code": "B_STALE_DRAFT",
        "category": "奖金",
        "title": "草稿批次滞留超过 30 天",
        "severity": "low",
        "hint": "长期处于草稿的批次可能被遗忘，请确认是否提交审批或删除。",
        "route": "/patent-bonus",
        "fix_field": "status",
        "count": len(stale),
        "samples": [{"id": b.id, "title": b.batch_name or b.batch_code,
                     "sub": f"创建于 {str(b.created_at)[:10]}", "route": "/patent-bonus"}
                    for b in stale[:sample]]
    })

    # ---------- 员工 / 基础档案 ----------
    def e_label(e):
        return {"id": e.id, "title": e.name, "sub": e.employee_no or "无工号",
                "route": "/settings"}

    E = db.query(Employee).filter(Employee.is_deleted == False)
    add("E_NO_DEPT", "基础档案", "员工缺少部门", "medium",
        "员工无部门会导致部门奖金分布统计不准。",
        "/settings", E.filter(_blank(Employee.department)), e_label, "department")

    add("E_NO_NO", "基础档案", "员工缺少工号", "low",
        "工号缺失时 Excel 导入难以精确匹配到人。",
        "/settings", E.filter(_blank(Employee.employee_no)), e_label, "employee_no")

    def a_label(a):
        return {"id": a.id, "title": a.agency_name, "sub": a.contact_person or "无联系人",
                "route": f"/agency/{a.id}"}

    A = db.query(Agency).filter(Agency.is_deleted == False)
    add("A_NO_CONTACT", "基础档案", "代理机构缺少联系方式", "low",
        "缺少联系人/电话，紧急年费沟通时无法及时联络。",
        "/agency",
        A.filter(_blank(Agency.contact_person), _blank(Agency.contact_phone)),
        a_label, "contact_person")

    # ---------- 汇总打分 ----------
    # 每个检查项按严重度设扣分上限，命中即扣基础分(35%)，再按影响面比例递增到上限
    cap = {"high": 8.0, "medium": 4.0, "low": 1.5}
    rank = {"high": 3, "medium": 2, "low": 1}
    base_total = (
        db.query(Patent).filter(Patent.is_deleted == False).count()
        + db.query(Trademark).filter(Trademark.is_deleted == False).count()
        + db.query(PatentFee).count()
        + db.query(PatentBonusItem).count()
    ) or 1

    penalty = 0.0
    for c in checks:
        if c["count"] <= 0:
            continue
        ratio = min(1.0, c["count"] / base_total)
        penalty += cap[c["severity"]] * (0.35 + 0.65 * ratio)
    score = max(0, min(100, round(100 - penalty, 1)))

    issues = [c for c in checks if c["count"] > 0]
    passed = [c for c in checks if c["count"] == 0]
    issues.sort(key=lambda c: (-rank[c["severity"]], -c["count"]))

    return {
        "checked_at": str(today),
        "score": score,
        "summary": {
            "check_total": len(checks),
            "passed": len(passed),
            "issue_kinds": len(issues),
            "high": sum(1 for c in issues if c["severity"] == "high"),
            "medium": sum(1 for c in issues if c["severity"] == "medium"),
            "low": sum(1 for c in issues if c["severity"] == "low"),
            "affected_records": sum(c["count"] for c in issues),
            "scanned_records": base_total
        },
        "issues": issues,
        "passed": [{"code": c["code"], "category": c["category"], "title": c["title"]} for c in passed]
    }


@router.get("/audit-logs")
def report_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str = Query(""),
    business_type: str = Query(""),
    business_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    """Paginated audit logs for reports/settings."""
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if business_type:
        q = q.filter(AuditLog.business_type == business_type)
    if business_id:
        q = q.filter(AuditLog.business_id == business_id)

    total = q.count()
    logs = q.order_by(AuditLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{
            "id": l.id,
            "user_id": l.user_id,
            "user_name": l.user_name,
            "action": l.action,
            "business_type": l.business_type,
            "business_id": l.business_id,
            "before_value": l.before_value,
            "after_value": l.after_value,
            "created_at": l.created_at
        } for l in logs]
    }
