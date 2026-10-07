import { formatTime } from '../utils/format.js'

const LEVEL_LABELS = { info: 'Info', warning: 'Alerte', critical: 'Critique' }

export default function AlertsList({ alerts }) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>Événements</h2>
        <span className="muted">{alerts.length}</span>
      </div>
      {alerts.length === 0 ? (
        <p className="card-body muted">Aucun événement pour l'instant</p>
      ) : (
        <div className="events">
          <table>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td className="muted">{formatTime(alert.ts)}</td>
                  <td>
                    <span className={`badge ${alert.level}`}>{LEVEL_LABELS[alert.level] ?? alert.level}</span>
                  </td>
                  <td>
                    {alert.message} <span className="muted">· {alert.source}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
