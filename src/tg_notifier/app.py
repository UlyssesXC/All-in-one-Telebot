from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any, Dict, List, Tuple, Optional

from .utils import configure_logging, load_yaml_with_env
from .notifiers.telegram import TelegramNotifier
from .pollers.http_json import HTTPJSONPoller
from .routing.router import Router
from .state.file_state import FileStateStore


STATE_DIR = ".state"


def build_notifiers(config: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for name, conf in (config.get("notifiers") or {}).items():
        type_ = conf.get("type")
        if type_ == "telegram":
            result[name] = TelegramNotifier(
                token=conf.get("token"),
                default_parse_mode=conf.get("default_parse_mode"),
            )
    return result


def build_pollers(config: Dict[str, Any]) -> Tuple[Dict[str, HTTPJSONPoller], Dict[str, Dict[str, Any]]]:
    pollers: Dict[str, HTTPJSONPoller] = {}
    options: Dict[str, Dict[str, Any]] = {}
    for name, conf in (config.get("pollers") or {}).items():
        type_ = conf.get("type")
        if type_ == "http_json":
            pollers[name] = HTTPJSONPoller(
                name=name,
                request=conf.get("request") or {},
                extract=conf.get("extract") or {},
                interval_seconds=int(conf.get("interval_seconds", 15)),
                id_path=conf.get("id_path"),
                updated_at_path=conf.get("updated_at_path"),
                fields=conf.get("fields") or {},
            )
            if conf.get("post_process"):
                options[name] = conf["post_process"]
    return pollers, options


def _apply_post_process(unseen: List[Dict[str, Any]], opt: Dict[str, Any]) -> List[Dict[str, Any]]:
    pick = opt.get("pick") or {}
    if pick.get("type") == "lowest_by":
        key = pick.get("key")
        if key and unseen:
            try:
                return [min(unseen, key=lambda x: float(x.get(key) or 0))]
            except Exception:
                return unseen[:1]
    return unseen


def _apply_pre_filter(events: List[Dict[str, Any]], opt: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = events
    where = opt.get("where") or {}
    if where:
        result = [e for e in result if all(e.get(f) == val for f, val in where.items())]
    where_gte = opt.get("where_gte") or {}
    if where_gte:
        filtered: List[Dict[str, Any]] = []
        for e in result:
            ok = True
            for f, min_val in where_gte.items():
                try:
                    v = float(e.get(f) or 0)
                    if v < float(min_val):
                        ok = False
                        break
                except Exception:
                    ok = False
                    break
            if ok:
                filtered.append(e)
        result = filtered
    return result


async def run(config_path: str, once: bool = False) -> None:
    configure_logging(logging.INFO)
    config = load_yaml_with_env(config_path)

    notifiers = build_notifiers(config)
    router = Router(notifiers)
    pollers, poller_opts = build_pollers(config)
    state = FileStateStore(STATE_DIR)

    async def worker(poller_name: str, poller: HTTPJSONPoller) -> None:
        opt = poller_opts.get(poller_name) or {}
        price_key = (opt.get("pick") or {}).get("key") or "price"
        while True:
            async for events in poller.poll():
                if not events:
                    if once:
                        break
                    continue
                # pre-filter
                events = _apply_pre_filter(events, opt)
                if not events:
                    if once:
                        break
                    continue
                # find current lowest by price_key among ALL current events (not just unseen)
                try:
                    current_lowest = min(events, key=lambda x: float(x.get(price_key) or 0))
                except Exception:
                    current_lowest = events[0]

                tracking = await state.load_tracking(poller_name)
                tracking_id = tracking.get("id") if tracking else None
                tracking_price = tracking.get("price") if tracking else None

                # If no tracking yet -> start tracking and notify this lowest
                if not tracking:
                    await state.save_tracking(poller_name, {
                        "id": current_lowest.get("__id__") or current_lowest.get("id"),
                        "price": current_lowest.get(price_key),
                        "total_amount": current_lowest.get("total_amount"),
                        "value": current_lowest.get("value"),
                    })
                    msg = "🛒 WLFI 新挂出最低价: 单价=${price} 数量=${total_amount} 总金额=${value} 前往：https://pro.whales.market/pre/Ethereum/WLFI?id={id} 购买"
                    current_lowest["id"] = current_lowest.get("__id__") or current_lowest.get("id")
                    current_lowest["__template__"] = msg
                    await router.deliverers(config.get("routes") or [], poller_name, [current_lowest])
                else:
                    # Is tracking order still present?
                    still_present = any((e.get("__id__") or e.get("id")) == tracking_id for e in events)
                    current_lowest_price = float(current_lowest.get(price_key) or 0)
                    tracking_price_f = float(tracking_price or 0)

                    if not still_present:
                        # Tracked order eaten/removed -> notify removal and new lowest
                        removal_msg = "✅ 之前最低价已成交或撤单: 单价=${price} 数量=${total_amount} 总金额=${value}\n➡️ 当前最新最低价: 单价=${new_price} 数量=${new_total} 总金额=${new_value}"
                        payload = {
                            "price": tracking.get("price"),
                            "total_amount": tracking.get("total_amount"),
                            "value": tracking.get("value"),
                            "new_price": current_lowest.get(price_key),
                            "new_total": current_lowest.get("total_amount"),
                            "new_value": current_lowest.get("value"),
                            "__template__": removal_msg,
                        }
                        await router.deliverers(config.get("routes") or [], poller_name, [payload])
                        await state.save_tracking(poller_name, {
                            "id": current_lowest.get("__id__") or current_lowest.get("id"),
                            "price": current_lowest.get(price_key),
                            "total_amount": current_lowest.get("total_amount"),
                            "value": current_lowest.get("value"),
                        })
                    else:
                        # If still present but a lower price appears -> switch tracking and notify new lowest
                        if current_lowest_price < tracking_price_f:
                            switch_msg = "🛒 出现更低价新挂单: 单价=${price} 数量=${total_amount} 总金额=${value} 前往：https://pro.whales.market/pre/Ethereum/WLFI?id={id} 购买"
                            current_lowest["id"] = current_lowest.get("__id__") or current_lowest.get("id")
                            current_lowest["__template__"] = switch_msg
                            await router.deliverers(config.get("routes") or [], poller_name, [current_lowest])
                            await state.save_tracking(poller_name, {
                                "id": current_lowest.get("__id__") or current_lowest.get("id"),
                                "price": current_lowest.get(price_key),
                                "total_amount": current_lowest.get("total_amount"),
                                "value": current_lowest.get("value"),
                            })
                        # else: do nothing

                if once:
                    break
            if once:
                break

    tasks = [asyncio.create_task(worker(name, poller)) for name, poller in pollers.items()]
    if not tasks:
        logging.getLogger(__name__).warning("No pollers configured. Exiting.")
        return

    try:
        await asyncio.gather(*tasks)
    finally:
        await asyncio.gather(*[n.close() for n in notifiers.values() if hasattr(n, "close")])
        await asyncio.gather(*[p.close() for p in pollers.values() if hasattr(p, "close")])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--once", action="store_true", help="Run one fetch cycle then exit")
    args = parser.parse_args()
    asyncio.run(run(args.config, once=args.once))


if __name__ == "__main__":
    main() 