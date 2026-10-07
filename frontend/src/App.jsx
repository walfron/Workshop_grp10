import AlertsList from './components/AlertsList.jsx'
import ChartCard from './components/ChartCard.jsx'
import ControlPanel from './components/ControlPanel.jsx'
import StatusPanel from './components/StatusPanel.jsx'
import WebcamPanel from './components/WebcamPanel.jsx'
import { useSentinel } from './hooks/useSentinel.js'
import './App.css'

const METRICS = [
  { dataKey: 'temperature', title: 'Température', unit: '°C', color: '#f97316', digits: 1 },
  { dataKey: 'humidity', title: 'Humidité', unit: '%', color: '#38bdf8', digits: 1 },
  { dataKey: 'gas', title: 'Gaz / fumée (MQ-2)', unit: '', color: '#a78bfa', digits: 0 },
]

export default function App() {
  const { latest, history, alerts, linkUp, deviceOnline, presence, threatLevel, actuators, sendCommand } = useSentinel()

  return (
    <div className="app">
      <header className="topbar">
        <h1>SENTINEL-X</h1>
      </header>

      <StatusPanel
        linkUp={linkUp}
        deviceOnline={deviceOnline}
        presence={presence}
        threatLevel={threatLevel}
      />

      <main className="grid">
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
      </main>
    </div>
  )
}
