import mqtt from 'mqtt'
import { config, topics } from './config.js'
import { createAlert, handleTelemetry, updateActuators } from './device.js'

const ACTUATORS = ['buzzer', 'led_red', 'led_orange', 'led_green']
let client

const pickActuators = (payload) =>
  Object.fromEntries(ACTUATORS.filter((name) => typeof payload?.[name] === 'boolean').map((name) => [name, payload[name]]))

export function startMqtt() {
  client = mqtt.connect(config.mqttUrl, {
    username: config.mqttUsername,
    password: config.mqttPassword,
    reconnectPeriod: 2000,
  })

  client.on('connect', () => {
    console.log(`[mqtt] connecté à ${config.mqttUrl}`)
    client.subscribe([topics.telemetry, topics.state])
  })
  client.on('error', (error) => console.error('[mqtt]', error.message))
  client.on('message', (topic, buffer) => {
    let data
    try {
      data = JSON.parse(buffer)
    } catch {
      return console.warn(`[mqtt] JSON invalide sur ${topic}`)
    }
    if (data === null || typeof data !== 'object') return

    if (topic === topics.telemetry) handleTelemetry(data)
    if (topic === topics.state) updateActuators(pickActuators(data))
  })
}

export const isMqttConnected = () => Boolean(client?.connected)

export function sendCommand(payload) {
  const command = pickActuators(payload)
  if (Object.keys(command).length === 0) return { status: 400, error: 'Aucune commande valide' }
  if (!isMqttConnected()) return { status: 503, error: 'Broker MQTT injoignable' }

  client.publish(topics.command, JSON.stringify(command), { qos: 1 })
  updateActuators(command)
  createAlert('info', 'dashboard', `Commande envoyée : ${JSON.stringify(command)}`)
  return { status: 200, command }
}
