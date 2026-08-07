# 构建编排升级方案

## Context

当前 `stream_build_process` 的 5 个步骤中 4 个是 `asyncio.sleep()` 伪装的，只有"Code Generation"做真实工作。本次升级按用户提出的 MVP Runtime 架构，将假执行流改为真实编排管线。

**范围**：仅做编排层，Artifact 仍为单 index.html，多文件改造为后续阶段。

---

## 目标架构

```
User Prompt
      │
      ▼
Requirement Analyzer         ← 真实LLM调用，输出结构化需求
      │
      ▼
Task Planner                 ← 真实LLM调用，输出 Task List
  (输出 Task List + 依赖关系)
      │
      ▼
Execution Scheduler          ← 逐个调度执行，更新 Timeline
  (逐个执行并更新状态)
      │
      ▼
Task Executor (统一入口)     ← 按 task.tool 分发
┌────────────┬──────────────┐
▼            ▼              ▼
LLM Tool    File Writer    Preview Tool   ← 3种工具
│            │              │
└────────────┴──────────────┘
             ▼
      Artifact Manager       ← 版本管理、存储
             ▼
       Project Storage       ← SQLite 持久化
```

### Task 数据结构

每个 Task 包含：
```python
{
    "name": "Analyze Todo Requirements",   # 任务名（显示在 Timeline）
    "tool": "llm",                          # 执行工具：llm / file_writer / preview
    "deps": [],                             # 依赖的前置任务索引（MVP阶段全部顺序执行，预留字段）
    "params": {                             # 传给工具的参数
        "prompt_type": "analysis",          # llm tool 专用：analysis / design / generation / continuation
        "instruction": "Analyze the todo app requirements"
    }
}
```

### Tool 定义

| Tool | 职责 | Demo模式 | AI模式 |
|------|------|----------|--------|
| **LLM Tool** | 调用AI模型生成文本/代码 | 确定性逻辑 + sleep | 真实LLM调用 |
| **File Writer** | 保存Artifact到数据库 | 同AI模式 | 同AI模式 |
| **Preview Tool** | 触发前端刷新预览 | 同AI模式 | 同AI模式 |

---

## 变更文件清单

### 后端（核心变更）

| 文件 | 变更 |
|------|------|
| `backend/app/services/ai_service.py` | **核心重构**：新增 3 个 Prompt、新增 analyze_requirements / plan_tasks / Tool 执行函数、重构 stream_build_process |
| `backend/app/models/models.py` | Execution 表新增 `task_order` 和 `task_type` 字段 |
| `backend/app/models/schemas.py` | 更新 ExecutionResponse，新增 RequirementAnalysis / TaskDefinition Schema |
| `backend/app/routers/build.py` | 小改：build_start 事件 |

### 前端（适配新事件）

| 文件 | 变更 |
|------|------|
| `frontend/src/lib/types.ts` | 新增 PlanEvent / TasksEvent 类型 |
| `frontend/src/app/workspace/[id]/page.tsx` | handleBuild 处理新事件、loadData 去重逻辑调整、Timeline pending 状态 |

---

## 实现步骤

### Step 1：数据库层（~15min）

**`models.py`**：Execution 表新增字段
```python
task_order = Column(Integer, default=0)    # 任务顺序
task_type = Column(String(50), default="") # 任务类型标记
```

**`schemas.py`**：更新 Schema
- ExecutionResponse 新增 `task_order: int = 0`, `task_type: str = ""`
- 新增 `RequirementAnalysis` Schema
- 新增 `TaskDefinition` Schema

删除旧 `.db` 文件让 `create_all` 重建。

### Step 2：AI Service 重构（~2.5h，核心）

**`ai_service.py`** 变更最多，按模块拆分：

#### 2.1 新增 Prompt（3个）

```python
# 需求分析 Prompt — 替代 PLANNER_SYSTEM_PROMPT
ANALYZER_SYSTEM_PROMPT = """
You are a requirement analyzer. Given a user's request, output a JSON analysis:
{
  "app_type": "todo_app | dashboard | landing_page | crm | e_commerce | blog | form_app | data_table | other",
  "core_features": ["3-6 core features"],
  "ui_style": "visual style description",
  "complexity": "simple | moderate | complex",
  "summary": "one-sentence summary"
}
Only output valid JSON, no markdown.
"""

# 任务规划 Prompt — 替代 PLANNER_SYSTEM_PROMPT 的规划部分
TASK_PLANNER_SYSTEM_PROMPT = """
You are a task planner for web app development. Given a requirement analysis, generate a task list in JSON:
{
  "tasks": [
    {
      "name": "short task name (5-8 words)",
      "tool": "llm | file_writer | preview",
      "deps": [],
      "params": {"prompt_type": "analysis|design|generation", "instruction": "..."}
    }
  ]
}
Rules:
1. First task: tool="llm", prompt_type="analysis" — refine requirements
2. Include 1-2 tasks with tool="llm", prompt_type="design" — UI/layout decisions
3. Include exactly ONE task with tool="llm", prompt_type="generation" — full code
4. Last task: tool="file_writer" — save artifact
5. Second-to-last: tool="preview" — assemble preview
6. Total: 4-7 tasks, all sequential (deps=[])
7. Task names should be specific to the app (e.g., "Generate Todo App" not "Code Generation")
Only output valid JSON, no markdown.
"""

# 设计类 Task 的 Prompt
DESIGN_TASK_SYSTEM_PROMPT = """
You are a UI/UX designer. Given the requirement and context, produce a concise design spec.
Describe: layout structure, component hierarchy, key interactions, colors.
Keep output under 200 words. Plain text only, no code.
"""
```

#### 2.2 新增分析/规划函数

```python
async def analyze_requirements(prompt: str) -> dict:
    """Requirement Analyzer: parse user request into structured analysis."""
    if is_demo_mode():
        return get_demo_analysis(prompt)
    # LLM 调用...

async def plan_tasks(analysis: dict) -> list[dict]:
    """Task Planner: generate dynamic task list based on analysis."""
    if is_demo_mode():
        return get_demo_task_plan(analysis)
    # LLM 调用...
```

#### 2.3 新增 Tool 执行函数

```python
async def execute_llm_tool(task: dict, context: dict, prompt: str, existing_code: str | None) -> str:
    """LLM Tool: call AI model based on task params."""
    prompt_type = task["params"].get("prompt_type", "generation")
    if is_demo_mode():
        if prompt_type == "analysis":
            await asyncio.sleep(0.3)
            return f"Requirement confirmed: {context.get('analysis', {}).get('summary', '')}"
        elif prompt_type == "design":
            await asyncio.sleep(0.4)
            return f"Design completed for {task['name']}"
        elif prompt_type in ("generation", "continuation"):
            await asyncio.sleep(1.0)
            if existing_code:
                return get_demo_continue_artifact(prompt, existing_code)
            return get_demo_artifact(prompt)
    # AI模式：根据 prompt_type 选择不同 system prompt...
    # analysis → ANALYZER_SYSTEM_PROMPT（短调用）
    # design → DESIGN_TASK_SYSTEM_PROMPT（短调用）
    # generation → GENERATOR_SYSTEM_PROMPT（长调用）
    # continuation → CONTINUE_SYSTEM_PROMPT（长调用）

async def execute_file_writer_tool(task: dict, context: dict, project_id: str) -> dict:
    """File Writer Tool: save artifact to database."""
    html_content = context.get("generated_code", "")
    if not html_content:
        return {"status": "skipped", "message": "No code to save"}
    # 查询版本号、保存 Artifact、保存 Conversation...
    return {"status": "saved", "filename": "index.html", "version": new_version}

async def execute_preview_tool(task: dict, context: dict) -> dict:
    """Preview Tool: prepare preview data."""
    return {"status": "ready", "content": context.get("generated_code", "")}
```

#### 2.4 重构 stream_build_process

```python
async def stream_build_process(project_id, prompt, existing_code=None):
    # Phase 1: Requirement Analyzer
    yield execution("Requirement Analysis", "running", "Analyzing requirements...")
    analysis = await analyze_requirements(prompt)
    yield {"type": "plan", "analysis": analysis}
    yield execution("Requirement Analysis", "completed", ...)

    # Update project title (first build only)
    ...

    # Phase 2: Task Planner
    yield execution("Task Planning", "running", "Planning tasks...")
    tasks = await plan_tasks(analysis)
    yield {"type": "tasks", "tasks": tasks}
    yield execution("Task Planning", "completed", ...)

    # Phase 3: Execution Scheduler — 逐个执行 Task
    context = {"analysis": analysis, "task_outputs": []}
    for i, task in enumerate(tasks):
        yield execution(task["name"], "running", task["params"].get("instruction", ""))
        await save_execution(task["name"], "running", ..., task_order=i, task_type=task["tool"])

        try:
            if task["tool"] == "llm":
                result = await execute_llm_tool(task, context, prompt, existing_code)
                if task["params"].get("prompt_type") in ("generation", "continuation"):
                    context["generated_code"] = result
            elif task["tool"] == "file_writer":
                result = await execute_file_writer_tool(task, context, project_id)
            elif task["tool"] == "preview":
                result = await execute_preview_tool(task, context)

            context["task_outputs"].append({"task": task["name"], "output": result})
            yield execution(task["name"], "completed", f"{task['name']} complete")

        except Exception as e:
            yield execution(task["name"], "failed", str(e))
            # project status → FAILED
            return

    # Phase 4: 发送 artifact + project_update
    yield {"type": "artifact", "filename": "index.html", "content": context["generated_code"], "version": context.get("artifact_version", 1)}
    yield {"type": "project_update", "status": "READY"}
```

#### 2.5 Demo 模式适配

```python
def get_demo_analysis(prompt: str) -> dict:
    # 基于 app_type 返回预设分析结果
    ...

def get_demo_task_plan(analysis: dict) -> list[dict]:
    # 基于 app_type 返回预设 Task List
    # 每个 Task 有 name/tool/params 字段
    ...
```

#### 2.6 删除旧函数

- 删除 `plan_project()`（被 `analyze_requirements` + `plan_tasks` 替代）
- 删除 `get_demo_plan()`（被 `get_demo_analysis` + `get_demo_task_plan` 替代）
- 保留 `generate_artifact()`、`get_demo_artifact()`、`get_demo_continue_artifact()`（被 LLM Tool 内部调用）

### Step 3：前端适配（~1h）

**`types.ts`**：新增事件类型
```typescript
export type PlanEvent = {
  type: "plan";
  analysis: { app_type: string; core_features: string[]; ui_style: string; complexity: string; summary: string };
};

export type TasksEvent = {
  type: "tasks";
  tasks: Array<{ name: string; tool: string; deps: number[]; params: Record<string, string> }>;
};

export type BuildEvent = ExecutionEvent | ArtifactEvent | ProjectUpdateEvent | PlanEvent | TasksEvent;
```

**`page.tsx`** handleBuild 新增事件处理：
- `tasks` 事件：一次性渲染所有 pending 状态到 Timeline
- `plan` 事件：在 Conversation 中展示分析摘要
- `execution` 事件：更新对应 Task 的 running/completed/failed 状态

**`page.tsx`** loadData 去重逻辑调整：
- 按最新一批 Execution 记录恢复（基于时间窗口，而非 step 名去重）
- 支持 task_order 排序

**`page.tsx`** Timeline pending 状态：
- pending 用空心圆 `Circle` 图标，灰色

### Step 4：Continue Building 适配（~30min）

- `build.py` 传 `existing_code` 到 stream_build_process 不变
- LLM Tool 中 prompt_type="continuation" 时使用 CONTINUE_SYSTEM_PROMPT
- Demo 模式下 `get_demo_continue_artifact()` 正常调用

### Step 5：验证（~30min）

1. 重启后端+前端
2. 新建项目（Demo 模式）→ Timeline 显示动态任务名
3. Continue Building → 任务列表反映修改需求
4. 刷新页面 → Execution 持久化恢复
5. 配置真实 API Key → AI 模式完整流程

---

## SSE 事件时序（新）

```
execution: step="Requirement Analysis" running
plan: {app_type, core_features, ...}
execution: step="Requirement Analysis" completed
  ↓
execution: step="Task Planning" running
tasks: [{name, tool, params}, ...]       ← 前端一次性渲染所有 pending 步骤
execution: step="Task Planning" completed
  ↓
execution: step="Analyze Todo Requirements" running     ← 来自 Task List
execution: step="Analyze Todo Requirements" completed
  ↓
execution: step="Design List & Input Layout" running
execution: step="Design List & Input Layout" completed
  ↓
execution: step="Generate Todo Application" running
execution: step="Generate Todo Application" completed
  ↓
execution: step="Save Artifact" running
execution: step="Save Artifact" completed
  ↓
execution: step="Build Preview" running
artifact: {filename, content, version}
project_update: {status: "READY"}
execution: step="Build Preview" completed
```

---

## 风险与应对

| 风险 | 应对 |
|------|------|
| LLM JSON 输出不稳定 | try/except 兜底，解析失败用默认分析/任务列表 |
| Demo 模式同名 Task 去重 | loadData 按时间窗口取最新一批，不做 step 名全局去重 |
| 上下文累积 prompt 过长 | design 产出限制 ~200 词，总增量 ~500 词 |
| 旧数据库兼容 | 新字段设默认值，旧数据不影响展示 |
