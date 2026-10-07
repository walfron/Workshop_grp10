export default function StatusTile({ label, value, tone, detail }) {
  return (
    <div className="card tile">
      <span className="tile-label">
        <span className={`dot ${tone}`} />
        {label}
      </span>
      <strong className="tile-value">{value}</strong>
      {detail && <span className="muted">{detail}</span>}
    </div>
  )
}
