import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { config } from './config.js'

mkdirSync(dirname(config.dbPath), { recursive: true })
const db = new DatabaseSync(config.dbPath)

db.exec(`
  CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    temperature REAL,
    humidity REAL,
    gas REAL,
    presence INTEGER NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry (ts);

  CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    level TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL
  );
`)

const insertTelemetry = db.prepare(
  'INSERT INTO telemetry (ts, device_id, temperature, humidity, gas, presence) VALUES (?, ?, ?, ?, ?, ?)',
)
const selectTelemetry = db.prepare(
  'SELECT ts, device_id, temperature, humidity, gas, presence FROM telemetry ORDER BY ts DESC LIMIT ?',
)
const insertAlert = db.prepare('INSERT INTO alerts (ts, level, source, message) VALUES (?, ?, ?, ?)')
const selectAlerts = db.prepare('SELECT id, ts, level, source, message FROM alerts ORDER BY id DESC LIMIT ?')

export function saveTelemetry(t) {
  insertTelemetry.run(t.ts, t.device_id, t.temperature, t.humidity, t.gas, t.presence ? 1 : 0)
}

export function recentTelemetry(limit) {
  return selectTelemetry.all(limit).reverse().map((row) => ({ ...row, presence: row.presence === 1 }))
}

export function saveAlert(alert) {
  const { lastInsertRowid } = insertAlert.run(alert.ts, alert.level, alert.source, alert.message)
  return { id: Number(lastInsertRowid), ...alert }
}

export function recentAlerts(limit) {
  return selectAlerts.all(limit).map((row) => ({ ...row }))
}
