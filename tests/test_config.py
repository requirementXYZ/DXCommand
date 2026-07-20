import json

from app.config import DEFAULTS, _merge, load_config, save_config


def test_merge_nested():
    out = _merge({"a": {"x": 1, "y": 2}, "b": 3}, {"a": {"y": 9}})
    assert out == {"a": {"x": 1, "y": 9}, "b": 3}


def test_defaults_not_mutated_by_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("DXDASH_DEMO", "1")
    cfg = load_config(tmp_path / "none.json")
    assert cfg["rig"]["backend"] == "simulator"
    # the module-level DEFAULTS must stay pristine
    assert DEFAULTS["rig"]["backend"] == "omnirig"
    assert DEFAULTS["cluster"]["simulate"] is False


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("DXDASH_DEMO", raising=False)
    path = tmp_path / "config.json"
    cfg = load_config(path)
    cfg.raw = _merge(cfg.raw, {"callsign": "ZL4AS",
                               "rig": {"backend": "simulator", "rig_number": 2},
                               "cluster": {"simulate": True}})
    save_config(cfg.raw, path)
    cfg2 = load_config(path)
    assert cfg2.callsign == "ZL4AS"
    assert cfg2["rig"]["backend"] == "simulator"
    assert cfg2["rig"]["rig_number"] == 2
    assert cfg2["cluster"]["simulate"] is True
    # untouched keys keep defaults
    assert cfg2["wsjtx"]["udp_port"] == 2237


def test_save_only_known_keys(tmp_path):
    cfg = load_config(tmp_path / "c.json")
    cfg.raw["_transient_junk"] = {"x": 1}
    save_config(cfg.raw, tmp_path / "c.json")
    saved = json.loads((tmp_path / "c.json").read_text())
    assert "_transient_junk" not in saved
    assert "callsign" in saved
