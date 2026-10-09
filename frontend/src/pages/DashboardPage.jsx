import AlertsList from '../components/AlertsList.jsx'
import ChartCard from '../components/ChartCard.jsx'
import ControlPanel from '../components/ControlPanel.jsx'
import PageHeader from '../components/PageHeader.jsx'
import StatusPanel from '../components/StatusPanel.jsx'
import WebcamPanel from '../components/WebcamPanel.jsx'

const METRICS = [
  { dataKey: 'temperature', title: 'Température', unit: '°C', digits: 1, padding: 1 },
  { dataKey: 'humidity', title: 'Humidité', unit: '%', digits: 1, padding: 5 },
  { dataKey: 'gas', title: 'Gaz / fumée', unit: '', digits: 0, padding: 10 },
]

export default function DashboardPage({ latest, history, alerts, linkUp, deviceOnline, presence, threatLevel, actuators, sendCommand }) {
  return (
    <>
      <PageHeader title="Dashboard" />
      <StatusPanel linkUp={linkUp} deviceOnline={deviceOnline} presence={presence} threatLevel={threatLevel} />
      <div className="charts">
        {METRICS.map((metric) => (
          <ChartCard key={metric.dataKey} {...metric} history={history} value={latest?.[metric.dataKey]} />
        ))}
      </div>
      <div className="split">
        <WebcamPanel />
        <div className="stack">
          <ControlPanel actuators={actuators} onCommand={sendCommand} disabled={!linkUp} />
          <AlertsList alerts={alerts} />
        </div>
      </div>
    </>
  )
}
