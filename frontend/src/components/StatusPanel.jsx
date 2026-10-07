import StatusTile from './StatusTile.jsx'

const THREATS = {
  normal: { label: 'Normal', tone: 'ok' },
  warning: { label: 'Vigilance', tone: 'warning' },
  critical: { label: 'Critique', tone: 'critical' },
}

export default function StatusPanel({ linkUp, deviceOnline, presence, threatLevel }) {
  const threat = THREATS[threatLevel]

  return (
    <div className="tiles">
      <StatusTile label="Liaison serveur" value={linkUp ? 'Connectée' : 'Coupée'} tone={linkUp ? 'ok' : 'critical'} />
      <StatusTile label="Boîtier" value={deviceOnline ? 'En ligne' : 'Hors ligne'} tone={deviceOnline ? 'ok' : 'critical'} />
      <StatusTile label="Présence" value={presence ? 'Détectée' : 'Aucune'} tone={presence ? 'warning' : 'ok'} />
      <StatusTile label="Niveau d'alerte" value={threat.label} tone={threat.tone} />
    </div>
  )
}
