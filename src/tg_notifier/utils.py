import os
import re
import json
import logging
from typing import Any, Dict, Optional

import yaml
from decimal import Decimal, ROUND_HALF_UP

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def expand_env_vars(value: Any) -> Any:
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, "")
        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env_vars(v) for v in value]
    return value


def load_yaml_with_env(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return expand_env_vars(data)


def get_by_path(data: Any, path: Optional[str]) -> Any:
    if path is None or path == "":
        return data
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


class SafeFormatDict(dict):
    def __missing__(self, key):  # type: ignore[override]
        return ""


def render_template(template: str, mapping: Dict[str, Any]) -> str:
    safe = SafeFormatDict({k: ("" if v is None else v) for k, v in mapping.items()})
    try:
        return template.format_map(safe)
    except Exception:
        return template


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def format_number_2dp_no_sci(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        d = Decimal(str(value))
    elif isinstance(value, Decimal):
        d = value
    else:
        return str(value)
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = format(q, "f")  # no scientific notation
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def format_numbers_in_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    formatted: Dict[str, Any] = {}
    for k, v in mapping.items():
        if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
            formatted[k] = format_number_2dp_no_sci(v)
        else:
            formatted[k] = v
    return formatted 