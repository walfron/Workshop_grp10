const isHealthy = ({ state, health }) => state === 'running' && (health === null || health === 'healthy')

export default function ContainerList({ containers }) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>Conteneurs Docker</h2>
        <span className="muted">{containers.length}</span>
      </div>
      {containers.length === 0 ? (
        <p className="card-body muted">Aucun conteneur signalé</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Nom</th>
              <th>État</th>
              <th>Redémarrages</th>
            </tr>
          </thead>
          <tbody>
            {containers.map((container, index) => (
              <tr key={`${container.name}-${index}`}>
                <td>{container.name ?? '—'}</td>
                <td>
                  <span className={`badge ${isHealthy(container) ? 'ok' : 'critical'}`}>
                    <span className="dot" />
                    {[container.state, container.health].filter(Boolean).join(', ') || '—'}
                  </span>
                </td>
                <td>{Number.isFinite(container.restarts) ? container.restarts : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
