# Atoms Lite Design Document

Version: v2.0

---

# 1. Background

## Challenge

实现一个可运行的 Atoms Demo。

官方关键词：

- Agent Driven
- Workspace
- Persistent
- Interactive

---

# 2. Product Vision

本 Demo 不尝试复刻 Atoms。

而是提炼其核心设计理念。

一句话：

> 一个以 Task Orchestration 为核心，
> 通过多个 Capability Agent 协同完成应用构建的 AI Native Workspace。

核心原则：

Goal First

Task First

Execution Visible

Artifact Driven

Workspace Persistent

---

# 3. Product Philosophy

传统 AI Coding：

Prompt

↓

LLM

↓

Code

↓

Preview

Atoms Lite：

Goal

↓

Requirement Analysis

↓

Task Planning

↓

Task Orchestration

↓

Capability Agents

↓

Artifacts

↓

Preview

↓

Continue Building

整个产品不是围绕 Chat。

而是围绕 Workflow。

---

# 4. MVP

保留：

✅ Workspace

✅ Project

✅ Planner

✅ Scheduler

✅ Agent Runtime

✅ Artifact

✅ Preview

✅ Persistence

删除：

❌ Marketplace

❌ Team Workspace

❌ Publish

❌ Multi User

---

# 5. Overall Runtime

                    User Goal

                         │

                         ▼

             Requirement Analyzer

                         │

                         ▼

                  Goal Parser

                         │

                         ▼

                 Task Planner

                         │

                         ▼

               Task Graph Builder

                         │

                         ▼

             Task Orchestrator

                         │

      ┌─────────┼───────────┐

      ▼         ▼           ▼

 Architecture  Generator   Reviewer

      │         │           │

      └─────────┴───────────┘

                    │

                    ▼

              Artifact Manager

                    │

                    ▼

               Preview Renderer

                    │

                    ▼

             Persistence Store

---

# 6. Capability Agent

本 Demo 不强调人格化 Agent。

而采用 Capability Agent。

每个 Agent 完成一种能力。

例如：

Requirement Analyzer

Planner

Architecture Designer

Code Generator

Code Reviewer

Preview Builder

未来：

一个 Capability

可以映射多个真正Agent。

例如：

多个Developer。

多个Reviewer。

整个架构无需修改。

---

# 7. Task Orchestration

Runtime 最大亮点。

不是：

Prompt

↓

LLM

而是：

Task。

整个 Runtime：

由 Task 驱动。

Task：

拥有：

Task ID

Task Type

Dependencies

Input

Output

Status

Duration

Artifact

Task Status：

WAITING

READY

RUNNING

SUCCESS

FAILED

SKIPPED

整个 Demo

展示：

Task State Machine。

---

# 8. Task Graph

Planner

生成：

Task DAG。

例如：

Requirement Analysis

↓

Architecture Design

↓

Generate Layout

↓

Generate Components

↓

Generate Styles

↓

Code Review

↓

Preview

Continue Build：

不会重新生成。

而是在 DAG 上：

新增节点。

例如：

Add Login

↓

Generate Login Page

↓

Update Router

↓

Review

↓

Refresh Preview

整个 Project

不断演化。

---

# 9. Scheduler

Scheduler

负责：

找出：

所有：

READY Task。

执行：

Task。

更新：

Task Status。

Scheduler：

不关心：

Agent。

不关心：

LLM。

只关心：

Task。

因此：

后续：

支持：

并发。

支持：

优先级。

支持：

Retry。

无需修改架构。

---

# 10. Agent Dispatcher

Scheduler

找到：

Task。

↓

Dispatcher。

↓

Capability。

例如：

Task：

Generate Component

↓

Generator

Task：

Review

↓

Reviewer

Task：

Architecture

↓

Architect

未来：

一个 Capability

可以绑定：

Claude

GLM

GPT

Qwen

MCP Tool

无需修改 Runtime。

---

# 11. Artifact

Artifact

不是：

聊天内容。

而是：

Task Output。

例如：

Task：

Generate Header

↓

Header.tsx

Task：

Generate Style

↓

index.css

Task：

Review

↓

Review Report

所有 Artifact

都属于：

Project。

---

# 12. Workspace

Workspace

围绕：

Project。

左侧：

Workflow

Task

Artifacts

中间：

Conversation

右侧：

Preview

Conversation：

不是主体。

Workflow：

才是主体。

---

# 13. Execution UI

Execution

采用：

Task Card。

例如：

🧠 Requirement Analysis

Status：

Completed

Duration：

0.6s

Output：

Detected React Todo App

──────────────────

📐 Architecture Design

Running...

──────────────────

⚛️ Generate Component

Waiting

整个 Workflow

可观察。

可解释。

---

# 14. Continue Building

Prompt：

Add Search

↓

Requirement Diff

↓

Planner

↓

新增 Task

↓

Scheduler

↓

Preview

而不是：

重新生成整个项目。

---

# 15. Persistence

保存：

Project

Conversation

Task

Task Graph

Artifacts

Preview Metadata

重新进入：

恢复：

整个 Runtime。

---

# 16. Tech Stack

React

TypeScript

Tailwind

FastAPI

SQLite

OpenAI Compatible API

React Flow（Task DAG，可选）

---

# 17. Demo Highlights

⭐ Highlight 1

Task Orchestration

整个 Runtime

围绕 Task。

★★★★★

⭐ Highlight 2

Capability Agent

不是：

聊天。

而是：

能力节点。

★★★★★

⭐ Highlight 3

Execution Visibility

整个执行过程：

透明。

★★★★★

⭐ Highlight 4

Artifact Driven

所有 Task

都有输出。

★★★★☆

⭐ Highlight 5

Continue Building

Task Graph

持续演化。

★★★★★

---

# 18. Future

Parallel Scheduler

Multi Agent

Human Approval

MCP

Memory

Plugin

Workflow Template

Cloud Execution
