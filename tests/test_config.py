import logging

import pytest

from config import Config, ConfigError, load_config, safe_config_summary


def test_config_missing_env(monkeypatch):
    for key in ["SAC_TOKEN_URL", "SAC_CLIENT_ID", "SAC_CLIENT_SECRET"]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError) as exc:
        load_config(env_path="")
    message = str(exc.value)
    assert "SAC_TOKEN_URL" in message
    assert "SAC_CLIENT_ID" in message
    assert "SAC_CLIENT_SECRET" in message


def test_logging_masks_secret(caplog):
    config = Config(
        tenant_url="https://example.sap",
        auth_url="https://example.auth",
        token_url="https://example.token",
        client_id="client-id",
        client_secret="supersecret",
        dataexport_base_url="https://example.export",
        namespace_id="sac",
        provider_id="provider",
    )
    caplog.set_level(logging.INFO)
    logging.getLogger("test").info("Loaded config: %s", safe_config_summary(config))
    assert "supersecret" not in caplog.text
