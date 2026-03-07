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
        handle_cache_clear,
    )
    from .handlers.voices import (
        handle_voices_list,
        handle_voices_engines,
        handle_voices_clone,
        handle_voices_catalog,
        handle_voices_remove,
        handle_voices_add,
    )
    from .handlers.ai import handle_ai_generate
    from .handlers.models import (
        handle_models_status,
        handle_models_list,
        handle_models_download,
        handle_models_download_progress,
        handle_models_remove,
    )
    from .handlers.engines import (
        handle_engines_active,
        handle_engines_use,
        handle_engines_list,
        handle_engines_install,
        handle_engines_uninstall,
    )
    from .handlers.sessions import (
        handle_sessions_list,
        handle_sessions_create,
        handle_sessions_load,
        handle_sessions_save,
        handle_sessions_delete,
        handle_sessions_rename,
        handle_sessions_dir_get,
        handle_sessions_dir_set,
    )

    server.register("script.lint", handle_script_lint)
    server.register("render.start", handle_render_start)
    server.register("render.progress", handle_render_progress)
    server.register("render.cancel", handle_render_cancel)
    server.register("render.preview", handle_render_preview)
    server.register("cache.clear", handle_cache_clear)
    server.register("voices.list", handle_voices_list)
    server.register("voices.engines", handle_voices_engines)
    server.register("voices.clone", handle_voices_clone)
    server.register("voices.catalog", handle_voices_catalog)
    server.register("voices.remove", handle_voices_remove)
    server.register("voices.add", handle_voices_add)
    server.register("engines.active", handle_engines_active)
    server.register("engines.use", handle_engines_use)
    server.register("engines.list", handle_engines_list)
    server.register("engines.install", handle_engines_install)
    server.register("engines.uninstall", handle_engines_uninstall)
    server.register("ai.generate", handle_ai_generate)
    server.register("models.status", handle_models_status)
    server.register("models.list", handle_models_list)
    server.register("models.download", handle_models_download)
    server.register("models.download.progress", handle_models_download_progress)
    server.register("models.remove", handle_models_remove)
    server.register("sessions.list", handle_sessions_list)
    server.register("sessions.create", handle_sessions_create)
    server.register("sessions.load", handle_sessions_load)
    server.register("sessions.save", handle_sessions_save)
    server.register("sessions.delete", handle_sessions_delete)
    server.register("sessions.rename", handle_sessions_rename)
    server.register("sessions.dir.get", handle_sessions_dir_get)
    server.register("sessions.dir.set", handle_sessions_dir_set)

    server.ready()
    server.run()


if __name__ == "__main__":
    main()
