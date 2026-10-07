import { createServer } from 'node:http'
import { createServer as createTcpServer } from 'node:net'
import { resolve } from 'node:path'
import { Aedes } from 'aedes'
import express from 'express'
import { config } from './config.js'
import { watchDeviceOnline } from './device.js'
import { startMqtt } from './mqtt.js'
import { api } from './routes.js'
import { startWebSocket } from './ws.js'

if (config.embeddedBroker) {
  const broker = await Aedes.createBroker()
  broker.on('client', (client) => console.log(`[broker] ${client.id} connecté`))
  broker.on('clientDisconnect', (client) => console.log(`[broker] ${client.id} déconnecté`))
  createTcpServer(broker.handle).listen(config.embeddedBrokerPort)
}

const app = express()
app.disable('x-powered-by')
app.use(express.json({ limit: '10kb' }))
app.use('/api/v1', api)
app.use(express.static(resolve(import.meta.dirname, '../../dashboard/dist')))
app.use((error, req, res, next) => {
  if (!error.status) console.error(error)
  res.status(error.status ?? 500).json({ error: error.status ? 'Requête invalide' : 'Erreur interne' })
})

const server = createServer(app)
startWebSocket(server)
startMqtt()
watchDeviceOnline()

server.listen(config.port, () => console.log(`[http] API sur http://localhost:${config.port}/api/v1`))
