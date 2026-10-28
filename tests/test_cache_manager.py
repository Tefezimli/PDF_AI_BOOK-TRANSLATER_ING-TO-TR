"""translators/cache_manager.py öz-onaran önbellek testleri."""
import json

from translators.cache_manager import CACHE_VERSION, SelfHealingCache


def make_cache(tmp_path):
    return SelfHealingCache(str(tmp_path / "cache.json"))


def test_put_and_get_roundtrip(tmp_path):
    cache = make_cache(tmp_path)
    cache.put("hello", "merhaba")
    assert cache.get("hello") == "merhaba"


def test_contaminated_mask_values_are_rejected(tmp_path):
    cache = make_cache(tmp_path)
    cache.put("bozuk", "ceviri CODE_0 temizlendi")
    assert cache.get("bozuk") is None


def test_save_and_reload_persists_entries(tmp_path):
    cache = make_cache(tmp_path)
    cache.put("hello", "merhaba")
    assert cache.save()

    reloaded = SelfHealingCache(str(tmp_path / "cache.json"))
    assert reloaded.get("hello") == "merhaba"


def test_heals_known_terminology_gaffes_on_load(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(
        json.dumps({"__version__": "eski", "k": "Bakım koşulları önemlidir"}, ensure_ascii=False),
        encoding="utf-8",
    )
    cache = SelfHealingCache(str(cache_file))
    healed = cache.get("k")
    assert "farketmez durumları" in healed
    assert "Bakım koşulları" not in healed


def test_cache_version_stamped(tmp_path):
    cache = make_cache(tmp_path)
    assert cache.data["__version__"] == CACHE_VERSION


def test_save_is_atomic_crash_keeps_old_file(tmp_path, monkeypatch):
    """Yazım ortasında çökme simülasyonu: yarım JSON eski dosyayı bozmamalı."""
    import translators.cache_manager as cm

    cache_file = tmp_path / "cache.json"
    cache = SelfHealingCache(str(cache_file))
    cache.put("anahtar", "eski ceviri")
    assert cache.save()

    def broken_dump(obj, fp, *args, **kwargs):
        fp.write('{"yarim": ')  # floş anında çökme: yarım yaz
        raise RuntimeError("crash")

    monkeypatch.setattr(cm.json, "dump", broken_dump)
    cache.put("yeni_anahtar", "kaydedilmemis")
    assert cache.save() is False  # sessiz False davranışı korunur

    # atomiklik kanıtı: eski dosya içeriği değişmemiş, yarımı yutmadı
    reloaded = SelfHealingCache(str(cache_file))
    assert reloaded.get("anahtar") == "eski ceviri"
    assert reloaded.get("yeni_anahtar") is None
    assert not (tmp_path / "cache.json.tmp").exists()  # tmp kalıntısı temizlenir


def test_save_without_directory_component(tmp_path, monkeypatch):
    """cache_path dizinsizse ("cache.json") os.makedirs("") FileNotFoundError atmamalı."""
    monkeypatch.chdir(tmp_path)
    cache = SelfHealingCache("cache.json")
    cache.put("x", "y")
    assert cache.save()
    assert SelfHealingCache("cache.json").get("x") == "y"
