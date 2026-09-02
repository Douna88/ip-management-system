#!/usr/bin/env bash
# IP 管理系统 - 一键启动（macOS / Linux）
set -e
cd "$(dirname "$0")/backend"

echo "============================================"
echo "   IP 管理系统 - 一键启动"
echo "============================================"
echo

# 1. 检查 Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "[错误] 未检测到 python3，请先安装 Python 3.10+"
    exit 1
fi

# 2. 虚拟环境
if [ ! -f "venv/bin/python" ]; then
    echo "[1/4] 首次运行，正在创建虚拟环境..."
    python3 -m venv venv
fi

# 3. 依赖
echo "[2/4] 检查并安装依赖（首次较慢）..."
./venv/bin/python -m pip install -q -r requirements.txt

# 4. 演示数据
if [ ! -f "ip_system.db" ]; then
    echo "[3/4] 首次运行，正在生成演示数据..."
    ./venv/bin/python seed_demo.py
fi

# 5. 启动
echo "[4/4] 启动服务..."
echo
echo "    访问地址 : http://localhost:8000"
echo "    管理员   : admin / admin123"
echo "    演示账号 : demo  / demo123"
echo
echo "    按 Ctrl+C 停止服务"
echo "============================================"
echo

open http://localhost:8000 2>/dev/null || true
./venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
