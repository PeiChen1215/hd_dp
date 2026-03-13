@echo off
chcp 65001 >nul
echo ========================================
echo ChronoSync 烟雾测试工具
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python，请确保 Python 已安装并添加到 PATH
    pause
    exit /b 1
)

:: 检查依赖
echo 检查依赖...
python -c "import httpx" >nul 2>&1
if errorlevel 1 (
    echo 安装 httpx...
    pip install httpx -q
)

python -c "import websockets" >nul 2>&1
if errorlevel 1 (
    echo 安装 websockets...
    pip install websockets -q
)

echo ✅ 依赖检查完成
echo.

:: 检查后端服务
echo 检查后端服务是否运行...
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" >nul 2>&1
if errorlevel 1 (
    echo ❌ 后端服务未运行，请先启动后端：
    echo    uvicorn app.main:app --reload
    pause
    exit /b 1
)

echo ✅ 后端服务运行正常
echo.

:: 选择测试类型
:menu
echo 请选择要运行的测试：
echo 1. 基础 API 测试 (smoke_test.py)
echo 2. WebSocket + 同步测试 (smoke_test_sync_ws.py)
echo 3. 运行全部测试
echo 4. 退出
echo.
set /p choice=请输入选项 (1-4): 

if "%choice%"=="1" goto basic
if "%choice%"=="2" goto websocket
if "%choice%"=="3" goto all
if "%choice%"=="4" goto end
goto menu

:basic
echo.
echo ========================================
echo 运行基础 API 测试...
echo ========================================
python smoke_test.py
pause
goto menu

:websocket
echo.
echo ========================================
echo 运行 WebSocket + 同步测试...
echo ========================================
python smoke_test_sync_ws.py
pause
goto menu

:all
echo.
echo ========================================
echo 运行基础 API 测试...
echo ========================================
python smoke_test.py
if errorlevel 1 (
    echo ❌ 基础测试失败，跳过后续测试
    pause
    goto menu
)

echo.
echo ========================================
echo 运行 WebSocket + 同步测试...
echo ========================================
python smoke_test_sync_ws.py
pause
goto menu

:end
echo 再见！
