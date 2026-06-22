'use client'
import { useWebSocket } from './useWebSocket'
import type { Alert } from '@/lib/types'

export function useAlerts() {
  return useWebSocket<Alert>('/ws/alerts')
}
