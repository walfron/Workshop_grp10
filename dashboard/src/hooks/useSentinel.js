import { useEffect, useReducer, useRef, useState } from 'react'

const WS_URL = import.meta.env.VITE_BACKEND_WS || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`
const HISTORY_SIZE = 60
const MAX_ALERTS = 50
const OFFLINE_AFTER_MS = 5000
const ALERT_WINDOW_MS = 30000

const initialState = { latest: null, history: [], alerts: [], linkUp: false, actuators: {} }

function reducer(state, message) {
  switch (message.type) {
    case 'link':
      return { ...state, linkUp: message.connected }
    case 'snapshot':
      return {
        ...state,
        history: message.telemetry,
        latest: message.telemetry.at(-1) ?? null,
        alerts: message.alerts,
        actuators: message.actuators,
      }
    case 'telemetry':
      return { ...state, latest: message, history: [...state.history, message].slice(-HISTORY_SIZE) }
    case 'alert':
      return { ...state, alerts: [message, ...state.alerts].slice(0, MAX_ALERTS) }
    case 'actuators':
      return { ...state, actuators: message.state }
    default:
      return state
  }
}

function getThreatLevel(alerts, presence, now) {
  const recent = alerts.filter((alert) => now - alert.ts < ALERT_WINDOW_MS)
  if (recent.some((alert) => alert.level === 'critical')) return 'critical'
  if (presence || recent.some((alert) => alert.level === 'warning')) return 'warning'
  return 'normal'
}

function toErrorAlert(message) {
  const ts = Date.now()
  return { type: 'alert', id: `erreur-${ts}`, ts, level: 'critical', source: 'backend', message }
}

export function useSentinel() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [now, setNow] = useState(() => Date.now())
  const socket = useRef(null)

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    let retryTimer

    const open = () => {
      const ws = new WebSocket(WS_URL)
      socket.current = ws
      ws.onopen = () => dispatch({ type: 'link', connected: true })
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data)
        dispatch(message.type === 'error' ? toErrorAlert(message.message) : message)
      }
      ws.onclose = () => {
        dispatch({ type: 'link', connected: false })
        retryTimer = setTimeout(open, 2000)
      }
    }

    open()
    return () => {
      clearTimeout(retryTimer)
      socket.current.onclose = null
      socket.current.close()
    }
  }, [])

  const sendCommand = (payload) => {
    if (socket.current?.readyState === WebSocket.OPEN) {
      socket.current.send(JSON.stringify({ type: 'command', payload }))
    }
  }

  const deviceOnline = state.latest !== null && now - state.latest.ts < OFFLINE_AFTER_MS
  const presence = deviceOnline && state.latest.presence

  return {
    ...state,
    deviceOnline,
    presence,
    threatLevel: getThreatLevel(state.alerts, presence, now),
    sendCommand,
  }
}
