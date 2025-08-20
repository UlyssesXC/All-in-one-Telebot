from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HTTPRequestConfig(BaseModel):
    url: str
    method: str = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = 10
    params: Dict[str, Any] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None


class HTTPJSONExtractConfig(BaseModel):
    items_jmespath: str


class PollerHTTPJSONConfig(BaseModel):
    type: str = "http_json"
    interval_seconds: int = 15
    request: HTTPRequestConfig
    extract: HTTPJSONExtractConfig
    id_path: Optional[str] = None
    updated_at_path: Optional[str] = None
    fields: Dict[str, str] = Field(default_factory=dict)


class NotifierTelegramConfig(BaseModel):
    type: str = "telegram"
    token: str
    default_parse_mode: Optional[str] = None


class DeliveryConfig(BaseModel):
    notifier: str
    chat_id: str | int
    template: str


class RouteMatch(BaseModel):
    poller_name: Optional[str] = None


class RouteConfig(BaseModel):
    name: str
    match: RouteMatch
    deliveries: List[DeliveryConfig]


class RootConfig(BaseModel):
    notifiers: Dict[str, Dict[str, Any]]
    routes: List[RouteConfig]
    pollers: Dict[str, Dict[str, Any]] 