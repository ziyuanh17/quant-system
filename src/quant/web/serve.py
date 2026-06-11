"""Launch the web console server.

Starts the FastAPI application with uvicorn.
Intended for local development and Mac Studio deployment.

"""

import os
import sys

import uvicorn


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Start the web console server.

    Parameters
    ----------
    host : str
        Bind address. Default ``127.0.0.1`` (local only).
        Use ``0.0.0.0`` to expose on all interfaces (not recommended
        without a reverse proxy or Tailscale).
    port : int
        Bind port. Default ``8000``.
    reload : bool
        Enable auto-reload for development. Default ``False``.

     """
    api_key_set = os.environ.get("QUANT_CONSOLE_API_KEY") is not None

    uvicorn.run(
        "quant.web.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
