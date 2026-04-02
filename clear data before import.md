# BLOX clear-data / clear-before-import — bug descriptions


---

## 1. Preview before import does not clearly show the right data (clear-before-import)

### Scope note
This is a **UX / completeness of preview** issue, not “the UI shows nothing about clearing” — on `BLOX-2001-clear-data`, clearing **is** reflected in the summary line when the API supplies it; the gap is **final-state clarity** and **alignment between the table and the clear+import story**.

The behaviour below is **still largely true** on that branch, with one important nuance.

### What is already implemented

- The **mapping preview** screen **does** surface clear-before-import when the API returns it.
- The UI shows a line like **“N values will be cleared”**, plus optional **`clear_scope_description`**, **appended** to the existing **“values will be updated from … rows”** text.
- Implementation reference: `traction-react/src/pages/ModelOverviewPage/Import/MappingDataSteps/MappedData.tsx` — the block that reads `mappedFileData.preview_run_result.summary`, including **`estimated_clear_count`** and **`clear_scope_description`**.

### What is still missing (why the issue remains)

- The **table under the tabs** is still driven by **`mappedFileData.response.indicator_data[...].actual_data`** — i.e. the **parsed file** / **“what we are loading”** view from **`calculate_actual_values(save_data=False)`**.
- There is **no separate grid** for **“model after clear, then after apply”**.
- There is **no single narrative** that ties **clear scope → then new values** to **what each cell will become** after the run.

### User-visible problem (one sentence)

Users see **incoming file data** in the grid plus **separate summary numbers** (updates, rows, skips, clears); that mix does **not** answer “what will the model look like after clear and import?” in one clear story — so the preview step can still feel **wrong or hard to read** even though **clear counts and scope text** are shown.

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
