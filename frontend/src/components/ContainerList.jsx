const isHealthy = ({ state, health }) => state === 'running' && (health === null || health === 'healthy')

export default function ContainerList({ containers }) {
  return (
    <section className="card">
      <header className="card-header">
        <h2>Conteneurs Docker</h2>
        <span className="muted">{containers.length}</span>
      </header>
      {containers.length === 0 ? (
        <p className="placeholder">Aucun conteneur signalé</p>
      ) : (
        <ul className="container-list">
          {containers.map((container, index) => (
            <li key={`${container.name}-${index}`} className={`tone-${isHealthy(container) ? 'ok' : 'critical'}`}>
              <span className="dot" />
              <span className="container-name">{container.name ?? '—'}</span>
              <span className="muted">{[container.state, container.health].filter(Boolean).join(' · ') || '—'}</span>
              <span className="muted">
                {Number.isFinite(container.restarts) ? `${container.restarts} redémarrage(s)` : '—'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
