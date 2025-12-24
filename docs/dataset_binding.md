# Dataset Binding — Locked Demo Slice (SAC DES)

This document defines the **locked slice** query used by the demo to fetch a
single, stable time series from the SAC provider.

## Provider coordinates
- NamespaceID: `sac`
- ProviderID: `C6a0bs069fpsb2as72454aoh2v`
- ProviderName: `NICOLAS COPY_PLAN_HR_HC_PLANNING`

## Locked slice query (copy/paste)
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

### Curl example (token redacted)
```bash
curl -sS -G \
  -H "Authorization: Bearer <TOKEN>" \
  -H "x-sap-sac-custom-auth: true" \
  --data-urlencode "$select=Date,Version,GLaccount,Function,Level,DataSource,Status,EmployeeType,CostCenters,Positions,SignedData" \
  --data-urlencode "$filter=Version eq 'public.Actual' and GLaccount eq 'FTE' and DataSource eq 'Basis' and Function eq '#' and Level eq '#' and Status eq '#' and EmployeeType eq '#' and CostCenters eq '#' and Positions eq '#'" \
  --data-urlencode "$orderby=Date asc" \
  "https://ndcgroup.eu10.hcs.cloud.sap/api/v1/dataexport/providers/sac/C6a0bs069fpsb2as72454aoh2v/FactData"
```

## Measure and filter rationale
- **Measure:** `SignedData` (stable series for demo).
- **Filters:**
  - `Version = public.Actual` to ensure actuals only.
  - `GLaccount = FTE` to target the headcount series.
  - `DataSource = Basis` to remove mix-in sources.
  - Remaining dimensions fixed to `#` (not applicable) for a minimal slice.

## Aggregation rule
- After filtering, **sum `SignedData` by `Date` (month)** to produce the demo series.

## Notes
- The DES FactData endpoint requires **all key columns** in `$select`, even if
  filtered to constant values. This is why the query includes all dimensions.
