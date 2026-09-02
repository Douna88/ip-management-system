"""AI bridge: three-tier switch (none / local / cloud).

统一入口，业务代码只调用 `chat()` / `chat_json()`，无需关心底层是本地还是云端模型。
调用 OpenAI 兼容接口（`/v1/chat/completions`），零第三方依赖（仅标准库 urllib）。
"""
import json
import urllib.request
import urllib.error

from app.config import (
    AI_MODE,
    AI_LOCAL_BASE_URL, AI_LOCAL_API_KEY, AI_LOCAL_MODEL, AI_LOCAL_TIMEOUT,
    AI_CLOUD_BASE_URL, AI_CLOUD_API_KEY, AI_CLOUD_MODEL, AI_CLOUD_TIMEOUT,
)


class AIUnavailable(Exception):
    """AI 功能未启用 / 未配置 / 调用失败。message 为可读原因。"""


def get_mode() -> str:
    return AI_MODE


def is_enabled() -> bool:
    return get_mode() != "none"


# 模型可达性探测结果缓存：避免每次请求都等一次 TCP 超时（离线时会拖到 20 秒以上）
_PROBE_CACHE = {"checked_at": 0.0, "ok": None, "detail": ""}
_PROBE_TTL = 60.0  # 秒


def _tcp_probe(host: str, port: int, timeout: float = 2.0) -> tuple:
    """快速探测模型服务的 TCP 端口是否可达。返回 (ok, detail)。"""
    import socket
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    finally:
        try:
            s.close()
        except Exception:
            pass


def ping(force: bool = False) -> tuple:
    """探测当前启用的模型服务是否可达，结果缓存 60 秒。返回 (ok, detail)。"""
    import time
    from urllib.parse import urlparse

    if not is_enabled():
        return False, "AI 未启用（AI_MODE=none）"

    now = time.time()
    if not force and _PROBE_CACHE["ok"] is not None and (now - _PROBE_CACHE["checked_at"]) < _PROBE_TTL:
        return _PROBE_CACHE["ok"], _PROBE_CACHE["detail"]

    base_url, _, _, _ = _resolve_config()
    try:
        u = urlparse(base_url if "://" in base_url else "http://" + base_url)
        host = u.hostname or ""
        port = u.port or (443 if u.scheme == "https" else 80)
    except Exception as e:  # noqa: BLE001
        return False, f"模型地址解析失败：{e}"

    if not host:
        return False, "模型地址未配置"

    ok, detail = _tcp_probe(host, port, timeout=2.0)
    _PROBE_CACHE.update({"checked_at": now, "ok": ok, "detail": detail})
    return ok, detail


def is_reachable(force: bool = False) -> bool:
    ok, _ = ping(force=force)
    return ok


def get_status() -> dict:
    """返回当前 AI 配置状态（不含密钥，供前端/接口展示）。"""
    return {
        "mode": get_mode(),
        "enabled": is_enabled(),
        "local": {
            "configured": bool(AI_LOCAL_BASE_URL and AI_LOCAL_MODEL),
            "model": AI_LOCAL_MODEL or None,
        },
        "cloud": {
            "configured": bool(AI_CLOUD_BASE_URL and AI_CLOUD_MODEL),
            "model": AI_CLOUD_MODEL or None,
        },
    }


def _resolve_config():
    """根据 mode 返回 (base_url, api_key, model, timeout)。"""
    mode = get_mode()
    if mode == "local":
        return AI_LOCAL_BASE_URL, AI_LOCAL_API_KEY, AI_LOCAL_MODEL, AI_LOCAL_TIMEOUT
    if mode == "cloud":
        return AI_CLOUD_BASE_URL, AI_CLOUD_API_KEY, AI_CLOUD_MODEL, AI_CLOUD_TIMEOUT
    return "", "", "", 0


def _build_url(base_url: str) -> str:
    """拼接 chat/completions 地址，兼容 base_url 带/不带 /v1 的写法。"""
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def chat(messages, temperature=0.2, max_tokens=None, timeout=None) -> str:
    """统一对话调用，返回模型文本内容。

    messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]
    失败时抛 AIUnavailable（含可读原因）。
    """
    if not is_enabled():
        raise AIUnavailable("AI 功能未启用（当前模式：none）。请在环境变量中设置 AI_MODE=local 或 cloud。")

    base_url, api_key, model, default_timeout = _resolve_config()
    if not base_url or not model:
        raise AIUnavailable(f"AI 模式 [{get_mode()}] 已开启，但未配置 base_url / model。")

    url = _build_url(base_url)
    timeout = timeout or default_timeout

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        raise AIUnavailable(f"模型调用失败（HTTP {e.code}）：{detail or e.reason}")
    except urllib.error.URLError as e:
        raise AIUnavailable(f"无法连接模型服务：{e.reason}")
    except Exception as e:  # noqa: BLE001
        raise AIUnavailable(f"模型调用异常：{e}")

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIUnavailable(f"模型返回格式异常：{str(body)[:300]}")
    return content


def chat_json(messages, **kwargs):
    """调用模型并尝试把返回解析为 JSON。失败返回 None（调用方自行降级处理）。"""
    text = chat(messages, **kwargs).strip()
    # 去除可能的 markdown 代码块包裹（```json ... ```）
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return None
