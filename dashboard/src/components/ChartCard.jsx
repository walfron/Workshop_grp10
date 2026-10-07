import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatTime } from '../utils/format.js'

const GRID_COLOR = '#1f2b38'
const AXIS_COLOR = '#8b9bab'
const TOOLTIP_STYLE = { background: '#121a23', border: `1px solid ${GRID_COLOR}`, borderRadius: 8 }

export default function ChartCard({ title, unit, color, dataKey, digits, history, value }) {
  return (
    <section className="card">
      <header className="card-header">
        <h2>{title}</h2>
        <span className="metric" style={{ color }}>
          {value == null ? '--' : value.toFixed(digits)} <small>{unit}</small>
        </span>
      </header>
      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={history} margin={{ top: 5, right: 10, bottom: 0, left: -10 }}>
            <CartesianGrid stroke={GRID_COLOR} vertical={false} />
            <XAxis dataKey="ts" tickFormatter={formatTime} stroke={AXIS_COLOR} fontSize={11} minTickGap={40} />
            <YAxis stroke={AXIS_COLOR} fontSize={11} domain={['auto', 'auto']} width={45} />
            <Tooltip labelFormatter={formatTime} formatter={(v) => [`${v} ${unit}`, title]} contentStyle={TOOLTIP_STYLE} />
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
