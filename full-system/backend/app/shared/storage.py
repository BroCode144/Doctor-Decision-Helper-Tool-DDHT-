"""Pluggable document storage.

The rest of the application only deals with opaque storage *keys* (e.g.
"patients/P001/3f2a...c1.pdf"), never filesystem paths. To move to S3 /
Azure Blob / GCS, implement `StorageBackend` and register it in
`get_storage()`; nothing else changes.
"""

import re
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

_KEY_RE = re.compile(r"^[A-Za-z0-9_\-]+(/[A-Za-z0-9_\-]+)*\.[a-z0-9]{1,5}$")


class StorageError(Exception):
    pass


def validate_key(key: str) -> str:
    if not _KEY_RE.fullmatch(key) or ".." in key:
        raise StorageError("Invalid storage key.")
    return key


class StorageBackend(ABC):
    name: str

    @abstractmethod
    def save(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def read(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalStorage(StorageBackend):
    name = "local"

    def __init__(self, base_dir: Path):
        self.base = Path(base_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        validate_key(key)
        path = (self.base / key).resolve()
        # Defense in depth against path traversal: must stay inside base dir.
        if self.base not in path.parents:
            raise StorageError("Invalid storage path.")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # "xb": never overwrite an existing file; files are written with
        # non-executable permissions.
        with open(path, "xb") as fh:
            fh.write(data)
        path.chmod(0o640)

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StorageError("File not found in storage.")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


@lru_cache
def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.upload_dir)
    raise RuntimeError(f"Unsupported STORAGE_BACKEND '{settings.storage_backend}'")
