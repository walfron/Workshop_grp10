import ContainerList from '../components/ContainerList.jsx'
import ServerInfo from '../components/ServerInfo.jsx'

export default function ServerPage({ system, monitorAlerts, supervisionOnline }) {
  if (!system) {
    return <p className="banner tone-warning">En attente des données de supervision du serveur…</p>
  }

  return (
    <>
      {!supervisionOnline && (
        <p className="banner tone-critical">Supervision hors ligne : aucune donnée du serveur depuis plus de 90 s</p>
      )}
      {monitorAlerts.map((alert) => (
        <p key={alert.check} className="banner tone-warning">
          {alert.message}
        </p>
      ))}
      <ServerInfo system={system} />
      <ContainerList containers={system.containers} />
    </>
  )
}
