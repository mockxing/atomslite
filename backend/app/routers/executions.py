from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.models import Execution
from app.models.schemas import ExecutionCreate, ExecutionResponse

router = APIRouter(prefix="/api/executions", tags=["executions"])


@router.get("/{project_id}", response_model=List[ExecutionResponse])
async def list_executions(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Execution)
        .where(Execution.project_id == project_id)
        .order_by(Execution.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=ExecutionResponse)
async def create_execution(data: ExecutionCreate, db: AsyncSession = Depends(get_db)):
    execution = Execution(
        project_id=data.project_id,
        step=data.step,
        status=data.status,
        message=data.message,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    return execution
