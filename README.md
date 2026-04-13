# 学生多维度能力评估系统 (Student Multi-Dimensional Profile System)

基于 Python、OpenAI GPT-4o 和 CrewAI 的智能化系统，用于全面评估学生的多维度能力，生成个性化的用户画像和能力报告。

## 功能特性

### 多媒体处理
- 支持论文（PDF/DOCX/TXT）、讲演视频（MP4/MOV）、音频录音（MP3/WAV）
- 提取关键帧、转录音频、解析文档内容

### 多智能体评估
- 内容分析师：评估论文深度、创新性
- 表达分析师：评估讲演清晰度、逻辑性
- 技术能力分析师：评估代码/算法
- 批判性思维分析师：评估论证能力
- 使用 CrewAI 编排多个 Agent 协作

### 数据融合
- 整合多个维度的评分，进行加权计算
- 生成最终评分和定性评语

### 数据库持久化
- 存储学生信息、提交记录、评估结果（PostgreSQL + SQLAlchemy）

### 可视化展示
- 雷达图、评分卡片、趋势图（Plotly）
- 生成可导出的用户画像

### API 服务
- FastAPI 提供文件上传、评估启动、结果查询接口

### 前端界面
- Streamlit 简易界面，供学生上传文件、查看报告

## 项目结构

```
student-profiler-system/
├── src/
│   ├── api/              # FastAPI API 服务
│   │   ├── __init__.py
│   │   └── main.py
│   ├── agents/           # 多智能体评估系统
│   │   ├── evaluation_agents.py
│   │   └── crew_manager.py
│   ├── database/         # 数据库模块
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── database_service.py
│   │   └── models.py
│   ├── frontend/         # Streamlit 前端界面
│   │   └── app.py
│   ├── models/           # 数据模型和模式
│   │   └── schemas.py
│   ├── utils/            # 工具函数
│   │   ├── data_fusion.py
│   │   ├── media_processor.py
│   │   ├── text_processor.py
│   │   └── visualization.py
│   ├── config.py         # 配置管理
│   └── main.py           # 主入口
├── alembic/              # 数据库迁移
│   ├── env.py
│   └── script.py.mako
├── uploads/              # 文件上传目录
├── requirements.txt      # 依赖配置
├── .env.example          # 环境变量示例
├── alembic.ini           # Alembic 配置
└── README.md             # 项目文档
```

## 技术栈

- **语言**：Python 3.9+
- **AI 框架**：OpenAI API (GPT-4o, Whisper), CrewAI, LangChain
- **媒体处理**：FFmpeg, PyPDF2, python-docx, librosa
- **数据库**：PostgreSQL, SQLAlchemy, Alembic
- **可视化**：Plotly, Matplotlib
- **后端**：FastAPI, Uvicorn
- **前端**：Streamlit
- **工具**：Git, Docker (可选)

## 安装依赖

1. 克隆项目
```bash
git clone <repository-url>
cd student-profiler-system
```

2. 创建虚拟环境（推荐）
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

## 环境配置

1. 复制 `.env.example` 文件为 `.env`：

```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填写相应的配置信息：

```
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key

# Database Settings
DATABASE_URL=postgresql://username:password@localhost:5432/student_profiler

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=True
```

## 数据库初始化

1. 创建 PostgreSQL 数据库：

```bash
# 使用 psql 命令创建数据库
psql -U postgres -c "CREATE DATABASE student_profiler;"
```

2. 运行数据库迁移：

```bash
# 生成迁移文件
alembic revision --autogenerate -m "Initial migration"

# 执行迁移
alembic upgrade head
```

## 运行项目

### 启动 API 服务

```bash
python src/api/main.py
```

API 服务将在 `http://localhost:8000` 运行，可通过 `http://localhost:8000/docs` 访问 API 文档。

### 启动前端界面

```bash
streamlit run src/frontend/app.py
```

前端界面将在浏览器中打开，默认地址为 `http://localhost:8501`。

## 使用流程

1. **学生管理**：在前端界面添加学生信息
2. **文件上传**：上传评估材料（论文、视频、音频）
3. **评估管理**：启动评估流程
4. **结果查询**：查看评估结果和可视化图表
5. **历史记录**：查看历史评估记录和能力发展趋势

## 评估维度

系统从以下10个维度对学生进行评估：

1. **学术表现** (Academic Performance)
   - 作业质量
   - 考试成绩
   - 项目完成度
   - 学术研究能力

2. **沟通能力** (Communication Skills)
   - 口头表达
   - 书面表达
   - 倾听能力
   - 非语言沟通

3. **领导力** (Leadership)
   - 决策能力
   - 团队激励
   - 目标设定
   - 责任担当

4. **团队协作** (Teamwork)
   - 协作态度
   - 团队贡献
   - 冲突处理
   - 合作精神

5. **创新能力** (Creativity)
   - 创新思维
   - 创意表达
   - 问题创新解决
   - 创新实践

6. **问题解决** (Problem Solving)
   - 问题分析
   - 方案制定
   - 执行能力
   - 结果评估

7. **时间管理** (Time Management)
   - 任务规划
   - 时间分配
   - 效率提升
   - 截止遵守

8. **适应能力** (Adaptability)
   - 环境适应
   - 变化应对
   - 学习适应
   - 压力管理

9. **技术能力** (Technical Skills)
   - 代码质量和规范性
   - 算法设计和效率
   - 技术实现的创新性
   - 问题解决的技术方案
   - 技术文档的完整性

10. **批判性思维** (Critical Thinking)
    - 论证结构的逻辑性
    - 证据的充分性和可靠性
    - 对不同观点的考虑
    - 分析问题的深度和广度
    - 结论的合理性

## API 端点

### 学生管理
- `POST /students` - 创建学生
- `GET /students/{student_id}` - 获取学生信息
- `GET /students` - 获取所有学生
- `PUT /students/{student_id}` - 更新学生信息

### 提交管理
- `POST /submissions` - 创建提交
- `GET /submissions/{submission_id}` - 获取提交信息
- `GET /students/{student_id}/submissions` - 获取学生的所有提交

### 文件管理
- `POST /submissions/{submission_id}/files` - 上传文件
- `GET /submissions/{submission_id}/files` - 获取提交的所有文件

### 评估管理
- `POST /evaluate` - 启动评估
- `GET /evaluations/{evaluation_id}` - 获取评估结果
- `GET /students/{student_id}/evaluations` - 获取学生的所有评估
- `GET /submissions/{submission_id}/evaluation` - 获取提交的评估结果

## 示例代码

### 1. 创建学生

```python
import requests

response = requests.post(
    "http://localhost:8000/students",
    json={
        "student_id": "S001",
        "name": "张三",
        "age": 20,
        "grade": "大三",
        "major": "计算机科学与技术"
    }
)
print(response.json())
```

### 2. 上传文件并评估

```python
import requests

# 创建提交
submission_response = requests.post(
    "http://localhost:8000/submissions",
    json={
        "student_id": "S001",
        "title": "人工智能课程论文",
        "description": "关于深度学习在计算机视觉中的应用"
    }
)
submission_id = submission_response.json()["submission_id"]

# 上传文件
with open("paper.pdf", "rb") as f:
    files = {"file": ("paper.pdf", f, "application/pdf")}
    upload_response = requests.post(
        f"http://localhost:8000/submissions/{submission_id}/files",
        files=files
    )

# 启动评估
evaluation_response = requests.post(
    "http://localhost:8000/evaluate",
    json={"submission_id": submission_id}
)
evaluation_result = evaluation_response.json()
print(evaluation_result)
```

## 配置说明

在 `.env` 文件中可以配置以下参数：

```env
# OpenAI 配置
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=2000

# Database Settings
DATABASE_URL=postgresql://username:password@localhost:5432/student_profiler

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=True

# CrewAI 配置
CREWAI_MAX_ITERATIONS=15
CREWAI_MAX_EXEC_TIME=300
CREWAI_VERBOSE=True

# 处理配置
VIDEO_FRAME_RATE=1
AUDIO_SAMPLE_RATE=16000
MAX_FILE_SIZE_MB=500

# 输出配置
OUTPUT_DIR=uploads
LOG_LEVEL=INFO
```

## 注意事项

1. **OpenAI API Key**：需要在 `.env` 文件中填写有效的 OpenAI API Key，否则评估功能将无法使用。

2. **PostgreSQL 数据库**：需要安装并运行 PostgreSQL 数据库，并创建名为 `student_profiler` 的数据库。

3. **FFmpeg**：处理视频和音频文件需要安装 FFmpeg。

4. **文件上传**：上传的文件会保存在 `uploads` 目录中，请确保该目录存在且有写入权限。

5. **评估时间**：评估过程可能需要较长时间，特别是处理视频和音频文件时，请耐心等待。

## 故障排查

### 常见问题

1. **ImportError**: 确保所有依赖已正确安装
2. **API Key 错误**: 检查 `.env` 文件中的 API Key 是否正确
3. **文件处理失败**: 检查文件格式是否支持，文件是否损坏
4. **评估超时**: 调整 `CREWAI_MAX_EXEC_TIME` 配置
5. **数据库连接失败**: 检查 PostgreSQL 是否运行，连接字符串是否正确
6. **内存不足**: 减少同时处理的文件数量

### 日志查看

查看应用日志：
```bash
tail -f data/output/app.log
```

## 扩展开发

### 添加新的评估维度

1. 在 `src/models/schemas.py` 中添加新的 `EvaluationDimension`
2. 在 `src/agents/evaluation_agents.py` 中创建对应的评估智能体
3. 在 `src/agents/crew_manager.py` 中注册新智能体
4. 在 `src/utils/data_fusion.py` 中更新权重配置

### 添加新的媒体格式支持

1. 在 `src/utils/media_processor.py` 中扩展媒体处理器
2. 添加新的文件类型检测和处理逻辑

### 自定义可视化

1. 在 `src/utils/visualization.py` 中扩展可视化服务
2. 添加新的图表类型或交互功能

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 发送邮件

---

**注意**: 本系统仅用于教育评估目的，请确保遵守相关法律法规和隐私政策。