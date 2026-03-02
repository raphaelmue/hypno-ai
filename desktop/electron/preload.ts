import { contextBridge, ipcRenderer } from 'electron';

let streamCounter = 0;
function newStreamId(): string {
  return `hypno-stream-${Date.now()}-${++streamCounter}`;
}

contextBridge.exposeInMainWorld('electronAPI', {
  rpcCall: (method: string, params: Record<string, unknown>): Promise<unknown> =>
    ipcRenderer.invoke('rpc-call', method, params),

  showOpenDialog: (options: {
    title?: string;
    filters?: { name: string; extensions: string[] }[];
    properties?: string[];
  }): Promise<{ canceled: boolean; filePaths: string[] }> =>
    ipcRenderer.invoke('show-open-dialog', options),

  rpcStream: (
    method: string,
    params: Record<string, unknown>,
    onChunk: (chunk: Record<string, unknown>) => void
  ): Promise<void> => {
    const streamId = newStreamId();
    return new Promise<void>((resolve, reject) => {
      const handler = (_event: Electron.IpcRendererEvent, chunk: Record<string, unknown>) => {
        if ('__error' in chunk) {
          ipcRenderer.removeListener(streamId, handler);
          reject(new Error(chunk.message as string));
          return;
        }
        onChunk(chunk);
        if (chunk.done === true) {
          ipcRenderer.removeListener(streamId, handler);
          resolve();
        }
      };
      ipcRenderer.on(streamId, handler);
      ipcRenderer.invoke('rpc-stream', method, params, streamId).catch((err: Error) => {
        ipcRenderer.removeListener(streamId, handler);
        reject(err);
      });
    });
  },
});
