@echo off
echo ========================================
echo 学生多维度评估系统 - 快速启动
echo ========================================
echo.

REM 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
) else (
    echo 虚拟环境不存在，请先创建虚拟环境并安装依赖
    echo 运行: python -m venv venv
    echo 运行: venv\Scripts\activate
    echo 运行: pip install -r requirements.txt
    pause
    exit /b 1
)

REM 检查环境变量文件
if not exist ".env" (
    echo 警告: .env 文件不存在
    echo 请从 .env.example 复制并配置 OpenAI API Key
    copy .env.example .env
    echo.
    echo 请编辑 .env 文件，填入你的 OpenAI API Key
    pause
)

REM 运行基础测试
echo.
echo 运行基础测试...
python tests\test_basic.py
if errorlevel 1 (
    echo 测试失败，请检查配置
    pause
    exit /b 1
)

echo.
echo ========================================
echo 选择运行模式:
echo ========================================
echo 1. 基础评估示例
echo 2. 批量评估示例
echo 3. 启动交互式仪表板
echo 4. 运行基础测试
echo 5. 退出
echo ========================================
echo.

set /p choice="请输入选项 (1-5): "

if "%choice%"=="1" (
    echo.
    echo 运行基础评估示例...
    python examples\basic_example.py
) else if "%choice%"=="2" (
    echo.
    echo 运行批量评估示例...
    python examples\batch_example.py
) else if "%choice%"=="3" (
    echo.
    echo 启动交互式仪表板...
    echo 提示: 需要先运行评估生成 JSON 数据
    streamlit run src\visualization\dashboard.py
) else if "%choice%"=="4" (
    echo.
    echo 运行基础测试...
    python tests\test_basic.py
) else if "%choice%"=="5" (
    echo.
    echo 退出
    exit /b 0
) else (
    echo.
    echo 无效选项
)

echo.
pause