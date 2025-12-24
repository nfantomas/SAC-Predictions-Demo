from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence
from urllib import parse

import pandas as pd

from config import Config, load_config
from sac_connector.auth import AuthError, TokenInfo, request_token
from sac_connector.export import ExportError, _extract_rows, _next_url, request_json_with_retry


DEFAULT_DIM_FIELDS = [
    "Version",
    "Date",
    "GLaccount",
    "Function",
    "Level",
    "DataSource",
    "Status",
    "EmployeeType",
    "CostCenters",
    "Positions",
]


@dataclass(frozen=True)
class SliceSpec:
    measure: str
    filters: Dict[str, str]
    orderby: str = "Date asc"


DEFAULT_SLICE = SliceSpec(
    measure="SignedData",
    filters={
        "Version": "public.Actual",
        "GLaccount": "FTE",
        "DataSource": "Basis",
        "Function": "#",
        "Level": "#",
        "Status": "#",
        "EmployeeType": "#",
        "CostCenters": "#",
        "Positions": "#",
    },
)


def _build_filter_clause(filters: Dict[str, str]) -> str:
    parts = [f"{key} eq '{value}'" for key, value in filters.items()]
    return " and ".join(parts)


def _build_headers(token_info: TokenInfo) -> Dict[str, str]:
    return {
        "Authorization": f"{token_info.token_type} {token_info.access_token}",
        "Accept": "application/json",
        "x-sap-sac-custom-auth": "true",
    }


def _row_signature(row: Dict) -> tuple:
    return tuple(sorted(row.items()))


def fetch_timeseries(
    provider_id: str,
    namespace_id: str = "sac",
    config: Optional[Config] = None,
    slice_spec: SliceSpec = DEFAULT_SLICE,
    max_rows: Optional[int] = None,
    page_size: int = 1000,
    timeout: int = 30,
    max_attempts: int = 5,
) -> pd.DataFrame:
    cfg = config or load_config()
    if not cfg.tenant_url:
        raise ExportError("Missing SAC_TENANT_URL for timeseries fetch.")

    try:
        token_info = request_token(cfg)
    except AuthError as exc:
        raise ExportError(str(exc)) from exc

    select_fields = DEFAULT_DIM_FIELDS + [slice_spec.measure]
    params = {
        "$select": ",".join(select_fields),
        "$filter": _build_filter_clause(slice_spec.filters),
        "$orderby": slice_spec.orderby,
        "$top": str(page_size),
    }
    base_url = (
        f"{cfg.tenant_url.rstrip('/')}/api/v1/dataexport/providers/"
        f"{namespace_id}/{provider_id}/FactData"
    )
    url = base_url + "?" + parse.urlencode(params)
    headers = _build_headers(token_info)

    rows: List[Dict] = []
    seen = set()
    next_url: Optional[str] = url

    while next_url:
        payload = request_json_with_retry(
            next_url, headers=headers, timeout=timeout, max_attempts=max_attempts
        )
        page_rows = _extract_rows(payload)
        for row in page_rows:
            signature = _row_signature(row)
            if signature in seen:
                continue
            seen.add(signature)
            rows.append(row)
            if max_rows and len(rows) >= max_rows:
                next_url = None
                break
        if next_url:
            next_url = _next_url(payload, next_url)

    return pd.DataFrame(rows)
