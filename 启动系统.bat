@echo off
chcp 65001 >nul
cd /d "%~dp0backend"
title IP 管理系统

echo ============================================
echo    IP 管理系统 - 一键启动
echo ============================================
echo.

REM ---- 1. 检查 Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python。
    echo        请先安装 Python 3.10 及以上版本，安装时勾选 Add to PATH。
    echo.
    pause
    exit /b 1
)

REM ---- 2. 创建虚拟环境（仅首次）----
if not exist "venv\Scripts\python.exe" (
    echo [1/4] 首次运行，正在创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败，请检查 Python 安装。
        pause
        exit /b 1
    )
)

REM ---- 3. 安装依赖 ----
echo [2/4] 检查并安装依赖（首次较慢，约 1-3 分钟）...
venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接。
    pause
    exit /b 1
)

REM ---- 4. 生成演示数据（仅首次）----
if not exist "ip_system.db" (
    echo [3/4] 首次运行，正在生成演示数据...
    venv\Scripts\python.exe seed_demo.py
    if errorlevel 1 (
        echo [错误] 演示数据生成失败。
        pause
        exit /b 1
    )
)

REM ---- 5. 启动服务 ----
echo [4/4] 启动服务...
echo.
echo    访问地址 : http://localhost:8000
echo    管理员   : admin / admin123
echo    演示账号 : demo  / demo123
echo.
echo    关闭此窗口即可停止服务。
echo ============================================
echo.

start "" http://localhost:8000
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
