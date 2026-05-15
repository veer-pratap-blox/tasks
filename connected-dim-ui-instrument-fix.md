# Dashboard Dimension Resolution Fix

## Best Fix

Do not rely on `dimension_name` being stored in BI metadata. Resolve it consistently from `dashboardBlocks`.

### Recommended frontend fix

Add a shared helper in `DashboardSliceV2.ts` or a dashboard utility:

```ts
resolveIndicatorDimension(blockDetails, blockId, indicatorId, dimensionId)
```

It should:

- Compare IDs using `Number(...)`.
- Look inside `indicator_dimensions`.
- Support connected dimensions because `dashboardBlocks` already merges native and connected dimensions.
- Return `indicator_dimension_name`.

Use that helper in:

- `LineChart.tsx`
- `BarChart.tsx`
- `Filters.tsx`
- `Variance.tsx` / variance path, if applicable
- Any dashboard render path that reads `indicator.dimension_name`

### Optional Redux enrichment

Optionally enrich loaded data in Redux:

- When `fetchDashboardMetadata` succeeds, add `dimension_name` to each `instrument_indicator`.
- When `fetchAllDataValues` succeeds, add `dimension_name` to each `data[*].indicator`.

This makes first page render, chart render, filter render, and edit modal all use the same resolved value.

## Minimal Fix

At minimum, change strict comparisons like this:

```ts
dim.indicator_dimension_id === indicator.dimension_id
```

to type-normalized comparisons:

```ts
Number(dim.indicator_dimension_id) === Number(indicator.dimension_id)
```

Specifically in:

- `traction-react/src/pages/ModelOverviewPage/Dashboard-v2/chart/LineChart.tsx`
- `traction-react/src/pages/ModelOverviewPage/Dashboard-v2/chart/BarChart.tsx`

This likely fixes the visible `undefined` in charts for this case.

## Better Fix

The better fix is to centralize dimension resolution so this does not keep returning in different dashboard components:

```ts
const foundDimension = resolveIndicatorDimension({
  blockDetails,
  blockId: indicator.block_id,
  indicatorId: indicator.indicator_id,
  dimensionId: indicator.dimension_id,
});
```

Then use:

```ts
const dimensionName = foundDimension?.indicator_dimension_name || indicator?.dimension_name;
```
