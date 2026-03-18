# 快速开始指南

## 5分钟快速上手

### 第一步：安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 第二步：配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 OpenAI API Key
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 第三步：准备测试数据

将你的媒体文件放入 `data/input/` 目录：

- 视频文件：`presentation.mp4`
- 音频文件：`interview.wav`
- 文档文件：`report.pdf`

支持的格式：
- 视频：`.mp4`, `.avi`, `.mov`, `.mkv`
- 音频：`.wav`, `.mp3`, `.flac`, `.aac`
- 文档：`.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`, `.txt`

### 第四步：运行测试

```bash
# 运行基础测试
python tests/test_basic.py
```

### 第五步：开始使用

#### 方式1：使用快速启动脚本

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

#### 方式2：直接运行示例

```bash
# 基础评估示例
python examples/basic_example.py

# 批量评估示例
python examples/batch_example.py
```

#### 方式3：使用命令行工具

```bash
# 评估单个学生
python main.py --mode evaluate \
    --student-id STU001 \
    --name "张三" \
    --grade "大三" \
    --major "计算机科学" \
    --video data/input/presentation.mp4 \
    --audio data/input/interview.wav \
    --document data/input/report.pdf

# 启动交互式仪表板
python main.py --mode dashboard --json-input data/output/evaluation_results.json
```

## 查看结果

评估完成后，在 `data/output/` 目录查看：

- `dimension_scores_*.png`: 维度评分图
- `radar_chart_*.png`: 能力雷达图
- `interactive_dashboard.html`: 交互式仪表板（用浏览器打开）
- `evaluation_results.json`: 评估结果数据

## 常见问题

### 1. API Key 错误

确保 `.env` 文件中的 `OPENAI_API_KEY` 正确，并且账户有足够的额度。

### 2. 依赖安装失败

某些依赖可能需要系统级库：

**Windows:**
- PyAudio: 可能需要安装 Microsoft Visual C++ Build Tools

**Linux:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
```

**Mac:**
```bash
brew install portaudio
pip install pyaudio
```

### 3. 文件处理失败

检查：
- 文件格式是否支持
- 文件是否损坏
- 文件大小是否超过限制（默认500MB）

### 4. 评估超时

在 `.env` 中增加超时时间：
```
CREWAI_MAX_EXEC_TIME=600
```

## 下一步

- 阅读 [README.md](README.md) 了解详细功能
- 查看 [examples/](examples/) 目录学习更多用法
- 自定义评估维度和智能体
- 扩展可视化功能

## 获取帮助

- 查看日志文件：`data/output/app.log`
- 运行测试：`python tests/test_basic.py`
- 提交 Issue 或联系开发团队