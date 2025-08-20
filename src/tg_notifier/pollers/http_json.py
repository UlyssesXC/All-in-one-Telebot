from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Set

import httpx
import jmespath

from ..utils import get_by_path

logger = logging.getLogger(__name__)


class HTTPJSONPoller:
    def __init__(
        self,
        name: str,
        request: Dict[str, Any],
        extract: Dict[str, Any],
        interval_seconds: int = 15,
        id_path: Optional[str] = None,
        updated_at_path: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None,
    ) -> None:
        self.name = name
        self.request = request
        self.extract = extract
        self.interval_seconds = max(1, interval_seconds)
        self.id_path = id_path
        self.updated_at_path = updated_at_path
        self.fields = fields or {}
        self._client: Optional[httpx.AsyncClient] = None
        self._compiled_expr = jmespath.compile(self.extract.get("items_jmespath"))

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            timeout = self.request.get("timeout_seconds", 10)
            self._client = httpx.AsyncClient(timeout=timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _fetch(self) -> List[Dict[str, Any]]:
        client = await self._get_client()
        method = self.request.get("method", "GET").upper()
        url = self.request["url"]
        headers = self.request.get("headers") or {}
        params = self.request.get("params") or {}
        body = self.request.get("body")
        resp = await client.request(method, url, headers=headers, params=params, json=body)
        resp.raise_for_status()
        data = resp.json()
        items = self._compiled_expr.search(data) or []
        if not isinstance(items, list):
            items = []
        out: List[Dict[str, Any]] = []
        for item in items:
            event: Dict[str, Any] = {}
            for out_key, path in self.fields.items():
                event[out_key] = get_by_path(item, path)
            if self.id_path:
                event["__id__"] = str(get_by_path(item, self.id_path))
            if self.updated_at_path:
                event["__updated_at__"] = get_by_path(item, self.updated_at_path)
            event["__raw__"] = item
            out.append(event)
        return out

    async def poll(self) -> AsyncIterator[List[Dict[str, Any]]]:
        try:
            while True:
                try:
                    events = await self._fetch()
                    yield events
                except Exception as e:
                    logger.exception("Poller %s fetch error: %s", self.name, e)
                    yield []
                await asyncio.sleep(self.interval_seconds)
        finally:
            await self.close() 