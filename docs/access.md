# SAC Access Checklist (OAuth + Export)

This checklist defines the minimum SAC access prerequisites to run the demo. It is written to be executed by a second engineer on a fresh SAC tenant.

## 1) SAC-side configuration (required once)
In SAC UI (Admin):
- Go to **System → Administration → App Integration → OAuth Clients**
- Create an OAuth client:
  - **Purpose:** API Access
  - **Access:** Data Export Service
  - **Grant Type:** Client Credentials

Save and copy:
- `CLIENT_ID`
- `CLIENT_SECRET`
- `TOKEN_URL` (shown in the UI)

Result: you now have everything needed for a headless integration.

## 2) Local configuration (env vars)
Set these environment variables (or put them into `.env` locally and load them):

```bash
export SAC_TENANT_URL="https://ndcgroup.eu10.hcs.cloud.sap"
export SAC_TOKEN_URL="https://ndcgroup.authentication.eu10.hana.ondemand.com/oauth/token"
export SAC_CLIENT_ID="..."
export SAC_CLIENT_SECRET="..."
```

Rules:
- Never commit `SAC_CLIENT_SECRET` to git.
- Do not print secrets or tokens in logs.

## 3) Token acquisition (core flow)
Request:
- **Method:** POST
- **URL:** `$SAC_TOKEN_URL`
- **Body:** `grant_type=client_credentials`
- **Auth:** HTTP Basic Auth using `client_id:client_secret`

Example:
```bash
TOKEN="$(
  curl -sS -u "$SAC_CLIENT_ID:$SAC_CLIENT_SECRET" \
    -d "grant_type=client_credentials" \
    "$SAC_TOKEN_URL" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
)"
echo "Got token: ${#TOKEN} chars"
```

If this fails, print the full JSON response (it usually contains `error` and `error_description`).

## 4) Calling SAC Data Export Service (DES)
Every DES call must include:
- `Authorization: Bearer <TOKEN>`
- `x-sap-sac-custom-auth: true`

Minimal connectivity test:
```bash
curl -sS -o /dev/null -w "DES HTTP status: %{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-sap-sac-custom-auth: true" \
  "$SAC_TENANT_URL/api/v1/dataexport/administration/Namespaces?\$top=1"
```

Expected: `DES HTTP status: 200`

## 5) Python auth check (demo)
```bash
poetry run python -m demo.auth_check
```

This validates token acquisition and a DES connectivity check to
`/administration/Namespaces?$top=1`.

## 6) Common failure meanings (fast troubleshooting)
- **401 from token endpoint**: wrong client id/secret or wrong token URL.
- **403 from DES**: OAuth client not granted DES access, or missing tenant permissions.
- **404 from DES**: wrong tenant base URL or wrong path.
- **429**: rate limit; add retry/backoff in export calls.
