import mqtt from 'mqtt'

const prefix = process.env.MQTT_TOPIC_PREFIX || 'sentinel/1'
const client = mqtt.connect(process.env.MQTT_URL || 'mqtt://localhost:1883', {
  clientId: 'esp-simulateur',
  username: process.env.MQTT_USERNAME,
  password: process.env.MQTT_PASSWORD,
})

const sensors = { temperature: 23, humidity: 42, gas: 300, presence: false }
const actuators = { buzzer: false, led_red: false, led_green: true }
let gasSpikeTicks = 0

const drift = (amplitude) => (Math.random() - 0.5) * amplitude
const round1 = (value) => Math.round(value * 10) / 10

client.on('connect', () => {
  console.log(`[simu] connecté, publication sur ${prefix}/telemetry`)
  client.subscribe(`${prefix}/cmd`)
  client.publish(`${prefix}/state`, JSON.stringify(actuators))
})

client.on('message', (topic, buffer) => {
  console.log(`[simu] commande reçue : ${buffer}`)
  Object.assign(actuators, JSON.parse(buffer))
  client.publish(`${prefix}/state`, JSON.stringify(actuators))
})

setInterval(() => {
  if (gasSpikeTicks === 0 && Math.random() < 0.02) gasSpikeTicks = 12
  gasSpikeTicks = Math.max(0, gasSpikeTicks - 1)

  sensors.temperature += drift(0.2)
  sensors.humidity += drift(0.4)
  sensors.gas += ((gasSpikeTicks > 0 ? 650 : 300) - sensors.gas) * 0.3 + drift(10)
  if (Math.random() < 0.05) sensors.presence = !sensors.presence

  client.publish(`${prefix}/telemetry`, JSON.stringify({
    device_id: 'sentinelx-g10',
    temperature: round1(sensors.temperature),
    humidity: round1(sensors.humidity),
    gas: Math.round(sensors.gas),
    presence: sensors.presence,
  }))
}, 1000)
