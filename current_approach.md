# Why Rust Calculation Can Be Slower Without Callbacks (and How to Improve It)

## Why is rust_calculation slower on the preload branch?

Even though we removed Python callbacks, **we moved all the work into Rust**. So we're now doing in Rust what Python used to do, and the way we do it can be less efficient than the old path.

### 1. **Repeated work per property node**

- **Development (callbacks):** For each property node we call Python. Python's `get_dimension_items(dim_id)` and `_item_properties_cache` lookups may be cached or cheap (e.g. same dimension items returned from cache). We do one callback **per property node**.
- **Preload branch:** For each property node we call `load_*_from_snapshot(snapshot, property_spec, scenario_id)`. That function:
  - Gets the dimension's item list from the snapshot (O(1) HashMap get).
  - **Iterates over every item** and does a HashMap get for `(item_id, property_id, scenario_id)`.
  - Builds a **new** `StringPropertyMap` or `PropertyMap` every time.

So **the same (dimension_id, property_id, scenario_id) can be loaded many times** (once per property node that uses it). We rebuild the same property map over and over instead of building it once and reusing. That’s redundant work and extra allocations.

### 2. **No Python callback overhead, but more Rust work**

- **Development:** Each callback has GIL + FFI overhead, but the actual “build map” work happens in Python (often with optimized dicts and maybe internal caching).
- **Preload:** No GIL/FFI during execution, but we do **all** map building in Rust. If we do it once per node with no cache, we can do more total work than before.

### 3. **Logging in the hot path**

- The executor has **many `warn!`** calls (50+). Even when the log level filters them out, the arguments (e.g. format strings, collections) are often still evaluated.
- With `RUST_LOG=warn` or `info`, these run on every step/node and add cost.

### 4. **preload_connected_dimensions**

- Runs at the start and does a lot of iteration and logging over blocks/dimensions. For large models this can add up.

---

## Exact improvements (in order of impact)

### 1. **Cache property maps in the executor (biggest win)**

**Idea:** For a given `(dimension_id, property_id, scenario_id)` we need at most one string property map and one numeric property map. Build each map once and reuse for every property node that uses that (dim, prop, scenario).

**Where:**  
- **Option A:** In `ExecutionContext` add a cache, e.g.  
  `HashMap<(i64, i64, i64), StringPropertyMap>` and  
  `HashMap<(i64, i64, i64), (PropertyMap, Vec<String>)>`.
- When `process_properties` (or the snapshot loader) is called for a given `(dim_id, prop_id, scenario_id)`, check the cache first. If missing, call `load_*_from_snapshot` once and store the result; then reuse for all nodes that need that (dim, prop, scenario).

**Why it helps:** Removes repeated iteration over dimension items and repeated HashMap lookups for the same property. One build per unique (dim, prop, scenario) instead of one per property node.

### 2. **Pre-build property maps in the snapshot (alternative to 1)**

**Idea:** When building `PreloadedMetadata`, for each `(dimension_id, property_id, scenario_id)` in `property_requests`, build the `StringPropertyMap` or `PropertyMap` once and store it in the snapshot (e.g. `HashMap<(i64, i64, i64), StringPropertyMap>` and a similar one for numeric maps).

**Where:** `preload.rs` and the snapshot type. At execution time, `load_*_from_snapshot` becomes a single HashMap lookup instead of iterating items and building a map.

**Why it helps:** Same as 1 – each property map is built once (at preload time) and then only looked up during execution.

### 3. **Reduce logging in the hot path**

- Change **hot-path `warn!`** in the executor (e.g. per-step, per-node, PRELOAD, INPUT_DEBUG, CALC STEP DEBUG) to **`trace!`** or **`debug!`** so they are not enabled by default.
- Keep only a small number of `warn!` for real anomalies.
- This avoids format and allocation overhead when logs are disabled.

**Where:** `executor.rs` (and optionally `preload_connected_dimensions` and input_handler). Search for `warn!(` and demote the ones that fire per step or per node.

### 4. **Trim work in preload_connected_dimensions**

- Reduce **per-block/per-dimension `warn!`** to `trace!`/`debug!`.
- Avoid redundant iterations or allocations (e.g. reusing buffers, or building connected columns only when needed).
- Ensure we don’t do unnecessary work for dimensions that have no property_values.

### 5. **Keep the “only load needed properties” preload**

- We already changed preload to only load `property_requests` instead of the whole cache. That keeps the snapshot small and lookups fast. Ensure that’s in the build you measure.

### 6. **Profile to find remaining hotspots**

- Use `cargo build --release` and run with a representative block.
- Profile with e.g. `cargo flamegraph` or `perf` to see where time is spent (formula evaluation, resolver, property loading, etc.). Then optimize the top consumers.

---

## Summary

| Cause of slowdown | Fix |
|-------------------|-----|
| Same property map built many times (once per node) | Cache property maps by (dim_id, prop_id, scenario_id) in the executor, or pre-build them in the snapshot. |
| Too much logging in hot path | Demote per-step/per-node `warn!` to `trace!`/`debug!`. |
| Heavy preload_connected_dimensions | Reduce logging and redundant work. |
| Snapshot too large | Already improved by loading only `property_requests`. |

The main lever is **not rebuilding the same property map repeatedly**. Doing that (via cache or pre-built maps in the snapshot) should get Rust calculation time closer to or below the development branch, while keeping the benefit of no Python callbacks during execution.
