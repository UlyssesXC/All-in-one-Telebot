import asyncio
import json
import os
from typing import Dict, Set, Any, Optional

from ..utils import ensure_dir


class FileStateStore:
    def __init__(self, root_dir: str) -> None:
        self.root_dir = root_dir
        ensure_dir(self.root_dir)
        self._locks: Dict[str, asyncio.Lock] = {}
        self._seen_cache: Dict[str, Set[str]] = {}
        self._present_cache: Dict[str, Set[str]] = {}

    def _file_path(self, poller_name: str) -> str:
        return os.path.join(self.root_dir, f"{poller_name}.json")

    def _present_file_path(self, poller_name: str) -> str:
        return os.path.join(self.root_dir, f"{poller_name}__present.json")

    def _tracking_file_path(self, poller_name: str) -> str:
        return os.path.join(self.root_dir, f"{poller_name}__tracking.json")

    def _get_lock(self, poller_name: str) -> asyncio.Lock:
        if poller_name not in self._locks:
            self._locks[poller_name] = asyncio.Lock()
        return self._locks[poller_name]

    async def _load_seen(self, poller_name: str) -> Set[str]:
        if poller_name in self._seen_cache:
            return self._seen_cache[poller_name]
        path = self._file_path(poller_name)
        if not os.path.exists(path):
            self._seen_cache[poller_name] = set()
            return self._seen_cache[poller_name]
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._seen_cache[poller_name] = set(data if isinstance(data, list) else [])
        except Exception:
            self._seen_cache[poller_name] = set()
        return self._seen_cache[poller_name]

    async def _persist_seen(self, poller_name: str) -> None:
        path = self._file_path(poller_name)
        ensure_dir(os.path.dirname(path))
        data = sorted(self._seen_cache.get(poller_name, set()))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    async def is_seen(self, poller_name: str, key: str) -> bool:
        async with self._get_lock(poller_name):
            seen = await self._load_seen(poller_name)
            return key in seen

    async def mark_seen(self, poller_name: str, keys: Set[str]) -> None:
        async with self._get_lock(poller_name):
            seen = await self._load_seen(poller_name)
            seen.update(keys)
            await self._persist_seen(poller_name)

    # ---- Present snapshot APIs ----
    async def load_last_present_ids(self, poller_name: str) -> Set[str]:
        async with self._get_lock(poller_name):
            if poller_name in self._present_cache:
                return self._present_cache[poller_name]
            path = self._present_file_path(poller_name)
            if not os.path.exists(path):
                self._present_cache[poller_name] = set()
                return self._present_cache[poller_name]
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._present_cache[poller_name] = set(data if isinstance(data, list) else [])
            except Exception:
                self._present_cache[poller_name] = set()
            return self._present_cache[poller_name]

    async def save_current_present_ids(self, poller_name: str, ids: Set[str]) -> None:
        async with self._get_lock(poller_name):
            self._present_cache[poller_name] = set(ids)
            path = self._present_file_path(poller_name)
            ensure_dir(os.path.dirname(path))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sorted(list(ids)), f, ensure_ascii=False)

    # ---- Tracking lowest order APIs ----
    async def load_tracking(self, poller_name: str) -> Optional[Dict[str, Any]]:
        async with self._get_lock(poller_name):
            path = self._tracking_file_path(poller_name)
            if not os.path.exists(path):
                return None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                return None
            return None

    async def save_tracking(self, poller_name: str, data: Optional[Dict[str, Any]]) -> None:
        async with self._get_lock(poller_name):
            path = self._tracking_file_path(poller_name)
            ensure_dir(os.path.dirname(path))
            if data is None:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
                return
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False) 