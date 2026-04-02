# BLOX clear-data / clear-before-import — bug descriptions

## End-to-end context (short)

- **Frontend:** You step through the import wizard; each screen is chosen from `DataStepsForm` based on choices (data vs forecast, single vs multiple periods, one vs many indicators, time in rows vs columns, etc.). The top stepper shows one tick per “step” and highlights the active index.
- **Backend:** Uploaded sheet data is loaded into Polars, reshaped to a normal “indicator + time + value (+ dimensions)” shape, then validated. **Preview** calls the same calculation as import but does not write to the database; it can attach **clear-before-import** stats (how many existing values would be cleared) when that option is enabled.
- **Why that matters:** Bugs can come from (a) the UI showing the wrong step or summary, (b) preview not matching what will really happen, or (c) the parser being strict about blank cells and layout.

---

## 1. Preview before import does not clearly show the right data (with clear-before-import)

**What you see:** On the step where you review what will be imported *after* choosing to clear existing data, the preview (table and/or the “X values will be updated / Y will be cleared” style summary) does not match what you expect: numbers, rows, or messaging feel wrong or hard to read.

**What is going wrong (conceptually):** Preview is meant to simulate the import without saving. With **clear before import**, two things happen in the product story: existing values in scope are removed, then new values from the file are applied. The UI may be mixing (i) raw file rows, (ii) rows after the engine drops or fills blanks, and (iii) counts of cells that will be cleared—so the **story** “what the model will look like after this run” is not aligned with what is on screen.

**In one sentence:** The preview step does not yet present a single, unambiguous picture of “file data + clear scope + final effect” for users.

---

## 2. Stepper ticks do not match the real wizard steps

**What you see:** The number of circles in the stepper, or which circle is “active,” does not line up with the step you are actually on; some ticks seem tied to the wrong step number.

**What is going wrong (conceptually):** The total number of steps changes depending on many options (single vs multiple period, one vs many indicators, time in rows vs columns, etc.). That count is computed as several separate updates. If those updates disagree or fire in an awkward order, the **length** of the stepper can disagree with the **real** sequence of screens driven by the same step index. Separately, the UI label “Step N” and the highlighted tick both use one shared index—so any mismatch in “how many steps exist” or “which screen belongs to which index” shows up exactly as wrong ticks.

**In one sentence:** The dynamic step list and the screen routing can get out of sync, so the progress indicator lies about where you are in the flow.

---

## 3. Auto-mapping indicators fails when time periods come from one row (wide layout)

**What you see:** With a wide P&amp;L-style sheet—**one row** of period labels and **rows** for each line—the automatic map from sheet names to model indicators is wrong or incomplete.

**What is going wrong:** Auto-mapping uses **distinct values in the column you chose for indicator names**. Rows that are not real indicators (titles, blanks, section labels) and the **single row of month headers** interact so the engine sees noisy labels next to clean account names.

**Example sheet — cells that drive issue 3**

| row (indicator / label column) | _1 | _2 | _3 | _4 | _5 | _6 | Issue 3 (what matters) |
|----------------------------------|----|----|----|----|----|----|-------------------------|
| profit and loss | _1 | _2 | _3 | _4 | _5 | _6 | **Noise** — not a model indicator; confuses name-based auto-map |
| neural voice ltd | | | | | | | **Noise** — blank cells; may appear as empty/odd distinct value |
| account | dec 2023 | jan 2024 | feb 2024 | mar 2024 | apr 2024 | may 2024 | **Time-in-one-row** — periods live here, not in the indicator column |
| turnover | | | | | | | **Noise** — label row, often empty |
| interest income | 0 | 0 | 0 | 0 | 0 | 0 | **Real indicator row** — should map cleanly |
| other revenue | 0 | 0 | 0 | 0.02 | 0 | 0 | **Real indicator row** |
| sales | 0 | 0 | 0 | 0 | 0 | 0 | **Real indicator row** |

**Where issue 3 hits:** Mostly the **first column** (mixed titles + blanks + real line items) plus the **row that holds all period names** (`account` → `dec 2023` …). Auto-map sees too many non-indicator strings in the “names” column and/or the layout does not match what the multi-period + column-time path expects.

---

## 4. Import sometimes fails when the sheet has null or empty entries

**What you see:** Blank rows or empty label cells cause preview/import to error or behave badly, even when numeric rows are fine.

**What is going wrong:** The pipeline often assumes non-null names/values in key columns or **drops / chokes on rows with nulls**. Decorative or empty label rows are not treated as harmless skips.

**Example sheet — cells that drive issue 4**

| row (indicator / label column) | _1 | _2 | _3 | _4 | _5 | _6 | Issue 4 (what matters) |
|----------------------------------|----|----|----|----|----|----|-------------------------|
| profit and loss | _1 | _2 | _3 | _4 | _5 | _6 | Usually filled — less often the trigger |
| neural voice ltd | | | | | | | **Problem area** — entire row empty / null labels |
| account | dec 2023 | jan 2024 | feb 2024 | mar 2024 | apr 2024 | may 2024 | Header row for time — typically OK |
| turnover | | | | | | | **Problem area** — empty label row (null / blank key field) |
| interest income | 0 | 0 | 0 | 0 | 0 | 0 | Data present — OK |
| other revenue | 0 | 0 | 0 | 0.02 | 0 | 0 | Data present — OK |
| sales | 0 | 0 | 0 | 0 | 0 | 0 | Data present — OK |

**Where issue 4 hits:** Specifically rows like **`neural voice ltd`** and **`turnover`** where the **label column (and often the whole row)** is empty or null—those rows are the ones that tend to break parsing or row handling even though the numeric indicator rows below are valid.
