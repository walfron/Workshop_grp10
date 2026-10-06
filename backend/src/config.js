const env = (name, fallback) => process.env[name] || fallback
const prefix = env('MQTT_TOPIC_PREFIX', 'sentinel/g10')

export const config = {
  port: Number(env('PORT', 3000)),
  dbPath: env('DB_PATH', './data/sentinel.db'),
  apiKey: env('API_KEY', null),
  offlineAfterMs: Number(env('OFFLINE_AFTER_MS', 10000)),
  mqttUrl: env('MQTT_URL', 'mqtt://localhost:1883'),
  mqttUsername: env('MQTT_USERNAME'),
  mqttPassword: env('MQTT_PASSWORD'),
  embeddedBroker: env('EMBEDDED_BROKER') === 'true',
  embeddedBrokerPort: Number(env('EMBEDDED_BROKER_PORT', 1883)),
}

export const topics = {
  telemetry: `${prefix}/telemetry`,
  command: `${prefix}/cmd`,
  state: `${prefix}/state`,
}
