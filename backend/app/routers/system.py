"""System admin router: 清除示例/业务数据。

用途：部署到公司虚拟机、准备导入真实数据前，一键清空演示数据，只保留登录账号。
安全设计：
  1. 执行前自动对当前数据库做一次一致性备份（WAL 安全），存到 backend/backups/
  2. 只删除业务数据行，不删除表结构
  3. 重新创建 admin / user 两个登录账号
  4. 仅管理员可调用
"""
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, SessionLocal, Base
from app.models import (
    SysUser, Employee, Patent, PatentFee, PatentInventor,
    Trademark, Agency, AgencyPriceChange,
    FeeStandard, BonusRule, FileStorage, AuditLog, TrademarkScope,
)
from app.security import get_current_user, hash_password
from app.config import UPLOAD_DIR

router = APIRouter(prefix="/api/system", tags=["system"])

ALL_TABLES = list(Base.metadata.sorted_tables)


def _backup() -> Path:
    backups = Path(__file__).resolve().parent.parent / "backups"
    backups.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = backups / f"before_reset_{ts}.db"
    src = sqlite3.connect(f"file:{engine.url.database}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(str(dst))
    try:
        with dst_conn:
            src.backup(dst_conn)
    finally:
        dst_conn.close()
        src.close()
    return dst


def _clear_uploads() -> int:
    if not UPLOAD_DIR.exists():
        return 0
    count = 0
    for p in UPLOAD_DIR.iterdir():
        if p.is_file():
            p.unlink(); count += 1
        elif p.is_dir():
            shutil.rmtree(p); count += 1
    return count


@router.post("/reset-demo")
def reset_demo(current_user: SysUser = Depends(get_current_user)):
    """清空所有业务数据，仅保留登录账号 admin / user。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    # 1. 备份
    bak = _backup()

    # 2. 确保表存在
    Base.metadata.create_all(bind=engine)

    # 3. 清空所有表（关外键约束后按依赖逆序删除，避免报错）
    sess = SessionLocal()
    try:
        sess.execute(text("PRAGMA foreign_keys=OFF"))
        for table in reversed(ALL_TABLES):
            sess.execute(table.delete())
        sess.execute(text("PRAGMA foreign_keys=ON"))
        sess.commit()
    finally:
        sess.close()

    # 4. 重建登录账号
    db2 = SessionLocal()
    try:
        db2.add(SysUser(
            username="admin", password_hash=hash_password("admin123"),
            display_name="管理员", email="admin@example.com", role="admin", status="active"))
        db2.add(SysUser(
            username="user", password_hash=hash_password("user1234"),
            display_name="部门成员", email="user@example.com", role="member", status="active"))
        db2.commit()
    finally:
        db2.close()

    # 5. 清空上传目录
    up = _clear_uploads()

    return {
        "message": "示例数据已清除，仅保留管理员账号。",
        "backup": str(bak),
        "uploads_removed": up,
        "accounts": ["admin / admin123", "user / user1234"],
    }
