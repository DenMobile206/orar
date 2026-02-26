"""Loads and caches config.yaml."""
import yaml
import os
from typing import Any, Dict

_config: Dict[str, Any] = {}


def load(path: str) -> Dict[str, Any]:
    global _config
    with open(path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    return _config


def get() -> Dict[str, Any]:
    return _config
