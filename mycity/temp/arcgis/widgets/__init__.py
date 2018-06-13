"""
The arcgis.widgets module provides components for visualizing GIS data and analysis.
This module includes the MapView Jupyter notebook widget for visualizing maps and layers
"""
import json
import random
import string
from uuid import uuid4

from arcgis.features import FeatureSet, Feature, FeatureCollection
from arcgis.raster import ImageryLayer
from arcgis.gis import Layer
from arcgis.gis import Item
from arcgis.mapping import WebMap
from arcgis._impl.common._utils import _date_handler
from arcgis.geometry import Point, Polygon, Polyline, MultiPoint, Geometry
try:
    from ipywidgets import widgets
except:
    from IPython.html import widgets

try:
    from traitlets import Unicode, Int, List, Bool, Dict
except:
    from IPython.utils.traitlets import Unicode, Int, List, Bool, Dict

import logging

_LOGGER = logging.getLogger(__name__)


class MapView(widgets.DOMWidget):
    """Mapping widget for Jupyter Notebook"""

    #region Class, instance and interop variables
    _view_name = Unicode('MapView').tag(sync=True)
    _view_module = Unicode('mapview').tag(sync=True)

    # value = Unicode('Hello World!').tag(sync=True)

    basemap = Unicode('topo').tag(sync=True)
    _basemap = Unicode('topo').tag(sync=True)
    basemaps = List([]).tag(sync=True)
    _gallerybasemaps = List([]).tag(sync=True)
    _gbasemaps_def = List([]).tag(sync=True)
    _js_basemap = Unicode('').tag(sync=True)
    _js_renderer = Unicode('').tag(sync=True)
    _js_layer_list = Unicode('').tag(sync=True)  # sync layer - to keep track of layers represented in JS code
    _js_interactive_drawn_graphic = Unicode('').tag(sync=True)  # get geometries of interactively drawn graphics
    _layerId_to_remove = Unicode('').tag(sync=True)
    _widget_layer_list = [] #internal to keep track of layers added, removed from widget
    _widget_graphics_list = [] #internal to keep track of layers sent to draw() of the widget
    _webmap_added_layer_list = []
    _webmap_drawn_layer_list = []
    width = Unicode('100%').tag(sync=True)
    zoom = Int(2).tag(sync=True)
    id = Unicode('').tag(sync=True)
    center = List([0, 0]).tag(sync=True)
    mode = Unicode('navigate').tag(sync=True)
    _addlayer = Unicode('').tag(sync=True)
    start_time = Unicode('').tag(sync=True)
    end_time = Unicode('').tag(sync=True)
    _extent = Unicode('').tag(sync=True)
    _jsextent = Unicode('').tag(sync=True)
    _token_info = Unicode('').tag(sync=True)
    _arcgis_url = Unicode('').tag(sync=True)
    _swipe_div = Unicode('').tag(sync=True)
    _gallery_initialized = False # Used to keep track if GalleryBasemaps has been called
    #endregion

    def __init__(self, **kwargs):
        """Constructor of Map widget.
        Accepts the following keyword arguments:
        gis     The gis instance with which the map widget works, used for authentication, and adding secure layers and
                private items from that GIS
        item    web map item from portal with which to initialize the map widget
        """
        super(MapView, self).__init__(**kwargs)
        self._click_handlers = widgets.CallbackDispatcher()
        self._draw_end_handlers = widgets.CallbackDispatcher()

        self.on_msg(self._handle_map_msg)

        self.basemaps = ['dark-gray',
                        'dark-gray-vector',
                        'gray',
                        'gray-vector',
                        'hybrid',
                        'national-geographic',
                        'oceans',
                        'osm',
                        'satellite',
                        'streets',
                        'streets-navigation-vector',
                        'streets-night-vector',
                        'streets-relief-vector',
                        'streets-vector',
                        'terrain',
                        'topo',
                        'topo-vector']
        self._swipe_div = 'swipeDiv' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))

        self._gis = kwargs.pop('gis', None)
        if self._gis is not None and self._gis._con._username is not None:  # not anonymous
            token_info = {
                "server": self._gis._con.baseurl.replace('http://', 'https://'),
                "tokenurl": (self._gis._con.baseurl +
                             'generateToken').replace('http://', 'https://'),
                "username": self._gis._con._username,
                "password": self._gis._con._password
            }
            self._token_info = json.dumps(token_info)
            # if self._gis.properties.portalName != 'ArcGIS Online':
            self._arcgis_url = self._gis._con.baseurl + 'content/items'

        self.item = kwargs.pop('item', None)

        #construct a webmap in memory
        self._webmap = WebMap()
        self._widget_layer_list = []  # initialize to empty list.
        self._widget_graphics_list = []  # initialize to empty list for each widget.
        self._webmap_added_layer_list = []  # keep track of layers in internal webmap from add_layer()
        self._webmap_drawn_layer_list = []  # keep track of layers in internal webmap from draw()
        self._smartmapping_layer_list = []  # keep track of layers that are rendered using smart mapping.

        if self.item is not None:
            if isinstance(self.item, WebMap):
                self.item = self.item.item

                # constuct the internal webmap using the passed web map item
                self._webmap = WebMap(self.item)

                # use internal webmap layers as widget layers
                self._widget_layer_list = self._webmap.layers
                for l in self._webmap.layers:
                    self._webmap_added_layer_list.append(l.id)  # append layer ids to added layer list.

            if 'type' in self.item and self.item.type.lower() != 'web map':
                raise TypeError("item type must be web map")
            self.id = self.item.id

    def draw(self, shape, popup=None, symbol=None, attributes=None):
        """
        Draws a shape on the map widget. You can draw anything from known geometries, coordinate pairs, FeatureSet
        objects.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        shape                  Required object.

                               Known geometries:
                               shape is one of ["circle", "downarrow", "ellipse", "extent", "freehandpolygon",
                                                "freehandpolyline", "leftarrow", "line", "multipoint", "point",
                                                "polygon", "polyline", "rectangle", "rightarrow", "triangle",
                                                "uparrow", or geometry dict object]

                               Coordinate pair: specify shape as a list of [lat, long]. Eg: [34, -81]

                               FeatureSet: shape can be a FeatureSet object.
        ------------------     --------------------------------------------------------------------
        popup                  Optional dict. Dict containing "title" and "content" as keys that will be displayed
                               when the shape is clicked. In case of a FeatureSet, "title" and "content" are names of
                               attributes of the features in the FeatureSet instead of actual string values for title
                               and content.
        ------------------     --------------------------------------------------------------------
        symbol                 Optional dict. symbol is specified in json format as described at
                               http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r3000000n5000000. A
                               default symbol is used if one is not specified.

                               Tip: a helper utility to get the symbol format for several predefined symbols is
                               available at http://esri.github.io/arcgis-python-api/tools/symbol.html
        ------------------     --------------------------------------------------------------------
        attributes             Optional dict. Specify a dict containing name value pairs of fields and field values
                               associated with the graphic.
        ==================     ====================================================================
        """

        title = attributes['title'] if attributes and 'title' in attributes else "Notebook sketch layer"

        if isinstance(shape, list) and len(shape) == 2:  # [lat, long] pair
            shape = {'x': shape[1], 'y': shape[0], "spatialReference": {"wkid": 4326}, 'type': 'point'}

        elif isinstance(shape, tuple):  # (lat, long) pair
            shape = {'x': shape[1], 'y': shape[0], "spatialReference": {"wkid": 4326}, 'type': 'point'}

        elif isinstance(shape, dict) and 'location' in shape: # geocoded location
            shape = {'x': shape['location']['x'], 'y': shape['location']['y'],
                     "spatialReference": {"wkid": 4326}, 'type': 'point'}

        if isinstance(shape, FeatureSet):
            fset = shape
            for feature in fset.features:
                if popup:
                    popup_dict = {'title':feature.attributes[popup['title']],
                                  'content':feature.attributes[popup['content']]}
                else:
                    popup_dict = None
                graphic = {
                    "geometry": feature.geometry,
                    "infoTemplate": popup_dict,
                    "symbol": symbol,
                    "attributes": feature.attributes
                }
                self.mode = json.dumps(graphic)

            #add as layer to internal webmap
            if popup:
                webmap_popup = {'title':"{" +popup['title']+"}",
                                'description':"{" + popup['content'] +"}"}
            else:
                webmap_popup = None

            # add at save time for consistency.
            self._webmap_drawn_layer_list.append({'data':shape,
                                                  'options':{'popup':webmap_popup, 'symbol':symbol, 'attributes':attributes,
                                                            'title':title, 'extent':self.extent}})

        elif isinstance(shape, dict):
            graphic = {
                "geometry": shape,
                "infoTemplate": popup,
                "symbol": symbol,
                "attributes": attributes
            }
            self.mode = json.dumps(graphic)
            # print(json.dumps(graphic))
            # build feature, then featureSet
            try:
                f = Feature(shape)
                fset = FeatureSet([f], geometry_type='esriGeometryPoint', spatial_reference={'wkid':4326})

                if popup:
                    webmap_popup = {'title':popup['title'], 'description':popup['content']}
                else:
                    webmap_popup = None

                # add at save time for consistency.
                self._webmap_drawn_layer_list.append({'data':fset,
                                                      'options':{'popup':webmap_popup, 'symbol':symbol, 'attributes':attributes,
                                              'title':title, 'extent':self.extent}})
            except:
                pass

        else:  # interactive sketches on map widget.
            self.mode = shape

    def add_layer(self, item, options=None):
        """
        Adds the specified layer or item to the map widget.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        item                   Required object. You can specify Item objects, Layer objects such as
                               FeatureLayer, ImageryLayer, MapImageLayer etc., FeatureSet and
                               FeatureCollection objects.
        ------------------     --------------------------------------------------------------------
        options                Optional dict. Specify visualization options such as renderer info,
                               opacity, definition expressions. See example below
        ==================     ====================================================================

        .. code-block:: python  (optional)

           USAGE EXAMPLE: Add a feature layer with smart mapping renderer and a definition expression to limit the
           features drawn.

           map1 = gis.map("Seattle, WA")
           map1.add_layer(wa_streets_feature_layer, {'renderer':'ClassedSizeRenderer',
                                                     'filed_name':'DistMiles',
                                                     'opacity':0.75})
        """

        self._js_renderer = ''
        if isinstance(item, list):
            for lyr in item:
                self.add_layer(lyr, options)

        elif isinstance(item, dict) and 'function_chain' in item:
            js_layer = item['layer']._lyr_json
            options_dict = {
                    "imageServiceParameters": {
                        "renderingRule": item['function_chain']
                    }
                }

            if options is not None:
                options_dict.update(options)

            js_layer.update({
                "options": json.dumps(options_dict)
            })
            self._addlayer = json.dumps(js_layer)
            #add to widget's layer list
            self._widget_layer_list.append(item)

        elif isinstance(item, FeatureSet):
            fc = FeatureCollection.from_featureset(item)
            self.add_layer(fc, options)

        elif isinstance(item, Layer):
            if isinstance(item, FeatureCollection):  # apply symbol, title for FeatureCollections
                if not options:
                    options = {'title':'Notebook sketch layer'}
                if options and 'title' not in options:
                    options['title'] = 'Notebook sketch layer'
                if options and 'symbol' in options:
                    if hasattr(item.layer, 'layers'):
                        item.layer.layers[0].layerDefinition.drawingInfo['renderer']['symbol'] = options['symbol']
                    else:
                        item.layer.layerDefinition.drawingInfo['renderer']['symbol'] = options['symbol']

            js_layer = item._lyr_json

            if 'type' in js_layer:
                if js_layer['type'] == 'MapImageLayer':
                    js_layer['type'] = 'ArcGISTiledMapServiceLayer' if 'TilesOnly' in item.properties.capabilities else 'ArcGISDynamicMapServiceLayer'

            if options is not None:
                if 'options' in js_layer:  # ImageryLayers may have rendering rules in options
                    lyr_options = json.loads(js_layer['options'])
                    lyr_options.update(options)
                    js_layer.update({'options': json.dumps(lyr_options)})
                else:
                    js_layer.update({"options": json.dumps(options)})
            else:
                options = {} #to store extent and other properties
            if 'uses_gbl' in js_layer:
                if js_layer["uses_gbl"] is True:
                    _LOGGER.warning("""Imagery layer object containing global functions in the function chain cannot be used for dynamic visualization.
                                   \nThe layer output must be saved as a new image service before it can be visualized. Use save() method of the layer object to create the processed output.""")
                    return None
            self._addlayer = json.dumps(js_layer,
                                        default=_date_handler)
            options['extent'] = self.extent

            self._webmap.add_layer(item, options)
            # add to widget's layer list
            self._widget_layer_list.append(item)

            # if smart mapping, then add it to the internal list
            if options and 'renderer' in options:
                self._smartmapping_layer_list.append({item: options})

        elif 'layers' in item:  # items as well as services
            if item.layers is None:
                raise RuntimeError('No layers accessible/available in this item or service')
            for lyr in item.layers:
                self.add_layer(lyr, options)  # recurse.
                # js_layer = lyr._lyr_json
                # if options is not None:
                #     js_layer.update({"options": json.dumps(options)})
                # self._addlayer = json.dumps(js_layer)
                #
                # self._webmap.add_layer(lyr, options)
                # # add to widget's layer list
                # self._widget_layer_list.append(item)

        else:  # dict {'url':'xxx', 'type':'yyy', 'opacity':'zzz' ...}
            if options is not None:
                item.update({"options": json.dumps(options)})

            self._addlayer = json.dumps(item)

    def clear_graphics(self):
        """
        Clear the graphics drawn on the map widget. Graphics are shapes drawn using the 'draw()' method.
        :return:
        """
        self.mode = "###clear_graphics"
        self._js_interactive_drawn_graphic = ""
        self._webmap_drawn_layer_list = []

    def set_time_extent(self, start_time, end_time):
        self.start_time = start_time
        self.end_time = end_time

    def remove_layers(self, layers=None):
        """
        Removes the layers added to the map widget. You can get the list of layers added to the widget by querying the
        'layers' property.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        layers                 Optional list. Specify the list of layers to be removed from the map widget. You can get
                               the list of layers on the map by querying the 'layers' property.

                               If not specified, it removes all layers added to the widget.
        ==================     ====================================================================
        :return:
            True if layer is successfully removed. Else, False.
        """

        if not layers:
            # self.mode = "###remove_layers"
            # self._js_layer_list = ''
            # for l in self._webmap.layers:
            #     self._webmap.remove_layer(l)
            # return True
            if self.layers:
                while len(self.layers) > 0:
                    self.remove_layers(layers=self.layers)
                return True
            else:
                return True

        elif isinstance(layers, list):
            # removal is async. Hence, loop until there is no layer left.
            for layer in layers:
                #find index - common across all internal lists
                index_to_remove = self._widget_layer_list.index(layer)

                #region remove from widget
                js_layers_parsed = json.loads(self._js_layer_list)
                js_layer_to_remove = js_layers_parsed[index_to_remove]

                self._layerId_to_remove = js_layer_to_remove['id']

                js_layers_parsed.remove(js_layer_to_remove)

                # remove the layer from synced trait
                self._js_layer_list = json.dumps(js_layers_parsed)
                #endregion

                #region remove from webmap
                webmap_layer_to_remove = self._webmap.layers[index_to_remove]
                self._webmap.remove_layer(webmap_layer_to_remove)
                #endregion

                #region remove from widget layer list
                self._widget_layer_list.remove(layer)
                #endregion
            return True

        else:
            return False

    @property
    def gallery_basemaps(self):
        """
        Retrieves the portal's custom basemap group and populates properties
        """

        if not self._gallery_initialized:
        #if len(self._gallerybasemaps) == 0:
            bmlyrs = []
            bms = []
            bmquery = self._gis.properties['basemapGalleryGroupQuery']
            basemapsgrp = self._gis.groups.search(bmquery, outside_org=True)
            if len(basemapsgrp) == 1:
                for bm in basemapsgrp[0].content():
                    if bm.type.lower() == 'web map': # Only use WebMaps
                        bms.append(bm.title.lower().replace(" ", "_"))  # item title will be name
                        item_data = bm.get_data()  # we have to get JSON definition to pass through
                        if item_data is not None:
                            bmlyrs.append(item_data['baseMap']['baseMapLayers'])
                #self._gbasemaps_def = bmlyrs
                self._gbasemaps_def = self._gbasemaps_def + bmlyrs
                #nm = self._gis.properties['defaultBasemap']['title']
                #print("Loading Gallery Basemaps....")
                #self._gallerybasemaps = bms
                self._gallerybasemaps = self._gallerybasemaps + bms
                self._gallery_initialized = True
                return self._gallerybasemaps
            else:
                #print("Basemap Group '" + str(bmquery) + "' could not be found...")
                #return [] # If unable to find the group, return empty list
                return self._gallerybasemaps # Return whatever state List is in, even if empty
        else:
            return self._gallerybasemaps

    @property
    def basemap(self):
        """
        Name of the basemap displayed on the map widget. To change the basemap, simply assign it a different value.
        You can get the list of all basemap values by calling the `basemaps` property.
        :return:
        """
        return self._basemap

    @basemap.setter
    def basemap(self, value):
        if isinstance(value, str):
            if (value in self.basemaps):
                self._basemap = value
            elif (value in self.gallery_basemaps): # this should initialize
                self._basemap = value
            else:
                print("Basemap '" + str(value) + "' is not a valid basemap name.")
        self._update_webmap_basemap()

    def _update_webmap_basemap(self):
        """
        Internal method, reads the mapwidget's basemap and applied that for the internal web map
        :return:
        """

        if self._js_basemap:
            basemap_urls = json.loads(self._js_basemap)
            basemap_layers = []

            for layer in basemap_urls:
                #construct basemap layer
                basemap_layers_dict = {'id': uuid4().__str__(),
                                       'visibility': True,
                                       'opacity': 1,
                                       'title': layer['title']}

                if 'vector' in layer['title']:
                    basemap_layers_dict['layerType'] = "VectorTileLayer"
                    basemap_layers_dict['styleUrl'] = layer['url']
                else:
                    basemap_layers_dict['layerType'] = "ArcGISTiledMapServiceLayer"
                    basemap_layers_dict['url'] = layer['url']

                #append to list of basemap layer
                basemap_layers.append(basemap_layers_dict)

            #update basemap in internal web map
            self._webmap._basemap['baseMapLayers'] = basemap_layers
            self._webmap._basemap['title'] = layer['title']
            self._webmap._webmapdict['baseMap'] = self._webmap._basemap


        # Allow for a WebMap item to be passed in and set.  This is useful if someone
        #  finds some other WebMap in AGOL/Portal that they would like to use in this
        #  notebook.  In this case, you need to add it to the current set.
        #  This will utilize the gallery_basemaps objects for adding the new basemap.
        #elif (isinstance(value, Item)):
        #    if value.type.lower() == "web map":
        #        webmapitem = value
        #        bmlyrs = []
        #        bms = []
        #        bms.append(webmapitem.title.lower().replace(" ", "_")) # item title will be name
        #        item_data = webmapitem.get_data()  # we have to get JSON definition to pass through
        #        if item_data is not None:
        #            bmlyrs.append(item_data['baseMap']['baseMapLayers'])
        #            self._gbasemaps_def = self._gbasemaps_def + bmlyrs
        #            self._gallerybasemaps = self._gallerybasemaps + bms
        #            self._basemap = bms[0]
        #            print('Set Map Widget Basemap to WebMap Item basemap layers.')
        #        else:
        #            print("WebMap item appears to have no item_data.")

    @property
    def extent(self):
        if self._jsextent is not None and self._jsextent != '':  # first preference to _jsextent
            return json.loads(self._jsextent)
        elif self._extent:
            ext = json.loads(self._extent)
            if not 'spatialReference' in ext:
                ext['spatialReference'] = {'wkid':4326, 'latestWkid':4326}
            return ext

    @extent.setter
    def extent(self, value):
        if isinstance(value, (tuple, list)):
            if all(isinstance(el, list) for el in value):
                extent = {
                    'xmin': value[0][0],
                    'ymin': value[0][1],
                    'xmax': value[1][0],
                    'ymax': value[1][1]
                }
                value = extent
        self._extent = json.dumps(value)

    @property
    def layers(self):
        """
        The list of layers added to the map widget using the `add_layers()` method.
        :return:
        """
        return self._widget_layer_list

    def on_click(self, callback, remove=False):
        """Register a callback to execute when the map is clicked.

        The callback will be called with one argument,
        the clicked widget instance.

        Parameters
        ----------
        remove : bool (optional)
            Set to true to remove the callback from the list of callbacks."""
        self._click_handlers.register_callback(callback, remove=remove)

    def on_draw_end(self, callback, remove=False):
        """Register a callback to execute when something is drawn

        The callback will be called with two argument,
        the clicked widget instance, and the geometry drawn

        Parameters
        ----------
        remove : bool (optional)
            Set to true to remove the callback from the list of callbacks."""
        self._draw_end_handlers.register_callback(callback, remove=remove)
        #todo - get geometry and call add_layer of webmap and sync the layer lists.

    def _handle_map_msg(self, _, content, buffers):
        """Handle a msg from the front-end.

        Parameters
        ----------
        content: dict
            Content of the msg."""

        if content.get('event', '') == 'mouseclick':
            self._click_handlers(self, content.get('message', None))
        if content.get('event', '') == 'draw-end':
            self._draw_end_handlers(self, content.get('message', None))

    def _process_drawn_graphics(self):
        """internal method to add graphics layers to web map.
        This needs to be done at the end since drawing on widget is async"""
        if self._webmap_drawn_layer_list:
            for element in self._webmap_drawn_layer_list:
                self._webmap.add_layer(element['data'], element['options'])

        if self._js_interactive_drawn_graphic:
            # geometry types could be one of [polyline, polygon, multipoint]
            drawn_graphic = json.loads(self._js_interactive_drawn_graphic)
            if drawn_graphic:
                for element in drawn_graphic:
                    # construct a Geometry object
                    if element['geometry']['type'] == 'polyline':
                        geom = Polyline(element['geometry'])
                    elif element['geometry']['type'] == 'polygon':
                        geom = Polygon(element['geometry'])
                    elif element['geometry']['type'] == 'multipoint':
                        geom = MultiPoint(element['geometry'])
                    elif element['geometry']['type']=='point':
                        geom = Point(element['geometry'])
                    else:
                        geom = Geometry(element['geometry'])

                    # construct a Feature and FeatureSet
                    feat = Feature(geom)
                    fset = FeatureSet([feat])

                    self._webmap.add_layer(fset, {'title':'Map notes'})

    def _process_smart_mapping(self):
        """internal method to insert smart mapping renderer info if used"""
        js_layers_parsed = json.loads(self._js_layer_list)
        for items in self._smartmapping_layer_list:
            lyr = list(items.keys())[0]
            opt = list(items.values())[0]
            # find the index in web map
            try:
                sm_layer_index = self._widget_layer_list.index(lyr)
                js_sm_layer = js_layers_parsed[sm_layer_index]
                wm_sm_layer = self._webmap._webmapdict['operationalLayers'][sm_layer_index]

                # region - heatmap renderer
                if opt['renderer'] in ['HeatmapRenderer', 'ClassedColorRenderer', 'ClassedSizeRenderer']:
                    rend_dict = js_sm_layer['renderer']

                    # update web map renderer
                    if 'featureCollection' not in wm_sm_layer:  # regular web layer
                        wm_sm_layer['layerDefinition']['drawingInfo'] = {'renderer': rend_dict}
                    else:
                        wm_sm_layer['featureCollection']['layers'][0]['layerDefinition']['drawingInfo'] = \
                            {'renderer': rend_dict}
                # endregion

            except ValueError:
                continue  # that layer with smart mapping must have been removed at a later time

    def save(self, item_properties, thumbnail=None, metadata=None, owner=None, folder=None):
        """
        Save the map widget object into a new web map Item in your GIS.

        .. note::
            If you started out with a fresh map widget object, use this method to save it as a the web map item in your
            GIS.

            If you started with a map widget object from an existing web map item or WebMap object, calling this method
            will create a web map new item with your changes. If you want to update the existing web map item with your
            changes, call the `update()` method instead.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        item_properties     Required dictionary. See table below for the keys and values.
        ---------------     --------------------------------------------------------------------
        thumbnail           Optional string. Either a path or URL to a thumbnail image.
        ---------------     --------------------------------------------------------------------
        metadata            Optional string. Either a path or URL to the metadata.
        ---------------     --------------------------------------------------------------------
        owner               Optional string. User object corresponding to the desired owner of this
                            item. Defaults to the logged in user.
        ---------------     --------------------------------------------------------------------
        folder              Optional string. Name of the folder where placing item.
        ===============     ====================================================================

        *Key:Value Dictionary Options for Argument item_properties*

        =================  =====================================================================
        **Key**            **Value**
        -----------------  ---------------------------------------------------------------------
        typeKeywords       Optional string. Provide a lists all sub-types, see URL 1 below for valid values.
        -----------------  ---------------------------------------------------------------------
        description        Optional string. Description of the item.
        -----------------  ---------------------------------------------------------------------
        title              Optional string. Name label of the item.
        -----------------  ---------------------------------------------------------------------
        tags               Optional string. Tags listed as comma-separated values, or a list of strings.
                           Used for searches on items.
        -----------------  ---------------------------------------------------------------------
        snippet            Optional string. Provide a short summary (limit to max 250 characters) of the what the item is.
        -----------------  ---------------------------------------------------------------------
        accessInformation  Optional string. Information on the source of the content.
        -----------------  ---------------------------------------------------------------------
        licenseInfo        Optional string.  Any license information or restrictions regarding the content.
        -----------------  ---------------------------------------------------------------------
        culture            Optional string. Locale, country and language information.
        -----------------  ---------------------------------------------------------------------
        access             Optional string. Valid values are private, shared, org, or public.
        -----------------  ---------------------------------------------------------------------
        commentsEnabled    Optional boolean. Default is true, controls whether comments are allowed (true)
                           or not allowed (false).
        -----------------  ---------------------------------------------------------------------
        culture            Optional string. Language and country information.
        =================  =====================================================================

        URL 1: http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r3000000ms000000

        :return:
            Item object corresponding to the new web map Item created.

        .. code-block:: python

           USAGE EXAMPLE: Save map widget as a new web map item in GIS

           map1 = gis.map("Italy")
           map1.add_layer(Italy_streets_item)
           map1.basemap = 'dark-gray'
           italy_streets_map = map1.save({'title':'Italy streets',
                                        'snippet':'Arterial road network of Italy',
                                        'tags':'streets, network, roads'})
        """

        # update the map extent
        self._webmap._extent = self.extent

        # add drawn graphics to web map
        self._process_drawn_graphics()

        # process smart mapping
        if self._smartmapping_layer_list:
            self._process_smart_mapping()

        # update the basemap
        self._update_webmap_basemap()

        return self._webmap.save(item_properties, thumbnail, metadata, owner, folder)

    def update(self, item_properties=None, thumbnail=None, metadata=None):
        """
        Updates the web map item that was used to create the MapWidget object. In addition, you can update
        other item properties, thumbnail and metadata.

        .. note::
            If you started out a MapView object from an existing web map item, use this method to update the web map
            item in your with your changes.

            If you started out with a fresh MapView object (without a web map item), calling this method will raise
            a RuntimeError exception. If you want to save the map widget into a new web map item, call the `save()`
            method instead.

            For item_properties, pass in arguments for only the properties you want to be updated.
            All other properties will be untouched.  For example, if you want to update only the
            item's description, then only provide the description argument in item_properties.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        item_properties     Optional dictionary. See table below for the keys and values.
        ---------------     --------------------------------------------------------------------
        thumbnail           Optional string. Either a path or URL to a thumbnail image.
        ---------------     --------------------------------------------------------------------
        metadata            Optional string. Either a path or URL to the metadata.
        ===============     ====================================================================

        *Key:Value Dictionary Options for Argument item_properties*

        =================  =====================================================================
        **Key**            **Value**
        -----------------  ---------------------------------------------------------------------
        typeKeywords       Optional string. Provide a lists all sub-types, see URL 1 below for valid values.
        -----------------  ---------------------------------------------------------------------
        description        Optional string. Description of the item.
        -----------------  ---------------------------------------------------------------------
        title              Optional string. Name label of the item.
        -----------------  ---------------------------------------------------------------------
        tags               Optional string. Tags listed as comma-separated values, or a list of strings.
                           Used for searches on items.
        -----------------  ---------------------------------------------------------------------
        snippet            Optional string. Provide a short summary (limit to max 250 characters) of the what the item is.
        -----------------  ---------------------------------------------------------------------
        accessInformation  Optional string. Information on the source of the content.
        -----------------  ---------------------------------------------------------------------
        licenseInfo        Optional string.  Any license information or restrictions regarding the content.
        -----------------  ---------------------------------------------------------------------
        culture            Optional string. Locale, country and language information.
        -----------------  ---------------------------------------------------------------------
        access             Optional string. Valid values are private, shared, org, or public.
        -----------------  ---------------------------------------------------------------------
        commentsEnabled    Optional boolean. Default is true, controls whether comments are allowed (true)
                           or not allowed (false).
        =================  =====================================================================

        URL 1: http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r3000000ms000000

        :return:
           A boolean indicating success (True) or failure (False).

        .. code-block:: python

           USAGE EXAMPLE: Interactively add a new layer and change the basemap of an existing web map.

           italy_streets_item = gis.content.search("Italy streets", "Web Map")[0]
           map1 = MapView(item = italy_streets_item)

           map1.add_layer(Italy_streets2)
           map1.basemap = 'dark-gray-vector'
           map1.update(thumbnail = './new_webmap.png')
        """

        if not self.item:
            raise RuntimeError('Item object missing, you should use `save()` method if you are creating a '
                               'new web map item')

        # update the map extent
        self._webmap._extent = self.extent

        # add drawn graphics to web map
        self._process_drawn_graphics()

        # process smart mapping
        if self._smartmapping_layer_list:
            self._process_smart_mapping()

        # update the basemap
        self._update_webmap_basemap()

        return self._webmap.update(item_properties, thumbnail, metadata)