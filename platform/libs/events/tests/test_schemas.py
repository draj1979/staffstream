import uuid

from events import ChatInteractionEvent, LLMUsageEvent, SkillUsageEvent


def test_llm_usage_event_round_trips_through_json():
    event = LLMUsageEvent(
        tenant_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        provider="claude",
        model="claude-sonnet-5",
        input_tokens=120,
        output_tokens=45,
        cost_usd=0.0031,
    )
    parsed = LLMUsageEvent.model_validate_json(event.model_dump_json())
    assert parsed == event


def test_llm_usage_event_agent_id_defaults_to_none():
    event = LLMUsageEvent(
        tenant_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        provider="claude",
        model="claude-sonnet-5",
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0001,
    )
    assert event.agent_id is None


def test_chat_interaction_event_round_trips():
    event = ChatInteractionEvent(
        tenant_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        success=False,
        error_stage="llm",
        latency_ms=842,
    )
    parsed = ChatInteractionEvent.model_validate_json(event.model_dump_json())
    assert parsed == event


def test_skill_usage_event_round_trips():
    event = SkillUsageEvent(
        tenant_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        skill_name="calendar.create_event",
        success=True,
    )
    parsed = SkillUsageEvent.model_validate_json(event.model_dump_json())
    assert parsed == event
