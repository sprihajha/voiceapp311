"""
Global Raster functions.
These functions are applied to the raster data to create a
processed product on disk, using ImageryLalyer.save() method or arcgis.raster.analytics.generate_raster().

Global functions cannot be used for visualization using dynamic image processing. They cannot be applied to layers that
are added to a map for on-the-fly image processing or visualized inline within the Jupyter notebook.

Functions can be applied to various rasters (or images), including the following:

* Imagery layers
* Rasters within imagery layers

"""
from arcgis.raster._layer import ImageryLayer
from arcgis.gis import Item
import copy
import numbers
from arcgis.raster.functions.utility import _raster_input, _get_raster, _replace_raster_url, _get_raster_url, _get_raster_ra

def _gbl_clone_layer(layer, function_chain, function_chain_ra):
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
    newlyr._uses_gbl_function = True
    return newlyr


def euclidean_distance(in_source_data,
                       cell_size=None,
                       max_distance=None):
    """
    Calculates, for each cell, the Euclidean distance to the closest source. 
    For more information, see 
    http://pro.arcgis.com/en/pro-app/help/data/imagery/euclidean-distance-global-function.htm

    Parameters
    ----------
    :param in_source_data: raster; The input raster that identifies the pixels or locations to
                            which the Euclidean distance for every output pixel location is calculated.
                            The input type can be an integer or a floating-point value.
    :param cell_size:  The pixel size at which the output raster will be created. If the cell
                            size was explicitly set in Environments, that will be the default cell size. 
                            If Environments was not set, the output cell size will be the same as the 
                            Source Raster
    :param max_distance: The threshold that the accumulative distance values cannot exceed. If an
                            accumulative Euclidean distance exceeds this value, the output value for
                            the pixel location will be NoData. The default distance is to the edge 
                            of the output raster
    :return: output raster with function applied
    """
    layer, in_source_data, raster_ra = _raster_input(in_source_data)
                  
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "EucDistance_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_distance_raster",
            "in_source_data": in_source_data,
                
        }
    }
    
    if cell_size is not None:
        template_dict["rasterFunctionArguments"]["cell_size"] = cell_size
    
    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_source_data"] = raster_ra

    return _gbl_clone_layer(layer, template_dict, function_chain_ra)
    


def euclidean_allocation(in_source_data,
                         in_value_raster=None,
                         max_distance=None,
                         cell_size=None,
                         source_field=None):
    
    """
    Calculates, for each cell, the nearest source based on Euclidean distance.
    For more information, see 
    http://pro.arcgis.com/en/pro-app/help/data/imagery/euclidean-allocation-global-function.htm

    Parameters
    ----------
    :param in_source_data: raster; The input raster that identifies the pixels or locations to which
                            the Euclidean distance for every output pixel location is calculated. 
                            The input type can be an integer or a floating-point value.
                            If the input Source Raster is floating point, the Value Raster must be set,
                            and it must be an integer. The Value Raster will take precedence over any
                            setting of the Source Field.
    :param in_value_raster: The input integer raster that identifies the zone values that should be 
                            used for each input source location. For each source location pixel, the
                            value defined by the Value Raster will be assigned to all pixels allocated
                            to the source location for the computation. The Value Raster will take 
                            precedence over any setting for the Source Field .
    :param max_distance: The threshold that the accumulative distance values cannot exceed. If an
                            accumulative Euclidean distance exceeds this value, the output value for
                            the pixel location will be NoData. The default distance is to the edge                     
                            of the output raster
    :param cell_size: The pixel size at which the output raster will be created. If the cell size
                            was explicitly set in Environments, that will be the default cell size. 
                            If Environments was not set, the output cell size will be the same as the 
                            Source Raster
    :param source_field: The field used to assign values to the source locations. It must be an
                            integer type. If the Value Raster has been set, the values in that input
                            will take precedence over any setting for the Source Field.
    :return: output raster with function applied
    """
    
    layer1, in_source_data, raster_ra1 = _raster_input(in_source_data)      
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "EucAllocation_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_allocation_raster",
            "in_source_data": in_source_data            
                
        }
    }
    
    if in_value_raster is not None:
        layer2, in_value_raster, raster_ra2 = _raster_input(in_value_raster)
        template_dict["rasterFunctionArguments"]["in_value_raster"] = in_value_raster
    
    if cell_size is not None:
        template_dict["rasterFunctionArguments"]["cell_size"] = cell_size
    
    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance
    
    if source_field is not None:
        template_dict["rasterFunctionArguments"]["source_field"] = source_field
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_source_data"] = raster_ra1
    if in_value_raster is not None:
        function_chain_ra["rasterFunctionArguments"]["in_value_raster"] = raster_ra2

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)
    
    
    
def cost_distance(in_source_data,
                  in_cost_raster,
                  max_distance=None,
                  source_cost_multiplier=None,
                  source_start_cost=None,
                  source_resistance_rate=None,
                  source_capacity=None,
                  source_direction=None):
    """
    Calculates the least accumulative cost distance for each cell from or to the least-cost
    source over a cost surface.
    For more information, see
    http://pro.arcgis.com/en/pro-app/help/data/imagery/cost-distance-global-function.htm

    Parameters
    ----------
    :param in_source_data: The input raster that identifies the pixels or locations to which the
                            least accumulated cost distance for every output pixel location is 
                            calculated. The Source Raster can be an integer or a floating-point value.
    :param in_cost_raster: A raster defining the cost or impedance to move planimetrically through each pixel.
                            The value at each pixel location represents the cost-per-unit distance for moving 
                            through it. Each pixel location value is multiplied by the pixel resolution, while 
                            also compensating for diagonal movement to obtain the total cost of passing through 
                            the pixel. 
    :param max_distance: The threshold that the accumulative cost values cannot exceed. If an accumulative cost
                            distance exceeds this value, the output value for the pixel location will be NoData. 
                            The maximum distance defines the extent for which the accumulative cost distances are
                            calculated. The default distance is to the edge of the output raster.
    :param source_cost_multiplier: The threshold that the accumulative cost values cannot exceed. If an accumulative
                            cost distance exceeds this value, the output value for the pixel location will be 
                            NoData. The maximum distance defines the extent for which the accumulative cost 
                            distances are calculated. The default distance is to the edge of the output raster.
    :param source_start_cost: The starting cost from which to begin the cost calculations. This parameter allows
                            for the specification of the fixed cost associated with a source. Instead of starting
                            at a cost of 0, the cost algorithm will begin with the value set here.
                            The default is 0. The value must be 0 or greater. A numeric (double) value or a field
                            from the Source Raster can be used for this parameter.
    :param source_resistance_rate: This parameter simulates the increase in the effort to overcome costs as the
                            accumulative cost increases. It is used to model fatigue of the traveler. The growing
                            accumulative cost to reach a pixel is multiplied by the resistance rate and added to 
                            the cost to move into the subsequent pixel.
                            It is a modified version of a compound interest rate formula that is used to calculate
                            the apparent cost of moving through a pixel. As the value of the resistance rate increases,
                            it increases the cost of the pixels that are visited later. The greater the resistance rate, 
                            the higher the cost to reach the next pixel, which is compounded for each subsequent movement. 
                            Since the resistance rate is similar to a compound rate and generally the accumulative cost 
                            values are very large, small resistance rates are suggested, such as 0.005 or even smaller, 
                            depending on the accumulative cost values.
                            The default is 0. The values must be 0 or greater. A numeric (double) value or a field from
                            the Source Raster can be used for this parameter.
    :param source_capacity: Defines the cost capacity for the traveler for a source. The cost calculations continue for
                            each source until the specified capacity is reached.
                            The default capacity is to the edge of the output raster. The values must be greater than 0. 
                            A double numeric value or a field from the Source Raster can be used for this parameter.
    :param source_direction: Defines the direction of the traveler when applying the source resistance rate and the source
                            starting cost.
                            From Source - The source resistance rate and source starting cost will be applied beginning
                            at the input source and moving out to the nonsource cells. This is the default.
                            To Source - The source resistance rate and source starting cost will be applied beginning at
                            each nonsource cell and moving back to the input source.
                            Either specify the From Source or To Source keyword, which will be applied to all sources,
                            or specify a field in the Source Raster that contains the keywords to identify the direction
                            of travel for each source. That field must contain the string From Source or To Source.
    
    :return: output raster with function applied
    """        
    layer1, in_source_data, raster_ra1 = _raster_input(in_source_data)  
    layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
                            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "CostDistance_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_distance_raster",
            "in_source_data": in_source_data, 
            "in_cost_raster": in_cost_raster
             
        }
    }    
    
    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance
    
    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier
    
    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost
    
    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate
    
    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity
    
    if source_direction is not None:
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_source_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_cost_raster"] = raster_ra2

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)
        
        
def cost_allocation(in_source_data,
                    in_cost_raster,
                    in_value_raster=None,
                    max_distance=None,                    
                    source_field=None,
                    source_cost_multiplier=None,
                    source_start_cost=None,
                    source_resistance_rate=None,
                    source_capacity=None,
                    source_direction=None):
    """
    Calculates, for each cell, its least-cost source based on the least accumulative cost over a cost surface.
    For more information, see
    http://pro.arcgis.com/en/pro-app/help/data/imagery/cost-allocation-global-function.htm

    Parameters
    ----------
    :param in_source_data: The input raster that identifies the pixels or locations to which the
                            least accumulated cost distance for every output pixel location is 
                            calculated. The Source Raster can be an integer or a floating-point value.
                            If the input Source Raster is floating point, the Value Raster must be set, 
                            and it must be an integer. The Value Raster will take precedence over any 
                            setting of the Source Field.
    :param in_cost_raster: A raster defining the cost or impedance to move planimetrically through each pixel.
                            The value at each pixel location represents the cost-per-unit distance for moving 
                            through it. Each pixel location value is multiplied by the pixel resolution, while 
                            also compensating for diagonal movement to obtain the total cost of passing through 
                            the pixel. 
                            The values of the Cost Raster can be integer or floating point, but they cannot be 
                            negative or zero.
    :param in_value_raster: The input integer raster that identifies the zone values that should be used for 
                            each input source location. For each source location pixel, the value defined by
                            the Value Raster will be assigned to all pixels allocated to the source location 
                            for the computation. The Value Raster will take precedence over any setting for 
                            the Source Field. 
    :param max_distance: The threshold that the accumulative cost values cannot exceed. If an accumulative cost
                            distance exceeds this value, the output value for the pixel location will be NoData. 
                            The maximum distance defines the extent for which the accumulative cost distances are
                            calculated. The default distance is to the edge of the output raster.
    :param source_field: The field used to assign values to the source locations. It must be an integer type.
                            If the Value Raster has been set, the values in that input will take precedence over
                            any setting for the Source Field.
    :param source_cost_multiplier: This parameter allows for control of the mode of travel or the magnitude at
                            a source. The greater the multiplier, the greater the cost to move through each cell.
                            The default value is 1. The values must be greater than 0. A numeric (double) value or
                            a field from the Source Raster can be used for this parameter.
    :param source_start_cost: The starting cost from which to begin the cost calculations. This parameter allows
                            for the specification of the fixed cost associated with a source. Instead of starting
                            at a cost of 0, the cost algorithm will begin with the value set here.
                            The default is 0. The value must be 0 or greater. A numeric  (double) value or a field
                            from the Source Raster can be used for this parameter.
    :param source_resistance_rate: This parameter simulates the increase in the effort to overcome costs as the
                            accumulative cost increases. It is used to model fatigue of the traveler. The growing
                            accumulative cost to reach a pixel is multiplied by the resistance rate and added to 
                            the cost to move into the subsequent pixel.
                            It is a modified version of a compound interest rate formula that is used to calculate
                            the apparent cost of moving through a pixel. As the value of the resistance rate increases,
                            it increases the cost of the pixels that are visited later. The greater the resistance rate, 
                            the higher the cost to reach the next pixel, which is compounded for each subsequent movement. 
                            Since the resistance rate is similar to a compound rate and generally the accumulative cost 
                            values are very large, small resistance rates are suggested, such as 0.005 or even smaller, 
                            depending on the accumulative cost values.
                            The default is 0. The values must be 0 or greater. A numeric (double) value or a field from
                            the Source Raster can be used for this parameter.
    :param source_capacity: Defines the cost capacity for the traveler for a source. The cost calculations continue for
                            each source until the specified capacity is reached.
                            The default capacity is to the edge of the output raster. The values must be greater than 0. 
                            A double numeric value or a field from the Source Raster can be used for this parameter.
    :source_direction: Defines the direction of the traveler when applying the source resistance rate and the source
                            starting cost.
                            From Source - The source resistance rate and source starting cost will be applied beginning
                            at the input source and moving out to the nonsource cells. This is the default.
                            To Source - The source resistance rate and source starting cost will be applied beginning at
                            each nonsource cell and moving back to the input source.
                            Either specify the From Source or To Source keyword, which will be applied to all sources,
                            or specify a field in the Source Raster that contains the keywords to identify the direction
                            of travel for each source. That field must contain the string From Source or To Source.
    
    :return: output raster with function applied
    """   
            
    layer1, in_source_data, raster_ra1 = _raster_input(in_source_data)
    layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "CostAllocation_sa",           
            "PrimaryInputParameterName":"in_source_data",
            "OutputRasterParameterName":"out_allocation_raster",
            "in_source_data": in_source_data, 
            "in_cost_raster": in_cost_raster
             
        }
    }    
    if in_value_raster is not None:
        layer3, in_value_raster, raster_ra3 = _raster_input(in_value_raster)
        template_dict["rasterFunctionArguments"]["in_value_raster"] = in_value_raster

    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance

    if source_field is not None:
        template_dict["rasterFunctionArguments"]["source_field"] = source_field
    
    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier
    
    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost
    
    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate
    
    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity
    
    if source_direction is not None:
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_source_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_cost_raster"] = raster_ra2
    if in_value_raster is not None:
        function_chain_ra["rasterFunctionArguments"]["in_value_raster"] = raster_ra3

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)
    
    
def zonal_statistics(in_zone_data,
                     zone_field,
                     in_value_raster,
                     ignore_nodata=None,
                     statistics_type=None):
                     
    """"
    Calculates statistics on values of a raster within the zones of another dataset.
    For more information, 
    http://pro.arcgis.com/en/pro-app/help/data/imagery/zonal-statistics-global-function.htm

    Parameters
    ----------
    :param in_zone_data: Dataset that defines the zones. The zones can be defined by an integer raster
    :param zone_field: Field that holds the values that define each zone. It can be an integer or a
                            string field of the zone raster.
    :param in_value_raster: Raster that contains the values on which to calculate a statistic.
    :param ignore_no_data: Denotes whether NoData values in the Value Raster will influence the results
                            of the zone that they fall within.
                            Yes - Within any particular zone, only pixels that have a value in the Value
                            Raster will be used in determining the output value for that zone. NoData 
                            pixels in the Value Raster will be ignored in the statistic calculation. 
                            This is the default.
                            No - Within any particular zone, if any NoData pixels exist in the Value 
                            Raster, it is deemed that there is insufficient information to perform 
                            statistical calculations for all the pixels in that zone; therefore, the 
                            entire zone will receive the NoData value on the output raster.
    :param statistics_type: Statistic type to be calculated.
                            Mean-Calculates the average of all pixels in the Value Raster that belong to
                            the same zone as the output pixel.
                            Majority-Determines the value that occurs most often of all pixels in the 
                            Value Raster that belong to the same zone as the output pixel.
                            Maximum-Determines the largest value of all pixels in the Value Raster 
                            that belong to the same zone as the output pixel.
                            Median-Determines the median value of all pixels in the Value Raster
                            that belong to the same zone as the output pixel.
                            Minimum-Determines the smallest value of all pixels in the Value Raster 
                            that belong to the same zone as the output pixel.
                            Minority-Determines the value that occurs least often of all pixels in
                            the Value Raster that belong to the same zone as the output pixel.
                            Range-Calculates the difference between the largest and smallest value 
                            of all pixels in the Value Raster that belong to the same zone as the
                            output pixel.
                            Standard Deviation-Calculates the standard deviation of all pixels in
                            the Value Rasterthat belong to the same zone as the output pixel.
                            Sum-Calculates the total value of all pixels in the Value Raster that
                            belong to the same zone as the output pixel.
                            Variety-Calculates the number of unique values for all pixels in the 
                            Value Raster that belong to the same zone as the output pixel.
    :return: output raster with function applied
    """
    layer1, in_zone_data, raster_ra1 = _raster_input(in_zone_data)  
    layer2, in_value_raster, raster_ra2 = _raster_input(in_value_raster)
        
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "ZonalStatistics_sa",           
            "PrimaryInputParameterName" : "in_zone_data",
            "OutputRasterParameterName" : "out_raster",
            "in_zone_data" : in_zone_data, 
            "zone_field" : zone_field,
            "in_value_raster" : in_value_raster
             
        }
    }    
    
    if ignore_nodata is not None:
        template_dict["rasterFunctionArguments"]["ignore_nodata"] = ignore_nodata
    
    if statistics_type is not None:
        template_dict["rasterFunctionArguments"]["statistics_type"] = statistics_type
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_zone_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_value_raster"] = raster_ra2

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)        
        
        
def least_cost_path(in_source_data,
                    in_cost_raster,
                    in_destination_data,
                    destination_field=None,                    
                    path_type=None,
                    max_distance=None,
                    source_cost_multiplier=None,
                    source_start_cost=None,
                    source_resistance_rate=None,
                    source_capacity=None,
                    source_direction=None):
    """
    Calculates the least-cost path from a source to a destination. The least accumulative cost distance 
    is calculated for each pixel over a cost surface, to the nearest source. This produces an output 
    raster that records the least-cost path, or paths, from selected locations to the closest source
    pixels defined within the accumulative cost surface, in terms of cost distance.
    For more information, see
    http://pro.arcgis.com/en/pro-app/help/data/imagery/least-cost-path-global-function.htm

    Parameters
    ----------
    :param in_source_data: The input raster that identifies the pixels or locations to which the
                            least accumulated cost distance for every output pixel location is 
                            calculated. The Source Raster can be an integer or a floating-point value.
                            If the input Source Raster is floating point, the Value Raster must be set, 
                            and it must be an integer. The Value Raster will take precedence over any 
                            setting of the Source Field.
    :param in_cost_raster: A raster defining the cost or impedance to move planimetrically through each pixel.
                            The value at each pixel location represents the cost-per-unit distance for moving 
                            through it. Each pixel location value is multiplied by the pixel resolution, while 
                            also compensating for diagonal movement to obtain the total cost of passing through 
                            the pixel. 
                            The values of the Cost Raster can be integer or floating point, but they cannot be 
                            negative or zero.
    :param in_destination_data: A raster dataset that identifies the pixels from which the least-cost path is 
                            determined to the least costly source. This input consists of pixels that have valid
                            values, and the remaining pixels must be assigned NoData. Values of 0 are valid.
    :param destination_field: The field used to obtain values for the destination locations.
    :param path_type: A keyword defining the manner in which the values and zones on the input destination
                            data will be interpreted in the cost path calculations:
                            EACH_CELL-A least-cost path is determined for each pixel with valid values on the 
                            input destination data, and saved on the output raster. Each cell of the input 
                            destination data is treated separately, and a least-cost path is determined for each from cell.
                            EACH_ZONE-A least-cost path is determined for each zone on the input destination data and
                            saved on the output raster. The least-cost path for each zone begins at the pixel with the
                            lowest cost distance weighting in the zone.
                            BEST_SINGLE-For all pixels on the input destination data, the least-cost path is derived
                            from the pixel with the minimum of the least-cost paths to source cells.
    :param max_distance: The threshold that the accumulative cost values cannot exceed. If an accumulative cost
                            distance exceeds this value, the output value for the pixel location will be NoData. 
                            The maximum distance defines the extent for which the accumulative cost distances are
                            calculated. The default distance is to the edge of the output raster.
    :param source_field: The field used to assign values to the source locations. It must be an integer type.
                            If the Value Raster has been set, the values in that input will take precedence over
                            any setting for the Source Field.
    :param source_cost_multiplier: The threshold that the accumulative cost values cannot exceed. If an accumulative
                            cost distance exceeds this value, the output value for the pixel location will be 
                            NoData. The maximum distance defines the extent for which the accumulative cost 
                            distances are calculated. The default distance is to the edge of the output raster.
    :param source_start_cost: The starting cost from which to begin the cost calculations. This parameter allows
                            for the specification of the fixed cost associated with a source. Instead of starting
                            at a cost of 0, the cost algorithm will begin with the value set here.
                            The default is 0. The value must be 0 or greater. A numeric (double) value or a field
                            from the Source Raster can be used for this parameter.
    :param source_resistance_rate: This parameter simulates the increase in the effort to overcome costs as the
                            accumulative cost increases. It is used to model fatigue of the traveler. The growing
                            accumulative cost to reach a pixel is multiplied by the resistance rate and added to 
                            the cost to move into the subsequent pixel.
                            It is a modified version of a compound interest rate formula that is used to calculate
                            the apparent cost of moving through a pixel. As the value of the resistance rate increases,
                            it increases the cost of the pixels that are visited later. The greater the resistance rate, 
                            the higher the cost to reach the next pixel, which is compounded for each subsequent movement. 
                            Since the resistance rate is similar to a compound rate and generally the accumulative cost 
                            values are very large, small resistance rates are suggested, such as 0.005 or even smaller, 
                            depending on the accumulative cost values.
                            The default is 0. The values must be 0 or greater. A numeric (double) value or a field from
                            the Source Raster can be used for this parameter.
    :param source_capacity: Defines the cost capacity for the traveler for a source. The cost calculations continue for
                            each source until the specified capacity is reached.
                            The default capacity is to the edge of the output raster. The values must be greater than 0. 
                            A double numeric value or a field from the Source Raster can be used for this parameter.
    :param source_direction: Defines the direction of the traveler when applying the source resistance rate and the source
                            starting cost.
                            From Source - The source resistance rate and source starting cost will be applied beginning
                            at the input source and moving out to the nonsource cells. This is the default.
                            To Source-The source resistance rate and source starting cost will be applied beginning at
                            each nonsource cell and moving back to the input source.
                            Either specify the From Source or To Source keyword, which will be applied to all sources,
                            or specify a field in the Source Raster that contains the keywords to identify the direction
                            of travel for each source. That field must contain the string From Source or To Source.
    
    :return: output raster with function applied
    """  
    layer1, in_source_data, raster_ra1 = _raster_input(in_source_data)
    layer2, in_cost_raster, raster_ra2 = _raster_input(in_cost_raster)
    layer3, in_destination_data, raster_ra3 = _raster_input(in_destination_data)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "ShortestPath",           
            "PrimaryInputParameterName" : "in_source_data",
            "OutputRasterParameterName":"out_path_raster",
            "in_source_data" : in_source_data, 
            "in_cost_raster" : in_cost_raster,
            "in_destination_data" : in_destination_data
                
        }
    }    
            
    if destination_field is not None:
        template_dict["rasterFunctionArguments"]["destination_field"] = destination_field
    
    if path_type is not None:
        template_dict["rasterFunctionArguments"]["path_type"] = path_type
    
    if max_distance is not None:
        template_dict["rasterFunctionArguments"]["maximum_distance"] = max_distance
    
    if source_cost_multiplier is not None:
        template_dict["rasterFunctionArguments"]["source_cost_multiplier"] = source_cost_multiplier
    
    if source_start_cost is not None:
        template_dict["rasterFunctionArguments"]["source_start_cost"] = source_start_cost
    
    if source_resistance_rate is not None:
        template_dict["rasterFunctionArguments"]["source_resistance_rate"] = source_resistance_rate
    
    if source_capacity is not None:
        template_dict["rasterFunctionArguments"]["source_capacity"] = source_capacity
    
    if source_direction is not None:
        template_dict["rasterFunctionArguments"]["source_direction"] = source_direction

    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_source_data"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_cost_raster"] = raster_ra2
    function_chain_ra["rasterFunctionArguments"]["in_destination_data"] = raster_ra3

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def flow_distance(input_stream_raster,
                  input_surface_raster,
                  input_flow_direction_raster=None,
                  distance_type=None):
                     
    """
    This function computes, for each cell, the minimum downslope 
    horizontal or vertical distance to cell(s) on a stream or
    river into which they flow. If an optional flow direction 
    raster is provided, the down slope direction(s) will be 
    limited to those defined by the input flow direction raster.

    Parameters
    ----------
    :param input_stream_raster: An input raster that represents a linear stream network
    :param input_surface_raster: The input raster representing a continuous surface.
    :param input_flow_direction_raster: The input raster that shows the direction of flow out of each cell.
    :param distance_type: VERTICAL or HORIZONTAL distance to compute; if not
                                 specified, VERTICAL distance is computed.
    :return: output raster with function applied
    """
    layer1, input_stream_raster, raster_ra1 = _raster_input(input_stream_raster)  
    layer2, input_surface_raster, raster_ra2 = _raster_input(input_surface_raster)

        
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "FlowDistance_sa",           
            "PrimaryInputParameterName" : "in_stream_raster",
            "OutputRasterParameterName" : "out_raster",
            "in_stream_raster" : input_stream_raster, 
            "in_surface_raster" : input_surface_raster,
             
        }
    }    
    if input_flow_direction_raster is not None:
        layer3, input_flow_direction_raster, raster_ra3 = _raster_input(input_flow_direction_raster)
        template_dict["rasterFunctionArguments"]["in_flow_direction_raster"] = input_flow_direction_raster

    if distance_type is not None:
        template_dict["rasterFunctionArguments"]["distance_type"] = distance_type
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra['rasterFunctionArguments']["in_stream_raster"] = raster_ra1
    function_chain_ra['rasterFunctionArguments']["in_surface_raster"] = raster_ra2
    if input_flow_direction_raster is not None:
        function_chain_ra["rasterFunctionArguments"]["in_flow_direction_raster"] = raster_ra3

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def flow_accumulation(input_flow_direction_raster,
                      input_weight_raster=None,
                      data_type=None):
                     
    """"    
    Replaces cells of a raster corresponding to a mask 
    with the values of the nearest neighbors.

    :param input_flow_direction_raster: The input raster that shows the direction of flow out of each cell.
    :param input_weight_raster: An optional input raster for applying a weight to each cell.
    :param data_type: INTEGER, FLOAT, DOUBLE
    :return: output raster with function applied

    """
    layer1, input_flow_direction_raster, raster_ra1 = _raster_input(input_flow_direction_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "FlowAccumulation_sa",           
            "PrimaryInputParameterName" : "in_flow_direction_raster",
            "OutputRasterParameterName" : "out_accumulation_raster",
            "in_flow_direction_raster" : input_flow_direction_raster
             
        }
    }    
    if input_weight_raster is not None:
        layer2, input_weight_raster, raster_ra2 = _raster_input(input_weight_raster) 
        template_dict["rasterFunctionArguments"]["in_weight_raster"] = input_weight_raster

    if data_type is not None:
        template_dict["rasterFunctionArguments"]["data_type"] = data_type
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_flow_direction_raster"] = raster_ra1    
    if input_weight_raster is not None:
        function_chain_ra['rasterFunctionArguments']["in_weight_raster"] = raster_ra2    

    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def flow_direction(input_surface_raster,
                   force_flow= "NORMAL",
                   flow_direction_type= "D8"):
    """
    Replaces cells of a raster corresponding to a mask 
    with the values of the nearest neighbors.

    Parameters
    ----------
    :param input_surface_raster: The input raster representing a continuous surface.
    :param force_flow: NORMAL or FORCE, Specifies if edge cells will always flow outward or follow normal flow rules.
    :param flow_direction_type: Specifies which flow direction type to use.
                          D8 - Use the D8 method. This is the default.
                          MFD - Use the Multi Flow Direction (MFD) method.
                          DINF - Use the D-Infinity method.
    
    :return: output raster with function applied

    """
    layer, input_surface_raster, raster_ra = _raster_input(input_surface_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "FlowDirection_sa",           
            "PrimaryInputParameterName" : "in_surface_raster",
            "OutputRasterParameterName" : "out_flow_direction_raster",
            "in_surface_raster" : input_surface_raster,
            "force_flow" : force_flow,
            "flow_direction_type" : flow_direction_type
             
        }
    }    
        
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_surface_raster"] = raster_ra    
    
    return _gbl_clone_layer(layer, template_dict, function_chain_ra)


def fill(input_surface_raster,        
         zlimit=None):
    """
    Fills sinks in a surface raster to remove small imperfections in the data

    Parameters
    ----------
    :param input_surface_raster: The input raster representing a continuous surface.
    :param zlimit: Data type - Double. Maximum elevation difference between a sink and
            its pour point to be filled.
            If the difference in z-values between a sink and its pour point is greater than the z_limit, that sink will not be filled.
            The value for z-limit must be greater than zero.
            Unless a value is specified for this parameter, all sinks will be filled, regardless of depth.
    
    :return: output raster with function applied

    """
    layer, input_surface_raster, raster_ra = _raster_input(input_surface_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "Fill_sa",           
            "PrimaryInputParameterName" : "in_surface_raster",
            "OutputRasterParameterName" : "out_surface_raster",
            "in_surface_raster" : input_surface_raster            
             
        }
    }    
    
    if zlimit is not None:
        template_dict["rasterFunctionArguments"]["z_limit"] = zlimit
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_surface_raster"] = raster_ra    
    
    return _gbl_clone_layer(layer, template_dict, function_chain_ra)


def nibble(input_raster,
           input_mask_raster,
           nibble_values= "ALL_VALUES",
           nibble_no_data= "PRESERVE_NODATA",
           input_zone_raster=None):
    """
    Replaces cells of a raster corresponding to a mask 
    with the values of the nearest neighbors.

    Parameters
    ----------
    :param input_raster: The input rater to nibble.
                   The input raster can be either integer or floating point type.
    :param input_mask_raster: The input raster to use as the mask.
    :param nibble_values: possbile options are "ALL_VALUES" and "DATA_ONLY".
        Default is "ALL_VALUES"
    :param nibble_no_data: PRESERVE_NODATA or PROCESS_NODATA possible values;
        Default is PRESERVE_NODATA.
    :param input_zone_raster: The input raster that defines the zones to use as the mask.
    
    :return: output raster with function applied

    """
    layer1, input_raster, raster_ra1 = _raster_input(input_raster)
    layer2, input_mask_raster, raster_ra2 = _raster_input(input_mask_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "Nibble_sa",           
            "PrimaryInputParameterName" : "in_raster",
            "OutputRasterParameterName" : "out_raster",
            "in_raster" : input_raster,
            "in_mask_raster" : input_mask_raster,
            "nibble_values" : nibble_values,
            "nibble_nodata" : nibble_no_data
             
        }
    }    
    
    if input_zone_raster is not None:
        layer3, input_zone_raster, raster_ra3 = _raster_input(input_zone_raster)
        template_dict["rasterFunctionArguments"]["in_zone_raster"] = input_zone_raster
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_raster"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_mask_raster"] = raster_ra2
    if input_zone_raster is not None:
        function_chain_ra["rasterFunctionArguments"]["in_zone_raster"] = raster_ra3
    
    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def stream_link(input_raster,
                input_flow_direction_raster):
    """
    Assigns unique values to sections of a raster linear network between intersections

    Parameters
    ----------
    :param input_raster:     An input raster that represents a linear stream network.
    :param input_flow_direction_raster: The input raster that shows the direction of flow out of each cell
    :return: output raster with function applied

    """
    layer1, input_raster, raster_ra1 = _raster_input(input_raster)
    layer2, input_flow_direction_raster, raster_ra2 = _raster_input(input_flow_direction_raster)  
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "StreamLink_sa",           
            "PrimaryInputParameterName" : "in_stream_raster",
            "OutputRasterParameterName" : "out_raster",
            "in_stream_raster" : input_raster,
            "in_flow_direction_raster" : input_flow_direction_raster                 
        }
    }    
    
    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_stream_raster"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_flow_direction_raster"] = raster_ra2
        
    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)


def watershed(input_flow_direction_raster,
              input_pour_point_data,
              pour_point_field=None):
    """
    Replaces cells of a raster corresponding to a mask 
    with the values of the nearest neighbors.

    Parameters
    ----------
    :param input_flow_direction_raster: The input raster that shows the direction of flow out of each cell.
    :param input_pour_point_data: The input pour point locations. For a raster, this represents cells above
                            which the contributing area, or catchment, will be determined. All cells that 
                            are not NoData will be used as source cells.
                            For a point feature dataset, this represents locations above which the contributing
                            area, or catchment, will be determined.
    :param pour_point_field: Field used to assign values to the pour point locations. If the pour point dataset is a
                       raster, use Value.
                       If the pour point dataset is a feature, use a numeric field. If the field contains 
                       floating-point values, they will be truncated into integers.    
    :return: output raster with function applied

    """
    layer1, input_flow_direction_raster, raster_ra1 = _raster_input(input_flow_direction_raster)  
    layer2, input_pour_point_data, raster_ra2 = _raster_input(input_pour_point_data)
            
    template_dict = {
        "rasterFunction" : "GPAdapter",
        "rasterFunctionArguments" : {
            "toolName" : "Watershed_sa",           
            "PrimaryInputParameterName" : "in_flow_direction_raster",
            "OutputRasterParameterName" : "out_raster",
            "in_flow_direction_raster" : input_flow_direction_raster,
            "in_pour_point_data" : input_pour_point_data
        }
    }    
    
    if pour_point_field is not None:
        template_dict["rasterFunctionArguments"]["pour_point_field"] = pour_point_field

    
    function_chain_ra = copy.deepcopy(template_dict)
    function_chain_ra["rasterFunctionArguments"]["in_flow_direction_raster"] = raster_ra1
    function_chain_ra["rasterFunctionArguments"]["in_pour_point_data"] = raster_ra2
        
    return _gbl_clone_layer(layer1, template_dict, function_chain_ra)
