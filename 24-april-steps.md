### 1. Move the latest `development` commit to a separate branch

- On the `development` branch, remove the latest commit from the branch history.
- Create a new branch for that work.
- Move the latest commit to the new branch, since it is related to the Notes App issue that was added.

### 2. Investigate the Blox block plan issue on `main`

- Switch to the `main` branch.
- Investigate the issue in the following Blox block plan using the browser:
  - https://app.blox.so/model/15164/block/41811/plan

#### Problem context

- Updating input values from the **Show Input Panel** to the Blox UI table fails.
- This exact model/block is not available in localhost, but localhost is running the same code as production.
- Some models are missing only at the database level, so the investigation should rely on production for the original case and localhost for similar reproducible cases.
- Ignore frontend warnings during testing.

#### Specific error to investigate

- In similar blocks, especially where **multiple dimensions are enabled**, updating values from the **Show Input Panel** causes the following error:
  - `'rename' on column: '_39415' is invalid`
- Failure schema:
  - `_39424: String`
  - `_39419: String`
  - `39415: String`
  - `value: Float64`
- The error occurs during the **PROJECT** operation in the resolved query plan.

#### Tasks

- Open and analyze this production block plan in the browser:
  - https://app.blox.so/model/15164/block/41811/plan
- Reproduce the issue by updating input indicator values from the **Show Input Panel** into the Blox table.
- Inspect the **Network** tab and determine exactly where and why the failure occurs.
- Since this exact model/block does not exist in localhost, search localhost for similar model/block plans that exhibit the same behavior.
- Specifically test cases where **multiple dimensions are enabled**.
- Find all similar local model/block plan pages that match this pattern and share their links:
  - `http://localhost:3000/model/{model_id}/block/{block_id}/plan`
- Focus only on investigation and analysis.
- Do **not** implement a fix.

#### Deliverable

Prepare a complete Jira-style issue write-up that includes:

- Problem statement
- Steps to reproduce
- Expected behavior
- Actual behavior
- Root cause analysis
- Additional observations/context
- Acceptance criteria

- Do **not** fix the issue.
- Only investigate, test, and document the findings.

### 3. Review the fix branch and prepare the Jira issue

- Switch to the branch:
  - `fix/block-outputs-v2-nested-json-params`
- Use Codex to rewrite the issue description in a clearer and more professional way.
- Use Codex to verify whether the issue is fixed correctly in the current branch.
- Check whether the fix has been fully applied or if there are any missing gaps.
- Confirm that the fix does not break any existing functionality.
- Create the Jira issue with the refined description and validation findings.

### 4. Implement the dropdown APIs

- Implement the required dropdown APIs.
- Ensure the APIs are integrated correctly with the relevant flow and data handling.
- Validate that the dropdown API implementation works as expected and does not break any existing functionality.
- Document any important assumptions, dependencies, or edge cases identified during implementation.
