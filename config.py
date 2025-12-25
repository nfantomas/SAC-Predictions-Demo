import os
from dataclasses import dataclass
from typing import Dict, Iterable, Optional


class ConfigError(Exception):
    pass


SECRET_KEYS = {"- d5a8f5c3-4096-4bea-98ac-c3d27854999b$-vG4IFa1FafjRJVqlfrWklxmzna2NJOVfcbtwDr8XU8="}


def _strip_quotes(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def load_env_file(path: str, override: bool = False) -> None:
    if not path or not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            value = _strip_quotes(value.strip())
            if override or key not in os.environ:
                os.environ[key] = value


def _missing_required(env: Dict[str, str], required: Iterable[str]) -> Iterable[str]:
    return [key for key in required if not env.get(key)]


def mask_secret(value: Optional[str], show_last: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= show_last:
        return "*" * len(value)
    return "*" * (len(value) - show_last) + value[-show_last:]


def safe_env_snapshot(env: Dict[str, str]) -> Dict[str, str]:
    safe = {}
    for key, value in env.items():
        if key in SECRET_KEYS:
            safe[key] = mask_secret(value)
        else:
            safe[key] = value
    return safe


@dataclass(frozen=True)
class Config:
    tenant_url: Optional[str]
    auth_url: Optional[str]
    token_url: str
    client_id: str
    client_secret: str
    dataexport_base_url: Optional[str]
    namespace_id: Optional[str]
    provider_id: Optional[str]


def safe_config_summary(config: Config) -> Dict[str, str]:
    return {
        "SAC_TENANT_URL": config.tenant_url or "",
        "SAC_AUTH_URL": config.auth_url or "",
        "SAC_TOKEN_URL": config.token_url,
        "SAC_CLIENT_ID": config.client_id,
        "SAC_CLIENT_SECRET": mask_secret(config.client_secret),
        "SAC_DATAEXPORT_BASE_URL": config.dataexport_base_url or "",
        "SAC_NAMESPACE_ID": config.namespace_id or "",
        "SAC_PROVIDER_ID": config.provider_id or "",
        "ANTHROPIC_API_KEY": mask_secret(os.getenv("ANTHROPIC_API_KEY", "")),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", ""),
        "LLM_TIMEOUT_SECONDS": os.getenv("LLM_TIMEOUT_SECONDS", ""),
        "LLM_MAX_RETRIES": os.getenv("LLM_MAX_RETRIES", ""),
    }


def load_config(env_path: str = ".env") -> Config:
    load_env_file(env_path)

    env = {
        "SAC_TENANT_URL": os.getenv("SAC_TENANT_URL", ""),
        "SAC_AUTH_URL": os.getenv("SAC_AUTH_URL", ""),
        "SAC_TOKEN_URL": os.getenv("SAC_TOKEN_URL", ""),
        "SAC_CLIENT_ID": os.getenv("SAC_CLIENT_ID", ""),
        "SAC_CLIENT_SECRET": os.getenv("SAC_CLIENT_SECRET", ""),
        "SAC_DATAEXPORT_BASE_URL": os.getenv("SAC_DATAEXPORT_BASE_URL", ""),
        "SAC_NAMESPACE_ID": os.getenv("SAC_NAMESPACE_ID", ""),
        "SAC_PROVIDER_ID": os.getenv("SAC_PROVIDER_ID", ""),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "ANTHROPIC_MODEL": os.getenv("ANTHROPIC_MODEL", ""),
        "LLM_TIMEOUT_SECONDS": os.getenv("LLM_TIMEOUT_SECONDS", ""),
        "LLM_MAX_RETRIES": os.getenv("LLM_MAX_RETRIES", ""),
    }

    missing = _missing_required(
        env,
        required=[
            "SAC_TOKEN_URL",
            "SAC_CLIENT_ID",
            "SAC_CLIENT_SECRET",
        ],
    )
    if missing:
        raise ConfigError(
            "Missing required env vars: " + ", ".join(sorted(missing))
        )

    return Config(
        tenant_url=env["SAC_TENANT_URL"] or None,
        auth_url=env["SAC_AUTH_URL"] or None,
        token_url=env["SAC_TOKEN_URL"],
        client_id=env["SAC_CLIENT_ID"],
        client_secret=env["SAC_CLIENT_SECRET"],
        dataexport_base_url=env["SAC_DATAEXPORT_BASE_URL"] or None,
        namespace_id=env["SAC_NAMESPACE_ID"] or None,
        provider_id=env["SAC_PROVIDER_ID"] or None,
    )
