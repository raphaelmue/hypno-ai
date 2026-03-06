import { app, BrowserWindow, dialog, ipcMain, shell, protocol, net } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import * as readline from 'readline';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

// Register custom scheme for serving local audio files to the renderer.
// Must be called before app is ready.
protocol.registerSchemesAsPrivileged([
  { scheme: 'hypnoai-local', privileges: { secure: true, standard: true, supportFetchAPI: true, stream: true } },
]);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Sidecar state
const sidecar = {
  process: null as ChildProcess | null,
  requestId: 0,
  ready: false,
  pendingReady: [] as Array<() => void>,
  exitError: '' as string,
};

type CallHandler = { resolve: (v: unknown) => void; reject: (e: Error) => void };
type StreamHandler = {
  onChunk: (chunk: Record<string, unknown>) => void;
  resolve: () => void;
  reject: (e: Error) => void;
};

// ID-keyed maps replace the old FIFO lineQueue.
// This prevents response mis-routing when multiple concurrent RPC calls or
// a stream + a call are in-flight at the same time.
const pendingCalls = new Map<number, CallHandler>();
const pendingStreams = new Map<number, StreamHandler>();

function findVenvPython(): string {
  let dir = __dirname;
  for (let i = 0; i < 10; i++) {
    const candidates = [
      path.join(dir, '.venv', 'Scripts', 'python.exe'), // Windows
      path.join(dir, '.venv', 'bin', 'python'),          // Unix
    ];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) return candidate;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return 'python';
}

// Collect recent stderr lines so we can surface them in error messages.
let sidecarStderr: string[] = [];

function startSidecar(): void {
  const isDev = !app.isPackaged;
  let command: string, args: string[];

  if (isDev) {
    command = findVenvPython();
    args = ['-m', 'hypnoai.sidecar'];
  } else {
    const exe = process.platform === 'win32' ? 'hypnoai-sidecar.exe' : 'hypnoai-sidecar';
    command = path.join(process.resourcesPath, 'hypnoai-sidecar', exe);
    args = [];
  }

  console.log('[sidecar] spawning:', command, args.join(' '));

  const child = spawn(command, args, {
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true,
  });
  sidecar.process = child;

  child.on('error', (err) => {
    console.error('[sidecar] spawn error:', err.message);
    sidecarStderr.push(err.message);
  });

  child.stderr?.on('data', (data: Buffer) => {
    const text = data.toString().trimEnd();
    if (text) {
      console.error('[sidecar]', text);
      sidecarStderr.push(text);
      if (sidecarStderr.length > 50) sidecarStderr.shift();
    }
  });

  const rl = readline.createInterface({ input: child.stdout!, crlfDelay: Infinity });
  rl.on('line', (line) => {
    if (!line.startsWith('{')) {
      console.warn('[sidecar] Unexpected line:', line);
      return;
    }
    let parsed: { method?: string; id?: number; result?: unknown; error?: { code: number; message: string } };
    try {
      parsed = JSON.parse(line);
    } catch {
      console.warn('[sidecar] Failed to parse line:', line);
      return;
    }
    // Unsolicited ready notification
    if (parsed.method === 'sidecar.ready') {
      sidecar.ready = true;
      sidecar.pendingReady.splice(0).forEach(fn => fn());
      return;
    }
    const id = parsed.id;
    if (id === undefined) {
      console.warn('[sidecar] Response missing id:', line);
      return;
    }
    // Route to the correct call or stream handler by id
    const call = pendingCalls.get(id);
    if (call) {
      pendingCalls.delete(id);
      if (parsed.error) call.reject(new Error(`[${parsed.error.code}] ${parsed.error.message}`));
      else call.resolve(parsed.result);
      return;
    }
    const stream = pendingStreams.get(id);
    if (stream) {
      if (parsed.error) {
        pendingStreams.delete(id);
        stream.reject(new Error(`[${parsed.error.code}] ${parsed.error.message}`));
        return;
      }
      if (parsed.result) {
        stream.onChunk(parsed.result as Record<string, unknown>);
        if ((parsed.result as Record<string, unknown>).done === true) {
          pendingStreams.delete(id);
          stream.resolve();
        }
      }
      return;
    }
    console.warn('[sidecar] No handler for id:', id, line);
  });

  child.on('exit', (code) => {
    const detail = sidecarStderr.length > 0 ? '\n' + sidecarStderr.join('\n') : '';
    console.error(`[sidecar] exited with code ${code}${detail}`);
    sidecar.process = null;
    sidecar.exitError = `Sidecar exited (code ${code})${detail}`;
    // Unblock any IPC calls waiting for the ready signal (sidecar died before it was ready)
    if (!sidecar.ready) {
      sidecar.ready = true;
      sidecar.pendingReady.splice(0).forEach(fn => fn());
    }
    // Reject all in-flight RPC calls and streams
    const err = new Error(sidecar.exitError);
    for (const h of pendingCalls.values()) h.reject(err);
    pendingCalls.clear();
    for (const h of pendingStreams.values()) h.reject(err);
    pendingStreams.clear();
  });
}

function nextId(): number { return ++sidecar.requestId; }

function writeRequest(method: string, params: unknown, id: number): void {
  sidecar.process!.stdin!.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
}

function waitForReady(): Promise<void> {
  if (sidecar.ready) return Promise.resolve();
  return new Promise(resolve => { sidecar.pendingReady.push(resolve); });
}

// Single request → single response
ipcMain.handle('rpc-call', (_e, method: string, params: unknown) => {
  if (!sidecar.process) return Promise.reject(new Error(sidecar.exitError || 'Sidecar not running'));
  return waitForReady().then(() => {
    if (!sidecar.process) return Promise.reject(new Error(sidecar.exitError || 'Sidecar not running'));
    const id = nextId();
    return new Promise<unknown>((resolve, reject) => {
      pendingCalls.set(id, { resolve, reject });
      writeRequest(method, params, id);
    });
  });
});

// Streaming request → chunks via webContents.send until done=true
ipcMain.handle('rpc-stream', (event, method: string, params: unknown, streamId: string) => {
  if (!sidecar.process) return Promise.reject(new Error(sidecar.exitError || 'Sidecar not running'));
  return waitForReady().then(() => {
    if (!sidecar.process) return Promise.reject(new Error(sidecar.exitError || 'Sidecar not running'));
    const id = nextId();
    return new Promise<void>((resolve, reject) => {
      pendingStreams.set(id, {
        onChunk: (chunk) => event.sender.send(streamId, chunk),
        resolve,
        reject,
      });
      writeRequest(method, params, id);
    });
  });
});

// Native file-open dialog
ipcMain.handle('show-open-dialog', async (_e, options: Electron.OpenDialogOptions) => {
  return dialog.showOpenDialog(options);
});

// Native save dialog
ipcMain.handle('show-save-dialog', async (_e, options: Electron.SaveDialogOptions) => {
  return dialog.showSaveDialog(options);
});

// Reveal file in native file manager
ipcMain.handle('show-in-folder', async (_e, filePath: string) => {
  shell.showItemInFolder(filePath);
});

function createWindow(): void {
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
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(() => {
  // Serve local files via hypnoai-local:// so the renderer can play audio
  protocol.handle('hypnoai-local', (request) => {
    const url = new URL(request.url);
    const filePath = decodeURIComponent(url.pathname.slice(1)); // strip leading /
    const normalized = filePath.replace(/\\/g, '/');
    const fileUrl = `file://${normalized.startsWith('/') ? '' : '/'}${normalized}`;
    return net.fetch(fileUrl);
  });
  startSidecar();
  createWindow();
});
app.on('window-all-closed', () => {
  sidecar.process?.kill();
  if (process.platform !== 'darwin') app.quit();
});
app.on('will-quit', () => { sidecar.process?.kill(); });
