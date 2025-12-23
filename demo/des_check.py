import logging
import sys

from config import ConfigError, load_config, safe_config_summary
from sac_connector.auth import AuthError, request_token
from sac_connector.export import ExportError, request_json_with_retry


logger = logging.getLogger("demo.des_check")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    logger.info("Loaded config: %s", safe_config_summary(config))

    if not config.dataexport_base_url:
        print("Config error: Missing SAC_DATAEXPORT_BASE_URL", file=sys.stderr)
        return 1

    try:
        token_info = request_token(config)
    except AuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    headers = {
        "Authorization": f"{token_info.token_type} {token_info.access_token}",
        "Accept": "application/json",
        "x-sap-sac-custom-auth": "true",
    }
    url = f"{config.dataexport_base_url}/administration/Namespaces?$top=1"

    try:
        request_json_with_retry(url, headers=headers, timeout=30, max_attempts=3)
    except ExportError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("DES OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
