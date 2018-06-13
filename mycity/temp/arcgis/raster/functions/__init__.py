"""
Raster functions allow you to define processing operations that will be applied to one or more rasters.
These functions are applied to the raster data on the fly as the data is accessed and viewed; therefore,
they can be applied quickly without having to endure the time it would otherwise take to create a
processed product on disk, for which raster analytics tools like arcgis.raster.analytics.generate_raster can be used.

Functions can be applied to various rasters (or images), including the following:

* Imagery layers
* Rasters within imagery layers

"""
# Raster dataset layers
# Mosaic datasets
# Rasters within mosaic datasets
from .._layer import ImageryLayer
from .utility import _raster_input, _get_raster, _replace_raster_url, _get_raster_url, _get_raster_ra
from arcgis.gis import Item
import copy
import numbers
from . import gbl

#
# def _raster_input(raster):
#
#     if isinstance(raster, ImageryLayer):
#         layer = raster
#         raster = raster._fn #filtered_rasters()
#     # elif isinstance(raster, dict) and 'function_chain' in raster:
#     #     layer = raster['layer']
#     #     raster = raster['function_chain']
#     elif isinstance(raster, list):
#         r0 = raster[0]
#         if 'function_chain' in r0:
#             layer = r0['layer']
#             raster = [r['function_chain'] for r in raster]
#     else:
#         layer = None
#
#     return layer, raster


def _clone_layer(layer, function_chain, raster_ra, raster_ra2=None, variable_name='Raster'):
    if isinstance(layer, Item):
        layer = layer.layers[0]

    function_chain_ra = copy.deepcopy(function_chain)
    function_chain_ra['rasterFunctionArguments'][variable_name] = raster_ra
    if raster_ra2 is not None:
        function_chain_ra['rasterFunctionArguments']['Raster2'] = raster_ra2    
    newlyr = ImageryLayer(layer._url, layer._gis)

    newlyr._lazy_properties = layer.properties
    newlyr._hydrated = True
    newlyr._lazy_token = layer._token

    # if layer._fn is not None: # chain the functions
    #     old_chain = layer._fn
    #     newlyr._fn = function_chain
    #     newlyr._fn['rasterFunctionArguments']['Raster'] = old_chain
    # else:
    newlyr._fn = function_chain
    newlyr._fnra = function_chain_ra

    newlyr._where_clause = layer._where_clause
    newlyr._spatial_filter = layer._spatial_filter
    newlyr._temporal_filter = layer._temporal_filter
    newlyr._mosaic_rule = layer._mosaic_rule
    newlyr._filtered = layer._filtered
    newlyr._extent = layer._extent
    newlyr._uses_gbl_function = layer._uses_gbl_function

    return newlyr

def _clone_layer_pansharpen(layer, function_chain, function_chain_ra):
    if isinstance(layer, Item):
        layer = layer.layers[0]
      
    newlyr = ImageryLayer(layer._url, layer._gis)

    newlyr._lazy_properties = layer.properties
    newlyr._hydrated = True
    newlyr._lazy_token = layer._token

    # if layer._fn is not None: # chain the functions
    #     old_chain = layer._fn
    #     newlyr._fn = function_chain
    #     newlyr._fn['rasterFunctionArguments']['Raster'] = old_chain
    # else:
    newlyr._fn = function_chain
    newlyr._fnra = function_chain_ra

    newlyr._where_clause = layer._where_clause
    newlyr._spatial_filter = layer._spatial_filter
    newlyr._temporal_filter = layer._temporal_filter
    newlyr._mosaic_rule = layer._mosaic_rule
    newlyr._filtered = layer._filtered
    newlyr._extent = layer._extent
    newlyr._uses_gbl_function = layer._uses_gbl_function

    return newlyr


def arg_statistics(rasters, stat_type=None, min_value=None, max_value=None, undefined_class=None, astype=None):
    """
    The arg_statistics function produces an output with a pixel value that represents a statistical metric from all
    bands of input rasters. The statistics can be the band index of the maximum, minimum, or median value, or the
    duration (number of bands) between a minimum and maximum value

    See http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/argstatistics-function.htm

    :param rasters: the imagery layers filtered by where clause, spatial and temporal filters
    :param stat_type: one of "max", "min", "median", "duration"
    :param min_value: double, required if the type is duration
    :param max_value: double, required if the type is duration
    :param undefined_class: int, required if the type is maximum or minimum
    :return: the output raster with this function applied to it
    """
    # find oids given spatial and temporal filter and where clause

    layer, raster, raster_ra = _raster_input(rasters)

    stat_types = {
        'max': 0,
        'min': 1,
        'median': 2,
        'duration': 3
    }
        
    template_dict = {
        "rasterFunction": "ArgStatistics",
        "rasterFunctionArguments": {            
            "Rasters": raster,
        },
        "variableName": "Rasters"
    }

    if stat_type is not None:       
        template_dict["rasterFunctionArguments"]['ArgStatisticsType'] = stat_types[stat_type.lower()]
    if min_value is not None:
        template_dict["rasterFunctionArguments"]['MinValue'] = min_value
    if max_value is not None:
        template_dict["rasterFunctionArguments"]['MaxValue'] = max_value
    if undefined_class is not None:
        template_dict["rasterFunctionArguments"]['UndefinedClass'] = undefined_class

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(raster, template_dict, raster_ra, variable_name='Rasters')

def arg_max(rasters, undefined_class=None, astype=None):
    """
    In the ArgMax method, all raster bands from every input raster are assigned a 0-based incremental band index,
    which is first ordered by the input raster index, as shown in the table below, and then by the relative band order
    within each input raster.

    See http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/argstatistics-function.htm

    :param rasters: the imagery layers filtered by where clause, spatial and temporal filters
    :param undefined_class: int, required
    :return: the output raster with this function applied to it
    """
    return arg_statistics(rasters, "max", undefined_class=undefined_class, astype=astype)

def arg_min(rasters, undefined_class=None, astype=None):
    """
    ArgMin is the argument of the minimum, which returns the Band index for which the given pixel attains
    its minimum value.

    See http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/argstatistics-function.htm

    :param rasters: the imagery layers filtered by where clause, spatial and temporal filters
    :param undefined_class: int, required
    :return: the output raster with this function applied to it
    """
    return arg_statistics(rasters, "min", undefined_class=undefined_class, astype=astype)

def arg_median(rasters, undefined_class=None, astype=None):
    """
    The ArgMedian method returns the Band index for which the given pixel attains the median value of values
    from all bands.

    Consider values from all bands as an array. After sorting the array in ascending order, the median is the
    one value separating the lower half of the array from the higher half. More specifically, if the ascend-sorted
    array has n values, the median is the ith (0-based) value, where: i = ( (n-1) / 2 )

    See http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/argstatistics-function.htm

    :param rasters: the imagery layers filtered by where clause, spatial and temporal filters
    :param undefined_class: int, required
    :return: the output raster with this function applied to it
    """
    return arg_statistics(rasters, "median", undefined_class=undefined_class, astype=astype)

def duration(rasters, min_value=None, max_value=None, undefined_class=None, astype=None):
    """
    Returns the duration (number of bands) between a minimum and maximum value.
    The Duration method finds the longest consecutive elements in the array, where each element has a value greater
    than or equal to min_value and less than or equal to max_value, and then returns its length.

    See http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/argstatistics-function.htm

    :param rasters: the imagery layers filtered by where clause, spatial and temporal filters
    :param undefined_class: int, required
    :return: the output raster with this function applied to it
    """
    return arg_statistics(rasters, "max",  min_value=min_value, max_value=max_value,
                          undefined_class=undefined_class, astype=astype)


def arithmetic(raster1, raster2, extent_type="FirstOf", cellsize_type="FirstOf", astype=None, operation_type=1):
    """
    The Arithmetic function performs an arithmetic operation between two rasters or a raster and a scalar, and vice versa.

    :param raster1: the first raster- imagery layers filtered by where clause, spatial and temporal filters
    :param raster2: the 2nd raster - imagery layers filtered by where clause, spatial and temporal filters
    :param extent_type: one of "FirstOf", "IntersectionOf" "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf "MeanOf", "LastOf"
    :param operation_type: int 1 = Plus, 2 = Minus, 3 = Multiply, 4=Divide, 5=Power, 6=Mode
    :return: the output raster with this function applied to it
    """

    layer1, raster_1, raster_ra1 = _raster_input(raster1)
    layer2, raster_2, raster_ra2 = _raster_input(raster1, raster2)

    layer = layer1 if layer1 is not None else layer2

    extent_types = {
        "FirstOf" : 0,
        "IntersectionOf" : 1,
        "UnionOf" : 2,
        "LastOf" : 3
    }

    cellsize_types = {
        "FirstOf" : 0,
        "MinOf" : 1,
        "MaxOf" : 2,
        "MeanOf" : 3,
        "LastOf" : 4
    }

    in_extent_type = extent_types[extent_type]
    in_cellsize_type = cellsize_types[cellsize_type]

    template_dict = {
        "rasterFunction": "Arithmetic",
        "rasterFunctionArguments": {
            "OperationType": operation_type,
            "Raster": raster_1,
            "Raster2": raster_2
        }
    }

    if in_extent_type is not None:
        template_dict["rasterFunctionArguments"]['ExtentType'] = in_extent_type
    if in_cellsize_type is not None:
        template_dict["rasterFunctionArguments"]['CellsizeType'] = in_cellsize_type

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra1, raster_ra2)

#
#
# def plus(raster1, raster2, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
#     """
#     Adds two rasters or a raster and a scalar, and vice versa
#
#     :param raster1: the first raster- imagery layers filtered by where clause, spatial and temporal filters
#     :param raster2: the 2nd raster - imagery layers filtered by where clause, spatial and temporal filters
#     :param extent_type: one of "FirstOf", "IntersectionOf" "UnionOf", "LastOf"
#     :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf "MeanOf", "LastOf"
#     :return: the output raster with this function applied to it
#     """
#
#     return arithmetic(raster1, raster2, extent_type, cellsize_type, astype, 1)
#
# def minus(raster1, raster2, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
#     """
#     Subtracts a raster or a scalar from another raster or a scaler
#
#     :param raster1: the first raster- imagery layers filtered by where clause, spatial and temporal filters
#     :param raster2: the 2nd raster - imagery layers filtered by where clause, spatial and temporal filters
#     :param extent_type: one of "FirstOf", "IntersectionOf" "UnionOf", "LastOf"
#     :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf "MeanOf", "LastOf"
#     :return: the output raster with this function applied to it
#     """
#
#     return arithmetic(raster1, raster2, extent_type, cellsize_type, astype, 2)
#
# def multiply(raster1, raster2, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
#     """
#     Multiplies two rasters or a raster and a scalar, and vice versa
#
#     :param raster1: the first raster- imagery layers filtered by where clause, spatial and temporal filters
#     :param raster2: the 2nd raster - imagery layers filtered by where clause, spatial and temporal filters
#     :param extent_type: one of "FirstOf", "IntersectionOf" "UnionOf", "LastOf"
#     :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf "MeanOf", "LastOf"
#     :return: the output raster with this function applied to it
#     """
#
#     return arithmetic(raster1, raster2, extent_type, cellsize_type, astype, 3)
#
# def divide(raster1, raster2, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
#     """
#     Divides two rasters or a raster and a scalar, and vice versa
#
#     :param raster1: the first raster- imagery layers filtered by where clause, spatial and temporal filters
#     :param raster2: the 2nd raster - imagery layers filtered by where clause, spatial and temporal filters
#     :param extent_type: one of "FirstOf", "IntersectionOf" "UnionOf", "LastOf"
#     :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf "MeanOf", "LastOf"
#     :return: the output raster with this function applied to it
#     """
#
#     return arithmetic(raster1, raster2, extent_type, cellsize_type, astype, 4)
#
# def power(raster1, raster2, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
#     """
#     Adds two rasters or a raster and a scalar, and vice versa
#
#     :param raster1: the first raster- imagery layers filtered by where clause, spatial and temporal filters
#     :param raster2: the 2nd raster - imagery layers filtered by where clause, spatial and temporal filters
#     :param extent_type: one of "FirstOf", "IntersectionOf" "UnionOf", "LastOf"
#     :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf "MeanOf", "LastOf"
#     :return: the output raster with this function applied to it
#     """
#
#     return arithmetic(raster1, raster2, extent_type, cellsize_type, astype, 5)
#
# def mode(raster1, raster2, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
#     """
#     Adds two rasters or a raster and a scalar, and vice versa
#
#     :param raster1: the first raster- imagery layers filtered by where clause, spatial and temporal filters
#     :param raster2: the 2nd raster - imagery layers filtered by where clause, spatial and temporal filters
#     :param extent_type: one of "FirstOf", "IntersectionOf" "UnionOf", "LastOf"
#     :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf "MeanOf", "LastOf"
#     :return: the output raster with this function applied to it
#     """
#
#     return arithmetic(raster1, raster2, extent_type, cellsize_type, astype, 6)
#

def aspect(raster):
    """
    aspect identifies the downslope direction of the maximum rate of change in value from each cell to its neighbors.
    Aspect can be thought of as the slope direction. The values of the output raster will be the compass direction of
    the aspect. For more information, see
    <a href="http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/aspect-function.htm">Aspect function</a>
    and <a href="http://desktop.arcgis.com/en/arcmap/latest/tools/spatial-analyst-toolbox/how-aspect-works.htm">How Aspect works</a>.

    :param raster: the input raster / imagery layer
    :return: aspect applied to the input raster
    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "Aspect",
        "rasterFunctionArguments": {
            "Raster" : raster,
        }
    }

    return _clone_layer(layer, template_dict, raster_ra)


def band_arithmetic(raster, band_indexes=None, astype=None, method=0):
    """
    The band_arithmetic function performs an arithmetic operation on the bands of a raster. For more information,
    see Band Arithmetic function at http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/band-arithmetic-function.htm

    :param raster: the input raster / imagery layer
    :param band_indexes: band indexes or expression
    :param astype: output pixel type
    :param method: int (0 = UserDefined, 1 = NDVI, 2 = SAVI, 3 = TSAVI, 4 = MSAVI, 5 = GEMI, 6 = PVI, 7 = GVITM, 8 = Sultan)
    :return: band_arithmetic applied to the input raster
    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "BandArithmetic",
        "rasterFunctionArguments": {
            "Method": method,
            "BandIndexes": band_indexes,
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra)

def ndvi(raster, band_indexes="4 3", astype=None):
    """
    Normalized Difference Vegetation Index
    NDVI = ((NIR - Red)/(NIR + Red))

    :param raster: the input raster / imagery layer
    :param band_indexes: Band Indexes "NIR Red", e.g., "4 3"
    :param astype: output pixel type
    :return: Normalized Difference Vegetation Index raster
    """
    return band_arithmetic(raster, band_indexes, astype, 1)

def savi(raster, band_indexes="4 3 0.33", astype=None):
    """
    Soil-Adjusted Vegetation Index
    SAVI = ((NIR - Red) / (NIR + Red + L)) x (1 + L)
    where L represents amount of green vegetative cover, e.g., 0.5

    :param raster: the input raster / imagery layer
    :param band_indexes: "BandIndexes": "NIR Red L", for example, "4 3 0.33"
    :param astype: output pixel type
    :return: output raster
    """
    return band_arithmetic(raster, band_indexes, astype, 2)

def tsavi(raster, band_indexes= "4 3 0.33 0.50 1.50", astype=None):
    """
    Transformed Soil Adjusted Vegetation Index
    TSAVI = (s(NIR-s*Red-a))/(a*NIR+Red-a*s+X*(1+s^2))

    :param raster: the input raster / imagery layer
    :param band_indexes: "NIR Red s a X", e.g., "4 3 0.33 0.50 1.50" where a = the soil line intercept, s = the soil line slope, X = an adjustment factor that is set to minimize soil noise
    :param astype: output pixel type
    :return: output raster
    """
    return band_arithmetic(raster, band_indexes, astype, 3)

def msavi(raster, band_indexes="4 3", astype=None):
    """
    Modified Soil Adjusted Vegetation Index
    MSAVI2 = (1/2)*(2(NIR+1)-sqrt((2*NIR+1)^2-8(NIR-Red)))

    :param raster: the input raster / imagery layer
    :param band_indexes: "NIR Red", e.g., "4 3"
    :param astype: output pixel type
    :return: output raster
    """
    return band_arithmetic(raster, band_indexes, astype, 4)

def gemi(raster, band_indexes="4 3", astype=None):
    """
    Global Environmental Monitoring Index
    GEMI = eta*(1-0.25*eta)-((Red-0.125)/(1-Red))
    where eta = (2*(NIR^2-Red^2)+1.5*NIR+0.5*Red)/(NIR+Red+0.5)

    :param raster: the input raster / imagery layer
    :param band_indexes:"NIR Red", e.g., "4 3"
    :param astype: output pixel type
    :return: output raster
    """
    return band_arithmetic(raster, band_indexes, astype, 5)

def pvi(raster, band_indexes="4 3 0.3 0.5", astype=None):
    """
    Perpendicular Vegetation Index
    PVI = (NIR-a*Red-b)/(sqrt(1+a^2))

    :param raster: the input raster / imagery layer
    :param band_indexes:"NIR Red a b", e.g., "4 3 0.3 0.5"
    :param astype: output pixel type
    :return: output raster
    """
    return band_arithmetic(raster, band_indexes, astype, 6)

def gvitm(raster, band_indexes= "1 2 3 4 5 6", astype=None):
    """
    Green Vegetation Index - Landsat TM
    GVITM = -0.2848*Band1-0.2435*Band2-0.5436*Band3+0.7243*Band4+0.0840*Band5-1.1800*Band7

    :param raster: the input raster / imagery layer
    :param band_indexes:"NIR Red", e.g., "4 3"
    :param astype: output pixel type
    :return: output raster
    """
    return band_arithmetic(raster, band_indexes, astype, 7)

def sultan(raster, band_indexes="1 2 3 4 5 6", astype=None):
    """
    Sultan's Formula (transform to 3 band 8 bit image)
        Band 1 = (Band5 / Band6) x 100
        Band 2 = (Band5 / Band1) x 100
        Band 3 = (Band3 / Band4) x (Band5 / Band4) x 100

    :param raster: the input raster / imagery layer
    :param band_indexes:"Band1 Band2 Band3 Band4 Band5 Band6", e.g., "1 2 3 4 5 6"
    :param astype: output pixel type
    :return: output raster
    """
    return band_arithmetic(raster, band_indexes, astype, 8)

def expression(raster, expression="(B3 - B1 / B3 + B1)", astype=None):
    """
    Use a single-line algebraic formula to create a single-band output. The supported operators are -, +, /, *, and unary -.
    To identify the bands, prepend the band number with a B or b. For example: "BandIndexes":"(B1 + B2) / (B3 * B5)"

    :param raster: the input raster / imagery layer
    :param expression: the algebric formula
    :param astype: output pixel type
    :return: output raster
    :return:
    """
    return band_arithmetic(raster, expression, astype, 0)

def classify(raster1, raster2=None, classifier_definition=None, astype=None):
    """
    classifies a segmented raster to a categorical raster.

    :param raster1: the first raster - imagery layers filtered by where clause, spatial and temporal filters
    :param raster2: Optional segmentation raster -  If provided, pixels in each segment will get same class assignments. 
                    imagery layers filtered by where clause, spatial and temporal filters
    :param classifier_definition: the classifier parameters as a Python dictionary / json format

    :return: the output raster with this function applied to it
    """

    layer1, raster_1, raster_ra1 = _raster_input(raster1)
    if raster2 is not None:
        layer2, raster_2, raster_ra2 = _raster_input(raster1, raster2)

    layer = layer1 if layer1 is not None else layer2

    template_dict = {
        "rasterFunction": "Classify",
        "rasterFunctionArguments": {
            "ClassifierDefinition": classifier_definition,
            "Raster": raster_1
        }
    }
    if classifier_definition is None:
        raise RuntimeError("classifier_definition cannot be empty")
    template_dict["rasterFunctionArguments"]["ClassifierDefinition"] = classifier_definition

    if raster2 is not None:
        template_dict["rasterFunctionArguments"]["Raster2"] = raster_2

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if raster2 is not None:
        return _clone_layer(layer, template_dict, raster_ra1, raster_ra2)
    return _clone_layer(layer, template_dict, raster_ra1)

def clip(raster, geometry=None, clip_outside=True, astype=None):
    """
    Clips a raster using a rectangular shape according to the extents defined or will clip a raster to the shape of an
    input polygon. The shape defining the clip can clip the extent of the raster or clip out an area within the raster.

    :param raster: input raster
    :param geometry: clipping geometry
    :param clip_outside: boolean, If True, the imagery outside the extents will be removed, else the imagery within the
            clipping_geometry will be removed.
    :param astype: output pixel type
    :return: the clipped raster
    """
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "Clip",
        "rasterFunctionArguments": {
            "ClippingGeometry": geometry,
            "ClipType": 1 if clip_outside else 2,
            "Raster": raster
        }
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra)


def colormap(raster, colormap_name=None, colormap=None, colorramp=None, astype=None):
    """
    Transforms the pixel values to display the raster data as a color (RGB) image, based on specific colors in
    a color map. For more information, see Colormap function at
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/colormap-function.htm

    :param raster: input raster
    :param colormap_name: colormap name, if one of Random | NDVI | Elevation | Gray
    :param colormap: [
                     [<value1>, <red1>, <green1>, <blue1>], //[int, int, int, int]
                     [<value2>, <red2>, <green2>, <blue2>]
                     ],
    :param colorramp: Can be a string specifiying color ramp name like <Black To White|Yellow To Red|Slope|more..>
                      or a color ramp object. 
                      For more information about colorramp object, see color ramp object at
                      http://resources.arcgis.com/en/help/arcgis-rest-api/#/Color_ramp_objects/02r3000001m0000000/)
    :param astype: output pixel type
    :return: the colorized raster
    """
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "Colormap",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if colormap_name is not None:
        template_dict["rasterFunctionArguments"]['ColormapName'] = colormap_name
    if colormap is not None:
        template_dict["rasterFunctionArguments"]['Colormap'] = colormap
    if colorramp is not None and isinstance(colorramp,str):
        template_dict["rasterFunctionArguments"]['ColorrampName'] = colorramp
    if colorramp is not None and isinstance(colorramp, dict):
        template_dict["rasterFunctionArguments"]['Colorramp'] = colorramp

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra)


def composite_band(rasters, astype=None):
    """
    Combines multiple images to form a multiband image.

    :param rasters: input rasters
    :param astype: output pixel type
    :return: the multiband image
    """
    layer, raster, raster_ra = _raster_input(rasters)

    template_dict = {
        "rasterFunction": "CompositeBand",
        "rasterFunctionArguments": {
            "Rasters": raster
        },
        "variableName": "Rasters"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra, variable_name='Rasters')

def contrast_brightness(raster, contrast_offset=2, brightness_offset=1, astype=None):
    """
    The ContrastBrightness function enhances the appearance of raster data (imagery) by modifying the brightness or
    contrast within the image. This function works on 8-bit input raster only.

    :param raster: input raster
    :param contrast_offset: double, -100 to 100
    :param brightness_offset: double, -100 to 100
    :param astype: pixel type of result raster
    :return: output raster
    """
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
      "rasterFunction" : "ContrastBrightness",
      "rasterFunctionArguments" : {
        "Raster": raster,
        "ContrastOffset" : contrast_offset,
        "BrightnessOffset" : brightness_offset
      },
      "variableName" : "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra)


def convolution(raster, kernel=None, astype=None):
    """
    The Convolution function performs filtering on the pixel values in an image, which can be used for sharpening an
    image, blurring an image, detecting edges within an image, or other kernel-based enhancements. For more information,
     see Convolution function at http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/convolution-function.htm

    :param raster: input raster
    :param kernel: well known kernel from arcgis.raster.kernels or user defined kernel passed as a list of list
    :param astype: pixel type of result raster
    :return: output raster
    """
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
      "rasterFunction" : "Convolution",
      "rasterFunctionArguments" : {
        "Raster": raster,
      },
      "variableName" : "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if (isinstance(kernel, int)):
        template_dict["rasterFunctionArguments"]['Type'] = kernel
    elif (isinstance(kernel, list)):
        numrows = len(kernel)
        numcols = len(kernel[0])
        flattened = [item for sublist in kernel for item in sublist]
        template_dict["rasterFunctionArguments"]['Columns'] = numcols
        template_dict["rasterFunctionArguments"]['Rows'] = numrows
        template_dict["rasterFunctionArguments"]['Kernel'] = flattened
    else:
        raise RuntimeError('Invalid kernel type - pass int or list of list: [[][][]...]')

    return _clone_layer(layer, template_dict, raster_ra)


def curvature(raster, curvature_type='standard', z_factor=1, astype=None):
    """
    The Curvature function displays the shape or curvature of the slope. A part of a surface can be concave or convex;
    you can tell that by looking at the curvature value. The curvature is calculated by computing the second derivative
    of the surface. Refer to this conceptual help on how it works.

    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/curvature-function.htm

    :param raster: input raster
    :param curvature_type: 'standard', 'planform', 'profile'
    :param z_factor: double
    :param astype: output pixel type
    :return: the output raster
    """
    layer, raster, raster_ra = _raster_input(raster)


    curv_types = {
        'standard': 0,
        'planform': 1,
        'profile': 2
    }

    in_curv_type = curv_types[curvature_type.lower()]

    template_dict = {
        "rasterFunction": "Curvature",
        "rasterFunctionArguments": {
            "Raster": raster,
            "Type": in_curv_type,
            "ZFactor": z_factor
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra)


def NDVI(raster, visible_band=2, ir_band=1, astype=None):
    """
    The Normalized Difference Vegetation Index (ndvi) is a standardized index that allows you to generate an image
    displaying greenness (relative biomass). This index takes advantage of the contrast of the characteristics of
    two bands from a multispectral raster dataset the chlorophyll pigment absorptions in the red band and the
    high reflectivity of plant materials in the near-infrared (NIR) band. For more information, see ndvi function.
    The arguments for the ndvi function are as follows:

    :param raster: input raster
    :param visible_band_id: int (zero-based band id, e.g. 2)
    :param infrared_band_id: int (zero-based band id, e.g. 1)
    :param astype: output pixel type
    :return: the output raster
    The following equation is used by the NDVI function to generate a 0 200 range 8 bit result:
    NDVI = ((IR - R)/(IR + R)) * 100 + 100
    If you need the specific pixel values (-1.0 to 1.0), use the lowercase ndvi method.
    """
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
      "rasterFunction" : "NDVI",
      "rasterFunctionArguments" : {
        "Raster": raster,
        "VisibleBandID" : visible_band,
        "InfraredBandID" : ir_band
      },
      "variableName" : "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra)


def elevation_void_fill(raster, max_void_width=0, astype=None):
    """
    The elevation_void_fill function is used to create pixels where holes exist in your elevation. Refer to
    <a href="http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/elevation-void-fill-function.htm">
    this conceptual help</a> on how it works. The arguments for the elevation_void_fill function are as follows:

    :param raster: input raster
    :param max_void_width: number. Maximum void width to fill. 0: fill all
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "ElevationVoidFill",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if max_void_width is not None:
        template_dict["rasterFunctionArguments"]["MaxVoidWidth"] = max_void_width

    return _clone_layer(layer, template_dict, raster_ra)


def extract_band(raster, band_ids=None, band_names=None, band_wavelengths=None, missing_band_action=None,
                 wavelength_match_tolerance=None, astype=None):
    """
    The extract_band function allows you to extract one or more bands from a raster, or it can reorder the bands in a
    multiband image. The arguments for the extract_band function are as follows:

    :param raster: input raster
    :param band_ids: array of int
    :param band_names: array of string
    :param band_wavelengths: array of double
    :param missing_band_action: int, 0 = esriMissingBandActionFindBestMatch, 1 = esriMissingBandActionFail
    :param wavelength_match_tolerance: double
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "ExtractBand",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if band_ids is not None:
        template_dict["rasterFunctionArguments"]["BandIDs"] = band_ids
    if band_names is not None:
        template_dict["rasterFunctionArguments"]["BandNames"] = band_names
    if band_wavelengths is not None:
        template_dict["rasterFunctionArguments"]["BandWavelengths"] = band_wavelengths
    if missing_band_action is not None:
        template_dict["rasterFunctionArguments"]["MissingBandAction"] = missing_band_action
    if wavelength_match_tolerance is not None:
        template_dict["rasterFunctionArguments"]["WavelengthMatchTolerance"] = wavelength_match_tolerance

    return _clone_layer(layer, template_dict, raster_ra)


def geometric(raster, geodata_transforms=None, append_geodata_xform=None, z_factor=None, z_offset=None, constant_z=None,
              correct_geoid=None, astype=None):
    """
    The geometric function transforms the image (for example, orthorectification) based on a sensor definition and a
    terrain model.This function was added at 10.1.The arguments for the geometric function are as follows:

    :param raster: input raster
    :param geodata_transforms: Please refer to the Geodata Transformations documentation for more details.
    :param append_geodata_xform: boolean
    :param z_factor: double
    :param z_offset: double
    :param constant_z: double
    :param correct_geoid: boolean
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "Geometric",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if geodata_transforms is not None:
        template_dict["rasterFunctionArguments"]["GeodataTransforms"] = geodata_transforms
    if append_geodata_xform is not None:
        template_dict["rasterFunctionArguments"]["AppendGeodataXform"] = append_geodata_xform
    if z_factor is not None:
        template_dict["rasterFunctionArguments"]["ZFactor"] = z_factor
    if z_offset is not None:
        template_dict["rasterFunctionArguments"]["ZOffset"] = z_offset
    if constant_z is not None:
        template_dict["rasterFunctionArguments"]["ConstantZ"] = constant_z
    if correct_geoid is not None:
        template_dict["rasterFunctionArguments"]["CorrectGeoid"] = correct_geoid

    return _clone_layer(layer, template_dict, raster_ra)


def hillshade(dem, azimuth=215.0, altitude=75.0, z_factor=0.3, slope_type=1, ps_power=None, psz_factor=None,
              remove_edge_effect=None, astype=None):
    """
    A hillshade is a grayscale 3D model of the surface taking the sun's relative position into account to shade the image.
    For more information, see
    <a href='http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/hillshade-function.htm'>hillshade
    function</a> and <a href="http://desktop.arcgis.com/en/arcmap/latest/tools/spatial-analyst-toolbox/how-hillshade-works.htm">How hillshade works.</a>
    The arguments for the hillshade function are as follows:

    :param dem: input DEM
    :param azimuth: double (e.g. 215.0)
    :param altitude: double (e.g. 75.0)
    :param z_factor: double (e.g. 0.3)
    :param slope_type: new at 10.2. 1=DEGREE, 2=PERCENTRISE, 3=SCALED. default is 1.
    :param ps_power: new at 10.2. double, used together with SCALED slope type
    :param psz_factor: new at 10.2. double, used together with SCALED slope type
    :param remove_edge_effect: new at 10.2. boolean, true of false
    :param astype: output pixel type
    :return: the output raster

    """
    raster = dem

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "Hillshade",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if azimuth is not None:
        template_dict["rasterFunctionArguments"]["Azimuth"] = azimuth
    if altitude is not None:
        template_dict["rasterFunctionArguments"]["Altitude"] = altitude
    if z_factor is not None:
        template_dict["rasterFunctionArguments"]["ZFactor"] = z_factor
    if slope_type is not None:
        template_dict["rasterFunctionArguments"]["SlopeType"] = slope_type
    if ps_power is not None:
        template_dict["rasterFunctionArguments"]["PSPower"] = ps_power
    if psz_factor is not None:
        template_dict["rasterFunctionArguments"]["PSZFactor"] = psz_factor
    if remove_edge_effect is not None:
        template_dict["rasterFunctionArguments"]["RemoveEdgeEffect"] = remove_edge_effect

    return _clone_layer(layer, template_dict, raster_ra)


def local(rasters, operation, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The local function allows you to perform bitwise, conditional, logical, mathematical, and statistical operations on
    a pixel-by-pixel basis. For more information, see
    <a href="http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/local-function.htm">local function</a>.

    License:At 10.5, you must license your ArcGIS Server as ArcGIS Server 10.5.1 Enterprise Advanced or
     ArcGIS Image Server to use this resource.
     At versions prior to 10.5, the hosting ArcGIS Server needs to have a Spatial Analyst license.

    The arguments for the local function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param operation: int see reference at http://resources.arcgis.com/en/help/arcobjects-net/componenthelp/index.html#//004000000149000000
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    # redacted - The local function works on single band or the first band of an image only, and the output is single band.
    raster = rasters

    layer, raster, raster_ra = _raster_input(raster)


    extent_types = {
        "FirstOf" : 0,
        "IntersectionOf" : 1,
        "UnionOf" : 2,
        "LastOf" : 3
    }

    cellsize_types = {
        "FirstOf" : 0,
        "MinOf" : 1,
        "MaxOf" : 2,
        "MeanOf" : 3,
        "LastOf" : 4
    }

    in_extent_type = extent_types[extent_type]
    in_cellsize_type = cellsize_types[cellsize_type]

    template_dict = {
        "rasterFunction": "Local",
        "rasterFunctionArguments": {
            "Rasters": raster
        },
        "variableName": "Rasters"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if operation is not None:
        template_dict["rasterFunctionArguments"]["Operation"] = operation
    if extent_type is not None:
        template_dict["rasterFunctionArguments"]["ExtentType"] = in_extent_type
    if cellsize_type is not None:
        template_dict["rasterFunctionArguments"]["CellsizeType"] = in_cellsize_type

    return _clone_layer(layer, template_dict, raster_ra, variable_name='Rasters')


###############################################  LOCAL FUNCTIONS  ######################################################

def plus(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The binary Plus (addition,+) operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 1, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def minus(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The binary Minus (subtraction,-) operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 2, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def times(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Times (multiplication,*) operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 3, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def sqrt(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Square Root operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 4, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def power(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Power operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 5, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def acos(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The acos operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 6, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def asin(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The asin operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 7, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def atan(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The ATan operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 8, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def atanh(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The ATanH operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 9, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def abs(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Abs operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 10, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def bitwise_and(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BitwiseAnd operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 11, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def bitwise_left_shift(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BitwiseLeftShift operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 12, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def bitwise_not(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BitwiseNot operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 13, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def bitwise_or(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BitwiseOr operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 14, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def bitwise_right_shift(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BitwiseRightShift operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 15, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def bitwise_xor(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BitwiseXOr operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 16, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def boolean_and(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BooleanAnd operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 17, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def boolean_not(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BooleanNot operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 18, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def boolean_or(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BooleanOr operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 19, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def boolean_xor(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The BooleanXOr operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 20, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def cos(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Cos operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 21, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def cosh(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The CosH operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 22, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def divide(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Divide operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 23, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def equal_to(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The EqualTo operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 24, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def exp(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Exp operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 25, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def exp10(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Exp10 operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 26, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def exp2(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Exp2 operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 27, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def greater_than(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The GreaterThan operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 28, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def greater_than_equal(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The GreaterThanEqual operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 29, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def INT(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Int operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 30, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def is_null(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The IsNull operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 31, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def FLOAT(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Float operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 32, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def less_than(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The LessThan operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 33, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def less_than_equal(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The LessThanEqual operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 34, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def ln(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Ln operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 35, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def log10(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Log10 operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 36, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def log2(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Log2 operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 37, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def majority(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False, astype=None):
    """
    The Majority operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param ignore_nodata: True or False, set to True to ignore NoData values
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 66 if ignore_nodata else 38
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def max(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False, astype=None):
    """
    The Max operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 67 if ignore_nodata else 39
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def mean(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False, astype=None):
    """
    The Mean operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param ignore_nodata: True or False, set to True to ignore NoData values
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 68 if ignore_nodata else 40
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def med(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False, astype=None):
    """
    The Med operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param ignore_nodata: True or False, set to True to ignore NoData values
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 69 if ignore_nodata else 41
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def min(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False, astype=None):
    """
    The Min operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param ignore_nodata: True or False, set to True to ignore NoData values
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 70 if ignore_nodata else 42
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def minority(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False, astype=None):
    """
    The Minority operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param ignore_nodata: True or False, set to True to ignore NoData values
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 71 if ignore_nodata else 43
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def mod(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Mod operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 44, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def negate(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Negate operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 45, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def not_equal(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The NotEqual operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 46, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def cellstats_range(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False, astype=None):
    """
    The Range operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param ignore_nodata: True or False, set to True to ignore NoData values
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 72 if ignore_nodata else 47
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def round_down(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The RoundDown operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 48, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def round_up(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The RoundUp operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 49, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def set_null(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The SetNull operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 50, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def sin(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Sin operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 51, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def sinh(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The SinH operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 52, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def square(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Square operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 53, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def std(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False, astype=None):
    """
    The Std operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param ignore_nodata: True or False, set to True to ignore NoData values
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 73 if ignore_nodata else 54
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def sum(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False,  astype=None):
    """
    The Sum operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param ignore_nodata: True or False, set to True to ignore NoData values
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 74 if ignore_nodata else 55
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def tan(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The Tan operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 56, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def tanh(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The TanH operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 57, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def variety(rasters, extent_type="FirstOf", cellsize_type="FirstOf", ignore_nodata=False, astype=None):
    """
    The Variety operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param ignore_nodata: True or False, set to True to ignore NoData values
    :param astype: output pixel type
    :return: the output raster

    """
    opnum = 75 if ignore_nodata else 58
    return local(rasters, opnum, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def acosh(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The ACosH operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 59, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def asinh(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The ASinH operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 60, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def atan2(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The ATan2 operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 61, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def float_divide(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The FloatDivide operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 64, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def floor_divide(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The FloorDivide operation

    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 65, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)


def con(rasters, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The con operation.Performs a conditional if/else evaluation on each of the input cells of an input raster.
	For more information see, http://desktop.arcgis.com/en/arcmap/latest/tools/spatial-analyst-toolbox/con-.htm
    The arguments for this function are as follows:

    :param rasters: array of rasters. If a scalar is needed for the operation, the scalar can be a double or string
    :param extent_type: one of "FirstOf", "IntersectionOf", "UnionOf", "LastOf"
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf, "MeanOf", "LastOf"
    :param astype: output pixel type
    :return: the output raster

    """
    return local(rasters, 78, extent_type=extent_type, cellsize_type=cellsize_type, astype=astype)

###############################################  LOCAL FUNCTIONS  ######################################################


def mask(raster, no_data_values=None, included_ranges=None, no_data_interpretation=None, astype=None):
    """
    The mask function changes the image by specifying a certain pixel value or a range of pixel values as no data.
    The arguments for the mask function are as follows:

    :param raster: input raster
    :param no_data_values: array of string ["band0_val","band1_val",...]
    :param included_ranges: array of double [band0_lowerbound,band0_upperbound,band1...],
    :param no_data_interpretation: int 0=MatchAny, 1=MatchAll
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "Mask",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if no_data_values is not None:
        template_dict["rasterFunctionArguments"]["NoDataValues"] = no_data_values
    if included_ranges is not None:
        template_dict["rasterFunctionArguments"]["IncludedRanges"] = included_ranges
    if no_data_interpretation is not None:
        template_dict["rasterFunctionArguments"]["NoDataInterpretation"] = no_data_interpretation

    return _clone_layer(layer, template_dict, raster_ra)


def ml_classify(raster, signature, astype=None):
    """
    The ml_classify function allows you to perform a supervised classification using the maximum likelihood classification
     algorithm. The hosting ArcGIS Server needs to have a Spatial Analyst license.LicenseLicense:At 10.5, you must license
     your ArcGIS Server as ArcGIS Server 10.5.1 Enterprise Advanced or ArcGIS Image Server to use this resource.
     At versions prior to 10.5, the hosting ArcGIS Server needs to have a Spatial Analyst license.
     The arguments for the ml_classify function are as follows:

    :param raster: input raster
    :param signature: string. a signature string returned from computeClassStatistics (GSG)
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "MLClassify",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if signature is not None:
        template_dict["rasterFunctionArguments"]["SignatureFile"] = signature

    return _clone_layer(layer, template_dict, raster_ra)

# See NDVI() above
# def ndvi(raster, visible_band_id=None, infrared_band_id=None, astype=None):
#     """
#     The Normalized Difference Vegetation Index (ndvi) is a standardized index that allows you to generate an image displaying greenness (relative biomass). This index takes advantage of the contrast of the characteristics of two bands from a multispectral raster dataset the chlorophyll pigment absorptions in the red band and the high reflectivity of plant materials in the near-infrared (NIR) band. For more information, see ndvi function.The arguments for the ndvi function are as follows:
#
#     :param raster: input raster
#     :param visible_band_id: int (zero-based band id, e.g. 2)
#     :param infrared_band_id: int (zero-based band id, e.g. 1)
#     :param astype: output pixel type
#     :return: the output raster
#
#     """
#
#     layer, raster, raster_ra = _raster_input(raster)
#
#     template_dict = {
#         "rasterFunction": "NDVI",
#         "rasterFunctionArguments": {
#             "Raster": raster
#         },
#         "variableName": "Raster"
#     }
#
#     if astype is not None:
#         template_dict["outputPixelType"] = astype.upper()
#
#     if visible_band_id is not None:
#         template_dict["rasterFunctionArguments"]["VisibleBandID"] = visible_band_id
#     if infrared_band_id is not None:
#         template_dict["rasterFunctionArguments"]["InfraredBandID"] = infrared_band_id
#
#     return {
#         'layer': layer,
#         'function_chain': template_dict
#     }

# TODO: how does recast work?
# def recast(raster, < _argument_name1 >= None, < _argument_name2 >= None, astype=None):
#     """
#     The recast function reassigns argument values in an existing function template.The arguments for the recast function are based on the function it is overwriting.
#
#     :param raster: input raster
#     :param <_argument_name1>: ArgumentName1 will be reassigned with ArgumentValue1
#     :param <_argument_name2>: ArgumentName1 will be reassigned with ArgumentValue2
#     :param astype: output pixel type
#     :return: the output raster
#
#     """
#
#     layer, raster, raster_ra = _raster_input(raster)
#
#     template_dict = {
#         "rasterFunction": "Recast",
#         "rasterFunctionArguments": {
#             "Raster": raster
#         },
#         "variableName": "Raster"
#     }
#
#     if astype is not None:
#         template_dict["outputPixelType"] = astype.upper()
#
#     if < _argument_name1 > is not None:
#         template_dict["rasterFunctionArguments"]["<ArgumentName1>"] = < _argument_name1 >
#     if < _argument_name2 > is not None:
#         template_dict["rasterFunctionArguments"]["<ArgumentName2>"] = < _argument_name2 >
#
#     return {
#         'layer': layer,
#         'function_chain': template_dict
#     }


def remap(raster, input_ranges=None, output_values=None, geometry_type=None, geometries=None, no_data_ranges=None,
          allow_unmatched=None, astype=None):
    """
    The remap function allows you to change or reclassify the pixel values of the raster data. For more information,
    see <a href="http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/remap-function.htm">remap function</a>.

    The arguments for the remap function are as follows:

    :param raster: input raster
    :param input_ranges: [double, double,...], input ranges are specified in pairs: from (inclusive) and to (exclusive).
    :param output_values: [double, ...], output values of corresponding input ranges
    :param geometry_type: added at 10.3
    :param geometries: added at 10.3
    :param no_data_ranges: [double, double, ...], nodata ranges are specified in pairs: from (inclusive) and to (exclusive).
    :param allow_unmatched: Boolean, specify whether to keep the unmatched values or turn into nodata.
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "Remap",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if input_ranges is not None:
        template_dict["rasterFunctionArguments"]["InputRanges"] = input_ranges
    if output_values is not None:
        template_dict["rasterFunctionArguments"]["OutputValues"] = output_values
    if geometry_type is not None:
        template_dict["rasterFunctionArguments"]["GeometryType"] = geometry_type
    if geometries is not None:
        template_dict["rasterFunctionArguments"]["Geometries"] = geometries
    if no_data_ranges is not None:
        template_dict["rasterFunctionArguments"]["NoDataRanges"] = no_data_ranges
    if allow_unmatched is not None:
        template_dict["rasterFunctionArguments"]["AllowUnmatched"] = allow_unmatched

    return _clone_layer(layer, template_dict, raster_ra)


def resample(raster, resampling_type=None, input_cellsize=None, output_cellsize=None, astype=None):
    """
    The resample function resamples pixel values from a given resolution.The arguments for the resample function are as follows:

    :param raster: input raster
    :param resampling_type: one of NearestNeighbor,Bilinear,Cubic,Majority,BilinearInterpolationPlus,BilinearGaussBlur,
            BilinearGaussBlurPlus, Average, Minimum, Maximum,VectorAverage(require two bands)
    :param input_cellsize: point that defines cellsize in source spatial reference
    :param output_cellsize: point that defines output cellsize
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)
    resample_types = {
        'NearestNeighbor': 0,
        'Bilinear': 1,
        'Cubic': 2,
        'Majority': 3,
        'BilinearInterpolationPlus': 4,
        'BilinearGaussBlur': 5,
        'BilinearGaussBlurPlus': 6,
        'Average': 7,
        'Minimum': 8,
        'Maximum': 9,
        'VectorAverage':10
    }

    if isinstance(resampling_type, str):
        resampling_type = resample_types[resampling_type]

    template_dict = {
        "rasterFunction": "Resample",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if resampling_type is not None:
        template_dict["rasterFunctionArguments"]["ResamplingType"] = resampling_type
    if input_cellsize is not None:
        template_dict["rasterFunctionArguments"]["InputCellsize"] = input_cellsize
    if output_cellsize is not None:
        template_dict["rasterFunctionArguments"]["OutputCellsize"] = output_cellsize

    return _clone_layer(layer, template_dict, raster_ra)


def segment_mean_shift(raster, spectral_detail=None, spatial_detail=None, spectral_radius=None, spatial_radius=None,
                       min_num_pixels_per_segment=None, astype=None):
    """
    The segment_mean_shift function produces a segmented output. Pixel values in the output image represent the
    converged RGB colors of the segment. The input raster needs to be a 3-band 8-bit image. If the imagery layer is not
    a 3-band 8-bit unsigned image, you can use the Stretch function before the segment_mean_shift function.

    License:At 10.5, you must license your ArcGIS Server as ArcGIS Server 10.5.1 Enterprise Advanced or
    ArcGIS Image Server to use this resource.
    At versions prior to 10.5, the hosting ArcGIS Server needs to have a Spatial Analyst license.

    When specifying arguments for SegmentMeanShift, use either SpectralDetail,SpatialDetail as a pair, or use
    SpectralRadius, SpatialRadius. They have an inverse relationship. SpectralRadius = 21 - SpectralDetail,
    SpatialRadius = 21 - SpectralRadius

    The arguments for the segment_mean_shift function are as follows:

    :param raster: input raster
    :param spectral_detail: double 0-21. Bigger value is faster and has more segments.
    :param spatial_detail: int 0-21. Bigger value is faster and has more segments.
    :param spectral_radius: double. Bigger value is slower and has less segments.
    :param spatial_radius: int. Bigger value is slower and has less segments.
    :param min_num_pixels_per_segment: int
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "SegmentMeanShift",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if spectral_detail is not None:
        template_dict["rasterFunctionArguments"]["SpectralDetail"] = spectral_detail
    if spatial_detail is not None:
        template_dict["rasterFunctionArguments"]["SpatialDetail"] = spatial_detail
    if spectral_radius is not None:
        template_dict["rasterFunctionArguments"]["SpectralRadius"] = spectral_radius
    if spatial_radius is not None:
        template_dict["rasterFunctionArguments"]["SpatialRadius"] = spatial_radius
    if min_num_pixels_per_segment is not None:
        template_dict["rasterFunctionArguments"]["MinNumPixelsPerSegment"] = min_num_pixels_per_segment

    return _clone_layer(layer, template_dict, raster_ra)


def shaded_relief(raster, azimuth=None, altitude=None, z_factor=None, colormap=None, slope_type=None, ps_power=None,
                  psz_factor=None, remove_edge_effect=None, astype=None):
    """
    Shaded relief is a color 3D model of the terrain, created by merging the images from the Elevation-coded and
    Hillshade methods. For more information, see
    <a href="http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/shaded-relief-function.htm">Shaded relief</a> function.

    The arguments for the shaded_relief function are as follows:

    :param raster: input raster
    :param azimuth: double (e.g. 215.0)
    :param altitude: double (e.g. 75.0)
    :param z_factor: double (e.g. 0.3)
    :param colormap: [[<value1>, <red1>, <green1>, <blue1>], [<value2>, <red2>, <green2>, <blue2>]]
    :param slope_type: 1=DEGREE, 2=PERCENTRISE, 3=SCALED. default is 1.
    :param ps_power: double, used together with SCALED slope type
    :param psz_factor: double, used together with SCALED slope type
    :param remove_edge_effect: boolean, True or False
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "ShadedRelief",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if azimuth is not None:
        template_dict["rasterFunctionArguments"]["Azimuth"] = azimuth
    if altitude is not None:
        template_dict["rasterFunctionArguments"]["Altitude"] = altitude
    if z_factor is not None:
        template_dict["rasterFunctionArguments"]["ZFactor"] = z_factor
    if colormap is not None:
        template_dict["rasterFunctionArguments"]["Colormap"] = colormap
    if slope_type is not None:
        template_dict["rasterFunctionArguments"]["SlopeType"] = slope_type
    if ps_power is not None:
        template_dict["rasterFunctionArguments"]["PSPower"] = ps_power
    if psz_factor is not None:
        template_dict["rasterFunctionArguments"]["PSZFactor"] = psz_factor
    if remove_edge_effect is not None:
        template_dict["rasterFunctionArguments"]["RemoveEdgeEffect"] = remove_edge_effect

    return _clone_layer(layer, template_dict, raster_ra)


def slope(dem, z_factor=None, slope_type=None, ps_power=None, psz_factor=None, remove_edge_effect=None,
          astype=None):
    """
    slope represents the rate of change of elevation for each pixel. For more information, see
    <a href="http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/slope-function.htm">slope function</a>
    and <a href="http://desktop.arcgis.com/en/arcmap/latest/tools/spatial-analyst-toolbox/how-slope-works.htm">How slope works</a>.
    The arguments for the slope function are as follows:

    :param dem: input DEM
    :param z_factor: double (e.g. 0.3)
    :param slope_type: new at 10.2. 1=DEGREE, 2=PERCENTRISE, 3=SCALED. default is 1.
    :param ps_power: new at 10.2. double, used together with SCALED slope type
    :param psz_factor: new at 10.2. double, used together with SCALED slope type
    :param remove_edge_effect: new at 10.2. boolean, true of false
    :param astype: output pixel type
    :return: the output raster

    """
    raster = dem

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "Slope",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if z_factor is not None:
        template_dict["rasterFunctionArguments"]["ZFactor"] = z_factor
    if slope_type is not None:
        template_dict["rasterFunctionArguments"]["SlopeType"] = slope_type
    if ps_power is not None:
        template_dict["rasterFunctionArguments"]["PSPower"] = ps_power
    if psz_factor is not None:
        template_dict["rasterFunctionArguments"]["PSZFactor"] = psz_factor
    if remove_edge_effect is not None:
        template_dict["rasterFunctionArguments"]["RemoveEdgeEffect"] = remove_edge_effect
    # if dem is not None:
    #     template_dict["rasterFunctionArguments"]["DEM"] = raster

    return _clone_layer(layer, template_dict, raster_ra)


def focal_statistics(raster, kernel_columns=None, kernel_rows=None, stat_type=None, columns=None, rows=None,
               fill_no_data_only=None, astype=None):
    """
    The focal_statistics function calculates focal statistics for each pixel of an image based on a defined focal neighborhood.
    For more information, see
    <a href="http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/statistics-function.htm">statistics function</a>.
    The arguments for the statistics function are as follows:

    :param raster: input raster
    :param kernel_columns: int (e.g. 3)
    :param kernel_rows: int (e.g. 3)
    :param stat_type: int or string 
					  There are four types of focal statistical functions:
					  1=Min, 2=Max, 3=Mean, 4=StandardDeviation
					  -Min-Calculates the minimum value of the pixels within the neighborhood
				      -Max-Calculates the maximum value of the pixels within the neighborhood
				      -Mean-Calculates the average value of the pixels within the neighborhood. This is the default.
				      -StandardDeviation-Calculates the standard deviation value of the pixels within the neighborhood
    :param columns: int (e.g. 3)
    :param rows: int (e.g. 3)
    :param fill_no_data_only: bool
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    statistics_types = ["Min", "Max", "Mean", "StandardDeviation"]

    template_dict = {
        "rasterFunction": "Statistics",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if kernel_columns is not None:
        template_dict["rasterFunctionArguments"]["KernelColumns"] = kernel_columns
    if kernel_rows is not None:
        template_dict["rasterFunctionArguments"]["KernelRows"] = kernel_rows
    if stat_type is not None: 
        if isinstance(stat_type, str) and stat_type in statistics_types:
            template_dict["rasterFunctionArguments"]['Type'] = stat_type
        elif isinstance(stat_type, int):
            template_dict["rasterFunctionArguments"]['Type'] = stat_type
    if columns is not None:
        template_dict["rasterFunctionArguments"]["Columns"] = columns
    if rows is not None:
        template_dict["rasterFunctionArguments"]["Rows"] = rows
    if fill_no_data_only is not None:
        template_dict["rasterFunctionArguments"]["FillNoDataOnly"] = fill_no_data_only

    return _clone_layer(layer, template_dict, raster_ra)


def stretch(raster, stretch_type=0, min=None, max=None, num_stddev=None, statistics=None,
            dra=None, min_percent=None, max_percent=None, gamma=None, compute_gamma=None, sigmoid_strength_level=None,
            astype=None):
    """
    The stretch function enhances an image through multiple stretch types. For more information, see
    <a href="http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/stretch-function.htm">stretch function</a>.

    Gamma stretch works with all stretch types. The Gamma parameter is needed when UseGamma is set to true. Min and Max
    can be used to define output minimum and maximum. DRA is used to get statistics from the extent in the export_image request.
    ComputeGamma will automatically calculate best gamma value to render exported image based on empirical model.

    Stretch type None does not require other parameters.
    Stretch type StdDev requires NumberOfStandardDeviations, Statistics, or DRA (true).
    Stretch type Histogram (Histogram Equalization) requires the source dataset to have histograms or additional DRA (true).
    Stretch type MinMax requires Statistics or DRA (true).
    Stretch type PercentClip requires MinPercent, MaxPercent, and DRA (true), or histograms from the source dataset.
    Stretch type Sigmoid does not require other parameters.

    Optionally, set the SigmoidStrengthLevel (1 to 6) to adjust the curvature of Sigmoid curve used in color stretch.


    The arguments for the stretch function are as follows:

    :param raster: input raster
    :param stretch_type: str, one of None, StdDev, Histogram, MinMax, PercentClip, 9 = Sigmoid
    :param min: double
    :param max: double
    :param num_stddev: double (e.g. 2.5)
    :param statistics: double (e.g. 2.5)[<min1>, <max1>, <mean1>, <standardDeviation1>], //[double, double, double, double][<min2>, <max2>, <mean2>, <standardDeviation2>]],
    :param dra: boolean. derive statistics from current request, Statistics parameter is ignored when DRA is true
    :param min_percent: double (e.g. 0.25), applicable to PercentClip
    :param max_percent: double (e.g. 0.5), applicable to PercentClip
    :param gamma: array of doubles
    :param compute_gamma: optional, applicable to any stretch type when "UseGamma" is "true"
    :param sigmoid_strength_level: int (1~6), applicable to Sigmoid
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    str_types = {
        'none': 0,
        'stddev': 3,
        'histogram' : 4,
        'minmax': 5,
        'percentclip' : 6,
        'sigmoid': 9
    }

    if isinstance(stretch_type, str):
        in_str_type = str_types[stretch_type.lower()]
    else:
        in_str_type = stretch_type

    template_dict = {
        "rasterFunction": "Stretch",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if stretch_type is not None:
        template_dict["rasterFunctionArguments"]["StretchType"] = in_str_type
    if min is not None:
        template_dict["rasterFunctionArguments"]["Min"] = min
    if max is not None:
        template_dict["rasterFunctionArguments"]["Max"] = max
    if num_stddev is not None:
        template_dict["rasterFunctionArguments"]["NumberOfStandardDeviations"] = num_stddev
    if statistics is not None:
        template_dict["rasterFunctionArguments"]["Statistics"] = statistics
    if dra is not None:
        template_dict["rasterFunctionArguments"]["DRA"] = dra
    if min_percent is not None:
        template_dict["rasterFunctionArguments"]["MinPercent"] = min_percent
    if max_percent is not None:
        template_dict["rasterFunctionArguments"]["MaxPercent"] = max_percent
    if gamma is not None:
        template_dict["rasterFunctionArguments"]["Gamma"] = gamma
    if compute_gamma is not None:
        template_dict["rasterFunctionArguments"]["ComputeGamma"] = compute_gamma
    if sigmoid_strength_level is not None:
        template_dict["rasterFunctionArguments"]["SigmoidStrengthLevel"] = sigmoid_strength_level

    if compute_gamma is not None or gamma is not None:
        template_dict["rasterFunctionArguments"]["UseGamma"] = True

    return _clone_layer(layer, template_dict, raster_ra)


def threshold(raster, astype=None):
    """
    The binary threshold function produces the binary image. It uses the Otsu method and assumes the input image to have
     a bi-modal histogram. The arguments for the threshold function are as follows:

    :param raster: input raster
    :param astype: output pixel type
    :return: the output raster

    """
    threshold_type = 1
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "Threshold",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if threshold_type is not None:
        template_dict["rasterFunctionArguments"]["ThresholdType"] = threshold_type

    return _clone_layer(layer, template_dict, raster_ra)


def transpose_bits(raster, input_bit_positions=None, output_bit_positions=None, constant_fill_check=None,
                   constant_fill_value=None, fill_raster=None, astype=None):
    """
    The transpose_bits function performs a bit operation. It extracts bit values from the source data and assigns them
    to new bits in the output data.The arguments for the transpose_bits function are as follows:

    If constant_fill_check is False, it assumes there is an input fill_raster. If an input fill_raster is not given,
    it falls back constant_fill_check to True and looks for constant_fill_value.
    Filling is used to initialize pixel values of the output raster.
    Landsat 8 has a quality assessment band. The following are the example input and output bit positions to extract
    confidence levels by mapping them to 0-3:
    * Landsat 8 Water: {"input_bit_positions":[4,5],"output_bit_positions":[0,1]}
    * Landsat 8 Cloud Shadow: {"input_bit_positions":[6,7],"output_bit_positions":[0,1]}
    * Landsat 8 Vegetation: {"input_bit_positions":[8,9],"output_bit_positions":[0,1]}
    * Landsat 8 Snow/Ice: {"input_bit_positions":[10,11],"output_bit_positions":[0,1]}
    * Landsat 8 Cirrus: {"input_bit_positions":[12,13],"output_bit_positions":[0,1]}
    * Landsat 8 Cloud: {"input_bit_positions":[14,15],"output_bit_positions":[0,1]}
    * Landsat 8 Designated Fill: {"input_bit_positions":[0],"output_bit_positions":[0]}
    * Landsat 8 Dropped Frame: {"input_bit_positions":[1],"output_bit_positions":[0]}
    * Landsat 8 Terrain Occlusion: {"input_bit_positions":[2],"output_bit_positions":[0]}

    :param raster: input raster
    :param input_bit_positions: array of long, required
    :param output_bit_positions: array of long, required
    :param constant_fill_check: bool, optional
    :param constant_fill_value: int, required
    :param fill_raster: optional, the fill raster
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "TransposeBits",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if input_bit_positions is not None:
        template_dict["rasterFunctionArguments"]["InputBitPositions"] = input_bit_positions
    if output_bit_positions is not None:
        template_dict["rasterFunctionArguments"]["OutputBitPositions"] = output_bit_positions
    if constant_fill_check is not None:
        template_dict["rasterFunctionArguments"]["ConstantFillCheck"] = constant_fill_check
    if constant_fill_value is not None:
        template_dict["rasterFunctionArguments"]["ConstantFillValue"] = constant_fill_value
    if fill_raster is not None:
        template_dict["rasterFunctionArguments"]["FillRaster"] = fill_raster

    return _clone_layer(layer, template_dict, raster_ra)


def unit_conversion(raster, from_unit=None, to_unit=None, astype=None):
    """
    The unit_conversion function performs unit conversions.The arguments for the unit_conversion function are as follows:
    from_unit and to_unit take the following str values:
    Speed Units: MetersPerSecond, KilometersPerHour, Knots, FeetPerSecond, MilesPerHour
    Temperature Units: Celsius,Fahrenheit,Kelvin
    Distance Units: str, one of Inches, Feet, Yards, Miles, NauticalMiles, Millimeters, Centimeters, Meters

    :param raster: input raster
    :param from_unit: units constant listed below (int)
    :param to_unit: units constant listed below (int)
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    unit_types = {
        'inches': 1,
        'feet': 3,
        'yards': 4,
        'miles': 5,
        'nauticalmiles': 6,
        'millimeters': 7,
        'centimeters': 8,
        'meters': 9,
        'celsius': 200,
        'fahrenheit': 201,
        'kelvin': 202,
        'meterspersecond': 100,
        'kilometersperhour': 101,
        'knots': 102,
        'feetpersecond': 103,
        'milesperhour': 104
    }

    if isinstance(from_unit, str):
        from_unit = unit_types[from_unit.lower()]

    if isinstance(to_unit, str):
        to_unit = unit_types[to_unit.lower()]


    template_dict = {
        "rasterFunction": "UnitConversion",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if from_unit is not None:
        template_dict["rasterFunctionArguments"]["FromUnit"] = from_unit
    if to_unit is not None:
        template_dict["rasterFunctionArguments"]["ToUnit"] = to_unit

    return _clone_layer(layer, template_dict, raster_ra)


def vector_field_renderer(raster, is_uv_components=None, reference_system=None, mass_flow_angle_representation=None,
                          calculation_method="Vector Average", symbology_name="Single Arrow", astype=None):
    """
    The vector_field_renderer function symbolizes a U-V or Magnitude-Direction raster.The arguments for the vector_field_renderer function are as follows:

    :param raster: input raster
    :param is_uv_components: bool
    :param reference_system: int 1=Arithmetic, 2=Angular
    :param mass_flow_angle_representation: int 0=from 1=to
    :param calculation_method: string, "Vector Average" |
    :param symbology_name: string, "Single Arrow" |
    :param astype: output pixel type
    :return: the output raster

    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": "VectorFieldRenderer",
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    if is_uv_components is not None:
        template_dict["rasterFunctionArguments"]["IsUVComponents"] = is_uv_components
    if reference_system is not None:
        template_dict["rasterFunctionArguments"]["ReferenceSystem"] = reference_system
    if mass_flow_angle_representation is not None:
        template_dict["rasterFunctionArguments"]["MassFlowAngleRepresentation"] = mass_flow_angle_representation
    if calculation_method is not None:
        template_dict["rasterFunctionArguments"]["CalculationMethod"] = calculation_method
    if symbology_name is not None:
        template_dict["rasterFunctionArguments"]["SymbologyName"] = symbology_name

    return _clone_layer(layer, template_dict, raster_ra)


def apply(raster, fn_name, **kwargs):
    """
    Applies a server side raster function template defined by the imagery layer (image service)
    The name of the raster function template is available in the imagery layer properties.rasterFunctionInfos.

    Function arguments are optional; argument names and default values are created by the author of the raster function
    template and are not known through the API. A client can simply provide the name of the raster function template
    only or, optionally, provide arguments to overwrite the default values.
    For more information about authoring server-side raster function templates, see
    <a href="http://server.arcgis.com/en/server/latest/publish-services/windows/server-side-raster-functions.htm">Server-side raster functions</a>.

    :param raster: the input raster, or imagery layer
    :param fn_name: name of the server side raster function template, See imagery layer properties.rasterFunctionInfos
    :param kwargs: keyword arguments to override the default values of the raster function template, including astype
    :return: the output raster
    """
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction": fn_name,
        "rasterFunctionArguments": {
            "Raster": raster
        },
        "variableName": "Raster"
    }

    for key, value in kwargs.items():
        template_dict["rasterFunctionArguments"][key] = value

    astype = kwargs.pop('astype', None)
    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra)


def vector_field(raster_u_mag, raster_v_dir, input_data_type='Vector-UV', angle_reference_system='Geographic',
                 output_data_type='Vector-UV', astype=None):
    """
    The VectorField function is used to composite two single-band rasters (each raster represents U/V or Magnitude/Direction)
    into a two-band raster (each band represents U/V or Magnitude/Direction). Data combination type (U-V or Magnitude-Direction)
    can also be converted interchangeably with this function.
    For more information, see Vector Field function
    (http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/vector-field-function.htm)

    :param raster_u_mag: raster item representing 'U' or 'Magnitude' - imagery layers filtered by where clause, spatial and temporal filters
    :param raster_v_dir: raster item representing 'V' or 'Direction' - imagery layers filtered by where clause, spatial and temporal filters
    :param input_data_type: string, 'Vector-UV' or 'Vector-MagDir' per input used in 'raster_u_mag' and 'raster_v_dir'
    :param angle_reference_system: string, optional when 'input_data_type' is 'Vector-UV', one of "Geographic", "Arithmetic"
    :param output_data_type: string, 'Vector-UV' or 'Vector-MagDir'
    :return: the output raster with this function applied to it
    """

    layer1, raster_u_mag_1, raster_ra1 = _raster_input(raster_u_mag)
    layer2, raster_v_dir_1, raster_ra2 = _raster_input(raster_u_mag, raster_v_dir)

    layer = layer1 if layer1 is not None else layer2

    angle_reference_system_types = {
        "Geographic" : 0,
        "Arithmetic" : 1
    }

    in_angle_reference_system = angle_reference_system_types[angle_reference_system]

    template_dict = {
        "rasterFunction": "VectorField",
        "rasterFunctionArguments": {
            "Raster1": raster_u_mag_1,
            "Raster2": raster_v_dir_1,            
        }
    }

    if in_angle_reference_system is not None:
        template_dict["rasterFunctionArguments"]["AngleReferenceSystem"] = in_angle_reference_system
    if input_data_type is not None and input_data_type in ["Vector-UV", "Vector-MagDir"]:
        template_dict["rasterFunctionArguments"]['InputDataType'] = input_data_type
    if output_data_type is not None and output_data_type in ["Vector-UV", "Vector-MagDir"]:
        template_dict["rasterFunctionArguments"]['OutputDataType'] = output_data_type
    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra1, raster_ra2)


def complex(raster):
    """
    Complex function computes magnitude from complex values. It is used when
    input raster has complex pixel type. It computes magnitude from complex
    value to convert the pixel type to floating point for each pixel. It takes
    no argument but an optional input raster. For more information, see 
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/complex-function.htm

    :param raster: the input raster / imagery layer
    :return: Output raster obtained after applying the function
    """
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction" : "Complex",
        "rasterFunctionArguments" : {
            "Raster" : raster,
        }
    }

    return _clone_layer(layer, template_dict, raster_ra)


def colormap_to_rgb(raster):
    """"
    The function is designed to work with single band image service that has
    internal colormap. It will convert the image into a three-band 8-bit RGB
    raster. This function takes no arguments except an input raster. For 
    qualified image service, there are two situations when ColormapToRGB 
    function is automatically applied: The "colormapToRGB" property of the 
    image service is set to true; or, client asks to export image into jpg 
    or png format. For more information, see 
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/colormap-to-rgb-function.htm)

    :param raster: the input raster / imagery layer
    :return: Three band raster
    """

    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction" : "ColormapToRGB",
        "rasterFunctionArguments" : {
            "Raster" : raster,
        }
    }

    return _clone_layer(layer, template_dict, raster_ra)


def statistics_histogram(raster, statistics=None, histograms=None):
    """"
    The function is used to define the statistics and histogram of a raster.
    It is normally used for control the default display of exported image. 
    For more information, see Statistics and Histogram function, 
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/statistics-and-histogram-function.htm

    :param raster: the input raster / imagery layer
    :param statistics: array of statistics objects. (Predefined statistics for each band)
    :param histograms: array of histogram objects. (Predefined histograms for each band)
    :return: Statistics and Histogram defined raster
    """
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction" : "StatisticsHistogram",
        "rasterFunctionArguments" : {            
            "Raster" : raster,
        }
    }

    if statistics is not None:
        template_dict["rasterFunctionArguments"]['Statistics'] = statistics
    if histograms is not None:
        template_dict["rasterFunctionArguments"]['Histograms'] = histograms

    return _clone_layer(layer, template_dict, raster_ra)


def tasseled_cap(raster):
    """"
    The function is designed to analyze and map vegetation and urban development
    changes detected by various satellite sensor systems. It is known as the 
    Tasseled Cap transformation due to the shape of the graphical distribution
    of data. This function takes no arguments except a raster. The input for 
    this function is the source raster of image service. There are no other 
    parameters for this function because all the information is derived from 
    the input's properties and key metadata (bands, data type, and sensor name). 
    Only imagery from the Landsat MSS, Landsat TM, Landsat ETM+, IKONOS, 
    QuickBird, WorldView-2 and RapidEye sensors are supported. Prior to applying
    this function, there should not be any functions that would alter the pixel
    values in the function chain, such as the Stretch, Apparent Reflectance or
    Pansharpening function. The only exception is for Landsat ETM+; when using 
    Landsat ETM+, the Apparent Reflectance function must precede the Tasseled 
    Cap function. For more information, see 
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/tasseled-cap-transformation.htm

    :param raster: the input raster / imagery layer
    :return: the output raster with TasseledCap function applied to it
    """
 
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction" : "TasseledCap",
        "rasterFunctionArguments" : {
            "Raster" : raster,
        }
    }

    return _clone_layer(layer, template_dict, raster_ra)


def identity(raster):
    """"
    The function is used to define the source raster as part of the default
    mosaicking behavior of the mosaic dataset. This function is a no-op function
    and takes no arguments except a raster. For more information, see
    (http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/identity-function.htm)

    :param raster: the input raster / imagery layer
    :return: the innput raster
    """
 
    layer, raster, raster_ra = _raster_input(raster)

    template_dict = {
        "rasterFunction" : "Identity",
        "rasterFunctionArguments": {
            "Raster" : raster,
        }
    }

    return _clone_layer(layer, template_dict, raster_ra)

def colorspace_conversion(raster, conversion_type="rgb_to_hsv"):
    """
    The ColorspaceConversion function converts the color model of a three-band
    unsigned 8-bit image from either the hue, saturation, and value (HSV)
    to red, green, and blue (RGB) or vice versa. An ExtractBand function and/or
    a Stretch function are sometimes used for converting the imagery into valid
    input of ColorspaceConversion function. For more information, see
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/color-model-conversion-function.htm

    :param raster: the input raster
    :param conversion_type: sting type, one of "rgb_to_hsv" or "hsv_to_rgb". Default is "rgb_to_hsv"
    :return: the output raster with this function applied to it
    """
 
    layer, raster, raster_ra = _raster_input(raster)

    conversion_types = {
        "rgb_to_hsv" : 0,
        "hsv_to_rgb" : 1
        }
            
    template_dict = {
        "rasterFunction" : "ColorspaceConversion",
        "rasterFunctionArguments" : {
            "Raster" : raster,            
        }
    }
    
    template_dict["rasterFunctionArguments"]['ConversionType'] = conversion_types[conversion_type]
         
    return _clone_layer(layer, template_dict, raster_ra)


def grayscale(raster, conversion_parameters=None):
    """
    The Grayscale function converts a multi-band image into a single-band grayscale
    image. Specified weights are applied to each of the input bands, and a 
    normalization is applied for output. For more information, see
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/grayscale-function.htm

    :param raster: the input raster
    :param conversion_parameters: array of double (A length of N array representing weights for each band, where N=band count.)
    :return: the output raster with this function applied to it
    """
 
    layer, raster, raster_ra = _raster_input(raster)
       
    template_dict = {
        "rasterFunction" : "Grayscale",
        "rasterFunctionArguments": {
            "Raster" : raster,            
        }
    }
    
    if conversion_parameters is not None and isinstance(conversion_parameters, list):
        template_dict["rasterFunctionArguments"]['ConversionParameters'] = conversion_parameters

    return _clone_layer(layer, template_dict, raster_ra)


def spectral_conversion(raster, conversion_matrix):
    """
    The SpectralConversion function applies a matrix to a multi-band image to
    affect the spectral values of the output. In the matrix, different weights
    can be assigned to all the input bands to calculate each of the output 
    bands. The column/row size of the matrix equals to the band count of input 
    raster. For more information, see Spectral Conversion function
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/spectral-conversion-function.htm

    :param raster: the input raster
    :param conversion_parameters: array of double (A NxN length one-dimension matrix, where N=band count.)
    :return: the output raster with this function applied to it
    """
 
    layer, raster, raster_ra = _raster_input(raster)
       
    template_dict = {
        "rasterFunction" : "SpectralConversion",
        "rasterFunctionArguments": {
            "Raster" : raster,  
            "ConversionMatrix" : conversion_matrix
        }
    }    
    
    return _clone_layer(layer, template_dict, raster_ra)


def raster_calculator(rasters, input_names, expression, extent_type="FirstOf", cellsize_type="FirstOf", astype=None):
    """
    The RasterCalculator function provides access to all existing math functions
    so you can make calls to them when building your expressions. The calculator
    function requires single-band inputs. If you need to perform expressions on
    bands in a multispectral image as part of a function chain, you can use 
    the Extract Bands Function before the RasterCalculator function. 
    For more info including operators supported, see Calculator function 
    http://pro.arcgis.com/en/pro-app/help/data/imagery/calculator-function.htm

    :param raster: array of rasters
    :param input_names: array of strings for arbitrary raster names.
    :param expression: string, expression to calculate output raster from input rasters
    :param extent_type: string, one of "FirstOf", "IntersectionOf" "UnionOf", "LastOf". Default is "FirstOf".
    :param cellsize_type: one of "FirstOf", "MinOf", "MaxOf "MeanOf", "LastOf". Default is "FirstOf".
    :param astype: output pixel type
    :return: output raster with function applied
    """
    
    layer, raster, raster_ra = _raster_input(rasters)
    
    extent_types = {
        "FirstOf" : 0,
        "IntersectionOf" : 1,
        "UnionOf" : 2,
        "LastOf" : 3
    }

    cellsize_types = {
        "FirstOf" : 0,
        "MinOf" : 1,
        "MaxOf" : 2,
        "MeanOf" : 3,
        "LastOf" : 4
    }      

    template_dict = {
        "rasterFunction" : "RasterCalculator",
        "rasterFunctionArguments": {
            "InputNames" : input_names,
            "Expression" : expression,
            "Rasters" : raster            
        },
        "variableName" : "Rasters"
    }
    
    template_dict["rasterFunctionArguments"]['ExtentType'] = extent_types[extent_type]    
    template_dict["rasterFunctionArguments"]['CellsizeType'] = cellsize_types[cellsize_type]

    if astype is not None:
        template_dict["outputPixelType"] = astype.upper()

    return _clone_layer(layer, template_dict, raster_ra, variable_name='Rasters')


def speckle(raster, 
            filter_type="Lee", 
            filter_size="3x3", 
            noise_model="Multiplicative", 
            noise_var=None,
            additive_noise_mean=None, 
            multiplicative_noise_mean=1,
            nlooks=1, 
            damp_factor=None):
    """
    The Speckle function filters the speckled radar dataset to smooth out the 
    noise while retaining the edges or sharp features in the image. Four speckle
    reduction filtering algorithms are provided through this function. For more
    information including required and optional parameters for each filter and 
    the default parameter values, see Speckle function 
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/speckle-function.htm

    :param raster: input raster type
    :param filter_type: string, one of "Lee", "EnhancedLee" "Frost", "Kaun". Default is "Lee".
    :param filter_size: string, kernel size. One of "3x3", "5x5", "7x7", "9x9", "11x11". Default is "3x3".
    :param noise_model: string, For Lee filter only. One of "Multiplicative", "Additive", "AdditiveAndMultiplicative"
    :param noise_var: double, for Lee filter with noise_model "Additive" or "AdditiveAndMultiplicative"
    :param additive_noise_mean: string, for Lee filter witth noise_model "AdditiveAndMultiplicative" only
    :param multiplicative_noise_mean: double, For Lee filter with noise_model "Additive" or "AdditiveAndMultiplicative"
    :param nlooks: int, for Lee, EnhancedLee and Kuan Filters
    :param damp_factor: double, for EnhancedLee and Frost filters
    :return: output raster with function applied
    """
   
    layer, raster, raster_ra = _raster_input(raster)
   
    filter_types = {
        "Lee" : 0,
        "EnhancedLee" : 1,
        "Frost" : 2,
        "Kuan" : 3
    }

    filter_sizes = {
        "3x3" : 0,
        "5x5" : 1,
        "7x7" : 2,
        "9x9" : 3,
        "11x11" : 4
    }

    noise_models = {
        "Multiplicative" : 0,
        "Additive" : 1,
        "AdditiveAndMultiplicative" : 2
    }    
    
    template_dict = {
        "rasterFunction" : "Speckle",
        "rasterFunctionArguments" : {            
            "Raster": raster,            
        }
    }
        
    template_dict["rasterFunctionArguments"]['FilterType'] = filter_types[filter_type]    
    template_dict["rasterFunctionArguments"]['FilterSize'] = filter_sizes[filter_size]    
    template_dict["rasterFunctionArguments"]['NoiseModel'] = noise_models[noise_model]

    if noise_var is not None:
        template_dict["rasterFunctionArguments"]['NoiseVar'] = noise_var
    if additive_noise_mean is not None:
        template_dict["rasterFunctionArguments"]['AdditiveNoiseMean'] = additive_noise_mean
    if multiplicative_noise_mean is not None:
        template_dict["rasterFunctionArguments"]['MultiplicativeNoiseMean'] = multiplicative_noise_mean
    if nlooks is not None:
        template_dict["rasterFunctionArguments"]['NLooks'] = nlooks
    if damp_factor is not None:
        template_dict["rasterFunctionArguments"]['DampFactor'] = damp_factor
    
    return _clone_layer(layer, template_dict, raster_ra)


def pansharpen(pan_raster,
               ms_raster,
               ir_raster=None,
               fourth_band_of_ms_is_ir = True,
               weights = [0.166, 0.167, 0.167, 0.5],               
               type="ESRI",                                
               sensor=None):
    """
    The Pansharpening function uses a higher-resolution panchromatic raster to
    fuse with a lower-resolution, multiband raster. It can generate colorized 
    multispectral image with higher resolution. For more information, see 
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/pansharpening-function.htm

    :param pan_raster: raster, which is panchromatic
    :param ms_raster: raster, which is multispectral
    :param ir_raster: Optional, if fourth_band_of_ms_is_ir is true or selected pansharpening method doesn't require near-infrared image
    :param fourth_band_of_ms_is_ir: Boolean, "true" if "ms_raster" has near-infrared image on fourth band
    :param weights: Weights applied for Red, Green, Blue, Near-Infrared bands. 4-elements array, Sum of values is 1
    :param type: string, describes the Pansharpening method one of "IHS", "Brovey" "ESRI", "SimpleMean", "Gram-Schmidt". Default is "ESRI"
    :param sensor: string, it is an optional parameter to specify the sensor name
    :return: output raster with function applied
    """

    layer1, pan_raster_1, raster_ra1 = _raster_input(pan_raster)
    layer2, ms_raster_1, raster_ra2 = _raster_input(pan_raster, ms_raster)
    if ir_raster is not None:
        layer3, ir_raster_1, raster_ra3 = _raster_input(pan_raster, ir_raster)

    if layer1 is not None:
        layer = layer1
    elif layer2 is not None:
       layer = layer2
    else:
        layer = layer3

    pansharpening_types = {
        "IHS" : 0,
        "Brovey" : 1,
        "ESRI" : 2,
        "SimpleMean" : 3,
        "Gram-Schmidt" : 4
    }

    template_dict = {
        "rasterFunction" : "Pansharpening",
        "rasterFunctionArguments" : {      
            "Weights" : weights,            
            "PanImage": pan_raster_1,
            "MSImage" : ms_raster_1
        }
    }

    if type is not None:
        template_dict["rasterFunctionArguments"]['PansharpeningType'] = pansharpening_types[type]

    if ir_raster is not None:
        template_dict["rasterFunctionArguments"]['InfraredImage'] = ir_raster_1

    if isinstance(fourth_band_of_ms_is_ir, bool):
        template_dict["rasterFunctionArguments"]['UseFourthBandOfMSAsIR'] = fourth_band_of_ms_is_ir

    if sensor is not None:
        template_dict["rasterFunctionArguments"]['Sensor'] = sensor

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']['PanImage'] = raster_ra1
    function_chain_ra['rasterFunctionArguments']['MSImage'] = raster_ra2
    if ir_raster is not None:
        function_chain_ra['rasterFunctionArguments']['InfraredImage'] = raster_ra3

    return _clone_layer_pansharpen(layer, template_dict, function_chain_ra)


def weighted_overlay(rasters, fields, influences, remaps, eval_from, eval_to):
               
    """
    The WeightedOverlay function allows you to overlay several rasters using a common 
	measurement scale and weights each according to its importance. For more information, see
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/weighted-overlay-function.htm

    :param raster: array of rasters
    :param fields: array of string fields of the input rasters to be used for weighting.				 
    :param influences: array of double, Each input raster is weighted according to its importance, or 
				       its influence. The sum of the influence weights must equal 1
    :param remaps: array of strings, Each value in an input raster is assigned a new value based on the 
				   remap. The remap value can be a valid value or a NoData value.    
	:param eval_from: required, numeric value of evaluation scale from
	:param eval_to: required, numeric value of evaluation scale to
    :return: output raster with function applied
    """

    layer, raster, raster_ra = _raster_input(rasters)   

    template_dict = {
        "rasterFunction" : "WeightedOverlay",
        "rasterFunctionArguments" : { 
            "Rasters" : raster,
            "Fields" : fields,
            "Influences": influences,
            "Remaps" : remaps,
            "EvalFrom" : eval_from,
            "EvalTo": eval_to
        },
        "variableName": "Rasters"
    }   
    
    return _clone_layer(layer, template_dict, raster_ra, variable_name='Rasters')


def weighted_sum(rasters, fields, weights):
               
    """
    The WeightedSum function allows you to overlay several rasters, multiplying each by their 
	given weight and summing them together.  For more information, see
    http://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/weighted-sum-function.htm

    :param raster: array of rasters
    :param fields: array of string fields of the input rasters to be used for weighting.				 
    :param weights: array of double, The weight value by which to multiply the raster. 
				    It can be any positive or negative decimal value.    
    :return: output raster with function applied
    """

    layer, raster, raster_ra = _raster_input(rasters)   
     
    template_dict = {
        "rasterFunction" : "WeightedSum",
        "rasterFunctionArguments" : { 
            "Rasters" : raster,
            "Fields" : fields,
            "Weights" : weights
        },
        "variableName": "Rasters"
    }   
    
    return _clone_layer(layer, template_dict, raster_ra, variable_name='Rasters')
