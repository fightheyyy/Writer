# AI Writer - 智能文章生成与编辑系统

基于 ReAct Agent 的智能写作助手，支持文章生成和编辑功能。

## 功能特点

### 1. 生成模式
- 根据用户主题自动搜索相关资料
- ReAct 智能决策是否需要更多资料
- 自动生成高质量文章
- 显示搜索历史

### 2. 编辑模式
- 基于原文和修改要求智能编辑
- Monaco Diff Editor 对比修改
- 可接受或拒绝修改

## 技术栈

### 后端
- FastAPI - 高性能 Web 框架
- OpenRouter - LLM API 服务
- httpx - 异步 HTTP 客户端

### 前端
- React - UI 框架
- Vite - 构建工具
- Monaco Editor - 代码编辑器
- Monaco Diff Editor - 差异对比

## 安装步骤

### 1. 后端安装

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
python setup_env.py
# 然后编辑 .env 文件，填入你的 OpenRouter API Key
```

### 2. 前端安装

```bash
cd frontend
npm install
```

## 配置说明

编辑 `.env` 文件：

```env
# OpenRouter API 配置
OPENROUTER_API_KEY=sk-or-v1-xxxxx  # 你的 API Key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# 模型配置
MODEL_NAME=anthropic/claude-3.5-sonnet

# Agent 配置
MAX_ITERATIONS=5
```

## 运行

### 开发模式

启动后端：
```bash
python run.py
```

启动前端（新终端）：
```bash
cd frontend
npm run dev
```

访问：http://localhost:5173

### 生产模式

构建前端：
```bash
cd frontend
npm run build
```

启动服务：
```bash
python run.py
```

访问：http://localhost:8000

## API 接口

### POST /generate

生成或编辑文章

**请求体：**
```json
{
  "query": "文章主题或修改要求",
  "original_content": "原文（编辑模式需要）",
  "mode": "generate 或 edit",
  "max_iterations": 5
}
```

**响应：**
```json
{
  "content": "生成/编辑后的文章",
  "search_history": [...],
  "mode": "generate 或 edit"
}
```

## 项目结构

```
Writer/
├── main.py              # FastAPI 主服务
├── react_agent.py       # ReAct Agent 核心逻辑
├── rag_tool.py          # RAG 搜索工具
├── config.py            # 配置管理
├── run.py               # 启动脚本
├── requirements.txt     # Python 依赖
├── .env                 # 环境变量
├── .env.example         # 环境变量模板
└── frontend/            # 前端项目
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   │   ├── GenerateMode.jsx
    │   │   └── EditMode.jsx
    │   └── main.jsx
    ├── package.json
    └── vite.config.js
```

## 支持的模型

可以使用 OpenRouter 支持的任何模型，推荐：

- `anthropic/claude-3.5-sonnet` - 高质量输出
- `openai/gpt-4-turbo` - 平衡性能
- `google/gemini-pro` - 成本优化

