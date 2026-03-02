"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
let streamCounter = 0;
function newStreamId() {
    return `hypno-stream-${Date.now()}-${++streamCounter}`;
}
electron_1.contextBridge.exposeInMainWorld('electronAPI', {
    rpcCall: (method, params) => electron_1.ipcRenderer.invoke('rpc-call', method, params),
    showOpenDialog: (options) => electron_1.ipcRenderer.invoke('show-open-dialog', options),
    rpcStream: (method, params, onChunk) => {
        const streamId = newStreamId();
        return new Promise((resolve, reject) => {
            const handler = (_event, chunk) => {
                if ('__error' in chunk) {
                    electron_1.ipcRenderer.removeListener(streamId, handler);
                    reject(new Error(chunk.message));
                    return;
                }
                onChunk(chunk);
                if (chunk.done === true) {
                    electron_1.ipcRenderer.removeListener(streamId, handler);
                    resolve();
                }
            };
            electron_1.ipcRenderer.on(streamId, handler);
            electron_1.ipcRenderer.invoke('rpc-stream', method, params, streamId).catch((err) => {
                electron_1.ipcRenderer.removeListener(streamId, handler);
                reject(err);
            });
        });
    },
});
//# sourceMappingURL=preload.js.map