"""AI 能力路由：对话查询 / 政策解析 / 智能汇报 / 到期提醒。

三档开关由 ai_bridge 控制（none / local / cloud），默认 none。
设计原则：数据聚合与 AI 摘要解耦 ——
  - query / parse-policy 依赖 AI，none 模式下返回友好提示；
  - report / reminders 先聚合数据，none 模式下仍返回纯数据（无 AI 摘要）。
"""
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app import ai_bridge
from app.database import get_db
from app.models import Patent, PatentFee, Trademark, PatentBonusBatch
from app.security import get_current_user
from app.models import SysUser

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ========== 请求体 ==========
class QueryRequest(BaseModel):
    question: str


class ParsePolicyRequest(BaseModel):
    text: str
    policy_type: str = "奖金规则"


# ========== 状态查询 ==========
@router.get("/status")
def ai_status(current_user: SysUser = Depends(get_current_user)):
    """返回当前 AI 开关状态与模型可达性（不含密钥）。"""
    st = ai_bridge.get_status()
    ok, detail = ai_bridge.ping()
    st["reachable"] = ok
    st["reachable_detail"] = detail or None
    # 模型不可达时，规则引擎仍能回答高频问题
    st["offline_capable"] = True
    return st


# ========== 1. 智能数据助手（NL2SQL，可读写） ==========
NL2SQL_SYSTEM = """你是 IP 管理系统的智能数据助手。把用户的自然语言需求转成 SQLite 语句（SELECT/INSERT/UPDATE/DELETE 都允许）。
只输出 SQL 本身，不要任何解释、不要 markdown 代码块。

数据库表（字段与示例值）：

- patent（专利）
  id, application_no（申请号，文本）, patent_name（专利名称）, patent_type（类型：发明/实用新型/外观/软产/软著）,
  application_date（申请日，'YYYY-MM-DD'）, authorization_date（授权日，'YYYY-MM-DD'）, applicant（申请人，默认"示例科技有限公司"）,
  inventors（发明人，逗号分隔字符串）, ipc_classification（IPC分类号）, is_pct（是否PCT：0/1）, official_fee, agency_fee,
  fee_year1~fee_year10（各年度年费金额，数字）, status（状态：申请中/受理/实审中/授权/维持中/驳回/失效）, agency_id, description, is_deleted（软删除：0/1）, created_at

- trademark（商标）
  id, trademark_no, trademark_type（文字/图形/文字+图形）, application_date, registration_date, valid_until（有效期至）,
  nice_class（尼斯分类，逗号分隔字符串）, scope_group（运动台/光学传感/电子/其他）, applicant, status（申请中/已注册/驳回/已续展/已失效/部分授权/审中/授权）, description, is_deleted, created_at

- patent_fee（专利年费记录）
  id, patent_id, fee_year（1-20）, due_date（应缴日，'YYYY-MM-DD'）, actual_pay_date, standard_amount, actual_pay_amount,
  status（待缴/已缴/逾期/滞纳金）, agency_id, receipt_no, notes, imported_from

- agency（代理机构）
  id, agency_name, status（合作中/暂停/已终止）, contact_person, contact_phone, email

- patent_bonus_batch（奖金批次）
  id, batch_code, batch_name, total_amount, status（草稿/审批中/已批准/已发放）, period_start, period_end

- patent_bonus_item（奖金条目）
  id, batch_id, patent_id, patent_name, patent_type, milestone（受理/授权/PCT叠加）, approved_amount, received_amount, applied_amount, total_amount, payment_status

- patent_bonus_detail（发明人分配明细）
  id, bonus_item_id, inventor_id（员工ID，关联 employee.id），external_name（外部发明人姓名），contribution_ratio, amount

- patent_bonus_approval（奖金审批记录）
  id, bonus_item_id, step（ip_engineer/rd_director/md）, approver_id, approve_status（待审/通过/驳回）, approve_comment, approve_time

- employee（员工）
  id, name, department, bu, position, status（在职/离职）

规则：
1. 可执行任何 SQL：SELECT / INSERT / UPDATE / DELETE 都允许（用户授权）。
2. 日期字段按 'YYYY-MM-DD' 字符串存储，比较用字符串：
   - 「今年」→ WHERE application_date LIKE strftime('%Y','now') || '-%'
   - 「本月」→ WHERE application_date LIKE strftime('%Y-%m','now') || '-%'
3. 模糊匹配用 LIKE '%关键词%'。
4. 统计：COUNT(*)、SUM(col)、GROUP BY、ORDER BY DESC（默认 LIMIT 100）。
5. INSERT 时必填字段必须给出（id 自动；时间字段可省略，默认 now()）。
6. UPDATE / DELETE 推荐先 SELECT 验证再执行。
7. 多表 JOIN 用 ON 关联（如 patent_bonus_item.patent_id = patent.id）。
8. status 等枚举字段值必须严格匹配，不要用近似词（如不要写"已授权"，要写"授权"）。
9. 「发明人姓名」在 employee.name，要 JOIN patent_bonus_detail 与 employee。
10. 年份筛选示例：WHERE pb.period_start >= '2025-01-01' AND pb.period_end <= '2025-12-31' 或 WHERE strftime('%Y', pb.period_start) = '2025'。
11. **不要返回空字符串**：哪怕需要简化问题、只查部分字段、或用近似条件，都必须返回一条可执行的 SQL。
12. 常见查询模板：
    - 谁某年奖金超过X：SELECT COALESCE(e.name, pd.external_name), SUM(pd.amount) FROM patent_bonus_detail pd JOIN patent_bonus_item pi ON pi.id=pd.bonus_item_id JOIN patent_bonus_batch pb ON pb.id=pi.batch_id LEFT JOIN employee e ON e.id=pd.inventor_id WHERE strftime('%Y', pb.period_start)='年份' GROUP BY ... HAVING SUM(pd.amount)>X
    - 某年奖金总额：SELECT SUM(pi.total_amount) FROM patent_bonus_item pi JOIN patent_bonus_batch pb ON pb.id=pi.batch_id WHERE strftime('%Y', pb.period_start)='年份'
"""

SUMMARY_SYSTEM = """你是 IP（专利+商标）管理数据解读助手。基于下面给出的【用户问题】和【SQL 执行结果】，用简洁、专业、自然的中文回答用户的问题。
要求：
- 直接回答用户的问题，不复述
- 引用具体数字（数量、金额、日期等）
- 结果为空时明确告知「暂无匹配数据」并给出可能原因或排查建议
- 控制在 2~5 句话以内，避免堆砌
- 涉及金额一律使用「元」作为单位
- 如果执行的是 INSERT/UPDATE/DELETE，简明告知影响了多少行"""


def _clean_sql(sql: str) -> str:
    s = sql.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("sql"):
            s = s[3:]
        s = s.strip()
    s = s.rstrip(";").strip()
    return s


def _parse_amount(raw: str):
    """把 '1万' / '1.5万' / '5千' / '8000' / '1w' 转成数字，失败返回 None。"""
    import re
    m = re.match(r"^([\d.]+)\s*(万|千|w|k)?$", (raw or "").strip(), re.I)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    unit = (m.group(2) or "").lower()
    if unit in ("万", "w"):
        v *= 10000
    elif unit in ("千", "k"):
        v *= 1000
    return v


def _fmt_money(v):
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return str(v)
    return f"{v:,.0f}" if abs(v - round(v)) < 0.01 else f"{v:,.2f}"


def _people_line(rows, limit=10):
    return "、".join(
        f"{r.get('name')} {_fmt_money(r.get('total_bonus'))}元" for r in rows[:limit]
    )


def _rule_engine(question: str):
    """内置规则引擎：命中高频问题时直接返回确定性的 SQL + 总结函数。

    与大模型路径的关系是「规则优先」，这样做有三个好处：
      1. 模型离线（如未接入内网大模型）时，常见问题依然能答；
      2. 免掉一次 5~20 秒的模型往返，秒回；
      3. 结果 100% 可控，不会有模型偶发写出错 SQL 的情况。
    未命中的复杂问题再交给大模型。
    返回 dict(sql, summarize, label) 或 None。
    """
    import re
    q = (question or "").strip()
    # 注意：金额整体作为一个捕获组，否则单位（万/千）会被丢掉
    AMT = r"([\d.]+\s*(?:万|千|w|k)?)"

    # ---- 谁 X 年奖金超过 Y ----
    m = re.search(rf"谁(\d{{4}})年奖金(?:超过|大于|高于)\s*{AMT}", q)
    if m:
        year, amt = m.group(1), _parse_amount(m.group(2))
        if amt is not None:
            def _s(rows):
                if not rows:
                    return (f"{year}年没有人奖金超过 {_fmt_money(amt)} 元。"
                            f"（该年最高为 {_peak_note(year)}）")
                return (f"{year}年奖金超过 {_fmt_money(amt)} 元的人员共 {len(rows)} 人："
                        f"{_people_line(rows)}。")
            return {
                "label": f"{year}年奖金超过{_fmt_money(amt)}元的人员",
                "sql": f"""SELECT COALESCE(e.name, pd.external_name) AS name, SUM(pd.amount) AS total_bonus
FROM patent_bonus_detail pd
JOIN patent_bonus_item pi ON pi.id = pd.bonus_item_id
JOIN patent_bonus_batch pb ON pb.id = pi.batch_id
LEFT JOIN employee e ON e.id = pd.inventor_id
WHERE strftime('%Y', pb.period_start) = '{year}'
GROUP BY COALESCE(e.name, pd.external_name)
HAVING SUM(pd.amount) > {amt}
ORDER BY total_bonus DESC
LIMIT 200""",
                "summarize": _s,
            }

    # ---- 各部门奖金分布 ----
    if re.search(r"各部门.*奖金|奖金.*部门|按部门.*奖金", q):

        def _s(rows):
            if not rows:
                return "暂无部门奖金数据。"
            parts = "、".join(f"{r.get('department')} {_fmt_money(r.get('total_bonus'))}元" for r in rows[:8])
            return f"部门奖金分布：{parts}。"
        return {
            "label": "部门奖金分布",
            "sql": """SELECT COALESCE(pi.department, '未分类') AS department, SUM(pi.total_amount) AS total_bonus
FROM patent_bonus_item pi
JOIN patent_bonus_batch pb ON pb.id = pi.batch_id
GROUP BY department
ORDER BY total_bonus DESC
LIMIT 20""",
            "summarize": _s,
        }

    # ---- 谁奖金最多 / 奖金排名 ----
    if re.search(r"(谁.*奖金(?:最多|最高)|奖金.*(?:最多|最高|排名))", q):
        m = re.search(r"(\d{4})年", q)
        where = f"WHERE strftime('%Y', pb.period_start) = '{m.group(1)}'" if m else ""
        scope = f"{m.group(1)}年" if m else "历年"

        def _s(rows):
            if not rows:
                return f"{scope}暂无奖金发放记录。"
            top = rows[0]
            return (f"{scope}奖金最高的是 {top.get('name')}，合计 "
                    f"{_fmt_money(top.get('total_bonus'))} 元；"
                    f"其后依次为 {_people_line(rows[1:6])}。")
        return {
            "label": f"{scope}发明人奖金排名",
            "sql": f"""SELECT COALESCE(e.name, pd.external_name) AS name, SUM(pd.amount) AS total_bonus
FROM patent_bonus_detail pd
JOIN patent_bonus_item pi ON pi.id = pd.bonus_item_id
JOIN patent_bonus_batch pb ON pb.id = pi.batch_id
LEFT JOIN employee e ON e.id = pd.inventor_id
{where}
GROUP BY COALESCE(e.name, pd.external_name)
ORDER BY total_bonus DESC
LIMIT 20""",
            "summarize": _s,
        }

    # ---- X 年奖金总额 ----
    m = re.search(r"(\d{4})年奖金总额", q)
    if m:
        year = m.group(1)

        def _s(rows):
            total = (rows[0].get("total_bonus") if rows else 0) or 0
            return f"{year}年奖金总额为 {_fmt_money(total)} 元（按奖金批次周期起始年份统计）。"
        return {
            "label": f"{year}年奖金总额",
            "sql": f"""SELECT SUM(pi.total_amount) AS total_bonus, COUNT(pi.id) AS item_count
FROM patent_bonus_item pi
JOIN patent_bonus_batch pb ON pb.id = pi.batch_id
WHERE strftime('%Y', pb.period_start) = '{year}'""",
            "summarize": _s,
        }

    # ---- 奖金年度趋势 ----
    if re.search(r"奖金.*年度趋势|奖金.*每年|每年.*奖金|奖金.*趋势", q) and re.search(r"趋势|每年|每年", q):

        def _s(rows):
            if not rows:
                return "暂无年度奖金数据。"
            parts = "、".join(f"{int(r.get('year'))}年 {_fmt_money(r.get('total_bonus'))}元" for r in rows)
            return f"奖金年度趋势：{parts}。"
        return {
            "label": "奖金年度趋势",
            "sql": """SELECT strftime('%Y', pb.period_start) AS year, SUM(pi.total_amount) AS total_bonus
FROM patent_bonus_item pi
JOIN patent_bonus_batch pb ON pb.id = pi.batch_id
WHERE pb.period_start IS NOT NULL
GROUP BY year
ORDER BY year""",
            "summarize": _s,
        }

    # ---- 奖金总额（不指定年） ----
    if re.search(r"奖金总额|总共?发(?:了|放)?多少奖金", q) and not re.search(r"\d{4}", q):
        def _s(rows):
            total = (rows[0].get("total_bonus") if rows else 0) or 0
            return f"历年奖金累计总额为 {_fmt_money(total)} 元。"
        return {
            "label": "奖金累计总额",
            "sql": """SELECT SUM(pi.total_amount) AS total_bonus, COUNT(pi.id) AS item_count
FROM patent_bonus_item pi""",
            "summarize": _s,
        }

    # ---- 专利类型分布 ----
    if re.search(r"专利类型分布|专利.*类型.*分布|各类专利.*比例", q):

        def _s(rows):
            if not rows:
                return "暂无专利类型数据。"
            parts = "、".join(f"{r.get('patent_type')} {r.get('count')}件" for r in rows)
            return f"专利类型分布：{parts}。"
        return {
            "label": "专利类型分布",
            "sql": """SELECT patent_type, COUNT(*) AS count
FROM patent WHERE is_deleted = 0 AND patent_type IS NOT NULL AND patent_type != ''
GROUP BY patent_type
ORDER BY count DESC""",
            "summarize": _s,
        }

    # ---- 专利总数 ----
    if re.search(r"(专利总数|多少件专利|专利.*一共|一共.*专利)", q) and not re.search(r"\d{4}", q):
        def _s(rows):
            r0 = rows[0] if rows else {}
            detail = [f"{label} {r0.get(k)} 件"
                      for k, label in [("invented", "发明"), ("utility", "实用新型"),
                                       ("design", "外观"), ("software", "软著/软产")]
                      if r0.get(k)]
            base = f"当前在库专利共 {r0.get('total', 0)} 件"
            return f"{base}，其中{'、'.join(detail)}。" if detail else base + "。"
        return {
            "label": "专利总数",
            "sql": """SELECT COUNT(*) AS total,
  SUM(CASE WHEN patent_type = '发明' THEN 1 ELSE 0 END) AS invented,
  SUM(CASE WHEN patent_type = '实用新型' THEN 1 ELSE 0 END) AS utility,
  SUM(CASE WHEN patent_type = '外观' THEN 1 ELSE 0 END) AS design,
  SUM(CASE WHEN patent_type IN ('软著','软产') THEN 1 ELSE 0 END) AS software
FROM patent WHERE is_deleted = 0""",
            "summarize": _s,
        }

    # ---- X 类型专利多少件 ----
    m = re.search(r"(发明|实用新型|外观|软著|软产).{0,6}(?:多少件|数量|有多少)", q)
    if m:
        ptype = m.group(1)

        def _s(rows):
            r0 = rows[0] if rows else {}
            return (f"「{ptype}」类专利共 {r0.get('total', 0)} 件，"
                    f"其中已授权 {r0.get('granted', 0)} 件、审查中 {r0.get('pending', 0)} 件。")
        return {
            "label": f"{ptype}专利数量",
            "sql": f"""SELECT COUNT(*) AS total,
  SUM(CASE WHEN status IN ('授权','已登记','维持中') THEN 1 ELSE 0 END) AS granted,
  SUM(CASE WHEN status IN ('受理','实质审查','申请中') THEN 1 ELSE 0 END) AS pending
FROM patent WHERE is_deleted = 0 AND patent_type = '{ptype}'""",
            "summarize": _s,
        }

    # ---- 近 X 年专利申请趋势 ----
    m = re.search(r"近(\d+)年.*专利.*趋势|专利.*近(\d+)年.*趋势|专利申请趋势|每年.*申请.*专利", q)
    if m:
        years = int(m.group(1) or m.group(2) or 5)

        def _s(rows):
            if not rows:
                return f"近 {years} 年暂无专利申请数据。"
            parts = "、".join(f"{r.get('year')}年 {r.get('count')}件" for r in rows)
            return f"近 {years} 年专利申请趋势：{parts}。"
        return {
            "label": f"近{years}年专利申请趋势",
            "sql": f"""SELECT strftime('%Y', application_date) AS year, COUNT(*) AS count
FROM patent
WHERE is_deleted = 0 AND application_date IS NOT NULL
  AND application_date >= date('now','-{years+1} years')
GROUP BY year
ORDER BY year""",
            "summarize": _s,
        }

    # ---- X 年申请了多少件专利 ----
    m = re.search(r"(\d{4})年.{0,8}(?:申请|新增).{0,4}(?:多少|几)件", q)
    if m:
        year = m.group(1)

        def _s(rows):
            return f"{year}年共申请专利 {(rows[0] or {}).get('total', 0) if rows else 0} 件。"
        return {
            "label": f"{year}年专利申请量",
            "sql": f"""SELECT COUNT(*) AS total FROM patent
WHERE is_deleted = 0 AND application_date >= '{year}-01-01' AND application_date <= '{year}-12-31'""",
            "summarize": _s,
        }

    # ---- 商标总数 ----
    if re.search(r"(商标总数|多少件商标|商标.*一共|一共.*商标)", q):
        def _s(rows):
            r0 = rows[0] if rows else {}
            return (f"当前在库商标共 {r0.get('total', 0)} 件，"
                    f"其中已注册 {r0.get('registered', 0)} 件、申请中 {r0.get('applying', 0)} 件。")
        return {
            "label": "商标总数",
            "sql": """SELECT COUNT(*) AS total,
  SUM(CASE WHEN status IN ('已注册','已续展') THEN 1 ELSE 0 END) AS registered,
  SUM(CASE WHEN status = '申请中' THEN 1 ELSE 0 END) AS applying
FROM trademark WHERE is_deleted = 0""",
            "summarize": _s,
        }

    # ---- 待缴年费 ----
    if re.search(r"(待缴年费|未缴年费|还有多少年费|年费.*待缴)", q):
        def _s(rows):
            r0 = rows[0] if rows else {}
            return (f"当前待缴年费共 {r0.get('total', 0)} 笔，"
                    f"应缴金额合计 {_fmt_money(r0.get('amount'))} 元"
                    f"（其中已逾期 {r0.get('overdue', 0)} 笔）。")
        return {
            "label": "待缴年费汇总",
            "sql": f"""SELECT COUNT(*) AS total,
  SUM(COALESCE(standard_amount, 0) + COALESCE(late_fee, 0)) AS amount,
  SUM(CASE WHEN due_date < date('now') THEN 1 ELSE 0 END) AS overdue
FROM patent_fee WHERE status = '待缴'""",
            "summarize": _s,
        }

    # ---- 已缴年费金额 ----
    if re.search(r"(已缴年费|年费.*已缴|缴纳了多少年费)", q):
        def _s(rows):
            r0 = rows[0] if rows else {}
            return (f"已缴年费共 {r0.get('total', 0)} 笔，实缴金额合计 "
                    f"{_fmt_money(r0.get('amount'))} 元。")
        return {
            "label": "已缴年费汇总",
            "sql": """SELECT COUNT(*) AS total, SUM(COALESCE(actual_pay_amount,0)) AS amount
FROM patent_fee WHERE status = '已缴'""",
            "summarize": _s,
        }

    # ---- 即将到期 / 逾期年费 ----
    if re.search(r"(快到期|即将到期|到期).{0,4}(年费)?|年费.*(快|即将|马上)", q) and re.search(r"年费", q):
        def _s(rows):
            if not rows:
                return "未来 90 天内没有到期的待缴年费，暂无缴纳压力。"
            names = "、".join(
                f"《{r.get('patent_name')}》第{r.get('fee_year')}年（{r.get('due_date')}）"
                for r in rows[:5])
            return f"未来 90 天内共有 {len(rows)} 笔年费到期：{names}。"
        return {
            "label": "近期到期年费",
            "sql": """SELECT p.patent_name, pf.fee_year, pf.due_date, pf.status,
  COALESCE(pf.standard_amount,0) + COALESCE(pf.late_fee,0) AS payable
FROM patent_fee pf
JOIN patent p ON p.id = pf.patent_id
WHERE pf.status = '待缴' AND pf.due_date >= date('now')
  AND pf.due_date <= date('now','+90 days')
ORDER BY pf.due_date
LIMIT 100""",
            "summarize": _s,
        }

    # ---- 被驳回的专利 ----
    if re.search(r"(被?驳回).{0,6}专利|专利.{0,6}(被?驳回)", q) and not re.search(r"(奖金|年费)", q):
        def _s(rows):
            if not rows:
                return "目前没有处于「驳回」状态的专利，全部专利都还在正常流程中。"
            parts = "、".join(
                f"《{r.get('patent_name')}》（{r.get('patent_type')}，{r.get('status')}）"
                for r in rows[:8])
            return f"被驳回的专利共 {len(rows)} 件：{parts}。"
        return {
            "label": "被驳回的专利",
            "sql": """SELECT patent_name, patent_type, status, inventors
FROM patent WHERE is_deleted = 0
  AND status LIKE '%驳回%'
ORDER BY application_date DESC
LIMIT 100""",
            "summarize": _s,
        }

    # ---- 年费缴纳情况（总括：已缴 / 待缴 / 逾期）----
    if re.search(r"年费.{0,4}(缴纳|缴|情况|统计|汇总)|缴纳.{0,4}年费.{0,4}(情况|统计)", q):
        def _s(rows):
            r0 = rows[0] if rows else {}
            return (f"年费缴纳情况：已缴 {r0.get('paid_count', 0)} 笔共 "
                    f"{_fmt_money(r0.get('paid_amount'))} 元；"
                    f"待缴 {r0.get('pending_count', 0)} 笔共 "
                    f"{_fmt_money(r0.get('pending_amount'))} 元"
                    f"（其中已逾期 {r0.get('overdue_count', 0)} 笔）。")
        return {
            "label": "年费缴纳情况总括",
            "sql": """SELECT
  SUM(CASE WHEN status = '已缴' THEN 1 ELSE 0 END) AS paid_count,
  SUM(CASE WHEN status = '已缴' THEN COALESCE(actual_pay_amount,0) ELSE 0 END) AS paid_amount,
  SUM(CASE WHEN status = '待缴' THEN 1 ELSE 0 END) AS pending_count,
  SUM(CASE WHEN status = '待缴' THEN COALESCE(standard_amount,0) + COALESCE(late_fee,0) ELSE 0 END) AS pending_amount,
  SUM(CASE WHEN status = '待缴' AND due_date < date('now') THEN 1 ELSE 0 END) AS overdue_count
FROM patent_fee""",
            "summarize": _s,
        }

    # ---- 待续展商标 ----
    if re.search(r"(待续展|需要?续展|续展.{0,4}商标|商标.{0,4}(续展|到期))", q):
        def _s(rows):
            if not rows:
                return "未来 90 天内没有需要续展的商标，商标到期风险较低。"
            parts = "、".join(
                f"《{r.get('trademark_name')}》（{r.get('valid_until')}）"
                for r in rows[:8])
            return f"未来 90 天内到期、需要续展的商标共 {len(rows)} 件：{parts}。"
        return {
            "label": "待续展商标",
            "sql": """SELECT trademark_name, valid_until, status
FROM trademark WHERE is_deleted = 0
  AND valid_until IS NOT NULL
  AND valid_until <= date('now','+90 days')
ORDER BY valid_until
LIMIT 100""",
            "summarize": _s,
        }

    return None


def _peak_note(year: str) -> str:
    """空结果时给出该年实际最高值，避免用户以为是系统坏了。"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        row = db.execute(text(f"""
            SELECT COALESCE(e.name, pd.external_name) AS name, SUM(pd.amount) AS total_bonus
            FROM patent_bonus_detail pd
            JOIN patent_bonus_item pi ON pi.id = pd.bonus_item_id
            JOIN patent_bonus_batch pb ON pb.id = pi.batch_id
            LEFT JOIN employee e ON e.id = pd.inventor_id
            WHERE strftime('%Y', pb.period_start) = '{year}'
            GROUP BY COALESCE(e.name, pd.external_name)
            ORDER BY total_bonus DESC LIMIT 1
        """)).fetchone()
    except Exception:
        return "该年暂无数据"
    finally:
        db.close()
    if not row:
        return "该年暂无奖金数据"
    return f"{row[0]} {_fmt_money(row[1])} 元"


def _generic_summary(question: str, result) -> str:
    """规则未命中且模型不可用时，也给出一句可读的结论。"""
    if not isinstance(result, list):
        return ""
    if not result:
        return "查询完成，但没有匹配的数据。可以换个说法，或把条件放宽一些再试。"
    r0 = result[0]
    if "affected_rows" in r0:
        return f"执行完成，影响 {r0.get('affected_rows')} 行（{r0.get('statement', '')}）。"
    cols = list(r0.keys())
    head = "、".join(f"{c}={r0.get(c)}" for c in cols[:4])
    more = f"，另有 {len(result) - 1} 条" if len(result) > 1 else ""
    return f"查询到 {len(result)} 条结果{more}。第一条：{head}。"


# ========== 图表生成引擎（让 AI 助手不只是表格，还能出图） ==========

def _color_palette(n: int):
    base = ["#409EFF", "#67C23A", "#E6A23C", "#F56C6C", "#8E44AD",
            "#00B4D8", "#FF7F50", "#909399", "#2ECC71", "#3498DB"]
    return [base[i % len(base)] for i in range(n)]


def _to_number(v):
    try:
        return float(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _build_pie(rows, name_col, value_col, title=""):
    data = [{"name": str(r.get(name_col, "")), "value": _to_number(r.get(value_col))}
            for r in rows if r.get(name_col) is not None]
    data.sort(key=lambda x: x["value"], reverse=True)
    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "normal"}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {"orient": "vertical", "left": "left", "type": "scroll"},
        "series": [{
            "type": "pie", "radius": ["40%", "65%"], "center": ["60%", "55%"],
            "data": data,
            "itemStyle": {"borderRadius": 4, "borderColor": "#fff", "borderWidth": 1},
            "label": {"formatter": "{b}\n{d}%"},
            "color": _color_palette(len(data)),
        }]
    }


def _build_bar(rows, name_col, value_col, title="", horizontal=True):
    cats = [str(r.get(name_col, "")) for r in rows]
    vals = [_to_number(r.get(value_col)) for r in rows]
    axis = {"type": "value"}
    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "normal"}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": axis if not horizontal else {"type": "category", "data": cats, "axisLabel": {"interval": 0}},
        "yAxis": {"type": "category", "data": cats, "axisLabel": {"interval": 0}} if horizontal else axis,
        "series": [{
            "type": "bar", "data": vals,
            "itemStyle": {"borderRadius": horizontal and [0, 4, 4, 0] or [4, 4, 0, 0]},
            "color": "#409EFF",
        }]
    }


def _build_line(rows, name_col, value_col, title=""):
    cats = [str(r.get(name_col, "")) for r in rows]
    vals = [_to_number(r.get(value_col)) for r in rows]
    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "normal"}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "category", "data": cats, "boundaryGap": False},
        "yAxis": {"type": "value"},
        "series": [{"type": "line", "data": vals, "smooth": True, "areaStyle": {"opacity": 0.15}, "color": "#409EFF"}]
    }


def _chart_engine(question: str, result):
    """根据问题与结果列，生成 ECharts option JSON。"""
    import re
    if not isinstance(result, list) or len(result) < 1 or "affected_rows" in (result[0] or {}):
        return None
    q = (question or "").strip()
    cols = list(result[0].keys())
    if len(cols) < 2:
        return None
    name_col, value_col = cols[0], cols[1]

    # 部门奖金 / 专利类型 / 商标状态 → 饼图
    if re.search(r"部门.*奖金|奖金.*部门|按部门|专利类型|类型分布|商标状态|状态分布", q):
        return _build_pie(result, name_col, value_col,
                          title=re.search(r"部门", q) and "部门奖金分布" or
                                re.search(r"专利类型|类型", q) and "专利类型分布" or "分布")

    # 发明人排名 / TOP10 / 谁奖金最多 / 各部门总额 → 条形图
    if re.search(r"发明人|排名|TOP|最多|最高|各部门|各类型", q, re.I):
        return _build_bar(result, name_col, value_col,
                          title=re.search(r"发明人", q) and "发明人奖金排名" or "排名")

    # 年份趋势 → 折线图
    if re.search(r"趋势|每年|近.*年|年度|变化", q) or re.search(r"^\d{4}$", str(result[0].get(name_col, ""))):
        return _build_line(result, name_col, value_col,
                           title=re.search(r"奖金", q) and "奖金年度趋势" or "年度趋势")

    return None


@router.post("/query")
def ai_query(body: QueryRequest, db: Session = Depends(get_db),
             current_user: SysUser = Depends(get_current_user)):
    question = (body.question or "").strip()
    if not question:
        return {"enabled": ai_bridge.is_enabled(), "error": "问题不能为空"}

    # ① 先走内置规则引擎：命中则无需联网，秒回且结果确定。
    #    规则引擎是纯本地确定性逻辑，不依赖大模型，
    #    因此即使 AI_MODE=none（未接入模型）也应正常提供服务。
    rule = _rule_engine(question)
    offline_note = None
    model_online = ai_bridge.is_reachable()

    if rule:
        sql = rule["sql"]
        source = "rule"
    elif not ai_bridge.is_enabled():
        # 规则未命中，且未启用大模型 —— 明确告知并给出可问清单
        return {
            "enabled": False,
            "message": "该问题需要大模型处理，当前未启用（AI_MODE=none）。"
                       "以下常见问题由内置规则引擎提供，无需模型即可直接提问：",
            "hint": ("「被驳回的专利有哪些」「年费缴纳情况怎么样」「哪些商标待续展」"
                     "「还有多少待缴年费」「近期到期年费」「各部门奖金分布」"
                     "「2025年谁奖金最多」「专利总数」「商标总数」。"),
        }
    elif not model_online:
        # 规则未命中且模型不可达 —— 不必等一次长超时，直接给可操作的提示
        _, detail = ai_bridge.ping()
        return {
            "enabled": True,
            "question": question,
            "error": f"大模型暂时不可用（{detail or '无法连接模型服务'}）",
            "offline": True,
            "hint": ("当前未接入内网大模型时，本地大模型无法连接。以下问题仍可直接问："
                     "「谁2025年奖金超过5000」「2025年奖金总额」「谁奖金最多」"
                     "「专利总数」「发明专利多少件」「待缴年费」「商标总数」「近期到期年费」。"),
        }
    else:
        # ② 未命中且模型在线才调大模型
        try:
            sql = ai_bridge.chat(
                [{"role": "system", "content": NL2SQL_SYSTEM},
                 {"role": "user", "content": question}],
                temperature=0.1, max_tokens=1500,
            )
        except ai_bridge.AIUnavailable as e:
            return {
                "enabled": True,
                "question": question,
                "error": f"大模型暂时不可用（{e}）",
                "offline": True,
                "hint": ("当前未接入内网大模型时，本地大模型无法连接。以下问题仍可直接问："
                         "「谁2025年奖金超过5000」「2025年奖金总额」「专利总数」"
                         "「发明专利多少件」「待缴年费」「商标总数」「近期到期年费」。"),
            }

        # 模型返回空时再要一次简化版 SQL
        if not sql or not sql.strip():
            try:
                sql = ai_bridge.chat(
                    [{"role": "system", "content": NL2SQL_SYSTEM + "\n\n重要：必须返回一条可执行的 SQL，哪怕用近似条件（如 '发明人' 字段模糊匹配）、简化字段（如 SELECT 5 个字段）、或加 LIMIT 5。只输出 SQL 本身，不要解释。"},
                     {"role": "user", "content": f"原问题：{question}\n请给出一条尽可能覆盖该问题的 SQL。"}],
                    temperature=0.2, max_tokens=800,
                )
            except ai_bridge.AIUnavailable:
                pass
        source = "ai"

    sql = _clean_sql(sql)

    # 防御：两条路都没拿到 SQL
    if not sql:
        return {
            "enabled": True,
            "question": question,
            "error": "AI 未能生成有效 SQL，请换一种问法，例如：2025 年奖金超过 1 万的人有哪些？",
        }

    try:
        res = db.execute(text(sql))
        # 处理 INSERT/UPDATE/DELETE：cursor.rowcount
        if res.returns_rows:
            columns = list(res.keys())
            rows = res.fetchall()
            result = [dict(zip(columns, row)) for row in rows]
        else:
            db.commit()
            stmt_type = (sql.split() or ['UNKNOWN'])[0].upper()
            result = [{"affected_rows": res.rowcount, "statement": stmt_type}]
            columns = list(result[0].keys()) if result else []
    except Exception as e:  # noqa: BLE001
        db.rollback()
        return {"enabled": True, "error": f"SQL 执行失败：{e}", "sql": sql}

    # 生成自然语言结论：规则命中先用规则，否则交给模型润色
    summary = None
    if rule:
        try:
            summary = (rule["summarize"](result) or "").strip()
        except Exception:
            summary = None
        # 规则路径下若模型在线，额外让模型补充一句解读（失败不影响主结果）
        if summary and model_online:
            try:
                sample = result[:20] if isinstance(result, list) else result
                raw = ai_bridge.chat(
                    [{"role": "system", "content": SUMMARY_SYSTEM},
                     {"role": "user", "content": f"用户问题：{question}\n已知结论：{summary}\n明细：{json.dumps(sample, ensure_ascii=False, default=str)}"}],
                    temperature=0.3, max_tokens=400,
                )
                if raw and raw.strip():
                    summary = raw.strip()
                    source = "ai"
            except ai_bridge.AIUnavailable:
                offline_note = "大模型当前不可达，以下结论由内置查询引擎直接给出。"
    elif model_online:
        try:
            sample = result[:20] if isinstance(result, list) and result and isinstance(result[0], dict) and 'affected_rows' not in result[0] else result
            ctx = (
                f"用户问题：{question}\n\n"
                f"执行的 SQL：{sql}\n\n"
                f"结果（共 {len(result) if isinstance(result, list) else 0} 条）：\n"
                f"{json.dumps(sample, ensure_ascii=False, default=str)}"
            )
            raw = ai_bridge.chat(
                [{"role": "system", "content": SUMMARY_SYSTEM},
                 {"role": "user", "content": ctx}],
                temperature=0.3, max_tokens=500,
            )
            summary = (raw or "").strip()
        except ai_bridge.AIUnavailable:
            summary = None
            offline_note = "大模型当前不可达，以下结论由内置查询引擎直接给出。"

    # 兜底：无论如何都给一句可读结论，不让用户面对空白
    if not summary:
        summary = _generic_summary(question, result)

    # 如果结果适合出图，顺带生成 ECharts option
    chart_option = _chart_engine(question, result)

    return {
        "enabled": True,
        "question": question,
        "sql": sql,
        "result": result,
        "summary": summary,
        "source": source,
        "label": (rule or {}).get("label"),
        "offline_note": offline_note,
        "chart_option": chart_option,
    }


# ========== 2. 政策 / 规则文档解析 ==========
PARSE_POLICY_SYSTEM = """你是政策文档解析助手。从下面的文档文本中抽取规则，输出严格 JSON（不要 markdown、不要解释）。

JSON 结构：
{
  "policy_name": "政策/规则名称",
  "effective_date": "生效日期或空字符串",
  "rules": [
    {"condition": "触发条件", "amount": "金额或计算方式", "period": "发放周期或空字符串"}
  ],
  "notes": "其他说明或空字符串"
}

只输出 JSON 对象本身。"""


@router.post("/parse-policy")
def ai_parse_policy(body: ParsePolicyRequest, current_user: SysUser = Depends(get_current_user)):
    text_content = (body.text or "").strip()
    if not text_content:
        return {"enabled": ai_bridge.is_enabled(), "error": "文本不能为空"}

    if not ai_bridge.is_enabled():
        return {"enabled": False, "message": "AI 政策解析未启用。请在环境变量设置 AI_MODE=local 或 cloud 后重试。"}

    try:
        parsed = ai_bridge.chat_json(
            [{"role": "system", "content": PARSE_POLICY_SYSTEM},
             {"role": "user", "content": text_content}],
            temperature=0.1, max_tokens=2000,
        )
    except ai_bridge.AIUnavailable as e:
        return {"enabled": True, "error": str(e)}

    return {"enabled": True, "parsed": parsed}


# ========== 3. 智能汇报 ==========
def _aggregate_stats(db: Session, period: str = ""):
    """聚合 IP 资产统计数据（与 AI 无关，任何模式都可用）。"""
    patent_q = db.query(Patent).filter(Patent.is_deleted == False)
    tm_q = db.query(Trademark).filter(Trademark.is_deleted == False)

    patent_total = patent_q.count()
    patent_by_type = dict(
        db.query(Patent.patent_type, func.count(Patent.id))
        .filter(Patent.is_deleted == False)
        .group_by(Patent.patent_type).all()
    )
    patent_by_status = dict(
        db.query(Patent.status, func.count(Patent.id))
        .filter(Patent.is_deleted == False)
        .group_by(Patent.status).all()
    )
    tm_total = tm_q.count()
    tm_by_status = dict(
        db.query(Trademark.status, func.count(Trademark.id))
        .filter(Trademark.is_deleted == False)
        .group_by(Trademark.status).all()
    )

    pending_fees = db.query(func.count(PatentFee.id)).filter(
        PatentFee.status.in_(["待缴", "逾期"])
    ).scalar() or 0

    bonus_paid = db.query(func.coalesce(func.sum(PatentBonusBatch.total_amount), 0)).filter(
        PatentBonusBatch.status == "已发放"
    ).scalar() or 0

    return {
        "period": period or "全部",
        "patent_total": patent_total,
        "patent_by_type": patent_by_type,
        "patent_by_status": patent_by_status,
        "trademark_total": tm_total,
        "trademark_by_status": tm_by_status,
        "pending_fee_count": pending_fees,
        "bonus_paid_total": bonus_paid,
    }


REPORT_SYSTEM = """你是 IP（专利+商标）管理汇报助手。根据下面 JSON 统计数据，用简洁专业的中文生成一段 100~200 字的月度汇报摘要，突出关键数字和值得注意的点。不要编造数据。"""


@router.get("/report")
def ai_report(period: str = Query("", description="汇报周期，如 2026-07"),
              db: Session = Depends(get_db),
              current_user: SysUser = Depends(get_current_user)):
    data = _aggregate_stats(db, period)

    if not ai_bridge.is_enabled():
        return {"enabled": False, "data": data, "summary": None,
                "message": "AI 摘要未启用（当前仅返回统计数据）。"}

    try:
        summary = ai_bridge.chat(
            [{"role": "system", "content": REPORT_SYSTEM},
             {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
            temperature=0.3, max_tokens=600,
        )
    except ai_bridge.AIUnavailable as e:
        return {"enabled": True, "data": data, "summary": None, "error": str(e)}

    return {"enabled": True, "data": data, "summary": summary}


# ========== 4. 到期 / 风险智能提醒 ==========
def _collect_reminders(db: Session, days: int):
    """收集即将到期的年费 / 商标续展（与 AI 无关）。"""
    today = date.today()
    horizon = today + timedelta(days=days)

    reminders = []

    # 专利年费：应缴日在 horizon 内且状态待缴/逾期
    fees = db.query(PatentFee).filter(
        PatentFee.due_date.isnot(None),
        PatentFee.due_date <= horizon,
        PatentFee.due_date >= today - timedelta(days=30),
        PatentFee.status.in_(["待缴", "逾期"]),
    ).order_by(PatentFee.due_date).all()

    for f in fees:
        days_left = (f.due_date - today).days
        reminders.append({
            "type": "专利年费",
            "title": f"专利年费到期：{f.patent.patent_name if f.patent else '未知专利'}",
            "detail": f"第 {f.fee_year} 年，应缴日 {f.due_date}，金额 {f.standard_amount or 0} 元",
            "due_date": str(f.due_date),
            "days_left": days_left,
            "status": f.status,
        })

    # 商标续展：有效期在 horizon 内且已注册
    tms = db.query(Trademark).filter(
        Trademark.valid_until.isnot(None),
        Trademark.valid_until <= horizon,
        Trademark.valid_until >= today,
        Trademark.status == "已注册",
        Trademark.is_deleted == False,
    ).order_by(Trademark.valid_until).all()

    for t in tms:
        days_left = (t.valid_until - today).days
        reminders.append({
            "type": "商标续展",
            "title": f"商标即将到期：{t.trademark_name}",
            "detail": f"注册号 {t.trademark_no or '-'}，有效期至 {t.valid_until}",
            "due_date": str(t.valid_until),
            "days_left": days_left,
            "status": "已注册",
        })

    reminders.sort(key=lambda x: x["days_left"])
    return reminders


REMINDER_SYSTEM = """你是 IP 管理提醒助手。根据下面的到期提醒列表（JSON），用简洁中文生成一段摘要，概括最紧急的几项和整体风险。不要编造。"""


@router.get("/reminders")
def ai_reminders(days: int = Query(90, description="提醒时间窗口（天）"),
                 db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)):
    reminders = _collect_reminders(db, days)

    if not ai_bridge.is_enabled():
        return {"enabled": False, "reminders": reminders, "summary": None,
                "message": "AI 摘要未启用（当前仅返回提醒数据）。"}

    try:
        summary = ai_bridge.chat(
            [{"role": "system", "content": REMINDER_SYSTEM},
             {"role": "user", "content": json.dumps(reminders, ensure_ascii=False)}],
            temperature=0.3, max_tokens=400,
        )
    except ai_bridge.AIUnavailable as e:
        return {"enabled": True, "reminders": reminders, "summary": None, "error": str(e)}

    return {"enabled": True, "reminders": reminders, "summary": summary}
