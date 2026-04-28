# Rust Omni-Calc Performance Improvement Issues

Copy this into Jira / split as separate tickets.

---

## Issue 1: Avoid Rebuilding Same Property Maps During Rust Execution

### Summary
Optimize Rust omni-calc execution by reusing property maps for the same `(dimension_id, property_id, scenario_id)` instead of rebuilding them repeatedly for every property node.

### Background
In the current preload-based Rust path, metadata is copied into `PreloadedMetadata` before execution. The snapshot stores:

- `dimension_items: HashMap<i64, Vec<DimensionItem>>`
- `property_maps: HashMap<(i64, i64, i64), HashMap<i64, String>>`

However, during execution, loaders such as `load_string_property_map_from_snapshot` and `load_property_map_from_snapshot` still iterate over dimension items and rebuild a new property map for each property node.

This means the same `(dimension_id, property_id, scenario_id)` can be processed multiple times if multiple nodes require the same property.

### Problem
Even though Python callback overhead is removed, Rust may still do more total work than the old path because it rebuilds the same maps repeatedly.

This causes:
- Repeated iteration over dimension items
- Repeated `HashMap` lookups
- Repeated string cloning
- Repeated numeric parsing
- Extra allocations per node

### Proposed Solution
Add or complete executor-level caching for property maps.

Cache keys:

```rust
(dimension_id, property_id, scenario_id)
```

Cache values:

```rust
HashMap<(i64, i64, i64), StringPropertyMap>
HashMap<(i64, i64, i64), (PropertyMap, Vec<String>)>
```

Implementation options:
- Use `ExecutionContext.string_property_map_cache`
- Use `ExecutionContext.numeric_property_map_cache`
- Before calling snapshot loader, check cache
- If missing, build once from `PreloadedMetadata`
- Reuse for all future nodes in the same execution

### Expected Performance Impact
High.

This should reduce redundant work significantly for models where multiple indicators use the same dimension property.

### Acceptance Criteria
- Same property map is built only once per execution per `(dimension_id, property_id, scenario_id)`
- Existing calculation outputs remain unchanged compared to development
- Add debug/profiling evidence showing reduced repeated property map builds
- Add unit or integration test to verify cache hit behavior
- No Python callback is introduced back into the Rust execution path

### Notes
This should be prioritized before larger architectural caching because it is a local Rust-side optimization with lower invalidation risk.

---

## Issue 2: Demote Hot-Path `warn!` Logs in Rust Executor and Preload Flow

### Summary
Reduce logging overhead in the Rust omni-calc hot path by demoting per-step, per-node, and preload debug logs from `warn!` to `debug!` or `trace!`.

### Background
The branch contains many `warn!` logs inside execution paths such as:
- Calc step processing
- Individual node processing
- Connected dimension preload
- Cross-object dependency debug
- Dimension property debug
- `RecordBatch` duplicate checks

Some logs also collect samples, vectors, column names, or calculated summaries before logging.

### Problem
`warn!` is too high for normal execution diagnostics and may run in production or staging log configurations.

This can add overhead due to:
- Formatting work
- Vector collection
- Sample value construction
- Repeated logging per step/node/block
- Large log volume during big model calculations

### Proposed Solution
Audit Rust omni-calc logging and apply this rule:
- Keep `warn!` only for real anomalies or correctness risks
- Move normal execution diagnostics to `debug!`
- Move per-node, per-row, per-dimension, and sample-heavy diagnostics to `trace!`
- Guard expensive log argument construction with `tracing::enabled!` where needed

Example:

```rust
if tracing::enabled!(tracing::Level::TRACE) {
    trace!(sample_values = ?values.iter().take(10).collect::<Vec<_>>());
}
```

### Expected Performance Impact
Medium.

This will not fix the main calculation bottleneck alone, but it can reduce overhead and noise, especially for large models.

### Acceptance Criteria
- No normal per-node/per-step execution log remains at `warn!`
- Production warning logs only represent actionable issues
- Expensive log sample construction is guarded
- Calculation output remains unchanged
- Benchmark or timing comparison is captured before and after

---

## Issue 3: Optimize `preload_connected_dimensions` to Avoid Redundant Iteration and Allocation

### Summary
Improve the connected-dimension preload flow by reducing redundant scans, repeated string formatting, and unnecessary allocation during Rust execution startup.

### Background
`preload_connected_dimensions` runs before calculation steps. It loops through blocks, dimensions, dimension items, linked dimension IDs, and existing state columns to build connected dimension columns used for cross-block and property-based filtering.

### Problem
For large models, this startup step can become expensive because it performs repeated work such as:
- Scanning existing columns multiple times
- Repeatedly formatting column names like `_{dim_id}`
- Collecting linked dimension IDs
- Building item-to-value maps
- Allocating connected value vectors
- Logging heavily per block/dimension

### Proposed Solution
Refactor the function to reduce repeated work:
- Precompute existing direct and connected column names as `HashSet<String>`
- Skip dimensions early when `property_values` are empty
- Avoid building `item_to_value` unless a linked dimension column actually needs to be added
- Avoid repeated `format!` calls where possible
- Demote detailed preload logs to `trace!`
- Add timing instrumentation around connected-dimension preload

### Expected Performance Impact
Medium.

This should improve execution startup time for larger blocks with many dimensions and property-linked dimensions.

### Acceptance Criteria
- Function avoids duplicate column scans using a set-based lookup
- Empty-property dimensions are skipped early
- No behavior changes for connected dimension filters
- Existing test cases continue passing
- Add at least one benchmark/log timing before and after the change

---

## Issue 4: Spike Calculation Result Caching with Fingerprint-Based Invalidation

### Summary
Investigate and design calculation result caching for omni-calc so unchanged models, scenarios, blocks, or indicators do not recompute unnecessarily.

### Background
The meeting discussion identified three possible cache areas:
- Metadata cache
- DAG/cache of computed calculation plan
- Final calculated results cache

The main performance issue appears to be calculation-side recomputation, not only metadata loading. The team also discussed indicator-level versus block-level caching and agreed this needs further analysis before implementation.

### Problem
Currently, the calculation engine may be called even when there are no meaningful changes to model/scenario/block inputs. This can waste time by recalculating the same outputs.

However, caching calculated results is complex because invalidation must handle:
- Model changes
- Scenario changes
- Block changes
- Indicator formula changes
- Dimension/property changes
- Cross-block dependencies
- Multi-user updates

### Proposed Solution
Create a spike to compare caching strategies.

Evaluate:

#### Option A: Block-Level Result Cache
Cache full block output for a given block/scenario/fingerprint.

Pros:
- Simpler cache key
- Useful when requests usually fetch many indicators from a block
- Lower dependency tracking complexity

Cons:
- Less granular
- Invalidates more work when one indicator changes

#### Option B: Indicator-Level Result Cache
Cache individual indicator outputs.

Pros:
- Finer-grained reuse
- Avoids recalculating unchanged indicators

Cons:
- More complex invalidation
- Dependency graph tracking required
- Harder with cross-block formulas

#### Option C: Hybrid Cache
Use block-level cache for normal request output and indicator-level cache only for expensive/high-reuse nodes.

### Fingerprint Inputs to Evaluate
- Model last modified timestamp
- Scenario last modified timestamp
- Block last modified timestamp
- Indicator formula/version
- Dimension item/version
- Property values/version
- Input data version
- Dependent block/indicator fingerprints
- Time filter/request shape

### Expected Performance Impact
Potentially high, but requires design validation.

### Acceptance Criteria
- Document pros/cons of block-level, indicator-level, and hybrid caching
- Define proposed fingerprint/cache key structure
- Define invalidation strategy
- Identify where cache should live: memory, Redis, DB, Parquet, or hybrid
- Include memory impact analysis
- Include recommendation for first implementation phase
- No implementation required unless spike is approved

---

## Issue 5: Parallelize Independent Nodes Within Calc Planner Execution Steps

### Summary
Improve omni-calc execution throughput by parallelizing independent nodes within each calculation step where dependency ordering allows it.

### Background
The meeting notes aligned on prioritizing calc planner parallel processing. The current executor processes nodes sequentially inside each calculation step. However, many nodes in the same step may be independent and can potentially be calculated in parallel.

### Problem
Sequential processing underuses CPU capacity, especially for large models with many independent indicators.

Some nodes must remain sequential due to dependencies, but independent nodes in the same step can likely be grouped and executed concurrently.

### Proposed Solution
Investigate and implement parallel node execution for safe groups inside each calc step.

Implementation approach:
- Identify independent nodes in a calculation step
- Group nodes that do not mutate shared state conflicts
- Use Rayon or scoped threads for parallel evaluation
- Merge calculated columns and warnings back into shared state after the parallel section
- Keep sequential steps unchanged unless dependency rules are proven safe
- Add correctness comparison against the existing sequential execution path

### Important Safety Considerations
The current `ExecutionContext` mutates shared state during execution:
- `calc_object_states`
- `resolver`
- `warnings`
- Calculated column lists
- Connected dimensions

So implementation should avoid shared mutable writes inside parallel workers. Each worker should produce local results, then merge deterministically after the parallel section.

### Expected Performance Impact
High for models with many independent indicators.

### Acceptance Criteria
- Parallel execution only applies to dependency-safe nodes
- Sequential and parallel outputs match for the same request
- Warnings remain deterministic and complete
- No data races or nondeterministic column overwrites
- Benchmark shows improvement on a representative large model
- Add feature flag or config switch to disable parallel execution if needed

---

## Issue 6: Reduce Arrow `RecordBatch` Construction Clones and Allocation Overhead

### Summary
Optimize Arrow `RecordBatch` construction to reduce repeated cloning of dimension, connected dimension, string, and numeric column vectors.

### Background
The Rust executor builds Arrow `RecordBatch` objects from calculation state. Current construction creates arrays using cloned vectors such as:
- `StringArray::from(values.clone())`
- `Float64Array::from(values.clone())`

This can be expensive for large blocks because every output build clones full column vectors.

### Problem
Large models can have many columns and rows. Cloning all values during batch construction increases:
- Memory pressure
- Allocation cost
- CPU time
- GC/allocator pressure around large responses

### Proposed Solution
Investigate lower-copy Arrow construction options.

Possible approaches:
- Store state columns in Arrow-friendly array/buffer structures earlier
- Convert `Vec<String>` and `Vec<f64>` into Arrow arrays without unnecessary intermediate clones where safe
- Use `Arc<ArrayRef>` reuse for columns that do not change
- Avoid rebuilding unchanged `RecordBatch` objects repeatedly
- Profile memory allocations during `build_record_batch`

### Expected Performance Impact
Medium to high for large row-count blocks.

### Acceptance Criteria
- Profile current allocation cost during `build_record_batch`
- Reduce unnecessary vector cloning where possible
- Maintain identical output schema and values
- Add test for schema consistency and duplicate column behavior
- Benchmark memory/time before and after

---

## Issue 7: Move DAG Building / Calculation Plan Construction Closer to Rust

### Summary
Investigate moving DAG building and calculation plan construction logic from Python into Rust, or caching the computed DAG to reduce repeated planning overhead.

### Background
The meeting discussed moving DAG calculations into Rust and/or caching DAG output. Current execution depends on Python-prepared calculation steps and plan structure.

### Problem
If DAG/planner work is rebuilt repeatedly for similar requests, it adds overhead before Rust execution even starts.

This can especially hurt when:
- Model structure does not change
- Request shape is similar
- Only small input changes are made
- Same blocks/scenarios are recalculated often

### Proposed Solution
Create a spike to evaluate:
- Caching computed DAG/calc steps by model/scenario/block fingerprint
- Moving DAG construction into Rust for faster graph processing
- Keeping Python as source of truth but serializing a reusable plan snapshot
- Benchmarking plan build time separately from execution time

### Expected Performance Impact
Medium to high depending on planner cost.

### Acceptance Criteria
- Measure current DAG/planner construction time
- Identify exact Python functions involved in DAG creation
- Define cache key for DAG/calc-step reuse
- Compare Python DAG build vs potential Rust implementation
- Recommend whether to cache first or port to Rust first

---

## Issue 8: Add Rust Omni-Calc Benchmark and Correctness Harness Against `development`

### Summary
Create a repeatable benchmark and correctness comparison harness for Rust omni-calc performance changes.

### Background
The branch changes the execution path by preloading metadata and running Rust calculation without Python callbacks during execution. The branch docs state that `allow_threads` should not change results as long as the Rust closure uses only the cloned plan and preloaded Rust metadata.

### Problem
Performance work is hard to validate without a stable benchmark harness. Also, correctness must be verified after each optimization because changes affect property loading, caching, connected dimensions, and execution order.

### Proposed Solution
Create a benchmark script/test harness that runs the same representative requests on:
- `development`
- `BLOX-2104-improve-preload-snapshot-py-rust-pass`
- Future optimization branches

Compare:
- Response payload hash
- Key indicator totals
- Row count
- Column count
- Warning count
- Execution time
- Preload time
- Planning time
- `RecordBatch` build time

### Representative Models
Use models discussed in the meeting, such as:
- Web Trends
- Thrive
- Any large customer block with heavy dimensions/properties

### Expected Performance Impact
Indirect but high value.

This will prevent regressions and make future performance improvements measurable.

### Acceptance Criteria
- Same request can be executed against two branches/environments
- Output comparison reports pass/fail
- Timing breakdown is captured
- Results can be pasted into PR/Jira
- Harness supports at least one large model and one small model
- Document how to run the benchmark locally

---

## Issue 9: Investigate Memory-Bounded Cache Strategy for Low-Memory Systems

### Summary
Design a memory-safe cache strategy for omni-calc that improves performance without increasing memory usage beyond acceptable limits.

### Background
The meeting highlighted that the system should remain low-memory because customer blocks can be large. There was also discussion around short-lived memory cache and possible disk/Parquet-backed cache.

### Problem
Caching can improve speed but may increase memory usage significantly if entire blocks, property maps, or result sets are retained too aggressively.

Without memory limits, caching could cause performance degradation or instability under large customer workloads.

### Proposed Solution
Design a memory-bounded cache policy.

Evaluate:
- LRU cache for hot metadata/property maps
- Short TTL memory cache for recent calculation results
- Disk-backed cache for larger results
- Parquet-backed result storage for reusable block outputs
- Max memory budget per worker/process
- Cache eviction based on block size and access frequency

### Expected Performance Impact
Medium to high, with lower production risk.

### Acceptance Criteria
- Define what can be cached safely in memory
- Define max cache size and eviction rules
- Define what should be disk-backed instead of memory-backed
- Include invalidation strategy
- Include metrics needed: hit rate, memory usage, eviction count
- Provide recommendation for first safe implementation

---

## Suggested Implementation Priority

1. Issue 8: Benchmark and correctness harness
2. Issue 1: Property map reuse/cache in executor
3. Issue 2: Hot-path logging cleanup
4. Issue 3: Optimize connected dimension preload
5. Issue 6: Arrow allocation reduction
6. Issue 4: Calculation result caching spike
7. Issue 9: Memory-bounded cache strategy
8. Issue 5: Parallel node execution
9. Issue 7: DAG/planner Rust migration or caching
