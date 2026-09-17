"""Minimal environments for local CLI subprocesses.

Do not pass parent-process credentials to independently executed agents.
"""

import os


SUBPROCESS_ENV_ALLOWLIST = (
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "CODEX_HOME",
    "CLAUDE_CONFIG_DIR", "SSL_CERT_FILE", "SSL_CERT_DIR",
)


def safe_subprocess_env(environment=None):
    """Build the only environment passed to local Codex and Claude CLIs."""
    source = os.environ if environment is None else environment
    return {
        key: source[key] for key in SUBPROCESS_ENV_ALLOWLIST
        if isinstance(source.get(key), str) and source[key]
    }
