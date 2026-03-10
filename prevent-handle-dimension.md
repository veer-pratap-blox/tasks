## Fix 1 — `calc_engine/util.py`

Add a new shared helper function `detect_dimension_mismatch(block, actual_data_values)`.

**What it does**
- Scans every row in `actual_data_values["actual_data"]`
- Extracts all numeric string keys (dimension IDs), ignoring `"value"`
- Compares them against `block.dimensions` (current block schema)
- Returns a list of dimension IDs present in actuals but missing from the block

**Does not** mutate data, does not raise, is reusable across all call sites.

---

## Fix 2 — `calc_engine/block_calculate_v3.py`

**Location:** inside `_load_actual_data()`

**Changes**
1. Call `detect_dimension_mismatch` before building `actual_df`
2. Filter out rows referencing missing dimension IDs (Option A — drop rows)
3. Log at detection: which dims are missing, how many rows dropped
4. Wrap `actual_df.join(block_df, how="right", on=columns)` in a `try/except`
5. On exception: log with `model_id`, `block_id`, `indicator_id`, `scenario_id`, `action=actuals_skipped_on_exception` and return `forecast_df` safely without re-raising

---

## Fix 3 — `calc_engine/calculate_input_indicator.py`

**Changes**
1. Call `detect_dimension_mismatch` before building `actual_df`
2. Filter out rows referencing missing dimension IDs
3. Log at detection with same required fields
4. Wrap both of these in `try/except`:
   - `block_df.update(actual_df, on=cols)`
   - `actual_data_df.join(actual_df, how="left", on=actual_df_cols)`
5. On exception: log and continue without re-raising — do not crash the model

---

## Fix 4 — `calc_engine/data_inputs.py`

**Location:** inside `get_actual_data_dataframe()`

**Changes**
1. Call `detect_dimension_mismatch` before building `actual_df` from stored JSON
2. Filter out rows referencing missing dimension IDs
3. Log at detection with same required fields
4. Wrap the dataframe build + any downstream join/stack in `try/except`
5. On exception: log and return an empty DataFrame safely instead of propagating the error

---

## Fix 5 — `resources/dimensions.py` + `services/routes.py`

**Add new class** `DimensionUsage(Resource)` in `resources/dimensions.py`

**Endpoint**
```
GET /dimension/<int:id>/usage
```

**Returns**
```json
{
  "dimension_id": 39096,
  "blocks": [{ "id": 123, "name": "Revenue Block" }],
  "indicators_with_actuals": [{ "id": 277201, "name": "Bookings", "block_id": 123 }],
  "indicators_in_formulas": [{ "id": 277205, "name": "Ending ARR", "block_id": 123 }],
  "models": [{ "id": 15013, "name": "Q1 Plan" }]
}
```

**Queries to implement**
- Blocks: find blocks where this dimension exists in `block.dimensions`
- Indicators with actuals: scan `actual_data_values["actual_data"]` rows for this dimension ID
- Indicators in formulas: reuse existing `check_dimension_usage_in_indicators()`

**Register route** in `services/routes.py`:
```python
api.add_resource(DimensionUsage, "/dimension/<int:id>/usage")
```

**Permission:** same as existing dimension read — `check_model_permission(..., action="is_read")`

---

## Required log fields (all 4 fixes)

Every log emitted across Fix 2, 3, and 4 must include at minimum:

| Field | Description |
|---|---|
| `model_id` | Model the block belongs to |
| `block_id` | Block being calculated |
| `indicator_id` | Indicator whose actuals have the mismatch |
| `scenario_id` | Active scenario |
| `missing_dimension_ids` | List of stale dim IDs found in actuals |
| `action` | One of: `actuals_rows_dropped`, `actuals_skipped_on_exception` |
| `rows_before` | Row count before filtering |
| `rows_after` | Row count after filtering |
