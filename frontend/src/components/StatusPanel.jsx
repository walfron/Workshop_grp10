const THREATS = {
  normal: { label: 'Normal', tone: 'ok' },
  warning: { label: 'Vigilance', tone: 'warning' },
  critical: { label: 'Critique', tone: 'critical' },
}

function StatusTile({ label, value, tone }) {
  return (
    <div className={`status-tile tone-${tone}`}>
      <span className="status-label">{label}</span>
      <span className="status-value">
        <span className="dot" />
        {value}
      </span>
    </div>
  )
}

export default function StatusPanel({ linkUp, deviceOnline, presence, threatLevel }) {
  const threat = THREATS[threatLevel]

  return (
    <section className="status-panel">
      <StatusTile label="Liaison serveur" value={linkUp ? 'Connectée' : 'Coupée'} tone={linkUp ? 'ok' : 'critical'} />
      <StatusTile label="Boîtier Sentinel-X" value={deviceOnline ? 'En ligne' : 'Hors ligne'} tone={deviceOnline ? 'ok' : 'critical'} />
      <StatusTile label="Présence (PIR)" value={presence ? 'Détectée' : 'Aucune'} tone={presence ? 'warning' : 'ok'} />
      <StatusTile label="Niveau d'alerte" value={threat.label} tone={threat.tone} />
    </section>
  )
}
