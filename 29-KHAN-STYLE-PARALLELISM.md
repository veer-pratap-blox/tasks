# Refactor Rust `omni-calc` Executor Toward Safe Kahn-Style Parallel DAG Scheduling

## Summary

Evaluate and refactor the Rust `omni-calc` execution model to prepare it for a future Kahn-style parallel DAG scheduler.

Currently, the Rust executor processes Python-provided `calc_steps` sequentially and mutates a shared `ExecutionContext` during each node execution. This makes safe parallel execution difficult because multiple ready nodes would need to read from and write to shared executor state at the same time.

The goal of this ticket is to refactor the executor design toward:

- Immutable execution snapshots
- Per-node execution outputs
- A small synchronized merge phase
- Explicit Rust-side dependency tracking
- Safe groundwork for future parallel DAG execution

---

## Background

The current Rust execution flow is mainly in the following files:

- `modelAPI/omni-calc/src/engine/exec/executor.rs`
- `modelAPI/omni-calc/src/engine/exec/context.rs`
- `modelAPI/omni-calc/src/engine/integration/calc_plan.rs`
- `modelAPI/omni-calc/src/engine/exec/get_source_data/resolver.rs`
- `modelAPI/omni-calc/src/engine/exec/preload.rs`

At the moment, Rust receives a Python-built `CalcPlan` containing:

- `blocks`
- `dimensions`
- Ordered `calc_steps`
- `node_maps`
- `variable_filters`
- `property_specs`

The Rust `executor::execute` function creates a single mutable `ExecutionContext` and processes each step in order:

```rust
for step in &plan.request.calc_steps {
    match step.calc_type.as_str() {
        "input" => process_input_step(&mut ctx, step),
        "calculation" => process_calculation_step(&mut ctx, step),
        "sequential" => process_sequential_step(&mut ctx, step),
        _ => {}
    }
}
```

This means the current model is effectively sequential topological execution based on Python-provided ordering, not a Rust-side Kahn scheduler.

---

## Current Problem

Most execution functions currently take:

```rust
&mut ExecutionContext
```

This allows each node execution to directly mutate shared executor state such as:

- `ctx.calc_object_states`
- `ctx.resolver`
- `ctx.warnings`
- `ctx.nodes_calculated`
- `ctx.string_property_map_cache`
- `ctx.numeric_property_map_cache`

This is safe today because execution is serial. However, this structure is not suitable for concurrent execution.

Simply wrapping the entire `ExecutionContext` in `Arc<Mutex<ExecutionContext>>` would technically make the code thread-safe, but it would not provide meaningful parallelism.

Bad pattern:

```rust
let mut ctx = ctx.lock().unwrap();
process_entire_node(&mut ctx, node);
```

If every worker locks the full context during node execution, only one node can effectively run at a time. This would serialize the executor behind a global lock.

---

## Required Design Direction

Refactor execution into three separate phases:

---

## 1. Build an Immutable Execution Snapshot

Create a read-only snapshot of everything a node needs before execution.

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
}
```

The snapshot should be:

- Read-only
- Safe to pass to worker threads
- Independent from mutable global executor state
- Built before node execution starts

---

## 2. Execute Node and Return `NodeOutput`

Node execution should not mutate global executor state directly.

Instead of this pattern:

```rust
fn process_node(ctx: &mut ExecutionContext, node_id: &str) {
    // read state
    // calculate
    // mutate state
}
```

Use this pattern:

```rust
fn execute_node(snapshot: ExecutionSnapshot, node: ExecNode) -> NodeOutput {
    // read from snapshot
    // calculate result
    // return output
}
```

Example output structure:

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

This makes node execution isolated and easier to parallelize later.

---

## 3. Merge Output in a Small Synchronized Phase

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
            state.string_columns.push(col);
        }

        for col in output.connected_dim_columns {
            state.connected_dim_columns.push(col);
        }
    }

    ctx.warnings.extend(output.warnings);
    ctx.nodes_calculated += output.nodes_calculated;

    if output.should_update_resolver {
        ctx.update_resolver(&output.block_key);
    }
}
```

This keeps expensive calculation outside the lock and keeps shared mutation short and deterministic.

---

## Additional Issue: Resolver Update Frequency

Currently:

```rust
ctx.update_resolver(&block_key)
```

rebuilds a full `RecordBatch` from the block state and inserts it into `CrossObjectResolver`.

This can happen after individual node execution.

This is expensive because `build_record_batch` clones dimension, connected dimension, string, and number columns into Arrow arrays.

Current problem:

```text
node 1 -> rebuild block RecordBatch
node 2 -> rebuild block RecordBatch
node 3 -> rebuild block RecordBatch
```

Recommended direction:

- Run ready nodes
- Merge outputs
- Update resolver only when downstream dependencies require the updated source block

Alternative direction:

- Update resolver after a batch/layer of completed nodes

This should reduce unnecessary repeated `RecordBatch` rebuilds.

---

## Additional Issue: Cross-Object Dependencies

`CrossObjectResolver` expects source block data to already exist in `calculated_blocks`.

A node with a reference like:

```text
block39951___ind259068
```

must not run until:

- Source block `b39951` has `ind259068` calculated
- Resolver has a usable snapshot for that source block

In the current serial model, this is guaranteed by Python’s `calc_steps`.

In a future Kahn-style scheduler, Rust must explicitly track this dependency.

---

## Additional Issue: Metadata Preload Requirement

This branch introduces `PreloadedMetadata` in:

```text
modelAPI/omni-calc/src/engine/exec/preload.rs
```

This is the correct direction for parallel execution because workers should read from Rust-owned immutable data instead of calling back into Python during execution.

For real parallel execution, required metadata should be preloaded before worker execution starts.

Without complete preload, worker threads may need Python callbacks or shared lazy metadata access, which can cause:

- GIL contention
- Blocking behavior
- Shared mutable cache issues
- Reduced parallel speedup
- Non-deterministic execution risks

---

## Proposed Implementation Plan

---

## Phase 1: Introduce Explicit Rust-Side Execution Graph

Add an internal graph structure such as:

```rust
struct ExecutionGraph {
    nodes: HashMap<String, ExecNode>,
    outgoing: HashMap<String, Vec<String>>,
    indegree: HashMap<String, usize>,
}
```

Each node should contain:

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

Node types:

```rust
enum ExecNodeType {
    InputIndicator,
    Property,
    Calculation,
    SequentialGroup,
}
```

Build this graph from:

- `CalcPlan.calc_steps`
- `CalcPlan.blocks`
- `CalcPlan.property_specs`
- `CalcPlan.node_maps`
- `CalcPlan.variable_filters`
- Parsed formulas

The graph should make dependency ordering explicit on the Rust side instead of relying only on the Python-provided `calc_steps` order.

---

## Phase 2: Keep Execution Sequential but Use Graph-Driven Scheduling

Before adding threads, replace the current direct `for calc_step in calc_steps` model with a single-threaded Kahn scheduler.

Pseudo-flow:

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

    for dep in graph.outgoing[&node_id].iter() {
        graph.indegree[dep] -= 1;
        if graph.indegree[dep] == 0 {
            ready.push_back(dep.clone());
        }
    }
}
```

This phase should:

- Preserve current behavior
- Validate the Rust-side dependency graph
- Keep execution single-threaded initially
- Make future parallelization easier and safer

---

## Phase 3: Add Parallel Execution Only for Safe Nodes

Once single-threaded Kahn execution matches current behavior, parallelize only nodes that are safe.

Safe nodes:

- Input indicator nodes with no unresolved dependencies
- Calculation nodes whose dependencies are complete
- Property nodes that only read preloaded metadata
- Nodes that produce distinct output columns

Do not parallelize initially:

- Sequential groups
- Nodes that require unresolved cross-object references
- Nodes requiring Python callbacks
- Nodes that depend on mutable resolver updates during execution

Parallel flow:

```rust
let outputs: Vec<NodeOutput> = parallel_ready_nodes
    .into_par_iter()
    .map(|node| {
        let snapshot = build_snapshot_readonly(&ctx, &node);
        execute_node(snapshot, node)
    })
    .collect();

for output in outputs {
    merge_node_output(&mut ctx, output);
}
```

This approach keeps expensive work parallel while keeping mutation centralized and deterministic.

---

## Out of Scope

This ticket should not implement full work-stealing yet.

Out of scope:

- Full parallel scheduler implementation
- Rayon/thread-pool integration
- Work-stealing optimization
- Parallelizing sequential groups
- Changing calculation semantics
- Changing Python DAG manager behavior
- Changing output format

This ticket is mainly to refactor the executor toward a safe architecture for future parallel scheduling.

---

## Acceptance Criteria

- Rust execution logic has a clear separation between:
  - Read-only execution snapshot
  - Node execution
  - Output merge

- Node execution no longer needs to mutate the full `ExecutionContext` directly.

- A `NodeOutput`-style result structure exists for calculated outputs.

- Shared mutable state updates are centralized in a merge function.

- Existing serial behavior remains unchanged.

- Sequential groups continue to execute atomically.

- Cross-object dependency handling remains correct.

- Metadata required during execution is read from `PreloadedMetadata` where possible.

- No Python metadata callbacks are introduced inside worker-style execution paths.

- Existing tests continue to pass.

- New tests cover:
  - Graph construction
  - Node output merge
  - Resolver update behavior
  - Dependency ordering
  - Sequential group atomic execution

---

## Notes

This refactor is required before implementing a true Kahn-style parallel DAG executor.

Using `Arc<Mutex<ExecutionContext>>` around the entire executor is not recommended because it would serialize most execution behind one global lock.

The preferred design is:

```text
ExecutionContext = coordinator-owned mutable state
ExecutionSnapshot = read-only worker input
NodeOutput = worker result
merge_node_output = only mutation point
```

---

## Final Target Architecture

```text
Coordinator:
  owns graph indegrees
  owns ready queue
  owns mutable ExecutionContext
  merges completed NodeOutput values

Workers:
  receive ready ExecNode
  read immutable ExecutionSnapshot
  calculate output
  return NodeOutput
  do not mutate global context

Merge:
  append output columns
  collect warnings
  update resolver when needed
  update stats
  release dependent nodes
```

---

## Implementation Principle

Avoid this pattern:

```rust
Arc<Mutex<ExecutionContext>>
```

for the entire node execution lifecycle.

Prefer this architecture:

```text
Build read-only snapshot
        ↓
Execute node without mutating global state
        ↓
Return NodeOutput
        ↓
Merge output in one controlled mutation phase
```

This gives us a safe transition path from the current serial executor to a future parallel DAG executor without changing calculation semantics.
