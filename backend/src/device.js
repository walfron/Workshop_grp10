import { EventEmitter } from 'node:events'
import { config } from './config.js'
import { saveAlert, saveTelemetry } from './db.js'

export const bus = new EventEmitter()

export const device = {
  lastTelemetry: null,
  online: false,
  actuators: { buzzer: false, led_red: false, led_orange: false, led_green: false },
}

const toNumber = (value) => (Number.isFinite(value) ? value : null)

export function createAlert(level, source, message) {
  const alert = saveAlert({ ts: Date.now(), level, source, message })
  console.log(`[alerte] ${level} (${source}) ${message}`)
  bus.emit('alert', alert)
  return alert
}

export function handleTelemetry(data) {
  const telemetry = {
    ts: Date.now(),
    device_id: String(data.device_id ?? 'inconnu').slice(0, 64),
    temperature: toNumber(data.temperature),
    humidity: toNumber(data.humidity),
    gas: toNumber(data.gas),
    presence: data.presence === true || data.presence === 1,
  }
  const motionStarted = telemetry.presence && !device.lastTelemetry?.presence

  device.lastTelemetry = telemetry
  saveTelemetry(telemetry)
  bus.emit('telemetry', telemetry)
  if (motionStarted) createAlert('warning', 'pir', 'Mouvement détecté')
}

export function updateActuators(changes) {
  Object.assign(device.actuators, changes)
  bus.emit('actuators', device.actuators)
}

export function watchDeviceOnline() {
  setInterval(() => {
    const online = Date.now() - (device.lastTelemetry?.ts ?? 0) < config.offlineAfterMs
    if (online === device.online) return

    device.online = online
    if (online) createAlert('info', 'backend', 'Boîtier Sentinel-X connecté')
    else createAlert('critical', 'backend', 'Boîtier Sentinel-X hors ligne (plus aucune donnée)')
  }, 2000)
}
