"""清空示例/虚拟数据，保留登录账号。

用途：部署到公司前，把开发时的假数据（示例专利、商标、员工等）全部清掉，
      只保留 admin 登录账号，方便你之后导入真实数据。

安全设计：
  1. 执行前自动对当前数据库做一次一致性备份（WAL 安全），存到 backend/backups/
  2. 只删除业务数据行，不删除表结构，也不会把数据库搞坏
  3. 重新创建 admin / user 两个登录账号（密码与全新 init_db 一致）

用法（在 backend 目录下执行）：
    python reset_db.py
"""
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

# 让脚本能 import 到 app 包
BASE_DIR = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(BASE_DIR))

from app.database import engine, SessionLocal, Base
from app.models import (
    SysUser, Employee, Patent, PatentFee, PatentInventor,
    Trademark, Agency, AgencyPriceChange,
    FeeStandard, BonusRule, FileStorage, AuditLog, TrademarkScope,
)
from app.security import hash_password
from app.config import UPLOAD_DIR

ALL_TABLES = list(Base.metadata.sorted_tables)


def confirm() -> bool:
    ans = input("将清空所有业务数据（已自动备份），仅保留登录账号。确认执行请输入 yes：").strip().lower()
    return ans == "yes"


def backup_first() -> Path:
    backups = BASE_DIR / "backups"
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


def clear_uploads():
    if not UPLOAD_DIR.exists():
        return 0
    count = 0
    for p in UPLOAD_DIR.iterdir():
        if p.is_file():
            p.unlink(); count += 1
        elif p.is_dir():
            shutil.rmtree(p); count += 1
    return count


def main():
    if not confirm():
        print("已取消，未做任何改动。")
        return

    # 1. 备份
    bak = backup_first()
    print(f"[1/4] 已备份当前数据 -> {bak}")

    # 2. 确保表存在
    Base.metadata.create_all(bind=engine)
    print("[2/4] 表结构已就绪")

    # 3. 清空所有表（关外键约束后按依赖逆序删除，避免报错）
    db = SessionLocal()
    try:
        db.execute(text("PRAGMA foreign_keys=OFF"))
        for table in reversed(ALL_TABLES):
            db.execute(table.delete())
        db.execute(text("PRAGMA foreign_keys=ON"))
        db.commit()
    finally:
        db.close()
    print(f"[3/4] 已清空 {len(ALL_TABLES)} 张表的业务数据")

    # 4. 重建登录账号
    db = SessionLocal()
    try:
        db.add(SysUser(
            username="admin", password_hash=hash_password("admin123"),
            display_name="管理员", email="admin@example.com", role="admin", status="active"))
        db.add(SysUser(
            username="user", password_hash=hash_password("user1234"),
            display_name="部门成员", email="user@example.com", role="member", status="active"))
        db.commit()
    finally:
        db.close()

    up = clear_uploads()
    print(f"[4/4] 已重建登录账号（admin / user），并清空 uploads 目录 {up} 个文件")

    print("\n完成！现在数据库是干净的，只剩登录账号。")
    print("  登录账号：admin / admin123（建议部署后在「系统设置」里改密码）")
    print("  之后在系统里导入真实数据即可。")


if __name__ == "__main__":
    main()
