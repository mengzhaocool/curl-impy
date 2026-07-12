"""
curl_impersonate_py - Python binding for curl-impersonate-chrome DLL

Supports impersonating any Chrome version by providing a JSON fingerprint config.
Requires no browser, no CDP, no environment dependencies.
"""
from .session import Session, AsyncSession
from .core import register_fingerprint, list_fingerprints
from .__version__ import __version__

__all__ = ["Session", "AsyncSession", "register_fingerprint", "list_fingerprints", "__version__"]
