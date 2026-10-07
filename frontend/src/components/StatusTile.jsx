export default function StatusTile({ label, value, tone, detail }) {
  return (
    <div className={`status-tile tone-${tone}`}>
      <span className="status-label">{label}</span>
      <span className="status-value">
        <span className="dot" />
        {value}
      </span>
      {detail && <span className="status-detail">{detail}</span>}
    </div>
  )
}
