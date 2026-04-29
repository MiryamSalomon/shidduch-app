"""
Rate Limiter
=============
Shared slowapi ``Limiter`` instance used across the application.

Defined in a dedicated module to avoid circular imports — routers import
from here, and ``main.py`` attaches it to ``app.state``.

The ``key_func`` uses the client's remote IP address to bucket requests.
Behind a reverse proxy (nginx, Cloudflare), set ``X-Forwarded-For`` trust
in the proxy config so the real IP reaches the app.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
