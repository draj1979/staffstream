from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import Principal, Role, require_auth, require_role
from events import ROUTING_KEY_AUDIT, AuditEvent, Publisher, schedule_publish

from .. import crud
from ..connectors import CONNECTOR_REGISTRY
from ..db import get_db
from ..dependencies import get_publisher
from ..schemas import SkillEnablementOut, SkillEnablementUpdate, ToolOut

router = APIRouter(tags=["skills"])
user_auth = require_auth()
# Turning a skill on/off for the whole tenant is admin-only — every
# employee who happens to have a manager/employee role shouldn't be able
# to widen or shrink what's available platform-wide.
admin_auth = require_role(Role.ADMIN.value)


@router.get("/skills", response_model=list[SkillEnablementOut])
async def list_skills(
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    """The catalog, annotated with this tenant's own enablement state —
    skills are opt-in per tenant, so "is this on" is never meaningful
    without also saying "on for whom"."""
    skills = await crud.list_skills(db)
    enablements = await crud.list_enablements(db)
    result = []
    for skill in skills:
        enablement = enablements.get(skill.skill_id)
        result.append(
            SkillEnablementOut(
                skill_id=skill.skill_id,
                name=skill.name,
                description=skill.description,
                connector=skill.connector,
                enabled=enablement.enabled if enablement else False,
                config=enablement.config if enablement else {},
            )
        )
    return result


@router.put("/skills/{skill_id}/enablement", response_model=SkillEnablementOut)
async def set_skill_enablement(
    skill_id: str,
    data: SkillEnablementUpdate,
    request: Request,
    principal: Principal = Depends(admin_auth),
    publisher: Publisher = Depends(get_publisher),
    db: AsyncSession = Depends(get_db),
):
    skill = await crud.get_skill(db, skill_id)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown skill")

    enablement = await crud.set_enablement(db, skill_id, enabled=data.enabled, config=data.config)

    event = AuditEvent(
        tenant_id=principal.tenant_id,
        actor_employee_id=principal.employee_id,
        action="skill.enablement_changed",
        target_type="skill",
        target_id=skill_id,
        metadata={"enabled": data.enabled},
    )
    schedule_publish(
        request.app.state, publisher, ROUTING_KEY_AUDIT, event.model_dump_json().encode()
    )
    return SkillEnablementOut(
        skill_id=skill.skill_id,
        name=skill.name,
        description=skill.description,
        connector=skill.connector,
        enabled=enablement.enabled,
        config=enablement.config,
    )


@router.get("/tools", response_model=list[ToolOut])
async def list_available_tools(
    principal: Principal = Depends(user_auth),
    db: AsyncSession = Depends(get_db),
):
    """Tools OpenClaw Runtime can offer the LLM for *this* employee right
    now: the tenant has to have turned the skill on, and this specific
    employee has to have actually connected their own account to it.
    Agent Registry's per-agent `skills` allowlist is a further filter
    OpenClaw applies on top of this list — this endpoint doesn't know
    about agents at all, by design.
    """
    enablements = await crud.list_enablements(db)
    enabled_skill_ids = {skill_id for skill_id, e in enablements.items() if e.enabled}
    if not enabled_skill_ids:
        return []

    tools: list[ToolOut] = []
    for skill_id in enabled_skill_ids:
        connector = CONNECTOR_REGISTRY.get(skill_id)
        if connector is None:
            continue
        connection = await crud.get_connection(db, principal.employee_id, skill_id)
        if connection is None:
            continue  # tenant enabled it, but this employee hasn't connected their own account
        for spec in connector.tool_specs():
            tools.append(
                ToolOut(
                    skill_id=skill_id,
                    name=spec.name,
                    description=spec.description,
                    input_schema=spec.input_schema,
                )
            )
    return tools
