# Final Merged Omni-Calc Performance / Parallelisation Jira Roadmap

## Branch / Code Reference

Branch:

```text
Blox-Dev / BLOX-2104-improve-preload-snapshot-py-rust-pass
```

GitHub:

```text
https://github.com/BloxSoftware/Blox-Dev/tree/BLOX-2104-improve-preload-snapshot-py-rust-pass
```

Reference planning document:

```text
https://github.com/veer-pratap-blox/tasks/blob/main/29-april-omni-calc-parallelisation-FINAL.md
```

Primary Rust areas reviewed / affected:

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

# High-Level Summary

The original planning document had 21 detailed issues related to Omni-Calc performance, parallelisation, data-structure improvements, clone reduction, preloaded data usage, and Rust execution safety.

This final version merges related issues into **10 final Jira issues** in the correct implementation order.

The goal is to move Omni-Calc from the current model:

```text
Python DAG manager creates ordered calc_steps
        ↓
Rust receives CalcPlan
        ↓
Rust creates one mutable ExecutionContext
        ↓
Rust loops through calc_steps in order
        ↓
Each node directly mutates shared state
        ↓
Resolver is updated during node processing
        ↓
Final RecordBatches are built
```

toward the target architecture:

```text
Benchmark baseline
    ↓
Better data structures + less cloning
    ↓
Immutable snapshots + NodeOutput
    ↓
Central merge phase
    ↓
Explicit Rust-side execution graph
    ↓
Single-threaded Kahn scheduler
    ↓
Preloaded-only execution hot path
    ↓
Safe resolver snapshots / materialization boundaries
    ↓
Targeted algorithmic optimizations
    ↓
Safe pre/post parallelism
    ↓
Configurable Rayon ready-node execution
```

---

# Important Global Rules

## 1. No Python callbacks inside Rust execution hot path

After preload, Omni-Calc Rust execution should use Rust-owned data only.

Allowed PyO3 usage:

```text
Python binding boundary
CalcPlan extraction
explicit metadata preload before Rust execution
returning result back to Python
```

Not allowed inside execution hot path:

```text
Python<'_>
PyObject
metadata_cache.call_method1(...)
metadata_cache.getattr(...)
lazy metadata callbacks from node execution
lazy metadata callbacks from Rayon workers
lazy metadata callbacks from formula evaluation
lazy metadata callbacks from resolver / join logic
```

Correct direction:

```text
Preload once
    ↓
Store in Rust-owned PreloadedMetadata
    ↓
Use immutable snapshots / Arc references
    ↓
Execute without Python callbacks
```

---

## 2. Do not start with global Arc<Mutex<ExecutionContext>>

This is rejected:

```rust
let ctx = Arc::new(Mutex::new(ctx));

ready_nodes.into_par_iter().for_each(|node| {
    let mut ctx = ctx.lock().unwrap();
    process_node(&mut ctx, node);
});
```

Reason:

```text
This makes execution thread-safe but not meaningfully parallel.
The entire node execution is serialized behind one global lock.
Formula evaluation, resolver updates, and state mutation all happen while holding the lock.
It can be slower than the current serial implementation.
```

Correct direction:

```text
ExecutionContext = coordinator-owned mutable state
ExecutionSnapshot = read-only worker input
NodeOutput = worker result
merge_node_output = short deterministic mutation phase
```

---

## 3. Do not parallelize sequential groups initially

Sequential functions such as:

```text
rollfwd(...)
prior(...)
balance(...)
change(...)
lookup(...)
```

must remain atomic initially because they rely on period order, entity state, and prior-period values.

Sequential groups should be represented as:

```rust
ExecNodeType::SequentialGroup
```

with:

```rust
parallel_safe = false
```

---

# Source Issue Mapping

The original 21 issues are merged into the final 10 issues as follows:

```text
Issue 1  -> Final Issue 3
Issue 2  -> Final Issue 10
Issue 3  -> Final Issue 6
Issue 4  -> Final Issue 6
Issue 5  -> Final Issue 5
Issue 6  -> Final Issue 5
Issue 7  -> Final Issue 2
Issue 8  -> Final Issue 2
Issue 9  -> Final Issue 5
Issue 10 -> Final Issue 3
Issue 11 -> Final Issue 4
Issue 12 -> Final Issue 4
Issue 13 -> Final Issue 1
Issue 14 -> Final Issue 1
Issue 15 -> Final Issue 7
Issue 16 -> Final Issue 8
Issue 17 -> Final Issue 9
Issue 18 -> Final Issue 1
Issue 19 -> Final Issue 2
Issue 20 -> Final Issue 4
Issue 21 -> Final Issue 2
```

---

# Correct Implementation Order

```text
1. Final Issue 1 — Benchmarking, Performance Baseline, and Debug Hot-Path Cleanup

2. Final Issue 2 — Data Structure, Clone Reduction, Shared References, FormulaEvaluator Context, and Typed IDs Foundation

3. Final Issue 3 — Core Kahn-Style Scheduler Foundation

4. Final Issue 4 — Actuals, Forecast, and Dimension Row Metadata Optimization

5. Final Issue 5 — Cross-Object Join, Lookup, Aggregation, and Join-Key Optimization

6. Final Issue 6 — Pre/Post Processing Parallelism

7. Final Issue 7 — Standalone Issue 15

8. Final Issue 8 — Standalone Issue 16

9. Final Issue 9 — Standalone Issue 17

10. Final Issue 10 — Configurable Rayon-Based Parallel Ready-Node Execution
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
Issue 13 - Benchmark harness / performance regression gates
Issue 14 - Debug hot-path cleanup
Issue 18 - Performance observability / benchmark-related cleanup
```

---

## Summary

Create a reliable benchmark and profiling foundation for Omni-Calc before implementing major scheduler, data-structure, clone-reduction, or Rayon parallelism changes.

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
RecordBatch materialization
final result build
```

Before making structural changes, we need benchmarks that show where time is currently spent.

Without benchmarks, performance changes may:

```text
look faster in theory but not in practice
improve one model shape and regress another
increase memory pressure
hide clone overhead behind parallelism
make Rayon execution memory-bound
```

---

## Problem Statement

Current risks:

```text
1. No consistent benchmark baseline for Omni-Calc execution.
2. No breakdown by execution phase.
3. No benchmark for formula evaluation alone.
4. No benchmark for resolver update/materialization.
5. No benchmark for cross-object join alignment.
6. No benchmark for RecordBatch creation.
7. No benchmark for clone-heavy evaluator setup.
8. Debug logs and diagnostics may allocate in hot paths.
9. Hardcoded debug paths can distort performance.
10. Future refactors may accidentally regress performance without being caught.
```

---

## Scope

Add benchmark and measurement coverage for:

```text
1. Full Omni-Calc execution
2. Current serial calc_steps execution
3. Future single-threaded Kahn scheduler
4. Future Rayon-ready-node execution
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

Add benchmark harness or internal performance mode.

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

Add benchmark scenarios:

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

Add config flags:

```text
CALC_DEBUG=false by default
CALC_PERF_TRACE=false by default
CALC_BENCH_MODE=true only in benchmark runs
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
Issue 7  - Optimize CalcObjectState column storage and lookup
Issue 8  - Reduce cloning and reuse preloaded/shared data
Issue 19 - Optimize FormulaEvaluator context cloning and shared column access
Issue 21 - Introduce structured node and column identifiers
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

Current examples:

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

or as an easier first step:

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

### Phase 1

Add `ColumnStore<T>` with stable order and indexed lookup.

### Phase 2

Convert dynamic columns:

```text
number_columns
string_columns
connected_dim_columns
```

to use `ColumnStore`.

### Phase 3

Add shared column aliases and avoid vector cloning in snapshots/evaluators where safe.

### Phase 4

Refactor `FormulaEvaluator` to share immutable `EvalContext`.

### Phase 5

Use `Arc<PreloadedMetadata>` / immutable property cache snapshots.

### Phase 6

Introduce typed ID helpers and conversion functions.

### Phase 7

Gradually migrate graph/scheduler/resolver to typed IDs where beneficial.

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

Refactor Rust Omni-Calc Executor Toward Safe Kahn-Style DAG Scheduling Foundation

---

## Source Issues Merged

```text
Issue 1  - Core scheduler foundation
Issue 10 - Cached parsed formula AST and dependency metadata
```

Includes original foundation sub-work:

```text
Immutable snapshots
NodeOutput
Central merge phase
Rust-side execution graph
Single-threaded Kahn scheduler
Resolver snapshot/materialization safety
Preloaded-only execution hot path
Reject global Arc<Mutex<ExecutionContext>>
Do not parallelize sequential groups initially
```

---

## Summary

Build the safe architecture required before true parallel execution.

The current Rust executor processes Python-provided `calc_steps` sequentially and mutates a shared `ExecutionContext`.

Target flow:

```text
Current serial executor
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
6. Formula dependency metadata is not structured for Rust-side scheduling.
7. Sequential groups must remain atomic.
8. Python callbacks must not occur in execution hot path.
```

---

## Scope

Add:

```rust
struct ExecutionSnapshot { ... }
struct NodeOutput { ... }
fn merge_node_output(ctx: &mut ExecutionContext, output: NodeOutput) { ... }
```

Add:

```rust
struct ExecutionGraph {
    nodes: HashMap<NodeId, ExecNode>,
    outgoing: HashMap<NodeId, Vec<NodeId>>,
    indegree: HashMap<NodeId, usize>,
}
```

Add:

```rust
enum ExecNodeType {
    InputIndicator,
    Property,
    Calculation,
    SequentialGroup,
}
```

Add formula dependency metadata:

```rust
struct FormulaDependencyInfo {
    input_indicators: Vec<NodeId>,
    property_refs: Vec<PropertyId>,
    cross_object_refs: Vec<CrossObjectRef>,
    sequential_functions: Vec<String>,
}
```

Cache parsed formula AST / dependency info:

```rust
struct PlannedFormula {
    node_id: NodeId,
    parsed_ast: Arc<AstNode>,
    dependency_info: FormulaDependencyInfo,
}
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

## Scheduler Requirements

Add single-threaded Kahn scheduler first:

```text
build graph
find zero-indegree nodes
execute one ready node
merge output
update resolver if needed
decrement dependents
enqueue newly ready nodes
```

No Rayon yet.

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

## Acceptance Criteria

```text
1. ExecutionSnapshot exists.
2. NodeOutput exists.
3. Shared state mutation is centralized in merge.
4. ExecutionGraph exists.
5. Graph tracks dependencies, outgoing edges, and indegrees.
6. Formula dependency metadata is cached/reused.
7. Single-threaded Kahn scheduler exists behind config/feature flag.
8. Single-threaded Kahn output matches current serial calc_steps output.
9. Resolver updates happen at safe boundaries.
10. Sequential groups are atomic.
11. No global Arc<Mutex<ExecutionContext>> production design.
12. No PyO3/Python callbacks in execution hot path.
```

---

## Testing Notes

Add tests for:

```text
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
missing preloaded metadata
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
python-ffi
parallelism-foundation
```

---

## Components

```text
Omni-Calc
Rust Engine
Executor
Scheduler
Cross-Object Resolver
Preload
Python Boundary
```

---

# FINAL ISSUE 4

## Issue Type

Performance / Algorithm Optimization / Refactor

---

## Title

Optimize Actuals, Forecast Handling, Dimension Row Metadata, and Entity Key Reuse

---

## Source Issues Merged

```text
Issue 11 - Actuals / forecast row-key handling
Issue 12 - Reuse dimension-combination metadata / compact row representation
Issue 20 - Actuals, forecast indices, and entity key reuse
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

### Phase 1

Precompute forecast mask per block.

Current style:

```rust
forecast_indices.contains(&row_idx)
```

Target:

```rust
forecast_mask[row_idx]
```

### Phase 2

Precompute row dimension keys once per block.

### Phase 3

Precompute row entity keys once per block, excluding time dimension.

### Phase 4

Update actuals loading to use cached row keys.

### Phase 5

Update sequential/last-actual logic to reuse entity keys.

### Phase 6

Avoid unnecessary cloning in `ActualsContext`.

### Phase 7

Optionally move from string keys to compact IDs after typed IDs / join-key optimizations are ready.

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
Issue 5 - Parallel join-path creation/alignment
Issue 6 - Parallel lookup-map aggregation
Issue 9 - Better join-key representation / avoid repeated string join paths
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
Issue 3 - Parallel final RecordBatch materialization
Issue 4 - Parallel connected dimension preload
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

Two expensive phases are currently good candidates for safe parallelism:

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

---

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

Standalone Issue 15 — Verify and Implement Specialized Scheduler / Safety / Performance Task

---

## Source Issue

```text
Issue 15
```

---

## Summary

Keep Issue 15 as a standalone task unless its exact description clearly belongs to one of the merged issues.

This issue must not be deleted or ignored.

If Issue 15 is about scheduler safety, sequential group safety, global lock rejection, or preloaded-only execution boundaries, then it can be merged into Final Issue 3.

Otherwise, keep it separate and implement it after the core scheduler foundation is complete.

---

## Merge Guidance

Merge into Final Issue 3 only if Issue 15 is about:

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

## Problem Statement

Issue 15 is not safely grouped without confirming its exact final content.

To avoid losing the issue, track it as a standalone verification/implementation item.

---

## Scope

```text
1. Re-open Issue 15 from the source document.
2. Confirm exact title and description.
3. Decide whether it belongs to Final Issue 3 or remains standalone.
4. If standalone, implement it after scheduler foundation and before Rayon ready-node execution.
5. Add tests according to the confirmed scope.
```

---

## Acceptance Criteria

```text
1. Issue 15 is reviewed and not lost.
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

Standalone Issue 16 — Verify and Implement Specialized DS / Preload / Join / Performance Task

---

## Source Issue

```text
Issue 16
```

---

## Summary

Keep Issue 16 as a standalone task unless its exact description clearly belongs to one of the merged issues.

This issue must not be deleted or ignored.

If Issue 16 is about clone reduction, shared references, ColumnStore, typed IDs, preloaded data reuse, resolver, join path, lookup aggregation, or join-key representation, then it can be merged into Final Issue 2 or Final Issue 5.

Otherwise, keep it standalone.

---

## Merge Guidance

Merge into Final Issue 2 if Issue 16 is about:

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

Merge into Final Issue 5 if Issue 16 is about:

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

## Problem Statement

Issue 16 was not safely mapped to one merged issue without confirming its exact source details.

It should remain visible as a standalone task until the exact scope is confirmed.

---

## Scope

```text
1. Re-open Issue 16 from the source document.
2. Confirm exact title and description.
3. Decide whether it belongs to Final Issue 2, Final Issue 5, or standalone.
4. If standalone, define concrete implementation and test plan.
5. Ensure any optimization uses Rust-owned preloaded data.
6. Ensure no PyO3 callback is introduced in execution hot path.
```

---

## Acceptance Criteria

```text
1. Issue 16 is reviewed and not lost.
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

Standalone Issue 17 — Verify and Implement Specialized Actuals / Metadata / Pre-Post Processing Task

---

## Source Issue

```text
Issue 17
```

---

## Summary

Keep Issue 17 as a standalone task unless its exact description clearly belongs to one of the merged issues.

This issue must not be deleted or ignored.

If Issue 17 is about actuals, forecast indices, entity key reuse, dimension row metadata, dimension combinations, RecordBatch materialization, connected dimension preload, or pre/post execution parallelism, then it can be merged into Final Issue 4 or Final Issue 6.

Otherwise, keep it standalone.

---

## Merge Guidance

Merge into Final Issue 4 if Issue 17 is about:

```text
actuals
forecast indices
entity key reuse
dimension row metadata
dimension combinations
row key cache
sequential metadata reuse
```

Merge into Final Issue 6 if Issue 17 is about:

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

## Problem Statement

Issue 17 was not safely mapped into one merged issue without confirming its exact source details.

It should remain visible as a standalone item until confirmed.

---

## Scope

```text
1. Re-open Issue 17 from the source document.
2. Confirm exact title and description.
3. Decide whether it belongs to Final Issue 4, Final Issue 6, or standalone.
4. If standalone, define implementation plan and test coverage.
5. Ensure no Python callback is added.
6. Preserve output and calculation semantics.
```

---

## Acceptance Criteria

```text
1. Issue 17 is reviewed and not lost.
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
Issue 2 - Parallel ready-node execution
```

Also includes original ticket grouping:

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
3. ExecutionSnapshot exists.
4. NodeOutput exists.
5. Central merge phase exists.
6. ExecutionGraph exists.
7. Single-threaded Kahn scheduler matches serial output.
8. Resolver updates are safe.
9. Preloaded-only execution path is enforced.
10. Python callbacks are removed from execution hot path.
11. Sequential groups remain atomic.
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
Depends on Final Issue 1
Depends on Final Issue 2
Depends on Final Issue 3
Strongly benefits from Final Issue 4
Strongly benefits from Final Issue 5
Can benefit from Final Issue 6
Should wait until Final Issue 7/8/9 are resolved or explicitly confirmed as not blocking
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
  -> should happen before Final Issue 3, 4, 5, 6, 10

Final Issue 3
  -> required before Final Issue 10
  -> useful before Final Issue 4, 5, 6

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

3. Final Issue 3 — Core Kahn-Style Scheduler Foundation

4. Final Issue 4 — Actuals, Forecast, and Dimension Row Metadata Optimization

5. Final Issue 5 — Cross-Object Join, Lookup, Aggregation, and Join-Key Optimization

6. Final Issue 6 — Pre/Post Processing Parallelism

7. Final Issue 7 — Standalone Issue 15

8. Final Issue 8 — Standalone Issue 16

9. Final Issue 9 — Standalone Issue 17

10. Final Issue 10 — Configurable Rayon-Based Parallel Ready-Node Execution
```

---

# Final Notes

This merged roadmap keeps all 21 original issues covered while reducing implementation tracking to 10 final Jira issues.

The most important rule is:

```text
Do not start Rayon parallel ready-node execution first.
```

Correct implementation path:

```text
measure baseline
    ↓
reduce clones and improve data structures
    ↓
build snapshot/output/merge foundation
    ↓
build single-threaded Kahn scheduler
    ↓
prove serial parity
    ↓
optimize metadata/actuals/join/pre-post phases
    ↓
resolve standalone issues
    ↓
enable controlled Rayon parallelism
```

This creates a safer and faster Omni-Calc engine without introducing race conditions, Python callback bottlenecks, nondeterministic output ordering, or global lock bottlenecks.
