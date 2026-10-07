import StatusTile from './StatusTile.jsx'

const THRESHOLDS = {
  cpu: { warning: 70, critical: 90 },
  ram: { warning: 70, critical: 85 },
  temp: { warning: 65, critical: 75 },
  disk: { warning: 70, critical: 85 },
}

const isNumber = (value) => Number.isFinite(value)

function toneFor(value, { warning, critical }) {
  if (!isNumber(value)) return 'unknown'
  if (value > critical) return 'critical'
  if (value >= warning) return 'warning'
  return 'ok'
}

const format = (value, unit = '', digits = 1) => (isNumber(value) ? `${value.toFixed(digits)}${unit}` : '—')

function formatUptime(seconds) {
  if (!isNumber(seconds)) return '—'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${days} j ${hours} h ${minutes} min`
}

function ramPercent({ mem_used_mb: used, mem_total_mb: total, mem_pct: fallback }) {
  return isNumber(used) && isNumber(total) && total > 0 ? (used / total) * 100 : fallback
}

const THROTTLE_FLAGS = [
  { mask: 0x1, value: 'Sous-tension', tone: 'critical' },
  { mask: 0x8, value: 'Limite thermique', tone: 'warning' },
  { mask: 0x6, value: 'Processeur bridé', tone: 'warning' },
  { mask: 0x10000, value: 'Sous-tension passée', tone: 'warning' },
  { mask: 0xe0000, value: 'Bridage passé', tone: 'warning' },
]

function powerStatus(throttled) {
  const flags = /^0x[0-9a-f]+$/i.test(throttled) ? Number.parseInt(throttled, 16) : NaN
  if (!isNumber(flags)) return { value: '—', tone: 'unknown' }
  return THROTTLE_FLAGS.find(({ mask }) => flags & mask) ?? { value: 'Normale', tone: 'ok' }
}

export default function ServerInfo({ system }) {
  const ram = ramPercent(system)
  const power = powerStatus(system.throttled)

  return (
    <section className="status-panel">
      <StatusTile label="CPU" value={format(system.cpu_pct, ' %')} tone={toneFor(system.cpu_pct, THRESHOLDS.cpu)} />
      <StatusTile
        label="RAM"
        value={format(ram, ' %')}
        tone={toneFor(ram, THRESHOLDS.ram)}
        detail={`${format(system.mem_used_mb, '', 0)} / ${format(system.mem_total_mb, ' Mo', 0)}`}
      />
      <StatusTile label="Température" value={format(system.temp_c, ' °C')} tone={toneFor(system.temp_c, THRESHOLDS.temp)} />
      <StatusTile
        label="Disque"
        value={format(system.disk_pct, ' %')}
        tone={toneFor(system.disk_pct, THRESHOLDS.disk)}
        detail={`${format(system.disk_free_gb, ' Go')} libres`}
      />
      <StatusTile
        label="Alimentation / bridage"
        value={power.value}
        tone={power.tone}
        detail={system.throttled && `code ${system.throttled}`}
      />
      <StatusTile
        label="Clients MQTT"
        value={format(system.mqtt_clients, '', 0)}
        tone={isNumber(system.mqtt_clients) ? 'ok' : 'unknown'}
      />
      <StatusTile
        label="Uptime"
        value={formatUptime(system.uptime_s)}
        tone={isNumber(system.uptime_s) ? 'ok' : 'unknown'}
      />
    </section>
  )
}
