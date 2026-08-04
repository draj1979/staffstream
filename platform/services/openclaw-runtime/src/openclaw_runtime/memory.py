"""Phase 4: real Memory Service wiring. Combines the four memory types
into what runtime.py needs — conversation history for the messages list,
long-term/preferences/facts to fold into the system prompt — and appends
the new turn afterward. Always fetched fresh over HTTP; nothing is cached
in this process between requests.
"""

from . import memory_client


async def load_context(memory_namespace: str, *, bearer_token: str) -> dict:
    history = await memory_client.get_conversation_history(
        memory_namespace, bearer_token=bearer_token
    )
    long_term = await memory_client.get_long_term_memory(
        memory_namespace, bearer_token=bearer_token
    )
    preferences = await memory_client.get_preferences(memory_namespace, bearer_token=bearer_token)
    facts = await memory_client.get_learned_facts(memory_namespace, bearer_token=bearer_token)
    return {
        "history": history,
        "long_term": long_term,
        "preferences": preferences,
        "facts": facts,
    }


async def store_turn(
    memory_namespace: str, *, bearer_token: str, user_message: str, assistant_reply: str
) -> None:
    await memory_client.append_conversation_turn(
        memory_namespace, bearer_token=bearer_token, role="user", content=user_message
    )
    await memory_client.append_conversation_turn(
        memory_namespace, bearer_token=bearer_token, role="assistant", content=assistant_reply
    )
