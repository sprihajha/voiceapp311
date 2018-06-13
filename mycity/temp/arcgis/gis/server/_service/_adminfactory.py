"""
Generates Layer Types from the given inputs.

"""
from __future__ import absolute_import
import os
from six import add_metaclass
from six.moves.urllib_parse import urlparse
from arcgis.gis import GIS
from arcgis.features.layer import FeatureLayer, FeatureLayerCollection
from arcgis.geocoding import Geocoder
from arcgis.geoprocessing._tool import Toolbox
from arcgis._impl.tools import _GeometryService as GeometryService
from arcgis.network import NetworkDataset
from arcgis.gis import Layer
from arcgis.mapping import VectorTileLayer
from arcgis.mapping import MapImageLayer
from arcgis.raster import ImageryLayer
from arcgis.schematics import SchematicLayers
from arcgis.mapping._types import SceneLayer
from .._common import ServerConnection
from ._geodataservice import GeoData
from ._layerfactory import Service
from ..admin._services import Service as AdminService
class AdminServiceFactory(type):
    """
    Generates an Administrative Service Object from a url or service object
    """
    def __call__(cls,
                 service,
                 gis,
                 initialize=False):
        """generates the proper type of layer from a given url"""

        url = service._url
        if isinstance(service, FeatureLayer) or \
           os.path.basename(url).isdigit():
            parent = Service(url=os.path.dirname(url), server=gis)
            return AdminServiceGen(parent, gis)
        elif isinstance(service, (NetworkDataset)):
            url = url.lower().replace("naserver", "mapserver")
            parent = Service(url=url, server=gis)
            return AdminServiceGen(parent, gis)
        else:
            connection = service._con
            admin_url = "%s.%s" % (
                os.path.dirname(url).lower().replace(
                    "/rest/", "/admin/"),
                os.path.basename(url))
            return AdminService(url=admin_url, connection=connection, server=gis)
        return type.__call__(cls, service, gis, False)
###########################################################################
@add_metaclass(AdminServiceFactory)
class AdminServiceGen(object):
    """
    The Layer class allows users to pass a url, connection or other object
    to the class and get back properties and functions specifically related
    to the service.

    Inputs:
       url - internet address to the service
       server - Server class
       item - Portal or AGOL Item class
    """
    def __init__(self, service, gis):
        iterable = None
        if iterable is None:
            iterable = ()
        super(AdminService, self).__init__(service, gis)