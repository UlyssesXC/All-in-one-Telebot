from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..notifiers.telegram import TelegramNotifier
from ..utils import render_template, format_numbers_in_mapping

logger = logging.getLogger(__name__)


class Router:
    def __init__(self, notifiers: Dict[str, Any]) -> None:
        self.notifiers: Dict[str, Any] = notifiers

    async def deliver(self, route: Dict[str, Any], poller_name: str, events: List[Dict[str, Any]]) -> None:
        match = route.get("match", {})
        if match.get("poller_name") and match.get("poller_name") != poller_name:
            return
        deliveries = route.get("deliveries", [])
        tasks = []
        for event in events:
            for d in deliveries:
                notifier_name = d.get("notifier")
                notifier = self.notifiers.get(notifier_name)
                if isinstance(notifier, TelegramNotifier):
                    mapping = format_numbers_in_mapping(event)
                    tmpl = event.get("__template__") or d.get("template", "{__raw__}")
                    text = render_template(tmpl, mapping)
                    tasks.append(
                        notifier.send_message(
                            chat_id=d.get("chat_id"),
                            text=text,
                        )
                    )
        if tasks:
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                logger.exception("Router deliver error: %s", e)

    async def deliverers(self, routes: List[Dict[str, Any]], poller_name: str, events: List[Dict[str, Any]]) -> None:
        tasks = [self.deliver(route, poller_name, events) for route in routes]
        if tasks:
            await asyncio.gather(*tasks) 