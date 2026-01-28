const { app, BrowserWindow } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

// Keep a global reference of the window object, if you don't, the window will
// be closed automatically when the JavaScript object is garbage collected.
let mainWindow
let pythonProcess

const isDev = !app.isPackaged
const PY_DIST_FOLDER = 'dist-python'
const PY_FOLDER = '..'
const PY_MODULE = 'backend/wsgi.py'

function getPythonScriptPath() {
    if (!isDev) {
        return path.join(process.resourcesPath, PY_DIST_FOLDER, 'web_server.exe')
    }
    return path.join(__dirname, '..', '..', PY_MODULE)
}

function startPythonSubprocess() {
    let script = getPythonScriptPath()

    if (isDev) {
        console.log('Starting Python (Dev Mode):', script)
        pythonProcess = spawn('python', [script], {
            cwd: path.join(__dirname, '..', '..'), // Project root
            detached: false
        })
    } else {
        console.log('Starting Python (Prod Mode):', script)
        pythonProcess = spawn(script, [], {
            detached: false
        })
    }

    if (pythonProcess != null) {
        console.log('Python process started. Pid: ' + pythonProcess.pid)
        pythonProcess.stdout.on('data', (data) => {
            console.log(`Python: ${data}`)
        })
        pythonProcess.stderr.on('data', (data) => {
            console.error(`Python Error: ${data}`)
        })
    }
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1300,
        height: 900,
        webPreferences: {
            nodeIntegration: true, // For simplicity in migration; consider contextBridge later
            contextIsolation: false,
            preload: path.join(__dirname, 'preload.cjs')
        },
        icon: path.join(__dirname, 'icon.png') // TODO: Add icon
    })

    // Start Python backend
    startPythonSubprocess()

    if (isDev) {
        // In dev, wait for Vite to start? Or assume it's running via concurrently
        mainWindow.loadURL('http://localhost:5173')
        mainWindow.webContents.openDevTools()
    } else {
        mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
    }

    mainWindow.on('closed', function () {
        mainWindow = null
    })
}

app.on('ready', createWindow)

app.on('window-all-closed', function () {
    if (pythonProcess) {
        pythonProcess.kill()
    }
    if (process.platform !== 'darwin') app.quit()
})

app.on('activate', function () {
    if (mainWindow === null) createWindow()
})

app.on('will-quit', function () {
    if (pythonProcess) {
        pythonProcess.kill()
    }
})
