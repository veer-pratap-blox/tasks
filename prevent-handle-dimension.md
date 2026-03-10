## Fix 1 — `calc_engine/util.py`

Add a new function:

`detect_dimension_mismatch(block, actual_data_values)`

**Purpose**
- Compare dimension keys in the stored actuals JSON against `block.dimensions`.
- Detect rows referencing dimensions that no longer exist on the block.

**Returns**
- A list of **dimension IDs** that are present in the actuals data but missing from the block.

---

## Fix 2 — `calc_engine/block_calculate_v3.py`

**Location:** inside `_load_actual_data`

**Changes**
1. Before building `actual_df`, call `detect_dimension_mismatch`.
2. Filter out rows referencing missing dimension IDs.
3. Wrap the following line in a `try/except` block:

```python
actual_df.join(block_df)
```

**Behavior**
- Log the error if it occurs.
- Return safely instead of crashing the entire model calculation.

---

## Fix 3 — `calc_engine/calculate_input_indicator.py`

Add a **guard step** before both operations:

```python
block_df.update(actual_df)
actual_data_df.join(actual_df)
```

**Changes**
- Filter out rows with invalid/missing dimension IDs using the same mismatch detection logic.
- Wrap operations in a `try/except` to catch **Polars errors** as a fallback.

---

## Fix 4 — `resources/dimensions.py` + `services/routes.py`

Add a new class:

`DimensionUsage`

**Endpoint**

```
GET /dimension/<id>/usage
```

**Purpose**
- Identify where a dimension is being used before deletion.

**Returns**
- Blocks whose **schema includes the dimension**
- Indicators whose **actuals reference the dimension**

**Goal**
- Allow the **frontend to warn users before deleting a dimension** that is still in use.
