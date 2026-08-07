// Path prefix for API calls.
// - Production (Vercel): use same-origin "/bff/*", which the Route Handler
//   (frontend/app/bff/[...path]/route.ts) proxies to the Railway backend "/api/*".
// - Local dev / custom domain: set NEXT_PUBLIC_API_URL (e.g. http://localhost:8000)
//   and we call the backend directly with "/api/*".
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const API_PREFIX = process.env.NEXT_PUBLIC_API_URL ? "/api" : "/bff";
// SSE streaming goes directly to the backend (cross-origin) to avoid Vercel's
// serverless streaming limits on proxied EventSource responses.
const SSE_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://atoms-lite-backend-production.up.railway.app";

export interface Project {
  id: string;
  title: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  project_id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface Artifact {
  id: string;
  project_id: string;
  filename: string;
  content: string;
  version: number;
  created_at: string;
}

export interface Execution {
  id: string;
  project_id: string;
  step: string;
  status: string;
  message: string;
  task_order?: number;
  task_type?: string;
  created_at: string;
}

// Project API
export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}${API_PREFIX}/projects`);
  if (!res.ok) throw new Error("Failed to fetch projects");
  return res.json();
}

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${API_BASE}${API_PREFIX}/projects/${id}`);
  if (!res.ok) throw new Error("Failed to fetch project");
  return res.json();
}

export async function createProject(title: string, description: string = ""): Promise<Project> {
  const res = await fetch(`${API_BASE}${API_PREFIX}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description }),
  });
  if (!res.ok) throw new Error("Failed to create project");
  return res.json();
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}${API_PREFIX}/projects/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete project");
}

// Conversation API
export async function listConversations(projectId: string): Promise<Conversation[]> {
  const res = await fetch(`${API_BASE}${API_PREFIX}/conversations/${projectId}`);
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

// Artifact API
export async function listArtifacts(projectId: string): Promise<Artifact[]> {
  const res = await fetch(`${API_BASE}${API_PREFIX}/artifacts/${projectId}`);
  if (!res.ok) throw new Error("Failed to fetch artifacts");
  return res.json();
}

// Execution API
export async function listExecutions(projectId: string): Promise<Execution[]> {
  const res = await fetch(`${API_BASE}${API_PREFIX}/executions/${projectId}`);
  if (!res.ok) throw new Error("Failed to fetch executions");
  return res.json();
}

// Build API - SSE stream
export async function streamBuild(
  projectId: string,
  prompt: string,
  onEvent: (event: any) => void,
): Promise<void> {
  const res = await fetch(`${SSE_BASE}/api/build/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ project_id: projectId, prompt }),
  });

  if (!res.ok) throw new Error("Failed to start build");

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value, { stream: true });
    // Parse SSE format
    const lines = text.split("\n");
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6).trim();
        if (data === "[DONE]") continue;
        try {
          const event = JSON.parse(data);
          onEvent(event);
        } catch (e) {
          // Skip unparseable lines
        }
      }
    }
  }
}
