import { app, BrowserWindow, dialog, ipcMain } from 'electron';
import { spawn } from 'child_process';
import * as readline from 'readline';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// Sidecar state (mirrors Rust SidecarState)
const sidecar = {
    process: null,
    requestId: 0,
    lineQueue: [],
};
function findVenvPython() {
    let dir = __dirname;
    for (let i = 0; i < 10; i++) {
        const candidates = [
            path.join(dir, '.venv', 'Scripts', 'python.exe'), // Windows
            path.join(dir, '.venv', 'bin', 'python'), // Unix
        ];
        for (const candidate of candidates) {
            if (fs.existsSync(candidate))
                return candidate;
        }
        const parent = path.dirname(dir);
        if (parent === dir)
            break;
        dir = parent;
    }
    return 'python';
}
function startSidecar() {
    const isDev = !app.isPackaged;
    let command, args;
    if (isDev) {
        command = findVenvPython();
        args = ['-m', 'hypnoai.sidecar'];
    }
    else {
        command = path.join(process.resourcesPath, 'hypnoai-sidecar');
        args = [];
    }
    const child = spawn(command, args, { stdio: ['pipe', 'pipe', 'inherit'] });
    sidecar.process = child;
    const rl = readline.createInterface({ input: child.stdout, crlfDelay: Infinity });
    rl.on('line', (line) => {
        const resolver = sidecar.lineQueue.shift();
        if (resolver)
            resolver(line);
        else
            console.warn('[sidecar] Unexpected line:', line);
    });
    child.on('exit', (code) => {
        console.log('[sidecar] exited with code:', code);
        sidecar.process = null;
        while (sidecar.lineQueue.length) {
            sidecar.lineQueue.shift()(JSON.stringify({ error: { code: -32000, message: 'Sidecar exited' } }));
        }
    });
}
function nextId() { return ++sidecar.requestId; }
function writeRequest(method, params, id) {
    sidecar.process.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
}
// Single request → single response
ipcMain.handle('rpc-call', async (_e, method, params) => {
    if (!sidecar.process)
        throw new Error('Sidecar not running');
    const id = nextId();
    writeRequest(method, params, id);
    const line = await new Promise(resolve => { sidecar.lineQueue.push(resolve); });
    const resp = JSON.parse(line);
    if (resp.error)
        throw new Error(`[${resp.error.code}] ${resp.error.message}`);
    return resp.result;
});
// Streaming request → chunks via webContents.send until done=true
ipcMain.handle('rpc-stream', async (event, method, params, streamId) => {
    if (!sidecar.process)
        throw new Error('Sidecar not running');
    const id = nextId();
    writeRequest(method, params, id);
    while (true) {
        const line = await new Promise(resolve => { sidecar.lineQueue.push(resolve); });
        const resp = JSON.parse(line);
        if (resp.error) {
            event.sender.send(streamId, { __error: true, message: `[${resp.error.code}] ${resp.error.message}` });
            break;
        }
        if (resp.result) {
            event.sender.send(streamId, resp.result);
            if (resp.result.done === true)
                break;
        }
    }
});
// Native file-open dialog
ipcMain.handle('show-open-dialog', async (_e, options) => {
    return dialog.showOpenDialog(options);
});
function createWindow() {
    const win = new BrowserWindow({
        width: 1280, height: 800, minWidth: 900, minHeight: 600,
        title: 'HypnoAI',
        webPreferences: {
            preload: path.join(__dirname, 'preload.cjs'),
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: false,
        },
    });
    if (!app.isPackaged) {
        win.loadURL('http://localhost:1420');
        win.webContents.openDevTools();
    }
    else {
        win.loadFile(path.join(__dirname, '../dist/index.html'));
    }
}
app.whenReady().then(() => { startSidecar(); createWindow(); });
app.on('window-all-closed', () => {
    sidecar.process?.kill();
    if (process.platform !== 'darwin')
        app.quit();
});
app.on('will-quit', () => { sidecar.process?.kill(); });
//# sourceMappingURL=main.js.map