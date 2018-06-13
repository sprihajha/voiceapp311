"Functions for calling the Raster Analysis Tools. The RasterAnalysisTools service is used by ArcGIS Server to provide distributed raster analysis."

from arcgis.geoprocessing._support import _analysis_job, _analysis_job_results, \
                                          _analysis_job_status, _layer_input
import json as _json
import arcgis as _arcgis
import string as _string
import random as _random

def get_datastores(gis=None):
    """
    Returns a helper object to manage raster analytics datastores in the GIS.
    If a gis isn't specified, returns datastore manager of arcgis.env.active_gis
    """
    gis = _arcgis.env.active_gis if gis is None else gis

    for ds in gis._datastores:
        if ds._server['serverFunction'] == 'RasterAnalytics':
            return ds

    return None


def is_supported(gis=None):
    """
    Returns True if the GIS supports raster analytics. If a gis isn't specified,
    checks if arcgis.env.active_gis supports raster analytics
    """
    gis = _arcgis.env.active_gis if gis is None else gis
    if 'rasterAnalytics' in gis.properties.helperServices:
        return True
    else:
        return False

def _id_generator(size=6, chars=_string.ascii_uppercase + _string.digits):
    return ''.join(_random.choice(chars) for _ in range(size))


def _set_context(params):
    out_sr = _arcgis.env.out_spatial_reference
    process_sr = _arcgis.env.process_spatial_reference
    out_extent = _arcgis.env.analysis_extent

    context = {}
    set_context = False

    if out_sr is not None:
        context['outSR'] = {'wkid': int(out_sr)}
        set_context = True
    if out_extent is not None:
        context['extent'] = out_extent
        set_context = True
    if process_sr is not None:
        context['processSR'] = {'wkid': int(process_sr)}
        set_context = True

    if set_context:
        params["context"] = _json.dumps(context)
        
def _create_output_image_service(gis, output_name, task):
    ok = gis.content.is_service_name_available(output_name, "Image Service")
    if not ok:
        raise RuntimeError("An Image Service by this name already exists: " + output_name)

    create_parameters = {
        "name": output_name,
        "description": "",
        "capabilities": "Image",
        "properties": {
            "path": "@",
            "description": "",
            "copyright": ""
        }
    }

    output_service = gis.content.create_service(output_name, create_params=create_parameters,
                                                      service_type="imageService")
    description = "Image Service generated from running the " + task + " tool."
    item_properties = {
        "description": description,
        "tags": "Analysis Result, " + task,
        "snippet": "Analysis Image Service generated from " + task
    }
    output_service.update(item_properties)
    return output_service

def _create_output_feature_service(gis, output_name, output_service_name='Analysis feature service', task='GeoAnalytics'):
    ok = gis.content.is_service_name_available(output_name, 'Feature Service')
    if not ok:
        raise RuntimeError("A Feature Service by this name already exists: " + output_name)

    createParameters = {
            "currentVersion": 10.2,
            "serviceDescription": "",
            "hasVersionedData": False,
            "supportsDisconnectedEditing": False,
            "hasStaticData": True,
            "maxRecordCount": 2000,
            "supportedQueryFormats": "JSON",
            "capabilities": "Query",
            "description": "",
            "copyrightText": "",
            "allowGeometryUpdates": False,
            "syncEnabled": False,
            "editorTrackingInfo": {
                "enableEditorTracking": False,
                "enableOwnershipAccessControl": False,
                "allowOthersToUpdate": True,
                "allowOthersToDelete": True
            },
            "xssPreventionInfo": {
                "xssPreventionEnabled": True,
                "xssPreventionRule": "InputOnly",
                "xssInputRule": "rejectInvalid"
            },
            "tables": [],
            "name": output_service_name.replace(' ', '_')
        }

    output_service = gis.content.create_service(output_name, create_params=createParameters, service_type="featureService")
    description = "Feature Service generated from running the " + task + " tool."
    item_properties = {
            "description" : description,
            "tags" : "Analysis Result, " + task,
            "snippet": output_service_name
            }
    output_service.update(item_properties)
    return output_service

# def monitor_vegetation(input_raster,
#                        method_to_use='NDVI',
#                        nir_band=1,
#                        red_band=2,
#                        options={},
#                        output_name=None,
#                        gis=None):
#     """
#
#     :param input_raster: multiband raster layer. Make sure the input raster has the appropriate bands available.
#
#     :param method_to_use: one of NDVI, GEMI, GVI, PVI, SAVI, MSAVI2, TSAVI, SULTAN.
#          the method used to create the vegetation index layer. The different vegetation indexes can help highlight
#          certain features, or help reduce various noise.
#
#         * GEMI - Global Environmental Monitoring Index - GEMI is a nonlinear vegetation index for global environmental
#             monitoring from satellite imagery. It is similar to NDVI, but it is less sensitive to atmospheric
#             effects. It is affected by bare soil; therefore, it is not recommended for use in areas of sparse or
#             moderately dense vegetation.
#         * GVI - Green Vegetation Index - Landsat TM - GVI was originally designed from Landsat MSS imagery but has been
#             modified for use with Landsat TM imagery. It is also known as the Landsat TM Tasseled Cap green
#             vegetation index. This monitoring index can also be used with imagery whose bands share the same
#             spectral characteristics.
#         * MSAVI2 - Modified Soil Adjusted Vegetation Index - MSAVI2 is a vegetation index that tries to minimize bare soil
#             influences of the SAVI method.
#         * NDVI - Normalized Difference Vegetation Index - NDVI is a standardized index allowing you to generate an image
#             displaying greenness, relative biomass. This index takes advantage of the contrast of the
#             characteristics of two bands from a multispectral raster dataset; the chlorophyll pigment absorptions
#             in the red band and the high reflectivity of plant materials in the near-infrared (NIR) band.
#         * PVI - Perpendicular Vegetation Index - PVI is similar to a difference vegetation index; however, it is sensitive
#             to atmospheric variations. When using this method to compare different images, it should only be used on
#             images that have been atmospherically corrected. This information can be provided by your data vendor.
#         * SAVI - Soil-Adjusted Vegetation Index - SAVI is a vegetation index that attempts to minimize soil brightness
#             influences using a soil-brightness correction factor. This is often used in arid regions where
#             vegetative cover is low.
#         * SULTAN - Sultan's Formula - The Sultan's Formula process takes a six-band 8-bit image and applied a specific
#             algorithm to it to produce a three-band 8-bit image. The resulting image highlights rock formations
#             called ophiolites on coastlines. This formula was designed based on the TM and ETM bands of a Landsat 5
#             or 7 scene.
#         * TSAVI - Transformed Soil-Adjusted Vegetation Index - Transformed-SAVI is a vegetation index that attempts to
#             minimize soil brightness influences by assuming the soil line has an arbitrary slope and intercept.
#
#     :param nir_band: the band indexes for the near-infrared (NIR) band.
#     :param red_band: the band indexes for the Red band.
#     :param options: additional parameters such as slope, intercept
#         * intercept is the value of near infrared (NIR) when the reflection value of the red (Red) band is 0 for the particular soil lines.
#         (a = NIR - sRed) , when Red is 0.
#         This parameter is only valid for Transformed Soil-Adjusted Vegetation Index.
#
#         * slope - Slope of soil line
#         The slope of the soil line. The slope is the approximate linear relationship between the NIR and red bands on a scatterplot.
#         This parameter is only valid for Transformed Soil-Adjusted Vegetation Index.
#
#         *
#     :param output_name:
#     :param gis:
#     :return:
#     """
#     NDVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 1, "BandIndexes": "1 2"}}
#
#     GEMI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 5, "BandIndexes": "1 2 3 4 5 6"}}
#
#     GVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 7, "BandIndexes": "1 2"}}
#
#     MSAVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 4, "BandIndexes": "1 2"}}
#
#     PVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 6, "BandIndexes": "1 2 111 222"}}
#
#     SAVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 2, "BandIndexes": "1 2 111"}}
#
#     SULTAN
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 8, "BandIndexes": "1 2 3 4 5 6"}}
#
#     TSAVI
#     {"rasterFunction": "BandArithmetic", "rasterFunctionArguments": {"Method": 3, "BandIndexes": "1 2 111 222 333"}}
#
#     raster_function = {"rasterFunction":"BandArithmetic","rasterFunctionArguments":{"Method":1,"BandIndexes":"1 2"}}
#
#     function_args = {'Raster': _layer_input(input_raster)}
#
#     return generate_raster(raster_function, function_args, output_name=output_name, gis=gis)

def generate_raster(raster_function,
                    function_arguments=None,
                    output_raster_properties=None,
                    output_name=None,
                    gis=None):
    """


    Parameters
    ----------
    raster_function : Required, see http://resources.arcgis.com/en/help/rest/apiref/israsterfunctions.html

    function_arguments : Optional,  for specifying input Raster alone, portal Item can be passed

    output_raster_properties : Optional
    
    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster. 
        You can pass in an existing Image Service Item from your GIS to use that instead.

        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be
        used as the output for the tool.

        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item
    """

    task = "GenerateRaster"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)
    
    output_service = None

    if output_name is None:
        output_name = 'GeneratedRasterProduct' + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
    else:
        raise TypeError("output_raster should be a string (service name) or Item")

    output_raster = _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 

    if isinstance(function_arguments, _arcgis.gis.Item):
        if function_arguments.type.lower() == 'image service':
            function_arguments = {"Raster": {"itemId": function_arguments.itemid}}
        else:
            raise TypeError("The item type of function_arguments must be an image service")

    params = {}

    params["rasterFunction"] = raster_function

    params["outputName"] = output_raster
    if function_arguments is not None:
        params["functionArguments"] = function_arguments
    if output_raster_properties is not None:
        params["rasterProperties"] = output_raster_properties
    _set_context(params)


    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def convert_feature_to_raster(input_feature,
                              output_cell_size,
                              value_field=None,
                              output_name=None,
                              gis=None):
    """
    Creates a new raster dataset from an existing feature dataset.
    Any feature class containing point, line, or polygon features can be converted to a raster dataset.
    The cell center is used to decide the value of the output raster pixel. The input field type determines
    the type of output raster. If the field is integer, the output raster will be integer;
    if it is floating point, the output will be floating point.

    Parameters
    ----------
    input_feature : Required. The input feature layer to convert to a raster dataset.

    output_cell_size : Required LinearUnit. The cell size and unit for the output rasters.
                       The available units are Feet, Miles, Meters, and Kilometers.
                       eg - {"distance":60,"units":meters}

    value_field : Optional string.  The field that will be used to assign values to the output raster.

    output_name : Optional. The name of the layer that will be created in My Content.
        If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_raster : Image layer item 
    """

    task = "ConvertFeatureToRaster"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_service = None

    if output_name is None:
        output_name = task + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
    else:
        raise TypeError("output_raster should be a string (service name) or Item")

    params = {}

    params["inputFeature"] = _layer_input(input_feature)


    output_raster = _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 

    params["outputName"] = output_raster

    params["outputCellSize"] = output_cell_size
    if value_field is not None:
        params["valueField"] = value_field
    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def copy_raster(input_raster,
                output_cellsize=None,
                resampling_method="NEAREST",
                clip_setting=None,
                output_name=None,
                gis=None):
    """


    Parameters
    ----------
    input_raster : Required string

    output_cellsize : Optional string

    resampling_method : Optional string
        One of the following: ['NEAREST', 'BILINEAR', 'CUBIC', 'MAJORITY']
    clip_setting : Optional string

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item 
    """

    task = "CopyRaster"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_service = None

    if output_name is None:
        output_name = task + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
    else:
        raise TypeError("output_raster should be a string (service name) or Item")

    params = {}

    output_raster = _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 
    params["outputName"] = output_raster

    params["inputRaster"] = _layer_input(input_raster)

    if output_cellsize is not None:
        params["outputCellsize"] = output_cellsize
    if resampling_method is not None:
        params["resamplingMethod"] = resampling_method
    if clip_setting is not None:
        params["clipSetting"] = clip_setting
    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def summarize_raster_within(input_zone_layer,
                            input_raster_layer_to_summarize,
                            zone_field="Value",
                            statistic_type="Mean",
                            ignore_missing_values=True,
                            output_name=None,
                            gis=None):
    """


    Parameters
    ----------
    input_zone_layer : Required layer - area layer to summarize a raster layer within defined boundaries.
        The layer that defines the boundaries of the areas, or zones, that will be summarized.
        The layer can be a raster or feature data. For rasters, the zones are defined by all locations in the input that
        have the same cell value. The areas do not have to be contiguous.

    input_raster_layer_to_summarize : Required  - raster layer to summarize.
        The raster cells in this layer will be summarized by the areas (zones) that they fall within.

    zone_field : Required string -  field to define the boundaries. This is the attribute of the layer that will be used
        to define the boundaries of the areas. For example, suppose the first input layer defines the management unit
        boundaries, with attributes that define the region, the district, and the parcel ID of each unit. You also have
        a raster layer defining a biodiversity index for each location. With the field you select, you can decide to
        calculate the average biodiversity at local, district, or regional levels.

    statistic_type : Optional string - statistic to calculate.
        You can calculate statistics of any numerical attribute of the points, lines, or areas within the input area
        layer. The available statistics types when the selected field is integer are
        Mean, Maximum, Median, Minimum, Minority, Range, Standard deviation(STD), Sum, and Variety. If the field is
        floating point, the options are Mean, Maximum, Minimum, Range, Standard deviation, and Sum.
        One of the following:
        ['Mean', 'Majority', 'Maximum', 'Median', 'Minimum', 'Minority', 'Range', 'STD', 'SUM', 'Variety']

    ignore_missing_values : Optional bool.
        If you choose to ignore missing values, only the cells that have a value in the layer to be summarized will be
        used in determining the output value for that area. Otherwise, if there are missing values anywhere in an area,
        it is deemed that there is insufficient information to perform statistical calculations for all the cells in
        that zone, and that area will receive a null (NoData) value in the output.

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item 
    """

    task = "SummarizeRasterWithin"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_service = None

    if output_name is None:
        output_name = task + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
        output_name = output_service['title']
    else:
        raise TypeError("output_raster should be a string (service name) or Item")

    params = {}

    output_raster = _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}})

    #    _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 
    params["OutputName"] = output_raster


    params["inputZoneLayer"] = _layer_input(input_zone_layer)
    params["zoneField"] = zone_field
    params["inputRasterLayertoSummarize"] = _layer_input(input_raster_layer_to_summarize)

    if statistic_type is not None:
        params["statisticType"] = statistic_type
    if ignore_missing_values is not None:
        params["ignoreMissingValues"] = ignore_missing_values
    _set_context(params)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def convert_raster_to_feature(input_raster,
                              field="Value",
                              output_type="Polygon",
                              simplify=True,
                              output_name=None,
                              gis=None):
    """
    This service tool converts imagery data to feature class vector data.

    Parameters
    ----------
    input_raster : Required. The input raster that will be converted to a feature dataset.

    field : Optional string - field that specifies which value will be used for the conversion.
        It can be any integer or a string field.
        A field containing floating-point values can only be used if the output is to a point dataset.
        Default is "Value"

    output_type : Optional string
        One of the following: ['Point', 'Line', 'Polygon']

    simplify : Optional bool, This option that specifies how the features should be smoothed. It is 
               only available for line and polygon output.
               True, then the features will be smoothed out. This is the default.
               if False, then The features will follow exactly the cell boundaries of the raster dataset.

    output_name : Optional. If not provided, an Feature layer is created by the method and used as the output .
        You can pass in an existing Feature Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Feature Service that should be created by this method
        to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_features : Image layer item 
    """

    task = "ConvertRasterToFeature"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    params["inputRaster"] = _layer_input(input_raster)

    if output_name is None:
        output_service_name = 'RasterToFeature_' + _id_generator()
        output_name = output_service_name.replace(' ', '_')
    else:
        output_service_name = output_name.replace(' ', '_')

    output_service = _create_output_feature_service(gis, output_name, output_service_name, 'Convert Raster To Feature')

    params["outputName"] = _json.dumps({"serviceProperties": {"name": output_service_name, "serviceUrl": output_service.url},
                                       "itemProperties": {"itemId": output_service.itemid}})
    if field is not None:
        params["field"] = field
    if output_type is not None:
        params["outputType"] = output_type
    if simplify is not None:
        params["simplifyLinesOrPolygons"] = simplify
    _set_context(params)


    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service

def calculate_density(input_point_or_line_features,
                      count_field=None,
                      search_distance=None,
                      output_area_units=None,
                      output_cell_size=None,
                      output_name=None,
                      gis=None):
    """
    Density analysis takes known quantities of some phenomenon and creates a density map by spreading
    these quantities across the map. You can use this tool, for example, to show concentrations of
    lightning strikes or tornadoes, access to health care facilities, and population densities.

    This tool creates a density map from point or line features by spreading known quantities of some
    phenomenon (represented as attributes of the points or lines) across the map. The result is a
    layer of areas classified from least dense to most dense.

    For point input, each point should represent the location of some event or incident, and the
    result layer represents a count of the incident per unit area. A larger density value in a new
    location means that there are more points near that location. In many cases, the result layer can
    be interpreted as a risk surface for future events. For example, if the input points represent
    locations of lightning strikes, the result layer can be interpreted as a risk surface for future
    lightning strikes.

    For line input, the line density surface represents the total amount of line that is near each
    location. The units of the calculated density values are the length of line-per-unit area.
    For example, if the lines represent rivers, the result layer will represent the total length
    of rivers that are within the search radius. This result can be used to identify areas that are
    hospitable to grazing animals.

    Other use cases of this tool include the following:

    *   Creating crime density maps to help police departments properly allocate resources to high crime
        areas.
    *   Calculating densities of hospitals within a county. The result layer will show areas with
        high and low accessibility to hospitals, and this information can be used to decide where
        new hospitals should be built.
    *   Identifying areas that are at high risk of forest fires based on historical locations of
        forest fires.
    *   Locating communities that are far from major highways in order to plan where new roads should
        be constructed.

    Parameters
    ----------
    input_point_or_line_features : Required feature layer - The input point or line layer that will be used to calculate
        the density layer.

    count_field : Optional string - count field
        Provide a field specifying the number of incidents at each location. For example, if you have points that
        represent cities, you can use a field representing the population of the city as the count field, and the
        resulting population density layer will calculate larger population densities near cities with
        larger populations. If the default choice of None is used, then each location will be assumed to represent a
        single count.

    search_distance : Optional LinearUnit - Search distance
        Enter a distance specifying how far to search to find point or line features when calculating density values.
        For example, if you provide a search distance of 10,000 meters, the density of any location in the output layer
        is calculated based on features that are within 10,000 meters of the location. Any location that does not have
        any incidents within 10,000 meters will receive a density value of zero.
        If no distance is provided, a default will be calculated that is based on the locations of the input features
        and the values in the count field (if a count field is provided).

    output_area_units : Optional string - Output area units
        Specify the output area unit. Density is count divided by area, and this parameter specifies the unit of the
        area in the density calculation. The available areal units are Square Miles and Square Kilometers.

    output_cell_size : Optional LinearUnit - Output cell size
        Enter the cell size and unit for the output rasters.

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item 
    """

    task = "CalculateDensity"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_service = None

    if output_name is None:
        output_name = task + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
    else:
        raise TypeError("output_raster should be a string (service name) or Item")

    params = {}

    output_raster = _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 
    params["outputName"] = output_raster


    params["inputPointOrLineFeatures"] = _layer_input(input_point_or_line_features)

    if count_field is not None:
        params["countField"] = count_field
    if search_distance is not None:
        params["searchDistance"] = search_distance
    if output_area_units is not None:
        params["outputAreaUnits"] = output_area_units
    if output_cell_size is not None:
        params["outputCellSize"] = output_cell_size
    _set_context(params)


    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def create_viewshed(input_elevation_surface,
                    input_observer_features,
                    optimize_for=None,
                    maximum_viewing_distance=None,
                    maximum_viewing_distance_field=None,
                    minimum_viewing_distance=None,
                    minimum_viewing_distance_field=None,
                    viewing_distance_is_3d=None,
                    observers_elevation=None,
                    observers_elevation_field=None,
                    observers_height=None,
                    observers_height_field=None,
                    target_height=None,
                    target_height_field=None,
                    above_ground_level_output_name=None,
                    output_name=None,
                    gis=None):
    """
    Compute visibility for an input elevation raster using geodesic method.

    Parameters
    ----------
    input_elevation_surface : Required string

    input_observer_features : Required FeatureSet

    optimize_for : Optional string
        One of the following: ['SPEED', 'ACCURACY']
    maximum_viewing_distance : Optional LinearUnit

    maximum_viewing_distance_field : Optional string

    minimum_viewing_distance : Optional LinearUnit

    minimum_viewing_distance_field : Optional string

    viewing_distance_is_3d : Optional bool

    observers_elevation : Optional LinearUnit

    observers_elevation_field : Optional string

    observers_height : Optional LinearUnit

    observers_height_field : Optional string

    target_height : Optional LinearUnit

    target_height_field : Optional string

    above_ground_level_output_name : Optional string

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    dict with the following keys:
       "output_raster" : layer
       "output_above_ground_level_raster" : layer
    """

    task = "CreateViewshed"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_service = None

    if output_name is None:
        output_name = task + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
    else:
        raise TypeError("output_raster should be a string (service name) or Item")

    params = {}

    output_raster = _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 
    params["outputName"] = output_raster


    params["inputElevationSurface"] = _layer_input(input_elevation_surface)
    params["inputObserverFeatures"] = _layer_input(input_observer_features)

    if optimize_for is not None:
        params["optimizeFor"] = optimize_for
    if maximum_viewing_distance is not None:
        params["maximumViewingDistance"] = maximum_viewing_distance
    if maximum_viewing_distance_field is not None:
        params["maximumViewingDistanceField"] = maximum_viewing_distance_field
    if minimum_viewing_distance is not None:
        params["minimumViewingDistance"] = minimum_viewing_distance
    if minimum_viewing_distance_field is not None:
        params["minimumViewingDistanceField"] = minimum_viewing_distance_field
    if viewing_distance_is_3d is not None:
        params["viewingDistanceIs3D"] = viewing_distance_is_3d
    if observers_elevation is not None:
        params["observersElevation"] = observers_elevation
    if observers_elevation_field is not None:
        params["observersElevationField"] = observers_elevation_field
    if observers_height is not None:
        params["observersHeight"] = observers_height
    if observers_height_field is not None:
        params["observersHeightField"] = observers_height_field
    if target_height is not None:
        params["targetHeight"] = target_height
    if target_height_field is not None:
        params["targetHeightField"] = target_height_field
    if above_ground_level_output_name is not None:
        params["aboveGroundLevelOutputName"] = above_ground_level_output_name
    _set_context(params)


    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    # print(job_values)
    if output_name is not None:
        # url = job_values['output']['url']
        # return FeatureLayer(url, self._gis) #item
        item_properties = {
            "properties": {
                "jobUrl": task_url + '/jobs/' + job_info['jobId'],
                "jobType": "GPServer",
                "jobId": job_info['jobId'],
                "jobStatus": "completed"
            }
        }
        output_service.update(item_properties)
        return output_service
    else:
        # Feature Collection

        output_raster = job_values['outputRaster']

        output_above_ground_level_raster = job_values['outputAboveGroundLevelRaster']
        return {"output_raster": output_raster, "output_above_ground_level_raster": output_above_ground_level_raster, }


def interpolate_points(input_point_features,
                       interpolate_field,
                       optimize_for="BALANCE",
                       transform_data=False,
                       size_of_local_models=None,
                       number_of_neighbors=None,
                       output_cell_size=None,
                       output_prediction_error=False,
                       output_name=None,
                       gis=None):
    """
    This tool allows you to predict values at new locations based on measurements from a collection of points. The tool
    takes point data with values at each point and returns a raster of predicted values:

    * An air quality management district has sensors that measure pollution levels. Interpolate Points can be used to
        predict pollution levels at locations that don't have sensors, such as locations with at-risk populations-
        schools or hospitals, for example.
    * Predict heavy metal concentrations in crops based on samples taken from individual plants.
    * Predict soil nutrient levels (nitrogen, phosphorus, potassium, and so on) and other indicators (such as electrical
        conductivity) in order to study their relationships to crop yield and prescribe precise amounts of fertilizer
        for each location in the field.
    * Meteorological applications include prediction of temperatures, rainfall, and associated variables (such as acid
        rain).

    Parameters
    ----------
    input_point_features : Required point layer containing locations with known values
        The point layer that contains the points where the values have been measured.

    interpolate_field : Required string -  field to interpolate
        Choose the field whose values you wish to interpolate. The field must be numeric.

    optimize_for : Optional string - Choose your preference for speed versus accuracy.
        More accurate predictions take longer to calculate. This parameter alters the default values of several other
        parameters of Interpolate Points in order to optimize speed of calculation, accuracy of results, or a balance of
        the two. By default, the tool will optimize for balance.
        One of the following: ['SPEED', 'BALANCE', 'ACCURACY']

    transform_data : Optional bool - Choose whether to transform your data to the normal distribution.
        Interpolation is most accurate for data that follows a normal (bell-shaped) distribution. If your data does not
        appear to be normally distributed, you should perform a transformation.

    size_of_local_models : Optional int - Size of local models
        Interpolate Points works by building local interpolation models that are mixed together to create the final
        prediction map. This parameter controls how many points will be contained in each local model. Smaller values
        will make results more local and can reveal small-scale effects, but it may introduce some instability in the
        calculations. Larger values will be more stable, but some local effects may be missed.
        The value can range from 30 to 500, but typical values are between 50 and 200.

    number_of_neighbors : Optional int - Number of Neighbors
        Predictions are calculated based on neighboring points. This parameter controls how many points will be used in
        the calculation. Using a larger number of neighbors will generally produce more accurate results, but the
        results take longer to calculate.
        This value can range from 1 to 64, but typical values are between 5 and 15.

    output_cell_size : Optional LinearUnit - Output cell size
        Enter the cell size and unit for the output rasters.
        The available units are Feet, Miles, Meters, and Kilometers.

    output_prediction_error : Optional bool - Output prediction error
        Choose whether you want to create a raster of standard errors for the predicted values.
        Standard errors are useful because they provide information about the reliability of the predicted values.
        A simple rule of thumb is that the true value will fall within two standard errors of the predicted value 95
        percent of the time. For example, suppose a new location gets a predicted value of 50 with a standard error of
        5. This means that this tool's best guess is that the true value at that location is 50, but it reasonably could
        be as low as 40 or as high as 60. To calculate this range of reasonable values, multiply the standard error by
        2, add this value to the predicted value to get the upper end of the range, and subtract it from the predicted
        value to get the lower end of the range.

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    dict with the following keys:
       "output_raster" : layer
       "output_error_raster" : layer
       "process_info" : layer
    """

    task = "InterpolatePoints"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)
    output_service = None

    if output_name is None:
        output_name = task + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
    else:
        raise TypeError("output_raster should be a string (service name) or Item")

    params = {}

    output_raster = _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 
    params["outputName"] = output_raster


    params["inputPointFeatures"] = _layer_input(input_point_features)
    params["interpolateField"] = interpolate_field

    if optimize_for is not None:
        params["optimizeFor"] = optimize_for
    if transform_data is not None:
        params["transformData"] = transform_data
    if size_of_local_models is not None:
        params["sizeOfLocalModels"] = size_of_local_models
    if number_of_neighbors is not None:
        params["numberOfNeighbors"] = number_of_neighbors
    if output_cell_size is not None:
        params["outputCellSize"] = output_cell_size
    if output_prediction_error is not None:
        params["outputPredictionError"] = output_prediction_error
    _set_context(params)


    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    # print(job_values)
    # if output_name is not None:
        # url = job_values['output']['url']
        # return FeatureLayer(url, self._gis) #item
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)


    #return output_service

    output_raster = output_service

    output_error_raster = job_values['outputErrorRaster']

    process_info = job_values['processInfo']

    return {"output_raster": output_raster, "output_error_raster": output_error_raster,
            "process_info": process_info, }


def classify(input_raster,
             input_classifier_definition,
             additional_input_raster=None,
             output_name=None,
             gis=None):
    """


    Parameters
    ----------
    input_raster : Required string

    input_classifier_definition : Required string

    additional_input_raster : Optional string

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.


    Returns
    -------
    output_raster : Image layer item 
    """

    task = "Classify"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_service = None

    if output_name is None:
        output_name = task + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
    else:
        raise TypeError("output_raster should be a string (service name) or Item")

    params = {}

    output_raster = _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 
    params["outputName"] = output_raster


    params["inputRaster"] = _layer_input(input_raster)
    params["inputClassifierDefinition"] = input_classifier_definition

    if additional_input_raster is not None:
        params["additionalInputRaster"] = _layer_input(additional_input_raster)

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def segment(input_raster,
            spectral_detail="15.5",
            spatial_detail="15",
            minimum_segment_size_in_pixels="20",
            band_indexes="0,1,2",
            remove_tiling_artifacts="false",
            output_name=None,
            gis=None):
    """


    Parameters
    ----------
    input_raster : Required string

    spectral_detail : Required string

    spatial_detail : Required string

    minimum_segment_size_in_pixels : Required string

    band_indexes : Required string

    remove_tiling_artifacts : Required string

    output_name : Optional. If not provided, an Image Service is created by the method and used as the output raster.
        You can pass in an existing Image Service Item from your GIS to use that instead.
        Alternatively, you can pass in the name of the output Image Service that should be created by this method to be used as the output for the tool.
        A RuntimeError is raised if a service by that name already exists

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_raster : Image layer item 
    """

    task = "Segment"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    output_service = None

    if output_name is None:
        output_name = task + '_' + _id_generator()
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, str):
        output_service = _create_output_image_service(gis, output_name, task)
    elif isinstance(output_name, _arcgis.gis.Item):
        output_service = output_name
    else:
        raise TypeError("output_raster should be a string (service name) or Item")

    params = {}

    output_raster = _json.dumps({"serviceProperties": {"name" : output_name, "serviceUrl" : output_service.url}, "itemProperties": {"itemId" : output_service.itemid}}) 
    params["outputName"] = output_raster


    params["inputRaster"] = _layer_input(input_raster)

    params["spectralDetail"] = spectral_detail
    params["spatialDetail"] = spatial_detail
    params["minimumSegmentSizeInPixels"] = minimum_segment_size_in_pixels
    params["bandIndexes"] = band_indexes
    params["removeTilingArtifacts"] = remove_tiling_artifacts

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    item_properties = {
        "properties": {
            "jobUrl": task_url + '/jobs/' + job_info['jobId'],
            "jobType": "GPServer",
            "jobId": job_info['jobId'],
            "jobStatus": "completed"
        }
    }
    output_service.update(item_properties)
    return output_service


def train_classifier(input_raster,
                     input_training_sample_json,
                     classifier_parameters,
                     segmented_raster=None,
                     segment_attributes="COLOR;MEAN",
                     gis=None):
    """


    Parameters
    ----------
    input_raster : Required string

    input_training_sample_json : Required string

    segmented_raster : Optional string

    classifier_parameters : Required string

    segment_attributes : Required string

    gis: Optional, the GIS on which this tool runs. If not specified, the active GIS is used.

    Returns
    -------
    output_classifier_definition
    """

    task = "TrainClassifier"

    gis = _arcgis.env.active_gis if gis is None else gis
    url = gis.properties.helperServices.rasterAnalytics.url
    gptool = _arcgis.gis._GISResource(url, gis)

    params = {}

    params["inputRaster"] = _layer_input(input_raster)
    params["inputTrainingSampleJSON"] = input_training_sample_json
    if segmented_raster is not None:
        params["segmentedRaster"] = _layer_input(segmented_raster)
    params["classifierParameters"] = classifier_parameters
    params["segmentAttributes"] = segment_attributes

    task_url, job_info, job_id = _analysis_job(gptool, task, params)

    job_info = _analysis_job_status(gptool, task_url, job_info)
    job_values = _analysis_job_results(gptool, task_url, job_info, job_id)
    # print(job_values)
    return job_values['outputClassifierDefinition']