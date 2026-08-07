"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Plus,
  Clock,
  Trash2,
  ArrowRight,
  Loader2,
  FolderOpen,
} from "lucide-react";
import { listProjects, createProject, deleteProject, type Project } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const data = await listProjects();
      setProjects(data);
    } catch (e) {
      console.error("Failed to load projects:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    try {
      setCreating(true);
      const project = await createProject(prompt.trim());
      router.push(`/workspace/${project.id}?prompt=${encodeURIComponent(prompt.trim())}`);
    } catch (e) {
      console.error("Failed to create project:", e);
    } finally {
      setCreating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await deleteProject(id);
      setProjects(projects.filter((p) => p.id !== id));
    } catch (e) {
      console.error("Failed to delete project:", e);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border bg-surface">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-foreground">Atoms Lite</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-12">
        {/* Hero Section */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-foreground mb-4">
            What do you want to build?
          </h1>
          <p className="text-text-secondary text-lg mb-8">
            Describe your idea, and AI will build it for you
          </p>

          {/* Input Area */}
          <div className="max-w-2xl mx-auto">
            <div className="relative bg-surface rounded-2xl border border-border shadow-lg hover:shadow-xl transition-shadow">
              <div className="flex items-center p-4">
                <Sparkles className="w-5 h-5 text-primary mr-3 flex-shrink-0" />
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="A todo app with dark mode..."
                  className="flex-1 text-lg outline-none bg-transparent text-foreground placeholder:text-text-secondary"
                  disabled={creating}
                />
                <button
                  onClick={handleGenerate}
                  disabled={!prompt.trim() || creating}
                  className="ml-3 px-6 py-2.5 bg-primary text-white rounded-xl font-medium flex items-center gap-2 hover:bg-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {creating ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <ArrowRight className="w-4 h-4" />
                  )}
                  Generate
                </button>
              </div>
            </div>
            <div className="flex gap-2 mt-3 justify-center flex-wrap">
              {["Todo App", "Dashboard", "Landing Page", "CRM"].map((tag) => (
                <button
                  key={tag}
                  onClick={() => setPrompt(tag)}
                  className="px-3 py-1.5 text-sm text-text-secondary bg-surface border border-border rounded-lg hover:bg-surface-hover hover:text-foreground transition-colors"
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Projects */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <Clock className="w-5 h-5 text-text-secondary" />
              Recent Projects
            </h2>
            {projects.length > 0 && (
              <span className="text-sm text-text-secondary">{projects.length} projects</span>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-primary animate-spin" />
            </div>
          ) : projects.length === 0 ? (
            <div className="text-center py-16 bg-surface rounded-2xl border border-border">
              <FolderOpen className="w-12 h-12 text-text-secondary mx-auto mb-3" />
              <p className="text-text-secondary text-lg">No projects yet</p>
              <p className="text-text-secondary text-sm mt-1">
                Describe your idea above to get started
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((project) => (
                <div
                  key={project.id}
                  onClick={() => router.push(`/workspace/${project.id}`)}
                  className="group bg-surface rounded-xl border border-border p-5 cursor-pointer hover:border-primary/50 hover:shadow-md transition-all"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-foreground truncate">
                        {project.title}
                      </h3>
                      <p className="text-sm text-text-secondary mt-1 line-clamp-2">
                        {project.description || "No description"}
                      </p>
                    </div>
                    <button
                      onClick={(e) => handleDelete(e, project.id)}
                      className="ml-2 p-1.5 text-text-secondary hover:text-error rounded-lg hover:bg-error/10 opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between mt-4">
                    <span className="text-xs text-text-secondary">
                      {formatDate(project.updated_at)}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        project.status === "READY"
                          ? "bg-success/10 text-success"
                          : project.status === "FAILED"
                          ? "bg-error/10 text-error"
                          : "bg-primary/10 text-primary"
                      }`}
                    >
                      {project.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
