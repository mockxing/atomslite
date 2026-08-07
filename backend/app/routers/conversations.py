from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.models import Conversation
from app.models.schemas import ConversationCreate, ConversationResponse

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("/{project_id}", response_model=List[ConversationResponse])
async def list_conversations(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.project_id == project_id)
        .order_by(Conversation.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=ConversationResponse)
async def create_conversation(data: ConversationCreate, db: AsyncSession = Depends(get_db)):
    conversation = Conversation(
        project_id=data.project_id,
        role=data.role,
        content=data.content,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation
