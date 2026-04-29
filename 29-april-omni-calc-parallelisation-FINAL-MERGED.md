# Final Corrected Merged Omni-Calc Performance / Parallelisation Jira Roadmap

## Reference

Source planning file:

```text
https://github.com/veer-pratap-blox/tasks/blob/main/29-april-omni-calc-parallelisation-FINAL.md
```

Code branch:

```text
https://github.com/BloxSoftware/Blox-Dev/tree/BLOX-2104-improve-preload-snapshot-py-rust-pass
```

Primary Omni-Calc Rust areas:

```text
modelAPI/omni-calc/src/engine/exec/executor.rs
modelAPI/omni-calc/src/engine/exec/context.rs
modelAPI/omni-calc/src/engine/exec/state.rs
modelAPI/omni-calc/src/engine/exec/preload.rs
modelAPI/omni-calc/src/engine/exec/formula_eval.rs
modelAPI/omni-calc/src/engine/exec/get_source_data/resolver.rs
modelAPI/omni-calc/src/engine/exec/get_source_data/dim_loader.rs
modelAPI/omni-calc/src/engine/exec/node_alignment/join_path.rs
modelAPI/omni-calc/src/engine/exec/node_alignment/lookup.rs
modelAPI/omni-calc/src/engine/exec/steps/input_handler/mod.rs
modelAPI/omni-calc/src/engine/exec/steps/calculation.rs
modelAPI/omni-calc/src/engine/exec/steps/sequential.rs
modelAPI/omni-calc/src/engine/integration/calc_plan.rs
modelAPI/omni-calc/src/python.rs
modelAPI/omni-calc/Cargo.toml
```

---

# Important Correction

Earlier mapping incorrectly described Source Issue 10 as:

```text
Cached parsed formula AST and dependency metadata
```

Correct Source Issue 10 is:

```text
Issue 10 — Expand and Normalize PreloadedMetadata for Worker-Safe Execution
```

So Source Issue 10 belongs with the scheduler / worker-safety foundation because complete normalized preload is required before worker-safe execution.

Corrected statement:

```text
Final Issue 3 merges:
- Source Issue 1 — Core scheduler foundation
- Source Issue 10 — Expand and Normalize PreloadedMetadata for Worker-Safe Execution
```

---

# Global Rule For All Issues

After preload, Omni-Calc Rust execution must use Rust-owned data.

Allowed PyO3 usage:

```text
Python binding boundary
CalcPlan extraction
explicit preload before Rust execution
returning result back to Python
```

Not allowed inside Rust execution hot path:

```text
Python<'_>
PyObject
metadata_cache.call_method1(...)
metadata_cache.getattr(...)
lazy metadata callback from node execution
lazy metadata callback from formula evaluation
lazy metadata callback from resolver / join logic
lazy metadata callback from Rayon workers
```

Correct execution direction:

```text
Python boundary
    ↓
Preload all required metadata into Rust-owned PreloadedMetadata
    ↓
Run Rust execution under py.allow_threads
    ↓
Use ExecutionSnapshot / PreloadedMetadata / PropertyCacheSnapshot
    ↓
No Python callback inside executor hot path
```

---

# Final Corrected Source Issue Mapping

```text
Source Issue 1  -> Final Issue 3
Source Issue 2  -> Final Issue 10
Source Issue 3  -> Final Issue 6
Source Issue 4  -> Final Issue 6
Source Issue 5  -> Final Issue 5
Source Issue 6  -> Final Issue 5
Source Issue 7  -> Final Issue 2
Source Issue 8  -> Final Issue 2
Source Issue 9  -> Final Issue 5
Source Issue 10 -> Final Issue 3
Source Issue 11 -> Final Issue 4
Source Issue 12 -> Final Issue 4
Source Issue 13 -> Final Issue 1
Source Issue 14 -> Final Issue 1
Source Issue 15 -> Final Issue 7
Source Issue 16 -> Final Issue 8
Source Issue 17 -> Final Issue 9
Source Issue 18 -> Final Issue 1
Source Issue 19 -> Final Issue 2
Source Issue 20 -> Final Issue 4
Source Issue 21 -> Final Issue 2
```

---

# Final Correct Implementation Order

```text
1. Final Issue 1 — Benchmarking, Performance Baseline, and Debug Hot-Path Cleanup

2. Final Issue 2 — Data Structure, Clone Reduction, Shared References, FormulaEvaluator Context, and Typed IDs Foundation

3. Final Issue 3 — Core Kahn-Style Scheduler Foundation + Complete PreloadedMetadata Worker-Safe Execution

4. Final Issue 4 — Actuals, Forecast, and Dimension Row Metadata Optimization

5. Final Issue 5 — Cross-Object Join, Lookup, Aggregation, and Join-Key Optimization

6. Final Issue 6 — Pre/Post Processing Parallelism

7. Final Issue 7 — Standalone Source Issue 15

8. Final Issue 8 — Standalone Source Issue 16

9. Final Issue 9 — Standalone Source Issue 17

10. Final Issue 10 — Configurable Rayon-Based Parallel Ready-Node Execution
```

---

# Why This Order Is Correct

```text
Benchmark first
    ↓
Know current runtime and memory baseline

Data structure / clone cleanup second
    ↓
Avoid making Rayon execution memory-bound

Scheduler + complete preload foundation third
    ↓
Build safe execution architecture and remove Python callback risk

Actuals / dimension row metadata fourth
    ↓
Reduce repeated row-key and forecast handling costs

Cross-object join optimization fifth
    ↓
Optimize resolver/join paths before parallel workers hit them heavily

Pre/post parallelism sixth
    ↓
Implement safer independent parallel wins

Standalone issues next
    ↓
Resolve remaining specific source issues before final parallel execution

Rayon ready-node execution last
    ↓
Only after correctness, preloaded-only execution, resolver safety, and serial Kahn parity are proven
```

---

# FINAL ISSUE 1

## Issue Type

Performance / Observability / Tech Debt

---

## Title

Add Omni-Calc Performance Benchmark Baseline and Remove Debug Hot-Path Overhead

---

## Source Issues Merged

```text
Source Issue 13
Source Issue 14
Source Issue 18
```

---

## Summary

Create a reliable benchmark, profiling, and observability foundation before implementing major scheduler, data-structure, clone-reduction, preload, resolver, join, or Rayon parallelism changes.

This issue should establish a clear before/after baseline for the current serial executor and remove debug/logging paths that allocate, clone, or distort runtime performance.

This issue should be solved first because every later optimization needs measurable proof.

---

## Background / Context

Current Omni-Calc execution has several performance-sensitive phases:

```text
metadata preload
connected dimension preload
input step processing
property loading
calculation step processing
sequential step processing
formula evaluation
cross-object resolver updates
join path creation
lookup aggregation
actuals / forecast handling
RecordBatch materialization
final result build
```

Before optimizing these areas, we need reliable benchmarks.

Without this baseline, later refactors may:

```text
look faster in theory but not in practice
improve one model shape but regress another
increase memory pressure
hide clone overhead behind parallelism
make Rayon execution memory-bound
make debugging harder
```

---

## Problem Statement

Current risks:

```text
1. No consistent benchmark baseline for Omni-Calc execution.
2. No clear phase-level runtime breakdown.
3. No benchmark for formula evaluation alone.
4. No benchmark for resolver update/materialization.
5. No benchmark for cross-object join alignment.
6. No benchmark for lookup aggregation.
7. No benchmark for final RecordBatch creation.
8. No benchmark for clone-heavy evaluator setup.
9. Debug logs and diagnostics may allocate in hot paths.
10. Hardcoded debug paths can distort production performance.
11. Future refactors can accidentally regress performance without being caught.
```

---

## Scope

Add benchmark coverage for:

```text
1. Full Omni-Calc execution
2. Current serial calc_steps execution
3. Future single-threaded Kahn scheduler
4. Future Rayon ready-node execution
5. Formula evaluation
6. FormulaEvaluator setup
7. Input indicator processing
8. Property loading from PreloadedMetadata
9. Resolver update/materialization
10. Cross-object join path creation
11. Lookup map aggregation
12. Final RecordBatch materialization
13. Connected dimension preload
14. Actuals / forecast handling
15. Clone-heavy paths
16. Memory allocation / peak memory where practical
```

Clean up or gate:

```text
1. Hardcoded block-specific debug logs
2. Debug-only vector sampling in hot paths
3. Repeated column-name collection for logging
4. Sample key/value construction unless tracing is enabled
5. Clone-heavy diagnostics
6. Expensive log formatting when logs are disabled
```

---

## Proposed Change

Add a benchmark harness or internal performance mode.

Recommended metrics:

```text
total_runtime_ms
preload_runtime_ms
connected_dimension_preload_ms
input_step_ms
property_step_ms
calculation_step_ms
sequential_step_ms
formula_eval_ms
formula_setup_ms
resolver_update_ms
recordbatch_materialization_ms
join_path_creation_ms
lookup_aggregation_ms
actuals_handling_ms
clone_hotspot_ms
row_count
block_count
column_count
node_count
warning_count
```

Benchmark scenarios:

```text
small model
medium model
large wide model
large row-count model
cross-object-heavy model
actuals-heavy model
sequential-heavy model
property-heavy model
```

Suggested flags:

```text
CALC_DEBUG=false by default
CALC_PERF_TRACE=false by default
CALC_BENCH_MODE=true only in benchmark runs
```

---

## Expected Impact

```text
1. Makes future optimization measurable.
2. Prevents performance regressions.
3. Helps decide where Rayon is actually useful.
4. Helps identify clone-heavy and allocation-heavy paths.
5. Provides safe baseline before scheduler changes.
```

---

## Acceptance Criteria

```text
1. Benchmark harness exists.
2. At least small, medium, and large model benchmarks exist.
3. Benchmarks can compare serial vs optimized paths.
4. Phase-level timing is available.
5. Debug/hot-path logs do not allocate unless enabled.
6. Hardcoded block/node debug logs are removed or gated.
7. Baseline numbers are documented before other optimization work begins.
8. Performance regression checks can be added to CI or run manually.
9. Benchmark results can be used by later issues to prove improvement.
```

---

## Testing Notes

Add tests / benchmark cases for:

```text
full serial execution
large formula evaluation
wide block column lookup
large cross-object join
lookup aggregation
RecordBatch output
connected dimension preload
actuals-heavy block
sequential-heavy block
debug disabled path
debug enabled path
```

---

## Out of Scope

```text
Changing calculation semantics
Adding Rayon execution
Changing output format
Changing Python DAG manager behavior
Refactoring scheduler
Changing resolver logic
```

---

## Priority

Highest

---

## Dependencies

```text
None
```

---

## Labels

```text
omni-calc
rust
benchmark
performance
profiling
debug-cleanup
regression-gates
observability
```

---

## Components

```text
Omni-Calc
Rust Engine
Benchmarking
Performance
Debugging
```

---

# FINAL ISSUE 2

## Issue Type

Performance / Data Structure Refactor / Memory Optimization

---

## Title

Optimize Omni-Calc Data Structures, Clone Reduction, Shared References, FormulaEvaluator Context, and Typed IDs Foundation

---

## Source Issues Merged

```text
Source Issue 7
Source Issue 8
Source Issue 19
Source Issue 21
```

---

## Summary

Refactor Omni-Calc internal data structures so execution can reuse Rust-owned preloaded data, reduce cloning, improve column lookup, and prepare for efficient scheduler-based and Rayon-based execution.

This issue should improve:

```text
CalcObjectState column lookup
NodeOutput merge performance
FormulaEvaluator input setup
FormulaEvaluator child evaluator cloning
PreloadedMetadata reuse
shared column storage
typed internal IDs
string parsing overhead
memory pressure
```

---

## Background / Context

Current state and evaluator paths are string-heavy and clone-heavy.

Common structures:

```rust
Vec<(String, Vec<f64>)>
Vec<(String, Vec<String>)>
HashMap<String, Vec<f64>>
HashMap<String, Vec<String>>
```

Current `CalcObjectState` concept:

```rust
pub struct CalcObjectState {
    pub object_key: String,
    pub object_type: CalcObjectType,

    pub dim_columns: Vec<(String, Vec<String>)>,
    pub row_count: usize,

    pub number_columns: Vec<(String, Vec<f64>)>,
    pub string_columns: Vec<(String, Vec<String>)>,
    pub connected_dim_columns: Vec<(String, Vec<String>)>,

    pub node_ids: HashSet<i64>,
}
```

Current lookup style:

```rust
self.number_columns
    .iter()
    .find(|(name, _)| name == column_name)
```

This is linear.

For wide models, this becomes expensive.

---

## Problem Statement

Current problems:

```text
1. Column lookup is often O(number_of_columns).
2. Duplicate checks scan Vec entries.
3. FormulaEvaluator owns and clones large column vectors.
4. Child evaluators can clone full EvalContext.
5. build_record_batch clones column vectors into Arrow arrays.
6. Resolver updates may repeatedly rebuild cloned RecordBatches.
7. PreloadedMetadata maps may be copied instead of reused.
8. Internal identifiers are string encoded.
9. Repeated string parsing / formatting costs CPU and memory.
10. Future Rayon execution can become memory-bandwidth bound if cloning remains high.
```

---

## Scope

### 1. Introduce ColumnStore

Add indexed column storage that preserves deterministic order.

Possible first version:

```rust
struct ColumnStore<T> {
    columns: Vec<(String, Arc<[T]>)>,
    index: HashMap<String, usize>,
}
```

Possible later version with typed IDs:

```rust
struct ColumnStore<T> {
    columns: Vec<(ColumnId, Arc<[T]>)>,
    index: HashMap<ColumnId, usize>,
}
```

Required methods:

```rust
insert(...)
get(...)
contains(...)
iter(...)
len(...)
is_empty(...)
```

---

### 2. Use Shared Column References

Introduce shared immutable column aliases:

```rust
type SharedNumberColumn = Arc<[f64]>;
type SharedStringColumn = Arc<[String]>;
```

or easier first step:

```rust
type SharedNumberColumn = Arc<Vec<f64>>;
type SharedStringColumn = Arc<Vec<String>>;
```

Preferred long-term:

```text
Arc<[T]>
```

because it clearly represents immutable shared slice data.

---

### 3. Refactor FormulaEvaluator Context

Current evaluator-like shape:

```rust
HashMap<String, Vec<f64>>
HashMap<String, Vec<String>>
Vec<String>
```

Target:

```rust
HashMap<String, Arc<[f64]>>
HashMap<String, Arc<[String]>>
Arc<[String]>
```

Avoid full context clone in child evaluator creation.

Target shape:

```rust
struct FormulaEvaluator {
    ctx: Arc<EvalContext>,
    warnings: Vec<EvalWarning>,
    actuals_context: Option<Arc<ActualsContext>>,
    property_filter_context: PropertyFilterContext,
    prior_called: bool,
    last_result_is_integer: bool,
}
```

---

### 4. Reuse PreloadedMetadata

Store/pass preloaded metadata as shared read-only data:

```rust
Arc<PreloadedMetadata>
```

Avoid cloning maps like:

```rust
HashMap<i64, Vec<DimensionItem>>
HashMap<(i64, i64, i64), HashMap<i64, String>>
```

during execution.

---

### 5. Add Typed IDs

Introduce typed internal IDs:

```rust
struct BlockId(i64);
struct IndicatorId(i64);
struct DimensionId(i64);
struct PropertyId(i64);
struct NodeId(i64);
```

Introduce column identity:

```rust
enum ColumnId {
    Indicator(IndicatorId),
    Dimension(DimensionId),
    Property {
        dimension_id: DimensionId,
        property_id: PropertyId,
    },
    CrossObjectIndicator {
        block_id: BlockId,
        indicator_id: IndicatorId,
    },
    ConnectedDimension {
        source_dimension_id: DimensionId,
        linked_dimension_id: DimensionId,
    },
}
```

Keep external output names unchanged.

---

## Proposed Implementation Plan

```text
Phase 1 - Add ColumnStore<T> with stable order and indexed lookup.
Phase 2 - Convert dynamic number/string/connected columns to ColumnStore.
Phase 3 - Add shared column aliases and avoid vector cloning in snapshots/evaluators where safe.
Phase 4 - Refactor FormulaEvaluator to share immutable EvalContext.
Phase 5 - Use Arc<PreloadedMetadata> / immutable property cache snapshots.
Phase 6 - Introduce typed ID helpers and conversion functions.
Phase 7 - Gradually migrate graph/scheduler/resolver to typed IDs where beneficial.
```

---

## Expected Impact

```text
1. Faster column lookup.
2. Faster duplicate checks.
3. Less memory allocation.
4. Lower peak memory usage.
5. Faster FormulaEvaluator setup.
6. Cheaper child evaluator creation.
7. Better use of Rust-owned preloaded data.
8. Better foundation for safe Rayon execution.
```

---

## Acceptance Criteria

```text
1. Dynamic column lookup is indexed, not linear.
2. Column insertion order remains deterministic.
3. Duplicate checks are O(1) average time.
4. FormulaEvaluator can read input columns without cloning full vectors.
5. with_raw_properties() does not clone full EvalContext.
6. PreloadedMetadata is reused by reference/Arc.
7. Property caches can be read-only where possible.
8. Typed ID helpers exist for block, indicator, dimension, property, node, and column identity.
9. External output names remain unchanged.
10. No Python/PyO3 callbacks are added.
11. Serial executor output remains identical.
12. Benchmarks show reduced allocations or runtime on large/wide models.
```

---

## Testing Notes

Add tests for:

```text
ColumnStore insert/get
ColumnStore duplicate insert
ColumnStore stable order
CalcObjectState column lookup parity
RecordBatch schema order
FormulaEvaluator shared context behavior
with_raw_properties shared context behavior
PreloadedMetadata reference reuse
typed ID parse / to_external_name roundtrip
serial output parity
large column lookup benchmark
clone/allocation benchmark
```

---

## Out of Scope

```text
Changing output schema
Changing calculation semantics
Changing Python DAG manager behavior
Full Rayon execution
Full formula engine rewrite
Removing human-readable debug names
Changing formula syntax
```

---

## Priority

Highest / High

---

## Dependencies

```text
Depends on Final Issue 1 for benchmark baseline.
Should be completed before Final Issue 3 and Final Issue 10.
```

---

## Labels

```text
omni-calc
rust
performance
data-structure
column-store
clone-reduction
shared-columns
arc
formula-evaluator
typed-ids
preloaded-data
memory-optimization
```

---

## Components

```text
Omni-Calc
Rust Engine
Execution State
Formula Evaluation
Preload
Column Store
Typed IDs
```

---

# FINAL ISSUE 3

## Issue Type

Technical Task / Refactor

---

## Title

Refactor Rust Omni-Calc Executor Toward Safe Kahn-Style DAG Scheduling Foundation and Worker-Safe PreloadedMetadata

---

## Source Issues Merged

```text
Source Issue 1  - Core scheduler foundation
Source Issue 10 - Expand and Normalize PreloadedMetadata for Worker-Safe Execution
```

---

## Important Correction

Source Issue 10 is:

```text
Expand and Normalize PreloadedMetadata for Worker-Safe Execution
```

It is not:

```text
Cached parsed formula AST and dependency metadata
```

This issue must therefore cover complete preload normalization and worker-safe metadata access.

---

## Summary

Build the safe architecture required before true parallel execution.

The current Rust executor processes Python-provided `calc_steps` sequentially and mutates a shared `ExecutionContext`.

Target flow:

```text
Current serial executor
    ↓
Complete normalized PreloadedMetadata
    ↓
ExecutionSnapshot
    ↓
NodeOutput
    ↓
Central merge phase
    ↓
Explicit ExecutionGraph
    ↓
Single-threaded Kahn scheduler
    ↓
Serial parity proven
    ↓
Ready for Rayon in later issue
```

---

## Background / Context

Current simplified executor flow:

```rust
pub fn execute(_engine: &mut Engine, plan: Plan) -> Result<CalcResult> {
    let start = Instant::now();

    let mut ctx = ExecutionContext::new(&plan, _engine.preloaded_metadata());

    preload_connected_dimensions(&mut ctx);

    for step in &plan.request.calc_steps {
        match step.calc_type.as_str() {
            "input" => process_input_step(&mut ctx, step),
            "calculation" => process_calculation_step(&mut ctx, step),
            "sequential" => process_sequential_step(&mut ctx, step),
            _ => {}
        }
    }

    build_execution_result(&ctx, start)
}
```

Current model:

```text
Python provides ordered calc_steps
Rust executes each step sequentially
Each step mutates ExecutionContext
Resolver is updated during node processing
```

Rust does not currently own an explicit ready queue / Kahn scheduler.

---

## Problem Statement

Current executor limitations:

```text
1. Rust trusts Python calc_steps ordering.
2. Rust does not track indegree/outgoing dependencies.
3. Rust does not know which nodes are independently ready.
4. Node execution mutates ExecutionContext directly.
5. Resolver is updated during node processing.
6. PreloadedMetadata may not yet be normalized for all worker execution needs.
7. Property maps and dimension items must be complete before execution.
8. Worker-safe execution cannot call Python/PyO3.
9. Sequential groups must remain atomic.
```

---

## Scope

### 1. Complete and Normalize PreloadedMetadata

Current preload direction:

```rust
pub struct PreloadedMetadata {
    pub dimension_items: HashMap<i64, Vec<DimensionItem>>,
    pub property_maps: HashMap<(i64, i64, i64), HashMap<i64, String>>,
}
```

This issue should expand/normalize preload so worker execution has everything required without Python callbacks.

Required preload coverage:

```text
dimension items
dimension item IDs
property maps
numeric property values
string property values
linked dimension properties
property maps by scenario
metadata needed for property nodes
metadata needed for cross-object joins
metadata needed for connected dimensions
metadata needed for filters
metadata needed by formula evaluation
```

Preloaded data should be stored in Rust-owned immutable structures:

```rust
Arc<PreloadedMetadata>
```

or equivalent.

Missing required preload data should fail early before execution:

```text
Do not lazy-load missing metadata from Python during execution.
```

---

### 2. Add ExecutionSnapshot

```rust
struct ExecutionSnapshot {
    block_key: String,
    block_spec: Arc<BlockSpec>,
    dim_columns: Arc<...>,
    number_columns: Arc<...>,
    string_columns: Arc<...>,
    connected_dim_columns: Arc<...>,
    resolver_snapshot: Arc<CrossObjectResolverSnapshot>,
    preloaded_metadata: Arc<PreloadedMetadata>,
    property_cache_snapshot: Arc<PropertyCacheSnapshot>,
}
```

---

### 3. Add NodeOutput

```rust
struct NodeOutput {
    block_key: String,
    number_columns: Vec<...>,
    string_columns: Vec<...>,
    connected_dim_columns: Vec<...>,
    warnings: Vec<CalcWarning>,
    nodes_calculated: usize,
    should_update_resolver: bool,
}
```

---

### 4. Add Central Merge Phase

```rust
fn merge_node_output(ctx: &mut ExecutionContext, output: NodeOutput) {
    // only place where shared state is updated
}
```

---

### 5. Add ExecutionGraph

```rust
struct ExecutionGraph {
    nodes: HashMap<NodeId, ExecNode>,
    outgoing: HashMap<NodeId, Vec<NodeId>>,
    indegree: HashMap<NodeId, usize>,
}
```

Node type:

```rust
enum ExecNodeType {
    InputIndicator,
    Property,
    Calculation,
    SequentialGroup,
}
```

---

### 6. Add Single-Threaded Kahn Scheduler

First implementation must remain single-threaded.

Pseudo-flow:

```text
build graph
find zero-indegree nodes
execute one ready node
return NodeOutput
merge output
update resolver if needed
decrement dependents
enqueue newly ready nodes
```

---

## Resolver Requirements

Resolver updates must be coordinator-owned.

Do not update resolver from worker/node execution.

Target:

```text
execute node
return NodeOutput
merge output
update resolver at safe dependency boundary
release dependents
```

Add read-only resolver snapshot concept:

```rust
struct CrossObjectResolverSnapshot {
    calculated_blocks: Arc<HashMap<BlockId, BlockData>>,
    node_maps: Arc<HashMap<NodeMapKey, PlannedNodeMap>>,
    variable_filters: Arc<HashMap<String, VariableFilter>>,
}
```

---

## Sequential Group Requirements

Sequential steps must remain atomic.

Represent as:

```rust
ExecNodeType::SequentialGroup
```

with:

```rust
parallel_safe = false
```

Do not split sequential group nodes into independent parallel nodes.

---

## Python / Preload Requirement

Worker-ready execution path must use:

```text
PreloadedMetadata
PropertyCacheSnapshot
ExecutionSnapshot
Rust-owned plan data
```

It must not call:

```text
Python<'_>
PyObject
metadata_cache.call_method1(...)
metadata_cache.getattr(...)
```

---

## Expected Impact

```text
1. Creates safe foundation for future parallelism.
2. Removes Python callback risk from worker execution.
3. Makes preload completeness explicit and testable.
4. Enables deterministic merge and resolver update boundaries.
5. Enables single-threaded Kahn scheduler parity testing.
6. Prevents global lock based false parallelism.
```

---

## Acceptance Criteria

```text
1. PreloadedMetadata is expanded/normalized for worker-safe execution.
2. All metadata required by worker-ready execution is available before execution starts.
3. Missing required metadata fails early with clear diagnostics.
4. ExecutionSnapshot exists.
5. NodeOutput exists.
6. Shared state mutation is centralized in merge.
7. ExecutionGraph exists.
8. Graph tracks dependencies, outgoing edges, and indegrees.
9. Single-threaded Kahn scheduler exists behind config/feature flag.
10. Single-threaded Kahn output matches current serial calc_steps output.
11. Resolver updates happen at safe boundaries.
12. Sequential groups are atomic.
13. No global Arc<Mutex<ExecutionContext>> production design.
14. No PyO3/Python callbacks in execution hot path.
```

---

## Testing Notes

Add tests for:

```text
PreloadedMetadata completeness
missing dimension items
missing property map
missing linked dimension property
missing filter metadata
preloaded-only mode rejects missing metadata
ExecutionSnapshot build
NodeOutput merge
duplicate column merge
input -> calculation dependency
intra-block formula dependency
cross-block dependency
property dependency
sequential group atomic node
cycle detection
topological order parity
single-threaded Kahn vs current serial output
resolver update boundary
```

---

## Out of Scope

```text
Rayon execution
Full parallel scheduler
Work stealing
Parallel sequential groups
Changing output format
Changing calculation semantics
Changing Python DAG manager behavior
Lazy Python metadata fallback
```

---

## Priority

Highest

---

## Dependencies

```text
Depends on Final Issue 1.
Strongly benefits from Final Issue 2.
Required before Final Issue 10.
```

---

## Labels

```text
omni-calc
rust
executor
kahn-scheduler
dag
dependency-graph
execution-snapshot
node-output
resolver
preload
preloaded-metadata
python-ffi
worker-safe
parallelism-foundation
```

---

## Components

```text
Omni-Calc
Rust Engine
Executor
Scheduler
Preload
Cross-Object Resolver
Python Boundary
```

---

# FINAL ISSUE 4

## Issue Type

Performance / Algorithm Optimization / Refactor

---

## Title

Optimize Actuals, Forecast, Dimension Row Metadata, and Entity Key Reuse

---

## Source Issues Merged

```text
Source Issue 11
Source Issue 12
Source Issue 20
```

---

## Summary

Optimize repeated row metadata work in Omni-Calc.

This includes:

```text
actuals handling
forecast index/mask handling
row dimension key construction
entity key construction
dimension-combination reuse
avoiding repeated string-heavy row metadata
```

This is important for actuals-heavy, sequential-heavy, and large row-count models.

---

## Problem Statement

Actuals-heavy and sequential-heavy models repeatedly build row keys and entity keys.

Current expensive patterns:

```text
1. Build dimension keys per row per indicator.
2. Build entity keys per row per actuals/sequential path.
3. Sort/join key parts repeatedly.
4. Use Vec::contains for forecast index membership.
5. Clone actual_values and forecast_indices into ActualsContext.
6. Store repeated dimension item names as strings.
7. Rebuild row metadata that could be shared per block.
```

---

## Proposed Change

Add per-block row metadata cache:

```rust
struct BlockRowMetadata {
    row_dimension_keys: Arc<[String]>,
    row_entity_keys: Arc<[String]>,
    forecast_mask: Arc<[bool]>,
    forecast_indices: Arc<[usize]>,
}
```

Longer-term compact version:

```rust
struct BlockRowMetadata {
    row_dimension_key_ids: Arc<[u64]>,
    row_entity_key_ids: Arc<[u64]>,
    forecast_mask: Arc<[bool]>,
    forecast_indices: Arc<[usize]>,
}
```

Update actuals context:

```rust
struct ActualsContext {
    actual_values: Arc<[f64]>,
    forecast_indices: Arc<[usize]>,
    forecast_mask: Arc<[bool]>,
    last_actual_by_entity: Arc<HashMap<String, f64>>,
    has_actuals: bool,
}
```

---

## Proposed Implementation Plan

```text
Phase 1 - Precompute forecast mask per block.
Phase 2 - Precompute row dimension keys once per block.
Phase 3 - Precompute row entity keys once per block, excluding time dimension.
Phase 4 - Update actuals loading to use cached row keys.
Phase 5 - Update sequential/last-actual logic to reuse entity keys.
Phase 6 - Avoid unnecessary cloning in ActualsContext.
Phase 7 - Optionally move from string keys to compact IDs after typed IDs / join-key optimizations are ready.
```

---

## Expected Impact

```text
1. Faster actuals loading.
2. Faster sequential function setup.
3. Faster last-actual-by-entity extraction.
4. Less repeated string allocation.
5. Less repeated sorting/joining of key parts.
6. Faster forecast membership checks.
7. Reduced memory churn.
```

---

## Acceptance Criteria

```text
1. Forecast membership is O(1) using mask/bitset/HashSet.
2. Row dimension keys are computed once per block.
3. Row entity keys are computed once per block.
4. Actuals loading reuses cached row keys.
5. Last-actual-by-entity extraction reuses cached entity keys.
6. ActualsContext avoids unnecessary vector clones.
7. Dimension combination metadata is reused across evaluator/resolver/snapshots where possible.
8. Existing actuals behavior remains unchanged.
9. Existing sequential formula behavior remains unchanged.
10. No Python callbacks are introduced.
```

---

## Testing Notes

Add tests for:

```text
forecast mask correctness
forecast indices correctness
dimension key parity
entity key parity
actuals matching parity
last actual by entity parity
monthly forecast start
yearly forecast start
missing time dimension
multi-dimension block
sequential formula parity
serial output parity
large actuals benchmark
```

---

## Out of Scope

```text
Changing actuals semantics
Changing forecast-start behavior
Changing Python parity behavior
Changing output format
Parallel execution itself
```

---

## Priority

High / Medium

---

## Dependencies

```text
Depends on Final Issue 1.
Benefits from Final Issue 2.
Should be completed before Final Issue 10 for actuals/sequential-heavy models.
```

---

## Labels

```text
omni-calc
rust
actuals
forecast
dimension-metadata
row-key-cache
entity-key-cache
performance
clone-reduction
```

---

## Components

```text
Omni-Calc
Rust Engine
Calculation Handler
Sequential Handler
Actuals Handling
Formula Evaluation
```

---

# FINAL ISSUE 5

## Issue Type

Performance / Algorithm Optimization

---

## Title

Optimize Cross-Object Join Path Creation, Lookup Aggregation, and Join-Key Representation

---

## Source Issues Merged

```text
Source Issue 5
Source Issue 6
Source Issue 9
```

---

## Summary

Optimize cross-object resolver and node alignment performance.

Current cross-object alignment uses string-heavy join paths and sequential lookup/aggregation logic.

This issue should improve:

```text
join-path creation
target alignment
lookup map creation
aggregation
join key representation
optional parallel execution for large row counts
```

---

## Problem Statement

Current join paths are string-heavy.

Example conceptual key:

```text
Alice|Sales|Jan
```

Problems:

```text
1. Many string allocations.
2. Many string clones.
3. HashMap<String, f64> can be memory-heavy.
4. Join paths are built per source/target row.
5. Alignment is sequential.
6. Aggregation is sequential.
7. Large cross-object models spend significant time in join logic.
```

---

## Proposed Change

### Step 1: Threshold-Based Parallel Join Path Creation

Use Rayon above a row-count threshold:

```rust
(0..row_count)
    .into_par_iter()
    .map(|row_idx| build_join_path(...))
    .collect()
```

### Step 2: Parallel Target Alignment

```rust
target_join_paths
    .par_iter()
    .map(|path| lookup.get(path).copied().unwrap_or(default_value))
    .collect()
```

### Step 3: Deterministic Parallel Aggregation

Use per-thread local maps:

```text
split rows into chunks
each worker builds local HashMap
merge local maps deterministically
```

Support:

```text
sum
mean
first
last
```

For first/last:

```text
track original row index
```

### Step 4: Better Join-Key Representation

Move from:

```rust
HashMap<String, f64>
```

toward:

```rust
HashMap<JoinKey, f64>
```

Possible forms:

```rust
struct JoinKey(Vec<u32>);
struct JoinKey64(u64);
struct JoinKey {
    item_ids: SmallVec<[u32; 4]>,
}
```

Start with a compatible wrapper and migrate gradually.

---

## Expected Impact

```text
1. Faster large cross-object joins.
2. Less string allocation.
3. Less memory pressure.
4. Faster resolver alignment.
5. Better use of Rayon where row counts justify it.
```

---

## Acceptance Criteria

```text
1. Join-path creation has threshold-based parallel path.
2. Target alignment has threshold-based parallel path.
3. Lookup aggregation supports deterministic parallel reduction.
4. first/last aggregation preserves original row-order semantics.
5. Join key representation reduces string allocation where possible.
6. Serial fallback remains available.
7. Output ordering matches current behavior.
8. Cross-object resolver output matches current behavior.
9. Benchmarks show improvement on large row-count joins.
10. No Python callbacks are introduced.
```

---

## Testing Notes

Add tests for:

```text
simple join path creation
multi-dimension join path creation
missing target keys
target alignment with default values
sum aggregation
mean aggregation
first aggregation
last aggregation
duplicate paths
large row benchmark
serial vs parallel parity
threshold fallback behavior
```

---

## Out of Scope

```text
Changing join semantics
Changing aggregation semantics
Changing output format
Full resolver rewrite
Parallel ready-node scheduler
```

---

## Priority

High / Medium

---

## Dependencies

```text
Depends on Final Issue 1.
Benefits from Final Issue 2.
Should be completed before Final Issue 10 if cross-object-heavy models are common.
```

---

## Labels

```text
omni-calc
rust
cross-object
resolver
join-path
lookup-aggregation
join-key
rayon
performance
```

---

## Components

```text
Omni-Calc
Rust Engine
Cross-Object Resolver
Node Alignment
Lookup Aggregation
```

---

# FINAL ISSUE 6

## Issue Type

Performance / Parallelism

---

## Title

Parallelize Safe Pre/Post Execution Processing: RecordBatch Materialization and Connected Dimension Preload

---

## Source Issues Merged

```text
Source Issue 3
Source Issue 4
```

---

## Summary

Parallelize safer independent phases that do not require full Kahn ready-node execution.

This includes:

```text
final RecordBatch materialization across blocks
connected dimension preload across blocks
```

These are safer than node-level execution because they are naturally per-block and can use compute/merge phases.

---

## Problem Statement

Two expensive phases are good candidates for safe parallelism:

```text
1. Final RecordBatch materialization
2. Connected dimension preload
```

RecordBatch materialization happens after execution is complete, so state should be read-only.

Connected dimension preload is mostly independent per block, but currently mixes computation with `ExecutionContext` mutation.

---

## Proposed Change

### RecordBatch Materialization

Parallelize per-block output creation:

```rust
let batches: Vec<(String, RecordBatch)> = ctx.calc_object_states
    .par_iter()
    .filter(|(block_key, _)| block_key.starts_with('b'))
    .filter_map(|(block_key, state)| {
        build_record_batch(state)
            .ok()
            .map(|batch| (block_key.clone(), batch))
    })
    .collect();
```

Then sort deterministically:

```rust
batches.sort_by(|a, b| a.0.cmp(&b.0));
```

### Connected Dimension Preload

Split into compute/merge:

```text
compute connected dimension columns per block
merge results into ExecutionContext
```

Parallel compute:

```rust
block_keys
    .par_iter()
    .map(|block_key| compute_connected_dims_for_block(...))
    .collect()
```

---

## Expected Impact

```text
1. Faster output creation for many-block models.
2. Faster connected dimension preload for many-block/many-dimension models.
3. Lower wall-clock time in pre/post execution stages.
4. Lower risk than node-level parallelism.
```

---

## Acceptance Criteria

```text
1. RecordBatch materialization can run per block in parallel.
2. Connected dimension preload can compute per block in parallel.
3. Both paths have deterministic merge order.
4. Both paths have serial fallback.
5. Output matches current serial behavior.
6. Memory pressure is measured.
7. No Python callbacks are introduced.
```

---

## Testing Notes

Add tests for:

```text
multiple block outputs
RecordBatch schema parity
numeric columns
string columns
connected dimension columns
block output ordering
connected dimension preload parity
duplicate connected dimension handling
serial vs parallel output parity
large block materialization benchmark
```

---

## Out of Scope

```text
Parallel ready-node execution
Changing RecordBatch schema
Changing connected dimension semantics
Changing calculation semantics
```

---

## Priority

Medium

---

## Dependencies

```text
Depends on Final Issue 1 for benchmark baseline.
Safer after Final Issue 2.
Can be implemented before Final Issue 10.
```

---

## Labels

```text
omni-calc
rust
recordbatch
connected-dimensions
preload
rayon
parallelism
performance
```

---

## Components

```text
Omni-Calc
Rust Engine
Result Materialization
Preload
Connected Dimensions
```

---

# FINAL ISSUE 7

## Issue Type

Standalone / Specialized Task

---

## Title

Standalone Source Issue 15 — Verify Scope and Implement Without Losing the Original Requirement

---

## Source Issue

```text
Source Issue 15
```

---

## Summary

Keep Source Issue 15 as a standalone task unless its exact description clearly belongs to one of the merged issues.

This issue must not be deleted or ignored.

If Source Issue 15 is about scheduler safety, sequential group safety, global lock rejection, or preloaded-only execution boundaries, then it can be merged into Final Issue 3.

Otherwise, keep it separate and implement it after the core scheduler foundation is complete.

---

## Merge Guidance

Merge into Final Issue 3 only if Source Issue 15 is about:

```text
sequential group safety
do not parallelize sequential groups
scheduler correctness
single-threaded Kahn parity
global Arc<Mutex<ExecutionContext>> rejection
resolver update boundary safety
preloaded-only execution hot path
```

Keep standalone if it is about:

```text
a specialized performance optimization
a localized correctness issue
a targeted refactor
a separate risk area
```

---

## Recommended Placement

```text
After Final Issue 3
Before Final Issue 10
```

---

## Scope

```text
1. Re-open Source Issue 15 from the source document.
2. Confirm exact title and description.
3. Decide whether it belongs to Final Issue 3 or remains standalone.
4. If standalone, implement it after scheduler foundation and before Rayon ready-node execution.
5. Add tests according to the confirmed scope.
```

---

## Acceptance Criteria

```text
1. Source Issue 15 is reviewed and not lost.
2. Final merge decision is documented.
3. If merged into Final Issue 3, its requirements are added there.
4. If standalone, a clear Jira task exists.
5. Any required tests are added.
6. No Python callbacks are introduced.
7. No calculation semantics are changed unless explicitly intended.
```

---

## Priority

Medium / High depending on confirmed scope

---

## Dependencies

```text
Likely depends on Final Issue 3.
Must be resolved before Final Issue 10 if scheduler/parallel-safety related.
```

---

## Labels

```text
omni-calc
rust
standalone
verification-needed
scheduler-safety
performance
```

---

## Components

```text
Omni-Calc
Rust Engine
Executor
```

---

# FINAL ISSUE 8

## Issue Type

Standalone / Specialized Task

---

## Title

Standalone Source Issue 16 — Verify Scope and Implement Without Losing the Original Requirement

---

## Source Issue

```text
Source Issue 16
```

---

## Summary

Keep Source Issue 16 as a standalone task unless its exact description clearly belongs to one of the merged issues.

This issue must not be deleted or ignored.

If Source Issue 16 is about clone reduction, shared references, ColumnStore, typed IDs, preloaded data reuse, resolver, join path, lookup aggregation, or join-key representation, then it can be merged into Final Issue 2 or Final Issue 5.

Otherwise, keep it standalone.

---

## Merge Guidance

Merge into Final Issue 2 if Source Issue 16 is about:

```text
clone reduction
shared references
ColumnStore
CalcObjectState structure
FormulaEvaluator clone reduction
typed IDs
PreloadedMetadata reuse
less copying
memory optimization
```

Merge into Final Issue 5 if Source Issue 16 is about:

```text
resolver
join path
lookup aggregation
cross-object join alignment
join-key representation
String join-path reduction
```

Keep standalone if it is about:

```text
a specialized optimization
a narrow algorithmic issue
a correctness issue not covered by other groups
```

---

## Recommended Placement

```text
After Final Issue 2
Before Final Issue 10
```

If join-related:

```text
After Final Issue 5
Before Final Issue 10
```

---

## Scope

```text
1. Re-open Source Issue 16 from the source document.
2. Confirm exact title and description.
3. Decide whether it belongs to Final Issue 2, Final Issue 5, or standalone.
4. If standalone, define concrete implementation and test plan.
5. Ensure any optimization uses Rust-owned preloaded data.
6. Ensure no PyO3 callback is introduced in execution hot path.
```

---

## Acceptance Criteria

```text
1. Source Issue 16 is reviewed and not lost.
2. Final merge decision is documented.
3. If merged, its requirements are added to the correct merged issue.
4. If standalone, a clear Jira task exists.
5. Tests are added according to the confirmed scope.
6. No Python callbacks are introduced.
7. Existing output behavior remains unchanged.
```

---

## Priority

Medium / High depending on confirmed scope

---

## Dependencies

```text
Likely depends on Final Issue 2 or Final Issue 5.
Must be resolved before Final Issue 10 if it affects worker hot path.
```

---

## Labels

```text
omni-calc
rust
standalone
verification-needed
data-structure
preload
resolver
performance
```

---

## Components

```text
Omni-Calc
Rust Engine
Execution State
Preload
Resolver
```

---

# FINAL ISSUE 9

## Issue Type

Standalone / Specialized Task

---

## Title

Standalone Source Issue 17 — Verify Scope and Implement Without Losing the Original Requirement

---

## Source Issue

```text
Source Issue 17
```

---

## Summary

Keep Source Issue 17 as a standalone task unless its exact description clearly belongs to one of the merged issues.

This issue must not be deleted or ignored.

If Source Issue 17 is about actuals, forecast indices, entity key reuse, dimension row metadata, dimension combinations, RecordBatch materialization, connected dimension preload, or pre/post execution parallelism, then it can be merged into Final Issue 4 or Final Issue 6.

Otherwise, keep it standalone.

---

## Merge Guidance

Merge into Final Issue 4 if Source Issue 17 is about:

```text
actuals
forecast indices
entity key reuse
dimension row metadata
dimension combinations
row key cache
sequential metadata reuse
```

Merge into Final Issue 6 if Source Issue 17 is about:

```text
RecordBatch materialization
connected dimension preload
pre/post execution parallelism
per-block compute/merge
safe parallel preprocessing
```

Keep standalone if it is about:

```text
a specialized performance task
a localized correctness issue
a narrow implementation concern
```

---

## Recommended Placement

If actuals/metadata-related:

```text
After Final Issue 4
Before Final Issue 10
```

If pre/post processing-related:

```text
After Final Issue 6
Before Final Issue 10
```

---

## Scope

```text
1. Re-open Source Issue 17 from the source document.
2. Confirm exact title and description.
3. Decide whether it belongs to Final Issue 4, Final Issue 6, or standalone.
4. If standalone, define implementation plan and test coverage.
5. Ensure no Python callback is added.
6. Preserve output and calculation semantics.
```

---

## Acceptance Criteria

```text
1. Source Issue 17 is reviewed and not lost.
2. Final merge decision is documented.
3. If merged, its requirements are added to the correct merged issue.
4. If standalone, a clear Jira task exists.
5. Tests are added according to the confirmed scope.
6. Existing output behavior remains unchanged.
7. No Python callbacks are introduced.
```

---

## Priority

Medium depending on confirmed scope

---

## Dependencies

```text
Likely depends on Final Issue 4 or Final Issue 6.
Must be resolved before Final Issue 10 if it affects parallel worker hot path.
```

---

## Labels

```text
omni-calc
rust
standalone
verification-needed
actuals
metadata
preload
recordbatch
performance
```

---

## Components

```text
Omni-Calc
Rust Engine
Actuals
Metadata
Pre/Post Processing
```

---

# FINAL ISSUE 10

## Issue Type

Epic / Story / Parallel Execution

---

## Title

Add Configurable Rayon-Based Parallel Execution for Independent Ready Nodes

---

## Source Issues Merged

```text
Source Issue 2
```

This issue includes the related parallel execution work originally discussed as:

```text
Parallelize independent input indicators
Parallelize property map population/property nodes
Parallelize independent calculation nodes
Configurable Rayon/thread-pool strategy
```

---

## Summary

After the foundation and data-structure work is complete, add actual parallel execution for independent ready nodes using Rayon.

This should be the final major implementation step, not the first.

The Rust scheduler should use the Kahn-style ready queue from Final Issue 3 and execute only safe independent nodes in parallel.

---

## Why This Must Be Last

Do not implement Rayon ready-node execution until:

```text
1. Benchmark baseline exists.
2. Clone-heavy structures are reduced.
3. PreloadedMetadata is complete and normalized for worker-safe execution.
4. ExecutionSnapshot exists.
5. NodeOutput exists.
6. Central merge phase exists.
7. ExecutionGraph exists.
8. Single-threaded Kahn scheduler matches serial output.
9. Resolver updates are safe.
10. Preloaded-only execution path is enforced.
11. Python callbacks are removed from execution hot path.
12. Sequential groups remain atomic.
```

---

## Scope

Parallelize only safe ready nodes:

```text
input indicator nodes
property nodes using PreloadedMetadata
independent calculation nodes
```

Do not parallelize:

```text
sequential groups
nodes with unresolved dependencies
nodes requiring Python callbacks
nodes requiring mutable resolver access during execution
nodes that depend on another node in the same parallel batch
```

---

## Proposed Flow

```rust
while !ready.is_empty() {
    let parallel_batch = collect_parallel_safe_ready_nodes(&ready);

    let outputs: Vec<NodeOutput> = parallel_batch
        .into_par_iter()
        .map(|node| {
            let snapshot = build_snapshot_readonly(&ctx, &node);
            execute_node(snapshot, node)
        })
        .collect();

    for output in stable_merge_order(outputs) {
        merge_node_output(&mut ctx, output);
    }

    update_ready_queue();
}
```

---

## Config Requirements

Add config:

```rust
pub struct EngineConfig {
    pub enable_parallel_execution: bool,
    pub parallel_threads: Option<usize>,
    pub parallel_node_threshold: usize,
    pub parallel_row_threshold: usize,
}
```

Rules:

```text
parallel mode disabled by default until parity is proven
serial fallback always available
custom Rayon thread pool should avoid oversubscription
nested Rayon should be avoided or controlled
parallel merge order must be deterministic
```

---

## Parallelism Targets

### 1. Independent input indicators

Input indicator nodes can run in parallel when they have no unresolved dependencies and each writes distinct output columns.

### 2. Property nodes

Property nodes can run in parallel only when they read from:

```text
PreloadedMetadata
PropertyCacheSnapshot
ExecutionSnapshot
```

No Python callback is allowed.

### 3. Independent calculation nodes

Calculation nodes can run in parallel when:

```text
all dependencies are merged
required resolver snapshot is available
required property columns are available
output columns are distinct
node is not sequential
node does not depend on another node in same batch
```

---

## Expected Impact

```text
1. Main execution speedup for wide models.
2. Better CPU utilization.
3. Parallel calculation of dependency-free nodes.
4. Better scaling after clone reduction and data-structure cleanup.
```

---

## Acceptance Criteria

```text
1. Parallel execution can be enabled/disabled.
2. Worker thread count can be configured.
3. Independent input nodes can run in parallel.
4. Property nodes can run in parallel using preloaded data only.
5. Independent calculation nodes can run in parallel.
6. Workers do not mutate ExecutionContext.
7. Workers do not mutate resolver.
8. Workers do not call Python/PyO3.
9. Merge order is deterministic.
10. Output matches single-threaded Kahn execution.
11. Output matches original serial execution.
12. Sequential groups are excluded.
13. Benchmarks prove speedup on wide models.
14. Serial fallback remains available.
```

---

## Testing Notes

Add tests for:

```text
serial vs parallel parity
different Rayon thread counts
parallel independent input indicators
parallel property nodes
parallel independent calculation nodes
dependent nodes not running too early
cross-block dependency ordering
deterministic warnings
deterministic output schema/order
parallel disabled fallback
missing preload rejected in parallel mode
sequential group exclusion
```

---

## Out of Scope

```text
Parallelizing sequential groups
Changing calculation semantics
Changing output format
Changing Python DAG manager behavior
Custom work-stealing scheduler
```

---

## Priority

High, but only after prerequisite issues are complete

---

## Dependencies

```text
Depends on Final Issue 1.
Depends on Final Issue 2.
Depends on Final Issue 3.
Strongly benefits from Final Issue 4.
Strongly benefits from Final Issue 5.
Can benefit from Final Issue 6.
Should wait until Final Issue 7, 8, and 9 are resolved or explicitly confirmed as not blocking.
```

---

## Labels

```text
omni-calc
rust
rayon
parallel-execution
ready-node-execution
scheduler
performance
preloaded-data
no-python-callbacks
```

---

## Components

```text
Omni-Calc
Rust Engine
Executor
Scheduler
Formula Evaluation
Input Execution
Property Loading
```

---

# Final Dependency Map

```text
Final Issue 1
  -> required before all performance work

Final Issue 2
  -> should happen before Final Issue 3, 4, 5, 6, and 10

Final Issue 3
  -> required before Final Issue 10
  -> useful before Final Issue 4, 5, and 6

Final Issue 4
  -> should happen before Final Issue 10 for actuals/sequential-heavy models

Final Issue 5
  -> should happen before Final Issue 10 for cross-object-heavy models

Final Issue 6
  -> can happen before Final Issue 10
  -> safer after Final Issue 2 and Final Issue 3

Final Issue 7
  -> place after Final Issue 3 unless merged into another issue

Final Issue 8
  -> place after Final Issue 2 or 5 depending on confirmed scope

Final Issue 9
  -> place after Final Issue 4 or 6 depending on confirmed scope

Final Issue 10
  -> final major implementation step
```

---

# Final Recommended Order

```text
1. Final Issue 1 — Benchmarking, Performance Baseline, and Debug Hot-Path Cleanup

2. Final Issue 2 — Data Structure, Clone Reduction, Shared References, FormulaEvaluator Context, and Typed IDs Foundation

3. Final Issue 3 — Core Kahn-Style Scheduler Foundation + Worker-Safe PreloadedMetadata

4. Final Issue 4 — Actuals, Forecast, and Dimension Row Metadata Optimization

5. Final Issue 5 — Cross-Object Join, Lookup, Aggregation, and Join-Key Optimization

6. Final Issue 6 — Pre/Post Processing Parallelism

7. Final Issue 7 — Standalone Source Issue 15

8. Final Issue 8 — Standalone Source Issue 16

9. Final Issue 9 — Standalone Source Issue 17

10. Final Issue 10 — Configurable Rayon-Based Parallel Ready-Node Execution
```

---

# Final Notes

This corrected merged roadmap keeps all 21 source issues covered while reducing implementation tracking to 10 final Jira issues.

The most important correction is:

```text
Source Issue 10 = Expand and Normalize PreloadedMetadata for Worker-Safe Execution
```

Therefore Source Issue 10 belongs in:

```text
Final Issue 3 — Core Kahn-Style Scheduler Foundation + Worker-Safe PreloadedMetadata
```

Do not start Rayon parallel ready-node execution first.

Correct implementation path:

```text
measure baseline
    ↓
reduce clones and improve data structures
    ↓
expand/normalize PreloadedMetadata
    ↓
build snapshot/output/merge foundation
    ↓
build single-threaded Kahn scheduler
    ↓
prove serial parity
    ↓
optimize actuals / row metadata / joins / pre-post phases
    ↓
resolve standalone issues
    ↓
enable controlled Rayon parallelism
```

This creates a safer and faster Omni-Calc engine without introducing race conditions, Python callback bottlenecks, nondeterministic output ordering, or global lock bottlenecks.
