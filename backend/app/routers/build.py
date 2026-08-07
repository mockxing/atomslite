from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse
import json

from app.database import get_db
from app.models.models import Project, Artifact
from app.models.schemas import BuildRequest
from app.services.ai_service import stream_build_process

router = APIRouter(prefix="/api/build", tags=["build"])


@router.post("/stream")
async def stream_build(request: BuildRequest, db: AsyncSession = Depends(get_db)):
    """Stream the build process via SSE."""

    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == request.project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get existing index.html artifact for continue building (latest version)
    artifact_result = await db.execute(
        select(Artifact)
        .where(Artifact.project_id == request.project_id, Artifact.filename == "index.html")
        .order_by(Artifact.version.desc())
        .limit(1)
    )
    existing_artifact = artifact_result.scalars().first()
    existing_code = existing_artifact.content if existing_artifact else None

    # Guard against a broken/corrupt latest artifact (e.g. a previous run that
    # was hard-cut by max_tokens). Feeding a truncated page into Continue Building
    # forces the model to "fix" it by rewriting the whole file. Detect obviously
    # broken HTML and fall back to a clean first-build instead.
    if existing_code and not existing_code.strip().lower().endswith("</html>"):
        existing_code = None

    async def event_generator():
        async for event in stream_build_process(
            project_id=request.project_id,
            prompt=request.prompt,
            existing_code=existing_code,
        ):
            yield {"data": json.dumps(event)}

    return EventSourceResponse(event_generator())
