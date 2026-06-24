'use client'
import { useEffect, useRef, useState, useCallback } from 'react'

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'
const SS_PREFIX = '__ws_'
const MAX_CACHED = 100

function ssRead<T>(path: string): T[] {
  if (typeof sessionStorage === 'undefined') return []
  try { return JSON.parse(sessionStorage.getItem(SS_PREFIX + path) ?? '[]') } catch { return [] }
}

function ssWrite<T>(path: string, data: T[]): void {
  if (typeof sessionStorage === 'undefined') return
  try { sessionStorage.setItem(SS_PREFIX + path, JSON.stringify(data.slice(0, MAX_CACHED))) } catch {}
}

export function useWebSocket<T>(path: string) {
  const [messages, setMessages] = useState<T[]>([])
  const [connected, setConnected] = useState(false)
  const ws = useRef<WebSocket | null>(null)
  const retryTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Restore from sessionStorage after hydration (can't do it in useState — SSR mismatch)
  useEffect(() => {
    const stored = ssRead<T>(path)
    if (stored.length > 0) setMessages(stored)
  }, [path])

  const connect = useCallback(() => {
    if (typeof window === 'undefined') return
    const socket = new WebSocket(`${WS_BASE}${path}`)
    ws.current = socket

    socket.onopen = () => setConnected(true)
    socket.onclose = () => {
      setConnected(false)
      retryTimeout.current = setTimeout(connect, 3000)
    }
    socket.onerror = () => socket.close()
    socket.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as T
        setMessages((prev) => {
          const next = [data, ...prev].slice(0, 200)
          ssWrite(path, next)
          return next
        })
      } catch {}
    }
  }, [path])

  useEffect(() => {
    connect()
    return () => {
      ws.current?.close()
      if (retryTimeout.current) clearTimeout(retryTimeout.current)
    }
  }, [connect])

  return { messages, connected }
}
