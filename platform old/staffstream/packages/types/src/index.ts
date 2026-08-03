// Core domain types — shared across all apps

export type DataClassification = 'public' | 'internal' | 'confidential' | 'restricted'
export type AutonomyMode = 'supervised' | 'trusted' | 'autonomous'
export type AgentStatus = 'provisioning' | 'active' | 'paused' | 'terminated'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired'
export type MessageType = 'REQUEST' | 'RESPONSE' | 'BROADCAST' | 'ESCALATION' | 'SUPERVISION'
export type TrustLevel = 'verified' | 'community' | 'experimental'

export interface AgentMessage {
  id: string
  type: MessageType
  fromAgentId: string
  toAgentId: string
  payload: Record<string, unknown>
  dataClassification: DataClassification
  timestamp: string
}

export interface ApprovalGate {
  actionCategory: string
  agentId: string
  description: string
  estimatedCost?: number
  timeoutHours: number
}

export interface OpenClawConfig {
  agentId: string
  roleId: string
  companyId: string
  systemPrompt: string
  skills: string[]
  mcpConnections: MCPConnectionRef[]
  messageBusChannels: {
    inbound: string
    outbound: string
  }
  llm: {
    provider: 'anthropic' | 'openai'
    model: string
    maxTokens: number
    costLimitUsd: number
  }
}

export interface MCPConnectionRef {
  name: string
  serverUrl: string
  tokenEndpoint: string   // internal endpoint that issues scoped tokens
}
