const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  dashboard: {
    metrics: (tenantId: string) => get(`/api/dashboard/metrics?tenant_id=${tenantId}`),
  },
  agents: {
    list: (tenantId: string) => get(`/api/agents/?tenant_id=${tenantId}`),
    get: (id: string) => get(`/api/agents/${id}`),
  },
  alerts: {
    list: (tenantId: string, limit = 50) => get(`/api/alerts/?tenant_id=${tenantId}&limit=${limit}`),
  },
  audit: {
    list: (tenantId: string, limit = 50) => get(`/api/audit/?tenant_id=${tenantId}&limit=${limit}`),
  },
  killSwitch: {
    fire: (agentId: string, operatorId: string, reason: string, tenantId = 'default') =>
      post('/api/kill_switch/fire', { agent_id: agentId, operator_id: operatorId, reason, tenant_id: tenantId }),
    resume: (agentId: string, operatorId: string, reason: string, tenantId = 'default') =>
      post('/api/kill_switch/resume', { agent_id: agentId, operator_id: operatorId, reason, tenant_id: tenantId }),
    state: (agentId: string) => get(`/api/kill_switch/state/${agentId}`),
  },
  compliance: {
    generate: (body: { tenant_id: string; time_range_start: string; time_range_end: string; regulations: string[] }) =>
      post('/api/compliance/generate', body),
  },
}
