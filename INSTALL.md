# 安装说明

## 已修复的问题

### 1. Whisper 包名错误
**问题**: `whisper-openai>=20230314` 包不存在
**解决**: 更改为 `openai-whisper>=20230314`

### 2. NumPy 版本冲突
**问题**: NumPy 2.0 与 pandas 等包不兼容
**解决**: 限制 NumPy 版本为 `<2.0.0`

### 3. OpenAI API Key 必填
**问题**: 配置文件中 `openai_api_key` 为必填字段，导致测试失败
**解决**: 改为可选字段 `Optional[str] = None`

### 4. EvaluationAgent 导入缺失
**问题**: `crew_manager.py` 中使用了 `EvaluationAgent` 但未导入
**解决**: 添加 `EvaluationAgent` 到导入列表

## 当前系统状态

✅ 所有依赖已正确安装
✅ 所有基础测试通过
✅ 系统配置正确
✅ 8个评估维度已定义
✅ 所有模块可正常导入

## 完整安装步骤

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 OpenAI API Key
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. 运行测试

```bash
py tests/test_basic.py
```

预期输出：
```
============================================================
学生多维度评估系统 - 基础测试
============================================================
测试模块导入...
  ✓ 配置模块导入成功
  ✓ 数据模型导入成功
  ✓ 处理器工厂导入成功
  ✓ CrewAI 管理器导入成功
  ✓ 可视化模块导入成功

测试配置...
  OpenAI 模型: gpt-4o
  温度: 0.7
  最大 tokens: 2000
  输入目录: D:\AGENT\student-profiler-system\data\input
  输出目录: data\output

测试数据模型...
  评估维度数量: 8
    - academic_performance
    - communication_skills
    - leadership
    - teamwork
    - creativity
    - problem_solving
    - time_management
    - adaptability

============================================================
✓ 所有测试通过！系统配置正确。
============================================================
```

## 可选依赖安装

### FFmpeg（用于音频/视频处理）

**Windows:**
1. 下载 FFmpeg: https://ffmpeg.org/download.html
2. 解压到某个目录（如 `C:\ffmpeg`）
3. 将 FFmpeg 的 `bin` 目录添加到系统 PATH

**Linux:**
```bash
sudo apt-get install ffmpeg
```

**Mac:**
```bash
brew install ffmpeg
```

### PyAudio（用于音频录制）

**Windows:**
```bash
pip install pyaudio
```

**Linux:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
```

**Mac:**
```bash
brew install portaudio
pip install pyaudio
```

## 系统要求

- Python 3.8+
- OpenAI API Key
- 足够的磁盘空间（用于存储媒体文件和输出）
- 稳定的网络连接（用于调用 OpenAI API）

## 已安装的主要包

- **AI 框架**: openai, crewai, crewai-tools, langchain
- **数据处理**: pandas, numpy, pydantic
- **媒体处理**: opencv-python, moviepy, pydub, speechrecognition
- **文档处理**: pypdf, python-docx, openpyxl
- **可视化**: matplotlib, seaborn, plotly, streamlit
- **工具**: requests, aiohttp, tenacity, tqdm

## 常见问题

### Q: 测试时出现 FFmpeg 警告
**A**: 这是正常的，不影响核心功能。如需完整音频/视频处理功能，请安装 FFmpeg。

### Q: 如何验证安装是否成功？
**A**: 运行 `py tests/test_basic.py`，如果所有测试通过则安装成功。

### Q: 可以使用其他 OpenAI 模型吗？
**A**: 可以，在 `.env` 文件中修改 `OPENAI_MODEL` 参数，如 `gpt-4`, `gpt-3.5-turbo` 等。

### Q: 系统支持哪些文件格式？
**A**: 
- 视频: .mp4, .avi, .mov, .mkv, .flv, .wmv
- 音频: .wav, .mp3, .flac, .aac, .m4a, .ogg
- 文档: .pdf, .docx, .doc, .xlsx, .xls, .txt

## 下一步

1. 准备测试数据（视频、音频、文档文件）
2. 运行基础示例: `py examples/basic_example.py`
3. 运行批量评估: `py examples/batch_example.py`
4. 启动交互式仪表板: `py main.py --mode dashboard --json-input data/output/evaluation_results.json`

## 获取帮助

- 查看日志: `data/output/app.log`
- 运行测试: `py tests/test_basic.py`
- 查看文档: [README.md](README.md)
- 快速开始: [QUICKSTART.md](QUICKSTART.md)