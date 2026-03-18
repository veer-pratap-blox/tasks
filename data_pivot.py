import json
import traceback

import polars as pl
from calc_engine.data_agreggator import TOTAL_OPTIONS, Agg_param, DataAggregator
from calc_engine.util import apply_filter_on_indicators
from lib import time
from lib.time import get_months_for_given_string


## Class to calculate the full data for a block by processing inputs, merging everything into a dataframe and applying calculations
class DataPivot:

    def __init__(
        self,
        raw_data_df,
        dimensions,
        fy_start_month,
        indicators=None,
        query_params=None,
        all_dimension_scenario_item_map=None,
    ):
        self.raw_data_df = raw_data_df
        # temp_indicators - temporaily added to get test working by mimicing previous behaviour
        if query_params:
            temp_indicators = indicators
        else:
            temp_indicators = None
        self.indexed_columns = []

        # If no query provided set a default query
        if query_params is None:
            query_params = {"rows": ["indicators"], "columns": ["time"]}
        if all_dimension_scenario_item_map:
            self.all_dimension_scenario_item_map = all_dimension_scenario_item_map
        # indicator_cols = [col for col in list(raw_data_df.columns) if col.startswith('ind')]
        # dimension_cols = [col for col in list(raw_data_df.columns) if col.startswith('_')]
        indicator_cols = [col for col in raw_data_df.columns if col.startswith("ind")]
        dimension_cols = [col for col in raw_data_df.columns if col.startswith("_")]

        # Parse query params and create a list we can use for filtering, aggregations and pivots
        query_dims = self.__parse_query_params(query_params, dimensions)

        # Setup indicator name lookup
        indicator_lookup = self.__create_indicator_lookup(
            temp_indicators, indicator_cols
        )
        # Format dimensions columns of dataframe as categories - helps reduce memory usage and with sorting
        categorical_df = self.__format_df_with_categories(
            raw_data_df, dimension_cols, dimensions, query_dims
        )

        # Apply filters for indicators
        filter_dims = [dim for dim in query_dims if dim["query_location"] == "filters"]
        filtered_dims_df = self.__apply_filters_on_dims(categorical_df, filter_dims)

        # if filtered dataframe is of height 0, then change the values of categorical_df to 0
        if filtered_dims_df.is_empty():
            filtered_dims_df = categorical_df.with_columns(
                [
                    (
                        pl.lit(0).cast(pl.Float64).alias(col)
                        if col.startswith("ind")
                        else pl.col(col)
                    )
                    for col in categorical_df.columns
                ]
            )

        # Aggregate data
        agg_params = self.__create_agg_params_list(query_dims)
        data_aggregator = DataAggregator(
            raw_data_df=filtered_dims_df,
            indicators=indicators,
            agg_params=agg_params,
            fy_start_month=fy_start_month,
        )
        aggregate_df = data_aggregator.df

        # Apply filters for indicators
        filtered_df = self.__apply_filters_on_indicators(
            aggregate_df, filter_dims, indicator_lookup
        )

        # Format the data values to something more sensible
        formatted_df = self.__format_data_values(filtered_df)

        # Pivot data & finalise df (replace columns)
        dim_name_lookup = self.__dimension_name_lookup(dimensions, dimension_cols)

        pivoted_df = self.__pivot_data_values(
            formatted_df, query_dims, indicator_lookup, dim_name_lookup, indicators
        )
        self.time_granularity = data_aggregator.time_granularity
        self.pivoted_df = pivoted_df

    def generated_connected_dim_mapping(self, dim):
        dim_item_to_connected_dim = {}
        for item in dim.items:
            for item_prop in item.item_properties:
                if item_prop.property_id == dim.group_property_id:
                    dim_item_to_connected_dim[item.name] = item_prop.value
        return dim_item_to_connected_dim

        # =====  helper for normalizing filter values =====

    def __normalize_filter_items(self, filter_val, dim, block_dims_item_map):
        if dim["name"] == "Time":
            if filter_val != "all":
                return get_months_for_given_string(
                    filter_val, block_dims_item_map.get(dim["id"], [])
                )
            return block_dims_item_map.get(dim["id"], [])

        if isinstance(filter_val, list):
            return filter_val

        return [filter_val]

    # =====  helper for normalizing filter values =====

    # =====  helper for resolving filter dimension by name or id =====
    def __resolve_filter_dimension(self, filter_key, block_dims, block_dims_by_id):
        if filter_key is None:
            return None

        dim = block_dims.get(str(filter_key).lower())
        if dim:
            return dim

        dim = block_dims_by_id.get(str(filter_key))
        if dim:
            return dim

        return None

    # =====  helper for resolving filter dimension by name or id =====

    #### Loop from query params - rows, columns, filters - lookup input strings to find dimension ids and populate a single list
    def __parse_query_params(self, query_params, dimensions):
        block_dims = {}
        block_dims_by_id = {}
        block_dims_item_map = {}
        block_dimension_ids = set()

        for dimension in dimensions:
            dim_obj = {
                "id": dimension.id,
                "name": dimension.name,
                "colname": f"_{dimension.id}",
                "connected_dim_map": self.generated_connected_dim_mapping(dimension),
            }

            block_dims[str(dimension.name).lower()] = dim_obj
            block_dims_by_id[str(dimension.id)] = dim_obj
            block_dims_item_map[dimension.id] = [item.name for item in dimension.items]

            # Keep this only if `dimensions` here are definitely direct block dimensions.
            # If this list can also include connected dimensions, this is only placeholder metadata.
            block_dimension_ids.add(dimension.id)

        # Manually add indicators to the list
        block_dims["indicators"] = {
            "id": "Indicators",
            "name": "Indicators",
            "colname": "_Indicators",
            "connected_dim_map": {},
        }
        block_dims_by_id["Indicators"] = block_dims["indicators"]
        block_dims_by_id["indicators"] = block_dims["indicators"]

        # Store for connected-dimension filter resolution in __apply_filters_on_dims
        self._block_dims = block_dims

        indicators_found_in_query = False
        query_dims = []

        if query_params:
            # Loops rows in query params
            qpRows = query_params.get("rows")
            if qpRows:
                axis_query_dims, indicators_found_in_axis = self.__parse_axis_params(
                    block_dims, block_dims_by_id, qpRows, "rows"
                )

                if axis_query_dims:
                    query_dims.extend(axis_query_dims)
                if indicators_found_in_axis:
                    indicators_found_in_query = True

            # Loops columns in query params
            qpCols = query_params.get("columns")
            if qpCols:
                axis_query_dims, indicators_found_in_axis = self.__parse_axis_params(
                    block_dims, block_dims_by_id, qpCols, "columns"
                )

                if axis_query_dims:
                    query_dims.extend(axis_query_dims)
                if indicators_found_in_axis:
                    indicators_found_in_query = True

            # Loops filters in query params
            qpFilters = query_params.get("filters")
            if qpFilters:
                for filter_obj in qpFilters:
                    if not isinstance(filter_obj, dict) or len(filter_obj) == 0:
                        continue

                    # Supports both:
                    # {"Region": ["APAC", "EMEA"]}
                    # {"dimension_id": 123, "values": ["APAC"], "name": "Region"}
                    if "dimension_id" in filter_obj or "values" in filter_obj:
                        filter_key = filter_obj.get("name")
                        if filter_obj.get("dimension_id") is not None:
                            filter_key = filter_obj.get("dimension_id")
                        filter_val = filter_obj.get("values", [])
                    else:
                        filter_key = list(filter_obj.keys())[0]
                        filter_val = filter_obj[filter_key]

                    dim = self.__resolve_filter_dimension(
                        filter_key, block_dims, block_dims_by_id
                    )

                    if not dim:
                        raise Exception(f"Filter dimension not found: {filter_key}")

                    filter_val = self.__normalize_filter_items(
                        filter_val, dim, block_dims_item_map
                    )

                    filter_val = [str(v) for v in filter_val if v not in (None, "")]
                    if len(filter_val) == 0:
                        continue

                    obj = {
                        "id": dim["id"],
                        "name": dim["name"],
                        "colname": dim["colname"],
                        "query_location": "filters",
                        "item": filter_val,
                        "connected_dim_map": dim.get("connected_dim_map") or {},
                        # Optional metadata only; not required for filtering logic
                        "dimension_type": (
                            "block" if dim["id"] in block_dimension_ids else "connected"
                        ),
                    }

                    query_dims.append(obj)

                    indicators_found_in_query = (
                        str(dim["name"]).lower() == "indicators"
                        or indicators_found_in_query
                    )

            if indicators_found_in_query is False:
                raise Exception(
                    "Error with query: Indicators must be set in the query, either on rows, columns or select one indicator in the filter"
                )

        return query_dims

    def __parse_axis_params(self, block_dims, block_dims_by_id, axis_obj, axis_type):
        axis_query_dims = []
        indicators_found_in_axis = False
        display_levels = None
        ind_filter = None
        sort = None
        group_by = None

        axis_obj = list(
            filter(
                lambda x: type(x) == str
                or ("name" in x and x["name"] is not None)
                or ("id" in x and x["id"] is not None),
                axis_obj,
            )
        )

        for dim_def in axis_obj:
            total_options: TOTAL_OPTIONS = TOTAL_OPTIONS.BASE_ONLY
            dim = None
            dim_name = None
            dim_id = None
            display_levels = None
            ind_filter = None
            sort = None
            group_by = None

            if type(dim_def) == str:
                dim_name = dim_def
            else:
                dim_name = dim_def.get("name")
                dim_id = dim_def.get("id")
                sum_opts_str = dim_def.get("total_options")
                if sum_opts_str:
                    total_options = TOTAL_OPTIONS[sum_opts_str.upper()]
                display_levels = dim_def.get("display_levels")
                ind_filter = dim_def.get("filter")
                group_by = dim_def.get("group_by")
                sort = dim_def.get("sort")

            if dim_name:
                dim = block_dims.get(str(dim_name).lower())
            elif dim_id is not None:
                dim = block_dims_by_id.get(str(dim_id))

            if dim:
                obj = {
                    "id": dim["id"],
                    "name": dim["name"],
                    "colname": dim["colname"],
                    "query_location": axis_type,
                    "total_options": total_options,
                    "display_levels": display_levels,
                    "filter": ind_filter,
                    "sort": sort,
                    "connected_dim_map": dim["connected_dim_map"],
                    "group_by": group_by,
                }
                axis_query_dims.append(obj)

                if str(dim["name"]).lower() == "indicators":
                    indicators_found_in_axis = True
            else:
                if dim_name:
                    dim_identifier = f"name={dim_name}"
                else:
                    dim_identifier = f"id={dim_id}"
                raise Exception(
                    f"Error with query: On {axis_type}, can't find {dim_identifier} in the model"
                )

        return axis_query_dims, indicators_found_in_axis

    def __create_indicator_lookup(self, indicators, indicator_cols):
        indicator_lookup = {}
        if indicators:
            for indicator in indicators:
                # Add to dict for dataframe rename function - Key should be current value {ind10001}, Value should be Indicator name
                indicator_lookup[f"ind{str(indicator.id)}"] = indicator.name
            return indicator_lookup

        # If we get this far with execution its because we didn't get passed the block_indicators list, so we just create a list from the dataframe columns
        indicator_lookup = {}
        if indicator_cols:
            for indicator in indicator_cols:
                indicator_lookup[indicator] = indicator.replace("ind", "")

        return indicator_lookup

    def __dimension_name_lookup(self, dimensions, dimension_cols):

        dim_name_lookup = {}
        if dimensions:
            for dim in dimensions:
                # Add to dict for dataframe rename function - Key should be current value {ind10001}, Value should be Indicator name
                dim_name_lookup[f"_{str(dim.id)}"] = dim.name
            # Manually add indicators to the list
            dim_name_lookup["_Indicators"] = "Indicators"
            return dim_name_lookup

        # If we get this far with execution its because we didn't get passed the block_dimensions list, so we just create a list from the dataframe columns
        dim_name_lookup = {}
        if dimension_cols:
            for dim in dimension_cols:
                dim_name_lookup[f"_{str(dim)}"] = dim.replace("_", "")
        dim_name_lookup["_Indicators"] = "Indicators"
        return dim_name_lookup

    def sort_dim_items(self, items, sort="ASC"):
        return sorted(
            items, key=lambda x: x.position, reverse=True if sort == "DESC" else False
        )

    def __format_df_with_categories(self, df, dimension_cols, dimensions, query_dims):

        for dim in dimensions:
            dim_items = self.all_dimension_scenario_item_map["_" + str(dim.id)]
            # If this is a time dimension, sort the items into ascending order, not the order of IDs which it does by default
            if dim.name == "Time":
                dim_items = time.sort_list_of_datestrings(dim_items)
            if dim.name != "Time":
                qd_list = [q_dim for q_dim in query_dims if q_dim["id"] == dim.id]
                if qd_list:
                    qd = qd_list[0]
                    if "sort" in qd and qd["sort"] is not None:
                        dim_items = [
                            item.name
                            for item in self.sort_dim_items(dim.items, qd["sort"])
                        ]

                    summary_opts_str = qd.get("total_options")
                    if summary_opts_str == TOTAL_OPTIONS.INCLUDE_TOTAL_AFTER:
                        dim_items.append("Total")
                    elif summary_opts_str == TOTAL_OPTIONS.INCLUDE_TOTAL_BEFORE:
                        dim_items.insert(0, "Total")

            # cat_dtype = CategoricalDtype(dim_items, ordered=True)
            dim_col_name = f"_{dim.id}"
            if dim_col_name in df.columns and df[dim_col_name].dtype.is_numeric():
                df = df.with_columns(pl.col(dim_col_name).cast(pl.Categorical))
                # df[dim_col_name] = df[dim_col_name].astype(cat_dtype)
        return df

    def __apply_filters_on_dims(self, raw_data_df, filters):
        if not filters:
            return raw_data_df

        block_dims = getattr(self, "_block_dims", None) or {}

        for f in filters:
            if f["colname"] == "_Indicators":
                continue

            colname = f["colname"]
            if colname in raw_data_df.columns:
                # Block dimension (or connected dim whose column exists): filter directly
                raw_data_df = raw_data_df.filter(
                    pl.col(colname).cast(pl.Utf8).is_in(f["item"])
                )
                continue

            # Filter dimension column not in data → try connected dimension resolution
            # Find a dimension that has its column in the df and maps to this filter's values
            filter_vals = set(f["item"])
            source_colname = None
            allowed_items = None

            for _key, dim_obj in block_dims.items():
                if _key == "indicators":
                    continue
                d_col = dim_obj.get("colname")
                d_map = dim_obj.get("connected_dim_map") or {}
                if not d_col or d_col not in raw_data_df.columns or not d_map:
                    continue
                # connected_dim_map: block_item -> connected_item (name)
                d_connected_vals = set(d_map.values())
                if not filter_vals.intersection(d_connected_vals):
                    continue
                # This dimension links to our filter dimension; resolve filter via it
                allowed_items = [k for k, v in d_map.items() if v in filter_vals]
                if not allowed_items:
                    continue
                source_colname = d_col
                break

            if source_colname is not None and allowed_items is not None:
                raw_data_df = raw_data_df.filter(
                    pl.col(source_colname).cast(pl.Utf8).is_in(allowed_items)
                )
            else:
                raise Exception(
                    "Filter dimension '{}' ({}) is not a column in the block data and could not be resolved "
                    "via a connected dimension. Check that the dimension name or id is correct and that the "
                    "block has a dimension linking to it.".format(f["name"], colname)
                )

        return raw_data_df

    def __apply_filters_on_indicators(self, raw_data_df, filters, indicator_lookup):

        conditions = None
        if filters:
            for filter in filters:
                # if filter is an indicator filter then we deal with a different way
                if filter["colname"] == "_Indicators":

                    # find indicator id for filter['item'] from query string
                    # loop through indicator_lookup dictionary looking for matching name
                    match_found = False
                    ind_id_to_filter = []
                    for id, name in indicator_lookup.items():
                        for item in filter["item"]:
                            if str(name) == str(item):  # exact match
                                ind_id_to_filter.append(id)
                                match_found = True
                            # drop all ind columns - except this one
                    cols_to_drop = [
                        col
                        for col in list(raw_data_df.columns)
                        if col.startswith("ind") and col not in ind_id_to_filter
                    ]
                    # raw_data_df=raw_data_df.drop(columns=cols_to_drop)
                    cols_to_keep = [
                        col for col in raw_data_df.columns if col not in cols_to_drop
                    ]
                    raw_data_df = raw_data_df.select(cols_to_keep)
                    if match_found == False:
                        raise Exception(
                            f"Error with Filter: Indicator '{str(filter['item'])}' not found in model."
                        )

            return raw_data_df
        else:
            return raw_data_df

    def __create_agg_params_list(self, query_dims):
        agg_params = []

        for dim in query_dims:
            if dim["query_location"] in ["rows", "columns"]:
                if dim["name"] != "Indicators":
                    agg_param = Agg_param(
                        id=dim["id"],
                        name=dim["name"],
                        col_name=dim["colname"],
                        total_options=dim["total_options"],
                        display_levels=dim["display_levels"],
                        connected_dim_map=dim["connected_dim_map"],
                        group_by=(
                            dim["group_by"]
                            if "group_by" in dim and dim["group_by"] is not None
                            else dim["name"]
                        ),
                    )
                    agg_params.append(agg_param)

        return agg_params

    def __format_data_values(self, time_aggregate_df):

        formatted_df = time_aggregate_df.clone()

        ###Formatting is now done on the front end based on the properties passed from the back end.
        ###Removing this section of code, however keeping the formatting step so that it can be easily integrated if required in future

        # indicator_cols = [col for col in list(formatted_df) if col.startswith('ind')]
        ##Format the data for each indicator column
        ##TODO - this should be based on the data format properties of each indicator. For now we're just rounding to 2dp for simplicity. BLOX-30
        # for col in indicator_cols:
        #    formatted_df = formatted_df.round({col : 2})

        return formatted_df

    def __pivot_data_values(
        self, data_df, query_dims, indicator_lookup, dim_name_lookup, indicators
    ):

        # Format the aggregated data for the block so that each of the indicators have a single row of data, with time data along the columns
        dimension_cols = [col for col in data_df.columns if not col.startswith("ind")]

        rows = []
        columns = []
        indicator_filter = None
        for dim in query_dims:
            if dim["query_location"] in ["rows"]:
                rows.append(dim["colname"])
            elif dim["query_location"] in ["columns"]:
                columns.append(dim["colname"])
            if (
                dim["colname"] == "_Indicators"
                and "filter" in dim
                and dim["filter"] is not None
            ):
                indicator_filter = dim["filter"]

        # First - we need to spin the dataframe. Till now the indicators each have their own columns.
        # for cases where we have no inputs in the block, we'll get an empty df. Deal with this differently
        if not data_df.is_empty():
            result_df = data_df.melt(
                id_vars=dimension_cols, variable_name="_Indicators"
            )

            if len(rows) == 0:
                result_df = result_df.with_columns(pl.lit("Values").alias("values"))
                rows.append("values")

            # PIVOT
            try:

                if len(columns) > 1:
                    result_df = result_df.pivot(
                        index=columns,
                        columns=rows,
                        values="value",
                        aggregate_function="mean",
                    )
                else:
                    result_df = result_df.pivot(
                        columns=columns, index=rows, values="value"
                    )
            except:
                traceback.print_exc()
                print(columns, rows)
                print(query_dims, indicator_lookup, dim_name_lookup, indicators)
                print(dim_name_lookup, indicators)
                raise Exception("Something went wrong")

            if indicator_filter:
                ind_to_retain = apply_filter_on_indicators(indicators, indicator_filter)
                ind_to_retain = ["ind" + str(ind.id) for ind in ind_to_retain]
                result_df = result_df.filter(pl.col("_Indicators").is_in(ind_to_retain))

            # Replace indicator IDs with Indicator names
            if len(columns) > 1:
                if "_Indicators" in columns:
                    result_df = result_df.with_columns(
                        pl.col("_Indicators")
                        .map_dict(indicator_lookup)
                        .alias("_Indicators")
                    )

                if "_Indicators" in rows:
                    result_df.columns = list(
                        map(
                            lambda x: (
                                indicator_lookup[x] if x in indicator_lookup else x
                            ),
                            result_df.columns,
                        )
                    )
            else:
                if "_Indicators" in columns:
                    result_df.columns = list(
                        map(
                            lambda x: (
                                indicator_lookup[x] if x in indicator_lookup else x
                            ),
                            result_df.columns,
                        )
                    )

                if "_Indicators" in rows:
                    result_df = result_df.with_columns(
                        pl.col("_Indicators")
                        .replace(indicator_lookup)
                        .alias("_Indicators")
                    )

            # If there are multiple columns then we end up with a Multiindex on columns which isn't going to work for us
            # This next bit flattens the column indexes and concats the strings into 1
            if len(columns) > 1:
                result_df = result_df.with_columns(
                    pl.concat_str(
                        [pl.col(col) for col in columns], separator=" | "
                    ).alias("_Indicators")
                )
                result_df = result_df.transpose(
                    header_name="_Indicators",
                    include_header=True,
                    column_names=result_df.select("_Indicators").to_series().to_list(),
                )
                result_df = result_df.filter(~pl.col("_Indicators").is_in(columns))
                result_df = result_df.rename({"_Indicators": rows[0]})
            # Replace name of index column headers with real dimension names
            if len(rows) == 1:
                if rows[0] != "values":
                    self.indexed_columns.append(dim_name_lookup[rows[0]])
                    result_df = result_df.rename({rows[0]: dim_name_lookup[rows[0]]})
                else:
                    self.indexed_columns.append("values")
            elif len(rows) > 1:
                for row in rows:
                    if row != "values":
                        self.indexed_columns.append(dim_name_lookup[row])
                        result_df = result_df.rename({row: dim_name_lookup[row]})
                    else:
                        self.indexed_columns.append("values")
        else:
            result_df = data_df

        return result_df

    def json(self, orient=None):

        if self.pivoted_df is None:
            raise Exception(f"Error with Data Pivot - pivoted data wasn't found.")

        if "Indicators" in self.pivoted_df.columns:
            df = self.pivoted_df.sort("Indicators", descending=False)
        else:
            df = self.pivoted_df

        numeric_columns = [
            df.columns[i]
            for i, col_name in enumerate(df.dtypes)
            if col_name.is_(pl.Float64)
        ]
        num_cols = []
        for col_name in numeric_columns:
            num_cols.append(pl.col(col_name).round(3).alias(col_name))
        df = df.with_columns(num_cols)

        # return the data values by outputing the dataframe as json
        # json_str = df.write_json(row_oriented=True)
        # parsed_json = json.loads(json_str)
        parsed_json = df.to_dicts() if not df.is_empty() else []

        output = {}
        if orient == "index":
            for item in parsed_json:
                for index_col in self.indexed_columns:
                    product_name = item.pop(
                        index_col
                    )  # Remove and get the product name
                    output[product_name] = item
        else:

            output["data"] = parsed_json
            fields = []
            dt_map = {
                pl.Utf8: "string",
                pl.Int32: "number",
                pl.Categorical: "string",
                pl.Float64: "number",
                pl.Float32: "number",
            }
            for field in df.schema:
                fields.append({"name": field, "type": dt_map[df.schema[field]]})
            output["schema"] = {
                "fields": fields,
                "pandas_version": "2.0.0",
                "primaryKey": self.indexed_columns,
            }

        return output
