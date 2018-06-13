"""

These tools are used for the day-to-day management of geographic and tabular data.

copy_to_data_store copies data to your ArcGIS Data Store and creates a layer in your web GIS.
"""
import json as _json
import logging as _logging
import arcgis as _arcgis
from arcgis.features import FeatureSet as _FeatureSet
from arcgis.geoprocessing._support import _execute_gp_tool
from ._util import _id_generator, _feature_input, _set_context, _create_output_service

_log = _logging.getLogger(__name__)

_use_async = True

def calculate_fields(input_layer,
                     field_name,
                     data_type,
                     expression,
                     track_aware=False,
                     track_fields=None,
                     output_name=None,
                     gis=None
                     ):
    """
    The Calculate Field task works with a layer to create and populate a
    new field. The output is a new feature layer, that is the same as the
    input features, with the additional field added.

    ================  ===============================================================
    **Argument**      **Description**
    ----------------  ---------------------------------------------------------------
    input_layer       required service , The table, point, line or polygon features
                      containing potential incidents.
    ----------------  ---------------------------------------------------------------
    field_name        required string, A string representing the name of the new
                      field. If the name already exists in the dataset, then a
                      numeric value will be appended to the field name.
    ----------------  ---------------------------------------------------------------
    data_type         required string, the type for the new field.
                      Values: Date |Double | Integer | String
    ----------------  ---------------------------------------------------------------
    expression        required string, An Arcade expression used to calculate the new
                      field values. You can use any of the Date, Logical,
                      Mathematical or Text function available with Arcade.
    ----------------  ---------------------------------------------------------------
    track_aware       optional boolean, Boolean value denoting if the expression is
                      track aware.
                      Default: False
    ----------------  ---------------------------------------------------------------
    track_fields      optional string, The fields used to identify distinct tracks.
                      There can be multiple track_fields. track_fields are only
                      required when track_aware is true.
    ----------------  ---------------------------------------------------------------
    output_name       optional string, The task will create a feature service of the
                      results. You define the name of the service.
    ----------------  ---------------------------------------------------------------
    gis               optional GIS, the GIS on which this tool runs. If not
                      specified, the active GIS is used.
    ================  ===============================================================

    :returns:
       Feature Layer
    """
    kwargs = locals()
    tool_name = "CalculateField"
    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url
    params = {
        "f" : "json"
    }
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Calculate_Fields_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Calculate Fields')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "field_name" : (str, "fieldName"),
        "data_type" : (str, "dataType"),
        "expression" : (str, "expression"),
        "track_aware" : (bool, "trackAware"),
        "track_fields" : (str, "trackFields"),
        "output_name": (str, "outputName"),
        "output": (_FeatureSet, "output"),
        "context": (str, "context")
    }
    return_values = [
        {"name": "output", "display_name": "Output Features", "type": _FeatureSet},
    ]
    try:
        _execute_gp_tool(gis, tool_name, params, param_db, return_values, _use_async, url, True)
        return output_service
    except:
        output_service.delete()
        raise

    return

def copy_to_data_store(
    input_layer,
    output_name = None,
    gis = None):
    """

    Copies an input feature layer or table to an ArcGIS Data Store and creates a layer in your web GIS.

    For example

    * Copy a collection of .csv files in a big data file share to the spatiotemporal data store for visualization.

    * Copy the features in the current map extent that are stored in the spatiotemporal data store to the relational data store.

    This tool will take an input layer and copy it to a data store. Data will be copied to the ArcGIS Data Store and will be stored in your relational or spatiotemporal data store.

    For example, you could copy features that are stored in a big data file share to a relational data store and specify that only features within the current map extent will be copied. This would create a hosted feature service with only those features that were within the specified map extent.

   Parameters:

   input_layer: Input Layer (feature layer). Required parameter.

   output_name: Output Layer Name (str). Required parameter.

   gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


Returns:
   output - Output Layer as a feature layer collection item


    """
    kwargs = locals()

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.geoanalytics.url

    params = {}
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value

    if output_name is None:
        output_service_name = 'Data Store Copy_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_service(gis, output_name, output_service_name, 'Copy To Data Store')

    params['output_name'] = _json.dumps({
        "serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url},
        "itemProperties": {"itemId" : output_service.itemid}})

    _set_context(params)

    param_db = {
        "input_layer": (_FeatureSet, "inputLayer"),
        "output_name": (str, "outputName"),
        "context": (str, "context"),
        "output": (_FeatureSet, "Output Layer"),
    }
    return_values = [
        {"name": "output", "display_name": "Output Layer", "type": _FeatureSet},
    ]
    try:
        _execute_gp_tool(gis, "CopyToDataStore", params, param_db, return_values, _use_async, url, True)
        return output_service
    except:
        output_service.delete()
        raise

copy_to_data_store.__annotations__ = {
    'output_name': str}





