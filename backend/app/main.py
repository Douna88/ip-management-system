"""FastAPI main application."""
import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers import (
    auth, patent, trademark, agency, dashboard, files,
    bonus, fee_standard, import_export, reports,
    trademark_scope, settings_admin, ai, export, system
)
from app.config import PRODUCTION

app = FastAPI(
    title="IP管理系统",
    description="专利 + 商标 + 代理机构 + 奖金管理",
    version="1.0.0",
    # 生产模式关闭交互式文档，避免接口结构对外暴露
    docs_url=None if PRODUCTION else "/docs",
    redoc_url=None if PRODUCTION else "/redoc",
    openapi_url=None if PRODUCTION else "/openapi.json",
)

# CORS: 开发期放开便于调试；生产模式默认同源部署，仅允许同源访问。
# 若前端单独部署在别的域名，用 CORS_ORIGINS 环境变量指定，多个用逗号分隔。
_cors_env = os.getenv("CORS_ORIGINS", "").strip()
if PRODUCTION:
    _allow_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or []
else:
    _allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(patent.router)
app.include_router(trademark.router)
app.include_router(agency.router)
app.include_router(dashboard.router)
app.include_router(files.router)
app.include_router(bonus.router)
app.include_router(fee_standard.router)
app.include_router(import_export.router)
app.include_router(reports.router)
app.include_router(trademark_scope.router)
app.include_router(settings_admin.router)
app.include_router(ai.router)
app.include_router(export.router)
app.include_router(system.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "IP管理系统"}


# Serve uploaded files (for image preview)
from app.config import UPLOAD_DIR, BASE_DIR
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# ---- Serve built frontend (single-process production deployment) ----
# The frontend is built into backend/static (vite build outDir).
FRONTEND_DIST = BASE_DIR / "static"

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    from fastapi.responses import FileResponse
    from fastapi import HTTPException

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # Let API / uploads / assets / docs routes handle their own 404s.
        if full_path.startswith(("api/", "uploads/", "assets/", "docs", "openapi.json", "redoc")):
            raise HTTPException(status_code=404)
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        raise HTTPException(status_code=404)
