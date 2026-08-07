"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Send,
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  FileCode2,
  Eye,
  MessageSquare,
  Zap,
  Sparkles,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  Folder,
  Download,
  FileText,
  File,
} from "lucide-react";
import {
  getProject,
  listConversations,
  listArtifacts,
  listExecutions,
  streamBuild,
  type Project,
  type Conversation,
  type Artifact,
} from "@/lib/api";
import type { BuildEvent, ExecutionStep } from "@/lib/types";

export default function WorkspacePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const initialPrompt = searchParams.get("prompt") || "";

  const [project, setProject] = useState<Project | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [prompt, setPrompt] = useState("");
  const [isBuilding, setIsBuilding] = useState(false);
  const [activeArtifact, setActiveArtifact] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string>("");
  const [showFileTree, setShowFileTree] = useState(true);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  const iframeRef = useRef<HTMLIFrameElement>(null);
  const hasAutoBuilt = useRef(false);

  useEffect(() => { loadData(); }, [projectId]);

  useEffect(() => {
    if (initialPrompt && project && !isBuilding && !hasAutoBuilt.current && conversations.length === 0) {
      hasAutoBuilt.current = true;
      handleBuild(initialPrompt);
    }
  }, [initialPrompt, project]);

  const loadData = async () => {
    try {
      const [proj, convs, arts, execs] = await Promise.all([
        getProject(projectId), listConversations(projectId),
        listArtifacts(projectId), listExecutions(projectId),
      ]);
      setProject(proj);
      setConversations(convs);
      // For artifacts, deduplicate by filename: keep only the latest version per file
      const latestArtMap = new Map<string, Artifact>();
      for (const art of arts) {
        const existing = latestArtMap.get(art.filename);
        if (!existing || art.version > existing.version) {
          latestArtMap.set(art.filename, art);
        }
      }
      const latestArts = Array.from(latestArtMap.values());
      setArtifacts(latestArts);
      // Set preview to index.html by default (preferred), otherwise last artifact
      if (latestArts.length > 0) {
        const htmlArtifact = latestArts.find((a) => a.filename === "index.html");
        const latest = htmlArtifact || latestArts[latestArts.length - 1];
        setPreviewHtml(latest.content);
        setActiveArtifact(latest.filename);
      }
      // For execution steps, take the latest build batch (by task_order)
      // Each build produces: 0=analyzer, 1=planner, 2..N=task executions
      // Find the index of the last "Requirement Analysis" running event, take everything from there
      if (execs.length > 0) {
        // Find the latest "Requirement Analysis" record - that's the start of the latest build
        let latestBuildStart = -1;
        for (let i = execs.length - 1; i >= 0; i--) {
          if (execs[i].step === "Requirement Analysis") {
            latestBuildStart = i;
            break;
          }
        }
        // If not found, use all records; otherwise take from that index onward
        const latestBatch = latestBuildStart >= 0 ? execs.slice(latestBuildStart) : execs;

        // Deduplicate by step name: prefer completed > running > failed > pending
        const statusPriority: Record<string, number> = { completed: 3, running: 2, failed: 1, pending: 0 };
        const stepMap = new Map<string, ExecutionStep>();
        for (const e of latestBatch) {
          const existing = stepMap.get(e.step);
          if (!existing || (statusPriority[e.status] ?? 0) >= (statusPriority[existing.status] ?? 0)) {
            stepMap.set(e.step, {
              step: e.step,
              status: e.status as ExecutionStep["status"],
              message: e.message,
              task_type: e.task_type,
              task_order: e.task_order,
            });
          }
        }
        // Sort by task_order if available
        const steps = Array.from(stepMap.values());
        steps.sort((a, b) => (a.task_order ?? 99) - (b.task_order ?? 99));
        setExecutionSteps(steps);
      }
    } catch (e) { console.error("Failed to load data:", e); }
  };

  const handleBuild = async (buildPrompt?: string) => {
    const currentPrompt = buildPrompt || prompt;
    if (!currentPrompt.trim() || isBuilding) return;
    setIsBuilding(true);
    setPrompt("");
    setConversations((prev) => [...prev, { id: `temp-${Date.now()}`, project_id: projectId, role: "user", content: currentPrompt, created_at: new Date().toISOString() }]);
    setExecutionSteps([]);
    try {
      await streamBuild(projectId, currentPrompt, (event: BuildEvent) => {
        switch (event.type) {
          case "execution":
            setExecutionSteps((prev) => {
              const existing = prev.findIndex((s) => s.step === event.step);
              if (existing >= 0) { const updated = [...prev]; updated[existing] = { step: event.step, status: event.status, message: event.message }; return updated; }
              return [...prev, { step: event.step, status: event.status, message: event.message }];
            });
            break;
          case "plan":
            // Show analysis summary in conversation
            setConversations((prev) => [...prev, {
              id: `temp-plan-${Date.now()}`,
              project_id: projectId,
              role: "assistant",
              content: `📋 Analysis: ${event.analysis.summary} (Type: ${event.analysis.app_type}, Complexity: ${event.analysis.complexity})`,
              created_at: new Date().toISOString(),
            }]);
            break;
          case "tasks":
            // Initialize all tasks as pending - they'll be updated as execution events arrive
            setExecutionSteps(event.tasks.map((t, i) => ({
              step: t.name,
              status: "pending" as const,
              message: t.params?.instruction || "",
              task_type: t.tool,
              task_order: i,
            })));
            break;
          case "artifact":
            // Only update preview in real-time; artifacts list is loaded from backend in finally
            setPreviewHtml(event.content);
            setActiveArtifact(event.filename);
            break;
          case "project_update":
            setProject((prev) => (prev ? { ...prev, status: event.status } : null));
            setConversations((prev) => [...prev, { id: `temp-assistant-${Date.now()}`, project_id: projectId, role: "assistant", content: "Application generated successfully!", created_at: new Date().toISOString() }]);
            break;
        }
      });
    } catch (e) {
      console.error("Build failed:", e);
      setConversations((prev) => [...prev, { id: `temp-error-${Date.now()}`, project_id: projectId, role: "assistant", content: "Build failed. Please try again.", created_at: new Date().toISOString() }]);
    } finally { setIsBuilding(false); loadData(); }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleBuild(); } };

  const getStepIcon = (status: ExecutionStep["status"]) => {
    switch (status) {
      case "completed": return <CheckCircle2 className="w-4 h-4" style={{ color: "#10b981" }} />;
      case "running": return <Loader2 className="w-4 h-4 animate-spin" style={{ color: "#6366f1" }} />;
      case "failed": return <XCircle className="w-4 h-4" style={{ color: "#ef4444" }} />;
      default: return <Circle className="w-4 h-4" style={{ color: "#94a3b8" }} />;
    }
  };

  const renderMarkdown = (md: string): string => {
    const lines = md.split("\n");
    let html = "";
    let inCodeBlock = false;
    let inTable = false;
    let tableHeader: string[] = [];
    let listType: "" | "ul" | "ol" = "";

    const escapeHtml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const inline = (s: string) => escapeHtml(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, '<code style="background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:0.9em;">$1</code>');

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Code block
      if (line.trim().startsWith("```")) {
        if (inCodeBlock) {
          html += "</code></pre>";
          inCodeBlock = false;
        } else {
          if (listType) { html += listType === "ul" ? "</ul>" : "</ol>"; listType = ""; }
          if (inTable) { html += "</table>"; inTable = false; }
          html += '<pre style="background:#1e293b;color:#e2e8f0;padding:14px 18px;border-radius:10px;overflow-x:auto;margin:10px 0;font-size:13px;line-height:1.6;"><code>';
          inCodeBlock = true;
        }
        continue;
      }
      if (inCodeBlock) {
        html += escapeHtml(line) + "\n";
        continue;
      }

      // Table
      if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
        if (listType) { html += listType === "ul" ? "</ul>" : "</ol>"; listType = ""; }
        const cells = line.trim().split("|").slice(1, -1).map(c => c.trim());
        // Check if next line is separator (|---|---|)
        const nextLine = lines[i + 1] || "";
        if (nextLine.trim().match(/^\|[\s-:|]+\|$/)) {
          if (!inTable) {
            html += '<table style="width:100%;border-collapse:collapse;margin:12px 0;font-size:13px;">';
            inTable = true;
          }
          html += "<thead><tr>";
          cells.forEach(c => { html += `<th style="padding:8px 12px;text-align:left;border-bottom:2px solid #e2e8f0;font-weight:600;color:#1e293b;">${inline(c)}</th>`; });
          html += "</tr></thead><tbody>";
          i++; // skip separator line
          continue;
        }
        if (inTable) {
          html += "<tr>";
          cells.forEach(c => { html += `<td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;color:#475569;">${inline(c)}</td>`; });
          html += "</tr>";
          continue;
        }
      }
      if (inTable && !line.trim().startsWith("|")) {
        html += "</tbody></table>";
        inTable = false;
      }

      // Headings
      if (line.startsWith("# ")) { if (listType) { html += listType === "ul" ? "</ul>" : "</ol>"; listType = ""; } html += `<h1 style="font-size:24px;font-weight:700;color:#1e293b;margin:20px 0 12px;">${inline(line.slice(2))}</h1>`; continue; }
      if (line.startsWith("## ")) { if (listType) { html += listType === "ul" ? "</ul>" : "</ol>"; listType = ""; } html += `<h2 style="font-size:20px;font-weight:600;color:#1e293b;margin:18px 0 10px;border-bottom:1px solid #f1f5f9;padding-bottom:6px;">${inline(line.slice(3))}</h2>`; continue; }
      if (line.startsWith("### ")) { if (listType) { html += listType === "ul" ? "</ul>" : "</ol>"; listType = ""; } html += `<h3 style="font-size:16px;font-weight:600;color:#4f46e5;margin:14px 0 8px;">${inline(line.slice(4))}</h3>`; continue; }
      if (line.startsWith("#### ")) { if (listType) { html += listType === "ul" ? "</ul>" : "</ol>"; listType = ""; } html += `<h4 style="font-size:14px;font-weight:600;color:#475569;margin:12px 0 6px;">${inline(line.slice(5))}</h4>`; continue; }

      // Lists
      if (line.match(/^\s*-\s+/)) {
        if (listType !== "ul") { if (listType) html += "</ol>"; html += '<ul style="margin:8px 0;padding-left:24px;">'; listType = "ul"; }
        html += `<li style="color:#475569;line-height:1.7;">${inline(line.replace(/^\s*-\s+/, ""))}</li>`;
        continue;
      }
      if (line.match(/^\s*\d+\.\s+/)) {
        if (listType !== "ol") { if (listType) html += "</ul>"; html += '<ol style="margin:8px 0;padding-left:24px;">'; listType = "ol"; }
        html += `<li style="color:#475569;line-height:1.7;">${inline(line.replace(/^\s*\d+\.\s+/, ""))}</li>`;
        continue;
      }
      if (listType) { html += listType === "ul" ? "</ul>" : "</ol>"; listType = ""; }

      // Horizontal rule
      if (line.trim() === "---" || line.trim() === "***") {
        html += '<hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;" />';
        continue;
      }

      // Empty line
      if (line.trim() === "") { continue; }

      // Paragraph
      html += `<p style="color:#475569;line-height:1.7;margin:6px 0;">${inline(line)}</p>`;
    }
    if (listType) html += listType === "ul" ? "</ul>" : "</ol>";
    if (inTable) html += "</tbody></table>";
    if (inCodeBlock) html += "</code></pre>";

    return `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#fff;color:#1e293b;padding:32px 40px;max-width:780px;margin:0 auto;line-height:1.6;}h1:first-child{margin-top:0;}</style></head><body>${html}</body></html>`;
  };

  const getPreviewContent = (): string => {
    if (!previewHtml) return "";
    const ext = activeArtifact?.split(".").pop()?.toLowerCase();
    if (ext === "md") return renderMarkdown(previewHtml);
    return previewHtml;
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase();
    switch (ext) {
      case "html": return <FileCode2 className="w-3.5 h-3.5" style={{ color: "#e44d26" }} />;
      case "css": return <FileText className="w-3.5 h-3.5" style={{ color: "#2563eb" }} />;
      case "js": case "ts": case "tsx": case "jsx": return <FileText className="w-3.5 h-3.5" style={{ color: "#eab308" }} />;
      case "json": return <File className="w-3.5 h-3.5" style={{ color: "#64748b" }} />;
      default: return <File className="w-3.5 h-3.5" style={{ color: "#64748b" }} />;
    }
  };

  const handleDownload = () => {
    if (!previewHtml) return;
    const blob = new Blob([previewHtml], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = activeArtifact || "index.html";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#f8f9fc" }}>
      {/* Top Bar */}
      <header style={{ height: 48, borderBottom: "1px solid #e2e8f0", background: "#fff", display: "flex", alignItems: "center", padding: "0 16px", gap: 12, flexShrink: 0 }}>
        <a href="/" style={{ padding: 6, borderRadius: 8, display: "flex", alignItems: "center" }}>
          <ArrowLeft className="w-4 h-4" style={{ color: "#64748b" }} />
        </a>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Sparkles className="w-4 h-4" style={{ color: "#6366f1" }} />
          <span style={{ fontWeight: 600, color: "#1a1a2e", fontSize: 14, maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {project?.title || "Loading..."}
          </span>
        </div>
        <div style={{ flex: 1 }} />
        {project && (
          <span style={{
            fontSize: 11, padding: "2px 8px", borderRadius: 9999, fontWeight: 500,
            background: project.status === "READY" ? "#d1fae5" : project.status === "FAILED" ? "#fee2e2" : "#e0e7ff",
            color: project.status === "READY" ? "#059669" : project.status === "FAILED" ? "#dc2626" : "#6366f1",
          }}>
            {project.status}
          </span>
        )}
      </header>

      {/* Main Content - Three Panel Layout */}
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>

        {/* ====== LEFT PANEL - Execution + Conversation + Prompt ====== */}
        <div style={{ width: 320, minWidth: 320, flexShrink: 0, display: "flex", flexDirection: "column", background: "#fff", borderRight: "1px solid #e2e8f0" }}>
          {/* Execution Timeline Header */}
          <div style={{ padding: "8px 12px", borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", gap: 6 }}>
            <Zap className="w-3.5 h-3.5" style={{ color: "#6366f1" }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: "#6366f1" }}>Execution</span>
          </div>

          {/* Execution Timeline */}
          <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
            {executionSteps.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {executionSteps.map((step, index) => {
                  const isExpanded = expandedStep === step.step;
                  const toolLabel = step.task_type
                    ? step.task_type === "llm" ? "LLM" : step.task_type === "file_writer" ? "File Writer" : step.task_type === "preview" ? "Preview" : step.task_type === "analyzer" ? "Analyzer" : step.task_type === "planner" ? "Planner" : step.task_type
                    : "";
                  const statusColor = step.status === "completed" ? "#10b981" : step.status === "running" ? "#6366f1" : step.status === "failed" ? "#ef4444" : "#94a3b8";
                  return (
                    <div key={index} className="slide-in">
                      <div
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 10,
                          cursor: "pointer",
                          padding: "4px 6px",
                          margin: "-4px -6px",
                          borderRadius: 6,
                          background: isExpanded ? "#f1f5ff" : "transparent",
                          transition: "background 0.15s",
                        }}
                        onClick={() => setExpandedStep(isExpanded ? null : step.step)}
                      >
                        <div style={{ marginTop: 2 }}>{getStepIcon(step.status)}</div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 13, fontWeight: 500, color: "#1a1a2e", display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{step.step}</span>
                            {toolLabel && (
                              <span style={{ fontSize: 9, padding: "1px 5px", borderRadius: 4, background: "#e0e7ff", color: "#6366f1", fontWeight: 600, flexShrink: 0 }}>{toolLabel}</span>
                            )}
                          </div>
                          {!isExpanded && step.message && (
                            <div style={{ fontSize: 11, color: "#64748b", marginTop: 2, lineHeight: "1.4", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{step.message}</div>
                          )}
                        </div>
                        {isExpanded ? <ChevronDown className="w-3 h-3" style={{ color: "#94a3b8", marginTop: 4, flexShrink: 0 }} /> : <ChevronRight className="w-3 h-3" style={{ color: "#94a3b8", marginTop: 4, flexShrink: 0 }} />}
                      </div>
                      {isExpanded && (
                        <div style={{ marginLeft: 18, marginTop: 6, padding: 10, background: "#f8f9fc", borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 11, lineHeight: 1.6 }}>
                          <div style={{ display: "flex", gap: 12, marginBottom: 6 }}>
                            <div><span style={{ color: "#94a3b8" }}>Status:</span> <span style={{ color: statusColor, fontWeight: 600 }}>{step.status}</span></div>
                            {step.task_order !== undefined && (
                              <div><span style={{ color: "#94a3b8" }}>Order:</span> <span style={{ color: "#1a1a2e" }}>#{step.task_order}</span></div>
                            )}
                          </div>
                          {step.message && (
                            <div style={{ marginBottom: 4 }}>
                              <div style={{ color: "#94a3b8", marginBottom: 2 }}>Detail</div>
                              <div style={{ color: "#475569", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{step.message}</div>
                            </div>
                          )}
                        </div>
                      )}
                      {index < executionSteps.length - 1 && (
                        <div style={{ marginLeft: 7, marginTop: 4, marginBottom: 4, width: 1, height: 8, background: "#e2e8f0" }} />
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: "32px 0" }}>
                <Zap className="w-8 h-8" style={{ color: "#94a3b8", margin: "0 auto 8px" }} />
                <p style={{ fontSize: 12, color: "#94a3b8" }}>Execution timeline will appear here</p>
              </div>
            )}
          </div>

          {/* Conversation */}
          <div style={{ borderTop: "1px solid #e2e8f0" }}>
            <div style={{ padding: "6px 12px", fontSize: 11, fontWeight: 500, color: "#94a3b8", display: "flex", alignItems: "center", gap: 4 }}>
              <MessageSquare className="w-3 h-3" /> Conversation
            </div>
            <div style={{ maxHeight: 100, overflowY: "auto", padding: "0 12px 6px" }}>
              {conversations.map((conv) => (
                <div key={conv.id} style={{ fontSize: 11, lineHeight: 1.5, marginBottom: 3 }}>
                  <span style={{ fontWeight: 500, color: conv.role === "user" ? "#6366f1" : "#059669" }}>
                    {conv.role === "user" ? "You: " : "AI: "}
                  </span>
                  <span style={{ color: "#64748b" }}>{conv.content}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Prompt Input */}
          <div style={{ borderTop: "1px solid #e2e8f0", padding: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#f8f9fc", borderRadius: 10, border: "1px solid #e2e8f0", padding: "10px 14px" }}>
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={isBuilding ? "Building..." : artifacts.length > 0 ? "Continue building..." : "What do you want to build?"}
                style={{ flex: 1, fontSize: 13, outline: "none", background: "transparent", color: "#1a1a2e" }}
                disabled={isBuilding}
              />
              <button onClick={() => handleBuild()} disabled={!prompt.trim() || isBuilding}
                style={{ padding: 4, color: "#6366f1", background: "none", border: "none", cursor: "pointer", borderRadius: 6, opacity: !prompt.trim() || isBuilding ? 0.4 : 1 }}>
                {isBuilding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>

        {/* ====== MIDDLE PANEL - File Viewer + Download (collapsible) ====== */}
        {showFileTree && (
          <div style={{ width: 220, minWidth: 220, flexShrink: 0, display: "flex", flexDirection: "column", background: "#fafbfc", borderRight: "1px solid #e2e8f0" }}>
            {/* Header with collapse button */}
            <div style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <FolderOpen className="w-3.5 h-3.5" style={{ color: "#64748b" }} />
                <span style={{ fontSize: 12, fontWeight: 600, color: "#1a1a2e" }}>Artifact</span>
              </div>
              <button onClick={() => setShowFileTree(false)} style={{ padding: 2, color: "#94a3b8", background: "none", border: "none", cursor: "pointer", borderRadius: 4, display: "flex" }}>
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Search Box */}
            <div style={{ padding: "6px 10px", borderBottom: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, background: "#fff", borderRadius: 6, border: "1px solid #e2e8f0", padding: "4px 8px" }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                <input type="text" placeholder="Search files..." style={{ flex: 1, fontSize: 11, outline: "none", background: "transparent", color: "#1a1a2e" }} />
              </div>
            </div>

            {/* File Tree */}
            <div style={{ flex: 1, overflowY: "auto", padding: "4px 0" }}>
              {artifacts.length > 0 ? (
                <div>
                  {/* .atoms folder */}
                  <div style={{ padding: "4px 10px", display: "flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 500, color: "#1a1a2e" }}>
                    <ChevronDown className="w-3 h-3" style={{ color: "#94a3b8", flexShrink: 0 }} />
                    <Folder className="w-3.5 h-3.5" style={{ color: "#eab308", flexShrink: 0 }} />
                    <span>.atoms</span>
                  </div>
                  {/* Files */}
                  {artifacts.map((artifact) => (
                    <button
                      key={artifact.id}
                      onClick={() => { setActiveArtifact(artifact.filename); setPreviewHtml(artifact.content); }}
                      style={{
                        width: "100%", textAlign: "left", padding: "4px 10px 4px 26px",
                        display: "flex", alignItems: "center", gap: 5, fontSize: 11,
                        background: activeArtifact === artifact.filename ? "#eff1ff" : "transparent",
                        color: activeArtifact === artifact.filename ? "#4f46e5" : "#475569",
                        border: "none", cursor: "pointer", borderRadius: 0,
                      }}
                    >
                      {getFileIcon(artifact.filename)}
                      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{artifact.filename}</span>
                      <span style={{ fontSize: 9, color: "#94a3b8", flexShrink: 0 }}>v{artifact.version}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: "center", padding: "32px 12px" }}>
                  <FolderOpen className="w-6 h-6" style={{ color: "#cbd5e1", margin: "0 auto 6px" }} />
                  <p style={{ fontSize: 11, color: "#94a3b8" }}>No files yet</p>
                  <p style={{ fontSize: 10, color: "#cbd5e1", marginTop: 3 }}>Build to generate files</p>
                </div>
              )}
            </div>

            {/* Download Project */}
            <div style={{ padding: "8px 10px", borderTop: "1px solid #e2e8f0" }}>
              <button
                onClick={handleDownload}
                disabled={!previewHtml}
                style={{
                  width: "100%", padding: "7px 10px", borderRadius: 6,
                  background: previewHtml ? "#4f46e5" : "#e2e8f0",
                  color: previewHtml ? "#fff" : "#94a3b8",
                  border: "none", cursor: previewHtml ? "pointer" : "not-allowed",
                  fontSize: 11, fontWeight: 500,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
                }}
              >
                <Download className="w-3.5 h-3.5" />
                Download Project
              </button>
            </div>
          </div>
        )}

        {/* Expand button when file tree is hidden */}
        {!showFileTree && (
          <button
            onClick={() => setShowFileTree(true)}
            style={{ width: 28, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "#fafbfc", borderRight: "1px solid #e2e8f0", border: "none", cursor: "pointer", color: "#94a3b8" }}
            title="Show Files"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        )}

        {/* ====== RIGHT PANEL - Preview ====== */}
        <div style={{ flex: 1, minWidth: 300, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Browser-style header */}
          <div style={{ height: 40, padding: "0 12px", borderBottom: "1px solid #e2e8f0", background: "#fff", display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <div style={{ display: "flex", gap: 6 }}>
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#fca5a5" }} />
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#fcd34d" }} />
              <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#86efac" }} />
            </div>
            <div style={{ flex: 1, background: "#f1f5f9", borderRadius: 6, padding: "4px 10px", fontSize: 11, color: "#94a3b8", display: "flex", alignItems: "center", gap: 4 }}>
              <Eye className="w-3 h-3" />
              {activeArtifact ? `${activeArtifact} — Preview` : "Application Preview"}
            </div>
          </div>
          {/* Preview Content */}
          <div style={{ flex: 1, background: "#fff", minHeight: 0, overflow: "hidden" }}>
            {previewHtml ? (
              <iframe ref={iframeRef} srcDoc={getPreviewContent()} style={{ width: "100%", height: "100%", border: "none" }} title="Application Preview" sandbox="allow-scripts allow-forms allow-modals allow-same-origin" />
            ) : (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
                <div style={{ textAlign: "center" }}>
                  <Eye className="w-12 h-12" style={{ color: "#cbd5e1", margin: "0 auto 12px" }} />
                  <p style={{ color: "#94a3b8", fontSize: 15, fontWeight: 500 }}>
                    {isBuilding ? "Building your application..." : "Preview will appear here"}
                  </p>
                  <p style={{ color: "#cbd5e1", fontSize: 12, marginTop: 4 }}>Describe what you want to build in the left panel</p>
                  {isBuilding && (
                    <div style={{ display: "flex", gap: 6, justifyContent: "center", marginTop: 16 }}>
                      <div className="w-2 h-2 bg-[#6366f1] rounded-full pulse-dot" />
                      <div className="w-2 h-2 bg-[#6366f1] rounded-full pulse-dot" />
                      <div className="w-2 h-2 bg-[#6366f1] rounded-full pulse-dot" />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
