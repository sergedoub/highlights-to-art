"""Configuration loading with environment-only secrets."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathsConfig:
    state_root: Path
    system_prompt: Path
    image_prompt: Path
    bowerbird_events: Path | None


@dataclass(frozen=True)
class GenerationConfig:
    model: str
    api_base: str
    width: int
    height: int
    publish_target: int
    max_api_calls_per_run: int
    max_attempts_per_highlight: int
    character_limit: int
    experiment_lengths: tuple[int, ...]
    experiment_samples_per_bucket: int
    experiment_min_pass_rate: float
    experiment_max_api_calls: int
    provider: str = "xai"
    size: str = "1024x1536"
    quality: str = "high"
    ocr_languages: str = "eng"


@dataclass(frozen=True)
class RotationConfig:
    active_size: int
    new_image_days: int


@dataclass(frozen=True)
class RelayConfig:
    host: str
    port: int
    max_body_bytes: int


@dataclass(frozen=True)
class AppConfig:
    root: Path
    paths: PathsConfig
    generation: GenerationConfig
    rotation: RotationConfig
    relay: RelayConfig
    relay_token: str
    xai_api_key: str
    api_key: str = ""


def _resolve(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(
    path: str | Path = "config.toml", *,
    require_xai: bool = False,
    require_provider: bool = False,
    require_relay: bool = False,
) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    root = config_path.parent
    _load_env_file(root / ".env")
    with config_path.open("rb") as stream:
        raw = tomllib.load(stream)
    paths = raw.get("paths", {})
    generation = raw.get("generation", {})
    rotation = raw.get("rotation", {})
    relay = raw.get("relay", {})
    provider = generation.get("provider", "xai")
    if provider not in {"openai", "xai"}:
        raise ValueError("generation.provider must be openai or xai")
    key_name = generation.get("api_key_env", "OPENAI_API_KEY" if provider == "openai" else "XAI_API_KEY")
    api_key = os.getenv(key_name, "")
    if (require_provider or require_xai) and not api_key:
        raise ValueError(f"{key_name} is required for {provider}")
    for name, default, minimum, maximum in (
        ("width", 1264, 64, 8192), ("height", 1680, 64, 8192),
        ("publish_target", 5, 1, 100), ("max_api_calls_per_run", 5, 1, 100),
        ("character_limit", 0, 0, 100000),
    ):
        if not minimum <= int(generation.get(name, default)) <= maximum:
            raise ValueError(f"generation.{name} must be between {minimum} and {maximum}")
    bowerbird = paths.get("bowerbird_events")
    relay_token = os.getenv("HIGHLIGHT_ART_RELAY_TOKEN", "")
    xai_api_key = os.getenv("XAI_API_KEY", "")
    if require_relay and len(relay_token) < 24:
        raise ValueError("HIGHLIGHT_ART_RELAY_TOKEN must contain at least 24 characters")
    return AppConfig(
        root=root,
        paths=PathsConfig(
            state_root=_resolve(root, paths.get("state_root", "var")),
            system_prompt=_resolve(root, paths.get("system_prompt", "prompts/system.md")),
            image_prompt=_resolve(root, paths.get("image_prompt", "prompts/image.md")),
            bowerbird_events=_resolve(root, bowerbird) if bowerbird else None,
        ),
        generation=GenerationConfig(
            model=generation.get("model", "gpt-image-2" if provider == "openai" else "grok-imagine-image-quality"),
            api_base=generation.get("api_base", "https://api.openai.com/v1" if provider == "openai" else "https://api.x.ai/v1").rstrip("/"),
            provider=provider,
            size=generation.get("size", "1024x1536"),
            quality=generation.get("quality", "high"),
            ocr_languages=generation.get("ocr_languages", "eng"),
            width=int(generation.get("width", 1264)),
            height=int(generation.get("height", 1680)),
            publish_target=int(generation.get("publish_target", 5)),
            max_api_calls_per_run=int(generation.get("max_api_calls_per_run", 5)),
            max_attempts_per_highlight=int(generation.get("max_attempts_per_highlight", 3)),
            character_limit=int(generation.get("character_limit", 0)),
            experiment_lengths=tuple(int(v) for v in generation.get("experiment_lengths", [80, 140, 220, 320])),
            experiment_samples_per_bucket=int(generation.get("experiment_samples_per_bucket", 5)),
            experiment_min_pass_rate=float(generation.get("experiment_min_pass_rate", 0.8)),
            experiment_max_api_calls=int(generation.get("experiment_max_api_calls", 60)),
        ),
        rotation=RotationConfig(
            active_size=int(rotation.get("active_size", 96)),
            new_image_days=int(rotation.get("new_image_days", 7)),
        ),
        relay=RelayConfig(
            host=relay.get("host", "127.0.0.1"),
            port=int(relay.get("port", 8788)),
            max_body_bytes=int(relay.get("max_body_bytes", 5_000_000)),
        ),
        relay_token=relay_token,
        xai_api_key=xai_api_key,
        api_key=api_key,
    )
