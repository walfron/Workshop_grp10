import { bus, createAlert } from './device.js'

const MAX_CONTAINERS = 20

const number = (value) => (Number.isFinite(value) ? value : null)
const text = (value, maxLength = 64) => (typeof value === 'string' ? value.slice(0, maxLength) : null)

const activeAlerts = new Map()

export const supervision = {
  system: null,
  get alerts() {
    return [...activeAlerts.values()]
  },
}

function toContainer(container) {
  return {
    name: text(container?.name),
    state: text(container?.state, 16),
    health: text(container?.health, 16),
    restarts: number(container?.restarts),
  }
}

export function handleSystem(data) {
  supervision.system = {
    ts: text(data.ts, 40),
    host: text(data.host),
    uptime_s: number(data.uptime_s),
    cpu_pct: number(data.cpu_pct),
    load1: number(data.load1),
    mem_pct: number(data.mem_pct),
    mem_used_mb: number(data.mem_used_mb),
    mem_total_mb: number(data.mem_total_mb),
    temp_c: number(data.temp_c),
    throttled: text(data.throttled, 16),
    disk_pct: number(data.disk_pct),
    disk_free_gb: number(data.disk_free_gb),
    mqtt_clients: number(data.mqtt_clients),
    containers: Array.isArray(data.containers) ? data.containers.slice(0, MAX_CONTAINERS).map(toContainer) : [],
  }
  bus.emit('system', supervision.system)
}

export function handleMonitorAlert(data) {
  const check = text(data.check)
  if (data.source !== 'monitor' || !check) return

  const message = text(data.message, 200) ?? `Alerte ${check}`
  if (data.state === 'alert') {
    activeAlerts.set(check, { check, message, value: number(data.value), threshold: number(data.threshold), ts: text(data.ts, 40) })
    createAlert('warning', 'monitor', message)
  } else if (data.state === 'ok' && activeAlerts.delete(check)) {
    createAlert('info', 'monitor', `Retour à la normale : ${check}`)
  } else {
    return
  }
  bus.emit('monitorAlerts', supervision.alerts)
}
