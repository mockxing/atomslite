from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.models import Artifact
from app.models.schemas import ArtifactCreate, ArtifactResponse

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("/{project_id}", response_model=List[ArtifactResponse])
async def list_artifacts(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Artifact)
        .where(Artifact.project_id == project_id)
        .order_by(Artifact.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=ArtifactResponse)
async def create_artifact(data: ArtifactCreate, db: AsyncSession = Depends(get_db)):
    # Check if artifact with same filename exists for this project
    result = await db.execute(
        select(Artifact)
        .where(Artifact.project_id == data.project_id, Artifact.filename == data.filename)
        .order_by(Artifact.version.desc())
    )
    existing = result.scalars().first()

    if existing:
        # Update existing artifact (increment version)
        existing.content = data.content
        existing.version += 1
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        artifact = Artifact(
            project_id=data.project_id,
            filename=data.filename,
            content=data.content,
        )
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        return artifact
