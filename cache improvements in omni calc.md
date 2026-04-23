# Omni-Calc Caching and Metadata Improvement Issues

This document captures proposed caching, preload, and metadata optimization issues for `modelAPI/omni-calc` and related backend metadata-loading paths.

---

## 1. [Spike] Define safe invalidation token for cross-request metadata caching using existing schema fields

### Current behavior
- `ModelMetadataCacheV4` is instantiated per request in `block_kpi_v4_rust.py` and `model_data_values_rust.py`.
- In the live DB schema, `last_modified_at` exists only on `Models`, `ModelScenarios`, and `Blocks`.
- `Dimensions`, `DimensionItems`, `DimensionProperties`, `DimItemProperties`, `DimItemScenarios`, and `DataInputs` do not have revision/version columns or `last_modified_at`.

### Problem
A cross-request cache cannot be made correctness-safe unless invalidation also detects changes in tables that currently have no direct revision or timestamp signal.

### Proposed approach
- Design a deterministic invalidation token using only real schema fields and tables.
- Combine model/scenario/block timestamps with deterministic fingerprints or counts derived from dimension/property/input tables.
- Explicitly avoid relying on non-existent fields such as `model_revision` or `scenario_revision`.

### Impact
Enables correctness-safe decisions for cross-request caching.

### Acceptance criteria
- A documented invalidation-token spec exists with exact SQL sources.
- A mutation test matrix proves the token changes when relevant metadata changes.
- Unsupported or unknown mutation paths are explicitly listed.

### Modules / files
- `model_metadata_cache_v4.py`
- `models.py`
- `model_scenario.py`
- `blocks.py`
- `dimensions.py`
- `dimItem_scenario.py`
- `data_inputs.py`

---

## 2. [Performance] Add optional process-level cross-request metadata snapshot cache keyed by model/scenario and invalidation token

### Current behavior
Each Rust request rebuilds `ModelMetadataCacheV4` from the DB using 10 parallel queries, even for repeated `(model_id, scenario_id)` requests.

### Problem
This causes repeated DB work and repeated JSON/metadata processing across requests for the same model and scenario.

### Proposed approach
- Add a bounded in-process LRU cache, with optional Redis support later.
- Key the cache by `(model_id, scenario_id, invalidation_token)`.
- Return immutable snapshot data for `ModelMetadataCacheV4`.

### Impact
Reduces DB load and lowers request latency for repeated calculations.

### Acceptance criteria
- Repeated requests with unchanged metadata hit the cache.
- Requests with changed metadata miss the cache.
- Parity tests confirm there are no stale results.

### Modules / files
- `model_metadata_cache_v4.py`
- `block_kpi_v4_rust.py`
- `model_data_values_rust.py`

---

## 3. [Performance] Build O(1) derived lookup caches inside `ModelMetadataCacheV4`

### Current behavior
Methods such as `get_block_indicators`, `find_dimension_property_by_id`, and `find_items_by_property_id_value` scan full dicts or lists on each call.

### Problem
Repeated linear scans add CPU overhead during DAG construction and Rust payload preparation.

### Proposed approach
Precompute derived lookup maps during `_process_results`, such as:
- `block_id -> indicators`
- `property_id -> property`
- Optional `(property_id, normalized_value) -> item list`

### Impact
Reduces CPU usage during request setup and improves scaling for large models.

### Acceptance criteria
- These lookups no longer iterate through full caches on each call.
- Output behavior remains identical to the current implementation.

### Modules / files
- `model_metadata_cache_v4.py`
- `dag_manager_v4.py`
- `rust_bridge.py`

---

## 4. [Performance] Cache parsed property metadata such as `linked_dimension_id` once in metadata cache

### Current behavior
`data_format` JSON is parsed repeatedly during DAG/filter extraction and Rust payload assembly.

### Problem
The same properties incur repeated JSON parsing and branching logic during hot setup paths.

### Proposed approach
- Normalize property metadata once inside `ModelMetadataCacheV4`.
- Include parsed `linked_dimension_id` and other frequently accessed derived fields.
- Have DAG and bridge code consume that normalized structure.

### Impact
Lowers request setup CPU and simplifies property-resolution paths.

### Acceptance criteria
- No repeated `json.loads` calls on property `data_format` in hot setup loops.
- Output parity is preserved.

### Modules / files
- `model_metadata_cache_v4.py`
- `dag_manager_v4.py`
- `rust_bridge.py`

---

## 5. [Performance] Add per-execution cache for row-aligned property columns in omni-calc

### Current behavior
Rust caches source property maps by `(dimension_id, property_id, scenario_id)` in `ExecutionContext`, but row-aligned vectors are still re-joined for each usage.

### Problem
This repeats join work for identical property references and identical target row shapes.

### Proposed approach
- Add an aligned-column cache keyed by property triple.
- Include target identity or row shape and filtering mode in the cache key.
- Reuse aligned outputs across compatible nodes within a single execution.

### Impact
Reduces repeated property-join work across nodes within a single execution.

### Acceptance criteria
- The same property reference used across multiple nodes is aligned only once per compatible key.
- Both numeric and string property paths safely reuse the cache.

### Modules / files
- `context.rs`
- `executor.rs`
- `input_handler/mod.rs`

---

## 6. [Performance] Cache cross-object join artifacts such as join paths and lookup maps per execution

### Current behavior
`CrossObjectResolver.resolve_reference` rebuilds source/target join paths and lookup maps for repeated references.

### Problem
The same source-target mapping patterns trigger duplicate work during execution.

### Proposed approach
- Add resolver-local caches keyed by mapping signature and source snapshot generation.
- Reuse join paths and lookup maps for repeated reference shapes.

### Impact
Speeds up cross-object resolution in block-heavy models.

### Acceptance criteria
- Repeated references with the same mapping reuse cached artifacts.
- The cache is invalidated whenever source block data changes.

### Modules / files
- `resolver.rs`
- `join_path.rs`
- `lookup.rs`

---

## 7. [Performance] Replace full resolver `RecordBatch` rebuilds with incremental cached representation

### Current behavior
`update_resolver` repeatedly rebuilds the full Arrow `RecordBatch` from block state, and `build_record_batch` clones all column vectors.

### Problem
As execution progresses and column counts grow, repeated full materialization becomes allocation-heavy and CPU-expensive.

### Proposed approach
- Maintain incremental resolver state.
- Materialize full Arrow batches only when necessary, or update only changed columns.
- Avoid cloning every column on each resolver refresh.

### Impact
Reduces allocation and CPU overhead during mid-execution resolver updates.

### Acceptance criteria
- Full-batch rebuild count drops significantly.
- Cross-block results remain identical to the current behavior.

### Modules / files
- `context.rs`
- `executor.rs`
- `resolver.rs`

---

## 8. [Performance] Cache connected-dimension alignments per block and execution

### Current behavior
Connected-dimension alignment is recomputed in multiple paths, including:
- `preload_connected_dimensions`
- Cross-object join preparation
- Sequential handling

### Problem
The same source/target combinations repeat string-vector alignment work unnecessarily.

### Proposed approach
- Cache aligned connected-dimension columns in execution context.
- Key the cache by `(source_dim, target_col, target_block, row_shape)`.
- Reuse alignment results across compatible paths.

### Impact
Reduces repeated connected-dimension preparation work.

### Acceptance criteria
- Duplicate alignments for the same key are avoided.
- Filtering and join behavior remain unchanged.

### Modules / files
- `executor.rs`
- `context.rs`
- `state.rs`

---

## 9. [Performance] Reduce preload fan-out string cloning when populating property maps

### Current behavior
In the Rust preload bulk path, property values are inserted using `value.clone()` for each target triple.

### Problem
This creates unnecessary allocations in fan-out cases.

### Proposed approach
- Move the string when there is only one target.
- Clone only when a single source value fans out to multiple target triples.
- Keep strings fully Rust-owned and avoid Python-borrowed lifetime complexity.

### Impact
Reduces allocations during the preload phase.

### Acceptance criteria
- Preload semantics remain unchanged.
- Profiling shows fewer string clone/allocation events in bulk property preload.

### Modules / files
- `preload.rs`
- `dim_loader.rs`

---

## 10. [Spike] Validate and potentially reduce all-scenarios property loading in `ModelMetadataCacheV4`

### Current behavior
Query 8 in `ModelMetadataCacheV4` intentionally loads `DimItemProperties` for all scenarios of the model (`WHERE d.model_id = $1`) to preserve Python v2 behavior for certain property filters.

### Problem
This can significantly increase memory use and request setup time in large models with many scenarios.

### Proposed approach
- Run parity tests for Rust endpoints to confirm whether all-scenario loading is strictly required.
- If it is not required, switch to scenario-scoped loading with explicit fallback rules.

### Impact
Can materially reduce cache size and preload cost.

### Acceptance criteria
- A parity report explicitly confirms whether all-scenario loading is required.
- If loading is narrowed to scenario scope, there is no behavior regression in filter or bridge cases.

### Modules / files
- `model_metadata_cache_v4.py`
- `dag_manager_v4.py`
- `block_kpi_v4_rust.py`
- `model_data_values_rust.py`
