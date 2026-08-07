export type ExecutionEvent = {
  type: "execution";
  step: string;
  status: "pending" | "running" | "completed" | "failed";
  message: string;
};

export type ArtifactEvent = {
  type: "artifact";
  filename: string;
  content: string;
  version?: number;
  truncated?: boolean;
};

export type ProjectUpdateEvent = {
  type: "project_update";
  status: string;
};

export type PlanEvent = {
  type: "plan";
  analysis: {
    app_type: string;
    core_features: string[];
    ui_style: string;
    complexity: string;
    summary: string;
  };
};

export type TaskItem = {
  name: string;
  tool: string; // llm | file_writer | preview
  deps: number[];
  params: Record<string, string>;
};

export type TasksEvent = {
  type: "tasks";
  tasks: TaskItem[];
};

export type BuildEvent =
  | ExecutionEvent
  | ArtifactEvent
  | ProjectUpdateEvent
  | PlanEvent
  | TasksEvent;

export interface ExecutionStep {
  step: string;
  status: "pending" | "running" | "completed" | "failed";
  message: string;
  task_type?: string;
  task_order?: number;
}
