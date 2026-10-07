import { WebSocket, WebSocketServer } from 'ws'
import { recentAlerts, recentTelemetry } from './db.js'
import { bus, device } from './device.js'
import { sendCommand } from './mqtt.js'
import { supervision } from './supervision.js'

export function startWebSocket(server) {
  const wss = new WebSocketServer({ server, path: '/ws', maxPayload: 4096 })

  const send = (socket, message) => {
    if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message))
  }
  const broadcast = (message) => wss.clients.forEach((socket) => send(socket, message))

  bus.on('telemetry', (telemetry) => broadcast({ type: 'telemetry', ...telemetry }))
  bus.on('alert', (alert) => broadcast({ type: 'alert', ...alert }))
  bus.on('actuators', (state) => broadcast({ type: 'actuators', state }))
  bus.on('system', (system) => broadcast({ type: 'system', system }))
  bus.on('monitorAlerts', (alerts) => broadcast({ type: 'monitorAlerts', alerts }))

  wss.on('connection', (socket) => {
    send(socket, {
      type: 'snapshot',
      telemetry: recentTelemetry(60),
      alerts: recentAlerts(50),
      actuators: device.actuators,
      system: supervision.system,
      monitorAlerts: supervision.alerts,
    })

    socket.on('message', (raw) => {
      try {
        const message = JSON.parse(raw)
        if (message.type !== 'command') return
        const { error } = sendCommand(message.payload)
        if (error) send(socket, { type: 'error', message: error })
      } catch {
        console.warn('[ws] message invalide ignoré')
      }
    })
  })
}
