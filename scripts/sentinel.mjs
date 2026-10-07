import { spawn, spawnSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { connect } from 'node:net'
import { dirname, join } from 'node:path'
import { setTimeout as sleep } from 'node:timers/promises'

const ROOT = join(import.meta.dirname, '..')
const PID_FILE = join(ROOT, '.run', 'pids.json')
const HEALTH_URL = 'http://localhost:3000/api/v1/health'
const MIN_NODE = { major: 22, minor: 13 }
const isWindows = process.platform === 'win32'

const APPS = [
  { name: 'back', dir: 'backend', port: 3000, envExample: '.env.example', envFile: '.env', run: 'npm start' },
  { name: 'front', dir: 'frontend', port: 5173, envExample: '.env.example', envFile: '.env.local', run: 'npm run dev -- --strictPort' },
]

const ok = (message) => console.log(`[ok] ${message}`)
const warn = (message) => console.log(`[!]  ${message}`)
function fail(message) {
  console.error(`[x]  ${message}`)
  process.exit(1)
}

const commands = { setup, start, stop }
const command = commands[process.argv[2]]
if (!command) fail('Usage : npm run setup | npm start | npm run stop')
await command()

async function setup() {
  checkNode()
  for (const app of APPS) {
    const dir = join(ROOT, app.dir)
    console.log(`\nInstallation de ${app.dir}...`)
    const install = spawnSync('npm install --no-audit --no-fund', { cwd: dir, stdio: 'inherit', shell: true })
    if (install.status !== 0) fail(`Échec de l'installation de ${app.dir}`)

    if (!existsSync(join(dir, app.envFile))) {
      copyFileSync(join(dir, app.envExample), join(dir, app.envFile))
      ok(`${app.dir}/${app.envFile} créé à partir de ${app.envExample}`)
    }
  }

  const backendEnv = readFileSync(join(ROOT, 'backend', '.env'), 'utf8')
  if (/^MQTT_PASSWORD=\s*$/m.test(backendEnv)) {
    warn('MQTT_PASSWORD est vide dans backend/.env : mets le mot de passe du compte backend (donné par l\'Infra)')
  }
  ok('Installation terminée. Lance le projet avec : npm start')
}

async function start() {
  checkNode()
  for (const app of APPS) {
    if (!existsSync(join(ROOT, app.dir, 'node_modules'))) fail(`${app.dir} n'est pas installé : lance d'abord npm run setup`)
    if (!existsSync(join(ROOT, app.dir, app.envFile))) fail(`${app.dir}/${app.envFile} manquant : lance d'abord npm run setup`)
    if (await isPortUsed(app.port)) fail(`Le port ${app.port} est déjà utilisé (${app.name} déjà lancé ?) : lance npm run stop`)
  }

  const children = APPS.map(launch)
  const pids = children.map((child) => child.pid)
  mkdirSync(dirname(PID_FILE), { recursive: true })
  writeFileSync(PID_FILE, JSON.stringify(pids))

  const shutdown = () => {
    killAll(pids)
    rmSync(PID_FILE, { force: true })
    process.exit(0)
  }
  process.on('SIGINT', shutdown)
  process.on('SIGTERM', shutdown)

  let running = children.length
  children.forEach((child) =>
    child.on('exit', () => {
      running -= 1
      if (running === 0) shutdown()
    }),
  )

  await reportReadiness()
}

async function stop() {
  if (!existsSync(PID_FILE)) {
    const busyPorts = []
    for (const app of APPS) if (await isPortUsed(app.port)) busyPorts.push(app.port)
    if (busyPorts.length === 0) ok('Rien ne tourne')
    else warn(`Aucun lancement via npm start, mais les ports ${busyPorts.join(', ')} sont occupés : ferme ces terminaux avec Ctrl+C`)
    return
  }

  killAll(JSON.parse(readFileSync(PID_FILE, 'utf8')))
  rmSync(PID_FILE, { force: true })
  ok('Front et back arrêtés')
}

function checkNode() {
  const [major, minor] = process.versions.node.split('.').map(Number)
  const tooOld = major < MIN_NODE.major || (major === MIN_NODE.major && minor < MIN_NODE.minor)
  if (tooOld) fail(`Node.js ${MIN_NODE.major}.${MIN_NODE.minor} minimum requis (installé : ${process.versions.node})`)
  ok(`Node.js ${process.versions.node}`)
}

function launch({ name, dir, run }) {
  const child = spawn(run, { cwd: join(ROOT, dir), shell: true, detached: !isWindows, stdio: ['ignore', 'pipe', 'pipe'] })
  const printLines = (chunk) =>
    chunk.toString().split(/\r?\n/).filter(Boolean).forEach((line) => console.log(`[${name}] ${line}`))
  child.stdout.on('data', printLines)
  child.stderr.on('data', printLines)
  child.on('exit', (code) => console.log(`[${name}] arrêté (code ${code ?? 'signal'})`))
  return child
}

function killAll(pids) {
  for (const pid of pids) {
    if (isWindows) {
      spawnSync(`taskkill /PID ${pid} /T /F`, { shell: true, stdio: 'ignore' })
      continue
    }
    try {
      process.kill(-pid, 'SIGTERM')
    } catch (error) {
      if (error.code !== 'ESRCH') throw error
    }
  }
}

async function isPortUsed(port) {
  const canConnect = (host) =>
    new Promise((resolve) => {
      const socket = connect({ port, host })
      socket.once('connect', () => {
        socket.destroy()
        resolve(true)
      })
      socket.once('error', () => resolve(false))
    })
  return (await canConnect('127.0.0.1')) || (await canConnect('::1'))
}

async function reportReadiness() {
  for (let second = 0; second < 30; second++) {
    await sleep(1000)
    const health = await fetch(HEALTH_URL).then((response) => response.json()).catch(() => null)
    if (!health) continue
    if (!health.mqtt && second < 10) continue

    if (health.mqtt) ok('Backend prêt et connecté au broker MQTT')
    else warn('Backend prêt mais PAS connecté au broker : vérifie MQTT_URL, le mot de passe et le réseau Wi-Fi')
    ok('Dashboard : http://localhost:5173   (Ctrl+C ici ou npm run stop pour tout arrêter)')
    return
  }
  warn('Le backend ne répond pas après 30 s : regarde les messages [back] ci-dessus')
}
