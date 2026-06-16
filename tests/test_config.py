from ai_clerk.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("SECRET_KEY", "s3cret")
    monkeypatch.setenv("FERNET_KEY", "key-placeholder")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "[111, 222]")

    s = Settings(_env_file=None)

    assert s.bot_token == "123:abc"
    assert s.secret_key == "s3cret"
    assert s.admin_telegram_ids == [111, 222]
    assert s.database_url.startswith("sqlite")  # default
    assert s.invite_ttl_seconds == 86400        # default


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "x")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("FERNET_KEY", "x")

    s = Settings(_env_file=None)

    assert s.admin_telegram_ids == []
    assert s.log_level == "INFO"


def test_anthropic_settings_defaults(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "x")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("FERNET_KEY", "x")

    s = Settings(_env_file=None)

    assert s.anthropic_api_key is None
    assert s.anthropic_model == "claude-sonnet-4-6"


def test_anthropic_settings_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "x")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("FERNET_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-123")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    s = Settings(_env_file=None)

    assert s.anthropic_api_key == "sk-ant-123"
    assert s.anthropic_model == "claude-opus-4-8"
