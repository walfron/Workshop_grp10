import { formatTime } from '../utils/format.js'

const LEVEL_LABELS = { info: 'Info', warning: 'Alerte', critical: 'Critique' }

export default function AlertsList({ alerts }) {
  return (
    <section className="card">
      <header className="card-header">
        <h2>Journal des événements</h2>
        <span className="muted">{alerts.length}</span>
      </header>
      {alerts.length === 0 ? (
        <p className="placeholder">Aucun événement pour l'instant</p>
      ) : (
        <ul className="alerts">
          {alerts.map((alert) => (
            <li key={alert.id} className={`alert level-${alert.level}`}>
              <span className="alert-time">{formatTime(alert.ts)}</span>
              <span className="alert-level">{LEVEL_LABELS[alert.level] ?? alert.level}</span>
              <span className="alert-message">
                {alert.message} <span className="muted">· {alert.source}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
