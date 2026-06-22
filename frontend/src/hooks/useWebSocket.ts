'use client'
import { useEffect, useRef, useState, useCallback } from 'react'

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export function useWebSocket<T>(path: string) {
  const [messages, setMessages] = useState<T[]>([])
  const [connected, setConnected] = useState(false)
  const ws = useRef<WebSocket | null>(null)
  const retryTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

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
        setMessages((prev) => [data, ...prev].slice(0, 200))
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
