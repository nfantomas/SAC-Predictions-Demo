# HR Cost Metric — Source of Truth (SAC)

This document defines the **single authoritative HR cost series** used by the demo.

## Approach chosen
**B (fallback)** — computed HR cost:
```
HR cost = FTE (SignedData) × avg_cost_per_fte (monthly)
```

Why: the `Cost` measure returns `null` for the locked slice in the current provider,
so a direct cost series is not reliable for the demo.

Default demo value:
- `avg_cost_per_fte_monthly = 8000`
- Currency: **EUR** (demo default; update if your tenant uses a different currency)

## Provider coordinates
- NamespaceID: `sac`
- ProviderID: `C6a0bs069fpsb2as72454aoh2v`
- ProviderName: `NICOLAS COPY_PLAN_HR_HC_PLANNING`

## DES query (copy/paste)
Endpoint:
```
GET https://ndcgroup.eu10.hcs.cloud.sap/api/v1/dataexport/providers/sac/C6a0bs069fpsb2as72454aoh2v/FactData
```

Query string:
```
$select=Date,Version,GLaccount,Function,Level,DataSource,Status,EmployeeType,CostCenters,Positions,SignedData
&$filter=Version eq 'public.Actual' and GLaccount eq 'FTE' and DataSource eq 'Basis' and Function eq '#' and Level eq '#' and Status eq '#' and EmployeeType eq '#' and CostCenters eq '#' and Positions eq '#'
&$orderby=Date asc
```

Curl example:
```bash
curl -sS -G \
  -H "Authorization: Bearer <TOKEN>" \
  -H "x-sap-sac-custom-auth: true" \
  --data-urlencode "$select=Date,Version,GLaccount,Function,Level,DataSource,Status,EmployeeType,CostCenters,Positions,SignedData" \
  --data-urlencode "$filter=Version eq 'public.Actual' and GLaccount eq 'FTE' and DataSource eq 'Basis' and Function eq '#' and Level eq '#' and Status eq '#' and EmployeeType eq '#' and CostCenters eq '#' and Positions eq '#'" \
  --data-urlencode "$orderby=Date asc" \
  "https://ndcgroup.eu10.hcs.cloud.sap/api/v1/dataexport/providers/sac/C6a0bs069fpsb2as72454aoh2v/FactData"
```

## Aggregation rule
- **SUM by month** after filtering (duplicates are summed).
- Date input is `YYYYMM`, normalized to `YYYY-MM-01`.

## Unit / currency
- `SignedData` represents **FTE** count.
- HR cost is derived as `FTE × avg_cost_per_fte_monthly` in **EUR** by default.
- If your tenant has an authoritative cost measure, update this document and set
  approach **A**.

## Sanity checks
- Query returns **rows > 0** spanning multiple months.
- `SignedData` should be within a plausible FTE range for the org.
- Computed monthly HR cost should be in the expected order of magnitude:
  - Example: FTE 100 × 8,000 EUR ≈ 800,000 EUR per month.
