from __future__ import annotations

import re
from pathlib import PurePosixPath


SKIPPED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".bzr",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".cache",
    "node_modules",
    "bower_components",
    "vendor",
    "build",
    "dist",
    "target",
    ".next",
    ".nuxt",
    ".turbo",
    ".idea",
    ".switchshelf",
    ".ssh",
    ".kube",
    ".aws",
    ".azure",
    ".gnupg",
    ".docker",
    ".terraform",
    ".pulumi",
}

SENSITIVE_EXACT_NAMES = {
    ".env",
    ".env.local",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials",
    "credentials.json",
    "secrets.json",
    "secret.json",
    "authorized_keys",
    "known_hosts",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "master.key",
    "service-account.json",
    ".bash_history",
    ".zsh_history",
    "ps_history",
    ".python_history",
    "consolehost_history.txt",
    "history.sqlite",
}

SENSITIVE_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".p7b",
    ".p7c",
    ".jks",
    ".keystore",
    ".kdb",
    ".kdbx",
    ".asc",
}

_SECRET_WORD = re.compile(
    r"(^|[._-])(secret|secrets|credential|credentials|privatekey|private_key|"
    r"api[_-]?key|access[_-]?token)([._-]|$)",
    re.IGNORECASE,
)


def normalize_relative(path: str) -> str:
    normalized = PurePosixPath(path.replace("\\", "/")).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_sensitive_path(path: str) -> bool:
    normalized = normalize_relative(path)
    parts = [part.casefold() for part in PurePosixPath(normalized).parts]
    if any(part in SKIPPED_DIRECTORIES for part in parts):
        return True

    for name in parts:
        if name in SENSITIVE_EXACT_NAMES:
            return True
        if name.startswith(".env."):
            return True
        if PurePosixPath(name).suffix.casefold() in SENSITIVE_SUFFIXES:
            return True
        if ".tfstate" in name:
            return True
        if _SECRET_WORD.search(name):
            return True
        if name.startswith("id_rsa.") or name.startswith("id_ed25519."):
            return True
    return False


def markdown_path(path: str) -> str:
    escaped = normalize_relative(path).replace("\\", "/")
    for char in (chr(96), "|", "<", ">", "\r", "\n"):
        escaped = escaped.replace(char, "_")
    return escaped
