"""Application configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 自动加载 backend/.env（若存在），使 AI 等配置无需每次启动手动带环境变量
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=False)
except Exception:
    pass

# Database: SQLite for dev, switch to PostgreSQL via DATABASE_URL env var
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'ip_system.db'}")

# JWT
_DEFAULT_SECRET = "ip-system-dev-secret-key-change-in-production"


def _resolve_secret_key() -> str:
    """解析 JWT 密钥：环境变量 > backend/.env > 自动生成并写入 .env。

    沿用代码里的默认密钥意味着任何人都能伪造登录令牌直接进系统，
    因此这里在缺失时强制生成一个随机值，而不是退回默认值。
    """
    env_key = (os.getenv("SECRET_KEY") or "").strip()
    if env_key and env_key != _DEFAULT_SECRET:
        return env_key

    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("SECRET_KEY="):
                    v = s.split("=", 1)[1].strip()
                    if v and v != _DEFAULT_SECRET:
                        return v
        except Exception:
            pass

    import secrets
    new_key = secrets.token_urlsafe(48)
    try:
        with env_file.open("a", encoding="utf-8") as f:
            f.write(
                "\n# JWT 签名密钥（首次启动自动生成，请勿泄露给无关人员）\n"
                "# 更换此值会使所有已登录用户失效，需要重新登录\n"
                f"SECRET_KEY={new_key}\n"
            )
    except Exception:
        pass
    return new_key


SECRET_KEY = _resolve_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# File upload
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def resolve_upload_path(storage_path: str) -> Path:
    """把 file_storage.storage_path 解析为真实磁盘路径。

    兼容两种存储格式：
      - 旧数据：存的是绝对路径（如 C:\\...\\uploads\\xxx.png），且该路径仍存在
      - 新数据：只存文件名（相对 UPLOAD_DIR）
    优先按旧绝对路径查找，否则回落到 UPLOAD_DIR / storage_path。
    """
    if not storage_path:
        return UPLOAD_DIR
    p = Path(storage_path)
    if p.is_absolute() and p.exists():
        return p
    cand = UPLOAD_DIR / storage_path
    if cand.exists():
        return cand
    # 都不存在也返回相对路径（调用方自行处理 404）
    return cand

# 服务监听地址与端口（部署时用环境变量覆盖，如 HOST=0.0.0.0 PORT=8080）
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# 生产模式：关闭交互式 API 文档，避免接口细节对外暴露
PRODUCTION = os.getenv("PRODUCTION", "false").strip().lower() in ("1", "true", "yes")

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "svg", "zip", "txt", "csv"
}

# ===== AI service: three-tier switch (none / local / cloud) =====
# none  : AI 功能关闭（默认，本地大模型测试期使用）
# local : 调用内网本地大模型（OpenAI 兼容优先）
# cloud : 调用云端 AI（过渡 / 备用）
AI_MODE = os.getenv("AI_MODE", "none").strip().lower()

# 本地大模型（内网，OpenAI 兼容 /v1/chat/completions 优先）
AI_LOCAL_BASE_URL = os.getenv("AI_LOCAL_BASE_URL", "")
AI_LOCAL_API_KEY = os.getenv("AI_LOCAL_API_KEY", "")
AI_LOCAL_MODEL = os.getenv("AI_LOCAL_MODEL", "")
AI_LOCAL_TIMEOUT = int(os.getenv("AI_LOCAL_TIMEOUT", "120"))

# 云端 AI（过渡 / 备用，同样按 OpenAI 兼容约定）
AI_CLOUD_BASE_URL = os.getenv("AI_CLOUD_BASE_URL", "")
AI_CLOUD_API_KEY = os.getenv("AI_CLOUD_API_KEY", "")
AI_CLOUD_MODEL = os.getenv("AI_CLOUD_MODEL", "")
AI_CLOUD_TIMEOUT = int(os.getenv("AI_CLOUD_TIMEOUT", "120"))
