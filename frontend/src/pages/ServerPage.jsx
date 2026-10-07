import ContainerList from '../components/ContainerList.jsx'
import PageHeader from '../components/PageHeader.jsx'
import ServerInfo from '../components/ServerInfo.jsx'
import { formatTime } from '../utils/format.js'

export default function ServerPage({ system, monitorAlerts, supervisionOnline }) {
  const updatedAt = Date.parse(system?.ts)

  return (
    <>
      <PageHeader title="Serveur" description="Supervision du Raspberry Pi">
        {Number.isFinite(updatedAt) && <span className="muted">Mis à jour à {formatTime(updatedAt)}</span>}
      </PageHeader>
      {system ? (
        <>
          {!supervisionOnline && (
            <p className="notice critical">Supervision hors ligne : aucune donnée du serveur depuis plus de 90 s</p>
          )}
          {monitorAlerts.map((alert) => (
            <p key={alert.check} className="notice warning">
              {alert.message}
            </p>
          ))}
          <ServerInfo system={system} />
          <ContainerList containers={system.containers} />
        </>
      ) : (
        <p className="muted">En attente des données de supervision du serveur…</p>
      )}
    </>
  )
}
