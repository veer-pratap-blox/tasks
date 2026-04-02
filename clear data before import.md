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

## 3. Time periods across columns are not auto-mapped to Blox periods

### What you see

When the file stores **each period in its own column** (wide layout), the wizard asks you to map **file columns** to **periods in Blox**. File columns are identified by internal names such as **`_1`**, **`_2`**, **`_3`**, …

**Expected:** If the sheet has a **row (or header row) where each column’s cell holds the real period label** (e.g. month and year text in the cells under `_1`, `_2`, `_3`, …), the product should use those labels to **suggest or fill** the mapping from each **`_n`** column to the correct Blox time period.

**Actual:** Those human-readable period strings are **not** used to auto-match Blox periods. You typically map **`_1` / `_2` / `_3` / …** to periods **manually**, one row at a time, which is slow and easy to get wrong.

### Example layout (period labels live in one row; amounts in rows below)

Columns are shown here as **`_1` … `_6`** to match how the app refers to file columns. One row carries **calendar labels** per column; lower rows are **values** for those periods.

| row (indicator / label column) | _1 | _2 | _3 | _4 | _5 | _6 | Role |
|----------------------------------|----|----|----|----|----|----|------|
| profit and loss | _1 | _2 | _3 | _4 | _5 | _6 | Layout / header noise — not the period-definition row. |
| neural voice ltd | | | | | | | Blank or non-period row. |
| account | dec 2023 | jan 2024 | feb 2024 | mar 2024 | apr 2024 | may 2024 | **Period row:** cell under each `_n` is the **period text** for that column; this is what should drive auto-mapping to Blox. |
| turnover | | | | | | | Label row; often empty. |
| interest income | 0 | 0 | 0 | 0 | 0 | 0 | Numeric data per period column. |
| other revenue | 0 | 0 | 0 | 0.02 | 0 | 0 | Numeric data per period column. |
| sales | 0 | 0 | 0 | 0 | 0 | 0 | Numeric data per period column. |

### What is going wrong (plain language)

The **mapping step only exposes generic column ids** (`_1`, `_2`, `_3`, …) on the file side. It does **not** infer Blox periods from the **period label row** (or equivalent header cells) that sits above the numbers. So users must **manually** align each **`_n`** with the right period in Blox, even when the sheet already spells out which month each column is.

### Why it matters

- Repeated manual work for every wide file.
- Higher risk of mapping a column to the **wrong** Blox period when matching is done only by column index, not by the visible date/month text in the file.

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
