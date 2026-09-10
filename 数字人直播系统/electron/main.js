// electron/main.js —— 桌面壳：启动时拉起 Python 后端，等端口就绪后开窗口。
const { app, BrowserWindow, shell } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const net = require('net')
const fs = require('fs')

const PORT = 8000
// 打包后资源在 resources/（含 venv、src、.env），只读；可写数据（state.json/chroma_db/日志）放 userData。
const APP_ROOT = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..')
const DATA_DIR = app.isPackaged ? app.getPath('userData') : path.join(APP_ROOT, 'src')
const DEBUG_LOG = path.join(DATA_DIR, 'electron-debug.log')
const BACKEND_LOG = path.join(DATA_DIR, 'electron-backend.log')
let backend = null

try { fs.mkdirSync(DATA_DIR, { recursive: true }) } catch (e) {}

function debug(msg) {
  try { fs.appendFileSync(DEBUG_LOG, `[${new Date().toISOString()}] ${msg}\n`) } catch (e) {}
}
debug(`启动：packaged=${app.isPackaged} APP_ROOT=${APP_ROOT} DATA_DIR=${DATA_DIR}`)

function backendCommand() {
  return {
    py: path.join(APP_ROOT, 'venv', 'Scripts', 'python.exe'),
    orch: path.join(APP_ROOT, 'src', 'orchestrator.py'),
  }
}

function startBackend() {
  const { py, orch } = backendCommand()
  // 用 openSync 拿真 fd：createWriteStream 是异步打开，fd 一开始是 null，spawn 会报
  // "stdio is invalid"；同步打开就不会踩这个坑。
  const fd = fs.openSync(BACKEND_LOG, 'a')
  fs.writeSync(fd, `\n\n===== ${new Date().toLocaleString()} 启动后端 =====\n`)
  debug(`spawn: py存在=${fs.existsSync(py)} orch存在=${fs.existsSync(orch)}`)
  backend = spawn(py, ['-u', orch, '--web', '--port', String(PORT)], {
    cwd: APP_ROOT,  // .env 在 APP_ROOT 下（dev=项目根，打包=resources/），load_dotenv 从这里找
    env: { ...process.env, ADH_DATA_DIR: DATA_DIR },
    stdio: ['ignore', fd, fd],
    windowsHide: true,
  })
  debug('spawn 返回，pid=' + backend.pid)
  backend.on('exit', (code) => {
    debug('后端退出 code=' + code)
    try { fs.writeSync(fd, `[后端退出] code=${code}\n`) } catch (e) {}
    try { fs.closeSync(fd) } catch (e) {}
    backend = null
  })
  backend.on('error', (err) => {
    debug('后端启动失败: ' + err.message)
    try { fs.writeSync(fd, `[后端启动失败] ${err.message}\n`) } catch (e) {}
    try { fs.closeSync(fd) } catch (e) {}
    backend = null
  })
}

function waitForPort(timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const t0 = Date.now()
    const tryConnect = () => {
      const sock = net.connect(PORT, '127.0.0.1')
      sock.on('connect', () => { sock.destroy(); resolve() })
      sock.on('error', () => {
        sock.destroy()
        if (Date.now() - t0 > timeoutMs) {
          reject(new Error('后端启动超时，看日志：' + BACKEND_LOG))
        } else {
          setTimeout(tryConnect, 500)
        }
      })
    }
    tryConnect()
  })
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1080,
    height: 780,
    title: '动漫数字人',
    backgroundColor: '#0e0f13',
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  })
  win.loadURL(`http://localhost:${PORT}/app.html`)
  // 页面里 window.open / 外链一律交给系统浏览器，不在应用内开新窗
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
  return win
}

app.whenReady().then(async () => {
  try {
    startBackend()
    await waitForPort()
    await createWindow()
    debug('窗口已创建')
  } catch (e) {
    debug('启动失败: ' + (e && e.message ? e.message : e))
    const { dialog } = require('electron')
    dialog.showErrorBox('启动失败', String(e.message || e))
    app.quit()
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (backend) { try { backend.kill() } catch (e) {} }
  if (process.platform !== 'darwin') app.quit()
})

app.on('will-quit', () => {
  if (backend) { try { backend.kill() } catch (e) {} }
})
