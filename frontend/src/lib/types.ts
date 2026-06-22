export type AgentState = 'active' | 'throttled' | 'paused' | 'terminated'
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical'
export type RequestStatus = 'passed' | 'blocked' | 'flagged' | 'error'

export interface Agent {
  id: string
  tenant_id: string
  name: string
  purpose_binding: string | null
  state: AgentState
  config: Record<string, unknown>
}

export interface Alert {
  id: string
  alert_type: string
  severity: AlertSeverity
  message: string
  agent_id: string | null
  created_at: string
}

export interface AuditEntry {
  id: number
  request_id: string
  action: string
  layer: number
  status: RequestStatus
  model: string | null
  regulation_mappings: Record<string, string[]>
  created_at: string
}

export interface DashboardMetrics {
  total_requests: number
  blocked_requests: number
  anomalies_flagged: number
  compliance_packages: number
  period_hours: number
}

export interface KillSwitchEvent {
  type: 'kill_switch_event'
  agent_id: string
  old_state: AgentState
  new_state: AgentState
  reason: string
  triggered_by: string
  operator_id: string | null
  timestamp: string
}

export interface LayerHealth {
  layer: number
  name: string
  throughput: number
  is_differentiator: boolean
}
