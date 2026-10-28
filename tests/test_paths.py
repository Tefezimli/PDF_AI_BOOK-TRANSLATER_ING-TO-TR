"""core/paths.build_path: kalıcı çıktı kökü CWD'den bağımsız olmalı (bulgu #14).

Not: buradaki testler repo build/ dizinine GERÇEK dosya yazmaz —
create_or_load/save kullanan testler tests/test_checkpoint.py ve
tests/test_cache_manager.py'de tmp path'lerle çalışır.
"""
import os

import core.paths
from core.paths import PROJECT_ROOT, build_path


def test_project_root_is_parent_of_core_dir():
    # core/paths.py -> core/ -> proje kökü
    assert PROJECT_ROOT == os.path.dirname(os.path.dirname(os.path.abspath(core.paths.__file__)))
    assert os.path.isdir(os.path.join(PROJECT_ROOT, "core"))


def test_build_path_stays_same_when_cwd_changes(monkeypatch, tmp_path):
    monkeypatch.delenv("PDF_AI_WORKDIR", raising=False)
    before = build_path("checkpoints")
    monkeypatch.chdir(tmp_path)  # CWD değişse bile yol aynı kalmalı
    after = build_path("checkpoints")
    assert after == before
    assert os.path.commonpath([os.path.abspath(after), PROJECT_ROOT]) == PROJECT_ROOT
    assert after == os.path.join(PROJECT_ROOT, "build", "checkpoints")


def test_checkpoint_default_dir_is_build_path(monkeypatch):
    monkeypatch.delenv("PDF_AI_WORKDIR", raising=False)
    from core.checkpoint import CHECKPOINT_DIR

    # Yalnızca yol karşılaştırması: dosya oluşturulmaz.
    assert os.path.abspath(CHECKPOINT_DIR) == os.path.abspath(build_path("checkpoints"))
    assert os.path.commonpath([os.path.abspath(CHECKPOINT_DIR), PROJECT_ROOT]) == PROJECT_ROOT


def test_settings_path_is_build_path(monkeypatch):
    monkeypatch.delenv("PDF_AI_WORKDIR", raising=False)
    from core.user_settings import SETTINGS_PATH

    assert os.path.abspath(SETTINGS_PATH) == os.path.abspath(build_path("gui_settings.json"))


def test_cache_default_path_is_build_path(monkeypatch):
    monkeypatch.delenv("PDF_AI_WORKDIR", raising=False)
    from translators.cache_manager import SelfHealingCache

    # Yalnızca karşılaştırma: varsayılan yol build_path'ten türemeli.
    cache = SelfHealingCache()
    assert os.path.abspath(cache.cache_path) == os.path.abspath(
        build_path("translation_cache.json")
    )
    assert os.path.commonpath([os.path.abspath(cache.cache_path), PROJECT_ROOT]) == PROJECT_ROOT


def test_cache_save_uses_explicit_tmp_path(tmp_path):
    from translators.cache_manager import SelfHealingCache

    cache = SelfHealingCache(cache_path=str(tmp_path / "translation_cache.json"))
    cache.put("key", "deger")
    assert cache.save()
    assert (tmp_path / "translation_cache.json").exists()
