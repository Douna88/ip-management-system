# -*- coding: utf-8 -*-
"""演示数据生成器 · Demo Data Seeder

为全新克隆生成一套**完全虚构**的演示数据，用于功能演示与界面预览。

设计要点：
  1. **固定随机种子** → 每次生成的数据完全一致，便于截图、演示、回归测试。
  2. **零真实数据** → 所有专利、商标、人名、机构均为虚构，不含任何公司信息。
  3. **覆盖全部功能** → 五种专利类型、年费阶梯与费减、奖金批次链路、
     商标尼斯分类、代理机构、费用标准，确保每个页面都有内容可看。
  4. **幂等** → 重复执行会先清空业务表再重建，不会产生脏数据。

用法：
    python seed_demo.py                # 写入默认数据库
    from seed_demo import load_demo_data; load_demo_data(db)   # 传入 session
"""
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.models import (
    Agency, AgencyPriceChange, BonusRule, Employee, FeeStandard,
    Patent, PatentBonusBatch, PatentBonusDetail, PatentBonusItem,
    PatentFee, PatentInventor, SysUser, Trademark, TrademarkScope,
)
from app.security import hash_password

# 固定种子：保证任何人、任何机器上生成的数据完全一致
SEED = 20260101
_rng = random.Random(SEED)

TODAY = date.today()

# ---------------------------------------------------------------- 虚构语料库

SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
            "徐", "孙", "马", "朱", "胡", "郭", "林", "何", "高", "罗"]
GIVEN_NAMES = ["伟", "芳", "娜", "敏", "静", "强", "磊", "洋", "勇", "艳",
               "杰", "涛", "明", "超", "秀英", "建国", "晓东", "志远", "文博", "思远"]

DEPARTMENTS = ["研发一部", "研发二部", "光学工程部", "控制算法部",
               "软件平台部", "精密机械部", "电子工程部"]

# 专利名称模板：采用中文专利常见命名习惯，技术领域通用化
PATENT_TEMPLATES = [
    "一种{m}的{a}方法",
    "一种{m}的{a}装置",
    "一种基于{m}的{a}系统及方法",
    "一种用于{m}的{a}结构",
    "{m}的{a}控制方法及装置",
    "一种高精度{m}{a}及其校准方法",
]
TECH_MODULES = ["精密位移台", "光学镜头组", "运动控制器", "图像传感器", "激光测距",
                "温控平台", "数据采集", "视觉对位", "振动抑制", "误差补偿",
                "多轴联动", "光束整形", "自动对焦", "信号滤波", "边缘检测"]
ACTION_WORDS = ["控制", "检测", "校准", "补偿", "识别", "定位", "测量", "优化"]

# 商标：虚构品牌造词，避免与任何真实商标近似
BRAND_WORDS = ["NexMove", "OptiCore", "PrecisionX", "智控", "锐视", "UltraStage",
               "BrightPath", "恒准", "SmartAxis", "ClearView", "微纳", "NovaTech",
               "稳行", "FlexMotion", "精测", "AeroStage", "睿控", "PureLens"]

PATENT_TYPES = ["发明", "实用新型", "外观", "软著", "软产"]
PATENT_STATUS = ["授权", "审中", "受理", "驳回终止", "撤回", "转让"]

AGENCY_NAMES = [
    "中科佳诚知识产权代理有限公司",
    "华进联合专利商标代理有限公司",
    "集慧智诚知识产权代理事务所",
    "允天知识产权代理有限公司",
    "智汇远见专利事务所",
]

SCOPE_GROUPS = ["精密机械", "光学传感", "电子控制", "软件与算法", "其他"]

# 国知局公开收费标准（元）：专利类型 -> [(起始年, 结束年, 官费)]
YEAR_FEE_LADDER = {
    "发明": [(1, 3, 900), (4, 6, 1200), (7, 9, 2000),
             (10, 12, 4000), (13, 15, 6000), (16, 20, 8000)],
    "实用新型": [(1, 3, 600), (4, 5, 900), (6, 8, 1200), (9, 10, 2000)],
    "外观": [(1, 3, 600), (4, 5, 900), (6, 8, 1200), (9, 10, 2000), (11, 15, 3000)],
}
MAX_YEAR = {"发明": 20, "实用新型": 10, "外观": 15, "软著": 0, "软产": 0}

# 尼斯分类（公开的分类体系）
NICE_CLASSES = [
    (7, "机械设备", "0742 金属加工机械；0749 工业自动化设备"),
    (9, "科学仪器", "0901 计算机及外部设备；0913 传感器；0910 测量仪器"),
    (35, "广告销售", "3501 广告；3503 商业管理辅助"),
    (37, "建筑修理", "3706 机械安装维护；3718 设备安装"),
    (40, "材料加工", "4015 材料处理；4001 定制加工"),
    (42, "技术服务", "4220 计算机编程；4214 工业设计与研究"),
]


# ---------------------------------------------------------------- 工具函数

def _name():
    return _rng.choice(SURNAMES) + _rng.choice(GIVEN_NAMES)


def _patent_name():
    """生成专利名称，并规避『控制控制』这类词语重复。"""
    for _ in range(12):
        name = _rng.choice(PATENT_TEMPLATES).format(
            m=_rng.choice(TECH_MODULES), a=_rng.choice(ACTION_WORDS))
        # 检测连续重复片段（两个字符重复出现），如 控制控制 / 检测检测
        if not re.search(r"(.{2})\1", name):
            return name
    return name


def _date(start_year, end_year):
    """在给定年份区间内随机取一天。"""
    start = date(start_year, 1, 1)
    end = min(date(end_year, 12, 31), TODAY)
    if start >= end:
        return start
    return start + timedelta(days=_rng.randint(0, (end - start).days))


def _year_fee(ptype, year):
    """按国知局阶梯返回某年度官费；无年费类型返回 0。"""
    for lo, hi, amount in YEAR_FEE_LADDER.get(ptype, []):
        if lo <= year <= hi:
            return amount
    return 0


def _apply_reduction(amount, rate):
    """费减比例 -> 实缴金额。85% 表示减免 85%（实缴 15%）。"""
    if rate == "85%":
        return round(amount * 0.15, 2)
    if rate == "70%":
        return round(amount * 0.30, 2)
    return float(amount)


# ---------------------------------------------------------------- 各表生成

def _clear_all(db):
    """按外键逆序清空业务表（保留表结构）。"""
    for model in [PatentBonusDetail, PatentBonusItem, PatentBonusBatch, PatentFee,
                  PatentInventor, Patent, Trademark, TrademarkScope,
                  AgencyPriceChange, Agency, FeeStandard, BonusRule,
                  Employee, SysUser]:
        db.query(model).delete()
    db.commit()


def _seed_users(db):
    users = [
        SysUser(username="admin", password_hash=hash_password("admin123"),
                display_name="系统管理员", email="admin@example.com", role="admin"),
        SysUser(username="demo", password_hash=hash_password("demo123"),
                display_name="演示账号", email="demo@example.com", role="member"),
    ]
    db.add_all(users)
    db.commit()
    return users


def _seed_employees(db, count=14):
    emps = []
    used = set()
    while len(emps) < count:
        n = _name()
        if n in used:
            continue
        used.add(n)
        emps.append(Employee(
            employee_no=f"E{1000 + len(emps)}",
            name=n,
            department=_rng.choice(DEPARTMENTS),
            bu=_rng.choice(["BU1", "BU2", "BU3"]),
            position=_rng.choice(["工程师", "高级工程师", "主任工程师", "技术专家"]),
            email=f"user{len(emps)+1}@example.com",
            hire_date=_date(2018, 2024),
            status="active",
        ))
    db.add_all(emps)
    db.commit()
    return emps


def _seed_agencies(db):
    agencies = []
    for i, name in enumerate(AGENCY_NAMES):
        agencies.append(Agency(
            agency_name=name,
            contact_person=_name(),
            contact_phone=f"010-{_rng.randint(1000,9999)}{_rng.randint(1000,9999)}",
            email=f"contact{i+1}@example.com",
            address=f"北京市海淀区示例路 {_rng.randint(1,200)} 号",
            business_scope="专利,商标,PCT",
            cooperation_start=_date(2019, 2022),
            status=_rng.choice(["合作中", "合作中", "合作中", "暂停"]),
            notes="演示数据：代理机构信息为虚构。",
        ))
    db.add_all(agencies)
    db.commit()

    # 价格变更记录：每家 1~2 条
    changes = []
    for a in agencies:
        for _ in range(_rng.randint(1, 2)):
            old = _rng.choice([1800, 2500, 3200, 4500])
            new = round(old * _rng.uniform(0.9, 1.15), -1)
            changes.append(AgencyPriceChange(
                agency_id=a.id,
                change_date=_date(2022, 2025),
                service_item=_rng.choice(["发明专利代理费", "实用新型代理费",
                                          "商标申请代理费", "年费代缴服务费"]),
                old_price=old,
                new_price=new,
                change_reason=_rng.choice(["服务内容扩充", "市场价格调整", "长期合作优惠"]),
                effective_date=_date(2022, 2025),
            ))
    db.add_all(changes)
    db.commit()
    return agencies


def _seed_fee_standards(db):
    """费用标准：直接采用国知局公开收费标准。"""
    rows = []
    for ptype, ladder in YEAR_FEE_LADDER.items():
        for lo, hi, amount in ladder:
            rows.append(FeeStandard(
                category="国内",
                fee_type=f"年费（第{lo}-{hi}年）" if lo != hi else f"年费（第{lo}年）",
                patent_type=ptype,
                year_start=lo,
                year_end=hi,
                standard_amount=amount,
                reduced_85_amount=round(amount * 0.15, 2),
                reduced_70_amount=round(amount * 0.30, 2),
                unit="元",
                note="数据来源：国家知识产权局公开收费标准",
                effective_from=date(2023, 1, 1),
                source="国知局收费标准（公开信息）",
            ))
    # 申请阶段费用
    for ptype, fee_name, amount in [
        ("发明", "申请费", 900), ("发明", "实质审查费", 2500),
        ("实用新型", "申请费", 500), ("外观", "申请费", 500),
    ]:
        rows.append(FeeStandard(
            category="国内", fee_type=fee_name, patent_type=ptype,
            standard_amount=amount,
            reduced_85_amount=round(amount * 0.15, 2),
            reduced_70_amount=round(amount * 0.30, 2),
            unit="元", effective_from=date(2023, 1, 1),
            source="国知局收费标准（公开信息）",
        ))
    db.add_all(rows)
    db.commit()


def _seed_bonus_rules(db):
    rules = [
        BonusRule(
            rule_name="知识产权奖励办法（2024版）",
            effective_from=date(2024, 1, 1),
            is_current=True,
            rules_json='{"发明":{"受理":3000,"授权":5000},'
                       '"实用新型":{"受理":1000,"授权":1000},'
                       '"软著":{"授权":3000},"PCT叠加":5000}',
            raw_text="演示数据：奖励标准示例。发明受理3000元、授权5000元；"
                     "实用新型受理1000元、授权1000元；软著授权3000元；PCT叠加5000元。",
        ),
        BonusRule(
            rule_name="知识产权奖励办法（2022版）",
            effective_from=date(2022, 1, 1),
            effective_until=date(2023, 12, 31),
            is_current=False,
            rules_json='{"发明":{"受理":2000,"授权":4000},'
                       '"实用新型":{"受理":800,"授权":800},'
                       '"软著":{"授权":2000},"PCT叠加":4000}',
            raw_text="演示数据：历史版本奖励标准。",
        ),
    ]
    db.add_all(rules)
    db.commit()
    return rules


def _seed_patents(db, employees, agencies, count=42):
    patents = []
    type_weights = (["发明"] * 22 + ["实用新型"] * 8 + ["外观"] * 5
                    + ["软著"] * 5 + ["软产"] * 2)
    for i in range(count):
        ptype = type_weights[i % len(type_weights)]
        app_date = _date(2017, 2025)
        status = _rng.choices(
            PATENT_STATUS, weights=[30, 22, 14, 10, 4, 5], k=1)[0]

        auth_date = None
        auth_no = None
        if status in ("授权", "转让"):
            auth_date = app_date + timedelta(days=_rng.randint(400, 1000))
            if auth_date > TODAY:
                auth_date = TODAY - timedelta(days=_rng.randint(30, 400))
            auth_no = f"ZL{app_date.year}{_rng.randint(1000000, 9999999)}"

        has_reduction = _rng.random() < 0.45
        rate = _rng.choice(["85%", "70%"]) if has_reduction else "none"

        p = Patent(
            application_no=f"CN{app_date.year}{_rng.randint(100000, 999999)}.{_rng.randint(0,9)}",
            patent_name=_patent_name(),
            patent_type=ptype,
            status=status,
            application_date=app_date,
            authorization_no=auth_no,
            authorization_date=auth_date,
            applicant="示例科技有限公司",
            inventors="",  # 由 _seed_inventors 回填
            ipc_classification=f"{_rng.choice(['G01B','G02B','H01L','G05B','G06T'])}"
                               f"{_rng.randint(1,99)}/{_rng.randint(10,99)}",
            correspondence_project=f"项目{_rng.choice('ABCDEF')}{_rng.randint(100,999)}",
            correspondence_product=_rng.choice(TECH_MODULES),
            protection_element=_rng.choice([
                "独立权利要求1记载的技术方案",
                "装置权利要求1-3的结构特征",
                "方法权利要求1的步骤流程",
            ]),
            quick_examination=_rng.random() < 0.15,
            expedited_examination=_rng.random() < 0.1,
            fee_reduction=has_reduction,
            fee_reduction_rate=rate,
            official_fee=_rng.choice([900, 500, 2500, 3000]),
            agency_fee=float(_rng.choice([1800, 2500, 3200, 4500])),
            pre_examination_fee=float(_rng.choice([0, 500, 800])),
            agency_id=_rng.choice(agencies).id,
            agency_case_no=f"AG{_rng.randint(10000, 99999)}",
            is_pct=_rng.random() < 0.12,
            description="演示数据：本条记录为系统自动生成的虚构专利。",
        )
        patents.append(p)

    db.add_all(patents)
    db.commit()
    return patents


def _seed_inventors(db, patents, employees):
    """为每件专利分配 1~4 名发明人，并回填 patent.inventors 字符串。"""
    rows = []
    for p in patents:
        k = _rng.randint(1, 4)
        picked = []
        used_names = set()
        # 70% 概率从在册员工选，其余用外部姓名（模拟合作方发明人）
        for order in range(1, k + 1):
            # 同一件专利内发明人不可重复
            for _try in range(20):
                if employees and _rng.random() < 0.7:
                    e = _rng.choice(employees)
                    nm, emp_id, ext = e.name, e.id, None
                else:
                    nm, emp_id, ext = _name(), None, _name()
                if nm not in used_names:
                    break
            else:
                continue
            used_names.add(nm)
            rows.append(PatentInventor(
                patent_id=p.id, employee_id=emp_id, external_name=ext,
                order_no=len(picked) + 1,
                contribution_ratio=round(100 / k, 1)))
            picked.append(nm)
        p.inventors = ",".join(picked)

    db.add_all(rows)
    db.commit()


def _seed_patent_fees(db, patents, agencies):
    """按类型生成年费记录：已缴 / 待缴 / 逾期 三种状态并存。"""
    rows = []
    for p in patents:
        max_year = MAX_YEAR.get(p.patent_type, 0)
        if max_year == 0:
            continue  # 软著 / 软产 无年费

        # 应缴年限：从申请日第 1 年到今年（最多 max_year 年）
        elapsed = TODAY.year - p.application_date.year
        years = min(max_year, max(elapsed, 1))

        for y in range(1, years + 1):
            due = date(p.application_date.year + y,
                       p.application_date.month,
                       min(p.application_date.day, 28))
            amount = _year_fee(p.patent_type, y)
            reduced = _apply_reduction(amount, p.fee_reduction_rate or "none")

            # 状态分配：早期基本已缴，近期存在待缴/逾期
            if due < TODAY - timedelta(days=365):
                status = "已缴"
            elif due < TODAY:
                status = _rng.choices(["已缴", "待缴"], weights=[65, 35], k=1)[0]
                if status == "待缴" and due < TODAY - timedelta(days=60):
                    status = "逾期"
            else:
                status = "待缴"

            paid_date = None
            paid_amount = None
            late = 0.0
            if status == "已缴":
                paid_date = due - timedelta(days=_rng.randint(5, 60))
                paid_amount = reduced
            elif status == "逾期":
                late = round(reduced * 0.05 * _rng.randint(1, 4), 2)

            rows.append(PatentFee(
                patent_id=p.id,
                fee_year=y,
                due_date=due,
                actual_pay_date=paid_date,
                standard_amount=float(amount),
                reduced_amount=reduced,
                actual_pay_amount=paid_amount,
                agency_id=_rng.choice(agencies).id,
                receipt_no=f"FP{_rng.randint(100000, 999999)}" if status == "已缴" else None,
                status=status,
                late_fee=late,
                payment_source=_rng.choice(["官费", "代理代缴"]),
                notes="演示数据" if status != "已缴" else None,
            ))
    db.add_all(rows)
    db.commit()
    return rows


def _seed_trademarks(db, agencies, count=32):
    rows = []
    nice_pool = [n[0] for n in NICE_CLASSES]
    for i in range(count):
        app_date = _date(2018, 2025)
        status = _rng.choices(
            ["已注册", "申请中", "审中", "部分授权", "驳回", "已续展"],
            weights=[42, 18, 14, 6, 8, 12], k=1)[0]
        reg_date = None
        if status in ("已注册", "部分授权", "已续展"):
            reg_date = app_date + timedelta(days=_rng.randint(300, 700))
        valid_until = (reg_date or app_date) + timedelta(days=365 * 10)
        renewal = 1 if status == "已续展" else 0

        rows.append(Trademark(
            trademark_no=f"TM{app_date.year}{_rng.randint(100000, 999999)}",
            trademark_name=f"{_rng.choice(BRAND_WORDS)}"
                           f"{_rng.choice(['', ' Pro', ' Plus', ' 系列', ' S1'])}",
            trademark_type=_rng.choice(["文字", "图形", "文字+图形"]),
            application_date=app_date,
            registration_date=reg_date,
            valid_until=valid_until,
            nice_class=",".join(str(c) for c in _rng.sample(nice_pool, _rng.randint(1, 3))),
            scope_group=_rng.choice(SCOPE_GROUPS),
            applicant="示例科技有限公司",
            agency_id=_rng.choice(agencies).id,
            status=status,
            renewal_count=renewal,
            last_renewal_date=valid_until - timedelta(days=365) if renewal else None,
            contact_person=_name(),
            notes="演示数据：商标信息为虚构。",
        ))
    db.add_all(rows)
    db.commit()
    return rows


def _seed_trademark_scope(db):
    rows = []
    for group in SCOPE_GROUPS:
        for nice, class_name, sub in _rng.sample(NICE_CLASSES, 4):
            rows.append(TrademarkScope(
                scope_group=group,
                nice_class=nice,
                subclass_code=f"{nice:02d}{_rng.randint(1,99):02d}",
                subclass_name=sub.split("；")[0],
                class_name=class_name,
                specific_products=f"{_rng.choice(TECH_MODULES)}、{_rng.choice(ACTION_WORDS)}设备",
                description="演示数据：注册范围库条目。",
                is_active=True,
            ))
    db.add_all(rows)
    db.commit()


def _seed_bonus(db, patents, employees, rules):
    """奖金链路：批次 -> 条目（关联专利）-> 明细（发明人分配）。"""
    current_rule = rules[0]
    batches = []
    for idx, (year, half) in enumerate([(2023, 1), (2023, 2), (2024, 1),
                                        (2024, 2), (2025, 1), (2025, 2)]):
        start = date(year, 7 if half == 2 else 1, 1)
        end = date(year, 12, 31) if half == 2 else date(year, 6, 30)
        batches.append(PatentBonusBatch(
            batch_code=f"B{year}H{half}",
            batch_name=f"{year}年{'下' if half == 2 else '上'}半年知识产权奖金",
            rule_id=current_rule.id,
            period_start=start,
            period_end=end,
            status=_rng.choice(["已发放", "已发放", "已批准", "草稿"]),
            created_by=1,
        ))
    db.add_all(batches)
    db.commit()

    # 只给有授权的专利发奖金，且里程碑区分 受理 / 授权
    granted = [p for p in patents if p.status in ("授权", "转让")]
    _rng.shuffle(granted)

    items = []
    for b in batches:
        n = _rng.randint(5, 10)
        for p in granted[:n]:
            milestone = _rng.choices(["受理", "授权"], weights=[40, 60], k=1)[0]
            base = 3000 if p.patent_type == "发明" else 1000
            if p.patent_type in ("软著", "软产"):
                base = 3000
            amount = base if milestone == "受理" else int(base * 1.6)
            if p.is_pct:
                amount += 5000

            items.append(PatentBonusItem(
                batch_id=b.id,
                patent_id=p.id,          # 关键：打通专利 -> 奖金关联
                patent_type=p.patent_type,
                patent_name=p.patent_name,
                milestone=milestone,
                department=_rng.choice(DEPARTMENTS),
                approved_amount=float(amount),
                received_amount=float(amount) if b.status == "已发放" else 0.0,
                applied_amount=float(amount),
                rule_id=current_rule.id,
                base_amount=float(amount),
                pct_bonus=5000.0 if p.is_pct else 0.0,
                total_amount=float(amount),
                payment_status="已发" if b.status == "已发放" else "待发",
                payment_date=b.period_end + timedelta(days=30) if b.status == "已发放" else None,
                source=_rng.choice(["系统计算", "系统计算", "Excel导入"]),
            ))
    db.add_all(items)
    db.commit()

    # 明细：按发明人等分
    details = []
    inv_map = {}
    for inv in db.query(PatentInventor).all():
        inv_map.setdefault(inv.patent_id, []).append(inv)

    for it in items:
        invs = inv_map.get(it.patent_id, [])
        if not invs:
            continue
        share = round(it.total_amount / len(invs), 2)
        for inv in invs:
            details.append(PatentBonusDetail(
                bonus_item_id=it.id,
                inventor_id=inv.employee_id,
                external_name=inv.external_name,
                contribution_ratio=inv.contribution_ratio,
                amount=share,
                milestone_amount='{"%s": %s}' % (it.milestone, share),
                payment_status=it.payment_status,
            ))
    db.add_all(details)
    db.commit()

    # 回算批次总额
    for b in batches:
        b.total_amount = sum(i.total_amount for i in b.items)
    db.commit()
    return batches, items, details


# ---------------------------------------------------------------- 入口

def load_demo_data(db=None):
    """生成演示数据。传入 SQLAlchemy session 则用它，否则自建连接。"""
    owns = db is None
    if owns:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()

    try:
        print("Clearing existing data...")
        _clear_all(db)

        print("Seeding users / employees / agencies ...")
        _seed_users(db)
        employees = _seed_employees(db)
        agencies = _seed_agencies(db)

        print("Seeding fee standards / bonus rules ...")
        _seed_fee_standards(db)
        rules = _seed_bonus_rules(db)

        print("Seeding patents / inventors / fees ...")
        patents = _seed_patents(db, employees, agencies)
        _seed_inventors(db, patents, employees)
        fees = _seed_patent_fees(db, patents, agencies)

        print("Seeding trademarks / scope library ...")
        _seed_trademarks(db, agencies)
        _seed_trademark_scope(db)

        print("Seeding bonus batches / items / details ...")
        batches, items, details = _seed_bonus(db, patents, employees, rules)

        db.commit()
        print("\n=== Demo data generated successfully ===")
        print(f"  专利 {len(patents)} 件 | 年费 {len(fees)} 条")
        print(f"  奖金批次 {len(batches)} | 条目 {len(items)} | 明细 {len(details)}")
        print(f"  商标 32 件 | 员工 {len(employees)} 人 | 代理机构 {len(agencies)} 家")
        print("\n登录账号：admin / admin123   或   demo / demo123")
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        if owns:
            db.close()


if __name__ == "__main__":
    load_demo_data()
