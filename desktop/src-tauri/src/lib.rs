/**
 * HypnoAI Tauri backend — manages the Python sidecar process and proxies
 * JSON-RPC calls between the React frontend and the Python engine.
 *
 * Architecture (§14.4):
 *   React (TypeScript)  →  tauri::invoke("rpc_call", …)
 *     →  Rust (this file)  →  writes JSON-RPC line to sidecar's stdin
 *     →  Python sidecar     reads from stdin, processes, writes response to stdout
 *     →  Rust reads stdout  →  returns result to React
 *
 * For streaming (ai.generate), the Rust side reads multiple lines from stdout
 * and forwards them to the frontend via a Tauri Channel.
 */
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager, State};

// ---------------------------------------------------------------------------
// Sidecar state
// ---------------------------------------------------------------------------

pub struct SidecarState {
    child: Arc<Mutex<Option<Child>>>,
    stdin: Arc<Mutex<Option<ChildStdin>>>,
    stdout: Arc<Mutex<Option<BufReader<ChildStdout>>>>,
    request_id: Arc<Mutex<u64>>,
}

impl SidecarState {
    pub fn new() -> Self {
        Self {
            child: Arc::new(Mutex::new(None)),
            stdin: Arc::new(Mutex::new(None)),
            stdout: Arc::new(Mutex::new(None)),
            request_id: Arc::new(Mutex::new(0)),
        }
    }

    pub fn next_id(&self) -> u64 {
        let mut id = self.request_id.lock().unwrap();
        *id += 1;
        *id
    }
}

// ---------------------------------------------------------------------------
// JSON-RPC types
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize)]
struct RpcRequest {
    jsonrpc: String,
    id: u64,
    method: String,
    params: Value,
}

#[derive(Serialize, Deserialize)]
struct RpcResponse {
    jsonrpc: Option<String>,
    id: Option<Value>,
    result: Option<Value>,
    error: Option<RpcError>,
}

#[derive(Serialize, Deserialize)]
struct RpcError {
    code: i64,
    message: String,
}

// ---------------------------------------------------------------------------
// Sidecar lifecycle
// ---------------------------------------------------------------------------

fn start_sidecar(app: &AppHandle) -> Result<(), String> {
    let state: State<SidecarState> = app.state();

    // Locate the Python sidecar binary.
    // In production: packaged alongside the app via Tauri sidecar.
    // In development: use the venv python in the engine directory.
    let sidecar_path = app
        .path()
        .resource_dir()
        .map(|d| d.join("hypnoai-sidecar"))
        .unwrap_or_else(|_| {
            // Development fallback: use venv python
            let cwd = std::env::current_dir().unwrap_or_default();
            // Walk up to find the project root
            let root = cwd
                .ancestors()
                .find(|p| p.join(".venv").exists())
                .map(|p| p.to_path_buf())
                .unwrap_or(cwd);
            root.join(".venv/bin/python")
        });

    let mut cmd = if sidecar_path.extension().is_some_and(|e| e == "py") {
        // Development: python -m hypnoai.sidecar
        let mut c = Command::new(&sidecar_path);
        c.arg("-m").arg("hypnoai.sidecar");
        c
    } else {
        // Production: direct binary
        Command::new(&sidecar_path)
    };

    let mut child = cmd
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| format!("Failed to start sidecar: {}", e))?;

    let stdin = child.stdin.take().ok_or("Failed to get sidecar stdin")?;
    let stdout = child.stdout.take().ok_or("Failed to get sidecar stdout")?;

    *state.child.lock().unwrap() = Some(child);
    *state.stdin.lock().unwrap() = Some(stdin);
    *state.stdout.lock().unwrap() = Some(BufReader::new(stdout));

    Ok(())
}

// ---------------------------------------------------------------------------
// Tauri commands
// ---------------------------------------------------------------------------

/// Send a JSON-RPC request to the Python sidecar and return the response.
#[tauri::command]
async fn rpc_call(
    method: String,
    params: Value,
    state: State<'_, SidecarState>,
) -> Result<Value, String> {
    let id = state.next_id();
    let request = RpcRequest {
        jsonrpc: "2.0".to_string(),
        id,
        method,
        params,
    };

    let request_str =
        serde_json::to_string(&request).map_err(|e| format!("Serialize error: {}", e))?;

    // Write request line to stdin
    {
        let mut stdin_guard = state.stdin.lock().unwrap();
        let stdin = stdin_guard
            .as_mut()
            .ok_or("Sidecar not running. Restart the app.")?;
        writeln!(stdin, "{}", request_str).map_err(|e| format!("Write error: {}", e))?;
    }

    // Read response line from stdout
    let response_str = {
        let mut stdout_guard = state.stdout.lock().unwrap();
        let reader = stdout_guard
            .as_mut()
            .ok_or("Sidecar not running. Restart the app.")?;
        let mut line = String::new();
        reader
            .read_line(&mut line)
            .map_err(|e| format!("Read error: {}", e))?;
        line
    };

    let response: RpcResponse = serde_json::from_str(&response_str)
        .map_err(|e| format!("Deserialize error: {} (raw: {})", e, response_str.trim()))?;

    if let Some(err) = response.error {
        return Err(format!("[{}] {}", err.code, err.message));
    }

    response.result.ok_or_else(|| "Empty result".to_string())
}

/// Send a streaming JSON-RPC request; each chunk is forwarded via a Tauri channel.
#[tauri::command]
async fn rpc_stream(
    method: String,
    params: Value,
    on_chunk: tauri::ipc::Channel<Value>,
    state: State<'_, SidecarState>,
) -> Result<(), String> {
    let id = state.next_id();
    let request = RpcRequest {
        jsonrpc: "2.0".to_string(),
        id,
        method,
        params,
    };

    let request_str =
        serde_json::to_string(&request).map_err(|e| format!("Serialize error: {}", e))?;

    {
        let mut stdin_guard = state.stdin.lock().unwrap();
        let stdin = stdin_guard
            .as_mut()
            .ok_or("Sidecar not running. Restart the app.")?;
        writeln!(stdin, "{}", request_str).map_err(|e| format!("Write error: {}", e))?;
    }

    // Read multiple response lines until done=true
    loop {
        let response_str = {
            let mut stdout_guard = state.stdout.lock().unwrap();
            let reader = stdout_guard
                .as_mut()
                .ok_or("Sidecar not running. Restart the app.")?;
            let mut line = String::new();
            reader
                .read_line(&mut line)
                .map_err(|e| format!("Read error: {}", e))?;
            line
        };

        let response: RpcResponse = serde_json::from_str(&response_str)
            .map_err(|e| format!("Deserialize error: {}", e))?;

        if let Some(err) = response.error {
            return Err(format!("[{}] {}", err.code, err.message));
        }

        if let Some(result) = response.result {
            let is_done = result
                .get("done")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);

            on_chunk.send(result).map_err(|e| format!("Channel error: {}", e))?;

            if is_done {
                break;
            }
        }
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// App setup
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState::new())
        .setup(|app| {
            if let Err(e) = start_sidecar(&app.handle()) {
                eprintln!("Warning: sidecar failed to start: {}", e);
                // Non-fatal in development — the UI will degrade gracefully.
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![rpc_call, rpc_stream])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
