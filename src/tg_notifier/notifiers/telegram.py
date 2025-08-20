from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: str, default_parse_mode: Optional[str] = None) -> None:
        self.token = token
        self.default_parse_mode = default_parse_mode
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        mode = parse_mode or self.default_parse_mode
        if mode:
            payload["parse_mode"] = mode
        client = await self._get_client()
        resp = await client.post(url, json=payload)
        try:
            data = resp.json()
        except Exception:
            data = {"ok": False, "status_code": resp.status_code, "text": resp.text}
        if not resp.is_success or not data.get("ok", False):
            logger.warning("Telegram sendMessage failed: status=%s body=%s", resp.status_code, data)
        return data 