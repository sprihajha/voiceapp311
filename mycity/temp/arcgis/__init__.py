__version__ = '1.4.0'

from . import features, geoanalytics, geocoding, geometry, geoprocessing, network, raster, realtime, schematics, mapping

from .gis import GIS
from .features.analysis import *
from .geocoding import geocode
#from .features._data.geodataset import SpatialDataFrame
__all__ = ['GIS', 'geocode', 'features',  'geoanalytics', 'geocoding', 'geometry', 'geoprocessing', 'network', 'raster',
           'realtime', 'schematics', 'mapping',
             'aggregate_points',
             'calculate_density',
             'connect_origins_to_destinations',
             'create_buffers',
             'create_drive_time_areas',
             'create_route_layers',
             'create_viewshed',
             'create_watersheds',
             'derive_new_locations',
             'dissolve_boundaries',
             'enrich_layer',
             'extract_data',
             'find_existing_locations',
             'find_hot_spots',
             'find_nearest',
             'find_similar_locations',
             'interpolate_points',
             'join_features',
             'merge_layers',
             'overlay_layers',
             'plan_routes',
             'summarize_nearby',
             'summarize_within',
             'trace_downstream'
           ]

def _jupyter_nbextension_paths():
    return [{
        'section': 'notebook',
        'src': 'widgets',
        'dest': 'arcgis',
        'require': 'arcgis/mapview'
    }]

