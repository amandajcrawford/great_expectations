import json
from typing import Optional

import pandas as pd
import pygeos as geos

from great_expectations.core.expectation_configuration import ExpectationConfiguration
from great_expectations.exceptions import InvalidExpectationConfigurationError
from great_expectations.execution_engine import (
    PandasExecutionEngine,
    SparkDFExecutionEngine,
    SqlAlchemyExecutionEngine,
)
from great_expectations.expectations.expectation import ColumnMapExpectation
from great_expectations.expectations.metrics import (
    ColumnMapMetricProvider,
    column_condition_partial,
)


# This class defines a Metric to support your Expectation.
# For most ColumnMapExpectations, the main business logic for calculation will live in this class.
class ColumnValuesGeometryNearShape(ColumnMapMetricProvider):

    # This is the id string that will be used to reference your metric.
    condition_metric_name = "column_values.geometry.near_shape"
    condition_value_keys = (
        "shape",
        "shape_format",
        "column_shape_format",
        "distance_tol",
    )

    # This method implements the core logic for the PandasExecutionEngine
    @column_condition_partial(engine=PandasExecutionEngine)
    def _pandas(cls, column, **kwargs):

        shape = kwargs.get("shape")
        shape_format = kwargs.get("shape_format")
        column_shape_format = kwargs.get("column_shape_format")
        distance_tol = kwargs.get("distance_tol")

        # Check that shape is given and given in the correct format
        if shape is not None:
            try:
                if shape_format == "wkt":
                    shape_ref = geos.from_wkt(shape)
                elif shape_format == "wkb":
                    shape_ref = geos.from_wkb(shape)
                elif shape_format == "geojson":
                    shape_ref = geos.from_geojson(shape)
                else:
                    raise NotImplementedError(
                        "Shape constructor method not implemented. Must be in WKT, WKB, or GeoJSON format."
                    )
            except:
                raise Exception("A valid reference shape was not given.")
        else:
            raise Exception("A shape must be provided for this method.")

        # Load the column into a pygeos Geometry vector from numpy array (Series not supported).
        if column_shape_format == "wkt":
            shape_test = geos.from_wkt(column.to_numpy(), on_invalid="ignore")
        elif column_shape_format == "wkb":
            shape_test = geos.from_wkb(column.to_numpy(), on_invalid="ignore")
        else:
            raise NotImplementedError("Column values shape format not implemented.")

        # Allow for an array of reference shapes to be provided. Return a union of all the shapes in the array (Polygon or Multipolygon)
        shape_ref = geos.union_all(shape_ref)

        # Prepare the geometries
        geos.prepare(shape_ref)
        geos.prepare(shape_test)

        # Return whether the distance is below the tolerance.
        return pd.Series(geos.dwithin(shape_test, shape_ref, distance_tol))

    # This method defines the business logic for evaluating your metric when using a SqlAlchemyExecutionEngine
    # @column_condition_partial(engine=SqlAlchemyExecutionEngine)
    # def _sqlalchemy(cls, column, _dialect, **kwargs):
    #     raise NotImplementedError

    # This method defines the business logic for evaluating your metric when using a SparkDFExecutionEngine
    # @column_condition_partial(engine=SparkDFExecutionEngine)
    # def _spark(cls, column, **kwargs):
    #     raise NotImplementedError


# This class defines the Expectation itself
class ExpectColumnValuesGeometryToBeNearShape(ColumnMapExpectation):
    """
    Expect that column values as geometries are near (within a given distance) of a given reference shape in the units of the provided geometries.

    expect_column_values_geometry_to_be_near_shape is a :func:`column_map_expectation <great_expectations.dataset.dataset.MetaDataset.column_map_expectation>`.

    Args:
        column (str): \
            The column name.
            Column values must be provided in WKT or WKB format, which are commom formats for GIS Database formats.
            WKT can be accessed thhrough the ST_AsText() or ST_AsBinary() functions in queries for PostGIS and MSSQL.

    Keyword Args:
        shape: str or list(str)
            The reference geometry

        shape_format: str
            Geometry format for 'shape' string(s). Can be provided as 'Well Known Text' (WKT), 'Well Known Binary' (WKB), or as GeoJSON.
            Must be one of: [wkt, wkb, geojson]
            Default: wkt

        column_shape_format: str
            Geometry format for 'column'. Column values must be provided in WKT or WKB format, which are commom formats for GIS Database formats.
            WKT can be accessed thhrough the ST_AsText() or ST_AsBinary() functions in queries for PostGIS and MSSQL.

        distance_tol: float
            Distance tolerance for the column value geometries to the reference shape. Note that 0 evaluates to expect_column_values_to_be_within_shape.
            Distance values are always positive. Negative tolerances will always evaluate to False.
            Default: 0

    Returns:
        An ExpectationSuiteValidationResult

    Notes:
        The distance returned and specified is based on the coordinate system of the points, not Latitude and Longitude.
        The user is responsible for the projection method and units (e.g. UTM in m).
        The distance calculation is based on a cartesian coordinate system.
        Convention is (X Y Z) for points, which would map to (Longitude Latitude Elevation) for geospatial cases.
        Any convention can be followed as long as the test and reference shapes are consistent.
        The reference shape allows for an array, but will union (merge) all the shapes into 1 and check the contains condition.
    """

    # These examples will be shown in the public gallery.
    # They will also be executed as unit tests for your Expectation.
    examples = [
        {
            "data": {
                "points_only": [
                    "POINT(1 1)",
                    "POINT(2 2)",
                    "POINT(6 4)",
                    "POINT(3 9)",
                    "POINT(8 9.999)",
                ],
                "points_and_lines": [
                    "POINT(1 1)",
                    "POINT(2 2)",
                    "POINT(6 4)",
                    "POINT(3 9)",
                    "LINESTRING(5 5, 8 10)",
                ],
            },
            "tests": [
                {
                    "title": "positive_test_with_points",
                    "exact_match_out": False,
                    "include_in_gallery": True,
                    "in": {
                        "column": "points_only",
                        "shape": "POINT(0 0)",
                        "shape_format": "wkt",
                        "column_shape_format": "wkt",
                        "distance_tol": 15.0,
                    },
                    "out": {
                        "success": True,
                    },
                },
                {
                    "title": "positive_test_with_points_and_lines",
                    "exact_match_out": False,
                    "include_in_gallery": True,
                    "in": {
                        "column": "points_and_lines",
                        "shape": "POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))",
                        "shape_format": "wkt",
                        "column_shape_format": "wkt",
                        "distance_tol": 10.0,
                    },
                    "out": {
                        "success": True,
                    },
                },
                {
                    "title": "positive_test_with_points_and_lines_geojson_reference_shape",
                    "exact_match_out": False,
                    "include_in_gallery": True,
                    "in": {
                        "column": "points_and_lines",
                        "shape": '{"type":"Polygon","coordinates":[[[0.0,0.0],[0.0,10.0],[10.0,10.0],[10.0,0.0],[0.0,0.0]]]}',
                        "shape_format": "geojson",
                        "column_shape_format": "wkt",
                        "distance_tol": 10.0,
                    },
                    "out": {
                        "success": True,
                    },
                },
                {
                    "title": "negative_test_with_points",
                    "exact_match_out": False,
                    "include_in_gallery": True,
                    "in": {
                        "column": "points_only",
                        "shape": "POINT(0 0)",
                        "shape_format": "wkt",
                        "column_shape_format": "wkt",
                        "distance_tol": 6.0,
                    },
                    "out": {"success": False, "unexpected_index_list": [2, 3, 4]},
                },
                {
                    "title": "negative_test_with_points_and_lines_and_array_reference_shape",
                    "exact_match_out": False,
                    "include_in_gallery": True,
                    "in": {
                        "column": "points_and_lines",
                        "shape": ["POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0))", "POINT(0 10)"],
                        "shape_format": "wkt",
                        "column_shape_format": "wkt",
                        "distance_tol": 5.0,
                    },
                    "out": {"success": False, "unexpected_index_list": [2, 4]},
                },
            ],
        }
    ]

    # This is the id string of the Metric used by this Expectation.
    # For most Expectations, it will be the same as the `condition_metric_name` defined in your Metric class above.
    map_metric = "column_values.geometry.near_shape"

    # This is a list of parameter names that can affect whether the Expectation evaluates to True or False
    success_keys = (
        "mostly",
        "shape",
        "shape_format",
        "column_shape_format",
        "distance_tol",
    )

    # This dictionary contains default values for any parameters that should have default values
    default_kwarg_values = {
        "mostly": 1,
        "shape_format": "wkt",
        "column_shape_format": "wkt",
        "distance_tol": 0.0,
    }

    def validate_configuration(self, configuration: Optional[ExpectationConfiguration]):
        """
        Validates that a configuration has been set, and sets a configuration if it has yet to be set. Ensures that
        necessary configuration arguments have been provided for the validation of the expectation.

        Args:
            configuration (OPTIONAL[ExpectationConfiguration]): \
                An optional Expectation Configuration entry that will be used to configure the expectation
        Returns:
            True if the configuration has been validated successfully. Otherwise, raises an exception
        """

        super().validate_configuration(configuration)
        if configuration is None:
            configuration = self.configuration

        # # Check other things in configuration.kwargs and raise Exceptions if needed
        # try:
        #     assert (
        #         ...
        #     ), "message"
        #     assert (
        #         ...
        #     ), "message"
        # except AssertionError as e:
        #     raise InvalidExpectationConfigurationError(str(e))

        return True

    # This object contains metadata for display in the public Gallery
    library_metadata = {
        "tags": [
            "geospatial",
            "hackathon-2022",
        ],  # Tags for this Expectation in the Gallery
        "contributors": [  # Github handles for all contributors to this Expectation.
            "@pjdobson",  # Don't forget to add your github handle here!
        ],
        "requirements": ["pygeos"],
    }


if __name__ == "__main__":
    ExpectColumnValuesGeometryToBeNearShape().print_diagnostic_checklist()
