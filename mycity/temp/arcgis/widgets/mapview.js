// leave at least 2 line with only a star on it below, or doc generation fails
/**
 *
 *
 * Placeholder for custom user javascript
 * mainly to be overridden in profile/static/custom/custom.js
 * This will always be an empty file in IPython
 *
 * User could add any javascript in the `profile/static/custom/custom.js` file.
 * It will be executed by the ipython notebook at load time.
 *
 * Same thing with `profile/static/custom/custom.css` to inject custom css into the notebook.
 *
 *
 * The object available at load time depend on the version of IPython in use.
 * there is no guaranties of API stability.
 *
 * The example below explain the principle, and might not be valid.
 *
 * Instances are created after the loading of this file and might need to be accessed using events:
 *     define([
 *        'base/js/namespace',
 *        'base/js/events'
 *     ], function(IPython, events) {
 *         events.on("app_initialized.NotebookApp", function () {
 *             IPython.keyboard_manager....
 *         });
 *     });
 *
 * __Example 1:__
 *
 * Create a custom button in toolbar that execute `%qtconsole` in kernel
 * and hence open a qtconsole attached to the same kernel as the current notebook
 *
 *    define([
 *        'base/js/namespace',
 *        'base/js/events'
 *    ], function(IPython, events) {
 *        events.on('app_initialized.NotebookApp', function(){
 *            IPython.toolbar.add_buttons_group([
 *                {
 *                    'label'   : 'run qtconsole',
 *                    'icon'    : 'icon-terminal', // select your icon from http://fortawesome.github.io/Font-Awesome/icons
 *                    'callback': function () {
 *                        IPython.notebook.kernel.execute('%qtconsole')
 *                    }
 *                }
 *                // add more button here if needed.
 *                ]);
 *        });
 *    });
 *
 * __Example 2:__
 *
 * At the completion of the dashboard loading, load an unofficial javascript extension
 * that is installed in profile/static/custom/
 *
 *    define([
 *        'base/js/events'
 *    ], function(events) {
 *        events.on('app_initialized.DashboardApp', function(){
 *            require(['custom/unofficial_extension.js'])
 *        });
 *    });
 *
 * __Example 3:__
 *
 *  Use `jQuery.getScript(url [, success(script, textStatus, jqXHR)] );`
 *  to load custom script into the notebook.
 *
 *    // to load the metadata ui extension example.
 *    $.getScript('/static/notebook/js/celltoolbarpresets/example.js');
 *    // or
 *    // to load the metadata ui extension to control slideshow mode / reveal js for nbconvert
 *    $.getScript('/static/notebook/js/celltoolbarpresets/slideshow.js');
 *
 *
 * @module IPython
 * @namespace IPython
 * @class customjs
 * @static
 */


var esriCDN = location.protocol + "//js.arcgis.com/3.17amd/"
var proxyUrl = "/proxy/proxy.jsp";

// Jupyter specific, but should work for local, tmpnb, NSF, and other scenarios
//    the way Jupyter Notebooks work; get last occurrence of notebooks in URL.
var strnb = location.href.lastIndexOf("/notebooks");
var nbextensionPath = "";
if (strnb < 0) {
    nbextensionPath = "/nbextensions/arcgis";
}
else {
    nbextensionPath = location.href.substring(0, strnb) + "/nbextensions/arcgis";
}

require.config({
    // Define path mappings for modules
    paths: {
        // [1] Modules hosted on Esri CDN.
        "dojo": esriCDN + "dojo",
        "dojox": esriCDN + "dojox",
        "dijit": esriCDN + "dijit",
        "esri": esriCDN + "esri",
        "dgrid": esriCDN + "dgrid",
        "xstyle": esriCDN + "xstyle",
        "put-selector": esriCDN + "put-selector",
        "moment": esriCDN + "moment",

        // [2] Modules hosted locally.
        // "location" is specified as path relative to web server root.
        // "requirejs":  "/research/js/requirejs", - already loaded
        //"text":       "/static/custom/requirejs/text"
        "mytext": nbextensionPath + "/requirejs/text"
    },

    urlArgs: "client=gsrs",

    // Use RequireJS text plugin instead of dojo/text plugin.
    // Any module that requires dojo/text plugin will use RequireJS
    // text plugin instead.
    // http://requirejs.org/docs/api.html#config
    map: {
        "*": {
            "dojo/text": "mytext"
        }
    },
    config: {
        mytext: {

            useXhr: function (url) {
                // Allow cross domain XHR requests:
                // We will route them through a proxy in onXhr below.
                // https://github.com/requirejs/text/blob/master/text.js#L129

                return true;
            },

            // In IE 9, text plugin fails even before onXhr is called:
            // It fails right when calling xhr.open:
            // https://github.com/requirejs/text/blob/master/text.js#L267
            // - This is different from other browsers which appear to fail
            // much later, allowing us a chance to append proxy below.
            // -- Probably because IE 9 does not support CORS as opposed to
            // other modern browsers that have CORS support.

            // ESRI modification: let's take over xhr.open below
            openXhr: false,

            onXhr: function (xhr, url) {
                // Route cross domain XHR through a proxy if required
                var hasCors = (
                  typeof XMLHttpRequest !== "undefined"
                  && ("withCredentials" in (new XMLHttpRequest()))
                );

                xhr.open(
                  "GET",
                  hasCors ? url : (proxyUrl + "?" + url),
                  true
                );
            }
        }
    }
});

//require([
//"widgets/js/widget",
//"widgets/js/manager",
//"nbextensions/widgets/widgets/js/widget",
//"nbextensions/widgets/widgets/js/manager",
require.undef('mapview');

define('mapview', [
     "jupyter-js-widgets",
     "esri/basemaps",
     "esri/map",
     "esri/config",
     "esri/Color",
     "esri/dijit/LayerSwipe",
     "esri/graphic",
     "esri/TimeExtent",
     "esri/ServerInfo",
     "esri/IdentityManager",
     "esri/geometry/Extent",
     "esri/SpatialReference",
     "esri/InfoTemplate",
     "esri/toolbars/draw",
     "esri/layers/KMLLayer",
     "esri/layers/VectorTileLayer",
     "esri/layers/RasterFunction",
     "esri/layers/MosaicRule",
     "esri/layers/ArcGISImageServiceLayer",
     "esri/layers/ArcGISDynamicMapServiceLayer",
     "esri/layers/ArcGISTiledMapServiceLayer", 
     "esri/layers/ImageServiceParameters",
     "esri/geometry/Polyline",
     "esri/geometry/Polygon",
     "esri/geometry/Point",
     "esri/geometry/Multipoint",
     "esri/layers/FeatureLayer",
     "esri/renderers/smartMapping",
	 "esri/renderers/jsonUtils",
     "esri/symbols/SimpleFillSymbol",
     "esri/symbols/SimpleLineSymbol",
     "esri/renderers/HeatmapRenderer",
     "esri/symbols/PictureMarkerSymbol",
     "esri/geometry/webMercatorUtils",
     "esri/arcgis/utils",
     "esri/dijit/PopupTemplate",
     "dojo/_base/array",
     "dojo/_base/lang",
     "dojo/domReady!"
], function (
     widgets,
     esriBasemaps,
     Map,
     esriConfig,
     Color,
     LayerSwipe,
     Graphic,
     TimeExtent,
     ServerInfo,
     IdentityManager,
     Extent,
     SpatialReference,
     InfoTemplate,
     Draw,
     KMLLayer,
     VectorTileLayer,
     RasterFunction,
     MosaicRule,
     ArcGISImageServiceLayer,
     ArcGISDynamicMapServiceLayer,
     ArcGISTiledMapServiceLayer,
     ImageServiceParameters,
     Polyline,
     Polygon,
     Point,
     Multipoint,
     FeatureLayer,
     smartMapping,
	 jsonUtils,
     SimpleFillSymbol,
     SimpleLineSymbol,
     HeatmapRenderer,
     PictureMarkerSymbol,
     webMercatorUtils,
     arcgisUtils,
     PopupTemplate,
     array,
     lang) {
    //var map, toolbar;
    // var layerList = new Array();
    var MapView = widgets.DOMWidgetView.extend({

        // var layerList = new Array(),

        // Render the view.
        render: function () {
            $('head').append($('<link rel="stylesheet" type="text/css" />').attr('href', nbextensionPath + '/custom.css'));
            $('body').addClass('claro');
            var that = this;

            var token_info = this.model.get('_token_info')
            if ((token_info) && (token_info.trim() != '')) {

                var token = JSON.parse(token_info);

                esriConfig.defaults.io.corsEnabledServers.push(token.server);

                var serverInfo = new ServerInfo();
                serverInfo.server = token.server;
                serverInfo.tokenServiceUrl = token.tokenurl;


                IdentityManager.registerServers([serverInfo]);


                var userId = token.username;
                var password = token.password;


                // https://geonet.esri.com/thread/119062
                IdentityManager.generateToken(serverInfo, {
                    username: userId,
                    password: password
                }).then(function (response) {
                    IdentityManager.registerToken({
                        server: serverInfo.server,
                        userId: userId,
                        token: response.token,
                        expires: response.expires,
                        ssl: response.ssl
                    });
                }).then(function (response) {

                    load_map(that);

                });


            } else {

                load_map(that);

            }

            function load_map(that) {
                IPython.keyboard_manager.disable(); // loading map can cause modal dialog for secure resources which is
                // incompatible with keyboard manager (eats shortcut keys)

                // This was introduced to handle situations where basemap is changed to a custom
                //   basemap before the map is actually loaded/drawn.  It seemed that in this situation,
                //   the model event isn't being trigged properly here in the JS code.
                //   If _gallerybasemaps has already been initialized, push items onto esriBasemaps object.
                var bms = that.model.get('_gallerybasemaps');
                if (bms.length > 0) {
                    var bmdefs = that.model.get('_gbasemaps_def');
                    for (var i=0;i < bms.length;i++) {
                        esriBasemaps[bms[i]] = {
                            baseMapLayers: bmdefs[i],
                            title: bms[i]
                        };
                    }
                }

                var id = that.model.get('id');
                if ((id) && (id.trim() != '')) {
                    var arcgis_url = that.model.get('_arcgis_url');
                    if ((arcgis_url) && (arcgis_url.trim() != '')) {
                        arcgisUtils.arcgisUrl = arcgis_url;
                    }
                    arcgisUtils.createMap(id, that.el).then(function (response) {
                        IPython.keyboard_manager.enable();
                        that.map = response.map;
                        that.map.disableKeyboardNavigation(); // interferes with the Notebook keyboard shortcuts
                        // create the draw toolbar, it activates only when mode=draw_*
                        that.toolbar = new Draw(that.map);
                        // hook up events
                        that.toolbar.on("draw-end", onDrawEnd);
                        //map.on("extent-change", onExtentChange);
                        that.map.on("click", onMouseClick);

                        that.mode_changed();
                        that.basemap_changed();
                        that.layer_changed();
                        that.start_time_changed();
                        that.end_time_changed();
                    });
                } else {

                    //that.$el.append("<div id='"+that.model.get('_swipe_div')+"'>");

                    if (that.model.get('_extent').indexOf("{") > -1) {
                        var ext = JSON.parse(that.model.get('_extent'));

                        var newExtent = new Extent();
                        newExtent.xmin = ext.xmin;
                        newExtent.xmax = ext.xmax;
                        newExtent.ymin = ext.ymin;
                        newExtent.ymax = ext.ymax;

                        newExtent.spatialReference = new SpatialReference({ wkid: 4326 });

                        that.map = new Map(that.el, {
                            basemap: that.model.get('_basemap'),
                            extent: newExtent
                        });


                    } else {

                        that.map = new Map(that.el, {
                            basemap: that.model.get('_basemap'),
                            center: that.model.get('center').reverse(),
                            zoom: that.model.get('zoom')
                        });
                    }

                    that.map.on("load", on_load);
                }
            }

            function on_load(evt) {
                console.log('***on_load');
                IPython.keyboard_manager.enable();
                evt.map.disableKeyboardNavigation(); // interferes with the Notebook keyboard shortcuts
                // Disable navigation by default, so scrolling the page doesn't scroll the map
                evt.map.disableMapNavigation();
                // When the user tries to pan the map, allow this
                evt.map.on('mouse-drag-start', function(){
                   evt.map.enableMapNavigation();
                });

                // Restore the no-scroll behaviour when the mouse leaves the map
                evt.map.on('mouse-out', function(){
                   evt.map.disableMapNavigation();
                });
                // create the draw toolbar, it activates only when mode=draw_*
                that.toolbar = new Draw(evt.map);
                // hook up events
                that.toolbar.on("draw-end", onDrawEnd);
                evt.map.on("extent-change", onExtentChange);
                evt.map.on("click", onMouseClick);


                that.mode_changed();
                that.basemap_changed();
                that.layer_changed();
                that.start_time_changed();
                that.end_time_changed();

                // amani - sync the initial extent
                // that.model.set('_jsextent', JSON.stringify(that.map.extent));
                // that.model.touch();
            }


            // JS map events

            function onExtentChange(evt){
                //console.log('#####EXTENTCHANGE')
              var extent = evt.extent,
                  zoomed = evt.levelChange;
                that.extent_change(extent, zoomed);
            }

            function onDrawEnd(evtObj) {
                var geometry = evtObj.geometry;

                var graphic = that.map.graphics.add(new Graphic(geometry, new SimpleFillSymbol()));

                that.toolbar.deactivate();
                that.draw_end(geometry);

                //amani- Add all interactive graphics to web map at the end. Save them all to a list of dicts
                var syncGraphic = {'geometry':geometry, 'symbol':graphic.symbol};

                var _current_js_dg_list = that.model.get('_js_interactive_drawn_graphic');
                if (_current_js_dg_list == ""){
                    _current_js_dg_list2 = [];
                }
                else{
                    _current_js_dg_list2 = JSON.parse(_current_js_dg_list);
                }
                _current_js_dg_list2.push(syncGraphic);
                that.model.set('_js_interactive_drawn_graphic', JSON.stringify(_current_js_dg_list2));
                that.touch();
            }

            function onMouseClick(event) {
                that.map.enableMapNavigation();
                //console.log("User clicked at " + event.screenPoint.x + ", " + event.screenPoint.y +
                //            " on the screen. The map coordinate at this point is " +
                //            event.mapPoint.x + ", " + event.mapPoint.y
                //);
                //console.log("MapCpoint:"+JSON.stringify(event.mapPoint));
                //var normalizedVal = webMercatorUtils.xyToLngLat(event.mapPoint.x, event.mapPoint.y);
                //console.log(normalizedVal);
                that.mouse_clicked(event.mapPoint);//normalizedVal[0], normalizedVal[1]);
            }


            // Model change events
            this.model.on('change:zoom', this.zoom_changed, this);
            this.model.on('change:mode', this.mode_changed, this);
            this.model.on('change:_extent', this.extent_changed, this);
            this.model.on('change:center', this.center_changed, this);
            this.model.on('change:_basemap', this.basemap_changed, this);
            this.model.on('change:_gallerybasemaps', this.gallerybasemaps_changed, this);
            this.model.on('change:_addlayer', this.layer_changed, this);
            this.model.on('change:start_time', this.start_time_changed, this);
            this.model.on('change:end_time', this.end_time_changed, this);
            this.model.on('change:_layerId_to_remove', this.remove_layer, this);

        },
        /*
        on_load: function(evt) {
            console.log('***on_load');
            evt.map.disableKeyboardNavigation(); // interferes with the Notebook keyboard shortcuts

            // create the draw toolbar, it activates only when mode=draw_*
            this.toolbar = new Draw(evt.map);

            // hook up events
            this.toolbar.on("draw-end", this.onDrawEnd);
            //map.on("extent-change", onExtentChange);
            //evt.map.target.on("click", this.onMouseClick);
            evt.map.on("click", this.onMouseClick);
        },

        onDrawEnd : function(evtObj){
            var geometry = evtObj.geometry;

            var graphic = this.map.graphics.add(new Graphic(geometry, new SimpleFillSymbol()));

            this.toolbar.deactivate();
            //this.draw_end(geometry);
                        this.model.set('mode','navigate');
            this.touch();
            this.send({event: 'draw-end', message: geometry});
        },

        onMouseClick: function(event) {
            console.log("User clicked at " +  event.screenPoint.x + ", " + event.screenPoint.y +
                        " on the screen. The map coordinate at this point is " +
                        event.mapPoint.x + ", " + event.mapPoint.y

            );
            //console.log("MapCpoint:"+JSON.stringify(event.mapPoint));
            //var normalizedVal = webMercatorUtils.xyToLngLat(event.mapPoint.x, event.mapPoint.y);
            //console.log(normalizedVal);

            //this.mouse_clicked(event.mapPoint);//normalizedVal[0], normalizedVal[1]);
            this.send({event: 'mouseclick', message: event.mapPoint});//'{ \'x\':' + mapx + ', \'y\':' + mapy + '}'});
        },
        */

        // Incoming Events from the model
        zoom_changed: function () {
            this.map.setZoom(this.model.get('zoom'));
        },

        mode_changed: function () {

            if (this.model.get('mode') == "navigate") {
                console.log("***mode = navigate")
                this.toolbar.deactivate();
            } else if (this.model.get('mode') == "###clear_graphics") {
                this.map.graphics.clear();
                this.model.set('_js_interactive_drawn_graphic', "");
            } else if (this.model.get('mode') == "###remove_layers") {
                this.map.removeAllLayers();
            } else if (this.model.get('mode').indexOf("{") > -1) {

                console.log("***mode=draw_geometry***");
                var drawgraphic = JSON.parse(this.model.get('mode'));
                var gfx = new Graphic(drawgraphic);

                if (gfx.symbol == null) {
                    if (gfx.geometry.type === 'polyline') {
                        console.log("GEOM TYPE POLYLINE");

                        gfx.symbol = new SimpleLineSymbol(SimpleLineSymbol.STYLE_SOLID, new dojo.Color([255, 0, 0, 0.5]), 3);
                    } else if (gfx.geometry.type === 'polygon') {
                        console.log("GEOM TYPE POLYGON***");

                        var polySymbol = new SimpleFillSymbol();
                        polySymbol.setOutline(new SimpleLineSymbol(SimpleLineSymbol.STYLE_SOLID, new dojo.Color([0, 0, 0, 0.5]), 1));
                        polySymbol.setColor(new Color([255, 127, 0, 0.7]));

                        gfx.symbol = polySymbol;
                    } else if (gfx.geometry.type === 'point') {
                        console.log("GEOM TYPE POINT");

                        gfx.symbol = new PictureMarkerSymbol(nbextensionPath + '/icons/pink.png', 32, 32);
                    } else if (gfx.geometry.type === 'multipoint') {
                        console.log("GEOM TYPE MULTIPOINT");

                        gfx.symbol = new PictureMarkerSymbol(nbextensionPath + '/icons/pink.png', 32, 32);
                    }
                }
                this.map.graphics.add(gfx);

            } else {
                var shape = this.model.get('mode');
                console.log("***mode=draw_" + shape);
                this.toolbar.activate(shape);
            }
        },
        createTemplate: function (layer) {
            var fieldInfos = array.map(layer.fields, function (field) {
                return {
                    "fieldName": field.name,
                    "label": field.alias,
                    "visible": true
                }
            });

            var template = new PopupTemplate({
                title: layer.name,
                fieldInfos: fieldInfos
            });
            return template;
        },

        layer_changed: function () {
            var that = this;
            var curbasemap = that.map.getBasemap();
            var bmgallery = this.model.get('_gallerybasemaps');
            // If using a custom basemap, smart mapping doesn't
            // support that so default to JSAPI topo instead.
            if (bmgallery.indexOf(curbasemap) >= 0) {
                curbasemap = 'topo';
            }
            if (this.model.get('_addlayer').indexOf("{") > -1) {

                console.log("***###***addlayer");

                var newlayer = JSON.parse(this.model.get('_addlayer'));
                if ((window.location.protocol === 'https:') && (newlayer.url.startsWith('http:'))) {
                    newlayer.url = newlayer.url.replace("http://","https://")
                }
                console.log(newlayer);
                if (newlayer.type == "KMLLayer") {
                    console.log("KMLLayer " + newlayer.url);
                    var kml = new KMLLayer(newlayer.url);
                    this.map.addLayer(kml);
                    kml.on("load", function () {
                        domStyle.set("loading", "display", "none");
                    });
                }
                else if (newlayer.type == "ArcGISTiledMapServiceLayer") {
                    var tl = new ArcGISTiledMapServiceLayer(newlayer.url);
                    this.map.addLayer(tl);
                }
                else if (newlayer.type == "ArcGISDynamicMapServiceLayer") {
                    var dmsl = new ArcGISDynamicMapServiceLayer(newlayer.url);
                    this.map.addLayer(dmsl);
                }
                else if (newlayer.type == "VectorTileLayer") {
                    var vtl = new VectorTileLayer(newlayer.url);
                    this.map.addLayer(vtl);
                }
                else if ((newlayer.type == "FeatureLayer") || (newlayer.type == "Feature Layer")) {
                    console.log("Adding FeatureLayer " + newlayer.url);

                    var layer = new FeatureLayer(newlayer.url, {
                        "outFields": ["*"]
                    });

                    if (newlayer.options != null) {
                        var lyr_options = JSON.parse(newlayer.options);
                        if (lyr_options.opacity != null) {
                            console.log('***opacity:' + lyr_options.opacity);
                            layer.setOpacity(lyr_options.opacity);
                        }

                        if (lyr_options.definition_expression != null) {
                            console.log("***DEF EXP");
                            console.log(lyr_options.definition_expression);
                            layer.setDefinitionExpression(lyr_options.definition_expression);
                        }

                        if (lyr_options.renderer == "HeatmapRenderer") {
                            var heatmapRenderer = new HeatmapRenderer();
                            layer.setRenderer(heatmapRenderer);
                        }

                        console.log("ClassedSizeRend0:" + lyr_options.renderer);
                        console.log("ClassedSizeRend:" + lyr_options.field_name);

                        if (lyr_options.renderer == "HeatmapRenderer") {
                            var heatmapRenderer = new HeatmapRenderer();
                            var hmoptions = {};

                            if (lyr_options.field_name != null) {
                                hmoptions = {
                                    field: lyr_options.field_name,
                                };
                            }
                            var heatmapRenderer = new HeatmapRenderer(hmoptions);

                            layer.setRenderer(heatmapRenderer);

                            //amani - this code is now redundant
                            // hm_renderer_string = JSON.stringify({"type":"heatmap",
                            //                                     "colorStops":heatmapRenderer.colorStops,
                            //                                     "blurRadius":heatmapRenderer.blurRadius,
                            //                                     "field":heatmapRenderer.field,
                            //                                     "maxPixelIntensity":heatmapRenderer.maxPixelIntensity,
                            //                                     "minPixelIntensity":heatmapRenderer.minPixelIntensity})
                            // this.model.set('_js_renderer', hm_renderer_string);
                            // this.touch();
                        }

                        else if (lyr_options.renderer == "ClassedSizeRenderer") {
                            console.log("ClassedSizeRenderer...");
                            setTimeout(function () { createClassedSizeRenderer(lyr_options); }, 500);
                            /*layer.on("load", function () {
                                console.log("AAA");
                                 createClassedSizeRenderer(lyr_options.field_name);
                             });*/
                        }

                        else if (lyr_options.renderer == "ClassedColorRenderer") {
                            setTimeout(function () { createClassedColorRenderer(lyr_options); }, 500);
                            /*layer.on("load", function () {
                                console.log("BBB");
                                 createClassedColorRenderer(lyr_options.field_name);
                             });
                             */
                        }
						else{
							var renderer = jsonUtils.fromJson(lyr_options.renderer); 
							layer.setRenderer(renderer);
						}

                        function createClassedColorRenderer(lyr_options) {
                            //smart mapping functionality begins
                            var default_properties = {
                                layer: layer,
                                field: lyr_options.field_name,
                                basemap: curbasemap,
                                classificationMethod: "quantile"
                            };

                            var renderer_properties = Object.assign(default_properties, lyr_options);

                            console.log(renderer_properties);

                            smartMapping.createClassedColorRenderer(renderer_properties).then(function (response) {
                                layer.setRenderer(response.renderer);

                                layer.redraw();
                                console.log(response.renderer);
                                //createLegend(map, layer, field);
                            });
                        }


                        function createClassedSizeRenderer(lyr_options) {
                            console.log("ClassedSizeRend2");
                            //smart mapping functionality begins
                            var default_properties = {
                                layer: layer,
                                field: lyr_options.field_name,
                                basemap: curbasemap,
                                classificationMethod: "quantile"
                            };

                            var renderer_properties = Object.assign(default_properties, lyr_options);

                            console.log(renderer_properties);

                            smartMapping.createClassedSizeRenderer(renderer_properties).then(function (response) {
                                layer.setRenderer(response.renderer);
                                layer.redraw();
                                //createLegend(map, layer, field);
                            });
                        }
                    }

                    if (newlayer.opacity != null) {
                        layer.setOpacity(newlayer.opacity);
                    }

                    if (newlayer.definition_expression != null) {
                        console.log("***DEF EXP");
                        console.log(newlayer.definition_expression);
                        layer.setDefinitionExpression(newlayer.definition_expression);
                    }

                    if (newlayer.renderer == "HeatmapRenderer") {
                        var heatmapRenderer = new HeatmapRenderer();
                        layer.setRenderer(heatmapRenderer);
                    }

                    bRend = false;
                    bSRend = false;

                    this.map.addLayer(layer);

                    if (newlayer.renderer == "ClassedColorRenderer") {
                        bRend = true;
                        //layer.on("load", function () {
                        //  createRenderer(newlayer.field_name);
                        //});
                    }

                    if (newlayer.renderer == "ClassedSizeRenderer") {
                        bSRend = true;
                        //layer.on("load", function () {
                        //  createSizeRenderer(newlayer.field_name);
                        //});
                    }

                    //amani - sync the layer info after layer loads - smartMapping is asyc
                    layer.on("load", lang.hitch(this, function(){

                        //add the current layer to layer list and sync with Python side.
                        //cannot stringify layers. So create a layer dict
                        var _layerDict = {'id':layer.id,
                                            'normalization':layer.normalization,
                                            'refreshInterval':layer.refreshInterval,
                                            'url':layer.url};
                        if (layer.renderer){
                            _layerDict['renderer'] = layer.renderer.toJson();
                            _layerDict['rendererType']=layer.renderer.declaredClass;
                        }

                        // Simply maintain the list of layers as a list in the synced property. Read it and extend this list
                        var _current_list = this.model.get('_js_layer_list');
                        if (_current_list == ""){
                            var _current_list2 = [];
                        }
                        else{
                            var _current_list2 = JSON.parse(_current_list);
                        }

                        _current_list2.push(_layerDict);
                        this.model.set('_js_layer_list', JSON.stringify(_current_list2));
                        this.touch();
                    }));

                    //amani - sync the layer info when renderer is changed due to smart mapping
                    layer.on("renderer-change", lang.hitch(this, function(){
                        if (typeof(lyr_options)!=typeof(undefined)) {
                            if ('renderer' in lyr_options) {
                                if ((lyr_options.renderer == 'ClassedColorRenderer') ||
                                    (lyr_options.renderer == "ClassedSizeRenderer")) {

                                    var _current_list = this.model.get('_js_layer_list');
                                    if (_current_list != "") {
                                        console.log("Update renderer of latest layer");
                                        var _current_list2 = JSON.parse(_current_list);
                                        _current_list2[_current_list2.length - 1]['renderer'] = layer.renderer.toJson();
                                        _current_list2[_current_list2.length - 1]['rendererType'] = layer.renderer.declaredClass;

                                        this.model.set('_js_layer_list', JSON.stringify(_current_list2));
                                        this.touch();
                                        console.log("CCR, CSR renderer updated");
                                    }
                                }
                            }
                            else {
                                console.log("Fired due to some other event");
                            }
                        }else{console.log("Not sure which fired renderer-change");}

                        // //add the current layer to layer list and sync with Python side.
                        // //cannot stringify layers. So create a layer dict
                        // var _layerDict = {'id':layer.id,
                        //                     'normalization':layer.normalization,
                        //                     'refreshInterval':layer.refreshInterval,
                        //                     'url':layer.url};
                        // if (layer.renderer){
                        //     _layerDict['renderer'] = layer.renderer.toJson();
                        //     _layerDict['rendererType']=layer.renderer.declaredClass;
                        // }
                        //
                        // // Simply maintain the list of layers as a list in the synced property. Read it and extend this list
                        // var _current_list = this.model.get('_js_layer_list');
                        // if (_current_list == ""){
                        //     var _current_list2 = [];
                        // }
                        // else{
                        //     var _current_list2 = JSON.parse(_current_list);
                        // }
                        //
                        // _current_list2.push(_layerDict);
                        // this.model.set('_js_layer_list', JSON.stringify(_current_list2));
                        // this.touch();
                    }));

                    layer.on("load", lang.hitch(this, function () {
                        layer.setInfoTemplate(this.createTemplate(layer));
                        if (bRend) {
                            createRenderer(newlayer.field_name);
                        }
                        if (bSRend) {
                            createSizeRenderer(newlayer.field_name);
                        }
                    }));
                    function createRenderer(field) {
                        //smart mapping functionality begins
                        smartMapping.createClassedColorRenderer({
                            layer: layer,
                            field: field,
                            basemap: curbasemap,
                            classificationMethod: "quantile"
                        }).then(function (response) {
                            layer.setRenderer(response.renderer);
                            layer.redraw();
                            //createLegend(map, layer, field);
                        });
                    }

                    function createSizeRenderer(field) {
                        console.log("ClassedSizeRend2");
                        //smart mapping functionality begins
                        smartMapping.createClassedSizeRenderer({
                            layer: layer,
                            field: field,
                            basemap: curbasemap,
                            classificationMethod: "quantile"
                        }).then(function (response) {
                            layer.setRenderer(response.renderer);
                            layer.redraw();
                            //createLegend(map, layer, field);
                        });
                    }
                }
                else if (newlayer.type == "ImageryLayer") {

                    console.log("ArcGISImageServiceLayer " + newlayer.url);
                    var options = {};
                    var swipelayer = false;
                    var opacity = -1;
                    if (newlayer.options != null) {
                        var imgsvc_options = JSON.parse(newlayer.options);

                        if (imgsvc_options.opacity) {
                            opacity = imgsvc_options.opacity;
                        }

                        if (imgsvc_options.swipelayer) {
                            swipelayer = imgsvc_options.swipelayer;
                        }
                        if (imgsvc_options.imageServiceParameters) {
                            var params = new ImageServiceParameters();

                            if (imgsvc_options.imageServiceParameters.renderingRule) {
                                var rasterFunction = new RasterFunction(imgsvc_options.imageServiceParameters.renderingRule);
                                params.renderingRule = rasterFunction;
                            }
                            if (imgsvc_options.imageServiceParameters.mosaicRule) {
                                var mosaicRule = new MosaicRule(imgsvc_options.imageServiceParameters.mosaicRule);
                                params.mosaicRule = mosaicRule;
                            }
                            if (imgsvc_options.imageServiceParameters.bandIds) {
                                params.bandIds = imgsvc_options.imageServiceParameters.bandIds;
                            }

                            options.imageServiceParameters = params;
                        }
                    }
                    var layer = new ArcGISImageServiceLayer(newlayer.url, options);

                    if (opacity != -1) {
                        console.log("******Setting opacity ");
                        layer.setOpacity(opacity);
                    }

                    this.map.addLayer(layer);

                    if (swipelayer) {
                        console.log("Swipe Layer");
                        var swipeWidget = new LayerSwipe({
                            type: "vertical",  //Try switching to "scope" or "horizontal"
                            map: map,
                            layers: [layer]
                        }, this.model.get('_swipe_div'));
                        swipeWidget.startup();
                    }

                    //amani - sync the layer info after layer loads - Imagery Layers
                    layer.on("load", lang.hitch(this, function(){

                        //add the current layer to layer list and sync with Python side.
                        //cannot stringify layers. So create a layer dict
                        var _layerDict = {'id':layer.id,
                                            'bandIds':layer.bandIds,
                                            'mosaicRule':layer.mosaicRule,
                                            'url':layer.url,
                                            'renderingRule':layer.renderingRule};
                        if (layer.renderer){
                            _layerDict['renderer'] = layer.renderer;
                            _layerDict['rendererType']=layer.renderer.declaredClass;
                        }

                        // Simply maintain the list of layers as a list in the synced property. Read it and extend this list
                        var _current_list = this.model.get('_js_layer_list');
                        if (_current_list == ""){
                            var _current_list2 = [];
                        }
                        else{
                            var _current_list2 = JSON.parse(_current_list);
                        }

                        _current_list2.push(_layerDict);
                        this.model.set('_js_layer_list', JSON.stringify(_current_list2));
                        this.touch();
                    }));
                }
                else { // Feature Collection

                    // console.log(newlayer);

                    var options = { mode: FeatureLayer.MODE_SNAPSHOT };
                    var newlyr_options = {};
                    if (newlayer.options != null) {
                        newlyr_options = Object.assign(options, JSON.parse(newlayer.options));
                    }

                    console.log("***Feature Collection layer###***");
                    console.log("inspecting if feature collection contains layers");
                    if ('layers' in newlayer){
                        newlayer = newlayer.layers[0];
                    }
                    var layer = new FeatureLayer(newlayer, newlyr_options);
                    //code added by MM to add pop up to a FC

                    layer.setInfoTemplate(this.createTemplate(layer));

                    //end changes from mm

                    if (newlayer.options != null) {
                        var lyr_options = JSON.parse(newlayer.options);


                        console.log("ClassedSizeRend0:" + lyr_options.renderer);
                        console.log("ClassedSizeRend:" + lyr_options.field_name);

                        if (lyr_options.renderer == "HeatmapRenderer") {
                            var heatmapRenderer = new HeatmapRenderer();
                            var hmoptions = {};

                            if (lyr_options.field_name != null) {
                                hmoptions = {
                                    field: lyr_options.field_name,
                                };
                            }
                            var heatmapRenderer = new HeatmapRenderer(hmoptions);

                            layer.setRenderer(heatmapRenderer);
                        }


                        if (lyr_options.renderer == "ClassedSizeRenderer") {
                            console.log("ClassedSizeRenderer...");
                            setTimeout(function () { createClassedSizeRenderer(lyr_options.field_name); }, 500);
                            /*layer.on("load", function () {
                                console.log("AAA");
                                 createClassedSizeRenderer(lyr_options.field_name);
                             });*/
                        }

                        if (lyr_options.renderer == "ClassedColorRenderer") {
                            setTimeout(function () { createClassedColorRenderer(lyr_options.field_name); }, 500);
                            /*layer.on("load", function () {
                                console.log("BBB");
                                 createClassedColorRenderer(lyr_options.field_name);
                             });
                             */
                        }

                        function createClassedColorRenderer(field) {
                            //smart mapping functionality begins
                            smartMapping.createClassedColorRenderer({
                                layer: layer,
                                field: field,
                                basemap: curbasemap,
                                classificationMethod: "quantile"
                            }).then(function (response) {
                                layer.setRenderer(response.renderer);
                                layer.redraw();
                                //createLegend(map, layer, field);
                            });
                        }


                        function createClassedSizeRenderer(field) {
                            console.log("ClassedSizeRend2");
                            //smart mapping functionality begins
                            smartMapping.createClassedSizeRenderer({
                                layer: layer,
                                field: field,
                                basemap: curbasemap,
                                classificationMethod: "quantile"
                            }).then(function (response) {
                                layer.setRenderer(response.renderer);
                                layer.redraw();
                                //createLegend(map, layer, field);
                            });
                        }
                    }


                    this.map.addLayer(layer);
                    console.log("added the fc layer");
                    //amani - sync the layer info after layer loads - smartMapping is asyc
                    var _layerDict = {'id':layer.id,
                                            'normalization':layer.normalization,
                                            'refreshInterval':layer.refreshInterval,
                                            'url':layer.url};
                    if (layer.renderer){
                        _layerDict['renderer'] = layer.renderer;
                        _layerDict['rendererType']=layer.renderer.declaredClass;
                    }

                    // Simply maintain the list of layers as a list in the synced property. Read it and extend this list
                    var _current_list = this.model.get('_js_layer_list');
                    if (_current_list == ""){
                        var _current_list2 = [];
                    }
                    else{
                        var _current_list2 = JSON.parse(_current_list);
                    }

                    _current_list2.push(_layerDict);
                    this.model.set('_js_layer_list', JSON.stringify(_current_list2));
                    this.touch();
                }

            }
        },

        remove_layer: function(){
            var that = this;
            var layerIdToRemove = this.model.get('_layerId_to_remove');
            var layerToRemove = this.map.getLayer(layerIdToRemove);
            console.log("*** removing individual layer ***");
            this.map.removeLayer(layerToRemove);

            //must update the _js_layer_list trait - happens in Python side.
        },

        center_changed: function () {
            console.log("changing center");
            this.map.centerAt(this.model.get('center').reverse());
        },

        extent_changed: function () {
            console.log("changing extent@@@@@");

            var ext = JSON.parse(this.model.get('_extent'));

            var newExtent = new Extent();
            newExtent.xmin = ext.xmin;
            newExtent.xmax = ext.xmax;
            newExtent.ymin = ext.ymin;
            newExtent.ymax = ext.ymax;

            newExtent.spatialReference = new SpatialReference({ wkid: 4326 });

            this.map.setExtent(newExtent);
        },

        start_time_changed: function () {
            var start_time = this.model.get('start_time')
            if ((start_time) && (start_time.trim() != '')) {
                console.log("changing start_time");
                var timeExtent = new TimeExtent();
                timeExtent.startTime = new Date(this.model.get('start_time'));
                timeExtent.endTime = new Date(this.model.get('end_time'));
                this.map.setTimeExtent(timeExtent);
            }
        },

        end_time_changed: function () {
            var end_time = this.model.get('end_time')
            if ((end_time) && (end_time.trim() != '')) {
                console.log("changing end_time");
                var timeExtent = new TimeExtent();
                timeExtent.startTime = new Date(this.model.get('start_time'));
                timeExtent.endTime = new Date(this.model.get('end_time'));
                this.map.setTimeExtent(timeExtent);
            }
        },

        basemap_changed: function () {
            this.map.setBasemap(this.model.get('_basemap'));
            var basemapChangeHandle = this.map.on("basemap-change", lang.hitch(this, function(){
                basemapChangeHandle.remove();
                var returnList = [];
                for (var i=0; i<this.map.basemapLayerIds.length; i++)
                {
                    var current_basemap_layer = this.map.getLayer(this.map.basemapLayerIds[i]);
                    try{
                        var resource_info = JSON.parse(current_basemap_layer.resourceInfo);
                        var _title = resource_info.documentInfo.Title;
                    }
                    catch(err){
                        var _title = this.model.get('_basemap');
                    }

                    var _basemap_dict = {'url':current_basemap_layer.url,
                                        'title':_title};
                    returnList.push(_basemap_dict);
                }

                this.model.set('_js_basemap', JSON.stringify(returnList));
                this.touch();
            }))
            // var current_basemap_layer = this.map.getLayer(this.map.basemapLayerIds[0]);
            // console.log(current_basemap_layer);
            // var basemap_dict = {'url':current_basemap_layer.url}
            // this.model.set('_js_basemap', current_basemap_layer.url);
            // this.touch();

        },

	    gallerybasemaps_changed: function () {
            console.log("**Using Basemaps Gallery....");
            var bms = this.model.get('_gallerybasemaps');
            // If the gallery_basemaps is not empty, then we must be using a group
            if (bms.length > 0) {
                var bmdefs = this.model.get('_gbasemaps_def');
                for (var i=0;i < bms.length;i++) {
                    esriBasemaps[bms[i]] = {
                        baseMapLayers: bmdefs[i],
                        title: bms[i]
                    };
                }
            }
        },

        // Outgoing events to the model

        mouse_clicked: function (geometry) { //mapx, mapy) {
            this.send({ event: 'mouseclick', message: geometry });//'{ \'x\':' + mapx + ', \'y\':' + mapy + '}'});
        },

        draw_end: function (geometry) {
            this.model.set('mode', 'navigate');
            this.touch();
            this.send({ event: 'draw-end', message: geometry });
        },

        extent_change: function(extent, zoomed) {
            //console.log(JSON.stringify(extent));
            //console.log(zoomed);
            this.model.set('_jsextent', JSON.stringify(extent));
            this.touch();
        },


        events: {
            // Dictionary of events and their handlers.
            'click': '_handle_click',
        },

        _handle_click: function () {
            /**
             * Handles when the button is clicked.
             */
            this.send({ event: 'click', message: 'xyz' });
        },

    });

    return {
        MapView: MapView
    };

    //manager.WidgetManager.register_widget_view('MapView', MapView);
});

define(function () {
    function load_ipython_extension() {
        console.info('loaded map widget');
    }
    return {
        load_ipython_extension: load_ipython_extension
    }
});
/*
var infoTemplate = new InfoTemplate("${state_name}", "Population (2000):  ${pop2000:NumberFormat}");
var featureLayer = new FeatureLayer("http://sampleserver6.arcgisonline.com/arcgis/rest/services/USA/MapServer/3",{
  mode: FeatureLayer.MODE_ONDEMAND,
  outFields: ["*"],
  infoTemplate: infoTemplate
});

//map.addLayer(featureLayer);
//map.infoWindow.resize(155,75);
*/
