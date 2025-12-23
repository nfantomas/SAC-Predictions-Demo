import logging
import sys
from datetime import datetime, timezone

from config import ConfigError, load_config, safe_config_summary
from sac_connector.auth import AuthError, request_token
from sac_connector.export import ExportError, request_json_with_retry


logger = logging.getLogger("demo.auth_check")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    logger.info("Loaded config: %s", safe_config_summary(config))

    try:
        token_info = request_token(config)
    except AuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    des_base = config.dataexport_base_url
    if not des_base and config.tenant_url:
        des_base = f"{config.tenant_url.rstrip('/')}/api/v1/dataexport"
    if not des_base:
        print("Config error: Missing SAC_DATAEXPORT_BASE_URL or SAC_TENANT_URL", file=sys.stderr)
        return 1

    headers = {
        "Authorization": f"{token_info.token_type} {token_info.access_token}",
        "Accept": "application/json",
        "x-sap-sac-custom-auth": "true",
    }
    des_url = f"{des_base}/administration/Namespaces?$top=1"

    try:
        request_json_with_retry(des_url, headers=headers, timeout=20, max_attempts=3)
    except ExportError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    expires_at = token_info.expires_at.astimezone(timezone.utc)
    print(f"OK {expires_at.isoformat()}")
    print("DES OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
