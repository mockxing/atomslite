# Atoms Lite Issues

> 记录云端部署与构建流程中的典型故障，便于后续排查与复盘。
> 涉及项目：`atoms-lite-frontend.vercel.app` + `atoms-lite-backend-production.up.railway.app`

---

## Issue 1：构建成功但产出为空、Preview 空白

- **现象**：LLM 正常走完所有步骤（analyzer / planner / generate code / file_writer / preview），云端 status=READY，但 `artifacts count = 0`，workspace 的 Preview iframe 无内容，也没有任何可下载的 artifact 文件。
- **根因**：
  1. 生成步骤 `max_tokens=4096` 过小，整页 HTML 代码被截断，响应里缺失 `</html>` 闭合标签。
  2. `execute_llm_tool` 的提取逻辑在找不到 `</html>` 时处理不健壮：`content` 为 `None`/空字符串时直接丢弃，导致 `context["generated_code"]` 为空。
  3. `execute_file_writer_tool` 命中 `if not html_content: return "skipped"`，于是没有任何文件被写入 DB → 0 artifact → preview 空白。
  - 证据：`985966c7`、`0ea927fb` 均 status=READY 但 artifacts=0，`Save Artifact` 在 0 秒内 skipped。
- **解决方案**（commit `ad6189c`）：
  1. `execute_llm_tool` 提取：处理 `content=None`、找不到 `</html>` 时保留截断内容、空结果回退 `raw = message.content`。
  2. 生成步骤 `max_tokens` 4096 → 8000。
  3. `execute_file_writer_tool` 兜底：`generated_code` 为空时从 `context["task_outputs"]` 取最后一个非空 HTML 输出写入，不再直接 skipped。
- **验证**：`ce26d66b` 首次生成成功（status=READY，artifacts=3：index.html 16KB + architecture.md + progress.md）。

---

## Issue 2：LLM 调用无 timeout，复杂任务时后端卡死（僵尸 running）

- **现象**：触发复杂项目（如 CRM）构建时，流程卡在最后一步（Generate CRM Code / Save Artifact）一直 running，永远不报失败，前端 UI 永久"运行中"。
- **根因**：`ai_service.py` 中所有 `client.chat.completions.create(...)` 调用**没有超时参数**。复杂 prompt（CRM）导致 LLM 首 token / 整段响应极慢（Railway 美节点跨太平洋更慢，可能 20–30s+），后端干等、不抛错、不超时；前端 fetch 流读取也无停滞看门狗 → UI 永久卡死。
- **解决方案**（commit `e37feb2`）：为关键 `create` 调用加 `timeout`：
  - 生成步骤：`timeout=180`，并把 `max_tokens` 8000 → 16000（避免长代码被截断）。
  - analyzer：`timeout=120, max_tokens=400`。
  - planner：`timeout=120, max_tokens=800`。
  - docs：`timeout=120, max_tokens=2000`。
- **注意**：更早的修复 `2f7de9c` 已通过 `asyncio.wait_for(timeout=90)` 包裹 `call_with_fallback` 给多模型故障转移加了硬超时（非流式调用全覆盖）；本 issue 是 MODEL_POOL 回退到单配置后，单 `create` 调用仍需自有 timeout 的兜底。

---

## Issue 3：Save Artifact 偶发 failed（非"空"，而是抛异常）

- **现象**：`329b5769` 那次构建，最后一个 `Save Artifact` 步骤状态是 **failed**（抛异常，而非为空 skipped），导致同样无产出。
- **根因**（已定位，复现于 `f6c4cb30`）：`execute_file_writer_tool` 的兜底逻辑把 `context["task_outputs"]` 当成 **dict** 调了 `.values()`，但它实际是 **list**（调度器里 `context["task_outputs"].append(result)`，存各步骤 result 字符串）。当 `generated_code` 为空触发兜底时，`list(task_outputs.values())` 直接抛 `AttributeError: 'list' object has no attribute 'values'`，file_writer 步骤 `failed`，无 artifact。
- **解决方案**：
  - 根治（commit `02300d5`）：兜底改为直接倒序遍历列表元素 `for val in reversed(task_outputs):`，命中含 `<html` 的字符串即恢复。
  - 临时 debug（commit `aa4917a`）：`execute_file_writer_tool` 写入逻辑包 `try/except`，failed 时把真实异常类型与 message 写回 execution result，便于排查。该 debug 版保留可作防御。
- **状态**：已根治，Railway 已重新部署。

---

## Issue 4：前端"继续编辑"批次切割 bug（旧，已知未修）

- **现象**：首次 build 完成后，点击"继续编辑"触发第二轮构建，前端把两轮 execution 记录混在一起显示，时间线/产物错乱。
- **根因**：前端 `loadData`（`frontend/src/app/workspace/[id]/page.tsx`）按"找最后一个 `step === "Requirement Analysis"` 作为批次切割点"来切分 build 批次；续轮步骤名是 `Analyze Requirements`，不认，导致两轮记录被合并到同一视图。
- **解决方案**：尚未修复（用户选择忽略，刷新后页面偶发恢复正常）。根治需让前端按 build 批次 ID / execution 分组而非按步骤名字符串切分。
- **状态**：低优先级，等候用户确认是否修复。

---

## Issue 5：部署方式误解（push 不自动部署）

- **现象**：本地 `git push origin main` 后，云端没有触发重新构建，用户以为"改动没生效"。
- **根因**：云端**不是 GitHub webhook 自动部署**，而是 **CLI 手动部署**。Railway 未接 GitHub 集成自动重部署；Vercel 同理需手动触发。
- **解决方案（SOP）**：
  - 后端：`cd backend && railway up --detach`（需先 `railway link`）。
  - 前端：`cd frontend && vercel deploy --prod`（或 `vercel --prod --yes`）。
- **教训**：改完代码并 push 后，必须手动跑上述 CLI 命令才会真正部署到云端。

---

## Issue 6：MODEL_POOL 配置非法导致静默走 Demo 模式

- **现象**：后端 API Key / provider 都"配好了"，但构建始终走 Demo 模板而非真实 LLM。
- **根因**：Railway Variables 里的 `MODEL_POOL` JSON 非法（全角逗号 `，`、base_url 写成 `https:/` 少斜杠）→ 解析失败 → 静默 fallback 到单 `OPENAI_*` 配置 → 未设 `OPENAI_API_KEY` → `model_pool=[]` → `is_demo_mode()=True`。
- **解决方案**（commit `c8e51b6`）：
  1. `config.py` 的 `model_pool` 解析失败时 `log.error` 明确告警，不再静默退化。
  2. 自动容错：全角逗号 `，` → `,`，`https:/`/`http:/` → `https://`/`http://`。
- **结论**：遇到"走 demo"先查 `MODEL_POOL` 是否为合法 JSON 且后端真读到了 provider，前端不负责 demo 判断。

---

## 部署与排查速查

| 场景 | 检查点 |
|------|--------|
| 产出为空 | `max_tokens` 是否截断、file_writer 是否 skipped（Issue 1） |
| 卡在最后一步 | 是否 LLM 调用无 timeout（Issue 2）；复杂任务优先用 16000 token |
| 偶发 failed | 读 execution result traceback（Issue 3 debug 版） |
| 走 Demo | 查 `MODEL_POOL` JSON 合法性（Issue 6） |
| 改动未生效 | 是否手动跑 CLI 部署（Issue 5） |

- 后端域名：`https://atoms-lite-backend-production.up.railway.app`
- 前端域名：`https://atoms-lite-frontend.vercel.app`
- 本地验证：`backend/scripts/test_failover.py`（`PROBE_TIMEOUT=25 python scripts/test_failover.py`）实测各 provider 延迟与故障转移。

---

## Issue 7：长页面生成被 max_tokens 截断（无交互，非沙箱）

- **现象**：`工作总结生成` 页面在 Vercel 预览和本地双击都**完全无交互**；同期 `todo app` 交互正常（说明 Issue 预览沙箱修复有效，环境无关）。下载的 `工作总结生成.html` 经读取确认：`<script>` 只写到一半（`generateBtn` 的 click 绑定从未出现，`</script></body></html>` 全缺），是**残缺 HTML**。
- **根因**：
  1. `execute_llm_tool` generation 步骤 `max_tokens=16000`（Issue 2 从 8000 提上来）。"工作总结生成"这类长 CSS+长 JS 页面顶到 16000 token 上限被硬截断。
  2. 旧代码在缺 `</html>` 时**保留半截 HTML 入库**，注释天真认为"truncated page is still renderable/previewable"——但半截 `<script>` 无事件绑定 → 彻底无交互。这与沙箱 / origin / `file://` 全部无关。
- **说明**：模型为自定义配置（deepseek v4 flash / qwen3.7 / kimi 2.6），输出上限远高于 16000，调大安全。
- **解决方案**：
  1. `ai_service.py` generation `max_tokens` 16000 → **32000**。
  2. `execute_llm_tool` 返回 `(content, is_truncated)` 元组；`</html>` 缺失时 `is_truncated=True`。
  3. `stream_build_process` 存 `context["generated_code_truncated"]`，`artifact` 事件带 `truncated` 字段。
  4. 前端 `ArtifactEvent` 加 `truncated?`；`page.tsx` 在 `truncated` 为真时提示用户"生成被截断，请重新生成"。
- **验证**：已生成的残缺页面不会自动变好，**必须重新发起一次 build** 才会用新 `max_tokens` 生成完整 HTML。
- **状态**：代码已改，待提交 + `railway up --detach`（后端）+ `vercel deploy --prod --yes`（前端）部署。

---

## Issue 8：Continue Building 触发整页重生成（非截断，是 continuation 分支预算不一致）

- **现象**：对某 project 做"主题修改"类的 Continue Building 时，原本完整的 `index.html` 被**整页重新生成**（而非局部修改），丢失原有内容与结构。首次生成完整、仅续建出错。
- **根因**（已排除脏数据/截断后定位）：
  1. `execute_llm_tool` 的 continuation 分支 `max_tokens=8000`，而 generation 分支已是 `32000`（Issue 7 提过）。CONTINUE_SYSTEM_PROMPT 要求"输出完整 HTML"，8000 token 装不下长页面 → 模型被迫输出精简重写版，表现为"整页重生成"。
  2. `existing_code` 在拼接 user_msg 时**无长度保护**，整段长页面直接塞入上下文，叠加指令占用，进一步压缩了模型输出空间、诱发重写。
- **解决方案**（本次修复）：
  1. `ai_service.py` continuation 分支 `max_tokens` 8000 → **32000**（与 generation 对齐）。
  2. continuation 分支对 `existing_code` 加头尾截断保护：超过 `MAX_EXISTING=14000` 字符时保留前 60% + 后 40%，中间插入"省略、保持原样"提示，避免上下文撑爆、同时约束模型只改指定部分。
  3. `build.py` 在取 latest `index.html` 作 `existing_code` 时，检测破损 artifact（不以 `</html>` 结尾）则回退为空，避免把脏数据喂给 continuation 触发重写。
- **状态**：代码已改（ai_service.py + build.py），无 lint 错误，待提交 + 部署。

---

## Issue 9：构建中途客户端断开 / 超时，project 永久卡在 GENERATING（最后一步 running）

- **现象**：对某 project（2637b862）做第三次 Continue Building，跑到最后一个 `Generate ... App Code` 步骤后中断，project 一直 `status=GENERATING`，最后一步 execution 永远 `running`、无 completed/failed；前端页面停止 loading（isBuilding=false）但时间线"卡在最后一步"。
- **根因**：`stream_build_process`（ai_service.py）的 task 循环 `try` 只 `except Exception`。SSE 客户端断开时，sse_starlette 取消消费协程，`CancelledError` 是 `BaseException` 子类（非 Exception），穿透 `except Exception` 未被捕获 → generator 协程被直接销毁，**没有任何 finally 把 project 状态收尾** → 永久 `GENERATING`。本次第三代续建用 `max_tok=32000` 生成更长页面，耗时更久，更易在 Railway 平台/代理超时或前端切走时断连触发。
- **解决方案**（本次修复）：
  1. `build.py` 的 SSE `event_generator` 外包 `try/finally`，在连接取消/断开时调用 `_finalize_on_disconnect()`：若 project 仍处于非终态（非 READY/FAILED），置为 `FAILED` 并补一条 `Build interrupted` failed execution，避免 UI 永久卡死。
  2. `executions.py` 新增 `PATCH /api/executions/{id}` 端点，便于把中断残留的 `running` 步骤标记为 `failed`（运维修复历史脏数据用）。
- **验证/恢复**：部署后用 PATCH 把卡死的 project 置回 READY，并用 executions PATCH 把孤儿 running 步骤标 failed，用户即可看到 v2 成品并重试续建。
- **状态**：代码已改（build.py + executions.py），无 lint 错误，待提交 + 部署 + 解锁该 project。
