from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# Project schemas
class ProjectCreate(BaseModel):
    title: str
    description: str = ""


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Conversation schemas
class ConversationCreate(BaseModel):
    project_id: str
    role: str
    content: str


class ConversationResponse(BaseModel):
    id: str
    project_id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# Artifact schemas
class ArtifactCreate(BaseModel):
    project_id: str
    filename: str
    content: str


class ArtifactResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    content: str
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


# Execution schemas
class ExecutionCreate(BaseModel):
    project_id: str
    step: str
    status: str = "pending"
    message: str = ""


class ExecutionResponse(BaseModel):
    id: str
    project_id: str
    step: str
    status: str
    message: str
    task_order: int = 0
    task_type: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


# Requirement analysis result
class RequirementAnalysis(BaseModel):
    app_type: str
    core_features: list[str]
    ui_style: str
    complexity: str
    summary: str


# Task definition from Task Planner
class TaskDefinition(BaseModel):
    name: str
    tool: str  # llm / file_writer / preview
    deps: list[int] = []
    params: dict = {}


# Build request
class BuildRequest(BaseModel):
    project_id: str
    prompt: str
