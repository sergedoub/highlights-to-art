import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "bin" / "install_kindle_plugin.py"
spec = importlib.util.spec_from_file_location("install_kindle_plugin", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_installer_writes_plugin_and_requires_smoke_tested_linkss(tmp_path, monkeypatch):
    mount = tmp_path / "Kindle"
    (mount / "koreader" / "plugins").mkdir(parents=True)
    source = tmp_path / "source" / "kindle" / "highlightart.koplugin"
    source.mkdir(parents=True)
    (source / "main.lua").write_text("return {}")
    monkeypatch.setattr(module, "ROOT", tmp_path / "source")
    plugin, settings = module.install(mount, "http://192.168.1.2:8788", "x" * 32)
    assert (plugin / "main.lua").exists()
    assert 'linkss_enabled\"] = false' in settings.read_text()

    try:
        module.install(mount, "http://192.168.1.2:8788", "x" * 32, enable_stock=True)
        raise AssertionError("expected missing linkss to fail")
    except ValueError as exc:
        assert "smoke-tested" in str(exc)
