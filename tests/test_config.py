import os

from viralagent.config import load_config


def test_defaults_loaded():
    cfg = load_config("does-not-exist.yaml")
    assert cfg.get("llm.model") == "claude-opus-4-8"
    assert cfg.content["format"] in ("short", "long")


def test_env_override(monkeypatch):
    monkeypatch.setenv("VIRALAGENT__CONTENT__CADENCE_HOURS", "6")
    monkeypatch.setenv("VIRALAGENT__LLM__USE_WEB_SEARCH", "false")
    cfg = load_config("does-not-exist.yaml")
    assert cfg.content["cadence_hours"] == 6
    assert cfg.get("llm.use_web_search") is False


def test_yaml_merge(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("content:\n  format: long\n", encoding="utf-8")
    cfg = load_config(str(cfg_file))
    assert cfg.content["format"] == "long"
    # Unspecified keys keep their defaults.
    assert cfg.content["words_per_minute"] == 165
