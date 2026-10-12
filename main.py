import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI(title="Effective Configuration API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


def normalize_key(key: str) -> str:
    key = key.strip()

    if key.startswith("APP_"):
        key = key[4:]

    key = key.lower()

    if key == "num_workers":
        return "workers"

    return key


def coerce(key: str, value):
    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in (
            "true",
            "1",
            "yes",
            "on",
        )

    return str(value)


def apply_layer(config: dict, layer: dict):
    for raw_key, value in layer.items():
        if value is None:
            continue

        key = normalize_key(str(raw_key))

        if key in config:
            config[key] = coerce(key, value)


@app.get("/effective-config")
def effective_config(
    set: Optional[list[str]] = Query(default=None)
):
    # Layer 1: Hardcoded defaults
    config = DEFAULTS.copy()

    # Layer 2: Environment-specific YAML
    env_name = os.getenv("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{env_name}.yaml"

    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_layer = yaml.safe_load(file) or {}

        if isinstance(yaml_layer, dict):
            apply_layer(config, yaml_layer)

    # Layer 3: .env file
    env_file = dotenv_values(BASE_DIR / ".env")
    apply_layer(config, env_file)

    # Layer 4: OS environment variables (APP_* only)
    os_layer = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_")
    }
    apply_layer(config, os_layer)

    # Layer 5: CLI-style query overrides
    # Supports multiple parameters: ?set=port=9000&set=debug=true
    for item in set or []:
        if "=" not in item:
            continue

        raw_key, raw_value = item.split("=", 1)
        key = normalize_key(raw_key)

        if key in config:
            config[key] = coerce(key, raw_value)

    # Never expose the actual API key
    config["api_key"] = "****"

    return config