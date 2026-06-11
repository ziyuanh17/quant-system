"""Launch the web console server.

Starts the FastAPI application with uvicorn.
Intended for local development and Mac Studio deployment.

"""

import ipaddress

import uvicorn


def _is_loopback_host(host: str) -> bool:
    """Return whether a bind host is restricted to the local machine."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


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
    if not _is_loopback_host(host):
        raise ValueError(
            "The console may only bind to a loopback address. "
            "Use a local Tailscale or authenticated reverse-proxy endpoint "
            "for remote access."
        )

    uvicorn.run(
        "quant.web.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
