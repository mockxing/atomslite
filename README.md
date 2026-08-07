# Atoms Lite

> A Project Driven AI Native Workspace

Atoms Lite 是一个 AI 驱动的 Web 应用构建工作区。用户通过自然语言描述需求，AI 实时执行并生成可交互的 Web 应用，支持持续迭代构建。

## ✨ 核心特性

- **🚀 AI Build** — 描述需求，AI 自动生成完整的 Web 应用
- **📊 Execution Timeline** — 实时观察 AI 执行过程，不是聊天而是 Workflow
- **🔄 Continue Building** — 在已有应用基础上持续修改，而非重新生成
- **💾 Project Persistence** — 执行记录、对话、生成物全部持久化，关闭浏览器恢复如初
- **🎨 Artifact Driven** — 文件树 + 实时预览，支持下载项目
- **🏠 Workspace First** — 左(Execution+Conversation) + 中(Artifact) + 右(Preview) 三栏工作区

## 🏗️ 技术架构

```
├── 前端 (Next.js + Tailwind CSS)
│   ├── / 首页 - 输入需求 + 项目列表
│   └── /workspace/[id] 工作区 - 三栏布局
│       ├── 左: Execution Timeline + Conversation + Prompt 输入
│       ├── 中: Artifact 文件查看器（可折叠）+ 下载项目
│       └── 右: Preview (iframe 实时预览，浏览器风格顶栏)
│
├── 后端 (FastAPI + SQLite)
│   ├── /api/projects - Project CRUD
│   ├── /api/conversations - 对话记录
│   ├── /api/artifacts - 生成物管理
│   ├── /api/executions - 执行步骤（持久化）
│   └── /api/build/stream - SSE 流式构建
│
└── AI 层 (OpenAI Compatible API)
    ├── Planner - 需求分析
    ├── Generator - 代码生成
    └── Executor - 执行编排
```

## 🚀 快速开始

### 前置条件

- Node.js 18+
- Python 3.11+
- (可选) OpenAI Compatible API Key

### 1. 启动后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key（不填则使用 Demo 模式）

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 配置环境变量
cp .env.example .env.local

# 启动开发服务器
npm run dev
```

### 3. 访问应用

打开浏览器访问 [http://localhost:3000](http://localhost:3000)

## 🤖 配置 LLM

LLM 配置文件位于 `backend/.env`，修改以下三个变量即可：

```env
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

支持所有 **OpenAI Compatible API**，常见配置示例：

| 服务商 | BASE_URL | MODEL |
|--------|----------|-------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-72B-Instruct` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |

> ⚠️ 修改 `.env` 后需重启后端服务生效。未配置 API Key 时自动使用内置 Demo 模式。

## ⚙️ 环境变量

### 后端 (`backend/.env`)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| OPENAI_API_KEY | OpenAI Compatible API Key | (空，使用 Demo 模式) |
| OPENAI_BASE_URL | API Base URL | https://api.openai.com/v1 |
| OPENAI_MODEL | 模型名称 | gpt-4o |
| DATABASE_URL | 数据库连接 | sqlite+aiosqlite:///./atoms_lite.db |

### 前端 (`frontend/.env.local`)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| NEXT_PUBLIC_API_URL | 后端 API 地址 | http://localhost:8000 |

## 🎯 Demo 模式

当未配置 API Key 时，系统自动进入 Demo 模式，内置了以下模板：

- **Todo App** — 带增删改查、筛选、统计的待办应用
- **Dashboard** — 带指标卡片、柱状图、环形图的分析仪表板
- **Landing Page** — 带 Hero 区域和特性展示的着陆页
- **CRM** — 客户关系管理系统

Demo 模式下 Continue Building 支持添加 Dark Mode 等功能。

## 📦 部署

- **前端**：Vercel（`vercel deploy`）
- **后端**：Railway（`railway up`）

## 📝 开发计划

- [x] Home 首页
- [x] Workspace 三栏布局（左 Execution + 中 Artifact + 右 Preview）
- [x] AI Build (Demo + Real)
- [x] Execution Timeline（持久化）
- [x] Artifact 文件查看器（可折叠）
- [x] Preview (iframe + 浏览器风格顶栏)
- [x] Continue Building
- [x] Project Persistence
- [x] 下载项目
- [ ] 多 Agent 协作
- [ ] Publish & Marketplace
- [ ] Team Workspace
- [ ] Plugin & MCP

## 📄 License

MIT
