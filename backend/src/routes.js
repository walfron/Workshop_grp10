import { Router } from 'express'
import { config } from './config.js'
import { recentAlerts, recentTelemetry } from './db.js'
import { createAlert, device } from './device.js'
import { isMqttConnected, sendCommand } from './mqtt.js'

const LEVELS = ['info', 'warning', 'critical']

const isText = (value, maxLength) => typeof value === 'string' && value.trim() !== '' && value.length <= maxLength

function parseLimit(value, fallback, max) {
  const limit = Number.parseInt(value, 10)
  return limit > 0 ? Math.min(limit, max) : fallback
}

function requireApiKey(req, res, next) {
  if (config.apiKey && req.get('X-API-Key') !== config.apiKey) {
    return res.status(401).json({ error: 'Clé API manquante ou invalide' })
  }
  next()
}

export const api = Router()

api.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    mqtt: isMqttConnected(),
    deviceOnline: device.online,
    lastTelemetryTs: device.lastTelemetry?.ts ?? null,
  })
})

api.get('/telemetry', (req, res) => res.json(recentTelemetry(parseLimit(req.query.limit, 60, 1000))))

api.get('/alerts', (req, res) => res.json(recentAlerts(parseLimit(req.query.limit, 50, 500))))

api.post('/alerts', requireApiKey, (req, res) => {
  const { level, message, source = 'externe' } = req.body ?? {}
  if (!LEVELS.includes(level)) {
    return res.status(400).json({ error: `level doit valoir ${LEVELS.join(', ')}` })
  }
  if (!isText(message, 200) || !isText(source, 32)) {
    return res.status(400).json({ error: 'message (1 à 200 caractères) et source (1 à 32) doivent être des textes' })
  }
  res.status(201).json(createAlert(level, source.trim(), message.trim()))
})

api.post('/commands', requireApiKey, (req, res) => {
  const { status, ...body } = sendCommand(req.body)
  res.status(status).json(body)
})
