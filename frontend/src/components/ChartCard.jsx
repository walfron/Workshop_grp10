import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatTime } from '../utils/format.js'

const LINE_COLOR = '#b5703a'
const GRID_COLOR = '#ece2d5'
const AXIS_COLOR = '#a08a76'

export default function ChartCard({ title, unit, dataKey, digits, history, value }) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>{title}</h2>
      </div>
      <div className="card-body metric">
        <p className="metric-value">
          {value == null ? '—' : value.toFixed(digits)}
          <span className="muted">{unit}</span>
        </p>
        <div className="chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history} margin={{ top: 5, right: 5, bottom: 0, left: -15 }}>
              <CartesianGrid stroke={GRID_COLOR} vertical={false} />
              <XAxis dataKey="ts" tickFormatter={formatTime} stroke={AXIS_COLOR} fontSize={11} minTickGap={40} />
              <YAxis stroke={AXIS_COLOR} fontSize={11} domain={['auto', 'auto']} width={45} />
              <Tooltip labelFormatter={formatTime} formatter={(v) => [`${v} ${unit}`, title]} />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={LINE_COLOR}
                fill={LINE_COLOR}
                fillOpacity={0.12}
                strokeWidth={1.5}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  )
}
