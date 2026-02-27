"""JSON-RPC 2.0 dispatcher for the HypnoAI sidecar.

Each request is a single JSON line on stdin.
Each response (or stream of responses) is one or more JSON lines on stdout.

Handlers may return:
- A ``dict`` — emitted as a single success response.
- A ``Generator[dict, None, None]`` — each yielded dict is emitted as a
  partial response with the same ``id``; the last dict (``{"done": True}``)
  terminates the stream.
- ``None`` — handler writes its own output (not used currently).
"""
from __future__ import annotations

import inspect
import json
import sys
import traceback
from typing import Any, Callable, Generator, IO

from .session import SidecarSession

# Standard JSON-RPC 2.0 error codes
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603

# HypnoAI-specific error codes (§18.3)
ERR_MODEL_NOT_INSTALLED = -1001
ERR_DOWNLOAD_FAILED = -1002
ERR_RENDER_FAILED = -1003
ERR_LLM_UNAVAILABLE = -1004
ERR_SCRIPT_VALIDATION = -1005
ERR_GPU_OOM = -1006

Handler = Callable[..., Any]


class RPCServer:
    """Minimal JSON-RPC 2.0 server backed by a :class:`SidecarSession`.

    Handlers are registered by method name.  The server reads lines from
    *stdin* and writes to *stdout* (both injectable for testing).
    """

    def __init__(
        self,
        session: SidecarSession,
        stdin: IO[str] | None = None,
        stdout: IO[str] | None = None,
    ) -> None:
        self._session = session
        self._handlers: dict[str, Handler] = {}
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout

    # ------------------------------------------------------------------
    # Public API

    def register(self, method: str, handler: Handler) -> None:
        """Register *handler* for *method*."""
        self._handlers[method] = handler

    def emit(self, obj: dict[str, Any]) -> None:
        """Write a single JSON line to stdout."""
        print(json.dumps(obj), file=self._stdout, flush=True)

    def run(self) -> None:
        """Main loop: read requests from stdin, dispatch, write responses."""
        for raw in self._stdin:
            raw = raw.strip()
            if not raw:
                continue
            self._process(raw)

    # ------------------------------------------------------------------
    # Internal

    def _process(self, raw: str) -> None:
        # Parse
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.emit(self._error(None, ERR_PARSE, f"Parse error: {exc}"))
            return

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        if not isinstance(method, str):
            self.emit(self._error(req_id, ERR_INVALID_REQUEST, "Missing or invalid 'method'"))
            return

        handler = self._handlers.get(method)
        if handler is None:
            self.emit(self._error(req_id, ERR_METHOD_NOT_FOUND, f"Method not found: {method!r}"))
            return

        try:
            result = handler(self._session, params)
        except (KeyError, TypeError, ValueError) as exc:
            self.emit(self._error(req_id, ERR_INVALID_PARAMS, str(exc)))
            return
        except PermissionError as exc:
            self.emit(self._error(req_id, ERR_MODEL_NOT_INSTALLED, str(exc)))
            return
        except RuntimeError as exc:
            self.emit(self._error(req_id, ERR_RENDER_FAILED, str(exc)))
            return
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            self.emit(self._error(req_id, ERR_INTERNAL, str(exc)))
            return

        # Streaming generator
        if inspect.isgenerator(result):
            for chunk in result:
                self.emit({"jsonrpc": "2.0", "id": req_id, "result": chunk})
        elif result is not None:
            self.emit({"jsonrpc": "2.0", "id": req_id, "result": result})

    @staticmethod
    def _error(req_id: Any, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }
