# FINAL ISSUE 1

## Issue Type

Performance / Observability / Tech Debt

---

## Title

Add Omni-Calc Execution Profiling, Benchmark Baseline, and Debug Hot-Path Cleanup

---

## Source Issues Merged

```text
Source Issue 16 - Add Execution Profiling and Benchmarks for Scheduler, Snapshot, Merge, and Resolver
```

Additional scope added from branch code analysis:

```text
Debug hot-path cleanup
Benchmark result reporting
Performance regression tracking
Measurement for preload, resolver, formula, actuals, joins, RecordBatch, clone-heavy paths, and debug overhead
```

---

## Summary

Add a reliable benchmark and profiling foundation for the Rust Omni-Calc engine before implementing scheduler, snapshot, merge, resolver, clone-reduction, or Rayon parallelism changes.

This issue should also clean up or properly gate hardcoded debug logs and expensive diagnostic collection inside hot execution paths.

The goal is to make performance work measurable and to ensure normal production execution is not slowed down by debug-only logging, sample collection, vector cloning, or diagnostic formatting.

This issue should answer:

```text
What is slow today?
Which execution phase is slow?
How much did a later optimization improve runtime?
Did memory usage increase?
Did Rayon actually help or only add overhead?
Are debug logs distorting production performance?
```

---

## Background / Context

The current Omni-Calc Rust executor processes Python-provided `calc_steps` sequentially.

Execution currently includes major runtime phases such as:

```text
metadata preload
connected dimension preload
input step processing
property loading
calculation step processing
sequential step processing
formula evaluator setup
formula evaluation
cross-object resolver updates
join path creation
lookup aggregation
actuals / forecast handling
RecordBatch materialization
final result build
warning collection
debug / tracing diagnostics
clone-heavy state movement
```

The branch code also contains debug/logging work inside hot paths, including:

```text
warn! calls inside executor startup
warn! calls inside connected dimension preload loops
warn! calls inside calculation step loops
debug-only sample collection
column-name collection for logs
sample values / first-N values collection
hardcoded node/block-specific diagnostics
vector sums/counts used only for logs
```

These diagnostics are useful while debugging but should not run in normal execution unless explicitly enabled.

---

## Problem Statement

Current risks:

```text
1. No consistent benchmark baseline for Omni-Calc execution.
2. No clear phase-level runtime breakdown.
3. No benchmark for graph construction / future scheduler work.
4. No benchmark for metadata preload.
5. No benchmark for bulk preload vs fallback PyO3 preload.
6. No benchmark for formula evaluation alone.
7. No benchmark for FormulaEvaluator setup / clone-heavy context setup.
8. No benchmark for calculation dependency-resolution sub-phases.
9. No benchmark for resolver update/materialization.
10. No benchmark for cross-object join alignment.
11. No benchmark for lookup aggregation.
12. No benchmark for final RecordBatch creation.
13. No benchmark for connected dimension preload.
14. No benchmark for actuals row-key construction.
15. No benchmark for forecast membership checks.
16. No benchmark for column lookup / duplicate-check cost.
17. No benchmark for warning collection / warning cloning cost.
18. Debug logs and diagnostics may allocate in hot paths.
19. Hardcoded debug paths can distort production performance.
20. Future refactors can accidentally regress performance without being caught.
```

---

## Why This Needs To Be Fixed First

This issue should be completed before scheduler, clone-reduction, resolver, or Rayon work because later performance changes need a trustworthy baseline.

Without this issue:

```text
we cannot prove whether an optimization helped
we cannot compare serial vs Kahn vs Rayon execution
we cannot identify whether bottlenecks are in preload, formula eval, resolver, joins, actuals, or output materialization
we may accidentally optimize the wrong path
debug logs may make benchmarks misleading
hardcoded logs may make production slower
```

This issue is not primarily about optimizing Omni-Calc yet.

It is about:

```text
measuring correctly
cleaning hot-path diagnostics
creating reliable before/after performance evidence
```

---

## Scope

Add benchmark coverage for the following major phases:

```text
1. Full Omni-Calc execution
2. Current serial calc_steps execution
3. Future single-threaded Kahn scheduler
4. Future Rayon ready-node execution
5. Metadata preload
6. Input indicator processing
7. Property loading from PreloadedMetadata
8. Formula evaluation
9. FormulaEvaluator setup
10. Calculation step processing
11. Sequential step processing
12. Resolver update/materialization
13. Cross-object join path creation
14. Lookup map aggregation
15. Final RecordBatch materialization
16. Connected dimension preload
17. Actuals / forecast handling
18. Clone-heavy paths
19. Memory allocation / peak memory where practical
```

Add detailed benchmark coverage for specific hot sub-paths:

```text
20. PreloadedMetadata bulk preload vs fallback PyO3 preload path
21. collect_metadata_needs(plan) cost
22. preload extraction/parsing cost
23. extract_dimension_items_bulk cost
24. extract_property_rows cost
25. Calculation dependency-resolution sub-phases:
    - connected dimension collection for cross-object joins
    - cross-object dependency resolution
    - dimension property column collection
    - connected dimension property collection
26. Formula parsing / parsed_formula AST setup cost
27. PropertyFilterContext creation cost
28. time_values clone/setup cost
29. Actuals row-key construction:
    - build_dimension_key
    - build_entity_key
30. Forecast membership checks:
    - forecast_indices.contains
    - future forecast mask/bitset checks
31. Resolver RecordBatch extraction helpers:
    - get_indicator_values
    - get_dimension_columns
    - get_property_column
    - extract_string_columns_from_batch
    - extract_connected_dim_columns_from_batch
32. Warning collection and warning clone cost
33. HashMap / column lookup cost across:
    - state.number_columns
    - state.string_columns
    - state.connected_dim_columns
34. Duplicate-check cost during column merge/materialization
35. Debug/tracing overhead with logging disabled vs enabled
```

---

## Debug / Hot-Path Cleanup Scope

Clean up or gate the following:

```text
1. Remove or gate hardcoded block-specific debug logs.
2. Remove or gate hardcoded node-specific debug logs.
3. Avoid always-on warn!/debug! diagnostics in hot loops.
4. Avoid collecting sample vectors unless tracing is enabled.
5. Avoid collecting column names unless tracing is enabled.
6. Avoid building sample key/value strings unless tracing is enabled.
7. Avoid clone-heavy diagnostics in normal execution.
8. Avoid expensive format! calls when logs are disabled.
9. Avoid collecting first-N sample paths unless trace/debug is enabled.
10. Avoid collecting available NodeMap keys unless trace/debug is enabled.
11. Avoid collecting available filter keys unless trace/debug is enabled.
12. Avoid summing large vectors only for logs unless trace/debug is enabled.
13. Avoid building debug-only Vec<String>, Vec<&str>, or sample arrays in normal execution.
14. Measure logging overhead with tracing disabled vs enabled.
```

Required logging rule:

```text
If debug/tracing is disabled, diagnostic collection should have near-zero runtime and allocation overhead.
```

Recommended implementation pattern:

```rust
if tracing::enabled!(tracing::Level::DEBUG) {
    let sample_values = values.iter().take(10).copied().collect::<Vec<_>>();

    debug!(
        node_id = %node_id,
        sample_values = ?sample_values,
        "Debug sample values"
    );
}
```

Avoid this pattern in hot paths:

```rust
let sample_values = values.iter().take(10).copied().collect::<Vec<_>>();

debug!(
    sample_values = ?sample_values,
    "Debug sample values"
);
```

because the sample vector is created even when debug logging is disabled.

---

## Proposed Change

Add a benchmark harness or internal performance mode.

Possible implementation options:

```text
Rust Criterion benchmarks
cargo bench benchmarks
internal benchmark command
test-only benchmark utilities
feature-gated benchmark mode
structured timing output from executor
```

Recommended benchmark structure:

```text
benches/
  omni_calc_full_execution.rs
  omni_calc_preload.rs
  omni_calc_graph_build.rs
  omni_calc_input_steps.rs
  omni_calc_formula_eval.rs
  omni_calc_resolver.rs
  omni_calc_join_alignment.rs
  omni_calc_recordbatch.rs
  omni_calc_actuals.rs
  omni_calc_scheduler.rs
```

Recommended performance instrumentation:

```text
PerfTimer / PhaseTimer helper
ExecutionTiming struct
BenchmarkResult struct
optional JSON output
optional CSV output
```

Example timing structure:

```rust
struct ExecutionTiming {
    total_runtime_ms: f64,
    preload_runtime_ms: f64,
    connected_dimension_preload_ms: f64,
    input_step_ms: f64,
    property_step_ms: f64,
    calculation_step_ms: f64,
    sequential_step_ms: f64,
    formula_eval_ms: f64,
    formula_setup_ms: f64,
    resolver_update_ms: f64,
    recordbatch_materialization_ms: f64,
    join_path_creation_ms: f64,
    lookup_aggregation_ms: f64,
    actuals_handling_ms: f64,
    clone_hotspot_ms: f64,
    debug_logging_overhead_ms: f64,
}
```

---

## Recommended Metrics

High-level metrics:

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

Detailed metrics:

```text
preload_bulk_ms
preload_fallback_ms
metadata_needs_ms
property_extract_ms
dimension_extract_ms
calc_dependency_resolution_ms
cross_object_resolution_ms
dimension_property_collection_ms
connected_dim_collection_ms
formula_parse_or_ast_setup_ms
property_filter_context_ms
time_values_clone_ms
actuals_row_key_ms
forecast_membership_ms
resolver_batch_extract_ms
warning_collection_ms
column_lookup_ms
duplicate_check_ms
debug_logging_overhead_ms
```

Memory/allocation-oriented metrics where practical:

```text
estimated_allocated_bytes
peak_memory_mb
number_column_clone_count
string_column_clone_count
recordbatch_clone_count
formula_context_clone_count
warning_clone_count
debug_vector_allocation_count
```

---

## Benchmark Scenarios

Add benchmark scenarios for:

```text
small model
medium model
large wide model
large row-count model
many-block model
cross-object-heavy model
actuals-heavy model
sequential-heavy model
property-heavy model
connected-dimension-heavy model
formula-heavy model
lookup-aggregation-heavy model
RecordBatch-heavy output model
debug-disabled run
debug-enabled run
```

Each benchmark result should record model shape:

```text
block_count
node_count
row_count_per_block
total_row_count
dimension_count
indicator_count
property_node_count
cross_object_reference_count
sequential_node_count
input_node_count
calculation_node_count
```

---

## Benchmark vs Logs Explanation

Benchmarks and logs solve different problems.

Benchmarks are better for performance measurement because:

```text
1. Benchmarks run intentionally, not during normal user execution.
2. Benchmarks can repeat the same workload many times.
3. Benchmarks give stable before/after numbers.
4. Benchmarks can compare model shapes.
5. Benchmarks can measure phase-level timings.
6. Benchmarks can be used for regression checks.
7. Benchmarks do not need to print/log every internal detail.
```

Logs are useful for debugging correctness problems, but logs are not a good replacement for benchmarks because:

```text
1. Logs can add runtime overhead.
2. Logs can allocate strings/vectors.
3. Logs can clone values for diagnostics.
4. Logs can distort the exact performance we are trying to measure.
5. Logs are noisy and not stable enough for performance regression tracking.
6. Always-on logs in loops can become a bottleneck.
```

Important clarification:

```text
Benchmarks do not make production faster by themselves.
Benchmarks also have overhead while they are running.
But if benchmarks are only run in cargo bench / benchmark mode, they add no overhead to normal production execution.
```

Correct principle:

```text
Use benchmarks to measure performance.
Use gated logs/tracing to debug specific issues.
Do not use always-on logs as performance measurement.
```

---

## Suggested Flags / Configuration

Add or support flags such as:

```text
CALC_DEBUG=false by default
CALC_PERF_TRACE=false by default
CALC_BENCH_MODE=true only in benchmark runs
CALC_LOG_HOT_PATH_DETAILS=false by default
```

Expected behavior:

```text
normal execution should not collect expensive debug data
benchmark mode can collect structured phase timings
debug mode can collect detailed diagnostics intentionally
```

---

## Expected Impact

```text
1. Makes future optimization measurable.
2. Prevents performance regressions.
3. Helps decide where Rayon is actually useful.
4. Helps identify clone-heavy and allocation-heavy paths.
5. Helps identify whether the bottleneck is execution, preload, resolver, joins, actuals, or output materialization.
6. Provides safe baseline before scheduler changes.
7. Makes it easier to prove improvements from later final issues.
8. Removes misleading debug overhead from production performance.
9. Makes benchmark results more trustworthy by removing hardcoded log noise.
```

---

## Acceptance Criteria

```text
1. Benchmark harness exists.
2. At least small, medium, and large model benchmarks exist.
3. Benchmarks can compare serial vs optimized paths.
4. Benchmarks can compare debug-disabled vs debug-enabled execution.
5. Phase-level timing is available.
6. Detailed timing is available for preload, resolver, formula, actuals, join, and RecordBatch paths.
7. PreloadedMetadata bulk vs fallback PyO3 preload timing is available.
8. Calculation dependency-resolution timing is available.
9. Actuals row-key and forecast membership timing is available.
10. Resolver RecordBatch extraction timing is available.
11. Column lookup / duplicate-check timing is available.
12. Warning collection / warning clone timing is available.
13. Debug/tracing overhead timing is available.
14. Debug/hot-path logs do not allocate unless enabled.
15. Hardcoded block/node debug logs are removed or gated.
16. Always-on warn!/debug! diagnostics in hot loops are removed or downgraded/gated.
17. Expensive diagnostic collection is guarded by tracing enabled checks.
18. Baseline numbers are documented before other optimization work begins.
19. Performance regression checks can be added to CI or run manually.
20. Benchmark results can be used by later issues to prove improvement.
```

---

## Testing Notes

Add tests / benchmark cases for:

```text
full serial execution
future Kahn scheduler execution
future Rayon execution
large formula evaluation
formula evaluator setup
wide block column lookup
duplicate column check
large cross-object join
lookup aggregation
RecordBatch output
connected dimension preload
PreloadedMetadata bulk preload
PreloadedMetadata fallback preload
property extraction
actuals-heavy block
actuals row-key construction
forecast membership check
sequential-heavy block
resolver batch extraction
warning collection
debug disabled path
debug enabled path
diagnostic collection disabled path
diagnostic collection enabled path
```

---

## Out of Scope

```text
Changing calculation semantics
Adding Rayon ready-node execution
Changing output format
Changing Python DAG manager behavior
Refactoring scheduler
Changing resolver logic
Optimizing data structures
Reducing clones
Changing PreloadedMetadata shape
Changing formula evaluation behavior
Changing actuals behavior
Changing join semantics
```

This issue is measurement and cleanup only.

Implementation changes for optimization should happen in later final issues.

---

## Priority

Highest

---

## Dependencies

```text
None
```

This issue should be completed before:

```text
Final Issue 2 - Data Structure / Clone Reduction / Shared References / Typed IDs
Final Issue 3 - Scheduler Foundation / Worker-Safe PreloadedMetadata
Final Issue 4 - Actuals / Forecast / Row Metadata Optimization
Final Issue 5 - Cross-Object Join Optimization
Final Issue 6 - Pre/Post Processing Parallelism
Final Issue 7 - Rayon Ready-Layer Execution
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
phase-timing
hot-path-cleanup
memory-profiling
```

---

## Components

```text
Omni-Calc
Rust Engine
Benchmarking
Performance
Debugging
Observability
Executor
Formula Evaluation
Preload
Resolver
RecordBatch Materialization
Scheduler
```

---

## Final Notes

This issue is the required first step for the Omni-Calc performance roadmap.

It should answer:

```text
Where is time currently spent?
Where are allocations happening?
Which debug paths distort runtime?
Which phase should be optimized first?
Which later issue produced measurable improvement?
```

Benchmarks should be the source of truth for performance.

Logs should be used only for targeted debugging and should be gated so normal execution does not pay for diagnostic collection.
