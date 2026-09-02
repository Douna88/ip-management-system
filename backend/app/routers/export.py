"""Dashboard export router: HTML / PDF / PPT downloads.

- /api/export/dashboard/html  -> 独立 HTML 文件（完整内容，含 ECharts 图表）
- /api/export/dashboard/pdf   -> 完整 PDF 文件（reportlab 生成，中文支持）
- /api/export/dashboard/ppt   -> 按 PPT 模板风格的汇报 PPT（python-pptx）
"""
import io
import json
import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user_flexible
from app.models import SysUser, Patent, Trademark, PatentFee, PatentBonusBatch, PatentBonusItem

from app.routers.reports import report_overview, bonus_stats

router = APIRouter(prefix="/api/export", tags=["export"])

# ---------------- 工具 ----------------

def _collect_dashboard_data(year: int, db: Session):
    """聚合看板所需的全部数据。"""
    overview = report_overview(year=year, db=db, current_user=None)
    bstat = bonus_stats(year=year, db=db, current_user=None)

    # 专利清单（按申请日期倒序，最多 100 条）
    patents = db.query(Patent).filter(Patent.is_deleted == False).order_by(
        Patent.application_date.desc()).limit(100).all()
    patent_list = []
    for p in patents:
        patent_list.append({
            "name": p.patent_name,
            "type": p.patent_type or "",
            "status": p.status or "",
            "inventors": p.inventors or "",
            "apply_date": str(p.application_date or ""),
        })

    # 奖金批次明细
    batches = db.query(PatentBonusBatch).order_by(PatentBonusBatch.created_at.desc()).all()
    batch_list = []
    for b in batches:
        items = db.query(PatentBonusItem).filter(
            PatentBonusItem.batch_id == b.id).all()
        batch_list.append({
            "name": b.batch_name or f"批次{b.id}",
            "period": f"{b.period_start or ''} ~ {b.period_end or ''}",
            "total": float(b.total_amount or 0),
            "status": b.status or "",
            "item_count": len(items),
        })

    return {
        "year": year,
        "overview": overview,
        "bonus": bstat,
        "patents": patent_list,
        "batches": batch_list,
    }


def _fmt_money(n):
    try:
        return f"¥{float(n):,.2f}".replace(".00", "")
    except (TypeError, ValueError):
        return "¥0"


def _top_n_depts(dist, n=8):
    """部门奖金分布：取 Top N，其余合并为「其他"。"""
    items = sorted(((k, v) for k, v in (dist or {}).items() if v > 0), key=lambda x: -x[1])
    top = items[:n]
    other = sum(v for _, v in items[n:])
    out = dict(top)
    if other > 0:
        out["其他"] = other
    return out


# ---------------- 模块选择解析 ----------------

def _parse_module_selection(modules: str) -> set:
    """解析 modules 参数：空/未指定 = 全部；否则按逗号分隔的白名单取交集。"""
    _valid = {"overview", "patent", "bonus", "fee", "system"}
    if modules:
        s = {m.strip() for m in modules.split(",") if m.strip() in _valid}
        if s:
            return s
    return set(_valid)


# ---------------- HTML 导出 ----------------

@router.get("/dashboard/html")
def export_dashboard_html(
    year: int = Query(None),
    modules: str = Query("", description="逗号分隔模块：overview,patent,bonus,fee,system；空=全部"),
    ai: bool = Query(False, description="是否附加 AI 智能分析（调用本地大模型）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user_flexible),
):
    if not year:
        year = date.today().year
    data = _collect_dashboard_data(year, db)
    o, b = data["overview"], data["bonus"]
    km = b.get("key_metrics", {})
    module_set = _parse_module_selection(modules)
    use_ai = bool(ai)

    # 图表数据（JSON 注入给 ECharts）
    chart_payload = {
        "patentType": {t: v for t, v in (o.get("patent", {}).get("by_type", {}) or {}).items() if v > 0},
        "patentTrend": o.get("patent", {}).get("trend_5yr", []),
        "tmStatus": {t: v for t, v in (o.get("trademark", {}).get("by_status", {}) or {}).items() if v > 0},
        "bonusYear": b.get("by_year", []),
        "top10": b.get("top10_inventors", []),
        "dept": _top_n_depts(b.get("by_department")),
    }

    # 内联 SVG 图标（与系统看板一致）
    ICONS = {
        "专利总数": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        "商标总数": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>',
        "奖金总额": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg>',
        "待缴年费": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
        "已缴年费累计": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/></svg>',
        "奖金批次数": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    }

    # 指标卡
    metrics = [
        ("专利总数", str(o.get("patent", {}).get("total", 0)), f"本年新增 {o.get('patent', {}).get('new_this_year', 0)} 件", "#409EFF"),
        ("商标总数", str(o.get("trademark", {}).get("total", 0)), f"本年新增 {o.get('trademark', {}).get('new_this_year', 0)} 件", "#67C23A"),
        ("奖金总额", _fmt_money(km.get("total_amount", 0)), f"本年 {_fmt_money(km.get('this_year_amount', 0))}", "#E6A23C"),
        ("待缴年费", str(o.get("fee", {}).get("pending_count", 0)), _fmt_money(o.get("fee", {}).get("pending_amount", 0)), "#F56C6C"),
        ("已缴年费累计", _fmt_money(o.get("fee", {}).get("total_paid", 0)), f"本年 {_fmt_money(o.get('fee', {}).get('this_year_paid', 0))}", "#909399"),
        ("奖金批次数", str(km.get("batch_count", 0)), f"发明人 {km.get('inventor_count', 0)} 位", "#8E44AD"),
    ]

    # 奖金批次表
    batch_rows = "\n".join(
        f"<tr><td>{r['name']}</td><td>{r['period']}</td><td>{r['item_count']}</td>"
        f"<td style='text-align:right'>{_fmt_money(r['total'])}</td><td>{r['status']}</td></tr>"
        for r in data["batches"]
    )

    # 代理机构表
    agency_rows = "\n".join(
        f"<tr><td>{a['name']}</td><td style='text-align:center'>{a['patent_count']}</td>"
        f"<td style='text-align:center'>{a['trademark_count']}</td>"
        f"<td style='text-align:right'>{_fmt_money(a['total_amount'])}</td></tr>"
        for a in o.get("agency", [])
    )

    payload_json = json.dumps(chart_payload, ensure_ascii=False)

    # 模块筛选 + AI 分析（与 PPT 口径一致）
    metric_cards = "\n".join(
        f'''<div class="metric-card" style="--accent:{color}">
          <div class="metric-icon">{ICONS.get(label, '')}</div>
          <div class="metric-body"><div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-sub">{sub}</div></div>
        </div>'''
        for label, value, sub, color in metrics
        if (
            ("overview" in module_set and label in ("专利总数", "商标总数"))
            or ("bonus" in module_set and label in ("奖金总额", "奖金批次数"))
            or ("fee" in module_set and label in ("待缴年费", "已缴年费累计"))
        )
    )

    # 图表卡片按模块组装（两列网格，奇数卡片独占一行）
    chart_cells = []
    if "patent" in module_set:
        chart_cells.append('<div class="card"><h3>专利类型分布</h3><div id="c1" class="chart"></div></div>')
        chart_cells.append('<div class="card"><h3>近 5 年专利申请趋势</h3><div id="c2" class="chart"></div></div>')
        chart_cells.append('<div class="card"><h3>商标状态分布</h3><div id="c3" class="chart"></div></div>')
    if "bonus" in module_set:
        chart_cells.append('<div class="card"><h3>奖金年度发放趋势</h3><div id="c4" class="chart"></div></div>')
        chart_cells.append('<div class="card"><h3>发明人奖金 TOP10</h3><div id="c5" class="chart"></div></div>')
        chart_cells.append('<div class="card"><h3>部门奖金分布</h3><div id="c6" class="chart"></div></div>')
    charts_html = ""
    for i in range(0, len(chart_cells), 2):
        pair = chart_cells[i:i + 2]
        charts_html += '  <div class="grid">\n' + "\n".join("    " + c for c in pair) + "\n  </div>\n"

    batch_block = (
        '''  <div class="card" style="margin-bottom:16px"><h3>奖金批次明细</h3>
    <table><thead><tr><th>批次</th><th>期间</th><th>条目数</th><th style="text-align:right">金额</th><th>状态</th></tr></thead>
    <tbody>''' + batch_rows + "</tbody></table>\n  </div>\n"
        if "bonus" in module_set else ""
    )
    agency_block = (
        '''  <div class="card"><h3>代理机构合作统计</h3>
    <table><thead><tr><th>机构名称</th><th style="text-align:center">代理专利</th><th style="text-align:center">代理商标</th><th style="text-align:right">累计费用</th></tr></thead>
    <tbody>''' + agency_rows + "</tbody></table>\n  </div>\n"
        if "patent" in module_set else ""
    )

    ai_html = ""
    if use_ai:
        ai_lines = _gen_ai_analysis(data, module_set, year)
        if ai_lines:
            lis = "".join(
                f"<li>{txt}</li>" if not bold else f"<li class='ai-h'>{txt}</li>"
                for txt, _lvl, bold in ai_lines
            )
            ai_html = f'''  <div class="card ai-card"><h3>AI 智能分析 <span class="ai-badge">本地大模型生成</span></h3>
    <ul class="ai-list">{lis}</ul></div>
'''

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>IP 资产全景看板 {year}年</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f0f2f5; color:#303133; padding:32px 40px; }}
  .head {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom:24px; border-bottom:3px solid #409EFF; padding-bottom:16px; }}
  .head h1 {{ font-size:26px; font-weight:600; }}
  .head .sub {{ color:#909399; font-size:13px; margin-top:6px; }}
  .head .date {{ color:#909399; font-size:13px; }}
  .metric-row {{ display:grid; grid-template-columns:repeat(6,1fr); gap:14px; margin-bottom:20px; }}
  .metric-card {{ background:#fff; border-radius:12px; padding:16px 14px; display:flex; gap:12px; align-items:center; box-shadow:0 2px 8px rgba(0,0,0,.05); border-top:3px solid var(--accent); }}
  .metric-icon {{ width:42px; height:42px; border-radius:10px; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
  .metric-icon svg {{ width:22px; height:22px; }}
  .metric-body {{ flex:1; min-width:0; }}
  .metric-label {{ font-size:13px; color:#909399; }}
  .metric-value {{ font-size:20px; font-weight:700; line-height:1.3; color:#303133; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .metric-sub {{ font-size:12px; color:#c0c4cc; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }}
  .card {{ background:#fff; border-radius:12px; padding:18px; box-shadow:0 2px 8px rgba(0,0,0,.05); }}
  .card h3 {{ font-size:15px; font-weight:600; margin-bottom:10px; color:#303133; }}
  .chart {{ width:100%; height:300px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ padding:9px 12px; border-bottom:1px solid #ebeef5; text-align:left; }}
  th {{ background:#f5f7fa; color:#606266; font-weight:600; }}
  tr:hover td {{ background:#fafcff; }}
  .footer {{ text-align:center; color:#c0c4cc; font-size:12px; margin-top:24px; }}
  .ai-card {{ margin-bottom:16px; border-left:4px solid #409EFF; }}
  .ai-badge {{ font-size:11px; color:#409EFF; background:#ecf5ff; border-radius:10px; padding:2px 8px; vertical-align:2px; margin-left:6px; font-weight:400; }}
  .ai-list {{ margin:0; padding-left:4px; }}
  .ai-list li {{ font-size:13.5px; line-height:1.9; color:#303133; padding-left:10px; position:relative; }}
  .ai-list li::before {{ content:'•'; color:#409EFF; position:absolute; left:0; }}
  .ai-list li.ai-h {{ font-weight:600; color:#1f3a68; }}
  @media print {{ body {{ background:#fff; padding:12px; }} .card,.metric-card {{ box-shadow:none; }} }}
</style>
</head>
<body>
  <div class="head">
    <div><h1>IP 资产全景看板 · {year} 年度</h1><div class="sub">专利 · 商标 · 奖金 · 年费 一体化数据汇报</div></div>
    <div class="date">生成时间：{date.today().isoformat()}</div>
  </div>

  <div class="metric-row">
    {metric_cards}
  </div>

{charts_html}
{batch_block}
{agency_block}
{ai_html}
  <div class="footer">IP 管理系统 · 数据来源：专利/商标/奖金/年费模块 · 仅部门内部使用</div>

<script>
var D = {payload_json};
var COLORS = ['#409EFF','#67C23A','#E6A23C','#F56C6C','#8E44AD','#00B4D8','#FF7F50'];
function pie(el, data, money) {{
  data = data || {{}};
  var arr = Object.keys(data).filter(function(k){{ return data[k] > 0; }}).map(function(k){{ return {{name:k, value:data[k]}}; }});
  var c = echarts.init(document.getElementById(el));
  c.setOption({{
    color: COLORS,
    tooltip: {{ trigger:'item', formatter: function(p){{ return p.name + ': ' + (money ? '¥' : '') + p.value + (money ? '' : ' 件') + ' (' + p.percent + '%)'; }} }},
    legend: {{ bottom: 0, type:'scroll', textStyle:{{ fontSize:10 }} }},
    series: [{{ type:'pie', radius:['38%','66%'], center:['50%','44%'],
      itemStyle: {{ borderRadius:6, borderColor:'#fff', borderWidth:2 }},
      label: {{ formatter: function(p){{ var nm = p.name.length > 12 ? p.name.slice(0, 11) + '…' : p.name; return nm + '\\n' + (money ? '¥' : '') + p.value; }}, fontSize:11 }},
      labelLayout: {{ hideOverlap:true }},
      data: arr }}]
  }});
  return c;
}}
var charts = [];
function reg(c) {{ if (c) charts.push(c); }}
reg(pie('c1', D.patentType, false));
(function() {{
  var el = document.getElementById('c2');
  if (!el) return;
  var c = echarts.init(el);
  c.setOption({{
    tooltip: {{ trigger:'axis' }}, grid: {{ left:'3%', right:'4%', bottom:'3%', top:'8%', containLabel:true }},
    xAxis: {{ type:'category', data: D.patentTrend.map(function(t){{ return t.year + '年'; }}) }},
    yAxis: {{ type:'value', minInterval:1 }},
    series: [{{ type:'line', smooth:true, data: D.patentTrend.map(function(t){{ return t.count; }}),
      symbolSize:8, itemStyle:{{ color:'#409EFF' }}, areaStyle:{{ color:'rgba(64,158,255,.12)' }},
      label:{{ show:true, position:'top' }} }}]
  }});
  reg(c);
}})();
reg(pie('c3', D.tmStatus, false));
(function() {{
  var el = document.getElementById('c4');
  if (!el) return;
  var c = echarts.init(el);
  c.setOption({{
    tooltip: {{ trigger:'axis', formatter: function(p){{ return p[0].axisValue + '年: ¥' + p[0].value.toLocaleString(); }} }},
    grid: {{ left:'3%', right:'4%', bottom:'3%', top:'8%', containLabel:true }},
    xAxis: {{ type:'category', data: D.bonusYear.map(function(t){{ return t.year + '年'; }}) }},
    yAxis: {{ type:'value' }},
    series: [{{ type:'bar', data: D.bonusYear.map(function(t){{ return t.total; }}),
      itemStyle:{{ color:'#E6A23C', borderRadius:[4,4,0,0] }}, barWidth:'45%',
      label:{{ show:true, position:'top' }} }}]
  }});
  reg(c);
}})();
(function() {{
  var el = document.getElementById('c5');
  if (!el) return;
  var c = echarts.init(el);
  var top10 = (D.top10 || []).slice().reverse();
  c.setOption({{
    tooltip: {{ trigger:'axis', formatter: function(p){{ return p[0].name + ': ¥' + Number(p[0].value).toLocaleString(); }} }},
    grid: {{ left:8, right:60, bottom:8, top:8, containLabel:true }},
    xAxis: {{ type:'value' }},
    yAxis: {{ type:'category', data: top10.map(function(i){{ return i.name; }}),
      axisLabel: {{ width:90, overflow:'truncate', fontSize:11 }} }},
    series: [{{ type:'bar', data: top10.map(function(i){{ return i.amount; }}),
      itemStyle:{{ color:'#8E44AD', borderRadius:[0,4,4,0] }}, barWidth:'55%',
      label:{{ show:true, position:'right', formatter: function(p){{ return '¥' + Number(p.value).toLocaleString(); }} }} }}]
  }});
  reg(c);
}})();
reg(pie('c6', D.dept, true));
window.addEventListener('resize', function(){{ charts.forEach(function(x){{ x.resize(); }}); }});
</script>
</body>
</html>"""

    fname = f"IP资产全景看板_{year}年.html"
    buf = io.BytesIO(html.encode("utf-8"))
    return StreamingResponse(
        buf,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"},
    )


# ---------------- 图表绘制工具（reportlab） ----------------

try:
    from reportlab.lib import colors
except Exception:
    colors = None

def _chart_colors(n):
    base = [
        colors.HexColor("#409EFF"), colors.HexColor("#67C23A"), colors.HexColor("#E6A23C"),
        colors.HexColor("#F56C6C"), colors.HexColor("#8E44AD"), colors.HexColor("#00B4D8"),
        colors.HexColor("#FF7F50"), colors.HexColor("#909399"), colors.HexColor("#2ECC71"),
        colors.HexColor("#3498DB"), colors.HexColor("#E74C3C"), colors.HexColor("#F1C40F"),
    ]
    return [base[i % len(base)] for i in range(n)]


from reportlab.platypus import Flowable


class _IconBullet(Flowable):
    """PDF 指标卡用的小图标（彩色圆角方块 + 白色首字母）。"""
    def __init__(self, color, letter='', size=10):
        super().__init__()
        self.color = color
        self.letter = letter
        self.size = size

    def wrap(self, availWidth, availHeight):
        return self.size, self.size

    def drawOn(self, canvas, x, y, _sW=0):
        r = 2.5
        canvas.setFillColor(self.color)
        canvas.roundRect(x, y, self.size, self.size, r, fill=1, stroke=0)
        if self.letter:
            canvas.setFillColor(colors.white)
            canvas.setFont(_pdf_font_name(), self.size * 0.55)
            tw = canvas.stringWidth(self.letter, _pdf_font_name(), self.size * 0.55)
            canvas.drawString(x + (self.size - tw) / 2, y + self.size * 0.22, self.letter)


class _ChartFlowable(Flowable):
    """把 reportlab Drawing 包装成 platypus Flowable。必须继承 Flowable，否则在 Table 中会被 toString。"""
    def __init__(self, drawing):
        super().__init__()
        self.drawing = drawing
    def wrap(self, availWidth, availHeight):
        return self.drawing.width, self.drawing.height
    def drawOn(self, canvas, x, y, _sW=0):
        self.drawing.drawOn(canvas, x, y)


def _shorten_label(s, max_len=14):
    """PDF 图表标签防截断：超过 max_len 个字符时截断加省略号。"""
    s = str(s or "")
    if len(s) <= max_len:
        return s
    return s[:max_len - 1] + "…"


def _bar_chart(labels, values, title="", width=400, height=200, horizontal=False):
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
    from reportlab.graphics.charts.textlabels import Label
    d = Drawing(width, height)
    if horizontal:
        # 横向条形图：y 轴标签按实际宽度预留（最多 48pt，对应约 12~14 个英文字符），
        # 超出的标签先截断，避免被画布裁切（此前超长部门名被裁成 "BU5-sV" 的问题）
        labels = [_shorten_label(x) for x in labels]
        chart = HorizontalBarChart()
        chart.x, chart.y = 92, 30
        chart.height, chart.width = height - 70, width - 132
        chart.categoryAxis.categoryNames = labels
        chart.valueAxis.valueMin = 0
    else:
        chart = VerticalBarChart()
        chart.x, chart.y = 40, 50
        chart.height, chart.width = height - 90, width - 80
        chart.data = [values]
        chart.categoryAxis.categoryNames = labels
        chart.valueAxis.valueMin = 0
    chart.barWidth = 18
    chart.bars[0].fillColor = colors.HexColor("#409EFF")
    chart.categoryAxis.labels.fontName = _pdf_font_name()
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.labels.fontName = _pdf_font_name()
    chart.valueAxis.labels.fontSize = 8
    d.add(chart)
    if title:
        lab = Label()
        lab.setOrigin(width/2, height-15)
        lab.setText(title)
        lab.fontName = _pdf_font_name()
        lab.fontSize = 11
        lab.fillColor = colors.HexColor("#303133")
        d.add(lab)
    return _ChartFlowable(d)


def _pie_chart(labels, values, title="", width=320, height=220):
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.textlabels import Label
    d = Drawing(width, height)
    pie = Pie()
    # 动态布局：圆直径取高度与宽度的较小者留足边距，左右各留 40% 画布给 sideLabels，
    # 避免长标签（如部门名）被画布裁切
    pie_d = min(height - 55, width * 0.55, 140)
    pie.x = (width - pie_d) / 2
    pie.y = (height - 45 - pie_d) / 2 + 10
    pie.width, pie.height = pie_d, pie_d
    pie.data = values
    pie.labels = [_shorten_label(x, 10) for x in labels]
    pie.sideLabels = True
    pie.slices.strokeWidth = 0.5
    # 饼图切片标签的字体来自 slices 里每个 WedgeProperties.fontName（默认 Helvetica），
    # 不设置的话中文标签会渲染成方块。这里统一套中文字体并缩小字号防重叠。
    fnt = _pdf_font_name()
    for i, c in enumerate(_chart_colors(len(values))):
        pie.slices[i].fillColor = c
        pie.slices[i].fontName = fnt
        pie.slices[i].fontSize = 7.5
    # draw() 按 i % styleCount 循环取样式，把剩余的内置样式对象也补上中文字体
    for i in range(len(values), 7):
        pie.slices[i].fontName = fnt
    d.add(pie)
    if title:
        lab = Label()
        lab.setOrigin(width/2, height-12)
        lab.setText(title)
        lab.fontName = _pdf_font_name()
        lab.fontSize = 11
        lab.fillColor = colors.HexColor("#303133")
        d.add(lab)
    return _ChartFlowable(d)


def _pdf_font_name():
    """返回 reportlab 已注册中文字体名（供图表标签使用）。"""
    from reportlab.pdfbase import pdfmetrics
    if "CJKFont" in pdfmetrics.getRegisteredFontNames():
        return "CJKFont"
    if "STSong-Light" in pdfmetrics.getRegisteredFontNames():
        return "STSong-Light"
    return "Helvetica"


# ---------------- PDF 导出 ----------------

@router.get("/dashboard/pdf")
def export_dashboard_pdf(
    year: int = Query(None),
    modules: str = Query("", description="逗号分隔模块：overview,patent,bonus,fee,system；空=全部"),
    ai: bool = Query(False, description="是否附加 AI 智能分析（调用本地大模型）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user_flexible),
):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    # 注册中文字体（Windows 系统自带微软雅黑 / 宋体）
    font_candidates = [
        ("CJKFont", r"C:\Windows\Fonts\msyh.ttc"),
        ("CJKFont", r"C:\Windows\Fonts\simsun.ttc"),
        ("CJKFont", r"C:\Windows\Fonts\simhei.ttf"),
    ]
    font_registered = False
    for name, path in font_candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                font_registered = True
                break
            except Exception:
                continue
    if not font_registered:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font_name = "STSong-Light"
    else:
        font_name = "CJKFont"

    if not year:
        year = date.today().year
    data = _collect_dashboard_data(year, db)
    o, b = data["overview"], data["bonus"]
    km = b.get("key_metrics", {})
    module_set = _parse_module_selection(modules)
    use_ai = bool(ai)

    def P(text, style):
        return Paragraph(str(text), style)

    st_title = ParagraphStyle("title", fontName=font_name, fontSize=20, leading=28,
                              alignment=TA_CENTER, textColor=colors.HexColor("#1f3a68"))
    st_sub = ParagraphStyle("sub", fontName=font_name, fontSize=10.5, leading=15,
                            alignment=TA_CENTER, textColor=colors.HexColor("#909399"))
    st_h = ParagraphStyle("h", fontName=font_name, fontSize=13, leading=18,
                          textColor=colors.HexColor("#303133"), spaceBefore=6, spaceAfter=4)
    st_cell = ParagraphStyle("cell", fontName=font_name, fontSize=9, leading=12)
    st_small = ParagraphStyle("small", fontName=font_name, fontSize=8.5, leading=11,
                              textColor=colors.HexColor("#c0c4cc"), alignment=TA_CENTER)
    st_ai = ParagraphStyle("ai", fontName=font_name, fontSize=10.5, leading=17,
                           textColor=colors.HexColor("#303133"))

    # 章节号（按实际输出章节动态编号）
    _CN = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
    sec_idx = [0]
    def sec_title(text):
        num = _CN[sec_idx[0]] if sec_idx[0] < len(_CN) else str(sec_idx[0] + 1)
        sec_idx[0] += 1
        return P(f"{num}、{text}", st_h)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm, title=f"IP资产全景看板 {year}年",
    )
    story = []
    story.append(P(f"IP 资产全景看板 · {year} 年度", st_title))
    story.append(Spacer(1, 4 * mm))
    story.append(P("专利 · 商标 · 奖金 · 年费 一体化数据汇报", st_sub))
    story.append(Spacer(1, 2 * mm))
    story.append(P(f"生成时间：{date.today().isoformat()}", st_sub))
    story.append(Spacer(1, 8 * mm))

    # 指标卡（表格形式，按模块筛选）
    pm = o.get("patent", {}); tm = o.get("trademark", {}); fee = o.get("fee", {})
    C_BL = colors.HexColor("#409EFF")
    C_OR = colors.HexColor("#E6A23C")
    C_RE = colors.HexColor("#F56C6C")
    def IC(color, letter): return _IconBullet(color, letter)
    metric_rows = []
    if "overview" in module_set:
        metric_rows.append(
            [IC(C_BL, "专"), "专利总数", f"{pm.get('total',0)} 件", IC(C_OR, "商"), "商标总数", f"{tm.get('total',0)} 件",
             IC(C_RE, "新"), "本年新增", f"专利 {pm.get('new_this_year',0)} / 商标 {tm.get('new_this_year',0)}"])
    if "bonus" in module_set:
        metric_rows.append(
            [IC(C_BL, "奖"), "奖金总额", _fmt_money(km.get("total_amount", 0)), IC(C_OR, "发"), "本年发放", _fmt_money(km.get("this_year_amount", 0)),
             IC(C_RE, "批"), "批次数", f"{km.get('batch_count',0)} 批 / 发明人 {km.get('inventor_count',0)} 人"])
    if "fee" in module_set:
        metric_rows.append(
            [IC(C_BL, "缴"), "待缴年费", f"{fee.get('pending_count',0)} 笔 {_fmt_money(fee.get('pending_amount',0))}",
             IC(C_OR, "累"), "已缴累计", _fmt_money(fee.get("total_paid",0)), IC(C_RE, "年"), "本年已缴", _fmt_money(fee.get("this_year_paid",0))])
    if metric_rows:
        mtable = Table(metric_rows, colWidths=[6*mm, 18*mm, 34*mm, 6*mm, 18*mm, 34*mm, 6*mm, 18*mm, 34*mm])
        mtable.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), font_name),
            ("FONTSIZE", (0,0), (-1,-1), 9.5),
            ("TEXTCOLOR", (1,0), (1,-1), colors.HexColor("#409EFF")),
            ("TEXTCOLOR", (4,0), (4,-1), colors.HexColor("#E6A23C")),
            ("TEXTCOLOR", (7,0), (7,-1), colors.HexColor("#F56C6C")),
            ("ALIGN", (2,0), (2,-1), "RIGHT"),
            ("ALIGN", (5,0), (5,-1), "RIGHT"),
            ("ALIGN", (8,0), (8,-1), "RIGHT"),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dcdfe6")),
            ("BACKGROUND", (0,0), (1,-1), colors.HexColor("#ecf5ff")),
            ("BACKGROUND", (3,0), (4,-1), colors.HexColor("#fdf6ec")),
            ("BACKGROUND", (6,0), (7,-1), colors.HexColor("#fef0f0")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.append(sec_title("核心指标"))
        story.append(mtable)
        story.append(Spacer(1, 6 * mm))

    # 图表：专利类型分布 + 近 5 年趋势（patent 模块）
    if "patent" in module_set:
        story.append(sec_title("专利资产图表"))
        chart_rows = []
        pt_labels = []
        pt_values = []
        for t, v in (pm.get("by_type", {}) or {}).items():
            if v:
                pt_labels.append(t)
                pt_values.append(v)
        if pt_labels:
            chart_rows.append([_pie_chart(pt_labels, pt_values, "专利类型分布", 260, 180),
                               _bar_chart([str(t["year"]) for t in (pm.get("trend_5yr", []) or [])],
                                          [t["count"] for t in (pm.get("trend_5yr", []) or [])],
                                          "近 5 年申请趋势", 260, 180)])
        if chart_rows:
            t = Table(chart_rows, colWidths=[80*mm, 80*mm])
            t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
            story.append(t)
            story.append(Spacer(1, 4 * mm))

    # 图表：发明人 TOP10 + 部门奖金分布（bonus 模块）
    if "bonus" in module_set:
        top10 = b.get("top10_inventors", []) or []
        chart_rows2 = []
        if top10:
            chart_rows2.append([
                _bar_chart([i["name"] for i in top10], [i["amount"] for i in top10],
                           "发明人奖金 TOP10", 260, 180, horizontal=True),
                _pie_chart(list(_top_n_depts(b.get("by_department")).keys()),
                           list(_top_n_depts(b.get("by_department")).values()),
                           "部门奖金分布", 260, 180)
            ])
        if chart_rows2:
            story.append(sec_title("奖金图表"))
            t = Table(chart_rows2, colWidths=[80*mm, 80*mm])
            t.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
            story.append(t)
            story.append(Spacer(1, 4 * mm))

    # 专利与商标分布（表格）（patent 模块）
    if "patent" in module_set:
        dist_rows = [["维度", "类别", "数量"]]
        for t, v in (pm.get("by_type", {}) or {}).items():
            if v:
                dist_rows.append(["专利类型", t, str(v)])
        for s, v in (pm.get("by_status", {}) or {}).items():
            if v:
                dist_rows.append(["专利状态", s, str(v)])
        for s, v in (tm.get("by_status", {}) or {}).items():
            if v:
                dist_rows.append(["商标状态", s, str(v)])
        if len(dist_rows) > 1:
            story.append(sec_title("专利与商标结构"))
            t = Table(dist_rows, colWidths=[30*mm, 40*mm, 30*mm], repeatRows=1)
            t.setStyle(TableStyle([
                ("FONTNAME", (0,0), (-1,-1), font_name),
                ("FONTSIZE", (0,0), (-1,-1), 9),
                ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dcdfe6")),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f5f7fa")),
                ("ALIGN", (2,0), (2,-1), "CENTER"),
            ]))
            story.append(t)
        story.append(Spacer(1, 6 * mm))

    # 年度趋势（overview 模块）
    if "overview" in module_set:
        story.append(sec_title("年度趋势（专利新增 / 奖金发放）"))
        trend_rows = [["年份", "新增专利（件）", "奖金发放（元）"]]
        trend_map = {t["year"]: t["count"] for t in (pm.get("trend_5yr", []) or [])}
        by_year = {t["year"]: t for t in (b.get("by_year", []) or [])}
        all_years = sorted(set(list(trend_map.keys()) + list(by_year.keys())))
        for y in all_years:
            by = by_year.get(y)
            trend_rows.append([str(y), str(trend_map.get(y, 0)),
                               f"{by['total']:,.2f}" if by else "0.00"])
        t = Table(trend_rows, colWidths=[30*mm, 45*mm, 55*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), font_name),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dcdfe6")),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f5f7fa")),
            ("ALIGN", (1,0), (-1,-1), "CENTER"),
        ]))
        story.append(t)
        story.append(Spacer(1, 6 * mm))

    # 发明人 TOP10（bonus 模块）
    if "bonus" in module_set:
        story.append(sec_title("发明人奖金 TOP10"))
        top_rows = [["排名", "姓名", "奖金金额（元）"]]
        for i, inv in enumerate(b.get("top10_inventors", []), 1):
            top_rows.append([str(i), inv["name"], f"{inv['amount']:,.2f}"])
        t = Table(top_rows, colWidths=[18*mm, 55*mm, 50*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), font_name),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dcdfe6")),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f5f7fa")),
            ("ALIGN", (0,0), (0,-1), "CENTER"),
            ("ALIGN", (2,0), (2,-1), "RIGHT"),
        ]))
        story.append(t)
        story.append(Spacer(1, 6 * mm))

    # 部门奖金（bonus 模块）
    if "bonus" in module_set:
        story.append(sec_title("部门奖金分布"))
        dept_rows = [["部门", "奖金金额（元）", "占比"]]
        dept_total = sum((b.get("by_department", {}) or {}).values()) or 1
        for d, v in sorted(_top_n_depts(b.get("by_department"), 10).items(), key=lambda x: -x[1]):
            pct = f"{v / dept_total * 100:.1f}%" if dept_total else "0%"
            dept_rows.append([d, f"{v:,.2f}", pct])
        t = Table(dept_rows, colWidths=[60*mm, 55*mm, 30*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), font_name),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dcdfe6")),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f5f7fa")),
            ("ALIGN", (1,0), (-1,-1), "RIGHT"),
            ("ALIGN", (2,0), (2,-1), "CENTER"),
        ]))
        story.append(t)
        story.append(Spacer(1, 6 * mm))

    # 奖金批次（bonus 模块）
    if "bonus" in module_set:
        story.append(sec_title("奖金批次明细"))
        batch_rows = [["批次", "期间", "条目数", "金额（元）", "状态"]]
        for r in data["batches"]:
            batch_rows.append([r["name"], r["period"], str(r["item_count"]),
                               f"{r['total']:,.2f}", r["status"]])
        t = Table(batch_rows, colWidths=[45*mm, 45*mm, 20*mm, 35*mm, 25*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), font_name),
            ("FONTSIZE", (0,0), (-1,-1), 8.5),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dcdfe6")),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f5f7fa")),
            ("ALIGN", (2,0), (2,-1), "CENTER"),
            ("ALIGN", (3,0), (3,-1), "RIGHT"),
            ("ALIGN", (4,0), (4,-1), "CENTER"),
        ]))
        story.append(t)
        story.append(Spacer(1, 8 * mm))

    # 代理机构（patent 模块）
    if "patent" in module_set:
        story.append(sec_title("代理机构合作统计"))
        agency_rows = [["机构名称", "代理专利", "代理商标", "累计费用（元）"]]
        for a in o.get("agency", []):
            agency_rows.append([a["name"], str(a["patent_count"]),
                                str(a["trademark_count"]),
                                f"{a['total_amount']:,.2f}"])
        t = Table(agency_rows, colWidths=[70*mm, 30*mm, 30*mm, 40*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), font_name),
            ("FONTSIZE", (0,0), (-1,-1), 8.5),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dcdfe6")),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f5f7fa")),
            ("ALIGN", (1,0), (-1,-1), "CENTER"),
            ("ALIGN", (3,0), (3,-1), "RIGHT"),
        ]))
        story.append(t)
        story.append(Spacer(1, 6 * mm))

    # AI 智能分析（可选，覆盖当前选定的数据模块）
    if use_ai:
        ai_lines = _gen_ai_analysis(data, module_set, year)
        if ai_lines:
            story.append(sec_title("AI 智能分析"))
            for j, (txt, _lvl, bold) in enumerate(ai_lines):
                style = ParagraphStyle("ai_h", parent=st_ai, fontSize=12,
                                       leading=18, textColor=colors.HexColor("#1f3a68")) if bold else st_ai
                if j:
                    story.append(Spacer(1, 2 * mm))
                story.append(P(txt, style))
            story.append(Spacer(1, 8 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(P("IP 管理系统 · 数据来源：专利/商标/奖金/年费模块 · 仅部门内部使用", st_small))

    doc.build(story)
    buf.seek(0)
    fname = f"IP资产全景看板_{year}年.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"},
    )


# ---------------- PPT 导出 ----------------

# PPT 模板候选路径（相对路径优先，跨机器部署不断链）。
# 模板为可选项：找不到时自动回退到 python-pptx 默认版式，导出功能不受影响。
PPT_TEMPLATE_CANDIDATES = [
    str(Path(__file__).resolve().parent.parent.parent / "PPT模板.pptx"),
    str(Path(__file__).resolve().parent.parent.parent / "assets" / "PPT模板.pptx"),
]


def _find_template() -> str | None:
    import os
    for p in PPT_TEMPLATE_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def _gen_ai_analysis(data, module_set, year):
    """调用本地大模型，对选定模块生成详细分析（PPT 用纯文本行）。

    - AI 未启用 / 不可达 / 调用失败时静默降级返回 []（不影响导出）。
    - 只输出要点本身，交由 add_content_slide 渲染成「AI 智能分析」页。
    """
    import re
    try:
        from app import ai_bridge
    except Exception:
        return []
    try:
        if not ai_bridge.is_enabled() or not ai_bridge.is_reachable():
            return []
    except Exception:
        return []

    o = data.get("overview", {}) or {}
    b = data.get("bonus", {}) or {}
    km = b.get("key_metrics", {}) or {}
    pm, tm, fee = o.get("patent", {}) or {}, o.get("trademark", {}) or {}, o.get("fee", {}) or {}

    want = module_set or {"overview", "patent", "bonus", "fee", "system"}
    parts = [f"汇报年份：{year}。"]
    if "overview" in want:
        parts.append(
            f"【概览】专利 {pm.get('total', 0)} 件（本年新增 {pm.get('new_this_year', 0)}），"
            f"商标 {tm.get('total', 0)} 件（本年新增 {tm.get('new_this_year', 0)}）；"
            f"奖金累计 {float(km.get('total_amount', 0)):,.0f} 元、本年 {float(km.get('this_year_amount', 0)):,.0f} 元，"
            f"共 {km.get('batch_count', 0)} 个批次、{km.get('inventor_count', 0)} 位发明人；"
            f"年费待缴 {fee.get('pending_count', 0)} 笔合计 {float(fee.get('pending_amount', 0)):,.0f} 元，"
            f"累计已缴 {float(fee.get('total_paid', 0)):,.0f} 元。"
        )
    if "patent" in want:
        by_type = "、".join(f"{t}:{v}" for t, v in (pm.get("by_type") or {}).items() if v)
        by_status = "、".join(f"{s}:{v}" for s, v in (pm.get("by_status") or {}).items() if v)
        trend5 = [f"{t['year']}年{t['count']}件" for t in (pm.get("trend_5yr") or [])]
        parts.append(
            f"【专利】类型分布[{by_type}]；状态分布[{by_status}]；近5年申请趋势[{';'.join(trend5)}]。"
        )
    if "bonus" in want:
        by_year = [f"{t['year']}年{float(t['total']):,.0f}元" for t in (b.get("by_year") or [])]
        top10 = [f"{i['name']}{float(i['amount']):,.0f}元" for i in (b.get("top10_inventors") or [])[:10]]
        by_dept = "、".join(f"{d}:{float(v):,.0f}" for d, v in list(_top_n_depts(b.get("by_department"), 8).items())[:8])
        by_type_b = "、".join(f"{t}:{float(v):,.0f}元" for t, v in (b.get("by_type") or {}).items() if v)
        parts.append(
            f"【奖金】年度趋势[{';'.join(by_year)}]；发明人TOP10[{';'.join(top10)}]；"
            f"部门分布[{by_dept}]；按专利类型[{by_type_b}]。"
        )
    if "fee" in want:
        parts.append(
            f"【年费】待缴 {fee.get('pending_count', 0)} 笔 / {float(fee.get('pending_amount', 0)):,.0f} 元；"
            f"累计已缴 {float(fee.get('total_paid', 0)):,.0f} 元；本年已缴 {float(fee.get('this_year_paid', 0)):,.0f} 元。"
        )

    if len(parts) <= 1:
        return []

    prompt = (
        "你是一名知识产权与研发管理领域的资深分析顾问。下面是一份 IP 资产管理系统按年份统计的数据摘要，"
        "请基于这些数据写一段专业、严谨、有洞察力的中文分析，用于年度汇报 PPT 的『AI 智能分析』页。\n"
        "要求：\n"
        "1. 总字数控制在 320 字以内；\n"
        "2. 分 4-6 条要点，每条一行，每行以『• 』开头，单条不超过 2 行；\n"
        "3. 必须包含：① 对整体资产/奖金/年费趋势的判断；② 2-3 个最值得关注的结论或亮点；"
        "③ 1-2 条可落地的管理建议；④ 用数据支撑观点（直接引用上面数字，不要编造数据）；\n"
        "4. 语言简练、商务化，避免空话套话，不要『根据数据』『综上所述』等冗余连接词；\n"
        "5. 只输出这些要点本身，不要标题、前言、结尾寒暄或额外说明。\n\n"
        "数据摘要：\n" + "\n".join(parts)
    )
    try:
        # 注意：本地模型是推理型（sglang/Qwen），max_tokens 过小会被思考占用 → 返回空内容。
        # 实测：分析类 prompt 需 8192 才稳定产出（4096 对较长 prompt 仍可能为空）。
        text = ai_bridge.chat(
            [{"role": "system", "content": "你是 IP 资产管理数据分析专家，严格遵循用户给定格式输出。"},
             {"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=8192, timeout=180,
        )
        if not text or not text.strip():
            return []
    except Exception:
        return []

    text = (text or "").strip()
    if not text:
        return []
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        line = re.sub(r"^[•·\-\*]+\s*", "• ", line)
        lines.append((line, 1, False))
    if not lines:
        return []
    return [("AI 解读（本地大模型生成）", 0, True)] + lines[:12]


@router.get("/dashboard/ppt")
def export_dashboard_ppt(
    year: int = Query(None),
    modules: str = Query("", description="逗号分隔模块：overview,patent,bonus,fee,system；空=全部"),
    ai: bool = Query(False, description="是否生成 AI 分析页（调用本地大模型）"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user_flexible),
):
    """按 PPT 模板版式生成 IP 汇报 PPT。

    模板页结构（14 页）：
      0 标题幻灯片(封面) / 4 节标题 / 5 内容(标题+副标题+正文)
      8 三栏文本 / 11 空白(标题+正文) / 13 Ending(致谢)
    生成时复制模板 → 保留封面/节标题/致谢 → 按版式填充数据页。
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import PP_PLACEHOLDER
    from pptx.chart.data import ChartData
    from pptx.enum.chart import XL_CHART_TYPE

    if not year:
        year = date.today().year
    data = _collect_dashboard_data(year, db)
    o, b = data["overview"], data["bonus"]
    km = b.get("key_metrics", {})
    pm, tm, fee = o.get("patent", {}), o.get("trademark", {}), o.get("fee", {})

    # 模块选择：空/未指定 = 全部；否则按逗号分隔的白名单取交集
    module_set = _parse_module_selection(modules)
    use_ai = bool(ai)

    # 重要：python-pptx 的 add_slide 用 len(sldIdLst)+1 推导新页 partname，
    # 若「先删模板页再新增」会出现 partname 重名导致 PPT 损坏。
    # 因此顺序固定为：先追加数据页（编号 15+）→ 再清理模板示例页。
    tmpl = _find_template()
    if tmpl:
        prs = Presentation(tmpl)
        layouts = {l.name: l for l in prs.slide_layouts}
        cover = prs.slides[0]     # 模板封面（标题幻灯片版式）
        ending = prs.slides[13]   # 模板致谢页（Ending 版式）
        n_original = len(prs.slides)
    else:
        # 无模板 → 空白 16:9
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        layouts = {}
        blank = prs.slide_layouts[6]
        cover = prs.slides.add_slide(blank)
        ending = prs.slides.add_slide(blank)
        n_original = len(prs.slides)

    # ---------- 填充封面 ----------
    def fill_ph(slide, mapping_by_idx):
        """mapping: placeholder idx -> (text, size_pt|None, color|None)。返回是否命中占位符。"""
        hit = False
        for idx, spec in mapping_by_idx.items():
            for ph in slide.placeholders:
                if ph.placeholder_format.idx == idx:
                    hit = True
                    text, size, color, align = spec
                    ph.text = ""
                    tf = ph.text_frame
                    tf.word_wrap = True
                    lines = text.split("\n")
                    for j, line in enumerate(lines):
                        p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                        if align:
                            p.alignment = align
                        r = p.add_run()
                        r.text = line
                        if size:
                            r.font.size = Pt(size)
                        if color:
                            r.font.color.rgb = color
                    break
        return hit

    # 模板封面实际 idx：0=标题 / 1=副标题 / 16=文本占位符
    filled = fill_ph(cover, {
        0: (f"IP 资产全景汇报 · {year} 年度", 32, RGBColor(0x1F, 0x3A, 0x68), None),
        1: ("专利 · 商标 · 奖金 · 年费 一体化数据管理", 16, RGBColor(0x90, 0x93, 0x99), None),
        16: (f"IP 管理系统 · 部门内部使用 · 生成于 {date.today().isoformat()}", 12, RGBColor(0xC0, 0xC4, 0xCC), None),
    })
    if not filled:
        # 无占位符（降级场景）→ 手工加文本框
        tb = cover.shapes.add_textbox(Inches(0.8), Inches(2.2), Inches(11.7), Inches(2.4))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, (txt, size, color) in enumerate([
            (f"IP 资产全景汇报 · {year} 年度", 34, RGBColor(0x1F, 0x3A, 0x68)),
            ("专利 · 商标 · 奖金 · 年费 一体化数据管理", 16, RGBColor(0x90, 0x93, 0x99)),
            (f"IP 管理系统 · 生成于 {date.today().isoformat()}", 12, RGBColor(0xC0, 0xC4, 0xCC)),
        ]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = txt
            r.font.size = Pt(size)
            r.font.bold = (i == 0)
            r.font.color.rgb = color

    # ---------- 新增数据页（使用「5_自定义版式」：标题+副标题+正文） ----------
    content_layout = None
    for name in ["5_自定义版式", "2_空白", "1_自定义版式"]:
        if name in layouts:
            content_layout = layouts[name]
            break
    if content_layout is None:
        # 退而求其次：模板首个版式 / 空白版式
        content_layout = prs.slide_layouts[0] if prs.slide_layouts else prs.slide_layouts[6]

    BLUE = RGBColor(0x1F, 0x3A, 0x68)
    GRAY = RGBColor(0x60, 0x62, 0x66)

    def add_content_slide(title, subtitle, lines):
        s = prs.slides.add_slide(content_layout)
        # 按占位符「类型」匹配（不同模板 idx 不同，类型才稳定）
        PH = PP_PLACEHOLDER
        title_set = sub_set = False
        for ph in s.placeholders:
            ptype = ph.placeholder_format.type
            if not title_set and ptype in (PH.TITLE, PH.CENTER_TITLE, PH.VERTICAL_TITLE):
                ph.text = title
                for p in ph.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(24)
                        r.font.bold = True
                        r.font.color.rgb = BLUE
                title_set = True
            elif not sub_set and ptype == PH.SUBTITLE:
                ph.text = subtitle
                for p in ph.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(13)
                        r.font.color.rgb = GRAY
                sub_set = True
        # 正文：取 BODY/OBJECT 类型中面积最大的占位符
        body_ph = None
        body_area = -1
        for ph in s.placeholders:
            ptype = ph.placeholder_format.type
            if ptype in (PH.BODY, PH.OBJECT, PH.VERTICAL_BODY):
                area = (ph.width or 0) * (ph.height or 0)
                if area > body_area:
                    body_ph, body_area = ph, area
        if body_ph is None:
            body_ph = s.shapes.add_textbox(Inches(0.63), Inches(1.7),
                                           Inches(12.1), Inches(5.2))
            tf0 = body_ph.text_frame
            tf0.word_wrap = True
        else:
            tf0 = body_ph.text_frame
            tf0.word_wrap = True
        tf0.clear()
        for i, (txt, lvl, bold) in enumerate(lines):
            p = tf0.paragraphs[0] if i == 0 else tf0.add_paragraph()
            p.level = lvl
            r = p.add_run()
            r.text = txt
            r.font.size = Pt(15 if lvl == 0 else 13)
            r.font.bold = bold
            r.font.color.rgb = BLUE if lvl == 0 else GRAY
            p.space_after = Pt(6)
        return s

    def add_chart_slide(title, chart_type, categories, values, series_name=""):
        """添加一个仅含标题+图表的幻灯片。"""
        PH = PP_PLACEHOLDER
        s = prs.slides.add_slide(content_layout)
        for ph in s.placeholders:
            ptype = ph.placeholder_format.type
            if ptype in (PH.TITLE, PH.CENTER_TITLE, PH.VERTICAL_TITLE):
                ph.text = title
                for p in ph.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(24)
                        r.font.bold = True
                        r.font.color.rgb = BLUE
                break
        # 如正文占位符存在则清空，避免遮挡图表
        for ph in s.placeholders:
            if ph.placeholder_format.type in (PH.BODY, PH.OBJECT, PH.VERTICAL_BODY):
                try:
                    ph.text_frame.clear()
                except Exception:
                    pass
        chart_data = ChartData()
        chart_data.categories = categories
        chart_data.add_series(series_name or title, values)
        x, y, cx, cy = Inches(0.8), Inches(1.6), Inches(11.7), Inches(5.2)
        graphic_frame = s.shapes.add_chart(chart_type, x, y, cx, cy, chart_data)
        chart = graphic_frame.chart
        chart.has_legend = True
        chart.legend.include_in_layout = False
        return s

    # 页1：核心指标（overview 模块）
    if "overview" in module_set:
        add_content_slide(
            "核心指标总览", "一、整体数据概览",
            [
                (f"专利总数 {pm.get('total',0)} 件（本年新增 {pm.get('new_this_year',0)}）；"
                 f"商标总数 {tm.get('total',0)} 件（本年新增 {tm.get('new_this_year',0)}）", 0, True),
                (f"奖金累计发放 {_fmt_money(km.get('total_amount',0))}，本年 {_fmt_money(km.get('this_year_amount',0))}；"
                 f"共 {km.get('batch_count',0)} 个批次，覆盖发明人 {km.get('inventor_count',0)} 位", 0, False),
                (f"年费：待缴 {fee.get('pending_count',0)} 笔（{_fmt_money(fee.get('pending_amount',0))}），"
                 f"累计已缴 {_fmt_money(fee.get('total_paid',0))}，本年已缴 {_fmt_money(fee.get('this_year_paid',0))}", 0, False),
                ("专利类型结构：" + "、".join(f"{t} {v} 件" for t, v in (pm.get("by_type") or {}).items() if v), 1, False),
                ("商标状态结构：" + "、".join(f"{s} {v} 件" for s, v in (tm.get("by_status") or {}).items() if v), 1, False),
            ],
        )

    # 页2：专利与商标（patent 模块）
    if "patent" in module_set:
        trend5 = pm.get("trend_5yr", []) or []
        trend_line = "；".join(f"{t['year']}年 {t['count']} 件" for t in trend5)
        add_content_slide(
            "专利与商标资产", "二、申请趋势与结构",
            [
                ("近 5 年专利申请趋势：" + (trend_line or "暂无数据"), 0, True),
                (f"当前在库专利 {pm.get('total',0)} 件、商标 {tm.get('total',0)} 件，"
                 "全部纳入系统台账，含证书/通知书归档与状态跟踪", 0, False),
                ("专利状态分布：" + "、".join(f"{s} {v} 件" for s, v in (pm.get("by_status") or {}).items() if v), 1, False),
                ("商标状态分布：" + "、".join(f"{s} {v} 件" for s, v in (tm.get("by_status") or {}).items() if v), 1, False),
                ("代理机构合作：" + "、".join(f"{a['name']}（专利 {a['patent_count']} / 商标 {a['trademark_count']}）"
                 for a in o.get("agency", [])[:5]) or "无", 1, False),
            ],
        )
        # 图表页：专利类型分布
        pt_items = [(t, v) for t, v in (pm.get("by_type") or {}).items() if v]
        if pt_items:
            add_chart_slide("专利类型分布", XL_CHART_TYPE.PIE,
                            [t for t, _ in pt_items], [v for _, v in pt_items], "件数")
        # 图表页：近 5 年专利申请趋势
        if trend5:
            add_chart_slide("近 5 年专利申请趋势", XL_CHART_TYPE.COLUMN_CLUSTERED,
                            [str(t["year"]) for t in trend5], [t["count"] for t in trend5], "申请量")

    # 页3：奖金（bonus 模块）
    if "bonus" in module_set:
        by_year = b.get("by_year", []) or []
        year_line = "；".join(f"{t['year']}年 {t['total']:,.0f} 元" for t in by_year) or "暂无数据"
        top5 = b.get("top10_inventors", [])[:5]
        top_line = "、".join(f"{i['name']} {i['amount']:,.0f} 元" for i in top5) or "暂无数据"
        dept_sorted = sorted(_top_n_depts(b.get("by_department"), 8).items(), key=lambda x: -x[1])
        dept_line = "、".join(f"{d} {v:,.0f} 元" for d, v in dept_sorted[:6]) or "暂无数据"
        add_content_slide(
            "专利奖金分析", "三、发放金额与结构",
            [
                (f"奖金总额 {_fmt_money(km.get('total_amount',0))}，本年发放 {_fmt_money(km.get('this_year_amount',0))}", 0, True),
                ("年度发放趋势：" + year_line, 0, False),
                ("发明人奖金 TOP5：" + top_line, 0, False),
                ("部门分布：" + dept_line, 1, False),
                ("按专利类型：" + "、".join(f"{t} {v:,.0f} 元" for t, v in (b.get("by_type") or {}).items() if v), 1, False),
            ],
        )
        # 图表页：奖金年度趋势
        if by_year:
            add_chart_slide("奖金年度发放趋势", XL_CHART_TYPE.COLUMN_CLUSTERED,
                            [str(t["year"]) for t in by_year], [round(t["total"], 2) for t in by_year], "金额")
        # 图表页：部门奖金分布
        if dept_sorted:
            add_chart_slide("部门奖金分布", XL_CHART_TYPE.PIE,
                            [d for d, _ in dept_sorted], [round(v, 2) for _, v in dept_sorted], "金额")
        # 图表页：发明人奖金 TOP10
        top10 = b.get("top10_inventors", []) or []
        if top10:
            add_chart_slide("发明人奖金 TOP10", XL_CHART_TYPE.BAR_CLUSTERED,
                            [i["name"] for i in top10], [round(i["amount"], 2) for i in top10], "金额")

    # 页4：年费管理（fee 模块）
    if "fee" in module_set:
        pending_fees = []
        try:
            from app.models import PatentFee, Patent as P2
            pend = db.query(PatentFee).filter(PatentFee.status == "待缴").all()
            for pf in pend[:10]:
                p2 = db.query(P2).filter(P2.id == pf.patent_id).first()
                pending_fees.append(f"{p2.patent_name if p2 else f'专利{pf.patent_id}'} 第{pf.fee_year}年 {_fmt_money(pf.standard_amount)}（{pf.due_date or ''}）")
        except Exception:
            pass
        add_content_slide(
            "年费管理", "四、缴纳状态与规则",
            [
                (f"待缴年费 {fee.get('pending_count',0)} 笔，金额合计 {_fmt_money(fee.get('pending_amount',0))}", 0, True),
                (f"累计已缴 {_fmt_money(fee.get('total_paid',0))}，本年已缴 {_fmt_money(fee.get('this_year_paid',0))}", 0, False),
                ("自动计费引擎：按国知局年费阶梯 + 费减 85% 规则，新增/导入专利自动生成应缴计划", 0, False),
                ("最近待缴清单：" + ("；".join(pending_fees[:6]) if pending_fees else "当前无待缴"), 1, False),
                ("支持 Excel 一键导入历史年费、逐笔标记缴费、上传凭证与备注", 1, False),
            ],
        )

    # AI 智能分析页（可选，调用本地大模型；覆盖当前选定的数据模块）
    if use_ai:
        ai_lines = _gen_ai_analysis(data, module_set, year)
        if ai_lines:
            add_content_slide("AI 智能分析", "AI · 本地大模型生成的详细解读", ai_lines)

    # 页5：系统能力（system 模块）
    if "system" in module_set:
        add_content_slide(
            "系统能力与后续计划", "五、平台化成果",
            [
                ("已上线能力", 0, True),
                ("专利/商标/代理机构/年费/奖金全模块台账管理，Excel 批量导入导出", 1, False),
                ("年费自动计算 + 缴费提醒 + 审计日志留痕", 1, False),
                ("接入本地大模型：AI 助手自然语言查询、政策规则解析", 1, False),
                ("数据看板支持 HTML / PDF / PPT 一键导出", 1, False),
                ("后续计划：部署至服务器供团队全员使用，并接入更多业务数据源", 0, True),
            ],
        )

    # 清理模板示例页：仅保留封面与致谢页
    if tmpl:
        xml = prs.slides._sldIdLst
        for i, sld in enumerate(list(xml)[:n_original]):
            if i not in (0, 13):
                prs.part.drop_rel(sld.rId)   # 断开关系，示例页部件不会被打包
                xml.remove(sld)
        # 把致谢页挪到最末：清理后顺序为 [封面, 致谢, 数据页...]
        entries = list(xml)
        if len(entries) > 2:
            end_entry = entries[1]
            xml.remove(end_entry)
            xml.append(end_entry)
        # 致谢页补一句收尾文案
        try:
            tb = ending.shapes.add_textbox(Inches(4.2), Inches(5.4), Inches(5), Inches(0.8))
            tf = tb.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = f"IP 管理系统 · {year} 年度汇报 · 谢谢"
            r.font.size = Pt(14)
            r.font.color.rgb = GRAY
        except Exception:
            pass

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    fname = f"IP资产全景汇报_{year}年.pptx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"},
    )
