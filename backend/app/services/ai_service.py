"""AI Service - Requirement Analyzer, Task Planner, Execution Engine, Tools."""
import json
import asyncio
from typing import AsyncGenerator
from openai import AsyncOpenAI

from app.config import get_settings

settings = get_settings()


def is_demo_mode() -> bool:
    """Check if we should use demo/mock mode (no API key configured)."""
    return not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-api-key-here"


def get_ai_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        # Disable SDK-level retries: with the default max_retries=2, a single
        # timeout becomes 3x (e.g. timeout=90 → 270s before the error fires).
        # We want timeouts to fire at the configured value so the build fails
        # fast and the user can retry, rather than hanging for minutes.
        max_retries=0,
    )


# ============ System Prompts ============

ANALYZER_SYSTEM_PROMPT = """You are a requirement analyzer. Given a user's request, output a JSON analysis:
{
  "app_type": "one of: todo_app, dashboard, landing_page, crm, e_commerce, blog, form_app, data_table, calendar, other",
  "core_features": ["list of 3-6 core features extracted from the request"],
  "ui_style": "description of visual style preference",
  "complexity": "simple | moderate | complex",
  "summary": "one-sentence summary of what to build"
}
Only output valid JSON, no markdown or extra text."""

TASK_PLANNER_SYSTEM_PROMPT = """You are a task planner for web app development. Given a requirement analysis, generate a task list in JSON:
{
  "tasks": [
    {
      "name": "short task name (5-8 words)",
      "tool": "llm | file_writer | preview",
      "deps": [],
      "params": {"prompt_type": "analysis | design | generation | continuation", "instruction": "what this task does"}
    }
  ]
}

Rules:
1. First task: tool="llm", params.prompt_type="analysis" - refine requirements
2. Include 1-2 tasks with tool="llm", params.prompt_type="design" - UI/layout decisions
3. Include exactly ONE task with tool="llm", params.prompt_type="generation" - full code generation
4. Then one task: tool="file_writer" - save artifact to storage
5. Last task: tool="preview" - assemble preview
6. Total: 4-7 tasks, all sequential (deps=[])
7. Task names should be specific to the app (e.g., "Generate Todo App" not "Code Generation")

Only output valid JSON, no markdown or extra text."""

DESIGN_TASK_SYSTEM_PROMPT = """You are a UI/UX designer. Given the requirement and context, produce a concise design spec.
Describe: layout structure, component hierarchy, key interactions, colors, typography.
Keep output under 200 words. Plain text only, no code."""

GENERATOR_SYSTEM_PROMPT = """You are an expert frontend developer. Generate a complete, working web application as a single HTML file with embedded CSS and JavaScript.

CRITICAL: Output ONLY the raw HTML code. No explanations, no introductions, no markdown code fences. Start with <!DOCTYPE html> and end with </html>. Nothing else.

Design Requirements:
1. Modern, polished UI - not a basic prototype. Think Apple/Linear/Notion quality.
2. Use a cohesive color palette via CSS variables:
   - Primary: #6366f1 (indigo) with a lighter variant #818cf8
   - Surface: #ffffff, Background: #f8fafc
   - Text: #1e293b (primary), #64748b (secondary)
   - Border: #e2e8f0, Success: #10b981, Danger: #ef4444
3. Use system fonts: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
4. Generous spacing, rounded corners (12-16px), subtle shadows (0 1px 3px rgba(0,0,0,0.1))
5. Smooth transitions on hover/click (0.2s ease)
6. Fully responsive with flexbox/grid
7. Interactive elements must have hover and active states
8. Include empty states and micro-interactions
9. Use SVG icons inline (no external icon libraries)
10. Add a gradient accent where appropriate (e.g., headers, buttons)

Technical Rules:
1. The HTML must be a complete, self-contained document
2. Use vanilla JavaScript for all interactivity
3. You MAY use localStorage for persistence, but MUST wrap all storage access in try/catch and fall back to in-memory state if storage is unavailable (e.g. inside sandboxed previews)
4. Do NOT use any external resources, CDNs, or imports

If this is a CONTINUATION (previous code exists), modify the existing code to add the new features while keeping all existing functionality intact. Do NOT remove existing features."""

CONTINUE_SYSTEM_PROMPT = """You are an AI code generator that MODIFIES existing web applications. You will be given the current application code and a modification request.

CRITICAL: You MUST output a STRUCTURED PATCH, not a full file. Do NOT reproduce the whole HTML document. Output only the section that needs to change, wrapped in the exact markers shown below. This keeps the response small and fast.

Exact output format (one block only):
<<<REPLACE_BEGIN>>>
<ANCHOR: an exact, unique substring copied VERBATIM from the given code, marking the location to change>
<<<REPLACE_ANCHOR_END>>>
<REPLACEMENT: the new/modified code, exactly as it should appear after the change>
<<<REPLACE_END>>>

Rules:
1. The anchor line(s) between `<<<REPLACE_BEGIN>>>` and `<<<REPLACE_ANCHOR_END>>>` MUST be copied EXACTLY (character-for-character) from the provided code, and the anchor MUST be unique in the document. Pick a small, distinctive snippet (a single line or a few consecutive lines) at the exact location to change — e.g. an opening tag, a CSS variable rule, a <script> section, or a specific component's markup. Do NOT add or remove whitespace from the anchor.
2. Do NOT include any marker inside the replacement content. The replacement code goes strictly between `<<<REPLACE_ANCHOR_END>>>` and `<<<REPLACE_END>>>`.
3. Keep ALL code you are NOT changing exactly as-is — only the anchored section is replaced.
4. The replacement must be well-formed and balanced: if your anchor is a whole element (e.g. <div>...</div> or <style>...</style>), the replacement must include both its opening and closing tags.
5. Maintain the existing visual style (colors, fonts, spacing) and only change what's asked.
6. If the user asks to change theme/colors, update the CSS variables or add a style block but keep the layout structure.
7. If the user asks to add a feature, add it in the right place and keep everything else untouched.
8. Output NO explanations, no markdown code fences, no intro/outro text — ONLY the patch block.

Remember: This is a CONTINUATION. The user wants to ITERATE on the existing app, not rebuild it."""


# ============ Demo Mode: Requirement Analyzer ============

def get_demo_analysis(prompt: str) -> dict:
    """Demo mode: deterministic requirement analysis based on keywords."""
    prompt_lower = prompt.lower()

    if "todo" in prompt_lower:
        return {
            "app_type": "todo_app",
            "core_features": ["add todo", "complete todo", "delete todo", "filter todos", "statistics"],
            "ui_style": "clean, minimal with indigo accent",
            "complexity": "simple",
            "summary": "A todo application with CRUD and filtering",
        }
    elif "dashboard" in prompt_lower:
        return {
            "app_type": "dashboard",
            "core_features": ["metric cards", "bar chart", "donut chart", "legend"],
            "ui_style": "modern analytics with card layout",
            "complexity": "moderate",
            "summary": "An analytics dashboard with charts and metrics",
        }
    elif "landing" in prompt_lower or "page" in prompt_lower:
        return {
            "app_type": "landing_page",
            "core_features": ["hero section", "feature grid", "call to action"],
            "ui_style": "gradient hero with clean feature cards",
            "complexity": "simple",
            "summary": "A landing page with hero section and features",
        }
    elif "crm" in prompt_lower:
        return {
            "app_type": "crm",
            "core_features": ["customer list", "contact details", "search", "status tags"],
            "ui_style": "business application with table layout",
            "complexity": "moderate",
            "summary": "A CRM application with customer management",
        }
    else:
        return {
            "app_type": "other",
            "core_features": ["main content", "navigation", "responsive layout"],
            "ui_style": "modern minimal with primary color",
            "complexity": "simple",
            "summary": prompt[:80] if len(prompt) > 80 else prompt,
        }


# ============ Demo Mode: Task Planner ============

def get_demo_task_plan(analysis: dict, is_continuation: bool = False) -> list[dict]:
    """Demo mode: generate task list based on requirement analysis."""
    app_type = analysis.get("app_type", "other")
    summary = analysis.get("summary", "the application")

    # Common task templates per app type - dynamic names reflecting the app
    templates = {
        "todo_app": [
            {"name": "Analyze Todo Requirements", "tool": "llm", "deps": [], "params": {"prompt_type": "analysis", "instruction": "Refine todo app requirements"}},
            {"name": "Design List & Input Layout", "tool": "llm", "deps": [], "params": {"prompt_type": "design", "instruction": "Design todo list and input layout"}},
            {"name": "Generate Todo Application", "tool": "llm", "deps": [], "params": {"prompt_type": "generation", "instruction": "Generate complete todo app HTML"}},
            {"name": "Save Artifact", "tool": "file_writer", "deps": [], "params": {"instruction": "Save index.html to storage"}},
            {"name": "Build Preview", "tool": "preview", "deps": [], "params": {"instruction": "Assemble preview"}},
        ],
        "dashboard": [
            {"name": "Analyze Dashboard Requirements", "tool": "llm", "deps": [], "params": {"prompt_type": "analysis", "instruction": "Refine dashboard requirements"}},
            {"name": "Design Metrics & Charts Layout", "tool": "llm", "deps": [], "params": {"prompt_type": "design", "instruction": "Design metric cards and chart layout"}},
            {"name": "Generate Dashboard Application", "tool": "llm", "deps": [], "params": {"prompt_type": "generation", "instruction": "Generate complete dashboard HTML"}},
            {"name": "Save Artifact", "tool": "file_writer", "deps": [], "params": {"instruction": "Save index.html to storage"}},
            {"name": "Build Preview", "tool": "preview", "deps": [], "params": {"instruction": "Assemble preview"}},
        ],
        "landing_page": [
            {"name": "Analyze Landing Page Requirements", "tool": "llm", "deps": [], "params": {"prompt_type": "analysis", "instruction": "Refine landing page requirements"}},
            {"name": "Design Hero & Features Layout", "tool": "llm", "deps": [], "params": {"prompt_type": "design", "instruction": "Design hero section and feature grid"}},
            {"name": "Generate Landing Page", "tool": "llm", "deps": [], "params": {"prompt_type": "generation", "instruction": "Generate complete landing page HTML"}},
            {"name": "Save Artifact", "tool": "file_writer", "deps": [], "params": {"instruction": "Save index.html to storage"}},
            {"name": "Build Preview", "tool": "preview", "deps": [], "params": {"instruction": "Assemble preview"}},
        ],
        "crm": [
            {"name": "Analyze CRM Requirements", "tool": "llm", "deps": [], "params": {"prompt_type": "analysis", "instruction": "Refine CRM requirements"}},
            {"name": "Design Customer Table Layout", "tool": "llm", "deps": [], "params": {"prompt_type": "design", "instruction": "Design customer list and detail layout"}},
            {"name": "Generate CRM Application", "tool": "llm", "deps": [], "params": {"prompt_type": "generation", "instruction": "Generate complete CRM app HTML"}},
            {"name": "Save Artifact", "tool": "file_writer", "deps": [], "params": {"instruction": "Save index.html to storage"}},
            {"name": "Build Preview", "tool": "preview", "deps": [], "params": {"instruction": "Assemble preview"}},
        ],
    }

    default_plan = [
        {"name": f"Analyze Requirements", "tool": "llm", "deps": [], "params": {"prompt_type": "analysis", "instruction": f"Refine requirements: {summary}"}},
        {"name": "Design Layout & Components", "tool": "llm", "deps": [], "params": {"prompt_type": "design", "instruction": "Design layout and component structure"}},
        {"name": "Generate Application", "tool": "llm", "deps": [], "params": {"prompt_type": "generation", "instruction": "Generate complete application HTML"}},
        {"name": "Save Artifact", "tool": "file_writer", "deps": [], "params": {"instruction": "Save index.html to storage"}},
        {"name": "Build Preview", "tool": "preview", "deps": [], "params": {"instruction": "Assemble preview"}},
    ]

    tasks = templates.get(app_type, default_plan)

    # For Continue Building, use continuation instead of generation
    if is_continuation:
        for t in tasks:
            pt = t.get("params", {}).get("prompt_type", "")
            if pt == "generation":
                t["params"]["prompt_type"] = "continuation"
                t["name"] = t["name"].replace("Generate", "Modify")

    return tasks


# ============ Demo Mode: Artifact Templates ============

def get_demo_artifact(prompt: str) -> str:
    """Generate a demo HTML artifact based on the prompt."""
    prompt_lower = prompt.lower()

    if "todo" in prompt_lower:
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Todo App</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --primary: #6366f1;
            --primary-light: #818cf8;
            --bg: #f8fafc;
            --surface: #ffffff;
            --text: #1e293b;
            --text-secondary: #64748b;
            --border: #e2e8f0;
            --success: #10b981;
            --danger: #ef4444;
        }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
        .container { max-width: 600px; margin: 0 auto; padding: 40px 20px; }
        h1 { font-size: 2rem; font-weight: 700; margin-bottom: 8px; }
        .subtitle { color: var(--text-secondary); margin-bottom: 32px; }
        .input-group { display: flex; gap: 12px; margin-bottom: 24px; }
        input[type="text"] { flex: 1; padding: 12px 16px; border: 2px solid var(--border); border-radius: 12px; font-size: 1rem; outline: none; transition: border-color 0.2s; }
        input[type="text"]:focus { border-color: var(--primary); }
        .btn-add { padding: 12px 24px; background: var(--primary); color: white; border: none; border-radius: 12px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
        .btn-add:hover { background: var(--primary-light); }
        .stats { display: flex; gap: 16px; margin-bottom: 24px; }
        .stat { background: var(--surface); padding: 16px 20px; border-radius: 12px; border: 1px solid var(--border); flex: 1; text-align: center; }
        .stat-number { font-size: 1.5rem; font-weight: 700; color: var(--primary); }
        .stat-label { font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }
        .todo-list { list-style: none; }
        .todo-item { background: var(--surface); padding: 16px 20px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 8px; display: flex; align-items: center; gap: 12px; transition: all 0.2s; }
        .todo-item:hover { border-color: var(--primary-light); box-shadow: 0 2px 8px rgba(99,102,241,0.1); }
        .todo-item.completed .todo-text { text-decoration: line-through; color: var(--text-secondary); }
        .checkbox { width: 22px; height: 22px; border: 2px solid var(--border); border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; flex-shrink: 0; }
        .checkbox.checked { background: var(--success); border-color: var(--success); }
        .checkbox.checked::after { content: "✓"; color: white; font-size: 14px; }
        .todo-text { flex: 1; font-size: 0.95rem; }
        .btn-delete { background: none; border: none; color: var(--text-secondary); cursor: pointer; padding: 4px 8px; border-radius: 6px; transition: all 0.2s; font-size: 1.1rem; }
        .btn-delete:hover { color: var(--danger); background: #fef2f2; }
        .empty { text-align: center; padding: 48px 20px; color: var(--text-secondary); }
        .empty-icon { font-size: 3rem; margin-bottom: 12px; }
        .filters { display: flex; gap: 8px; margin-bottom: 16px; }
        .filter-btn { padding: 6px 14px; border: 1px solid var(--border); background: var(--surface); border-radius: 8px; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }
        .filter-btn.active { background: var(--primary); color: white; border-color: var(--primary); }
    </style>
</head>
<body>
    <div class="container">
        <h1>✨ Todo App</h1>
        <p class="subtitle">Stay organized, get things done</p>
        <div class="input-group">
            <input type="text" id="todoInput" placeholder="What needs to be done?" onkeypress="if(event.key==='Enter')addTodo()">
            <button class="btn-add" onclick="addTodo()">Add</button>
        </div>
        <div class="stats">
            <div class="stat"><div class="stat-number" id="totalCount">0</div><div class="stat-label">Total</div></div>
            <div class="stat"><div class="stat-number" id="activeCount">0</div><div class="stat-label">Active</div></div>
            <div class="stat"><div class="stat-number" id="doneCount">0</div><div class="stat-label">Done</div></div>
        </div>
        <div class="filters">
            <button class="filter-btn active" onclick="setFilter('all',this)">All</button>
            <button class="filter-btn" onclick="setFilter('active',this)">Active</button>
            <button class="filter-btn" onclick="setFilter('completed',this)">Completed</button>
        </div>
        <ul class="todo-list" id="todoList"></ul>
    </div>
    <script>
        let todos = []; let filter = 'all';
        function addTodo() {
            const input = document.getElementById('todoInput');
            const text = input.value.trim();
            if (!text) return;
            todos.push({ id: Date.now(), text, completed: false });
            input.value = '';
            render();
        }
        function toggleTodo(id) { todos = todos.map(t => t.id === id ? {...t, completed: !t.completed} : t); render(); }
        function deleteTodo(id) { todos = todos.filter(t => t.id !== id); render(); }
        function setFilter(f, btn) {
            filter = f;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            render();
        }
        function render() {
            const list = document.getElementById('todoList');
            const filtered = todos.filter(t => filter === 'all' ? true : filter === 'active' ? !t.completed : t.completed);
            if (filtered.length === 0) {
                list.innerHTML = '<div class="empty"><div class="empty-icon">📝</div><p>No todos yet. Add one above!</p></div>';
            } else {
                list.innerHTML = filtered.map(t => '<li class="todo-item ' + (t.completed ? 'completed' : '') + '">' +
                    '<div class="checkbox ' + (t.completed ? 'checked' : '') + '" onclick="toggleTodo(' + t.id + ')"></div>' +
                    '<span class="todo-text">' + t.text + '</span>' +
                    '<button class="btn-delete" onclick="deleteTodo(' + t.id + ')">✕</button></li>').join('');
            }
            document.getElementById('totalCount').textContent = todos.length;
            document.getElementById('activeCount').textContent = todos.filter(t => !t.completed).length;
            document.getElementById('doneCount').textContent = todos.filter(t => t.completed).length;
        }
        render();
    </script>
</body>
</html>'''

    elif "dashboard" in prompt_lower:
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root { --primary: #6366f1; --bg: #f8fafc; --surface: #fff; --text: #1e293b; --text-secondary: #64748b; --border: #e2e8f0; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }
        .header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; }
        .header h1 { font-size: 1.25rem; }
        .content { max-width: 1200px; margin: 0 auto; padding: 32px; }
        .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }
        .metric-card { background: var(--surface); border-radius: 16px; padding: 24px; border: 1px solid var(--border); }
        .metric-label { font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
        .metric-value { font-size: 2rem; font-weight: 700; }
        .metric-change { font-size: 0.85rem; margin-top: 4px; }
        .metric-change.up { color: #10b981; }
        .metric-change.down { color: #ef4444; }
        .chart-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
        .chart-card { background: var(--surface); border-radius: 16px; padding: 24px; border: 1px solid var(--border); }
        .chart-card h3 { margin-bottom: 16px; font-size: 1rem; }
        .bar-chart { display: flex; align-items: flex-end; gap: 12px; height: 200px; }
        .bar { flex: 1; background: var(--primary); border-radius: 8px 8px 0 0; transition: height 0.5s; opacity: 0.8; }
        .bar:hover { opacity: 1; }
        .donut-chart { width: 160px; height: 160px; border-radius: 50%; background: conic-gradient(#6366f1 0% 42%, #818cf8 42% 68%, #c7d2fe 68% 85%, #e2e8f0 85% 100%); margin: 0 auto; position: relative; }
        .donut-hole { width: 80px; height: 80px; background: var(--surface); border-radius: 50%; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.2rem; }
        .legend { margin-top: 16px; }
        .legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 0.85rem; }
        .legend-dot { width: 10px; height: 10px; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="header"><h1>📊 Analytics Dashboard</h1><span style="color:var(--text-secondary)">Last 30 days</span></div>
    <div class="content">
        <div class="metrics">
            <div class="metric-card"><div class="metric-label">Revenue</div><div class="metric-value">$48.2k</div><div class="metric-change up">↑ 12.5%</div></div>
            <div class="metric-card"><div class="metric-label">Users</div><div class="metric-value">2,847</div><div class="metric-change up">↑ 8.2%</div></div>
            <div class="metric-card"><div class="metric-label">Orders</div><div class="metric-value">1,234</div><div class="metric-change down">↓ 3.1%</div></div>
            <div class="metric-card"><div class="metric-label">Conversion</div><div class="metric-value">3.6%</div><div class="metric-change up">↑ 1.2%</div></div>
        </div>
        <div class="chart-grid">
            <div class="chart-card"><h3>Monthly Revenue</h3><div class="bar-chart"><div class="bar" style="height:45%"></div><div class="bar" style="height:62%"></div><div class="bar" style="height:55%"></div><div class="bar" style="height:78%"></div><div class="bar" style="height:70%"></div><div class="bar" style="height:85%"></div><div class="bar" style="height:92%"></div><div class="bar" style="height:88%"></div></div></div>
            <div class="chart-card"><h3>Traffic Sources</h3><div class="donut-chart"><div class="donut-hole">42%</div></div><div class="legend"><div class="legend-item"><div class="legend-dot" style="background:#6366f1"></div>Direct - 42%</div><div class="legend-item"><div class="legend-dot" style="background:#818cf8"></div>Organic - 26%</div><div class="legend-item"><div class="legend-dot" style="background:#c7d2fe"></div>Referral - 17%</div><div class="legend-item"><div class="legend-dot" style="background:#e2e8f0"></div>Social - 15%</div></div></div>
        </div>
    </div>
</body>
</html>'''

    else:
        # Generic landing page template
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{prompt}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{ --primary: #6366f1; --primary-light: #818cf8; --bg: #f8fafc; --surface: #fff; --text: #1e293b; --text-secondary: #64748b; --border: #e2e8f0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
        .hero {{ text-align: center; padding: 100px 20px 80px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%); color: white; }}
        .hero h1 {{ font-size: 3.5rem; font-weight: 800; margin-bottom: 16px; }}
        .hero p {{ font-size: 1.25rem; opacity: 0.9; max-width: 600px; margin: 0 auto 32px; }}
        .btn-hero {{ display: inline-block; padding: 16px 40px; background: white; color: var(--primary); border-radius: 12px; font-weight: 700; font-size: 1.1rem; text-decoration: none; transition: transform 0.2s, box-shadow 0.2s; }}
        .btn-hero:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.15); }}
        .features {{ max-width: 1000px; margin: 0 auto; padding: 80px 20px; }}
        .features h2 {{ text-align: center; font-size: 2rem; margin-bottom: 48px; }}
        .feature-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 32px; }}
        .feature-card {{ background: var(--surface); padding: 32px; border-radius: 16px; border: 1px solid var(--border); transition: transform 0.2s, box-shadow 0.2s; }}
        .feature-card:hover {{ transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }}
        .feature-icon {{ font-size: 2.5rem; margin-bottom: 16px; }}
        .feature-card h3 {{ margin-bottom: 8px; }}
        .feature-card p {{ color: var(--text-secondary); font-size: 0.95rem; line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="hero">
        <h1>{prompt}</h1>
        <p>Built with AI. Powered by Atoms Lite. This is a demo application generated from your description.</p>
        <a href="#features" class="btn-hero">Get Started</a>
    </div>
    <div class="features" id="features">
        <h2>Features</h2>
        <div class="feature-grid">
            <div class="feature-card"><div class="feature-icon">⚡</div><h3>Lightning Fast</h3><p>Built for speed and performance. Get results in seconds, not minutes.</p></div>
            <div class="feature-card"><div class="feature-icon">🎨</div><h3>Beautiful Design</h3><p>Modern, clean interface that looks great on any device.</p></div>
            <div class="feature-card"><div class="feature-icon">🔒</div><h3>Secure</h3><p>Your data is safe with enterprise-grade security.</p></div>
            <div class="feature-card"><div class="feature-icon">📱</div><h3>Responsive</h3><p>Works perfectly on desktop, tablet, and mobile.</p></div>
            <div class="feature-card"><div class="feature-icon">🔌</div><h3>Integrations</h3><p>Connect with your favorite tools and services.</p></div>
            <div class="feature-card"><div class="feature-icon">📊</div><h3>Analytics</h3><p>Track and measure everything that matters to you.</p></div>
        </div>
    </div>
</body>
</html>'''


def get_demo_continue_artifact(prompt: str, existing_code: str) -> str:
    """Modify existing demo code based on continuation prompt."""
    prompt_lower = prompt.lower()

    # Simple continuation: inject a notification banner at the top of body
    if "dark" in prompt_lower or "dark mode" in prompt_lower:
        # Add dark mode toggle to existing code
        dark_mode_script = '''
        <div style="position:fixed;top:16px;right:16px;z-index:9999;">
            <button onclick="toggleDarkMode()" style="padding:8px 16px;background:#6366f1;color:white;border:none;border-radius:8px;cursor:pointer;font-size:0.85rem;">🌙 Dark Mode</button>
        </div>
        <script>
        function toggleDarkMode(){document.body.classList.toggle('dark-mode');const s=document.createElement('style');s.textContent='.dark-mode{background:#1e293b!important;color:#e2e8f0!important}.dark-mode .metric-card,.dark-mode .chart-card,.dark-mode .feature-card,.dark-mode .todo-item,.dark-mode .stat,.dark-mode input{background:#334155!important;color:#e2e8f0!important;border-color:#475569!important}';document.head.appendChild(s)}
        </script>
        '''
        return existing_code.replace("<body>", "<body>" + dark_mode_script)

    # Add a banner for generic modifications
    banner = f'''
    <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;padding:12px 24px;text-align:center;font-size:0.9rem;">
        ✨ Updated: {prompt}
    </div>
    '''
    return existing_code.replace("<body>", "<body>" + banner)


# ============ Demo Mode: Process Docs ============

def get_demo_docs(prompt: str, analysis: dict, tasks: list[dict], is_continuation: bool = False) -> dict:
    """Demo mode: generate architecture.md and progress.md based on analysis and tasks."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    app_type = analysis.get("app_type", "other")
    features = analysis.get("core_features", [])
    ui_style = analysis.get("ui_style", "modern minimal")
    summary = analysis.get("summary", prompt[:80])

    # ===== architecture.md =====
    arch = f"""# Architecture

last_updated: {now}

## Overview

{summary}

## Application Type

{app_type}

## Design Philosophy

- **UI Style**: {ui_style}
- **Architecture**: Single-file HTML application with embedded CSS and JavaScript
- **Rendering**: Client-side rendering with vanilla JS
- **State Management**: In-memory state with localStorage persistence where applicable

## Component Structure

```
App Container
├── Header / Navigation
├── Main Content Area
│   ├── Input / Action Bar
│   ├── Content List / Cards
│   └── Filters / Tabs
├── Modal / Dialog (if needed)
└── Footer / Bottom Nav
```

## Core Features

"""
    for i, f in enumerate(features, 1):
        arch += f"{i}. {f}\n"

    arch += f"""
## Styling Strategy

- CSS Variables for theming (`--primary`, `--bg`, `--surface`, etc.)
- Flexbox / Grid for layout
- Responsive design with media queries
- Smooth transitions and hover effects

## Data Flow

```
User Input → Event Handler → State Update → Re-render → UI Update
```

## Technical Decisions

- **Vanilla JavaScript** (no framework dependency) for portability
- **CSS Variables** for easy theming and dark mode support
- **LocalStorage** for client-side data persistence
- **Single HTML file** for zero-build deployment
"""

    # ===== progress.md =====
    progress = f"""# Progress

last_updated: {now}

## Requirements & Progress

### Requirements Overview

{summary}

**App Type**: {app_type}
**Complexity**: {analysis.get('complexity', 'simple')}
**UI Style**: {ui_style}

### User Stories

"""
    for i, f in enumerate(features, 1):
        # Convert feature to user story
        progress += f"{i}. As a user, I want to {f} so that I can manage my tasks effectively.\n"

    progress += f"""

### Task Breakdown

| ID | Task | Assignee | Status | Deps |
|----|------|----------|--------|------|
"""
    for i, t in enumerate(tasks, 1):
        task_name = t.get("name", f"Task {i}")
        task_tool = t.get("tool", "llm")
        deps = ",".join(str(d) for d in t.get("deps", [])) or "-"
        progress += f"| T{i} | {task_name} | {task_tool} | completed | {deps} |\n"

    progress += f"""

### Progress Log

- `{now}` - Requirement analysis completed: identified {len(features)} core features
- `{now}` - Task planning completed: {len(tasks)} tasks generated
- `{now}` - All tasks executed successfully
- `{now}` - Application generated and ready for preview
"""
    if is_continuation:
        progress += f"- `{now}` - Continue Building: {prompt}\n"

    return {"architecture.md": arch, "progress.md": progress}


# ============ Requirement Analyzer ============

async def analyze_requirements(prompt: str) -> dict:
    """Requirement Analyzer: parse user request into structured analysis."""
    if is_demo_mode():
        await asyncio.sleep(0.4)
        return get_demo_analysis(prompt)

    client = get_ai_client()
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": ANALYZER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=400,
        timeout=120,
    )
    content = response.choices[0].message.content.strip()
    try:
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except json.JSONDecodeError:
        return get_demo_analysis(prompt)


# ============ Task Planner ============

async def plan_tasks(analysis: dict, is_continuation: bool = False) -> list[dict]:
    """Task Planner: generate dynamic task list based on analysis."""
    if is_demo_mode():
        await asyncio.sleep(0.3)
        return get_demo_task_plan(analysis, is_continuation=is_continuation)

    client = get_ai_client()
    analysis_str = json.dumps(analysis, ensure_ascii=False)

    # For continuation, instruct planner to use "continuation" prompt_type
    continuation_note = ""
    if is_continuation:
        continuation_note = "\n\nIMPORTANT: This is a CONTINUE BUILDING request. The code generation task MUST use prompt_type=\"continuation\" (not \"generation\"). The user wants to modify an existing application, not build from scratch."

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": TASK_PLANNER_SYSTEM_PROMPT + continuation_note},
            {"role": "user", "content": f"Requirement analysis:\n{analysis_str}"},
        ],
        temperature=0.7,
        max_tokens=800,
        timeout=120,
    )
    content = response.choices[0].message.content.strip()
    try:
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content)
        tasks = data.get("tasks", [])
        if not tasks:
            return get_demo_task_plan(analysis, is_continuation=is_continuation)
        # Force continuation prompt_type for Continue Building (safety net)
        if is_continuation:
            for t in tasks:
                pt = t.get("params", {}).get("prompt_type", "")
                if pt == "generation":
                    t["params"]["prompt_type"] = "continuation"
        return tasks
    except json.JSONDecodeError:
        return get_demo_task_plan(analysis, is_continuation=is_continuation)


# ============ Incremental Merge (Continue Building patch mode) ============

REPLACE_BEGIN = "<<<REPLACE_BEGIN>>>"
REPLACE_ANCHOR_END = "<<<REPLACE_ANCHOR_END>>>"
REPLACE_END = "<<<REPLACE_END>>>"


def _extract_block(text: str, begin: str, end: str, strip: bool = True) -> str:
    """Extract the substring strictly between `begin` and `end` markers.

    Returns "" if markers are absent or out of order. Used both for the anchor
    (old code) and for the replacement (new code).

    `strip`: for the replacement code we trim stray blank lines around it. For
    the anchor we must NOT strip leading indentation (the anchor is matched
    verbatim against the existing file), so we only drop the single newline that
    sits right after the begin marker and right before the end marker.
    """
    bi = text.find(begin)
    if bi < 0:
        return ""
    bi += len(begin)
    ei = text.find(end, bi)
    if ei < 0:
        return ""
    block = text[bi:ei]
    if strip:
        return block.strip()
    # Keep indentation inside the anchor: drop only the leading/trailing newline
    # that comes from the marker's own line break.
    if block.startswith("\n"):
        block = block[1:]
    if block.endswith("\n"):
        block = block[:-1]
    return block


def _html_well_formed(html: str) -> bool:
    """Cheap sanity check that key tags are balanced (no missing closures).

    Not a full HTML parser — just enough to catch the common failure where the
    model's replacement drops a closing tag and leaves a broken page.
    """
    pairs = [("body", True), ("head", True), ("script", True), ("style", True)]
    for tag, requires_open in pairs:
        open_count = html.lower().count(f"<{tag}")
        close_count = html.lower().count(f"</{tag}>")
        if open_count != close_count:
            return False
    return True


def apply_incremental_merge(existing_code: str, patch_result: str) -> str | None:
    """Apply a structured patch to existing_code and return the merged file.

    The model (in continuation mode) is asked to output exactly one block:

        <<<REPLACE_BEGIN>>>
        <anchor: an EXACT, unique substring copied from the current HTML>
        <<<REPLACE_ANCHOR_END>>>
        <replacement code — the new/modified section>
        <<<REPLACE_END>>>

    This function:
      1. Locates the anchor substring in existing_code (must be unique).
      2. Replaces it with the new code.
      3. Validates the result still looks like a complete, balanced HTML doc.
      4. Returns None if anything looks wrong so the caller can fall back to a
         full-file rewrite (never silently ship a broken page).
    """
    anchor = _extract_block(patch_result, REPLACE_BEGIN, REPLACE_ANCHOR_END, strip=False)
    if not anchor:
        return None
    new_code = _extract_block(patch_result, REPLACE_ANCHOR_END, REPLACE_END)

    # Reject pure deletions: dropping the anchored section entirely is too risky
    # (often leaves unbalanced tags). The full-file rewrite path can still do it.
    if not new_code:
        return None

    # Anchor must appear exactly once; ambiguity or absence => fail to fallback.
    count = existing_code.count(anchor)
    if count != 1:
        return None

    merged = existing_code.replace(anchor, new_code, 1)

    # Validate the merged output is still a complete, balanced HTML doc.
    if "<html" not in merged.lower() or not merged.strip().lower().endswith("</html>"):
        return None
    if len(merged) < len(existing_code) // 2:
        return None
    if not _html_well_formed(merged):
        return None

    return merged


async def execute_llm_tool(
    task: dict,
    context: dict,
    prompt: str,
    existing_code: str | None,
) -> tuple[str, bool]:
    """LLM Tool: call AI model based on task params.prompt_type.

    Returns (content, is_truncated) — is_truncated is True when the generated
    HTML was cut off (missing </html>), e.g. by max_tokens.
    """
    is_truncated = False
    prompt_type = task.get("params", {}).get("prompt_type", "generation")
    analysis = context.get("analysis", {})
    design_outputs = context.get("task_outputs", [])

    # ---------- Demo Mode ----------
    if is_demo_mode():
        if prompt_type == "analysis":
            await asyncio.sleep(0.3)
            features = analysis.get("core_features", [])
            return f"Requirement confirmed. Core features: {', '.join(features)}. App type: {analysis.get('app_type', 'other')}.", False

        if prompt_type == "design":
            await asyncio.sleep(0.4)
            return f"Design spec: {analysis.get('ui_style', 'modern minimal')}. Layout uses card-based structure with primary color #6366f1.", False

        if prompt_type in ("generation", "continuation"):
            await asyncio.sleep(1.0)
            if existing_code:
                return get_demo_continue_artifact(prompt, existing_code), False
            return get_demo_artifact(prompt), False

        # Unknown prompt_type
        await asyncio.sleep(0.3)
        return f"Task completed: {task.get('name', '')}", False

    # ---------- AI Mode ----------
    client = get_ai_client()

    if prompt_type == "analysis":
        # Refine requirements - short call
        user_msg = f"Original request: {prompt}\nExisting analysis: {json.dumps(analysis, ensure_ascii=False)}\nRefine the requirements and provide a clear feature list."
        system_msg = DESIGN_TASK_SYSTEM_PROMPT
        max_tok = 300
    elif prompt_type == "design":
        # Design decision - short call
        design_context = "\n".join(f"- {o}" for o in design_outputs[-2:]) if design_outputs else "No prior design."
        user_msg = f"App type: {analysis.get('app_type')}\nUI style: {analysis.get('ui_style')}\nPrior context:\n{design_context}\nProvide a design spec for: {task.get('params', {}).get('instruction', '')}"
        system_msg = DESIGN_TASK_SYSTEM_PROMPT
        max_tok = 400
    elif prompt_type == "continuation":
        # Continue Building - INCREMENTAL PATCH MODE.
        # Instead of asking the model to rewrite the whole file (slow, 180s,
        # easy for the user to give up and refresh), we ask it to emit ONLY the
        # changed section wrapped in anchor markers. The model output is far
        # smaller, so the call is dramatically faster and the disconnect window
        # shrinks. We merge the patch back into the saved artifact ourselves.
        # Guard existing_code length: pass enough context (head + tail) that the
        # model can still SEE the section it must change and pick an accurate
        # anchor. We deliberately keep MAX_EXISTING generous — the speed win of
        # patch mode comes from shrinking the OUTPUT (only the changed block),
        # not from starving the input context.
        safe_code = existing_code or ""
        MAX_EXISTING = 14000
        if len(safe_code) > MAX_EXISTING:
            head = safe_code[: int(MAX_EXISTING * 0.6)]
            tail = safe_code[-int(MAX_EXISTING * 0.4):]
            safe_code = f"{head}\n\n/* ... middle {len(safe_code) - MAX_EXISTING} chars omitted for brevity — KEEP IT AS-IS, only change what the request asks ... */\n\n{tail}"
        user_msg = f"Here is the current application code:\n\n{safe_code}\n\nModification request: {prompt}\n\nRequirement summary: {analysis.get('summary', '')}\nFeatures: {', '.join(analysis.get('core_features', []))}\n\nEmit your change as a single patch block (see system instructions)."
        system_msg = CONTINUE_SYSTEM_PROMPT
        # Keep a large output budget: patch mode makes the OUTPUT smaller in
        # practice, but a large modification (e.g. adding a whole theme system)
        # must never be hard-cut. The short timeout is the real "stay responsive"
        # guard, not a small token cap.
        max_tok = 32000
    else:
        # generation - full code
        design_context = "\n".join(f"- {o}" for o in design_outputs) if design_outputs else ""
        user_msg = f"Build a web application: {prompt}\n\nRequirement summary: {analysis.get('summary', '')}\nCore features: {', '.join(analysis.get('core_features', []))}\nUI style: {analysis.get('ui_style', '')}\n\nDesign decisions:\n{design_context}"
        system_msg = GENERATOR_SYSTEM_PROMPT
        # Raised from 16000 — custom models (deepseek/kimi/qwen) support much
        # larger output, and long single-file apps (e.g. big HTML+CSS+JS pages)
        # were being hard-cut at 16k, producing truncated, non-interactive pages.
        max_tok = 32000

    # Patch-mode continuation: kimi-k2.7-code measured ~78s for a patch
    # response, so 90s was too tight (any jitter → timeout). 120s gives headroom
    # while still failing fast enough for the user to retry. Generation (first
    # build) stays at 180s as it produces much larger output.
    timeout = 120 if prompt_type == "continuation" else 180

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.7,
        max_tokens=max_tok,
        timeout=timeout,
    )

    raw = response.choices[0].message.content
    content = (raw or "").strip()

    # ---- Incremental patch merge (continuation only) ----
    # If the model returned a structured patch block (as instructed in patch
    # mode), merge it back into the saved artifact. This is the fast path.
    if prompt_type == "continuation" and existing_code and REPLACE_BEGIN in content:
        merged = apply_incremental_merge(existing_code, content)
        if merged is not None:
            # Patch applied cleanly and the result validated as a complete doc.
            return merged, False
        # The model gave us a patch but we couldn't apply it safely (bad anchor,
        # malformed block, or broken result). NEVER ship a broken page and never
        # silently save a truncated patch as the artifact. Raise so the task
        # fails cleanly and the saved artifact stays untouched — the user can
        # re-run. (If the model instead fell back to a full HTML doc, the branch
        # below still handles it normally.)
        if "<html" not in content.lower():
            raise RuntimeError(
                "Incremental patch could not be applied safely to the existing code. "
                "Please re-run the build; the previous version is intact."
            )

    # Robust HTML extraction: strip any non-HTML content (explanations, code fences)
    if prompt_type in ("generation", "continuation"):
        # Strategy 1: find <!DOCTYPE html> and extract from there to </html>
        doctype_idx = content.lower().find("<!doctype html")
        html_idx = content.lower().find("<html")
        start_idx = -1
        if doctype_idx >= 0:
            start_idx = doctype_idx
        elif html_idx >= 0:
            start_idx = html_idx

        is_truncated = False
        if start_idx >= 0:
            content = content[start_idx:]
            # Find the last </html> tag. If missing (e.g. output truncated by
            # max_tokens), keep the partial HTML rather than dropping everything
            # — a truncated page is still renderable/previewable. But flag it so
            # the UI can warn the user that the page may be incomplete.
            end_idx = content.lower().rfind("</html>")
            if end_idx >= 0:
                content = content[:end_idx + len("</html>")]
            else:
                is_truncated = True
        else:
            # Strategy 2: strip markdown code fences if present
            if content.startswith("```"):
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)

    # Fallback: if extraction yielded nothing but the model did return
    # something, use the raw output so we never silently lose the result.
    if not content and raw:
        content = raw.strip()

    return content, is_truncated


async def execute_file_writer_tool(
    task: dict,
    context: dict,
    project_id: str,
    prompt: str,
) -> dict:
    """File Writer Tool: save all artifacts (index.html + process docs) to database with version management."""
    from app.database import async_session
    from app.models.models import Artifact, Conversation
    from sqlalchemy import select

    html_content = context.get("generated_code", "")
    docs = context.get("docs", {})

    # Fallback: generated_code may be empty if the generator step failed to
    # propagate it. Recover the last non-empty HTML output from task_outputs so
    # we still persist a usable artifact instead of silently producing nothing.
    if not html_content:
        task_outputs = context.get("task_outputs", []) or []
        # task_outputs is a list of per-task result strings (see scheduler).
        for val in reversed(task_outputs):
            if isinstance(val, str) and "<html" in val.lower():
                html_content = val
                break

    if not html_content:
        return {"status": "skipped", "message": "No code to save", "version": 0, "saved_files": []}

    # Collect all files to save: index.html + docs
    files_to_save = {"index.html": html_content}
    for fname, fcontent in docs.items():
        if fcontent:
            files_to_save[fname] = fcontent

    saved_files = []
    saved_version = 1

    try:
        async with async_session() as db:
            for filename, content in files_to_save.items():
                # Query max version for this project + filename
                version_result = await db.execute(
                    select(Artifact.version)
                    .where(Artifact.project_id == project_id, Artifact.filename == filename)
                    .order_by(Artifact.version.desc())
                    .limit(1)
                )
                max_version = version_result.scalar_one_or_none()
                new_version = (max_version or 0) + 1

                artifact = Artifact(
                    project_id=project_id,
                    filename=filename,
                    content=content,
                    version=new_version,
                )
                db.add(artifact)
                saved_files.append({"filename": filename, "version": new_version, "content": content})
                if filename == "index.html":
                    saved_version = new_version

            conv = Conversation(
                project_id=project_id,
                role="assistant",
                content=f"Generated application based on: {prompt}",
            )
            db.add(conv)
            await db.commit()
    except Exception as exc:
        import traceback
        return {
            "status": "failed",
            "message": f"file_writer error: {type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-800:],
            "version": 0,
            "saved_files": [],
        }

    return {
        "status": "saved",
        "filename": "index.html",
        "version": saved_version,
        "content": html_content,
        "saved_files": saved_files,
    }


async def execute_preview_tool(task: dict, context: dict) -> dict:
    """Preview Tool: prepare preview data from generated code."""
    await asyncio.sleep(0.2)
    return {
        "status": "ready",
        "content": context.get("generated_code", ""),
        "filename": "index.html",
        "version": context.get("artifact_version", 1),
    }


# ============ Docs Generator (process artifacts) ============

DOCS_SYSTEM_PROMPT = """You are a technical documentation writer. Given the requirement analysis, task list, and generated application code, produce two markdown files:

1. architecture.md - Records the design philosophy, component structure, data flow, and technical decisions
2. progress.md - Records the requirements, user stories, task breakdown table, and progress log

Output format: return a JSON object with two keys "architecture.md" and "progress.md", each containing the full markdown content as a string.

For progress.md, use this format:
```
# Progress

last_updated: <ISO timestamp>

## Requirements & Progress

### Requirements Overview
<summary>

### User Stories
<list of user stories>

### Task Breakdown
| ID | Task | Assignee | Status | Deps |
|----|------|----------|--------|------|
<truncated>

### Progress Log
- <timestamp> - <event>
```

Only output valid JSON, no markdown code fences. Example:
{"architecture.md": "# Architecture\\n...", "progress.md": "# Progress\\n..."}"""


async def generate_docs(
    prompt: str,
    analysis: dict,
    tasks: list[dict],
    generated_code: str,
    is_continuation: bool = False,
) -> dict:
    """Generate architecture.md and progress.md as process artifacts."""
    if is_demo_mode():
        await asyncio.sleep(0.3)
        return get_demo_docs(prompt, analysis, tasks, is_continuation)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    client = get_ai_client()
    # Truncate generated_code to keep prompt manageable
    code_snippet = generated_code[:3000] + ("\n... (truncated)" if len(generated_code) > 3000 else "")

    user_msg = f"""Generate architecture.md and progress.md for this project:

Requirement Analysis: {json.dumps(analysis, ensure_ascii=False)}

Task List: {json.dumps(tasks, ensure_ascii=False)}

User Prompt: {prompt}

Generated Code (preview):
{code_snippet}

Is Continuation: {is_continuation}
Current Timestamp: {now}

Return JSON with keys "architecture.md" and "progress.md"."""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": DOCS_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.5,
        max_tokens=2000,
        timeout=120,
    )
    content = response.choices[0].message.content.strip()

    try:
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        docs = json.loads(content)
        # Ensure both files exist
        if "architecture.md" not in docs or "progress.md" not in docs:
            return get_demo_docs(prompt, analysis, tasks, is_continuation)
        return docs
    except json.JSONDecodeError:
        return get_demo_docs(prompt, analysis, tasks, is_continuation)


# ============ Execution Engine: stream_build_process ============

async def stream_build_process(
    project_id: str,
    prompt: str,
    existing_code: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream the entire build process: Analyzer → Planner → Scheduler → Tools."""
    from app.database import async_session
    from app.models.models import Project, Execution, Conversation
    from sqlalchemy import select

    async def save_execution(step: str, status: str, message: str, task_order: int = 0, task_type: str = ""):
        """Persist an execution step to the database."""
        async with async_session() as db:
            db.add(Execution(
                project_id=project_id,
                step=step,
                status=status,
                message=message,
                task_order=task_order,
                task_type=task_type,
            ))
            await db.commit()

    # Save user conversation
    async with async_session() as db:
        db.add(Conversation(project_id=project_id, role="user", content=prompt))
        await db.commit()

    # ===== Phase 1: Requirement Analyzer =====
    yield {"type": "execution", "step": "Requirement Analysis", "status": "running", "message": "Analyzing your requirements..."}
    await save_execution("Requirement Analysis", "running", "Analyzing your requirements...", task_order=0, task_type="analyzer")

    analysis = await analyze_requirements(prompt)

    # Update project title (first build only) + status
    async with async_session() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            if not existing_code:
                # Derive title from analysis summary
                title = analysis.get("summary", prompt[:50])
                if len(title) > 60:
                    title = title[:60]
                project.title = title
                project.description = analysis.get("ui_style", "")
            project.status = "PLANNING"
            await db.commit()

    analysis_msg = f"App type: {analysis.get('app_type', 'other')} | Features: {len(analysis.get('core_features', []))} identified"
    yield {"type": "plan", "analysis": analysis}
    yield {"type": "execution", "step": "Requirement Analysis", "status": "completed", "message": analysis_msg}
    await save_execution("Requirement Analysis", "completed", analysis_msg, task_order=0, task_type="analyzer")

    # ===== Phase 2: Task Planner =====
    yield {"type": "execution", "step": "Task Planning", "status": "running", "message": "Planning execution tasks..."}
    await save_execution("Task Planning", "running", "Planning execution tasks...", task_order=1, task_type="planner")

    tasks = await plan_tasks(analysis, is_continuation=bool(existing_code))

    yield {"type": "tasks", "tasks": tasks}
    plan_msg = f"Planned {len(tasks)} tasks"
    yield {"type": "execution", "step": "Task Planning", "status": "completed", "message": plan_msg}
    await save_execution("Task Planning", "completed", plan_msg, task_order=1, task_type="planner")

    # Update project status to GENERATING
    async with async_session() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.status = "GENERATING"
            await db.commit()

    # ===== Phase 3: Execution Scheduler - run each Task =====
    context = {"analysis": analysis, "task_outputs": [], "generated_code": "", "artifact_version": 1, "docs": {}}

    for i, task in enumerate(tasks):
        task_name = task.get("name", f"Task {i+1}")
        task_tool = task.get("tool", "llm")
        task_instruction = task.get("params", {}).get("instruction", "")
        task_order = i + 2  # 0 and 1 are reserved for analyzer and planner

        yield {"type": "execution", "step": task_name, "status": "running", "message": task_instruction}
        await save_execution(task_name, "running", task_instruction, task_order=task_order, task_type=task_tool)

        try:
            if task_tool == "llm":
                result, is_truncated = await execute_llm_tool(task, context, prompt, existing_code)
                prompt_type = task.get("params", {}).get("prompt_type", "")
                if prompt_type in ("generation", "continuation"):
                    context["generated_code"] = result
                    context["generated_code_truncated"] = is_truncated

                    # Generate process docs (architecture.md + progress.md) after code generation
                    if context["generated_code"]:
                        docs = await generate_docs(
                            prompt, analysis, tasks, context["generated_code"],
                            is_continuation=(existing_code is not None),
                        )
                        context["docs"] = docs

                context["task_outputs"].append(result)
                completion_msg = f"{task_name} complete"
                if prompt_type in ("analysis", "design"):
                    # Show a brief preview of the output
                    completion_msg = f"{task_name} complete: {result[:80]}{'...' if len(result) > 80 else ''}"

            elif task_tool == "file_writer":
                result = await execute_file_writer_tool(task, context, project_id, prompt)
                if result.get("status") == "saved":
                    context["artifact_version"] = result["version"]
                    # Ensure generated_code has the saved content
                    if not context["generated_code"]:
                        context["generated_code"] = result.get("content", "")
                    # Store saved_files for later artifact events
                    context["saved_files"] = result.get("saved_files", [])
                completion_msg = f"Saved {len(result.get('saved_files', []))} files (index.html v{result.get('version', 1)})"

            elif task_tool == "preview":
                result = await execute_preview_tool(task, context)
                completion_msg = "Preview assembled"

            else:
                completion_msg = f"{task_name} complete"

            yield {"type": "execution", "step": task_name, "status": "completed", "message": completion_msg}
            await save_execution(task_name, "completed", completion_msg, task_order=task_order, task_type=task_tool)

        except Exception as e:
            fail_msg = f"Task failed: {str(e)}"
            yield {"type": "execution", "step": task_name, "status": "failed", "message": fail_msg}
            await save_execution(task_name, "failed", fail_msg, task_order=task_order, task_type=task_tool)

            # Update project status to FAILED
            async with async_session() as db:
                result = await db.execute(select(Project).where(Project.id == project_id))
                project = result.scalar_one_or_none()
                if project:
                    project.status = "FAILED"
                    await db.commit()
            return

    # ===== Phase 4: Update project status + send artifacts + project_update =====
    async with async_session() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.status = "READY"
            await db.commit()

    # Send all artifacts (index.html + architecture.md + progress.md)
    saved_files = context.get("saved_files", [])
    is_truncated = context.get("generated_code_truncated", False)
    if saved_files:
        for f in saved_files:
            yield {
                "type": "artifact",
                "filename": f["filename"],
                "content": f["content"],
                "version": f["version"],
                "truncated": is_truncated and f["filename"] == "index.html",
            }
    else:
        # Fallback if saved_files not populated
        yield {
            "type": "artifact",
            "filename": "index.html",
            "content": context.get("generated_code", ""),
            "version": context.get("artifact_version", 1),
        }

    # Send project update
    yield {"type": "project_update", "status": "READY"}
