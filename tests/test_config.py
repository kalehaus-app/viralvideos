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


def test_dotenv_autoloaded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        '# comment\nANTHROPIC_API_KEY="sk-test-123"\n', encoding="utf-8"
    )
    cfg = load_config("does-not-exist.yaml")
    assert cfg.secrets.anthropic_api_key == "sk-test-123"


def test_real_env_beats_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "real-key")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=file-key\n", encoding="utf-8")
    cfg = load_config("does-not-exist.yaml")
    # A real exported env var must not be overwritten by the .env file.
    assert cfg.secrets.anthropic_api_key == "real-key"
