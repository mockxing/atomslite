from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.sql import func
from app.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(String(50), default="CREATED")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, nullable=False, index=True)
    role = Column(String(50), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())


class Execution(Base):
    __tablename__ = "executions"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, nullable=False, index=True)
    step = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")  # pending / running / completed / failed
    message = Column(Text, default="")
    task_order = Column(Integer, default=0)  # Task order within a build
    task_type = Column(String(50), default="")  # llm / file_writer / preview / planner
    created_at = Column(DateTime, server_default=func.now())
