"""PDF_AI_WORKDIR: kalıcı dosyaların kökü tek yerden çözülür."""
import importlib
import os


def reload_with_workdir(monkeypatch, tmp_path, module_name):
    monkeypatch.setenv("PDF_AI_WORKDIR", str(tmp_path))
    import core.paths
    importlib.reload(core.paths)
    module = importlib.import_module(module_name)
    return importlib.reload(module)


def teardown_module():
    # Modül durumunu varsayılana döndür (sonraki test dosyaları etkilenmesin).
    import core.paths
    os.environ.pop("PDF_AI_WORKDIR", None)
    importlib.reload(core.paths)


def test_checkpoint_dir_follows_workdir(monkeypatch, tmp_path):
    import core.checkpoint as ckpt_mod
    mod = reload_with_workdir(monkeypatch, tmp_path, "core.checkpoint")
    assert mod.CHECKPOINT_DIR.startswith(str(tmp_path))
    monkeypatch.delenv("PDF_AI_WORKDIR")
    importlib.reload(ckpt_mod)  # varsayılanı geri getir


def test_settings_path_follows_workdir(monkeypatch, tmp_path):
    mod = reload_with_workdir(monkeypatch, tmp_path, "core.user_settings")
    assert mod.SETTINGS_PATH.startswith(str(tmp_path))
    assert mod.save_settings(dict(mod.DEFAULTS))
    assert (tmp_path / "gui_settings.json").exists()


def test_cache_default_path_follows_workdir(monkeypatch, tmp_path):
    mod = reload_with_workdir(monkeypatch, tmp_path, "translators.cache_manager")
    cache = mod.SelfHealingCache()
    assert cache.cache_path.startswith(str(tmp_path))
    cache.put("k", "v")
    assert cache.save()
    assert (tmp_path / "translation_cache.json").exists()


def test_build_dir_default_without_env(monkeypatch):
    monkeypatch.delenv("PDF_AI_WORKDIR", raising=False)
    import core.paths
    importlib.reload(core.paths)
    assert core.paths.build_dir("x") == os.path.join("build", "x")
