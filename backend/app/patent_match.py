"""专利名称匹配工具。

用于「奖金条目 → 专利」的关联匹配，供两个场景复用：
1. 历史奖金数据回填脚本（_devtmp/backfill_bonus_patent.py）
2. Excel 导入时的 patent_id 自动关联（routers/import_export.py）

奖金表里的 patent_name 经常是混合格式，例如：
  - 纯英文名：BU2-Glider-System and Test
  - 中文名 + 英文括注：基于xx的装置（BU5-sMA-RT 方法）
  - 多专利换行拼接：专利A\\n专利B
匹配策略（三级）：
  1) 全名归一化后精确相等
  2) 从奖金名中抽取片段（括号内内容 / 换行、分号切分），片段归一化后精确命中
  3) 双向包含（较短一方占较长方 ≥ 60% 且长度 ≥ 4，防止 "Total" 之类短词误配）
"""
import re

from sqlalchemy.orm import Session

from .models import Patent

# 太短的片段一律不做包含匹配（避免 "Total"、"合计"、"Old rule" 等聚合词误配）
_MIN_CONTAIN_LEN = 4
_CONTAIN_RATIO = 0.6


def _norm(s) -> str:
    """归一化：去所有空白、统一全角→半角括号、转小写。"""
    s = str(s or "")
    s = s.replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", s).lower()


def _extract_candidates(name) -> list:
    """从奖金条目 patent_name 中抽取候选专利名（去重、保序）。"""
    raw = str(name or "")
    out = []
    seen = set()

    def _push(s):
        s = (s or "").strip()
        if not s:
            return
        key = _norm(s)
        if key and key not in seen:
            seen.add(key)
            out.append(s)

    # 整名（去掉全角括注后也保留一份裸名）
    _push(raw)
    _push(re.sub(r"（[^（）]*）", "", raw))

    # 全角括号内的内容（通常是中文专利名）
    for m in re.finditer(r"（([^（）]+)）", raw):
        _push(m.group(1))

    # 半角括号内的内容（英文专利名常见写法）
    for m in re.finditer(r"\(([^()]+)\)", raw):
        _push(m.group(1))

    # 换行 / 分号 / 顿号 / 逗号 切分出的多专利
    for part in re.split(r"[\n;；、\r\t]+", raw):
        _push(part)

    return out


def _load_patents(db: Session):
    """一次性载入全部有效专利，返回 (全名归一化索引, 专利对象列表)。"""
    patents = db.query(Patent).filter(Patent.is_deleted == False).all()
    index = {}
    for p in patents:
        n = _norm(p.patent_name)
        if n:
            index.setdefault(n, p)
    return index, patents


def _contain_match(fragment_n, patents, index) -> Patent | None:
    """双向包含匹配：fragment 与某专利名互相包含且比例达标。"""
    if len(fragment_n) < _MIN_CONTAIN_LEN:
        return None
    best, best_len = None, 0
    for p in patents:
        pn = _norm(p.patent_name)
        if not pn:
            continue
        if fragment_n in pn or pn in fragment_n:
            shorter = min(len(fragment_n), len(pn))
            longer = max(len(fragment_n), len(pn))
            if shorter / longer >= _CONTAIN_RATIO and len(pn) > best_len:
                best, best_len = p, len(pn)
    return best


def match_patent_by_name(db: Session, name) -> Patent | None:
    """按名称匹配专利。无匹配返回 None。"""
    if not str(name or "").strip():
        return None
    index, patents = _load_patents(db)
    for cand in _extract_candidates(name):
        cn = _norm(cand)
        if not cn:
            continue
        p = index.get(cn)
        if p:
            return p
        p = _contain_match(cn, patents, index)
        if p:
            return p
    return None
