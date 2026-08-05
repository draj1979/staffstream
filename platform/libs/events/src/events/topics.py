"""One topic exchange, one routing key + queue name per event type.
Producers only need the exchange name + a routing key; only the consumer
(Analytics Service) needs the queue names."""

EXCHANGE_NAME = "staffstream.events"

ROUTING_KEY_LLM_USAGE = "llm.usage"
ROUTING_KEY_CHAT_INTERACTION = "chat.interaction"
ROUTING_KEY_SKILL_USAGE = "skill.usage"
ROUTING_KEY_AUDIT = "audit.logged"

QUEUE_LLM_USAGE = "analytics.llm_usage"
QUEUE_CHAT_INTERACTION = "analytics.chat_interaction"
QUEUE_SKILL_USAGE = "analytics.skill_usage"
QUEUE_AUDIT = "audit.logged"
