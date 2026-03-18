@echo off
chcp 65001 > nul
echo ========================================
echo 学生多维度能力评估系统 - 启动脚本
echo ========================================
echo.

:main_menu
echo [1] 启动前端服务 (Streamlit) - 端口 8501
echo [2] 启动后端服务 (FastAPI) - 端口 8000
echo [3] 同时启动前端和后端服务
echo [4] 停止所有服务
echo [5] 退出
echo.

set /p choice=请选择操作 (1-5): 

if "%choice%"=="1" goto start_frontend
if "%choice%"=="2" goto start_backend
if "%choice%"=="3" goto start_all
if "%choice%"=="4" goto stop_all
if "%choice%"=="5" goto end

echo 无效选择，请重新输入
goto main_menu

:stop_all
echo 正在停止所有服务...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM streamlit.exe /T 2>nul
timeout /t 2 /nobreak >nul
echo 所有服务已停止
goto main_menu

:start_frontend
echo 正在启动前端服务 (Streamlit)...
echo 前端服务将在 http://localhost:8501 上运行
start "前端服务" cmd /k "cd /d %~dp0 && streamlit run src\frontend\app.py --server.port 8501"
echo.
echo 前端服务已启动！
echo 访问地址: http://localhost:8501
echo.
goto main_menu

:start_backend
echo 正在启动后端服务 (FastAPI)...
echo 后端服务将在 http://localhost:8000 上运行
start "后端服务" cmd /k "cd /d %~dp0 && uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"
echo.
echo 后端服务已启动！
echo 访问地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.
goto main_menu

:start_all
echo 正在同时启动前端和后端服务...
echo 前端服务将在 http://localhost:8501 上运行
echo 后端服务将在 http://localhost:8000 上运行
start "前端服务" cmd /k "cd /d %~dp0 && streamlit run src\frontend\app.py --server.port 8501"
timeout /t 3 /nobreak >nul
start "后端服务" cmd /k "cd /d %~dp0 && uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"
echo.
echo 所有服务已启动！
echo 前端地址: http://localhost:8501
echo 后端地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.
goto main_menu

:end
echo 感谢使用！
pause
exit
