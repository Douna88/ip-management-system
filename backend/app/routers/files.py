"""File router: upload, download, list, delete."""
import os
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FileStorage, AuditLog, SysUser
from app.security import get_current_user, get_current_user_flexible
from app.config import UPLOAD_DIR, MAX_FILE_SIZE, ALLOWED_EXTENSIONS, resolve_upload_path

router = APIRouter(prefix="/api/files", tags=["files"])

# File type detection
EXT_TYPE_MAP = {
    "pdf": "pdf", "doc": "word", "docx": "word",
    "xls": "excel", "xlsx": "excel", "ppt": "ppt", "pptx": "ppt",
    "jpg": "image", "jpeg": "image", "png": "image", "svg": "image",
    "zip": "zip", "txt": "other", "csv": "other",
}


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    business_type: str = Query("", description="patent/trademark/agency/bonus/standard"),
    business_id: int = Query(0, description="关联的业务记录ID"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    # Validate extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: .{ext}")

    # Read file
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过100MB限制")

    # Compute checksum
    checksum = hashlib.sha256(content).hexdigest()

    # Save file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = file.filename.replace(" ", "_").replace("/", "_")
    stored_name = f"{timestamp}_{safe_name}"
    stored_path = UPLOAD_DIR / stored_name
    stored_path.write_bytes(content)

    # Determine file type
    file_type = EXT_TYPE_MAP.get(ext, "other")

    # Create record（只存文件名，运行时用 UPLOAD_DIR 解析真实路径，便于迁移）
    f = FileStorage(
        original_name=file.filename,
        storage_path=stored_name,
        file_type=file_type,
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        business_type=business_type or None,
        business_id=business_id or None,
        uploaded_by=current_user.id,
        checksum=checksum,
    )
    db.add(f)
    db.commit()
    db.refresh(f)

    return {
        "id": f.id,
        "original_name": f.original_name,
        "storage_path": stored_name,
        "file_type": f.file_type,
        "file_size": f.file_size,
        "uploaded_at": f.uploaded_at,
        "message": "上传成功"
    }


@router.get("")
def list_files(
    business_type: str = Query(""),
    business_id: int = Query(0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user)
):
    q = db.query(FileStorage)
    if business_type:
        q = q.filter(FileStorage.business_type == business_type)
    if business_id:
        q = q.filter(FileStorage.business_id == business_id)

    total = q.count()
    files = q.order_by(FileStorage.uploaded_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "items": [{
            "id": f.id, "original_name": f.original_name, "file_type": f.file_type,
            "file_size": f.file_size, "business_type": f.business_type,
            "business_id": f.business_id, "uploaded_at": f.uploaded_at
        } for f in files],
        "page": page,
        "page_size": page_size
    }


@router.get("/{fid}/download")
def download_file(
    fid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user_flexible)
):
    f = db.query(FileStorage).filter(FileStorage.id == fid).first()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")

    real = resolve_upload_path(f.storage_path)
    if not real.exists():
        raise HTTPException(status_code=404, detail="文件已被移除")

    return FileResponse(str(real), filename=f.original_name)


@router.delete("/{fid}")
def delete_file(fid: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    f = db.query(FileStorage).filter(FileStorage.id == fid).first()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")

    # Remove physical file
    real = resolve_upload_path(f.storage_path)
    if real.exists():
        real.unlink()

    db.delete(f)
    db.commit()

    return {"message": "文件已删除"}
