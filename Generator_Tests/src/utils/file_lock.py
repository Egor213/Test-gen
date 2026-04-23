# src/utils/file_lock.py
import asyncio
import threading
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path


class FileLockManager:
    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls) -> "FileLockManager":
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._locks: dict[str, threading.RLock] = defaultdict(threading.RLock)
                cls._instance._async_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
                cls._instance._registry_lock = threading.Lock()
        return cls._instance

    def _get_key(self, path: Path) -> str:
        return str(path.resolve())

    def _get_sync_lock(self, path: Path) -> threading.RLock:
        key = self._get_key(path)
        with self._registry_lock:
            if key not in self._locks:
                self._locks[key] = threading.RLock()
            return self._locks[key]

    def _get_async_lock(self, path: Path) -> asyncio.Lock:
        key = self._get_key(path)
        with self._registry_lock:
            if key not in self._async_locks:
                self._async_locks[key] = asyncio.Lock()
            return self._async_locks[key]

    @contextmanager
    def lock(self, path: Path):
        sync_lock = self._get_sync_lock(path)
        sync_lock.acquire()
        try:
            yield
        finally:
            sync_lock.release()

    @asynccontextmanager
    async def async_lock(self, path: Path):
        async_lk = self._get_async_lock(path)
        sync_lk = self._get_sync_lock(path)

        await async_lk.acquire()
        try:
            sync_lk.acquire()
            try:
                yield
            finally:
                sync_lk.release()
        finally:
            async_lk.release()
