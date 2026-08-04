from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ConversationTurn, LearnedFact, LongTermMemoryEntry, Preference
from .schemas import (
    ConversationTurnCreate,
    LearnedFactCreate,
    LongTermMemoryCreate,
)


async def add_conversation_turn(
    db: AsyncSession, memory_namespace: str, data: ConversationTurnCreate
) -> ConversationTurn:
    turn = ConversationTurn(memory_namespace=memory_namespace, **data.model_dump())
    db.add(turn)
    await db.commit()
    await db.refresh(turn)
    return turn


async def list_conversation_turns(
    db: AsyncSession, memory_namespace: str, limit: int = 20
) -> list[ConversationTurn]:
    result = await db.execute(
        select(ConversationTurn)
        .where(ConversationTurn.memory_namespace == memory_namespace)
        .order_by(ConversationTurn.created_at.desc())
        .limit(limit)
    )
    turns = list(result.scalars().all())
    turns.reverse()  # chronological order, ready to feed straight into an LLM messages list
    return turns


async def add_long_term_memory(
    db: AsyncSession, memory_namespace: str, data: LongTermMemoryCreate
) -> LongTermMemoryEntry:
    entry = LongTermMemoryEntry(memory_namespace=memory_namespace, **data.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_long_term_memory(
    db: AsyncSession, memory_namespace: str, limit: int = 50
) -> list[LongTermMemoryEntry]:
    result = await db.execute(
        select(LongTermMemoryEntry)
        .where(LongTermMemoryEntry.memory_namespace == memory_namespace)
        .order_by(LongTermMemoryEntry.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_preference(db: AsyncSession, memory_namespace: str, key: str) -> Preference | None:
    result = await db.execute(
        select(Preference).where(
            Preference.memory_namespace == memory_namespace, Preference.key == key
        )
    )
    return result.scalar_one_or_none()


async def list_preferences(db: AsyncSession, memory_namespace: str) -> list[Preference]:
    result = await db.execute(
        select(Preference)
        .where(Preference.memory_namespace == memory_namespace)
        .order_by(Preference.key)
    )
    return list(result.scalars().all())


async def set_preference(db: AsyncSession, memory_namespace: str, key: str, value) -> Preference:
    preference = await get_preference(db, memory_namespace, key)
    if preference is None:
        preference = Preference(memory_namespace=memory_namespace, key=key, value=value)
        db.add(preference)
    else:
        preference.value = value
    await db.commit()
    await db.refresh(preference)
    return preference


async def delete_preference(db: AsyncSession, preference: Preference) -> None:
    await db.delete(preference)
    await db.commit()


async def add_learned_fact(
    db: AsyncSession, memory_namespace: str, data: LearnedFactCreate
) -> LearnedFact:
    fact = LearnedFact(memory_namespace=memory_namespace, **data.model_dump())
    db.add(fact)
    await db.commit()
    await db.refresh(fact)
    return fact


async def list_learned_facts(
    db: AsyncSession, memory_namespace: str, limit: int = 50
) -> list[LearnedFact]:
    result = await db.execute(
        select(LearnedFact)
        .where(LearnedFact.memory_namespace == memory_namespace)
        .order_by(LearnedFact.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
