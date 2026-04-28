# Omni-Calc Rust Parallelism Refactor: Jira Issue Set

## Branch / Code Reference

Branch:

```text
Blox-Dev / BLOX-2104-improve-preload-snapshot-py-rust-pass
```

GitHub:

```text
https://github.com/BloxSoftware/Blox-Dev/tree/BLOX-2104-improve-preload-snapshot-py-rust-pass
```

Primary Rust areas reviewed:

```text
modelAPI/omni-calc/src/engine/exec/executor.rs
modelAPI/omni-calc/src/engine/exec/context.rs
modelAPI/omni-calc/src/engine/exec/preload.rs
modelAPI/omni-calc/src/engine/exec/get_source_data/resolver.rs
modelAPI/omni-calc/src/engine/exec/get_source_data/dim_loader.rs
modelAPI/omni-calc/src/engine/exec/steps/input_handler/mod.rs
modelAPI/omni-calc/src/engine/exec/steps/calculation.rs
modelAPI/omni-calc/src/engine/exec/steps/sequential.rs
modelAPI/omni-calc/src/engine/integration/calc_plan.rs
modelAPI/omni-calc/src/python.rs
modelAPI/omni-calc/Cargo.toml
```

---

# High-Level Summary

This Jira issue set is based on the current Omni-Calc Rust execution model in the branch:

```text
BLOX-2104-improve-preload-snapshot-py-rust-pass
```

The branch has already moved metadata access toward Rust-side preload using `PreloadedMetadata`, which reduces Python callback dependency during execution. This creates a path toward real Rust-side parallel execution in the future.

However, the current executor still processes Python-provided `calc_steps` sequentially and mutates a shared `ExecutionContext` during node execution.

Current model:

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

Target architecture:

```text
Current serial executor
    ↓
Immutable execution snapshots
    ↓
Per-node NodeOutput
    ↓
Central merge phase
    ↓
Explicit Rust-side execution graph
    ↓
Single-threaded Kahn scheduler
    ↓
Safe foundation for future parallelism
    ↓
Parallel ready-node execution in later follow-up issues
```

---

# Issue Grouping

The original 15 analysis tickets are grouped into the following Jira issues:

## Issue 1: Core Foundation Refactor

Merged original tickets:

```text
Ticket 1  - Immutable snapshots + NodeOutput + merge phase
Ticket 2  - Rust-side execution graph
Ticket 3  - Single-threaded Kahn scheduler
Ticket 7  - Resolver materialization / read-only resolver snapshot
Ticket 12 - Remove/isolate Python callback paths from Rust hot path
Ticket 14 - Reject global Arc<Mutex<ExecutionContext>>
Ticket 15 - Do not parallelize sequential groups initially
```

## Issue 2: Future Node-Level Parallel Execution

Merged original tickets:

```text
Ticket 4  - Parallelize independent input indicators
Ticket 5  - Parallelize property map population/property nodes
Ticket 6  - Parallelize independent calculation nodes
Ticket 13 - Configurable Rayon/thread-pool strategy
```

## Independent Performance Issues

These are separate follow-up issues because they can be implemented independently after the core executor structure is safer:

```text
Ticket 8  - Parallelize final RecordBatch materialization
Ticket 9  - Parallelize connected dimension preload
Ticket 10 - Parallelize join-path creation/alignment
Ticket 11 - Parallel aggregation for lookup maps
```

Final issue list:

```text
Issue 1 - Refactor Rust Omni-Calc Executor Toward Safe Kahn-Style DAG Scheduling Foundation
Issue 2 - Add Configurable Rayon-Based Parallel Execution for Independent Ready Nodes
Issue 3 - Parallelize Final RecordBatch Materialization Across Blocks
Issue 4 - Parallelize Connected Dimension Preload Across Blocks
Issue 5 - Parallelize Join-Path Creation and Target Alignment for Large Cross-Object Joins
Issue 6 - Evaluate Parallel Lookup-Map Aggregation with Deterministic Reductions
```

---

# ISSUE 1

## Issue Type

Technical Task / Refactor

---

## Title

Refactor Rust Omni-Calc Executor Toward Safe Kahn-Style DAG Scheduling Foundation

---

## Original Tickets Merged Into This Issue

```text
Ticket 1  - Immutable snapshots + NodeOutput + merge phase
Ticket 2  - Rust-side execution graph
Ticket 3  - Single-threaded Kahn scheduler
Ticket 7  - Resolver materialization / read-only resolver snapshot
Ticket 12 - Remove/isolate Python callback paths from Rust hot path
Ticket 14 - Reject global Arc<Mutex<ExecutionContext>>
Ticket 15 - Do not parallelize sequential groups initially
```

---

## Summary

Refactor the Rust `omni-calc` executor so it is structurally ready for a future Kahn-style parallel DAG scheduler.

The current Rust executor processes Python-provided `calc_steps` sequentially and mutates a shared `ExecutionContext` during node execution. This is safe for the current serial model, but it prevents safe, deterministic, and meaningful parallel execution of independent ready nodes.

This issue should create the architecture required for future parallelism, but it should **not** implement actual Rayon/thread-pool parallel execution yet.

The goal is to move from:

```text
calc_steps[0] -> calc_steps[1] -> calc_steps[2] -> ...
```

to a single-threaded version of:

```text
ready queue
    ↓
execute ready node
    ↓
return NodeOutput
    ↓
merge output centrally
    ↓
update resolver at safe boundary
    ↓
release dependent nodes
```

This gives the executor a correct dependency-driven foundation before any parallel worker execution is introduced.

---

## Background / Context

The current execution flow is mainly in:

```text
modelAPI/omni-calc/src/engine/exec/executor.rs
```

Current simplified flow:

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

Important point:

```rust
process_input_step(&mut ctx, step)
process_calculation_step(&mut ctx, step)
process_sequential_step(&mut ctx, step)
```

Each step receives mutable access to the same `ExecutionContext`.

The executor comments also state that the `calc_steps` are already ordered by the Python DAG manager, so Rust simply processes them in order.

Today Rust is effectively doing:

```text
Python-built topological step order
        ↓
Rust sequentially executes each step
        ↓
Each node mutates shared executor state
```

Rust is **not yet** doing:

```text
Build Rust-side graph
        ↓
Track indegrees
        ↓
Find dependency-free ready nodes
        ↓
Execute ready nodes
        ↓
Merge outputs
        ↓
Release dependents
```

---

## Current Graph Representation

The graph-like request data comes from:

```text
modelAPI/omni-calc/src/engine/integration/calc_plan.rs
```

Relevant structures:

```rust
pub struct CalcPlan {
    pub scenario_id: i64,
    pub forecast_start_date: Option<String>,
    pub model_start_date: Option<String>,
    pub time_granularity: String,
    pub fy_start_month: String,
    pub blocks: HashMap<String, BlockSpec>,
    pub dimensions: HashMap<String, DimensionSpec>,
    pub calc_steps: Vec<CalcStep>,
    pub metadata: CalcMetadata,
    pub node_maps: Vec<PlannedNodeMap>,
    pub variable_filters: HashMap<String, VariableFilter>,
    pub property_specs: HashMap<String, PropertySpec>,
}
```

Current step structure:

```rust
pub struct CalcStep {
    pub calc_type: String,
    pub nodes: Vec<String>,
}
```

Rust receives ordered steps like:

```json
[
  { "calc_type": "input", "nodes": ["ind1", "ind2"] },
  { "calc_type": "calculation", "nodes": ["ind3"] },
  { "calc_type": "sequential", "nodes": ["ind4", "ind5"] }
]
```

But Rust does not currently maintain:

```rust
struct ExecutionGraph {
    nodes: HashMap<NodeId, ExecNode>,
    indegree: HashMap<NodeId, usize>,
    outgoing: HashMap<NodeId, Vec<NodeId>>,
}
```

Dependency ordering is mostly implicit in `calc_steps`.

Cross-object mapping is represented separately using:

```rust
PlannedNodeMap
VariableFilter
PropertySpec
```

---

## Current Shared Mutable State

The shared state is defined in:

```text
modelAPI/omni-calc/src/engine/exec/context.rs
```

Current `ExecutionContext` concept:

```rust
pub struct ExecutionContext<'a> {
    pub calc_object_states: HashMap<String, CalcObjectState>,
    pub resolver: CrossObjectResolver,
    pub plan: &'a Plan,
    pub preloaded_metadata: Option<&'a PreloadedMetadata>,
    pub string_property_map_cache: HashMap<(i64, i64, i64), StringPropertyMap>,
    pub numeric_property_map_cache: HashMap<(i64, i64, i64), (PropertyMap, Vec<String>)>,
    pub input_handler: InputStepHandler,
    pub calc_handler: CalculationStepHandler,
    pub seq_handler: SequentialStepHandler,
    pub nodes_calculated: usize,
    pub warnings: Vec<CalcWarning>,
}
```

The following shared mutable fields are important for parallelism:

```text
ctx.calc_object_states
ctx.resolver
ctx.warnings
ctx.nodes_calculated
ctx.string_property_map_cache
ctx.numeric_property_map_cache
```

Today this is fine because execution is serial.

In a parallel-ready design, node execution should not directly mutate these shared fields.

---

## Current State Mutation During Calculation

Current calculation processing lives in:

```text
modelAPI/omni-calc/src/engine/exec/executor.rs
```

`process_calculation_step` loops node-by-node:

```rust
for node_id in &step.nodes {
    ...
}
```

Inside each node, the code may:

```rust
ctx.warnings.push(warning);
```

```rust
state.number_columns.push((col_name, values));
```

```rust
state.string_columns.push((col_name, values));
```

```rust
state.connected_dim_columns.push((col_name, values));
```

```rust
ctx.nodes_calculated += step_res.count;
```

```rust
ctx.update_resolver(&block_key);
```

So each node currently does:

```text
dependency resolution
+ property collection
+ cross-object resolution
+ formula evaluation
+ state mutation
+ warning collection
+ resolver update
```

This mixing of calculation and mutation is the main blocker for safe parallelism.

---

## Why `Arc<Mutex<ExecutionContext>>` Is Not Acceptable

A naive approach would be:

```rust
let ctx = Arc::new(Mutex::new(ctx));

ready_nodes.into_par_iter().for_each(|node| {
    let mut ctx = ctx.lock().unwrap();
    process_node(&mut ctx, node);
});
```

This is not a good production design.

Reason:

```text
The whole executor state is locked for the entire node execution.
Only one worker can actually run node logic at a time.
Expensive formula evaluation happens while holding the lock.
Resolver updates happen while holding the lock.
State mutation happens while holding the lock.
This provides thread safety but not true parallel speedup.
```

Rejected production design:

```rust
Arc<Mutex<ExecutionContext>>
```

around the full node lifecycle.

Preferred design:

```text
Build immutable snapshot
        ↓
Execute node without global mutation
        ↓
Return NodeOutput
        ↓
Merge output in one short controlled mutation phase
```

---

## Proposed Architecture

### 1. Keep `ExecutionContext` Coordinator-Owned

`ExecutionContext` should remain the owner of mutable execution state, but only the coordinator/scheduler should mutate it.

Workers or node execution functions should not take:

```rust
&mut ExecutionContext
```

for full node processing.

Target:

```text
ExecutionContext = coordinator-owned mutable state
```

---

### 2. Add Immutable `ExecutionSnapshot`

Add a read-only snapshot containing all data required for a node to calculate safely.

Example concept:

```rust
#[derive(Clone)]
struct ExecutionSnapshot {
    block_key: String,
    block_spec: Arc<BlockSpec>,

    dim_columns: Arc<Vec<(String, Vec<String>)>>,
    number_columns: Arc<Vec<(String, Vec<f64>)>>,
    string_columns: Arc<Vec<(String, Vec<String>)>>,
    connected_dim_columns: Arc<Vec<(String, Vec<String>)>>,

    resolver_snapshot: Arc<CrossObjectResolverSnapshot>,
    preloaded_metadata: Arc<PreloadedMetadata>,
    property_cache_snapshot: Arc<PropertyCacheSnapshot>,
}
```

Purpose:

```text
ExecutionSnapshot = read-only node input
```

A node should be executable using only:

```rust
fn execute_node(snapshot: ExecutionSnapshot, node: ExecNode) -> NodeOutput
```

No global mutable context should be required during calculation.

---

### 3. Add `NodeOutput`

Instead of directly pushing results into `CalcObjectState`, node execution should return an output object.

Example:

```rust
struct NodeOutput {
    block_key: String,

    number_columns: Vec<(String, Vec<f64>)>,
    string_columns: Vec<(String, Vec<String>)>,
    connected_dim_columns: Vec<(String, Vec<String>)>,

    warnings: Vec<CalcWarning>,
    nodes_calculated: usize,

    should_update_resolver: bool,
}
```

This makes the node execution output explicit.

Worker-like flow:

```rust
let output = execute_node(snapshot, node);
```

Coordinator flow:

```rust
merge_node_output(&mut ctx, output);
```

---

### 4. Add Centralized Merge Phase

Only the merge phase should mutate `ExecutionContext`.

Example:

```rust
fn merge_node_output(ctx: &mut ExecutionContext, output: NodeOutput) {
    if let Some(state) = ctx.calc_object_states.get_mut(&output.block_key) {
        for col in output.number_columns {
            if !state.number_columns.iter().any(|(name, _)| name == &col.0) {
                state.number_columns.push(col);
            }
        }

        for col in output.string_columns {
            if !state.string_columns.iter().any(|(name, _)| name == &col.0) {
                state.string_columns.push(col);
            }
        }

        for col in output.connected_dim_columns {
            if !state.connected_dim_columns.iter().any(|(name, _)| name == &col.0) {
                state.connected_dim_columns.push(col);
            }
        }
    }

    ctx.warnings.extend(output.warnings);
    ctx.nodes_calculated += output.nodes_calculated;

    if output.should_update_resolver {
        ctx.update_resolver(&output.block_key);
    }
}
```

This creates a controlled mutation point.

Important rule:

```text
Do not lock/mutate during calculation.
Only mutate during merge.
```

---

## Rust-Side Execution Graph

### Proposed Types

Add:

```rust
struct ExecutionGraph {
    nodes: HashMap<String, ExecNode>,
    outgoing: HashMap<String, Vec<String>>,
    indegree: HashMap<String, usize>,
}
```

Add:

```rust
struct ExecNode {
    id: String,
    block_key: String,
    calc_type: ExecNodeType,
    deps: Vec<String>,
    outputs: Vec<String>,
    parallel_safe: bool,
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

---

## Graph Construction Inputs

Build the graph from:

```text
CalcPlan.calc_steps
CalcPlan.blocks
BlockSpec.indicators
IndicatorSpec.parsed_formula
CalcPlan.property_specs
CalcPlan.node_maps
CalcPlan.variable_filters
```

---

## Dependency Tracking Requirements

### 1. Intra-Block Indicator Dependencies

If formula for `ind200` references `ind100`, graph should contain:

```text
ind100 -> ind200
```

Meaning:

```text
ind200 cannot execute until ind100 is merged.
```

---

### 2. Cross-Object Dependencies

Relevant resolver file:

```text
modelAPI/omni-calc/src/engine/exec/get_source_data/resolver.rs
```

`CrossObjectResolver` stores calculated source block data:

```rust
pub struct CrossObjectResolver {
    calculated_blocks: HashMap<String, BlockData>,
    node_maps: HashMap<NodeMapKey, PlannedNodeMap>,
    variable_filters: HashMap<String, VariableFilter>,
}
```

Current resolver expects source block to already exist:

```rust
let source_block = self.calculated_blocks.get(&source_block_key)
    .ok_or_else(|| Error::eval_error(...))?;
```

A formula reference like:

```text
block39951___ind259068
```

means the target node must wait until:

```text
source block b39951 has ind259068 calculated
source block is materialized into resolver
resolver has needed connected dimension columns for joins/filters
```

In graph form:

```text
b39951.ind259068 -> target_node
```

---

### 3. Planned NodeMap Dependencies

`PlannedNodeMap` includes:

```rust
source_block_key
target_block_key
variable_name
source_dims_that_map
additional_columns_for_join
merge_on
groupby
property_join_columns
aggregation_mode
```

The graph should preserve dependencies implied by:

```text
source_block_key
target_block_key
variable_name
property_join_columns
additional_columns_for_join
```

If property bridge columns are required for a cross-object join, the source block snapshot must include them before the dependent node runs.

---

### 4. Variable Filter Dependencies

`VariableFilter` includes:

```rust
variable_name
source_block_key
source_node_id
filters
```

Filtered cross-object references should be treated as dependencies on:

```text
source block
source node
filter dimension/property availability
connected dimension columns if linked_dimension_id is used
```

---

### 5. Property Dependencies

Relevant files:

```text
modelAPI/omni-calc/src/engine/exec/preload.rs
modelAPI/omni-calc/src/engine/exec/get_source_data/dim_loader.rs
modelAPI/omni-calc/src/engine/exec/steps/input_handler/mod.rs
```

This branch adds `PreloadedMetadata`:

```rust
pub struct PreloadedMetadata {
    pub dimension_items: HashMap<i64, Vec<DimensionItem>>,
    pub property_maps: HashMap<(i64, i64, i64), HashMap<i64, String>>,
}
```

Property loading has Rust snapshot-based functions:

```rust
load_string_property_map_from_snapshot(...)
load_property_map_from_snapshot(...)
```

But legacy PyO3 callback functions still exist:

```rust
load_property_map(py, metadata_cache, ...)
load_string_property_map(py, metadata_cache, ...)
```

Graph/scheduler work must ensure future worker execution paths use preloaded Rust data only.

---

### 6. Sequential Group Dependencies

Sequential steps must be atomic.

Current sequential handler:

```text
modelAPI/omni-calc/src/engine/exec/steps/sequential.rs
```

Sequential formulas include:

```text
rollfwd(...)
prior(...)
balance(...)
change(...)
lookup(...)
```

These use period-by-period evaluation with entity state/history.

Do not split a sequential step like:

```text
nodes = [ind1, ind2, ind3]
```

into independent graph nodes.

Represent it as:

```rust
ExecNode {
    id: "seq_group_<id>",
    block_key,
    calc_type: ExecNodeType::SequentialGroup,
    deps,
    outputs: vec!["ind1", "ind2", "ind3"],
    parallel_safe: false,
}
```

---

## Single-Threaded Kahn Scheduler

Before adding Rayon or worker threads, add a single-threaded Kahn scheduler.

Pseudo-code:

```rust
let mut ready = VecDeque::new();

for node in graph.nodes.values() {
    if graph.indegree[&node.id] == 0 {
        ready.push_back(node.id.clone());
    }
}

while let Some(node_id) = ready.pop_front() {
    let node = graph.nodes[&node_id].clone();

    let snapshot = build_snapshot(&ctx, &node);
    let output = execute_node(snapshot, node);

    merge_node_output(&mut ctx, output);

    update_resolver_if_needed(&mut ctx, &node);

    for dep in graph.outgoing[&node_id].iter() {
        graph.indegree[dep] -= 1;
        if graph.indegree[dep] == 0 {
            ready.push_back(dep.clone());
        }
    }
}
```

The first implementation must remain single-threaded.

Purpose:

```text
Validate graph correctness.
Validate dependency ordering.
Validate resolver materialization timing.
Validate output parity with current calc_steps execution.
Keep sequential groups atomic.
```

---

## Resolver Materialization / Snapshot Strategy

Current resolver update:

```rust
pub fn update_resolver(&mut self, block_key: &str) {
    if let Some(state) = self.calc_object_states.get(block_key) {
        if let Ok(batch) = build_record_batch(state) {
            self.resolver.add_block(block_key.to_string(), batch);
        }
    }
}
```

Current issue:

```text
Node 1 -> rebuild full RecordBatch
Node 2 -> rebuild full RecordBatch
Node 3 -> rebuild full RecordBatch
```

`build_record_batch` clones:

```rust
StringArray::from(values.clone())
Float64Array::from(values.clone())
```

This is expensive and makes resolver mutation tightly coupled to node execution.

### Proposed Direction

Node execution should not call:

```rust
ctx.update_resolver(...)
```

directly.

Instead:

```text
execute node
return NodeOutput
merge output
update resolver at dependency-safe boundary
release dependents
```

### Read-Only Resolver Snapshot Concept

Add a read-only snapshot concept:

```rust
struct CrossObjectResolverSnapshot {
    calculated_blocks: Arc<HashMap<String, BlockData>>,
    node_maps: Arc<HashMap<NodeMapKey, PlannedNodeMap>>,
    variable_filters: Arc<HashMap<String, VariableFilter>>,
}
```

Future workers should read from resolver snapshots.

Workers should not mutate:

```rust
ctx.resolver
```

---

## Python Callback Boundary / Preload Requirement

Python boundary:

```text
modelAPI/omni-calc/src/python.rs
```

The branch preloads metadata before Rust execution:

```rust
let preloaded =
    crate::engine::exec::preload::preload_metadata(py, metadata_cache.as_ref(), &plan.inner)
        .map_err(pyo3::exceptions::PyRuntimeError::new_err)?;

engine.set_preloaded_metadata(preloaded);

let result = py
    .allow_threads(|| runtime::execute(&mut engine, plan.inner.clone()))
    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
```

This is good because Rust execution happens inside:

```rust
py.allow_threads(...)
```

Meaning:

```text
Rust execution can run without holding the Python GIL.
```

However, worker-ready execution must not call Python at all.

### Required Mode

Add a conceptual mode:

```rust
enum MetadataAccessMode {
    PreloadedOnly,
    PythonFallbackAllowed,
}
```

Future parallel/worker-ready execution should require:

```rust
MetadataAccessMode::PreloadedOnly
```

If required metadata is missing, fail early with a clear error.

Do not lazy-load metadata from Python inside node execution.

---

## Scope

This issue includes:

```text
1. Introduce ExecutionSnapshot or equivalent read-only node input.
2. Introduce NodeOutput or equivalent per-node result.
3. Centralize state mutation in merge_node_output or equivalent.
4. Build explicit Rust-side ExecutionGraph.
5. Track node dependencies, outgoing edges, and indegrees.
6. Represent sequential steps as atomic non-parallel-safe nodes.
7. Implement single-threaded Kahn scheduler behind a feature flag/config.
8. Keep existing serial calc_steps execution path as default until parity is proven.
9. Refactor resolver updates to be coordinator-owned.
10. Add/read-only resolver snapshot concept for future worker execution.
11. Ensure worker-style execution paths use PreloadedMetadata only.
12. Reject global Arc<Mutex<ExecutionContext>> around full node execution.
13. Reject parallelizing sequential groups in this foundation issue.
```

---

## Out of Scope

This issue should not implement real parallel execution yet.

Out of scope:

```text
Full parallel scheduler with worker threads
Rayon/thread-pool integration
Work-stealing optimization
Parallelizing independent input indicators
Parallelizing property map population/property nodes
Parallelizing independent calculation nodes
Parallelizing final RecordBatch materialization
Parallelizing connected dimension preload
Parallelizing join-path creation/alignment
Parallel aggregation for lookup maps
Parallelizing sequential groups
Changing calculation semantics
Changing Python DAG manager behavior
Changing output format
```

---

## Proposed Implementation Plan

### Phase 1: Snapshot + Output Model

Add:

```rust
ExecutionSnapshot
NodeOutput
merge_node_output(...)
```

Refactor internals so node execution can eventually return `NodeOutput`.

Initial implementation can still run serially.

---

### Phase 2: Centralize Mutation

Move these operations into merge/coordinator functions:

```rust
ctx.warnings.push(...)
ctx.nodes_calculated += ...
state.number_columns.push(...)
state.string_columns.push(...)
state.connected_dim_columns.push(...)
ctx.update_resolver(...)
```

---

### Phase 3: Add ExecutionGraph

Add:

```rust
ExecutionGraph
ExecNode
ExecNodeType
```

Graph should include:

```text
node id
block key
node type
dependencies
outputs
parallel_safe
outgoing dependents
indegree
```

---

### Phase 4: Graph Diagnostics

Add diagnostics:

```text
print/debug node dependencies
print/debug ready nodes
detect cycles
compare graph topological order with current calc_steps order
```

---

### Phase 5: Single-Threaded Kahn Execution

Add:

```rust
execute_with_kahn_scheduler(ctx, graph)
```

behind a feature flag/config.

Keep existing execution path until parity is proven.

---

### Phase 6: Resolver Boundary Cleanup

Make resolver updates coordinator-owned.

Workers or node execution functions should not directly mutate resolver.

---

### Phase 7: Preloaded-Only Validation

Audit execution paths to ensure future worker-ready paths do not use:

```rust
Python<'_>
PyObject
metadata_cache.call_method1(...)
metadata_cache.getattr(...)
```

---

## Acceptance Criteria

### Architecture

- `ExecutionSnapshot` or equivalent exists.
- `NodeOutput` or equivalent exists.
- Node execution can be separated from global state mutation.
- Shared state mutation is centralized.
- Full `ExecutionContext` is not locked for entire node execution.
- Existing serial path remains available.

### Graph

- Rust can build an explicit graph from `CalcPlan`.
- Graph includes input nodes, property nodes, calculation nodes, and sequential groups.
- Graph tracks dependencies, outgoing edges, and indegrees.
- Sequential groups are represented as atomic nodes.
- Cross-object references become explicit dependencies.
- Property dependencies are represented or validated.
- Cycle detection exists.

### Scheduler

- Single-threaded Kahn scheduler exists behind config/feature flag.
- Kahn scheduler produces same outputs as current serial calc_steps execution.
- Resolver updates happen at safe boundaries.
- Dependent nodes are released only after required outputs are merged.

### Resolver

- Resolver mutation is coordinator-owned.
- Node execution does not directly call resolver updates.
- Read-only resolver snapshot concept exists.
- Cross-object references still resolve correctly.

### Python / Preload

- Future worker-style execution path uses `PreloadedMetadata`.
- Missing preloaded metadata fails early with a clear diagnostic.
- Python callback loaders are not used in worker-ready paths.
- No PyO3/Python callbacks should occur inside the Rust Omni-Calc execution hot path after preload. PyO3 should remain only at the Python boundary/preload stage.

### Rejected Designs

- No production implementation uses one global `Arc<Mutex<ExecutionContext>>` around full node execution.
- Sequential groups are not parallelized.

---

## Testing Notes

Add or update tests for:

### Snapshot / Output / Merge

```text
numeric column merge
string column merge
connected dimension column merge
duplicate column prevention
warning merge behavior
node count merge behavior
resolver update trigger behavior
```

### Graph Construction

```text
input -> calculation dependency
multiple independent inputs
intra-block formula dependency
cross-block blockX___indY dependency
property dependency
filtered cross-object dependency
sequential group as atomic node
cycle detection
topological order parity with calc_steps
```

### Kahn Scheduler

```text
pure input plan
simple calculated indicator
calculated indicator depending on another indicator
cross-block reference
property join
filtered reference
sequential step
actuals / forecast-start behavior
serial executor vs Kahn executor parity
```

### Resolver

```text
source block available before dependent node
source indicator exists in resolver batch
connected dimension columns included in resolver batch
resolver update after merge
missing source block diagnostic
missing indicator column diagnostic
```

### Python / Preload

```text
complete preload success
missing dimension items
missing property map
preloaded-only mode rejects missing metadata
no Python callback required during worker-ready execution
```

---

## Risks / Edge Cases

```text
Hidden dependencies may exist that are currently only protected by Python calc_steps ordering.
Cross-object references require resolver snapshots at precise times.
Connected dimension columns may be needed in resolver batches for property-bridge joins.
Warning order may change if graph order differs from calc_steps.
Column order may matter for downstream consumers.
Duplicate columns must be handled deterministically.
Sequential groups must remain atomic.
Preloaded metadata may not cover every legacy path.
Removing lazy Python fallback may expose missing metadata gaps.
Single-threaded Kahn must prove parity before any Rayon parallelism is attempted.
```

---

## Priority

Highest

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
gil
parallelism-foundation
tech-debt
performance-foundation
```

---

## Components

```text
Omni-Calc
Rust Engine
Calculation Executor
Dependency Scheduler
Cross-Object Resolver
Metadata Preload
Python Boundary
```

---

# ISSUE 2

## Issue Type

Epic / Story

---

## Title

Add Configurable Rayon-Based Parallel Execution for Independent Ready Nodes

---

## Original Tickets Merged Into This Issue

```text
Ticket 4  - Parallelize independent input indicators
Ticket 5  - Parallelize property map population/property nodes
Ticket 6  - Parallelize independent calculation nodes
Ticket 13 - Configurable Rayon/thread-pool strategy
```

---

## Summary

After Issue 1 lands and the executor has a safe graph/snapshot/output/merge architecture, add actual parallel execution for independent ready nodes.

This issue should use the Rust-side Kahn scheduler to find dependency-free ready nodes and execute safe nodes concurrently using Rayon.

Parallelize only nodes that are proven independent and safe:

```text
input indicator nodes
property nodes using preloaded metadata
calculation nodes with complete dependencies
```

Do not parallelize sequential groups.

---

## Background / Context

The branch already includes:

```text
rayon = "1.10"
```

in:

```text
modelAPI/omni-calc/Cargo.toml
```

However, current Rust execution does not yet use Rayon for executor scheduling.

The branch also moves metadata toward Rust-side preload, which allows property-related execution to avoid Python callbacks when `PreloadedMetadata` is complete.

---

## Problem Statement

Even after Issue 1, execution will still be single-threaded.

The next opportunity is to run independent ready nodes concurrently.

Examples:

```text
multiple input indicators in the same ready layer
multiple property nodes that only read preloaded metadata
multiple calculation nodes whose dependencies are already merged
```

Current executor processes these sequentially.

---

## Scope

This issue includes:

```text
1. Add configurable Rayon/thread-pool strategy.
2. Parallelize independent input indicator nodes.
3. Parallelize property map population/property node execution where metadata is preloaded.
4. Parallelize independent calculation nodes.
5. Preserve deterministic merge order.
6. Keep sequential groups excluded.
7. Keep serial fallback mode.
```

---

## Technical Analysis

### Input Nodes

Input loading is handled in:

```text
modelAPI/omni-calc/src/engine/exec/steps/input_handler/mod.rs
```

Input processing includes:

```text
parse data_values_json
detect input type
build DimensionMapper
build TimeUtils
load constant/raw/growth/constant_by_year values
apply actuals / forecast-start behavior
```

This is mostly local CPU work and does not require Python callbacks.

Parallelism level:

```text
independent calc execution
dependency graph layer execution
```

---

### Property Nodes

Property data is now available through:

```text
PreloadedMetadata
```

Snapshot-based functions:

```rust
load_string_property_map_from_snapshot(...)
load_property_map_from_snapshot(...)
```

Property maps should be prebuilt or read-only during node execution.

Parallelism level:

```text
cache population
preloaded metadata processing
independent property node execution
```

---

### Calculation Nodes

Formula evaluation is Rust-local via:

```text
modelAPI/omni-calc/src/engine/exec/steps/calculation.rs
modelAPI/omni-calc/src/engine/exec/formula_eval.rs
```

A calculation node can run in parallel if:

```text
all dependencies are already merged
required cross-object columns are available in the snapshot
required property columns are available from immutable property cache
it writes unique output columns
it is not a sequential group
it does not depend on another node in the same batch
```

Parallelism level:

```text
independent calc execution
dependency graph layer execution
batch formula evaluation
```

---

## Proposed Change

### Add Config

Add or extend engine config:

```rust
pub struct EngineConfig {
    pub enable_parallel_execution: bool,
    pub parallel_threads: Option<usize>,
    pub parallel_node_threshold: usize,
    pub parallel_row_threshold: usize,
}
```

### Add Parallel Execution Path

Conceptual flow:

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

### Deterministic Merge

Even if execution is parallel, merge must be deterministic.

Recommended:

```text
sort outputs by graph order / node order / original calc_steps order before merge
```

---

## Why Rayon Is Appropriate

Rayon is appropriate because this is CPU-bound Rust work:

```text
formula evaluation
input value generation
property map processing
vector calculations
```

Async is not appropriate for these execution paths because there is no IO wait inside worker node execution after preload.

Work-stealing should not be customized initially. Rayon’s default scheduler is sufficient for first implementation.

---

## Risks / Edge Cases

```text
Oversubscription if Python service handles many requests concurrently.
Nested Rayon usage could cause excessive parallelism.
Parallel output order must be deterministic.
Warnings must be stable or explicitly ordered.
Memory usage may increase when many large nodes run concurrently.
Hidden dependencies must be caught by graph construction.
Property cache must be immutable/read-only during worker execution.
Workers must not mutate ExecutionContext.
Workers must not mutate resolver.
Workers must not call Python.
```

---

## Dependencies

Requires Issue 1.

Specifically requires:

```text
ExecutionSnapshot
NodeOutput
central merge phase
ExecutionGraph
single-threaded Kahn scheduler parity
preloaded-only worker path
resolver snapshot safety
```

---

## Acceptance Criteria

- Parallel execution can be enabled/disabled by config.
- Serial fallback remains available.
- Rayon worker count can be configured or controlled.
- Independent input nodes can execute in parallel.
- Property nodes can execute in parallel using preloaded metadata only.
- Independent calculation nodes can execute in parallel.
- Workers do not mutate `ExecutionContext`.
- Workers do not mutate `CrossObjectResolver`.
- Workers do not call Python.
- Merge order is deterministic.
- Output matches serial Kahn execution.
- Sequential groups are excluded.

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
```

---

## Out of Scope

```text
Parallelizing sequential groups
Changing calculation semantics
Changing Python DAG manager behavior
Changing output format
Custom work-stealing scheduler
Parallel RecordBatch materialization
Parallel connected dimension preload
Parallel join-path alignment
Parallel lookup-map aggregation
```

---

## Priority

High

---

## Labels

```text
omni-calc
rust
rayon
parallel-execution
input-nodes
property-nodes
calculation-nodes
scheduler
performance
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

# ISSUE 3

## Issue Type

Performance Task

---

## Title

Parallelize Final RecordBatch Materialization Across Blocks

---

## Original Ticket

```text
Ticket 8 - Parallelize final RecordBatch materialization
```

---

## Summary

Parallelize final output `RecordBatch` construction across blocks after execution completes.

This is an independent performance optimization because final result materialization is naturally per-block and happens after executor mutation is complete.

---

## Background / Context

Final result building is in:

```text
modelAPI/omni-calc/src/engine/exec/context.rs
```

Current result building loops through `ctx.calc_object_states` and calls:

```rust
build_record_batch(state)
```

for each block.

`build_record_batch` clones columns into Arrow arrays:

```rust
StringArray::from(values.clone())
Float64Array::from(values.clone())
```

---

## Problem Statement

Final block materialization is sequential.

For models with many blocks or large block states, this can be CPU/memory-copy heavy.

Since final execution state should be read-only at this point, each block’s `RecordBatch` can be built independently.

---

## Proposed Change

Use Rayon to build batches per block:

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

Then sort and insert deterministically:

```rust
let mut batches = batches;
batches.sort_by(|a, b| a.0.cmp(&b.0));

for (block_key, batch) in batches {
    result.add_block(block_key, batch);
}
```

---

## Parallelism Opportunity

```text
snapshot/materialization work
per-block final output build
```

---

## Expected Impact

```text
Faster final result build for many-block models.
Low risk because state is read-only after execution.
No dependency graph changes required.
```

---

## Risks / Edge Cases

```text
Higher memory pressure because multiple Arrow arrays may be built at once.
Block output ordering must remain deterministic.
Errors must be handled consistently with current serial behavior.
```

---

## Dependencies

Can be done independently.

Recommended after Issue 1 for cleaner state ownership.

---

## Acceptance Criteria

- Final `RecordBatch` creation can run in parallel per block.
- Output matches serial implementation.
- Block ordering is deterministic.
- Errors are handled consistently.
- Serial fallback exists or can be configured.
- Tests cover multiple block outputs and schema parity.

---

## Testing Notes

Add tests for:

```text
multiple block outputs
numeric columns
string columns
connected dimension columns
duplicate column warning behavior
serial vs parallel result parity
large synthetic block materialization benchmark
```

---

## Out of Scope

```text
Changing RecordBatch schema
Changing output format
Parallelizing per-column materialization inside one block
Changing calculation execution
```

---

## Priority

Medium

---

## Labels

```text
omni-calc
rust
recordbatch
arrow
rayon
materialization
quick-win
performance
```

---

## Components

```text
Omni-Calc
Rust Engine
Result Materialization
Arrow Output
```

---

# ISSUE 4

## Issue Type

Performance Task / Tech Debt

---

## Title

Parallelize Connected Dimension Preload Across Blocks

---

## Original Ticket

```text
Ticket 9 - Parallelize connected dimension preload
```

---

## Summary

Refactor `preload_connected_dimensions` so connected dimension columns are computed per block in parallel and merged afterward.

---

## Background / Context

Connected dimension preload is currently in:

```text
modelAPI/omni-calc/src/engine/exec/executor.rs
```

Function:

```rust
fn preload_connected_dimensions(ctx: &mut ExecutionContext)
```

Current behavior:

```text
for each block
    for each block dimension
        inspect DimensionSpec.property_values
        build connected dimension columns
        mutate state.connected_dim_columns
```

This is currently sequential and mixes computation with state mutation.

---

## Problem Statement

Connected dimension preload is mostly independent per block.

However, current implementation directly reads and mutates `ExecutionContext`.

This prevents safe parallel execution and makes the logic harder to reason about.

---

## Proposed Change

Split into compute and merge phases.

Compute phase:

```rust
fn compute_connected_dims_for_block(
    snapshot: ConnectedDimPreloadSnapshot,
    block_key: String,
) -> BlockConnectedDimOutput
```

Output:

```rust
struct BlockConnectedDimOutput {
    block_key: String,
    connected_dim_columns: Vec<(String, Vec<String>)>,
    warnings: Vec<CalcWarning>,
}
```

Parallel compute:

```rust
let outputs: Vec<BlockConnectedDimOutput> = block_keys
    .par_iter()
    .map(|block_key| compute_connected_dims_for_block(snapshot.clone(), block_key.clone()))
    .collect();
```

Deterministic merge:

```rust
for output in stable_order(outputs) {
    merge_connected_dim_output(&mut ctx, output);
}
```

---

## Parallelism Opportunity

```text
preload work
per-block preprocessing
cache population
```

---

## Expected Impact

```text
Faster preload for models with many blocks/dimensions.
Cleaner compute/merge separation.
Less shared mutable state during preload.
```

---

## Risks / Edge Cases

```text
Duplicate connected dimension columns must still be skipped.
Merge order must be deterministic.
Existing warning/logging behavior may change.
Parallel logging may become noisy.
Must avoid reading mutable state while merging.
```

---

## Dependencies

Can be done independently.

Recommended after Issue 1 or with a local compute/merge split.

---

## Acceptance Criteria

- Connected dimension computation does not mutate `ExecutionContext`.
- Per-block connected dimension computation can run in parallel.
- Merge preserves current output behavior.
- Duplicate column handling remains correct.
- Serial and parallel preload outputs match.
- Logging remains usable.

---

## Testing Notes

Add tests for:

```text
block with no connected dimensions
block with connected dimension property values
multiple blocks with connected dimensions
duplicate connected dimension columns
missing dimension specs
empty property_values
serial vs parallel preload parity
```

---

## Out of Scope

```text
Changing connected dimension semantics
Changing Python payload format
Parallelizing formula execution
Parallelizing property map population
```

---

## Priority

Medium

---

## Labels

```text
omni-calc
rust
preload
connected-dimensions
rayon
performance
```

---

## Components

```text
Omni-Calc
Rust Engine
Preload
Connected Dimensions
```

---

# ISSUE 5

## Issue Type

Performance Task

---

## Title

Parallelize Join-Path Creation and Target Alignment for Large Cross-Object Joins

---

## Original Ticket

```text
Ticket 10 - Parallelize join-path creation/alignment
```

---

## Summary

Add threshold-based parallel implementations for join-path creation and target alignment in node alignment code.

---

## Background / Context

Cross-object alignment uses:

```text
modelAPI/omni-calc/src/engine/exec/node_alignment/join_path.rs
modelAPI/omni-calc/src/engine/exec/node_alignment/lookup.rs
modelAPI/omni-calc/src/engine/exec/node_alignment/mod.rs
modelAPI/omni-calc/src/engine/exec/get_source_data/resolver.rs
```

Current join path build:

```rust
pub fn build_all_join_paths(
    dim_columns: &[(String, Vec<String>)],
    dim_names: &[String],
) -> Vec<String> {
    (0..row_count)
        .map(|row_idx| build_join_path(dim_columns, dim_names, row_idx))
        .collect()
}
```

Current target alignment:

```rust
for path in target_join_paths {
    let value = lookup.get(path).copied().unwrap_or(default_value);
    result.push(value);
}
```

---

## Problem Statement

For large row counts, join path construction and target alignment can be CPU/memory intensive.

These operations are currently sequential.

---

## Proposed Change

Add parallel variants:

```rust
pub fn build_all_join_paths_parallel(...)
pub fn align_with_lookup_parallel(...)
```

Use threshold-based fallback:

```text
if row_count < threshold:
    use serial implementation
else:
    use parallel implementation
```

Example:

```rust
use rayon::prelude::*;

(0..row_count)
    .into_par_iter()
    .map(|row_idx| build_join_path(dim_columns, dim_names, row_idx))
    .collect()
```

For alignment:

```rust
target_join_paths
    .par_iter()
    .map(|path| lookup.get(path).copied().unwrap_or(default_value))
    .collect()
```

---

## Parallelism Opportunity

```text
cross-object alignment
row-level batch evaluation
read-only lookup usage
```

---

## Expected Impact

```text
Faster cross-block joins for large row counts.
Useful for models with heavy cross-object references.
No full scheduler parallelism required.
```

---

## Risks / Edge Cases

```text
String allocation is heavy and parallelization may increase memory pressure.
Small datasets may become slower due to Rayon overhead.
Output ordering must remain identical to serial implementation.
Debug counters and missing-count stats need reduction-safe logic.
HashMap must be read-only during parallel access.
```

---

## Dependencies

Can be implemented independently.

Recommended after Issue 1 and Issue 7-style resolver cleanup.

---

## Acceptance Criteria

- Parallel path is threshold-based.
- Serial fallback remains available.
- Output ordering matches serial implementation.
- Missing/default value behavior matches serial implementation.
- Tests prove serial/parallel parity.
- Benchmarks show improvement on large row counts.

---

## Testing Notes

Add tests for:

```text
simple join path creation
multi-dimension join path creation
missing target keys
target alignment with default values
large row synthetic benchmark
threshold fallback behavior
serial vs parallel parity
```

---

## Out of Scope

```text
Parallel lookup-map aggregation
Replacing string keys with encoded keys
Changing join semantics
Changing resolver behavior
```

---

## Priority

Medium

---

## Labels

```text
omni-calc
rust
node-alignment
join-path
cross-object
rayon
performance
```

---

## Components

```text
Omni-Calc
Rust Engine
Node Alignment
Cross-Object Resolver
```

---

# ISSUE 6

## Issue Type

Performance Research / Optimization

---

## Title

Evaluate Parallel Lookup-Map Aggregation with Deterministic Reductions

---

## Original Ticket

```text
Ticket 11 - Parallel aggregation for lookup maps
```

---

## Summary

Investigate and implement parallel lookup-map aggregation for large cross-object joins only if deterministic and measurably faster than the current sequential `HashMap` aggregation.

---

## Background / Context

Lookup map creation is in:

```text
modelAPI/omni-calc/src/engine/exec/node_alignment/lookup.rs
```

Current aggregation concept:

```rust
for (path, &value) in join_paths.iter().zip(values.iter()) {
    *lookup.entry(path.clone()).or_insert(0.0) += value;
}
```

Supported aggregation modes include:

```text
sum
mean
first
last
```

---

## Problem Statement

For large source row counts, lookup map creation can be expensive.

However, naive parallelization using a shared `HashMap` would require locking and may be slower or nondeterministic.

---

## Proposed Change

Use per-worker local maps and deterministic reduction.

Conceptual approach:

```text
split rows into chunks
each worker builds local HashMap
merge local maps deterministically
```

Aggregation representation:

```rust
enum AggValue {
    Sum(f64),
    Mean { sum: f64, count: usize },
    First { index: usize, value: f64 },
    Last { index: usize, value: f64 },
}
```

Rules:

```text
sum  -> reduce by addition
mean -> reduce sum and count
first -> keep lowest original row index
last -> keep highest original row index
```

---

## Parallelism Opportunity

```text
aggregation/reduction
large cross-object joins
lookup-map construction
```

---

## Expected Impact

```text
Potential speedup for large grouped cross-object references.
Complements Issue 5.
May reduce cost of CrossObjectResolver alignment.
```

---

## Risks / Edge Cases

```text
Floating-point summation order may change tiny numeric results.
first/last must preserve original row order semantics.
Per-thread maps increase memory usage.
Parallel version may be slower for small/medium inputs.
Must benchmark before enabling by default.
```

---

## Dependencies

Recommended after Issue 5.

---

## Acceptance Criteria

- Parallel aggregation is deterministic.
- Modes match serial behavior:
  - sum
  - mean
  - first
  - last
- Threshold-based fallback exists.
- Floating-point tolerance is documented.
- Benchmarks justify enabling the parallel path.
- Serial implementation remains available.

---

## Testing Notes

Add tests for:

```text
sum aggregation parity
mean aggregation parity
first aggregation by row index
last aggregation by row index
duplicate join paths
empty input
large synthetic grouped input
deterministic output across repeated runs
serial vs parallel benchmark
```

---

## Out of Scope

```text
Changing aggregation semantics
Replacing join path string keys
Changing resolver behavior
Full scheduler parallelism
```

---

## Priority

Low / Medium

---

## Labels

```text
omni-calc
rust
lookup-map
aggregation
deterministic-reduction
rayon
performance-research
```

---

## Components

```text
Omni-Calc
Rust Engine
Node Alignment
Cross-Object Resolver
```

---

# Recommended Implementation Order

```text
1. Issue 1 - Core Kahn-style scheduler foundation
2. Issue 2 - Configurable Rayon-based parallel ready-node execution
3. Issue 3 - Parallel final RecordBatch materialization
4. Issue 4 - Parallel connected dimension preload
5. Issue 5 - Parallel join-path creation and target alignment
6. Issue 6 - Parallel lookup-map aggregation research
```

---

# Dependency Map

```text
Issue 1
  -> required before Issue 2

Issue 2
  -> depends on Issue 1

Issue 3
  -> can be done independently
  -> safer after Issue 1

Issue 4
  -> can be done independently with local compute/merge split
  -> cleaner after Issue 1

Issue 5
  -> can be done independently
  -> benefits from resolver cleanup in Issue 1

Issue 6
  -> should follow Issue 5
```

---

# Quick Wins vs Larger Refactors

## Larger Refactors

```text
Issue 1 - Core Kahn-style scheduler foundation
Issue 2 - Configurable Rayon-based parallel ready-node execution
```

Why:

```text
They change executor architecture and scheduling.
They require strong output parity tests.
They touch shared state, resolver behavior, and dependency ordering.
```

## Quick / Medium Wins

```text
Issue 3 - Parallel final RecordBatch materialization
Issue 4 - Parallel connected dimension preload
Issue 5 - Parallel join-path creation/alignment
```

Why:

```text
They are more localized.
They are naturally per-block or per-row.
They do not require full scheduler parallelism.
```

## Research / Benchmark First

```text
Issue 6 - Parallel lookup-map aggregation
```

Why:

```text
Correctness is more subtle because aggregation modes must remain deterministic.
Floating-point reduction order may change tiny numeric results.
Must benchmark before enabling by default.
```

---

# Final Notes

The branch’s preload changes create a real opportunity for Rust-side parallelism because metadata can now be moved into `PreloadedMetadata` before execution and Rust execution runs under `py.allow_threads`.

However, the current executor is still serial and mutable-state-centric.

The correct path is:

```text
Issue 1:
    Build safe architecture first.

Issue 2:
    Add controlled parallel ready-node execution.

Issues 3-6:
    Add independent performance optimizations after correctness foundation exists.
```

Do not start by wrapping the whole executor in:

```rust
Arc<Mutex<ExecutionContext>>
```

Do not parallelize sequential groups initially.

Do not allow worker execution to call Python.

Do not change calculation semantics or output format as part of these issues.
