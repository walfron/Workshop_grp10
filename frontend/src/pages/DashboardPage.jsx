import AlertsList from '../components/AlertsList.jsx'
import ChartCard from '../components/ChartCard.jsx'
import ControlPanel from '../components/ControlPanel.jsx'
import StatusPanel from '../components/StatusPanel.jsx'
import WebcamPanel from '../components/WebcamPanel.jsx'

const METRICS = [
  { dataKey: 'temperature', title: 'Température', unit: '°C', color: '#f97316', digits: 1 },
  { dataKey: 'humidity', title: 'Humidité', unit: '%', color: '#38bdf8', digits: 1 },
  { dataKey: 'gas', title: 'Gaz / fumée (MQ-2)', unit: '', color: '#a78bfa', digits: 0 },
]

export default function DashboardPage({ latest, history, alerts, linkUp, deviceOnline, presence, threatLevel, actuators, sendCommand }) {
  return (
    <>
      <StatusPanel linkUp={linkUp} deviceOnline={deviceOnline} presence={presence} threatLevel={threatLevel} />
      <div className="grid">
        <div className="column">
          {METRICS.map((metric) => (
            <ChartCard key={metric.dataKey} {...metric} history={history} value={latest?.[metric.dataKey]} />
          ))}
        </div>
        <div className="column">
          <WebcamPanel />
          <ControlPanel actuators={actuators} onCommand={sendCommand} disabled={!linkUp} />
          <AlertsList alerts={alerts} />
        </div>
      </div>
    </>
  )
}
