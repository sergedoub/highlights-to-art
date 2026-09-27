"""Top-level newest-Kindle-highlight orchestration."""
from .config import AppConfig
from .store import Store
from .workflow import latest_run


def run_pipeline(config: AppConfig, *, target: int | None = None) -> dict:
    store = Store(config.paths.state_root)
    rows = [row for row in store.iter_highlights() if row.source == "kindle-clippings"]
    return latest_run(config, rows, count=target or config.generation.publish_target, generate=True)
