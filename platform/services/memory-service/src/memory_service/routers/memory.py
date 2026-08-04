from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, require_auth

from .. import crud
from ..db import get_db
from ..schemas import (
    ConversationTurnCreate,
    ConversationTurnOut,
    LearnedFactCreate,
    LearnedFactOut,
    LongTermMemoryCreate,
    LongTermMemoryOut,
    PreferenceOut,
    PreferenceSet,
)

router = APIRouter(prefix="/memory/{memory_namespace}", tags=["memory"])
user_auth = require_auth()


@router.post(
    "/conversation", response_model=ConversationTurnOut, status_code=status.HTTP_201_CREATED
)
async def add_conversation_turn(
    memory_namespace: str,
    data: ConversationTurnCreate,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.add_conversation_turn(db, memory_namespace, data)


@router.get("/conversation", response_model=list[ConversationTurnOut])
async def list_conversation_turns(
    memory_namespace: str,
    limit: int = 20,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_conversation_turns(db, memory_namespace, limit=limit)


@router.post(
    "/long-term", response_model=LongTermMemoryOut, status_code=status.HTTP_201_CREATED
)
async def add_long_term_memory(
    memory_namespace: str,
    data: LongTermMemoryCreate,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.add_long_term_memory(db, memory_namespace, data)


@router.get("/long-term", response_model=list[LongTermMemoryOut])
async def list_long_term_memory(
    memory_namespace: str,
    limit: int = 50,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_long_term_memory(db, memory_namespace, limit=limit)


@router.get("/preferences", response_model=list[PreferenceOut])
async def list_preferences(
    memory_namespace: str,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_preferences(db, memory_namespace)


@router.put("/preferences/{key}", response_model=PreferenceOut)
async def set_preference(
    memory_namespace: str,
    key: str,
    data: PreferenceSet,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.set_preference(db, memory_namespace, key, data.value)


@router.delete("/preferences/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preference(
    memory_namespace: str,
    key: str,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    preference = await crud.get_preference(db, memory_namespace, key)
    if preference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preference not found")
    await crud.delete_preference(db, preference)


@router.post("/facts", response_model=LearnedFactOut, status_code=status.HTTP_201_CREATED)
async def add_learned_fact(
    memory_namespace: str,
    data: LearnedFactCreate,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.add_learned_fact(db, memory_namespace, data)


@router.get("/facts", response_model=list[LearnedFactOut])
async def list_learned_facts(
    memory_namespace: str,
    limit: int = 50,
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    return await crud.list_learned_facts(db, memory_namespace, limit=limit)
