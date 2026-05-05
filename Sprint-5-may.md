# Sprint Demo Presenter Notes

## Slide 6 — BLOX-2137: Dataflow Stream Crashing Midway

### Issue

The dataflow stream was crashing midway while processing a large file of around **17k rows**.  
Because of this, the stream was stopping before completion and the status was not getting updated properly.

### Cause

The worker was running out of memory and getting killed during execution.

### Fix

The production EBS instance was upgraded from `t2.small` to `t2.medium` so it can handle more load.

### Presenter Script

For this issue, the dataflow stream was stopping midway while processing a large file, and the status was not updating.  
The root cause was low memory, where the worker was getting killed during execution.  
We fixed this by upgrading the production instance to handle more load, so larger streams can complete more reliably.

---

## Slide 7 — BLOX-2127: Dashboard Rolling Sum

### Issue

The dashboard only supported a **12-month rolling sum**.  
This was limiting for users who wanted shorter summaries or totals across the selected timeframe.

### Fix

We added support for more rolling sum options:

- `ROLLING_3` — aggregate last 3 months
- `ROLLING_4` — aggregate last 4 months
- `ROLLING_6` — aggregate last 6 months
- `DISPLAY_TIMESCALE` — aggregate over the selected displayed timeframe

### Presenter Script

Earlier, dashboards only supported a 12-month rolling sum.  
We extended this so users can now view 3-month, 4-month, and 6-month rolling summaries.  
We also added an all-time option, which summarizes values across the selected displayed timeframe.

---

## Slide 8 — BLOX-2129: Dataflow Scheduler Token Invalidation

### Issue

Scheduled dataflow runs were failing because the Blox token refresh was not working properly in some cases.

### Cause

The refresh token was sometimes not being stored correctly.  
Because of this, authentication failed during scheduled stream execution.

### Fix

We fixed the token refresh handling so scheduled streams can authenticate correctly and continue running.

### Presenter Script

This issue was related to scheduled dataflow runs failing due to authentication errors.  
The root cause was that the refresh token was not always being stored correctly.  
We fixed the token handling so scheduled streams can refresh authentication properly and run without repeated token failures.

---

## Slide 9 — BLOX-1975: Data Connectors — Slack Notification Service

### Issue

There was no proper Slack notification flow for data connector stream executions and failures.

### Fix

We integrated Slack notifications for stream execution events, including:

- Execution started
- Execution success
- Execution failed
- Fatal error alerts

The notification can include useful details such as:

- Stream name
- Execution ID
- Timestamp
- Status
- Error details

### Presenter Script

For this feature, we added Slack notifications for data connector streams.  
Now the team can receive updates when a stream starts, succeeds, or fails.  
This helps us monitor both manual and scheduled stream runs more easily, especially when there are execution errors.

---

## Slide 10 — BLOX-2131: Builder and Planner Values Mismatch in Thrive

### Issue

In the Thrive model, values were different between **Builder mode** and **Planner mode**.  
In some cases, numbers were visible in Builder mode but not visible in Planner mode.

### Cause

Some recent Omni-Calc changes affected existing functionality and caused incorrect responses for certain blocks.

### Fix

We resolved the mismatch and restored the original working logic where the new changes were breaking existing behavior.

### Presenter Script

This issue was about value mismatch between Builder and Planner mode for Thrive.  
Some numbers were showing correctly in Builder but not in Planner.  
We found that recent Omni-Calc changes affected existing block behavior, so we fixed the mismatch and restored the working logic to make both modes consistent again.

---

## Slide 11 — BLOX-2116: Access Control Architecture Mapping

### Issue

Before implementing the new access control system, we needed to understand how it fits into the current Blox backend architecture.

### Scope

We analyzed the proposed access control model with three main layers:

- Organization permissions
- Model access groups
- Dimension-level data access

We mapped these concepts to the current backend structures, including:

- Users
- Organizations
- Models
- Permissions
- Dimensions
- Dimension items

### Outcome

We identified:

- What existing components can be reused
- What gaps are present in the current system
- Where more centralized and granular permission handling is needed
- How feasible the proposed access control model is before implementation

### Presenter Script

This was a spike task for the new access control system.  
We reviewed how organization permissions, model groups, and dimension-level access can fit into the current backend.  
The goal was to understand what existing structures we can reuse and what gaps need to be solved before implementation.

---

## Slide 23 — BLOX-2121: Make Rust Default for All Users

### Issue

Some models were still depending on the legacy Python flow unless the Rust running version was explicitly configured.

### Fix

We made Rust version `5` the default running version across the backend.

### What Changed

Rust is now used by default for:

- New models
- Copied models
- Block output APIs
- Data value APIs

If the config is missing or the lookup fails, the system now defaults to Rust instead of falling back to the older Python flow.

### Presenter Script

For this task, we made Rust the default execution engine for all users.  
Earlier, some models could still fall back to the older Python flow if the running version was missing.  
Now new models, copied models, block outputs, and data values use Rust version 5 by default, which makes the Rust flow consistent across the app.
