"""HypnoAI JSON-RPC sidecar — entrypoint for the Tauri desktop GUI.

The sidecar reads one-line JSON-RPC 2.0 requests from **stdin** and writes
responses to **stdout**.  Audio data is *never* sent over the bridge — only
file paths (§18 of the design doc).

Usage (from Tauri managed-sidecar config or shell):
    python -m hypnoai.sidecar
"""

from .server import RPCServer
from .session import SidecarSession


def main() -> None:
    """Start the JSON-RPC sidecar loop."""
    session = SidecarSession()
    server = RPCServer(session)

    # Register all handlers
    from .handlers.script import handle_script_lint
    from .handlers.render import (
        handle_render_start,
        handle_render_progress,
        handle_render_cancel,
        handle_render_preview,
    )
    from .handlers.voices import handle_voices_list, handle_voices_clone
    from .handlers.ai import handle_ai_generate
    from .handlers.models import (
        handle_models_status,
        handle_models_list,
        handle_models_download,
        handle_models_download_progress,
        handle_models_remove,
    )

    server.register("script.lint", handle_script_lint)
    server.register("render.start", handle_render_start)
    server.register("render.progress", handle_render_progress)
    server.register("render.cancel", handle_render_cancel)
    server.register("render.preview", handle_render_preview)
    server.register("voices.list", handle_voices_list)
    server.register("voices.clone", handle_voices_clone)
    server.register("ai.generate", handle_ai_generate)
    server.register("models.status", handle_models_status)
    server.register("models.list", handle_models_list)
    server.register("models.download", handle_models_download)
    server.register("models.download.progress", handle_models_download_progress)
    server.register("models.remove", handle_models_remove)

    server.run()


if __name__ == "__main__":
    main()
