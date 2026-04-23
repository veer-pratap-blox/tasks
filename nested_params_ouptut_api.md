# Jira Issue

## Summary
**POST `/block/{id}/outputs/v2` should support nested `params` JSON and apply safe defaults for omitted time fields**

## Issue Type
- Bug
- Technical Improvement

## Description

### Background
Builder and some API clients historically called `GET /block/{id}/outputs` using query parameters, often in an axios-style shape such as:

```json
{ "params": { ... } }
```

After the migration to `POST /block/{id}/outputs/v2` through `BlockKPIRouter` and the `BlockKPINew` / `V3` / `V4` / `V4Rust` handlers, request parsing relied on Flask-RESTful `RequestParser` with `parse_args()`, which only reads top-level JSON keys from the request body.

### Problem
When clients sent a nested payload like:

```json
{
  "params": {
    "dim_id": "16013",
    "scenario_id": 10957
  }
}
```

the parsed request object did not populate `dim_id` and `scenario_id` correctly.

As a result, the API could return `HTTP 200` with an incomplete or incorrect payload, for example:
- `dim_item_data = null`
- different time labels than the expected dimension pivot response
- smaller response payloads than the equivalent valid request

This looked like a calculation issue, but the actual root cause was request parsing.

A second issue is that builder cannot send some optional fields that the plan UI can send:
- `time_aggregation` (example: `"Y,Q,M"`)
- `time_filter` (example: `"all"`)
- `dim_sort` (example: `"ASC"`)

The `/outputs/v2` endpoint must remain usable even when these fields are omitted.

---

## Fix Implemented

### Request normalization helper
Added request normalization in:

- `modelAPI/util/block_outputs_request.py`

### Helper behavior
`parse_block_outputs_post_data(parser)` now:

- starts with `parser.parse_args()`
- merges `body["params"]` into the parsed arguments
- allows top-level body keys to override nested `params` values
- preserves query-string and form fallback behavior by keeping `parse_args()` first
- applies defaults when values are missing or empty:
  - `time_filter = "all"`
  - `time_aggregation = "Y,Q,M"`
  - `dim_sort = "ASC"`
- coerces `dim_id` to `str` when present, because downstream handlers call `dim_id.split(",")`

### Handlers updated
The helper is now wired into all POST KPI handlers using the shared parser:

- `modelAPI/resources/new_block_kpi.py`
- `modelAPI/resources/block_kpi_v3.py`
- `modelAPI/resources/block_kpi_v4.py`
- `modelAPI/resources/block_kpi_v4_rust.py`

For POST request handling, direct `parser.parse_args()` usage is replaced with `parse_block_outputs_post_data(parser)`.

---

## Expected Behavior After Fix

| Request Type | Expected Result |
|---|---|
| Flat JSON with `dim_id`, `scenario_id`, optional time fields | Works as before |
| Nested `{ "params": { ... } }` JSON with `dim_id`, `scenario_id` | Works with the same pivot and payload shape as flat JSON |
| Request omits `time_aggregation`, `time_filter`, `dim_sort` | Works and backend applies defaults |
| `GET /block/{id}/outputs?...` | Unchanged |

---

## Known Gaps / Out of Scope

### Not covered in this fix
- `indicator_filter` parity with legacy GET behavior  
  Legacy `GET BlockKPI` filters indicators via `apply_filter_on_indicators`, while V4 POST does not currently guarantee the same behavior for `indicator_filter` in JSON. This should be tracked separately if parity is required.

- Scenario resolution behavior  
  Handlers still require a resolvable scenario, either explicit or base scenario. If neither exists, failure behavior is unchanged.

### Out of scope
- Frontend builder migration from legacy GET to POST
- Full `indicator_filter` parity on V4 POST
- Cross-request caching or broader performance work

---

## Acceptance Criteria

- [ ] `POST /block/{id}/outputs/v2` returns `200` with a consistent KPI payload when the request body is only:

```json
{"params":{"dim_id":"<id>","scenario_id":<n>}}
```

- [ ] The above request works without `time_aggregation`, `time_filter`, and `dim_sort`.
- [ ] A flat top-level JSON request and an equivalent nested `params` request produce equivalent semantics for the same block, scenario, and dimension.
- [ ] Full top-level JSON behavior remains unchanged from pre-fix behavior.
- [ ] Query parameters continue to work for any arguments still passed via URL.
- [ ] Manual or unit verification is documented using `/outputs/v2` on block `16641` or an agreed test block.
- [ ] With the patch, all four request variants return a consistent first-indicator shape and correct `dim_item_data`.
- [ ] Without the patch, nested variants reproduce the original incorrect `dim_item_data` behavior.
- [ ] The fix is deployed to the target environment, or deployment is tracked separately.

---

## Scope

### In Scope
- ModelAPI request normalization for `POST /block/{id}/outputs/v2`
- Shared parser compatibility across relevant KPI handlers
- Defaulting of:
  - `time_aggregation`
  - `time_filter`
  - `dim_sort`

### Out of Scope
- Builder frontend migration from `GET /outputs` to `POST /outputs/v2`
- `indicator_filter` parity
- Performance or caching improvements beyond this parsing fix

---

## Components / Labels
- `modelAPI`
- `api`
- `block-outputs`
- `builder-compat`
- `regression-risk-low`

---

## References
- Route: `BlockKPIRouter -> /block/<int:block_id>/outputs/v2`
- Helper: `modelAPI/util/block_outputs_request.py`
- Related context: migration from `GET /outputs` with query params to `POST /outputs/v2` with JSON body

---

## QA Notes

### Test endpoint
```bash
POST http://127.0.0.1:5000/block/16641/outputs/v2
Authorization: Bearer <valid token>
```

### Test variants
1. Full top-level JSON:
   - `dim_id`
   - `scenario_id`
   - `time_aggregation`
   - `time_filter`
   - `dim_sort`

2. Minimal top-level JSON:
```json
{
  "dim_id": "16013",
  "scenario_id": 10957
}
```

3. Full nested JSON:
```json
{
  "params": {
    "dim_id": "16013",
    "scenario_id": 10957,
    "time_aggregation": "Y,Q,M",
    "time_filter": "all",
    "dim_sort": "ASC"
  }
}
```

4. Minimal nested JSON:
```json
{
  "params": {
    "dim_id": "16013",
    "scenario_id": 10957
  }
}
```

### Expected QA result
Variants 2, 3, and 4 should match variant 1 in:
- `dim_item_data`
- response shape
- dimension pivot behavior
- overall response size consistency

---

## Follow-up
Create a separate linked ticket for:

**Builder: switch `FetchBlockOutputs` from legacy GET `/outputs` to POST `/outputs/v2`**

Suggested link type:
- `relates to`
- `is blocked by`
