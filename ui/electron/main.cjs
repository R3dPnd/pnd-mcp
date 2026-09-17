'use strict'

const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')

const isDev = process.env.NODE_ENV === 'development'
const BACKEND_PORT = 8000
const DEV_PORT = 3000

let mainWindow = null
let backendProcess = null

// Poll GET /health until it responds 200 or we run out of retries
function waitForBackend (retries = 40, interval = 500) {
  return new Promise((resolve, reject) => {
    const attempt = (n) => {
      http.get(`http://127.0.0.1:${BACKEND_PORT}/health`, (res) => {
        if (res.statusCode === 200) return resolve()
        retry(n)
      }).on('error', () => retry(n))
    }
    const retry = (n) => {
      if (n <= 0) return reject(new Error('Backend did not start in time'))
      setTimeout(() => attempt(n - 1), interval)
    }
    attempt(retries)
  })
}

function startBackend () {
  // __dirname is <persona-repo>/runtime/ui/electron — this file (main.cjs)
  // lives inside the pnd-mcp runtime/ submodule, but the shared venv and
  // config.yaml live one level further up, in the *persona* repo's root
  // (same convention dann.py and config.yaml's mcp.servers[].command use
  // elsewhere — see dann-of-thursday/CLAUDE.md). cwd stays at runtime/ so
  // `app.main:app` resolves; only the venv/config lookups reach up further.
  const runtimeRoot = path.join(__dirname, '..', '..')
  const personaRoot = path.join(runtimeRoot, '..')
  const venvBin = process.platform === 'win32' ? 'Scripts' : 'bin'
  const venvPython = process.platform === 'win32' ? 'python.exe' : 'python'
  const python = path.join(personaRoot, '.venv', venvBin, venvPython)

  backendProcess = spawn(
    python,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    {
      cwd: runtimeRoot,
      windowsHide: true,
      env: { ...process.env, DANN_CONFIG_PATH: path.join(personaRoot, 'config.yaml') },
    }
  )

  backendProcess.stdout.on('data', (d) => process.stdout.write(d))
  backendProcess.stderr.on('data', (d) => process.stderr.write(d))
  backendProcess.on('error', (err) => console.error('[electron] Backend spawn error:', err.message))
}

function killBackend () {
  if (!backendProcess) return
  backendProcess.kill()
  backendProcess = null
}

async function createWindow () {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    fullscreen: process.env.DANN_FULLSCREEN === '1',
    backgroundColor: '#09090b', // zinc-950 — prevents white flash before React loads
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: 'Dann of Thursday',
  })

  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.on('closed', () => { mainWindow = null })

  if (isDev) {
    // Dev: load Vite dev server (hot reload). Start Python backend manually.
    mainWindow.loadURL(`http://localhost:${DEV_PORT}`)
    mainWindow.webContents.openDevTools()
  } else {
    // Prod: spawn the Python backend then load it
    startBackend()
    try {
      await waitForBackend()
    } catch (err) {
      console.error('[electron] Backend failed to start:', err.message)
    }
    mainWindow.loadURL(`http://localhost:${BACKEND_PORT}`)
  }
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  killBackend()
  app.quit()
})

app.on('before-quit', killBackend)
