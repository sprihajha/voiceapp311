import uuid
import re
import tempfile
import os
import zipfile
import shutil
import logging
from functools import reduce
from urllib.parse import urlparse
import asyncio
import concurrent.futures
from arcgis import gis
from arcgis.features import FeatureLayerCollection
from arcgis.features import FeatureLayer
from arcgis.mapping import MapImageLayer
from arcgis.geometry import *

_TEXT_BASED_ITEM_TYPES = ['Web Map', 'Feature Service', 'Map Service', 'Operation View', 'Dashboard',
                          'Image Service', 'Feature Collection', 'Feature Collection Template',
                          'Web Mapping Application', 'Mobile Application', 'Symbol Set', 'Color Set',
                          'Document Link', 'Geocode Service', 'Geodata Service', 'Application',
                          'Geometry Service', 'Geoprocessing Service', 'Network Analysis Service',
                          'Workflow Manager Service']

#region Group and Item Definition Classes


class _DeepCloner():
    """
    A class to handle all of the deep cloning actions
    """
    def __init__(self, target, items=None, folder=None, item_extent=None,
                 use_org_basemap=False, copy_data=True, search_existing_items=True, item_mapping=None, group_mapping=None):
        self._graph = {}
        self.folder = folder
        self._logger = logging.getLogger()
        self.target = target
        self._items = items
        self._item_extent = item_extent
        self._use_org_basemap = use_org_basemap
        self._copy_data = copy_data
        self._search_existing_items=search_existing_items
        self._clone_mapping = {'Item IDs': {}, 'Group IDs': {}, 'Services': {}}
        if item_mapping is not None:
            self._clone_mapping['Item IDs'] = item_mapping
        if group_mapping is not None:
            self._clone_mapping['Group IDs'] = group_mapping
        self._temp_dir = tempfile.TemporaryDirectory()
        # parse the config and get values
        self._create_graph()
        self._cloned_items = []

    def _create_graph(self):
        """
        Build the graph of dependencies so we can traverse it to clone items based on if their
        child items have been cloned
        :return:
        """
        for item in self._items:
            user = self.target.users.me
            # Get the definitions associated with the item
            self._get_item_definitions(item)

            # Test if the user has the correct privileges to create the items requested
            if 'privileges' in user and user['privileges'] is not None:
                privileges = user.privileges
                for item_definition in self._graph.values():
                    if isinstance(item_definition, _ItemDefinition):
                        if 'portal:user:createItem' not in privileges:
                            raise Exception("To clone this item you must have permission to create new content in the target organization.")

                    if isinstance(item_definition, _GroupDefinition):
                        if 'portal:user:createGroup' not in privileges or 'portal:user:shareToGroup' not in privileges:
                            raise Exception("To clone this item you must have permission to create new groups and share content to groups in the target organization.")

                    if isinstance(item_definition, _FeatureServiceDefinition):
                        if 'portal:publisher:publishFeatures' not in privileges:
                            raise Exception("To clone this item you must have permission to publish hosted feature layers in the target organization.")

    def _get_leaf_nodes(self):
        """
        Gets all leaf nodes that are not resolved
        :return: <List> of leaf nodes
        """
        # get all of the leaf nodes
        # (in this sense a leaf node, is a node where all it's children are resolved or it has no children)
        leaf_nodes = []
        for node in [x for x in self._graph.values() if not x.resolved]:
            if all([child.resolved for child in node.children]) or not node.children:
                leaf_nodes.append(node)
        return leaf_nodes

    def _get_item_definitions(self, item):
        """" Get a list of definitions for the specified item.
        This method differs from get_item_definition in that it is run recursively to return the definitions of dependent items depending on the type.
        These definitions can be used to clone or download the items.
        Keyword arguments:
        item - The arcgis.GIS.Item to get the definition for
        item_definitions - A list of item and group definitions. When first called this should be an empty list that you hold a reference to and all definitions related to the item will be appended to the list.
        """

        item_definition = None
        source = item._gis

        # Check if the item definition has already been added to the collection of item definitions
        item_definition = next((i for i in self._graph.values() if i.info['id'] == item.id), None)
        if item_definition:
            return item_definition

        # if the item is a group find all the web maps that are shared with the group
        if isinstance(item, gis.Group):
            item_definition = self._get_group_definition(item)
            # add to graph
            self._graph[item_definition.info["id"]] = item_definition
            group_id = item['id']

            search_query = 'group:{0}'.format(group_id)
            group_items = source.content.search(search_query, max_items=1000, outside_org=True)
            for group_item in group_items:
                item_definition2 = self._get_item_definitions(group_item)
                item_definition.add_parent(item_definition2)
                if item_definition2 is not None:
                    item_definition2.sharing['groups'].append(group_id)

        # If the item is an application or dashboard find the web map or group that the application referencing
        elif item['type'] in ['Web Mapping Application', 'Operation View', 'Dashboard']:
            item_definition = self._get_item_definition(item)
            self._graph[item.id] = item_definition

            webmap_ids = []
            layer_ids = []
            app_json = item_definition.data
            if app_json is not None:
                if 'Story Map' in item['typeKeywords'] or 'Story Maps' in item['typeKeywords']:
                    webmap_ids = []

                elif item['type'] == "Operation View":
                    webmap_ids.extend(_OperationViewDefintion.get_webmap_ids(app_json))
                    layer_ids.extend(_OperationViewDefintion.get_layer_ids(app_json))

                elif item['type'] == "Dashboard":
                    webmap_ids.extend(_DashboardDefinition.get_webmap_ids(app_json))
                    layer_ids.extend(_DashboardDefinition.get_layer_ids(app_json))

                elif "Web AppBuilder" in item['typeKeywords']:  # Web AppBuilder
                    if 'map' in app_json:
                        if 'itemId' in app_json['map']:
                            webmap_ids.append(app_json['map']['itemId'])

                else:  # Configurable Application Template
                    if 'values' in app_json:
                        if 'group' in app_json['values']:
                            group_id = app_json['values']['group']
                            try:
                                group = source.groups.get(group_id)
                            except RuntimeError:
                                raise
                            item_definition.add_child(self._get_item_definitions(group))

                        if 'webmap' in app_json['values']:
                            if isinstance(app_json['values']['webmap'], list):
                                webmap_ids.extend(app_json['values']['webmap'])
                            else:
                                webmap_ids.append(app_json['values']['webmap'])

            for webmap_id in webmap_ids:
                try:
                    webmap = source.content.get(webmap_id)
                except RuntimeError:
                    raise
                item_definition.add_child(self._get_item_definitions(webmap))
            for layer_id in layer_ids:
                try:
                    item = source.content.get(layer_id)
                except RuntimeError:
                    raise
                item_definition.add_child(self._get_item_definitions(item))


        # If the item is a web map find all the feature service layers and tables that make up the map
        elif item['type'] == 'Web Map':
            item_definition = self._get_item_definition(item)
            self._graph[item.id] = item_definition

            webmap_json = item_definition.data
            featurelayer_services = []
            feature_collections = []

            if 'operationalLayers' in webmap_json:
                featurelayer_services += [layer for layer in webmap_json['operationalLayers'] if
                                          'layerType' in layer and layer[
                                              'layerType'] == "ArcGISFeatureLayer" and 'url' in layer and layer[
                                              'url'] is not None and (
                                          'type' not in layer or layer['type'] != "Feature Collection")]
                feature_collections += [layer for layer in webmap_json['operationalLayers'] if
                                        'layerType' in layer and layer[
                                            'layerType'] == "ArcGISFeatureLayer" and 'type' in layer and layer[
                                            'type'] == "Feature Collection"]
            if 'tables' in webmap_json:
                featurelayer_services += [table for table in webmap_json['tables'] if 'url' in table]

            for layer in featurelayer_services:
                service_url = os.path.dirname(layer['url'])
                feature_service = next((definition for definition in self._graph.values() if
                                        'url' in definition.info and _compare_url(definition.info['url'], service_url)),
                                       None)
                if not feature_service:
                    feature_service = _get_feature_service_related_item(service_url, source)
                    if feature_service:
                        item_definition.add_child(self._get_item_definitions(feature_service))
                else:
                    item_definition.add_child(self._get_item_definitions(feature_service.portal_item))

            for feature_collection in feature_collections:
                if 'itemId' in feature_collection and feature_collection['itemId'] is not None:
                    feature_collection = source.content.get(feature_collection['itemId'])
                    item_definition.add_child(self._get_item_definitions(feature_collection))

        # If the item is a feature service determine if it is a view and if it is find all it's sources
        elif item['type'] == 'Feature Service':
            svc = FeatureLayerCollection.fromitem(item)
            service_definition = dict(svc.properties)

            is_view = False
            if "isView" in service_definition and service_definition["isView"] is not None:
                is_view = service_definition["isView"]

            # Get the definitions of the the layers and tables
            layers_definition = {'layers': [], 'tables': []}
            for layer in svc.layers:
                layers_definition['layers'].append(dict(layer.properties))
            for table in svc.tables:
                layers_definition['tables'].append(dict(table.properties))

            # Get the item data, for example any popup definition associated with the item
            data = item.get_data()

            # Process the feature service if it is a view
            view_sources = {}
            view_source_fields = {}
            if is_view:
                try:
                    multiple_source_error = "Views based on multiple source layers are not supported."
                    sources = source._portal.con.get(svc.url + '/sources')
                    if len(sources['services']) != 1:
                        raise Exception(multiple_source_error)
                    source_service = sources['services'][0]
                    source_item = source.content.get(source_service['serviceItemId'])
                    source_fs_definition = self._get_item_definitions(source_item)

                    for layer in svc.layers + svc.tables:
                        layer_sources = source._portal.con.get(svc.url + '/' + str(layer.properties['id']) + '/sources')
                        layer_source = None
                        if 'layers' in layer_sources and len(layer_sources['layers']) == 1:
                            layer_source = layer_sources['layers'][0]
                        elif 'tables' in layer_sources and len(layer_sources['tables']) == 1:
                            layer_source = layer_sources['tables'][0]
                        else:
                            raise Exception(multiple_source_error)
                        view_sources[layer.properties['id']] = layer_source['url']
                        feature_layer = FeatureLayer(layer_source['url'], source)
                        view_source_fields[layer.properties['id']] = feature_layer.properties.fields
                except RuntimeError:
                    raise

            item_definition = _FeatureServiceDefinition(self.target, self._clone_mapping, dict(item), service_definition, layers_definition, is_view,
                                                        view_sources, view_source_fields, features=None, data=data, folder=self.folder,
                                                        thumbnail=None, portal_item=item, copy_data=self._copy_data, service_extent=self._item_extent, search_existing=self._search_existing_items)
            self._graph[item.id] = item_definition
            if is_view and source_fs_definition:
                item_definition.add_child(source_fs_definition)

        # If the item is a workforce find the group, maps and services that support the project
        elif item['type'] == 'Workforce Project':
            workforce_json = item.get_data()

            # Workforce group
            group_id = _deep_get(workforce_json, 'groupId')
            group = source.groups.get(group_id)
            group_item_definition = self._get_group_definition(group)
            self._graph[group_id] = group_item_definition

            wf_item_definition = self._get_item_definition(item)
            wf_item_definition.sharing['groups'].append(group_id)
            self._graph[item.id] = wf_item_definition
            wf_item_definition.add_child(group_item_definition)

            # Process the services
            services = ['dispatchers', 'assignments', 'workers', 'tracks']
            for service in services:
                item_id = _deep_get(workforce_json, service, 'serviceItemId')
                if item_id is not None:
                    service_item = source.content.get(item_id)
                    item_definition = self._get_item_definitions(service_item)
                    self._graph[item_id] = item_definition
                    wf_item_definition.add_child(item_definition)
                    item_definition.sharing['groups'].append(group_id)
                    item_definition.add_child(group_item_definition)


            # Process the web maps
            web_maps = ['workerWebMapId', 'dispatcherWebMapId']
            for web_map in web_maps:
                item_id = _deep_get(workforce_json, web_map)
                if item_id is not None:
                    web_map_item = source.content.get(item_id)
                    item_definition = self._get_item_definitions(web_map_item)
                    item_definition.sharing['groups'].append(group_id)
                    wf_item_definition.add_child(item_definition)
                    item_definition.add_child(group_item_definition)

            # Handle any app integrations
            integrations = _deep_get(workforce_json, 'assignmentIntegrations')
            if integrations is not None:
                for integration in integrations:
                    url_template = _deep_get(integration, 'urlTemplate')
                    if url_template is not None:
                        item_ids = re.findall('itemID=[0-9A-F]{32}', url_template, re.IGNORECASE)
                        for item_id in item_ids:
                            integration_item = source.content.get(item_id[7:])
                            item_definition = self._get_item_definitions(integration_item)
                            self._graph[item_id[7:]] = item_definition
                            wf_item_definition.add_child(item_definition)


        # If the item is a form find the feature service that supports it
        elif item['type'] == 'Form':
            item_definition = self._get_item_definition(item)
            self._graph[item.id] = item_definition

            for related_item in item_definition.related_items:
                item_def = self._get_item_definitions(source.content.get(related_item['id']))
                item_definition.add_child(item_def)

        # If the item is a pro map find the feature services that supports it
        elif item['type'] == 'Pro Map':
            item_definition = self._get_item_definition(item)
            self._graph[item.id] = item_definition

            map_json = None
            with open(item_definition.data, 'r') as file:
                map_json = json.loads(file.read())

            data_connections = []
            layer_definitions = _deep_get(map_json, 'layerDefinitions')
            if layer_definitions is not None:
                for layer_definition in layer_definitions:
                    data_connection = _deep_get(layer_definition, 'featureTable', 'dataConnection')
                    if data_connection is not None:
                        data_connections.append(data_connection)

            table_definitions = _deep_get(map_json, 'tableDefinitions')
            if table_definitions is not None:
                for table_definition in table_definitions:
                    data_connection = _deep_get(table_definition, 'dataConnection')
                    if data_connection is not None:
                        data_connections.append(data_connection)

            for data_connection in data_connections:
                if 'workspaceFactory' in data_connection and data_connection['workspaceFactory'] == 'FeatureService':
                    if 'workspaceConnectionString' in data_connection and data_connection[
                        'workspaceConnectionString'] is not None:
                        service_url = data_connection['workspaceConnectionString'][4:]
                        feature_service = next((definition for definition in self._graph.values() if
                                                'url' in definition.info and _compare_url(definition.info['url'],
                                                                                          service_url)), None)
                        if not feature_service:
                            feature_service = _get_feature_service_related_item(service_url, source)
                            if feature_service:
                                fs_definition = self._get_item_definitions(feature_service)
                                item_definition.add_child(fs_definition)

        # If the item is a pro project find the feature services that supports it
        elif item['type'] == 'Project Package':
            item_definition = self._get_item_definition(item)
            self._graph[item.id] = item_definition

            try:
                import arcpy
                ppkx = item_definition.data
                extract_dir = os.path.join(os.path.dirname(ppkx), 'extract')
                if not os.path.exists(extract_dir):
                    os.makedirs(extract_dir)

                arcpy.ExtractPackage_management(ppkx, extract_dir)

                # 1.x versions of Pro use a different folder name
                project_folder = 'p20'
                version = arcpy.GetInstallInfo()['Version']
                if version.startswith('1'):
                    project_folder = 'p12'

                project_dir = os.path.join(extract_dir, project_folder)
                if os.path.exists(project_dir):
                    aprx_files = [f for f in os.listdir(project_dir) if f.endswith('.aprx')]
                    if len(aprx_files) == 1:
                        aprx_file = os.path.join(project_dir, aprx_files[0])
                        aprx = arcpy.mp.ArcGISProject(aprx_file)
                        maps = aprx.listMaps()
                        for map in maps:
                            layers = [l for l in map.listLayers() if l.supports('connectionProperties')]
                            layers.extend(map.listTables())
                            for lyr in layers:
                                connection_properties = lyr.connectionProperties
                                workspace_factory = _deep_get(connection_properties, 'workspace_factory')
                                service_url = _deep_get(connection_properties, 'connection_info', 'url')
                                if workspace_factory == 'FeatureService' and service_url is not None:
                                    feature_service = next((definition for definition in self._graph.values() if
                                                            'url' in definition.info and _compare_url(
                                                                definition.info['url'], service_url)), None)
                                    if not feature_service:
                                        feature_service = _get_feature_service_related_item(service_url, source)
                                        if feature_service:
                                            fs_definition = self._get_item_definitions(feature_service)
                                            item_definition.add_child(fs_definition)


            except ImportError:
                pass

        # If the item is a code attachment ignore it
        elif item['type'] == 'Code Attachment':
            pass

        # All other types we no longer need to recursively look for related items
        else:
            item_definition = self._get_item_definition(item)
            self._graph[item.id] = item_definition

        return item_definition

    async def _clone(self, excecutor):
        """
        This processes each node using the asyncio library so we can have some multi-threaded stuff for POST/GET
        :return:
        """
        # Create folder if it doesn't already exist
        user = self.target.users.me
        target_folder = None
        if self.folder is not None:
            folders = user.folders
            target_folder = next((f for f in folders if f['title'].lower() == self.folder.lower()), None)
            if target_folder is None:
                target_folder = self.target.content.create_folder(self.folder)

        # Validate the item mapping and build service mapping for Feature Service and Map Service items
        for original_item_id, new_item_id in self._clone_mapping['Item IDs'].items():
            new_item = self.target.content.get(new_item_id)
            if not new_item:
                raise Exception('Item "{0}" does not exist in the target portal'.format(new_item_id))

            original_item = None
            for item in self._items:
                original_item = item._gis.content.get(original_item_id)
                if original_item:
                    break
            if not original_item:
                raise Exception('Item "{0}" does not exist in the source portal'.format(original_item_id))

            if original_item.type != new_item.type:
                raise Exception('Source item type {0} {1} does not match the target item type {2} {3}'.format(original_item['type'], original_item['title'], new_item['type'], new_item['title']))

            if new_item.type in ['Feature Service', 'Map Service']:
                layer_field_mapping, layer_id_mapping, relationship_field_mapping = _compare_service(new_item, original_item)
                self._clone_mapping['Services'][original_item['url'].rstrip('/')] = {'id' : new_item['id'], 'url' : new_item['url'].rstrip('/'), 'layer_field_mapping' : layer_field_mapping,
                                                                                    'layer_id_mapping' : layer_id_mapping, 'relationship_field_mapping' : relationship_field_mapping}

        # Then use graph to clone rest of things
        leaf_nodes = self._get_leaf_nodes()
        level = 0
        # also includes items that already existed and mapped
        cloned_items = []
        while leaf_nodes:
            logging.getLogger().info("Processing Level: {}".format(level))
            loop = asyncio.get_event_loop()
            # things to execute async
            futures = []
            synchronous_clone = []
            for node in leaf_nodes:
                if node.info['id'] not in self._clone_mapping['Item IDs'] and node.info['id'] not in self._clone_mapping['Group IDs']:
                    if isinstance(node, _ProProjectPackageDefinition):
                        synchronous_clone.append(node)
                    else:
                        futures.append(
                            loop.run_in_executor(
                                excecutor,
                                node.clone,
                            )
                        )
                else:
                    node.resolved = True
            results = []
            if len(synchronous_clone) > 0:
                for node in synchronous_clone:
                    try:
                        results.append(node.clone())
                    except _ItemCreateException as ex:
                        results.append(ex)
                        break
            if len(futures) > 0:
                results.extend(await asyncio.gather(*futures, return_exceptions=True))
                
            # if any of the results are an _ItemCreate Exception, then delete all created items/groups
            for result in results:
                if isinstance(result, _ItemCreateException):
                    for node in self._graph.values():
                        for item in node.created_items:
                            item.delete()
                    raise result
                # only return created items, not groups or item already found in target portal
                for node in self._graph.values():
                    for item in node.created_items:
                        if item not in cloned_items and isinstance(item, arcgis.gis.Item):
                            cloned_items.append(item)
            level += 1
            leaf_nodes = self._get_leaf_nodes()
        logging.getLogger().info("Completed")
        return cloned_items

    def clone(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            asyncio.set_event_loop(asyncio.new_event_loop())
            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(self._clone(executor))
            loop.close()
            return results

    def _get_group_definition(self, group):
        """Get an instance of the group definition for the specified item. This definition can be used to clone or download the group.
        Keyword arguments:
        group - The arcgis.GIS.Group to get the definition for."""
        return _GroupDefinition(self.target, self._clone_mapping, dict(group), thumbnail=None, portal_group=group, search_existing=self._search_existing_items)

    def _get_item_definition(self, item):
        """Get an instance of the corresponding definition class for the specified item. This definition can be used to clone or download the item.
        Keyword arguments:
        item - The arcgis.GIS.Item to get the definition for.
        """

        # If the item is an application or dashboard get the ApplicationDefinition
        if item['type'] == 'Web Mapping Application':
            app_json = None
            source_app_title = None
            update_url = False

            try:
                app_json = item.get_data()
            except Exception:
                pass  # item doesn't have json data

            if app_json is not None:
                update_url = True
                if "Web AppBuilder" not in item['typeKeywords'] and item[
                    'type'] != 'Operation View' and 'source' in app_json:
                    try:
                        source = item._gis
                        source_id = app_json['source']
                        app_item = source.content.get(source_id)
                        if app_item is not None:
                            source_app_title = app_item['title']
                    except Exception:
                        pass

            return _ApplicationDefinition(self.target, self._clone_mapping, dict(item), source_app_title=source_app_title, update_url=update_url,
                                          data=app_json, thumbnail=None, portal_item=item, item_extent=self._item_extent, folder=self.folder, search_existing=self._search_existing_items)

        elif item['type'] == 'Operation View':
            app_json = item.get_data()
            return _OperationViewDefintion(self.target, self._clone_mapping, dict(item), data=app_json, thumbnail=None, portal_item=item, folder=self.folder, search_existing=self._search_existing_items)

        elif item['type'] == 'Dashboard':
            app_json = item.get_data()
            return _DashboardDefinition(self.target, self._clone_mapping, dict(item), data=app_json, thumbnail=None, portal_item=item, folder=self.folder, search_existing=self._search_existing_items)

        # If the item is a web map get the WebMapDefintion
        elif item['type'] == 'Web Map':
            webmap_json = item.get_data()
            return _WebMapDefinition(self.target, self._clone_mapping, dict(item), data=webmap_json, thumbnail=None,
                                     folder=self.folder, portal_item=item, item_extent=self._item_extent, use_org_basemap=self._use_org_basemap, search_existing=self._search_existing_items)

        # If the item is a workforce project get the WorkforceProjectDefintion
        elif item['type'] == 'Workforce Project':
            workforce_json = item.get_data()
            return _WorkforceProjectDefinition(self.target, self._clone_mapping, dict(item), data=workforce_json, thumbnail=None, portal_item=item, folder=self.folder, search_existing=self._search_existing_items)

        # If the item is a workforce project get the WorkforceProjectDefintion
        elif item['type'] == 'Form':
            related_items = item.related_items('Survey2Service', 'forward')
            return _FormDefinition(self.target, self._clone_mapping, dict(item), related_items, data=None, thumbnail=None, portal_item=item, folder=self.folder, item_extent=self._item_extent, search_existing=self._search_existing_items)

        # If the item is a feature service get the FeatureServiceDefintion
        elif item['type'] == 'Feature Service':
            svc = FeatureLayerCollection.fromitem(item)
            service_definition = dict(svc.properties)

            # Get the definitions of the the layers and tables
            layers_definition = {'layers': [], 'tables': []}
            for layer in svc.layers:
                layers_definition['layers'].append(dict(layer.properties))
            for table in svc.tables:
                layers_definition['tables'].append(dict(table.properties))

            # Get the item data, for example any popup definition associated with the item
            data = item.get_data()

            return _FeatureServiceDefinition(self.target, self._clone_mapping, dict(item), service_definition, layers_definition, features=None,
                                             data=data, thumbnail=None, portal_item=item, folder=self.folder, copy_data=self._copy_data, service_extent=self._item_extent, search_existing=self._search_existing_items)

        # If the item is a feature collection get the FeatureCollectionDefintion
        elif item['type'] == 'Feature Collection':
            return _FeatureCollectionDefinition(self.target, self._clone_mapping, dict(item), data=item.get_data(), thumbnail=None, portal_item=item, folder=self.folder, search_existing=self._search_existing_items)

        # If the item is a pro map get the ProMapDefintion
        elif item['type'] == 'Pro Map':
            temp_dir = os.path.join(self._temp_dir.name, item['id'])
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            pro_map = item.download(temp_dir)
            return _ProMapDefinition(self.target, self._clone_mapping, dict(item), data=pro_map, thumbnail=None, portal_item=item, folder=self.folder, search_existing=self._search_existing_items)

        # If the item is a pro package get the ProProjectPackageDefintion
        elif item['type'] == 'Project Package':
            temp_dir = os.path.join(self._temp_dir.name, item['id'])
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            pro_package = item.download(temp_dir)
            return _ProProjectPackageDefinition(self.target, self._clone_mapping, dict(item), data=pro_package, thumbnail=None, portal_item=item, folder=self.folder, search_existing=self._search_existing_items)

        # For all other types get the corresponding definition
        else:
            if item['type'] in _TEXT_BASED_ITEM_TYPES:
                return _TextItemDefinition(self.target, self._clone_mapping, dict(item), data=item.get_data(), thumbnail=None, portal_item=item, folder=self.folder, search_existing=self._search_existing_items)
            return _ItemDefinition(self.target, self._clone_mapping, dict(item), data=None, thumbnail=None, portal_item=item, folder=self.folder, search_existing=self._search_existing_items)


class CloneNode:

    def __init__(self, target, clone_mapping, search_existing=True):
        """
        Creates a node that represents something to clone
        :param target: <GIS> The GIS where the folder should be cloned to
        """

        self._parents = set()
        self._children = set()
        self.target = target
        self._resolved = False
        self._clone_mapping = clone_mapping
        self._search_existing = search_existing
        self._temp_dir = tempfile.TemporaryDirectory()

    @property
    def children(self):
        return list(self._children)

    @property
    def parents(self):
        return list(self._parents)

    @property
    def resolved(self):
        return self._resolved

    @resolved.setter
    def resolved(self, resolved):
        self._resolved = resolved

    def add_child(self, node):
        """
        Adds a child node to this node
        :param node: <Node> The child node to add
        :return:
        """
        self._children.add(node)
        if self not in node.parents:
            node.add_parent(self)

    def add_parent(self, node):
        """
        Adds a parent node to this node
        :param node: <Node> The parent node to add
        :return:
        """
        self._parents.add(node)
        if self not in node.children:
            node.add_child(self)

    def clone(self):
        """
        The method that sub-classes can override to do whatever they need to do
        :return:
        """
        self._resolved = True

    def __repr__(self):
        return '<node representation>'


class _GroupDefinition(CloneNode):
    """
    Represents the definition of a group within ArcGIS Online or Portal.
    """

    def __init__(self, target, clone_mapping, info, thumbnail=None, portal_group=None, search_existing=True):
        super().__init__(target, clone_mapping, search_existing)
        self.info = info
        self.thumbnail = thumbnail
        self.portal_group = portal_group
        self.created_items = []

    def clone(self):
        """Clone the group in the target organization.
        Keyword arguments:
        target - The instance of arcgis.gis.GIS (the portal) to group to."""

        try:
            new_group = None
            original_group = self.info
            if self._search_existing:
                new_group = _search_for_existing_group(self.target.users.me, self.portal_group)
            if not new_group:
                title = original_group['title']
                tags = original_group['tags']
                for tag in list(tags):
                    if tag.startswith("source-") or tag.startswith("sourcefolder-"):
                        tags.remove(tag)

                original_group['tags'].append("source-{0}".format(original_group['id']))
                tags = ','.join(original_group['tags'])

                #Find a unique name for the group
                i = 1
                while True:
                    search_query = 'title:"{0}" AND owner:{1}'.format(title, self.target.users.me.username)
                    groups = [group for group in self.target.groups.search(search_query, outside_org=False) if group['title'] == title]
                    if len(groups) == 0:
                        break
                    i += 1
                    title = "{0} {1}".format(original_group['title'], i)

                thumbnail = self.thumbnail
                if not thumbnail and self.portal_group:
                    temp_dir = os.path.join(self._temp_dir.name, original_group['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_group.download_thumbnail(temp_dir)

                new_group = self.target.groups.create(title, tags, original_group['description'], original_group['snippet'],
                                                    'private', thumbnail, True, original_group['sortField'], original_group['sortOrder'], True)
                self.created_items.append(new_group)
            self.resolved=True
            self._clone_mapping['Group IDs'][original_group['id']] = new_group['id']
            return new_group
        except Exception as ex:
            raise _ItemCreateException("Failed to create group '{0}': {1}".format(original_group['title'], str(ex)), new_group)


class _ItemDefinition(CloneNode):
    """
    Represents the definition of an item within ArcGIS Online or Portal.
    """

    def __init__(self, target, clone_mapping, info, data=None, sharing=None, thumbnail=None, portal_item=None, folder=None, item_extent=None, search_existing=True):
        super().__init__(target, clone_mapping, search_existing)
        self.info = info
        self._data = data
        self.sharing = sharing
        if not self.sharing:
            self.sharing = {"access": "private", "groups": []}
        self.thumbnail = thumbnail
        self._item_property_names = ['title', 'type', 'description',
                                     'snippet', 'tags', 'culture',
                                     'accessInformation', 'licenseInfo',
                                     'typeKeywords', 'extent', 'url']
        self.portal_item = portal_item
        self.folder = folder
        self.item_extent = item_extent
        self.created_items = []

    @property
    def data(self):
        """Gets the data of the item"""
        return copy.deepcopy(self._data)

    def _get_item_properties(self, item_extent=None):
        """Get a dictionary of item properties used in create and update operations."""

        item_properties = {}
        for property_name in self._item_property_names:
            item_properties[property_name] = self.info[property_name]

        type_keywords = item_properties['typeKeywords']
        for keyword in list(type_keywords):
            if keyword.startswith('source-'):
                type_keywords.remove(keyword)

        tags = item_properties['tags']
        type_keywords.append('source-{0}'.format(self.info['id']))
        item_properties['typeKeywords'] = ','.join(item_properties['typeKeywords'])
        item_properties['tags'] = ','.join(item_properties['tags'])

        extent = _deep_get(item_properties, 'extent')
        if item_extent is not None and extent is not None and len(extent) > 0:
            item_properties['extent'] = '{0}, {1}, {2}, {3}'.format(item_extent.xmin, item_extent.ymin, item_extent.xmax, item_extent.ymax)

        return item_properties

    def clone(self):
        """Clone the item in the target organization.
        Keyword arguments:
        """

        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:

                # Get the item properties from the original item to be applied when the new item is created
                item_properties = self._get_item_properties(self.item_extent)

                temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)

                data = self.data
                if not data and self.portal_item:
                    data = self.portal_item.download(temp_dir)

                # The item's name will default to the name of the data, if it already exists in the folder we need to rename it to something unique
                name = os.path.basename(data)
                item = next((item for item in self.target.users.me.items(folder=self.folder) if item['name'] == name), None)
                if item:
                    new_name = "{0}_{1}{2}".format(os.path.splitext(name)[0], str(uuid.uuid4()).replace('-', ''), os.path.splitext(name)[1])
                    new_path = os.path.join(temp_dir, new_name)
                    os.rename(data, new_path)
                    data = new_path

                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)

                # Add the new item
                new_item = self.target.content.add(item_properties=item_properties, data=data, thumbnail=thumbnail, folder=self.folder)
                self.created_items.append(new_item)
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved = True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item
        except Exception as ex:
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)


class _TextItemDefinition(_ItemDefinition):
    """
    Represents the definition of a text based item within ArcGIS Online or Portal.
    """

    def clone(self):
        """Clone the item in the target organization.
        """
        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:
                # Get the item properties from the original item to be applied when the new item is created
                item_properties = self._get_item_properties(self.item_extent)
                data = self.data
                if data:
                    item_properties['text'] = json.dumps(data)

                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)
                new_item = self.target.content.add(item_properties=item_properties, thumbnail=thumbnail, folder=self.folder)
                self.created_items.append(new_item)
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved = True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item
        except Exception as ex:
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)


class _FeatureCollectionDefinition(_TextItemDefinition):
    """
    Represents the definition of a feature collection within ArcGIS Online or Portal.
    """

    def __init__(self, target, clone_mapping, info, data=None, sharing=None, thumbnail=None, portal_item=None, folder=None, item_extent=None, copy_data=False, search_existing=True):
        super().__init__(target, clone_mapping, info, data, sharing, thumbnail, portal_item, folder, item_extent, search_existing)
        self.copy_data = copy_data

    def clone(self):
        """Clone the item in the target organization.
        Keyword arguments:
        """

        try:
            new_item=None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:
                # Get the item properties from the original item to be applied when the new item is created
                item_properties = self._get_item_properties(self.item_extent)
                data = self.data
                if data:
                    if not self.copy_data:
                        if 'layers' in data and data['layers'] is not None:
                            for layer in data['layers']:
                                if 'featureSet' in layer and layer['featureSet'] is not None:
                                    layer['featureSet']['features'] = []
                    item_properties['text'] = json.dumps(data)

                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)
                new_item = self.target.content.add(item_properties=item_properties, thumbnail=thumbnail, folder=self.folder)
                self.created_items.append(new_item)
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved = True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item
        except Exception as ex:
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)


class _FeatureServiceDefinition(_TextItemDefinition):
    """
    Represents the definition of a hosted feature service within ArcGIS Online or Portal.
    """

    def __init__(self, target, clone_mapping, info, service_definition, layers_definition, is_view=False, view_sources={}, view_source_fields={}, features=None, data=None, sharing=None, thumbnail=None, portal_item=None, folder=None, copy_data=False, service_extent=None, search_existing=True):
        super().__init__(target, clone_mapping, info, data, sharing, thumbnail, portal_item, folder, service_extent, search_existing)
        self._service_definition = service_definition
        self._service_extent = service_extent
        self._layers_definition = layers_definition
        self._features = features
        self._is_view = is_view
        self._view_sources = view_sources
        self._view_source_fields = view_source_fields
        self.copy_data = copy_data


    @property
    def service_definition(self):
        """Gets the definition of the service"""
        return copy.deepcopy(self._service_definition)

    @property
    def layers_definition(self):
        """Gets the layer and table definitions of the service"""
        return copy.deepcopy(self._layers_definition)

    @property
    def is_view(self):
        """Gets if the service is a view"""
        return self._is_view

    @property
    def view_sources(self):
        """Gets the sources for the view"""
        return self._view_sources

    @property
    def view_source_fields(self):
        """Gets the original fields for the source view"""
        return self._view_source_fields

    @property
    def features(self):
        """Gets the features for the service"""
        return copy.deepcopy(self._features)

    def _get_features(self, feature_layer, spatial_reference=None):
        """Get the features for the given feature layer of a feature service. Returns a list of json features.
        Keyword arguments:
        feature_layer - The feature layer to return the features for
        spatial_reference -  The spatial reference to return the features in"""
        if spatial_reference is None:
            spatial_reference = { 'wkid' : 102100 }

        total_features = []
        record_count = feature_layer.query(return_count_only=True)
        max_record_count = feature_layer.properties['maxRecordCount']
        if max_record_count < 1:
            max_record_count = 1000
        offset = 0
        return_z = 'hasZ' in feature_layer.properties and feature_layer.properties['hasZ']
        return_m = 'hasM' in feature_layer.properties and feature_layer.properties['hasM']
        while offset < record_count:
            features = feature_layer.query(out_sr=spatial_reference, result_offset=offset, result_record_count=max_record_count, return_z=return_z, return_m=return_m).features
            offset += len(features)
            total_features += [f.as_dict for f in features]
        return total_features

    def _add_features(self, layers, relationships, layer_field_mapping, spatial_reference):
        """Add the features from the definition to the layers returned from the cloned item.
        Keyword arguments:
        layers - Dictionary containing the id of the layer and its corresponding arcgis.lyr.FeatureLayer
        relationships - Dictionary containing the id of the layer and its relationship definitions
        layer_field_mapping - field mapping if the case or name of field changed from the original service
        spatial_reference -  The spatial reference to create the features in"""

        # Get the features if they haven't already been queried
        features = self.features
        original_layers = []
        if not features and self.portal_item:
            svc = FeatureLayerCollection.fromitem(self.portal_item)
            features = {}
            original_layers = svc.layers + svc.tables
            for layer in original_layers:
                features[str(layer.properties['id'])] = self._get_features(layer, spatial_reference)
        else:
            return

        # Update the feature attributes if field names have changed
        for layer_id in features:
            if int(layer_id) in layer_field_mapping:
                field_mapping = layer_field_mapping[int(layer_id)]
                for feature in features[layer_id]:
                    _update_feature_attributes(feature, field_mapping)

        # Add in chunks of 2000 features
        chunk_size = 2000
        layer_ids = [id for id in layers]
        object_id_mapping = {}

        # Find all the relates where the layer's role is the origin and the key field is the global id field
        # We want to process these first, get the new global ids that are created and update in related features before processing the relates
        for layer_id in relationships:
            if layer_id not in layer_ids or layer_id not in layers:
                continue

            properties = layers[layer_id].properties
            if 'globalIdField' not in properties:
                continue

            global_id_field = properties['globalIdField']
            object_id_field = properties['objectIdField']
            relates = [relate for relate in relationships[layer_id] if relate['role'] == 'esriRelRoleOrigin' and relate['keyField'] == global_id_field]
            if len(relates) == 0:
                continue

            layer = layers[layer_id]
            layer_features = features[str(layer_id)]
            if len(layer_features) == 0:
                layer_ids.remove(layer_id)
                continue

            # Add the features to the layer in chunks
            add_results = []
            for features_chunk in [layer_features[i:i+chunk_size] for i in range(0, len(layer_features), chunk_size)]:
                edits = layer.edit_features(adds=features_chunk)
                add_results += edits['addResults']
            layer_ids.remove(layer_id)

            # Create a mapping between the original global id and the new global id
            object_id_mapping[layer_id] = {layer_features[i]['attributes'][object_id_field] : add_results[i]['objectId'] for i in range(0, len(layer_features))}
            global_id_mapping = {layer_features[i]['attributes'][global_id_field] : add_results[i]['globalId'] for i in range(0, len(layer_features))}

            for relate in relates:
                related_layer_id = relate['relatedTableId']
                if related_layer_id not in layer_ids:
                    continue
                related_layer_features = features[str(related_layer_id)]
                if len(related_layer_features) == 0:
                    layer_ids.remove(related_layer_id)
                    continue

                # Get the definition of the definition relationship
                destination_relate = next((r for r in relationships[related_layer_id] if r['id'] == relate['id'] and r['role'] == 'esriRelRoleDestination'), None)
                if not destination_relate:
                    continue

                key_field = destination_relate['keyField']

                # Update the relate features keyfield to the new global id
                for feature in related_layer_features:
                    if key_field in feature['attributes']:
                        global_id = feature['attributes'][key_field]
                        if global_id in global_id_mapping:
                            feature['attributes'][key_field] = global_id_mapping[global_id]

                # Add the related features to the layer in chunks
                add_results = []
                for features_chunk in [related_layer_features[i:i+chunk_size] for i in range(0, len(layer_features), chunk_size)]:
                    edits = layers[related_layer_id].edit_features(adds=features_chunk)
                    add_results += edits['addResults']
                layer_ids.remove(related_layer_id)
                object_id_field = layers[related_layer_id].properties['objectIdField']
                object_id_mapping[related_layer_id] = {related_layer_features[i]['attributes'][object_id_field] : add_results[i]['objectId'] for i in range(0, len(related_layer_features))}

        # Add features to all other layers and tables
        for layer_id in layer_ids:
            layer_features = features[str(layer_id)]
            if len(layer_features) == 0:
                continue
            add_results = []
            for features_chunk in [layer_features[i:i+chunk_size] for i in range(0, len(layer_features), chunk_size)]:
                edits = layers[layer_id].edit_features(adds=features_chunk)
                add_results += edits['addResults']
            object_id_field = layers[layer_id].properties['objectIdField']
            object_id_mapping[layer_id] = {layer_features[i]['attributes'][object_id_field] : add_results[i]['objectId'] for i in range(0, len(layer_features))}

        # Add attachments
        for original_layer in original_layers:
            properties = original_layer.properties
            layer_id = properties['id']
            if 'hasAttachments' in properties and properties['hasAttachments']:
                if str(layer_id) in features and features[str(layer_id)] is not None:
                    original_attachments = original_layer.attachments
                    attachments = layers[layer_id].attachments
                    object_id_field = layers[layer_id].properties['objectIdField']
                    layer_features = features[str(layer_id)]
                    if layer_id not in object_id_mapping:
                        continue

                    for feature in layer_features:
                        original_oid = feature['attributes'][object_id_field]
                        if original_oid not in object_id_mapping[layer_id]:
                            continue

                        oid = object_id_mapping[layer_id][original_oid]
                        attachment_infos = original_attachments.get_list(original_oid)
                        if len(attachment_infos) > 0:
                            temp_dir = os.path.join(self._temp_dir.name, 'attachments')
                            if not os.path.exists(temp_dir):
                                os.makedirs(temp_dir)
                            for attachment_info in attachment_infos:
                                attachment_file = original_attachments.download(original_oid, attachment_info['id'], temp_dir)
                                attachments.add(oid, attachment_file)

    def _get_unique_name(self, target, name, force_add_guid_suffix=False):
        """Create a new unique name for the service.
        Keyword arguments:
        target - The instance of arcgis.gis.GIS (the portal) to clone the feature service to.
        name - The original name.
        force_add_guid_suffix - Indicates if a guid suffix should automatically be added to the end of the service name
        """

        if name[0].isdigit():
            name = '_' + name
        name = name.replace(' ', '_')

        if not force_add_guid_suffix:
            guids = re.findall('[0-9A-F]{32}', name, re.IGNORECASE)
            for guid in guids:
                if guid in self._clone_mapping['Group IDs']:
                    name = name.replace(guid, self._clone_mapping['Group IDs'][guid])
                elif guid in self._clone_mapping['Item IDs']:
                    name = name.replace(guid, self._clone_mapping['Item IDs'][guid])
                else:
                    new_guid = str(uuid.uuid4()).replace('-', '')
                    name = name.replace(guid, new_guid)

            while True:
                if target.content.is_service_name_available(name, 'featureService'):
                    break

                guid = str(uuid.uuid4()).replace('-', '')
                ends_with_guid = re.findall('_[0-9A-F]{32}$', name, re.IGNORECASE)
                if len(ends_with_guid) > 0:
                    name = name[:len(name) - 32] + guid
                else:
                    name = "{0}_{1}".format(name, guid)

        else:
            guid = str(uuid.uuid4()).replace('-', '')
            ends_with_guid = re.findall('_[0-9A-F]{32}$', name, re.IGNORECASE)
            if len(ends_with_guid) > 0:
                name = name[:len(name) - 32] + guid
            else:
                name = "{0}_{1}".format(name, guid)

        return name

    def clone(self):
        """Clone the feature service in the target organization.
        Keyword arguments:
        target - The instance of arcgis.gis.GIS (the portal) to clone the feature service to.
        folder - The name of the folder to create the item in
        clone_mapping - Dictionary containing mapping between new and old items.
        """

        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
                if new_item:
                    # build the mappings
                    layer_field_mapping, layer_id_mapping, relationship_field_mapping = _compare_service(new_item, self.portal_item)

            if not new_item:

                # Get the definition of the original feature service
                service_definition = self.service_definition

                # Modify the definition before passing to create the new service
                name = original_item['name']
                if name is None:
                    name = os.path.basename(os.path.dirname(original_item['url']))
                name = self._get_unique_name(self.target, name)
                service_definition['name'] = name

                for key in ['layers', 'tables', 'fullExtent', 'hasViews']:
                    if key in service_definition:
                        del service_definition[key]

                # Set the extent and spatial reference of the service
                new_extent = service_definition['initialExtent']
                if self._service_extent:
                    new_extent = json.loads(self._service_extent.JSON)
                service_definition['initialExtent'] = new_extent
                service_definition['spatialReference'] = new_extent['spatialReference']

                if self.is_view:
                    properties = ['name', 'isView', 'sourceSchemaChangesAllowed', 'isUpdatableView', 'capabilities']
                    service_definition_copy = copy.deepcopy(service_definition)
                    for key, value in service_definition_copy.items():
                        if key not in properties:
                            del service_definition[key]

                # Remove any unsupported capabilities from layer for Portal
                supported_capabilities = ['Create','Query','Editing','Update','Delete','Uploads','Sync','Extract']
                if self.target.properties.isPortal:
                    capabilities = _deep_get(service_definition, 'capabilities')
                    if capabilities is not None:
                       service_definition['capabilities'] = ','.join([x for x in capabilities.split(',') if x in supported_capabilities])

                # Create a new feature service
                # In some cases isServiceNameAvailable returns true but fails to create the service with error that a service with the name already exists.
                # In these cases catch the error and try again with a unique name.
                try:
                    new_item = self.target.content.create_service(name, service_type='featureService', create_params=service_definition, is_view=self.is_view, folder=self.folder)
                    self.created_items.append(new_item)
                except RuntimeError as ex:
                    if "already exists" in str(ex):
                        name = self._get_unique_name(self.target, name)
                        service_definition['name'] = name
                        new_item = self.target.content.create_service(name, service_type='featureService', create_params=service_definition, folder=self.folder)
                        self.created_items.append(new_item)
                    elif "managed database" in str(ex):
                        raise Exception("The target portal's managed database must be an ArcGIS Data Store.")
                    else:
                        raise

                # Get the layer and table definitions from the original service and prepare them for the new service
                layers_definition = self.layers_definition
                relationships = {}
                time_infos = {}
                for layer in layers_definition['layers'] + layers_definition['tables']:
                    # Need to remove relationships first and add them back individually
                    # after all layers and tables have been added to the definition
                    if 'relationships' in layer and layer['relationships'] is not None and len(layer['relationships']) != 0:
                        relationships[layer['id']] = layer['relationships']
                        layer['relationships'] = []

                    # Remove time settings first and add them back after the layer has been created
                    if 'timeInfo' in layer and layer['timeInfo'] is not None:
                        time_infos[layer['id']] = layer['timeInfo']
                        del layer['timeInfo']

                    # Need to remove all indexes duplicated for fields.
                    # Services get into this state due to a bug in 10.4 and 1.2
                    field_names = [f['name'].lower() for f in layer['fields']]

                    unique_fields = []
                    if 'indexes' in layer:
                        for index in list(layer['indexes']):
                            fields = index['fields'].lower()
                            if fields in unique_fields or fields not in field_names:
                                layer['indexes'].remove(index)
                            else:
                                unique_fields.append(fields)

                    # Due to a bug at 10.5.1 any domains for a double field must explicitly have a float code rather than int
                    for field in layer['fields']:
                        field_type = _deep_get(field, 'type')
                        if field_type in ["esriFieldTypeDouble", "esriFieldTypeSingle"]:
                            coded_values = _deep_get(field, 'domain', 'codedValues')
                            if coded_values is not None:
                                for coded_value in coded_values:
                                    code = _deep_get(coded_value, 'code')
                                    if code is not None:
                                        coded_value['code'] = float(code)

                    # Set the extent of the feature layer to the specified default extent
                    if layer['type'] == 'Feature Layer':
                        layer['extent'] = new_extent

                    # Remove hasViews property if exists
                    if 'hasViews' in layer:
                        del layer['hasViews']

                    # Update the view layer source properties
                    if self.is_view:
                        url = self.view_sources[layer['id']]
                        original_feature_service = os.path.dirname(url)
                        original_id = os.path.basename(url)
                        admin_layer_info = {}
                        layer['adminLayerInfo'] = admin_layer_info

                        for key, value in self._clone_mapping['Services'].items():
                            if _compare_url(key, original_feature_service):
                                new_service = value
                                view_layer_definition = {}
                                view_layer_definition['sourceServiceName'] = os.path.basename(os.path.dirname(new_service['url']))
                                view_layer_definition['sourceLayerId'] = new_service['layer_id_mapping'][int(original_id)]
                                view_layer_definition['sourceLayerFields'] = '*'
                                admin_layer_info['viewLayerDefinition'] = view_layer_definition
                                break

                    # Remove any unsupported capabilities from layer for Portal
                    if self.target.properties.isPortal:
                        capabilities = _deep_get(layer, 'capabilities')
                        if capabilities is not None:
                            layer['capabilities'] = ','.join([x for x in capabilities.split(',') if x in supported_capabilities])

                # Add the layer and table definitions to the service
                # Explicitly add layers first and then tables, otherwise sometimes json.dumps() reverses them and this effects the output service
                feature_service = FeatureLayerCollection.fromitem(new_item)
                feature_service_admin = feature_service.manager
                layers = []
                tables = []
                if len(layers_definition['layers']) > 0:
                    layers = copy.deepcopy(layers_definition['layers'])
                    if self.is_view:
                        for layer in layers:
                            del layer['fields']
                if len(layers_definition['tables']) > 0:
                    tables = copy.deepcopy(layers_definition['tables'])
                    if self.is_view:
                        for table in tables:
                            del table['fields']
                definition = '{{"layers" : {0}, "tables" : {1}}}'.format(json.dumps(layers), json.dumps(tables))
                _add_to_definition(feature_service_admin, definition)

                # Create a lookup between the new and old layer ids
                layer_id_mapping = {}
                original_layers = layers_definition['layers'] + layers_definition['tables']
                i = 0
                for layer in feature_service.layers + feature_service.tables:
                    layer_id_mapping[original_layers[i]['id']] = layer.properties['id']
                    i += 1

                # Create a lookup for the layers and tables using their id
                new_layers = {}
                for layer in feature_service.layers + feature_service.tables:
                    for key, value in layer_id_mapping.items():
                        if value == layer.properties['id']:
                            new_layers[key] = layer
                            break

                # Create a field mapping object if the case or name of the field has changes
                layer_field_mapping = {}
                for layer in layers_definition['layers'] + layers_definition['tables']:
                    layer_id = layer['id']
                    fields = layer['fields']
                    if self.is_view:
                        fields = self.view_source_fields[layer_id]
                    new_layer = new_layers[layer_id]
                    field_mapping = {}
                    if len(fields) <= len(new_layer.properties['fields']):
                        for i in range(0, len(fields)):
                            if fields[i]['name'] != new_layer.properties['fields'][i]['name']:
                                field_mapping[fields[i]['name']] = new_layer.properties['fields'][i]['name']
                        if len(field_mapping) > 0:
                            layer_field_mapping[layer_id] = field_mapping

                    # If editor tracking fields changed from original layer we need to update the layer field mapping
                    del_fields = []
                    if 'editFieldsInfo' in layer and layer['editFieldsInfo'] is not None and 'editFieldsInfo' in new_layer.properties and new_layer.properties['editFieldsInfo'] is not None:
                        new_edit_fields_info = new_layer.properties['editFieldsInfo']
                        for key, old_field in layer['editFieldsInfo'].items():
                            if key in new_edit_fields_info:
                                new_field = new_edit_fields_info[key]
                                if old_field != new_field:
                                    new_delete_field = old_field
                                    if old_field in field_mapping:
                                        new_delete_field = field_mapping[old_field]
                                    for field in new_layer.properties['fields']:
                                        if field['name'] == new_delete_field and self.is_view == False:
                                            del_fields.append(new_delete_field)
                                            break
                                    if layer_id in layer_field_mapping:
                                        layer_field_mapping[layer_id][old_field] = new_field
                                    else:
                                        field_mapping = {old_field : new_field}
                                        layer_field_mapping[layer_id] = field_mapping

                    update_definition = {}
                    delete_definition = {}

                    if len(del_fields) > 0 or layer_id in layer_field_mapping:
                        # Delete the old editor tracking fields from the layer
                        if len(del_fields) > 0:
                            layer_admin = new_layer.manager
                            delete_definition_fields = []
                            for field in del_fields:
                                delete_definition_fields.append({'name': field})
                            delete_definition['fields'] = delete_definition_fields

                        # Update editing templates if field mapping is required
                        if layer_id in layer_field_mapping:
                            field_mapping = layer_field_mapping[layer_id]

                            if 'templates' in new_layer.properties and new_layer.properties['templates'] is not None:
                                templates = new_layer.properties['templates']
                                for template in templates:
                                    if 'prototype' in template and template['prototype'] is not None:
                                        _update_feature_attributes(template['prototype'], field_mapping)
                                update_definition['templates'] = templates

                            if 'types' in new_layer.properties and new_layer.properties['types'] is not None:
                                types = new_layer.properties['types']
                                for layer_type in types:
                                    if 'templates' in layer_type and layer_type['templates'] is not None:
                                        for template in layer_type['templates']:
                                            if 'prototype' in template and template['prototype'] is not None:
                                                _update_feature_attributes(template['prototype'], field_mapping)
                                update_definition['types'] = types

                    # Update field visibility for views
                    if self.is_view:
                        if 'viewDefinitionQuery' in layer and layer['viewDefinitionQuery']:
                            update_definition['viewDefinitionQuery'] = layer['viewDefinitionQuery']
                            if layer_id in layer_field_mapping:
                                update_definition['viewDefinitionQuery'] = _find_and_replace_fields(update_definition['viewDefinitionQuery'], layer_field_mapping[layer_id])

                        field_visibility = []
                        need_update = False
                        view_field_names = [f['name'].lower() for f in layer['fields']]
                        for source_field in self.view_source_fields[layer_id]:
                            source_field_name = source_field['name']
                            visible = source_field_name.lower() in view_field_names
                            if not visible:
                                need_update = True
                            field_name = source_field_name
                            if layer_id in layer_field_mapping:
                                if source_field_name in layer_field_mapping[layer_id]:
                                    field_name = layer_field_mapping[layer_id][source_field_name]
                            field_visibility.append({'name' : field_name, 'visible' : visible})
                        if need_update:
                            update_definition['fields'] = field_visibility

                    # Add time settings back to the layer
                    if layer_id in time_infos:
                        time_info = time_infos[layer_id]
                        start_time = _deep_get(time_info, "startTimeField")
                        if start_time and start_time in field_mapping:
                            time_info["startTimeField"] = field_mapping[start_time]
                        elif start_time == "":
                            time_info["startTimeField"] = None
                        end_time = _deep_get(time_info, "endTimeField")
                        if end_time and end_time in field_mapping:
                            time_info["endTimeField"] = field_mapping[end_time]
                        elif end_time == "":
                            time_info["endTimeField"] = None
                        update_definition['timeInfo'] = time_info

                    # Update the definition of the layer
                    if len(update_definition) > 0 or len(delete_definition) > 0:
                        layer_admin = new_layer.manager
                        if len(update_definition) > 0:
                            layer_admin.update_definition(update_definition)
                        if len(delete_definition) > 0:
                            layer_admin.delete_from_definition(delete_definition)

                # Add the relationships back to the layers
                relationship_field_mapping = {}
                if len(relationships) > 0 and self.is_view == False:
                    for layer_id in relationships:
                        for relationship in relationships[layer_id]:
                            if layer_id in layer_field_mapping:
                                field_mapping = layer_field_mapping[layer_id]
                                if relationship['keyField'] in field_mapping:
                                    relationship['keyField'] = field_mapping[relationship['keyField']]
                            related_table_id = relationship['relatedTableId']
                            if related_table_id in layer_field_mapping:
                                field_mapping = layer_field_mapping[related_table_id]
                                if layer_id not in relationship_field_mapping:
                                    relationship_field_mapping[layer_id] = {}
                                relationship_field_mapping[layer_id][relationship['id']] = field_mapping

                    relationships_copy = copy.deepcopy(relationships)
                    for layer_id in relationships_copy:
                        for relationship in relationships_copy[layer_id]:
                            relationship['relatedTableId'] = layer_id_mapping[relationship['relatedTableId']]

                    if self.target.properties.isPortal:
                        relationships_definition = {'layers' : []}
                        for key, value in layer_id_mapping.items():
                            if key in relationships_copy:
                                relationships_definition['layers'].append({'id' : value, 'relationships' : relationships_copy[key]})
                            else:
                                relationships_definition['layers'].append({'id' : value, 'relationships' : []})
                        feature_service_admin.add_to_definition(relationships_definition)
                    else:
                        for layer_id in relationships_copy:
                            layer = new_layers[layer_id]
                            layer.manager.add_to_definition({'relationships' : relationships_copy[layer_id]})

                # Get the item properties from the original item
                item_properties = self._get_item_properties(self.item_extent)
                del item_properties['url']

                # Merge type keywords from what is created by default for the new item and what was in the original item
                type_keywords = list(new_item['typeKeywords'])
                type_keywords.extend(item_properties['typeKeywords'].split(','))
                type_keywords = list(set(type_keywords))

                # Replace type keyword if it references an item id of cloned item, ex. Survey123
                for keyword in list(type_keywords):
                    if keyword in self._clone_mapping['Item IDs']:
                        type_keywords.remove(keyword)
                        type_keywords.append(self._clone_mapping['Item IDs'][keyword])
                item_properties['typeKeywords'] = ','.join(type_keywords)

                # Get the collection of layers and tables from the item data
                data = self.data
                layers = []
                if data and 'layers' in data and data['layers'] is not None:
                    layers += [layer for layer in data['layers']]
                if data and 'tables' in data and data['tables'] is not None:
                    layers += [layer for layer in data['tables']]

                # Update any pop-up, labeling or renderer field references
                for layer_id in layer_field_mapping:
                    layer = next((layer for layer in layers if layer['id'] == layer_id), None)
                    if layer:
                        _update_layer_fields(layer, layer_field_mapping[layer_id])

                for layer_id in relationship_field_mapping:
                    layer = next((layer for layer in layers if layer['id'] == layer_id), None)
                    if layer:
                        _update_layer_related_fields(layer, relationship_field_mapping[layer_id])

                # Update the layer id
                for layer in layers:
                    layer['id'] = layer_id_mapping[layer['id']]

                # Set the data to the text properties of the item
                if data:
                    item_properties['text'] = json.dumps(data)

                # If the item title has a guid, check if it is in the clone_mapping and replace if it is.
                guids = re.findall('[0-9A-F]{32}', item_properties['title'], re.IGNORECASE)
                for guid in guids:
                    if guid in self._clone_mapping['Group IDs']:
                        item_properties['title'] = item_properties['title'].replace(guid, self._clone_mapping['Group IDs'][guid])
                    elif guid in self._clone_mapping['Item IDs']:
                        item_properties['title'] = item_properties['title'].replace(guid, self._clone_mapping['Item IDs'][guid])

                # Update the item definition of the service
                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)
                new_item.update(item_properties=item_properties, thumbnail=thumbnail)

                # Copy features from original item
                if self.copy_data and not self.is_view:
                    self._add_features(new_layers, relationships, layer_field_mapping, feature_service.properties['spatialReference'])

            # share items
            _share_item_with_groups(new_item, self.sharing,self._clone_mapping["Group IDs"])
            self.resolved = True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            self._clone_mapping['Services'][original_item['url'].rstrip('/')] = {'id' : new_item['id'], 'url' : new_item['url'].rstrip('/'), 'layer_field_mapping' : layer_field_mapping, 'layer_id_mapping' : layer_id_mapping, 'relationship_field_mapping' : relationship_field_mapping}
            return new_item
        except Exception as ex:
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)


class _WebMapDefinition(_TextItemDefinition):
    """
    Represents the definition of a web map within ArcGIS Online or Portal.
    """

    def __init__(self, target, clone_mapping, info, data=None, sharing=None, thumbnail=None, portal_item=None, folder=None, item_extent=None, use_org_basemap=False, search_existing=True):
        super().__init__(target, clone_mapping, info, data, sharing, thumbnail, portal_item, folder, item_extent, search_existing)
        self.use_org_basemap = use_org_basemap

    def clone(self):
        """Clone the web map in the target organization.
        """

        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:

                # Get the item properties from the original web map which will be applied when the new item is created
                item_properties = self._get_item_properties(self.item_extent)

                # Swizzle the item ids and URLs of the feature layers and tables in the web map
                webmap_json = self.data

                layers = []
                feature_collections = []
                map_service_layers = []
                if 'operationalLayers' in webmap_json:
                    layers += [layer for layer in webmap_json['operationalLayers'] if 'layerType' in layer and layer['layerType'] == "ArcGISFeatureLayer" and 'url' in layer and layer['url'] is not None]
                    feature_collections += [layer for layer in webmap_json['operationalLayers'] if 'layerType' in layer and layer['layerType'] == "ArcGISFeatureLayer" and 'type' in layer and layer['type'] == "Feature Collection"]
                    map_service_layers += [layer for layer in webmap_json['operationalLayers'] if 'layerType' in layer and layer['layerType'] == "ArcGISMapServiceLayer" and 'url' in layer and layer['url'] is not None]
                if 'tables' in webmap_json:
                    layers += [table for table in webmap_json['tables'] if 'url' in table]

                for layer in layers:
                    feature_service_url = os.path.dirname(layer['url'])
                    for original_url, new_service in self._clone_mapping['Services'].items():
                        if _compare_url(feature_service_url, original_url):
                            layer_id = int(os.path.basename(layer['url']))
                            new_id = new_service['layer_id_mapping'][layer_id]
                            layer['url'] = "{0}/{1}".format(new_service['url'], new_id)
                            layer['itemId'] = new_service['id']
                            if layer_id in new_service['layer_field_mapping']:
                                _update_layer_fields(layer, new_service['layer_field_mapping'][layer_id])
                            if layer_id in new_service['relationship_field_mapping']:
                                _update_layer_related_fields(layer, new_service['relationship_field_mapping'][layer_id])
                            break

                for feature_collection in feature_collections:
                    if 'itemId' in feature_collection and feature_collection['itemId'] is not None and feature_collection['itemId'] in self._clone_mapping['Item IDs']:
                        feature_collection['itemId'] = self._clone_mapping['Item IDs'][feature_collection['itemId']]

                for map_service_layer in map_service_layers:
                    for original_url, new_service in self._clone_mapping['Services'].items():
                        if _compare_url(feature_service_url, original_url):
                            map_service_layer['url'] = new_service['url']
                            map_service_layer['itemId'] = new_service['id']
                            break

                # Change the basemap to the default basemap defined in the target organization
                if self.use_org_basemap:
                    properties = self.target.properties
                    if 'defaultBasemap' in properties and properties['defaultBasemap'] is not None:
                        default_basemap = properties['defaultBasemap']
                        if 'title' in default_basemap and 'baseMapLayers' in default_basemap and default_basemap['baseMapLayers'] is not None:
                            for key in [k for k in default_basemap]:
                                if key not in ['title', 'baseMapLayers']:
                                    del default_basemap[key]
                            for basemap_layer in default_basemap['baseMapLayers']:
                                if 'resourceInfo' in basemap_layer:
                                    del basemap_layer['resourceInfo']
                            webmap_json['baseMap'] = default_basemap

                # Add the web map to the target portal
                item_properties['text'] = json.dumps(webmap_json)

                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)
                new_item = self.target.content.add(item_properties=item_properties, thumbnail=thumbnail, folder=self.folder)
                self.created_items.append(new_item)
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved=True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item
        except Exception as ex:
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)


class _OperationViewDefintion(_TextItemDefinition):
    """
    Represents the definition of an Operation View within ArcGIS Online or Portal
    """

    def clone(self):
        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:

                # Get the item properties from the original application which will be applied when the new item is created
                item_properties = self._get_item_properties(self.item_extent)

                # Swizzle the item ids of the web maps, groups and URLs of defined in the application's data
                app_json = self.data

                if app_json is not None:
                    app_json_text = ''

                if app_json and 'version' in app_json:
                    if app_json['version'] == "1.2":
                        app_json = self._swizzle_ids(self._clone_mapping)
                    else:
                        raise _ItemCreateException("Version {} is not supported".format(app_json['version']))
                else:
                    raise _ItemCreateException("Operation View is not versioned and cannot be cloned")

                # dump json
                app_json_text = json.dumps(app_json)

                # Perform a general find and replace of field names if field mapping is required
                for service in self._clone_mapping['Services']:
                    for layer_id in self._clone_mapping['Services'][service]['layer_field_mapping']:
                        field_mapping = self._clone_mapping['Services'][service]['layer_field_mapping'][layer_id]
                        app_json_text = _find_and_replace_fields(app_json_text, field_mapping)

                item_properties['text'] = app_json_text

                # Add the application to the target portal
                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)
                new_item = self.target.content.add(item_properties=item_properties, thumbnail=thumbnail,
                                              folder=self.folder)
                self.created_items.append(new_item)
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved=True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item

        except Exception as ex:
            raise _ItemCreateException(
                "Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)

    def _swizzle_ids(self, clone_mapping):
        """
        Injects the new item ids into the operation view json
        :param clone_mapping: The item id mapping dictionary
        :return: the updated json/dict
        """
        app_json = self.data
        if 'widgets' in app_json:
            for widget in app_json['widgets']:
                if widget['type'] == 'mapWidget':
                    if 'mapId' in widget:
                        widget['mapId'] = clone_mapping['Item IDs'][widget['mapId']]
        if 'standaloneDataSources' in app_json:
            for ds in app_json['standaloneDataSources']:
                if 'serviceItemId' in ds:
                    # update the url
                    if 'url' in ds:
                        for url, cloned_service in clone_mapping['Services'].items():
                            if cloned_service['id'] == clone_mapping['Item IDs'][ds["serviceItemId"]]:
                                # get layer id from url
                                layer_id = int(ds['url'].split("/")[-1])
                                ds['url'] = "{}/{}".format(cloned_service['url'], cloned_service['layer_id_mapping'][layer_id])
                    # update the item id
                    ds['serviceItemId'] = clone_mapping['Item IDs'][ds['serviceItemId']]
        return app_json

    @staticmethod
    def get_webmap_ids(data):
        """
        Parses an operation view json/dict at version 1.2 to find all of the webmap ids
        :param data: The json/dict to parse
        :return: A list of webmap ids
        """
        webmap_ids = set()
        if 'widgets' in data:
            for widget in data['widgets']:
                if widget['type'] == 'mapWidget':
                    if 'mapId' in widget:
                        webmap_ids.add(widget['mapId'])
        return list(webmap_ids)

    @staticmethod
    def get_layer_ids(data):
        """
        Parses an operation view json/dict at version 1.2 to find all of the webmap ids
        :param data: The json/dict to parse
        :return: A list of layer ids
        """
        layer_ids = set()
        if 'standaloneDataSources' in data:
            for ds in data['standaloneDataSources']:
                if 'serviceItemId' in ds:
                    layer_ids.add(ds['serviceItemId'])
        return list(layer_ids)


class _DashboardDefinition(_TextItemDefinition):
    """
    Represents the definition of a Dashboard within ArcGIS Online or Portal
    """

    def clone(self):
        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:

                # Get the item properties from the original application which will be applied when the new item is created
                item_properties = self._get_item_properties(self.item_extent)

                # Swizzle the item ids of the web maps, groups and URLs of defined in the application's data
                app_json = self.data

                if app_json is not None:
                    app_json_text = ''

                if app_json and 'version' in app_json:
                    if app_json['version'] == 24:
                        app_json = self._swizzle_v24(self._clone_mapping)
                    else:
                        raise _ItemCreateException("Dashboard version {} is not supported".format(app_json['version']))
                else:
                    raise _ItemCreateException("Dashboard is not versioned and cannot be cloned")

                # dump json
                app_json_text = json.dumps(app_json)

                # Perform a general find and replace of field names if field mapping is required
                for service in self._clone_mapping['Services']:
                    for layer_id in self._clone_mapping['Services'][service]['layer_field_mapping']:
                        field_mapping = self._clone_mapping['Services'][service]['layer_field_mapping'][layer_id]
                        app_json_text = _find_and_replace_fields(app_json_text, field_mapping)

                item_properties['text'] = app_json_text

                # Add the application to the target portal
                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)
                new_item = self.target.content.add(item_properties=item_properties, thumbnail=thumbnail,
                                              folder=self.folder)
                self.created_items.append(new_item)
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved=True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item

        except Exception as ex:
            raise _ItemCreateException(
                "Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)

    def _swizzle_v24(self, clone_mapping):
        """
        Injects the new item ids into the dashboard json
        :param clone_mapping: The item id mapping dictionary
        :return: the updated json/dict
        """
        app_json = self.data
        if 'widgets' in self.data:
            for widget in app_json['widgets']:
                if widget['type'] == 'mapWidget':
                    if 'itemId' in widget:
                        widget['itemId'] = clone_mapping['Item IDs'][widget['itemId']]
                elif "datasets" in widget:
                    for dataset in widget["datasets"]:
                        if "dataSource" in dataset and "itemId" in dataset["dataSource"]:
                            # in some cases the layer ids may have changed when cloning
                            # so we can use a mapping between the old and new to update it
                            for url, cloned_service in clone_mapping['Services'].items():
                                if cloned_service['id'] == clone_mapping['Item IDs'][dataset["dataSource"]["itemId"]]:
                                    # update the layer id
                                    dataset["dataSource"]["layerId"] = cloned_service['layer_id_mapping'][dataset["dataSource"]["layerId"]]
                            # update the item id
                            dataset["dataSource"]["itemId"] = clone_mapping['Item IDs'][dataset["dataSource"]["itemId"]]

        if "headerPanel" in app_json and "selectors" in app_json["headerPanel"]:
            for selector in app_json["headerPanel"]["selectors"]:
                if "datasets" in selector:
                    for dataset in selector["datasets"]:
                        if "dataSource" in dataset and "itemId" in dataset["dataSource"]:
                            # in some cases the layer ids may have changed when cloning
                            # so we can use a mapping between the old and new to update it
                            for url, cloned_service in clone_mapping['Services'].items():
                                if cloned_service['id'] == clone_mapping['Item IDs'][dataset["dataSource"]["itemId"]]:
                                    # update the layer id
                                    dataset["dataSource"]["layerId"] = cloned_service['layer_id_mapping'][dataset["dataSource"]["layerId"]]
                            # update the item id
                            dataset["dataSource"]["itemId"] = clone_mapping['Item IDs'][dataset["dataSource"]["itemId"]]

        if "leftPanel" in app_json and "selectors" in app_json["leftPanel"]:
            for selector in app_json["leftPanel"]["selectors"]:
                if "datasets" in selector:
                    for dataset in selector["datasets"]:
                        if "dataSource" in dataset and "itemId" in dataset["dataSource"]:
                            # in some cases the layer ids may have changed when cloning
                            # so we can use a mapping between the old and new to update it
                            for url, cloned_service in clone_mapping['Services'].items():
                                if cloned_service['id'] == clone_mapping['Item IDs'][dataset["dataSource"]["itemId"]]:
                                    # update the layer id
                                    dataset["dataSource"]["layerId"] = cloned_service['layer_id_mapping'][dataset["dataSource"]["layerId"]]
                            # update the item id
                            dataset["dataSource"]["itemId"] = clone_mapping['Item IDs'][dataset["dataSource"]["itemId"]]
        return app_json

    @staticmethod
    def get_webmap_ids(data):
        """
        Parses a dashboard based on version to return the list of webmap ids
        :param data: The json/dict to parse
        :return: A list of webmap ids
        """
        if 'version' in data:
            if data['version'] == 24:
                webmap_ids = _DashboardDefinition._get_webmap_ids_v24(data)
            else:
                raise _ItemCreateException("Dashboard version {} is not supported".format(data['version']))
        else:
            raise _ItemCreateException("Dashboard is not versioned and cannot be cloned")
        return list(webmap_ids)

    @staticmethod
    def _get_webmap_ids_v24(data):
        """
        Parses a dashboard at version 24 to find data webmap ids
        :param data: The json/dict to parse
        :return: A list of webmap ids
        """
        webmap_ids = set()
        if 'widgets' in data:
            for widget in data['widgets']:
                if widget['type'] == 'mapWidget':
                    if 'itemId' in widget:
                        webmap_ids.add(widget['itemId'])
        return list(webmap_ids)

    @staticmethod
    def get_layer_ids(data):
        """
        Parses a dashboard based on version to return the list of layer ids
        :param data: The json/dict to parse
        :return: A list of layer ids
        """
        if 'version' in data:
            if data['version'] == 24:
                layer_ids = _DashboardDefinition._get_layer_ids_v24(data)
            else:
                raise _ItemCreateException("Dashboard version {} is not supported".format(data['version']))
        else:
            raise _ItemCreateException("Dashboard is not versioned and cannot be cloned")
        return list(layer_ids)

    @staticmethod
    def _get_layer_ids_v24(data):
        """
        Parses a dashboard at version 24 to find layer/service ids
        :param data: The json/dict to parse
        :return: A list of layer ids
        """
        layer_ids = set()
        if "widgets" in data:
            for widget in data["widgets"]:
                if "datasets" in widget:
                    layer_ids = layer_ids.union(_DashboardDefinition.
                                                _parse_datasets_v24(widget["datasets"]), layer_ids)

        if "headerPanel" in data and "selectors" in data["headerPanel"]:
            for selector in data["headerPanel"]["selectors"]:
                if "datasets" in selector:
                    layer_ids = layer_ids.union(_DashboardDefinition.
                                                _parse_datasets_v24(selector["datasets"]), layer_ids)

        if "leftPanel" in data and "selectors" in data["leftPanel"]:
            for selector in data["leftPanel"]["selectors"]:
                if "datasets" in selector:
                    layer_ids = layer_ids.union(_DashboardDefinition.
                                                _parse_datasets_v24(selector["datasets"]), layer_ids)
        return layer_ids

    @staticmethod
    def _parse_datasets_v24(datasets):
        """
        Parses a data set in a version 24 dashboard
        :param datasets: the list of datasets
        :return: A set of layer ids
        """
        layer_ids = set()
        for dataset in datasets:
            # newer schema
            if "dataSource" in dataset:
                ds = dataset["dataSource"]
                # newer property
                if "itemId" in ds:
                    layer_ids.add(ds['itemId'])
        return layer_ids


class _ApplicationDefinition(_TextItemDefinition):
    """
    Represents the definition of an application within ArcGIS Online or Portal.
    """

    def __init__(self, target, clone_mapping, info, source_app_title=None, update_url=True, data=None, sharing=None, thumbnail=None, portal_item=None, item_extent=None, folder=None, search_existing=True):
        super().__init__(target, clone_mapping, info, data, sharing, thumbnail, portal_item, folder, item_extent, search_existing)
        self._source_app_title = source_app_title
        self._update_url = update_url


    @property
    def source_app_title(self):
        """Gets the title of the application"""
        return self._source_app_title

    @property
    def update_url(self):
        """Gets a value indicating if the application url should be updated"""
        return self._update_url

    def clone(self):
        """Clone the application in the target organization.
        """

        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:
                org_url = _get_org_url(self.target)
                is_web_appbuilder = False

                # Get the item properties from the original application which will be applied when the new item is created
                item_properties = self._get_item_properties(self.item_extent)

                # Swizzle the item ids of the web maps, groups and URLs of defined in the application's data
                app_json = self.data
                if app_json is not None:
                    app_json_text = ''

                    # If item is a story map don't swizzle any of the json references
                    if 'Story Map' in original_item['typeKeywords'] or 'Story Maps' in original_item['typeKeywords']:
                        app_json_text = json.dumps(app_json)

                    else:
                        if "Web AppBuilder" in original_item['typeKeywords']: #Web AppBuilder
                            is_web_appbuilder = True
                            if 'portalUrl' in app_json:
                                app_json['portalUrl'] = org_url
                            if 'map' in app_json:
                                if 'portalUrl' in app_json['map']:
                                    app_json['map']['portalUrl'] = org_url
                                if 'itemId' in app_json['map']:
                                    app_json['map']['itemId'] = self._clone_mapping['Item IDs'][app_json['map']['itemId']]
                                if 'mapOptions' in app_json['map'] and app_json['map']['mapOptions'] is not None:
                                    if 'extent' in app_json['map']['mapOptions']:
                                        del app_json['map']['mapOptions']['extent']
                            if 'httpProxy' in app_json:
                                if 'url' in app_json['httpProxy']:
                                    app_json['httpProxy']['url'] = org_url + "sharing/proxy"
                            if 'geometryService' in app_json and 'geometry' in self.target.properties['helperServices']:
                                app_json['geometryService'] = self.target.properties['helperServices']['geometry']['url']

                        else: #Configurable Application Template
                            if 'folderId' in app_json:
                                user = self.target.users.me
                                if self.folder is not None:
                                    folders = user.folders
                                    target_folder = next((f for f in folders if f['title'].lower() == self.folder.lower()), None)
                                    if target_folder:
                                        app_json['folderId'] = _deep_get(target_folder, 'id')
                                else:
                                    app_json['folderId'] = None

                            if 'values' in app_json:
                                if 'group' in app_json['values']:
                                    app_json['values']['group'] = self._clone_mapping['Group IDs'][app_json['values']['group']]
                                if 'webmap' in app_json['values']:
                                    if isinstance(app_json['values']['webmap'], list):
                                        new_webmap_ids = []
                                        for webmap_id in app_json['values']['webmap']:
                                            new_webmap_ids.append(self._clone_mapping['Item IDs'][webmap_id])
                                        app_json['values']['webmap'] = new_webmap_ids
                                    else:
                                        app_json['values']['webmap'] = self._clone_mapping['Item IDs'][app_json['values']['webmap']]
                            if self.source_app_title is not None:
                                search_query = 'title:"{0}" AND owner:{1} AND type:Web Mapping Application'.format(self.source_app_title, "esri_en")
                                search_items = self.target.content.search(search_query, max_items=100, outside_org=True)
                                if len(search_items) > 0:
                                    existing_item = max(search_items, key=lambda x: x['created'])
                                    app_json['source'] = existing_item['id']

                        app_json_text = json.dumps(app_json)
                        for original_url in self._clone_mapping['Services']:
                            service = self._clone_mapping['Services'][original_url]
                            for key, value in service['layer_id_mapping'].items():
                                app_json_text = re.sub("{0}/{1}".format(original_url, key),
                                                       "{0}/{1}".format(service['url'], value),
                                                       app_json_text, 0, re.IGNORECASE)
                            app_json_text = re.sub(original_url, service['url'], app_json_text, 0, re.IGNORECASE)
                        for original_id in self._clone_mapping['Item IDs']:
                            app_json_text = re.sub(original_id, self._clone_mapping['Item IDs'][original_id], app_json_text, 0, re.IGNORECASE)

                        # Replace any references to default print service
                        new_print_url = _deep_get(self.target.properties, 'helperServices', 'printTask', 'url')
                        if new_print_url is not None:
                            old_print_url = 'https://utility.arcgisonline.com/arcgis/rest/services/Utilities/PrintingTools/GPServer/Export%20Web%20Map%20Task'
                            if self.portal_item is not None and _deep_get(self.portal_item._gis.properties, 'helperServices', 'printTask', 'url') is not None:
                                old_print_url = _deep_get(self.portal_item._gis.properties, 'helperServices', 'printTask', 'url')

                            app_json_text = re.sub(old_print_url, new_print_url, app_json_text, 0, re.IGNORECASE)
                            if old_print_url.startswith('https://'):
                                app_json_text = re.sub('http://' + old_print_url[8:], new_print_url, app_json_text, 0, re.IGNORECASE)
                            elif old_print_url.startswith('http://'):
                                app_json_text = re.sub('https://' + old_print_url[7:], new_print_url, app_json_text, 0, re.IGNORECASE)

                        # Perform a general find and replace of field names if field mapping is required
                        for service in self._clone_mapping['Services']:
                            for layer_id in self._clone_mapping['Services'][service]['layer_field_mapping']:
                                field_mapping = self._clone_mapping['Services'][service]['layer_field_mapping'][layer_id]
                                app_json_text = _find_and_replace_fields(app_json_text, field_mapping)

                    # Replace any references to the original org url with the target org url. Used to re-point item resource references
                    if original_item['url'] is not None:
                        url = original_item['url']
                        find_string = "/apps/"
                        index = url.find(find_string)
                        if index != -1:
                            source_org_url = url[:index+1]
                            app_json_text = re.sub(source_org_url, org_url, app_json_text, 0, re.IGNORECASE)

                    item_properties['text'] = app_json_text

                # Add the application to the target portal
                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)
                new_item = self.target.content.add(item_properties=item_properties, thumbnail=thumbnail, folder=self.folder)
                self.created_items.append(new_item)

                # Add the resources to the new item
                if self.portal_item:
                    resources = self.portal_item.resources
                    resource_list = resources.list()
                    if len(resource_list) > 0:
                        resources_dir = os.path.join(self._temp_dir.name, original_item['id'], 'resources')
                        if not os.path.exists(resources_dir):
                            os.makedirs(resources_dir)
                        for resource in resource_list:
                            resource_path = resources.get(resource['resource'], False, resources_dir)
                            folder_name = None
                            resource_name = resource['resource']
                            if len(resource_name.split('/')) == 2:
                                folder_name, resource_name = resource_name.split('/')
                            new_item.resources.add(resource_path, folder_name, resource_name)

                # Update the url of the item to point to the new portal and new id of the application if required
                if original_item['url'] is not None:
                    url = original_item['url']
                    if self.update_url:
                        find_string = "/apps/"
                        index = original_item['url'].find(find_string)
                        url = '{0}{1}'.format(org_url.rstrip('/'), original_item['url'][index:])
                        find_string = "id="
                        index = url.find(find_string)
                        url = '{0}{1}'.format(url[:index + len(find_string)], new_item.id)
                    item_properties = {'url' : url}
                    new_item.update(item_properties)

                # Add a code attachment if the application is Web AppBuilder so that it can be downloaded
                if is_web_appbuilder:
                    url = '{0}sharing/rest/content/items/{1}/package'.format(org_url[org_url.find('://') + 1:], new_item['id'])
                    code_attachment_properties = {'title' : new_item['title'], 'type' : 'Code Attachment', 'typeKeywords' : 'Code,Web Mapping Application,Javascript',
                                                    'relationshipType' : 'WMA2Code', 'originItemId' : new_item['id'], 'url' : url }
                    code_attachment = self.target.content.add(item_properties=code_attachment_properties, folder=self.folder)
                    self.created_items.append(code_attachment)
                    _share_item_with_groups(code_attachment, self.sharing, self._clone_mapping["Group IDs"])

                # With Portal sometimes after sharing the application the url is reset.
                # Check if the url is incorrect after sharing and set back to correct url.
                if 'url' in new_item and new_item['url'] is not None:
                    url = new_item['url']
                    new_item = self.target.content.get(new_item['id'])
                    if new_item['url'] != url:
                        new_item.update({'url': url})

            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved=True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item
        except Exception as ex:
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)


class _FormDefinition(_ItemDefinition):
    """
    Represents the definition of an form within ArcGIS Online or Portal.
    """
    def __init__(self, target, clone_mapping, info, related_items, data=None, sharing=None, thumbnail=None, portal_item=None, folder=None, item_extent=None, search_existing=True):
        super().__init__(target, clone_mapping, info, data, sharing, thumbnail, portal_item, folder, item_extent, search_existing)
        self._related_items = related_items


    @property
    def related_items(self):
        """Gets the related items for the survey"""
        return self._related_items

    def clone(self):
        """Clone the form in the target organization.
        """
        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:

                # Get the item properties from the original item to be applied when the new item is created
                item_properties = self._get_item_properties(self.item_extent)

                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)

                # Add the new item
                new_item = self.target.content.add(item_properties=item_properties, data=None, thumbnail=thumbnail, folder=self.folder)
                self.created_items.append(new_item)

                # Update Survey123 form data
                original_item = self.info
                self.update_form(self.target, new_item, self._clone_mapping)
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved = True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item

        except Exception as ex:
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)

    def update_form(self, target, new_item, clone_mapping):
        """Update the form with form zip data in the target organization.
        Keyword arguments:
        target - The instance of arcgis.gis.GIS (the portal) to update the item
        new_item - The form item to update
        clone_mapping - Dictionary containing mapping between new and old items.
        """

        original_item = self.info
        temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        form_zip = self.portal_item.download(temp_dir)
        zip_file = zipfile.ZipFile(form_zip)

        try:
            # Extract the zip archive to a sub folder
            new_dir = os.path.join(temp_dir, 'extract')
            zip_dir = os.path.join(new_dir, 'esriinfo')

            zip_file.extractall(new_dir)
            zip_file.close()

            feature_service_url = None
            form_json = None

            # Loop through the files and update references to the feature service and item id
            for path in os.listdir(zip_dir):
                if os.path.splitext(path)[1].lower() == '.info':
                    with open(os.path.join(zip_dir, path), 'r') as file:
                        data = json.loads(file.read())

                    original_url = data['serviceInfo']['url']
                    for key, value in clone_mapping['Services'].items():
                        if _compare_url(original_url, key):
                            data['serviceInfo']['itemId'] = value['id']
                            data['serviceInfo']['url'] = value['url']
                            feature_service_url = value['url']
                            break

                    with open(os.path.join(zip_dir, path), 'w') as file:
                        file.write(json.dumps(data))

                elif os.path.splitext(path)[1].lower() == '.xml' or path.lower() == 'webform.json':
                    with open(os.path.join(zip_dir, path), 'r') as file:
                        data = file.read()

                    data = data.replace(original_item['id'], new_item['id'])
                    for key, value in clone_mapping['Services'].items():
                        data = re.sub(key, value['url'], data, 0, re.IGNORECASE)

                    with open(os.path.join(zip_dir, path), 'w') as file:
                        file.write(data)

                elif os.path.splitext(path)[1].lower() == '.iteminfo':
                    with open(os.path.join(zip_dir, path), 'w') as file:
                        file.write(json.dumps(dict(new_item)))

                elif path.lower() == 'form.json':
                    with open(os.path.join(zip_dir, path), 'r') as file:
                        form_json = file.read()

                elif os.path.splitext(path)[1].lower() == '.xlsx':
                    xlsx = zipfile.ZipFile(os.path.join(zip_dir, path))
                    xlsx_dir = os.path.join(zip_dir, 'xlsx')
                    try:
                        xlsx.extractall(xlsx_dir)
                        xlsx.close()

                        with open(os.path.join(xlsx_dir, 'xl/sharedStrings.xml'), 'r') as file:
                            data = file.read()

                        for key, value in clone_mapping['Services'].items():
                            data = re.sub(key, value['url'], data, 0, re.IGNORECASE)

                        with open(os.path.join(xlsx_dir, 'xl/sharedStrings.xml'), 'w') as file:
                            file.write(data)

                        xlsx = zipfile.ZipFile(os.path.join(zip_dir, path), 'w', zipfile.ZIP_DEFLATED)
                        _zip_dir(xlsx_dir, xlsx, False)
                    except Exception:
                        continue
                    finally:
                        xlsx.close()
                        if os.path.exists(xlsx_dir):
                            shutil.rmtree(xlsx_dir)

            # Add a relationship between the new survey and the service
            for related_item in self.related_items:
                for key, value in clone_mapping['Services'].items():
                    if _compare_url(related_item['url'], key):
                        feature_service = target.content.get(value['id'])
                        new_item.add_relationship(feature_service, 'Survey2Service')
                        break

            # If the survey was authored on the web add the web_json to the metadata table in the service
            if form_json is not None and feature_service_url is not None:
                svc = FeatureLayerCollection(feature_service_url, target)
                table = next((t for t in svc.tables if t.properties.name == 'metadata'), None)
                if table is not None:
                    deletes = table.query(where="name = 'form'")
                    table.edit_features(adds=[{'attributes' : {'name' : 'form', 'value' : form_json}}], deletes=deletes)

            # Zip the directory
            zip_file = zipfile.ZipFile(form_zip, 'w', zipfile.ZIP_DEFLATED)
            _zip_dir(zip_dir, zip_file)
            zip_file.close()

            # Upload the zip to the item
            new_item.update(data=form_zip)
        except Exception as ex:
            raise Exception("Failed to update {0} {1}: {2}".format(new_item['type'], new_item['title'], str(ex)))
        finally:
            zip_file.close()


class _WorkforceProjectDefinition(_TextItemDefinition):
    """
    Represents the definition of an workforce project within ArcGIS Online or Portal.
    """

    def clone(self):
        """Clone the form in the target organization.
        """

        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:

                # Get the item properties from the original application which will be applied when the new item is created
                item_properties = self._get_item_properties(self.item_extent)
                workforce_json = self.data

                # Update the webmap references
                webmaps = ['workerWebMapId', 'dispatcherWebMapId']
                for webmap in webmaps:
                    original_id = _deep_get(workforce_json, webmap)
                    if original_id is not None and original_id in self._clone_mapping['Item IDs']:
                        workforce_json[webmap] = self._clone_mapping['Item IDs'][original_id]

                # Update the service references
                services = ['dispatchers', 'assignments', 'workers', 'tracks']
                for service in services:
                    service_definiton = _deep_get(workforce_json, service)
                    if service_definiton is not None:
                        layer_url = _deep_get(service_definiton, 'url')
                        feature_service_url = os.path.dirname(layer_url)
                        for key, value in self._clone_mapping['Services'].items():
                            if _compare_url(feature_service_url, key):
                                layer_id = int(os.path.basename(layer_url))
                                new_id = value['layer_id_mapping'][layer_id]
                                service_definiton['url'] = "{0}/{1}".format(value['url'], new_id)
                                service_definiton['serviceItemId'] = value['id']

                                if service == 'dispatchers':
                                    feature_layer = FeatureLayer(service_definiton['url'], self.target)
                                    user = self.target.users.me
                                    features = feature_layer.query("userId = '{0}'".format(user.username)).features
                                    if len(features) == 0:
                                        features = [{"attributes" : {"name" : user.fullName, "userId" : user.username}}]
                                        feature_layer.edit_features(adds=features)
                                break

                # Update the group reference
                group_id = _deep_get(workforce_json, 'groupId')
                workforce_json['groupId'] = self._clone_mapping['Group IDs'][group_id]

                # Update the folder reference
                if 'folderId' in workforce_json:
                    user = self.target.users.me
                    if self.folder is not None:
                        folders = user.folders
                        target_folder = next((f for f in folders if f['title'].lower() == self.folder.lower()), None)
                        if target_folder:
                            workforce_json['folderId'] = _deep_get(target_folder, 'id')
                    else:
                        workforce_json['folderId'] = None

                # Update the application integration references
                integrations = _deep_get(workforce_json, 'assignmentIntegrations')
                if integrations is not None:
                    for integration in integrations:
                        url_template = _deep_get(integration, 'urlTemplate')
                        if url_template is not None:
                            item_references = re.findall('itemID=[0-9A-F]{32}', url_template, re.IGNORECASE)
                            for item_reference in item_references:
                                item_id = item_reference[7:]
                                if item_id in self._clone_mapping['Item IDs']:
                                    integration['urlTemplate'] = url_template.replace(item_id, self._clone_mapping['Item IDs'][item_id])

                # Add the project to the target portal
                item_properties['text'] = json.dumps(workforce_json)
                thumbnail = self.thumbnail
                if not thumbnail and self.portal_item:
                    temp_dir = os.path.join(self._temp_dir.name, original_item['id'])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    thumbnail = self.portal_item.download_thumbnail(temp_dir)
                new_item = self.target.content.add(item_properties=item_properties, thumbnail=thumbnail, folder=self.folder)
                self.created_items.append(new_item)
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved=True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item
        except Exception as ex:
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)


class _ProMapDefinition(_ItemDefinition):
    """
    Represents the definition of an pro map within ArcGIS Online or Portal.
    """

    def clone(self):
        """Clone the pro map in the target organization.
        """

        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:
                mapx = self.data

                map_json = None
                with open(mapx, 'r') as file:
                    map_json = json.loads(file.read())

                data_connections = []
                layer_definitions = _deep_get(map_json, 'layerDefinitions')
                if layer_definitions is not None:
                    for layer_definition in layer_definitions:
                        data_connection = _deep_get(layer_definition, 'featureTable', 'dataConnection')
                        if data_connection is not None:
                            data_connections.append(data_connection)

                table_definitions = _deep_get(map_json, 'tableDefinitions')
                if table_definitions is not None:
                    for table_definition in table_definitions:
                        data_connection = _deep_get(table_definition, 'dataConnection')
                        if data_connection is not None:
                            data_connections.append(data_connection)

                for data_connection in data_connections:
                    if 'workspaceFactory' in data_connection and data_connection['workspaceFactory'] == 'FeatureService':
                        if 'workspaceConnectionString' in data_connection and data_connection['workspaceConnectionString'] is not None:
                            feature_service_url = data_connection['workspaceConnectionString'][4:]
                            for original_url in self._clone_mapping['Services']:
                                if _compare_url(feature_service_url, original_url):
                                    new_service = self._clone_mapping['Services'][original_url]
                                    layer_id = int(data_connection['dataset'])
                                    new_id = new_service['layer_id_mapping'][layer_id]
                                    data_connection['workspaceConnectionString'] = "URL={0}".format(new_service['url'])
                                    data_connection['dataset'] = new_id

                new_mapx_dir = os.path.join(os.path.dirname(mapx), 'new_mapx')
                os.makedirs(new_mapx_dir)
                new_mapx = os.path.join(new_mapx_dir, os.path.basename(mapx))
                with open(new_mapx, 'w') as file:
                    file.write(json.dumps(map_json))
                self._data = new_mapx

                new_item = super().clone()
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved = True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item

        except Exception as ex:
            if isinstance(ex, _ItemCreateException):
                raise
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)
        finally:
            self._data = mapx
            new_mapx_dir = os.path.join(os.path.dirname(mapx), 'new_mapx')
            if os.path.exists(new_mapx_dir):
                shutil.rmtree(new_mapx_dir)


class _ProProjectPackageDefinition(_ItemDefinition):
    """
    Represents the definition of an pro map within ArcGIS Online or Portal.
    """

    def clone(self):
        """Clone the pro map in the target organization.
        """

        try:
            new_item = None
            original_item = self.info
            if self._search_existing:
                new_item = _search_org_for_existing_item(self.target, self.portal_item)
            if not new_item:
                aprx = None
                map = None
                maps = None
                layers = None
                lyr = None
                ppkx = self.data

                try:
                    import arcpy

                    extract_dir = os.path.join(os.path.dirname(ppkx), 'extract')
                    if not os.path.exists(extract_dir):
                        os.makedirs(extract_dir)
                        arcpy.ExtractPackage_management(ppkx, extract_dir)

                    # 1.x versions of Pro use a different folder name
                    project_folder = 'p20'
                    version = arcpy.GetInstallInfo()['Version']
                    if version.startswith('1'):
                        project_folder = 'p12'

                    project_dir = os.path.join(extract_dir, project_folder)
                    if os.path.exists(project_dir):
                        aprx_files = [f for f in os.listdir(project_dir) if f.endswith('.aprx')]
                        if len(aprx_files) == 1:
                            service_version_infos = {}

                            aprx_file = os.path.join(project_dir, aprx_files[0])
                            aprx = arcpy.mp.ArcGISProject(aprx_file)
                            maps = aprx.listMaps()
                            for map in maps:
                                layers = [l for l in map.listLayers() if l.supports('connectionProperties')]
                                layers.extend(map.listTables())
                                for lyr in layers:
                                    connection_properties = lyr.connectionProperties
                                    workspace_factory = _deep_get(connection_properties, 'workspace_factory')
                                    service_url = _deep_get(connection_properties, 'connection_info', 'url')
                                    if workspace_factory == 'FeatureService' and service_url is not None:
                                        for original_url in self._clone_mapping['Services']:
                                            if _compare_url(service_url, original_url):
                                                new_service = self._clone_mapping['Services'][original_url]
                                                layer_id = int(connection_properties['dataset'])
                                                new_id = new_service['layer_id_mapping'][layer_id]
                                                new_connection_properties = copy.deepcopy(connection_properties)
                                                new_connection_properties['connection_info']['url'] = new_service['url']
                                                new_connection_properties['dataset'] = str(new_id)

                                                if new_service['url'] not in service_version_infos:
                                                    try:
                                                        service_version_infos[new_service['url']] = _get_version_management_server(self.target, new_service['url'])
                                                    except:
                                                        service_version_infos[new_service['url']] = {}
                                                version_info = service_version_infos[new_service['url']]
                                                for key, value in {'defaultVersionName' : 'version', 'defaultVersionGuid': 'versionguid'}.items():
                                                    if key in version_info:
                                                        new_connection_properties['connection_info'][value] = version_info[key]
                                                    elif value in new_connection_properties['connection_info']:
                                                        del new_connection_properties['connection_info'][value]

                                                lyr.updateConnectionProperties(connection_properties, new_connection_properties, validate=False)
                            aprx.save()

                            additional_files = None
                            user_data = os.path.join(os.path.dirname(ppkx), 'extract', 'commondata', 'userdata')
                            if os.path.exists(user_data):
                                additional_files = [os.path.join(user_data, f) for f in os.listdir(user_data)]

                            new_package_dir = os.path.join(os.path.dirname(ppkx), 'new_package')
                            os.makedirs(new_package_dir)
                            new_package = os.path.join(new_package_dir, os.path.basename(ppkx))
                            item_properties = self._get_item_properties(self.item_extent)
                            description = original_item['title']
                            if item_properties['snippet'] is not None:
                                description = item_properties['snippet']

                            arcpy.management.PackageProject(aprx_file, new_package, "INTERNAL", "PROJECT_PACKAGE", "DEFAULT", "ALL", additional_files, description, item_properties['tags'], "ALL")
                            self._data = new_package

                except ImportError:
                    pass

                new_item = super().clone()
            _share_item_with_groups(new_item, self.sharing, self._clone_mapping["Group IDs"])
            self.resolved=True
            self._clone_mapping['Item IDs'][original_item['id']] = new_item['id']
            return new_item

        except Exception as ex:
            if isinstance(ex, _ItemCreateException):
                raise
            raise _ItemCreateException("Failed to create {0} {1}: {2}".format(original_item['type'], original_item['title'], str(ex)), new_item)
        finally:
            del aprx, map, maps, layers, lyr
            self._data = ppkx
            extract_dir = os.path.join(os.path.dirname(ppkx), 'extract')
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            new_package_dir = os.path.join(os.path.dirname(ppkx), 'new_package')
            if os.path.exists(new_package_dir):
                shutil.rmtree(new_package_dir)


class _ItemCreateException(Exception):
    """
    Exception raised during the creation of new items, used to clean-up any partially created items in the process.
    """
    pass

#endregion

#region Private API Functions


def _get_feature_service_related_item(service_url, source):
    try:
        service = FeatureLayerCollection(service_url, source)
    except Exception:
        return

    if 'serviceItemId' in service.properties and service.properties['serviceItemId']:
        item_id = service.properties['serviceItemId']
        return source.content.get(item_id)
    return


def _compare_service(new_item, original_item):
    layer_field_mapping = {}
    layer_id_mapping = {}
    relationship_field_mapping = {}

    new_service = None
    if new_item['type'] == 'Feature Service':
        new_service = FeatureLayerCollection.fromitem(new_item)
    elif new_item['type'] == 'Map Service':
        new_service = MapImageLayer.fromitem(new_item)
    new_layers = [l.properties for l in new_service.layers + new_service.tables]

    original_layers = None
    if isinstance(original_item, gis.Item):
        if original_item['type'] == 'Feature Service':
            original_service = FeatureLayerCollection.fromitem(original_item)
        elif original_item['type'] == 'Map Service':
            original_service = MapImageLayer.fromitem(original_item)
        original_layers = [l.properties for l in original_service.layers + original_service.tables]
    else:
        layers_definition = original_item.layers_definition
        original_layers = layers_definition['layers'] + layers_definition['tables']

    if len(new_layers) < len(original_layers):
        raise Exception('{0} {1} layers and tables must match the source {2} {3}'.format(new_item['type'], new_item['title'], original_item['type'], original_item['title']))

    # Get a mapping between layer ids, fields and related fields
    original_layer_ids = [original_layer['id'] for original_layer in original_layers]
    new_layer_ids = [new_layer['id'] for new_layer in new_layers]
    new_layer_names = [new_layer['name'] for new_layer in new_layers]
    for layer in original_layers:
        try:
            new_layer = new_layers[new_layer_names.index(layer['name'])]
            layer_id_mapping[layer['id']] = new_layer['id']
            new_layer_ids.remove(new_layer['id'])
            original_layer_ids.remove(layer['id'])
        except ValueError:
            pass
    for id in original_layer_ids:
        layer_id_mapping[id] = new_layer_ids.pop(0)

    for original_id, new_id in layer_id_mapping.items():
        field_mapping = {}
        for layer in original_layers:
            if layer['id'] == original_id:
                new_layer = next((l for l in new_layers if l['id'] == new_id), None)
                original_fields = _deep_get(layer, 'fields')
                new_fields = _deep_get(new_layer, 'fields')
                if new_fields is None or original_fields is None:
                    break
                new_fields_lower = [f['name'].lower() for f in new_fields]

                if 'editFieldsInfo' in layer and layer['editFieldsInfo'] is not None:
                    if 'editFieldsInfo' in new_layer and new_layer['editFieldsInfo'] is not None:
                        for editor_field in ['creationDateField', 'creatorField', 'editDateField', 'editorField']:
                            original_editor_field_name = _deep_get(layer, 'editFieldsInfo', editor_field)
                            new_editor_field_name = _deep_get(new_layer, 'editFieldsInfo', editor_field)
                            if original_editor_field_name !=  new_editor_field_name:
                                if original_editor_field_name is not None and original_editor_field_name != "" and new_editor_field_name is not None and new_editor_field_name != "":
                                    field_mapping[original_editor_field_name] = new_editor_field_name

                original_oid_field = _deep_get(layer, 'objectIdField')
                new_oid_field = _deep_get(new_layer, 'objectIdField')
                if original_oid_field != new_oid_field:
                    if original_oid_field is not None and original_oid_field != "" and new_oid_field is not None and new_oid_field != "":
                        field_mapping[original_oid_field] = new_oid_field

                original_globalid_field = _deep_get(layer, 'globalIdField')
                new_globalid_field = _deep_get(new_layer, 'globalIdField')
                if original_globalid_field != new_globalid_field:
                    if original_globalid_field is not None and original_globalid_field != "" and new_globalid_field is not None and new_globalid_field != "":
                        field_mapping[original_globalid_field] = new_globalid_field

                for field in original_fields:
                    if field['name'] in field_mapping:
                        continue
                    try:
                        new_field = new_fields[new_fields_lower.index(field['name'].lower())]
                        if field['name'] != new_field['name']:
                            field_mapping[field['name']] = new_field['name']
                    except ValueError:
                        pass
                break
        if len(field_mapping) > 0:
            layer_field_mapping[original_id] = field_mapping

    for layer in original_layers:
        layer_id = layer['id']
        if 'relationships' in layer and layer['relationships'] is not None:
            for relationship in layer['relationships']:
                related_table_id = relationship['relatedTableId']
                if related_table_id in layer_field_mapping:
                    if layer_id not in relationship_field_mapping:
                        relationship_field_mapping[layer_id] = {}
                    field_mapping = layer_field_mapping[related_table_id]
                    relationship_field_mapping[layer_id][relationship['id']] = field_mapping

    return [layer_field_mapping, layer_id_mapping, relationship_field_mapping]


def _search_org_for_existing_item(target, item):
    """Search for an item with a specific type keyword or tag.
    This is used to determine if the item has already been cloned in the folder.
    Keyword arguments:
    target - The portal that items will be cloned to.
    item - The original item used to determine if it has already been cloned to the specified folder."""

    search_query = 'typekeywords:source-{0} type:{1}'.format(item['id'], item['type'])
    items = target.content.search(search_query, max_items=100, outside_org=False)
    search_query = 'tags:source-{0} type:{1}'.format(item['id'], item['type'])
    items.extend(target.content.search(search_query, max_items=100, outside_org=False))
    existing_item = None
    if len(items) > 0:
        existing_item = max(items, key=lambda x: x['created'])
    return existing_item


def _search_for_existing_group(user, group):
    """Test if a group with a given source tag that the user is a member of already exists in the organization.
    This is used to determine if the group has already been created and if new maps and apps that belong to the same group should be shared to the same group.
    Keyword arguments:
    user - The gis.User to search through their group membership.
    group - The original group used to determine if it has already been cloned in the organization."""

    existing_group = None
    if 'groups' in user and user['groups'] is not None:
        groups = [g for g in user['groups'] if "source-{0}".format(group['id']) in g['tags']]
        if len(groups) > 0:
            existing_group = max(groups, key=lambda x: x['created'])
    return existing_group


def _share_item_with_groups(item, sharing, group_mapping):
    """Share the new item using the sharing properties of original item and group mapping.
    Keyword arguments:
    item - The item to share
    sharing - the sharing properties of the original item
    group_mapping - A dictionary containing the id of the original group and the id of the new group"""

    if sharing:
        groups = []
        for group in sharing['groups']:
            if group in group_mapping:
                groups.append(group_mapping[group])
        if len(groups) == 0:
            return

        everyone = False
        org = False
        if 'access' in item and item['access'] is not None:
            everyone = item['access'] == 'public'
            org = item['access'] == 'org'
        item.share(everyone, org, ','.join(groups))


def _wgs84_envelope(envelope):
    """Return the envelope in WGS84."""
    spatial_reference = SpatialReference({'wkid': 4326})
    new_envelope = project([envelope], in_sr=envelope['spatialReference'], out_sr=spatial_reference)[0]
    new_envelope.spatial_reference = spatial_reference
    return new_envelope


def _add_to_definition(feature_layer_manager, definition):
    """Create a new service.
    Keyword arguments:
    feature_layer_manager - The instance of FeatureLayerManager of the service to edit
    definition - The definition as a string to add to the service"""

    params = {
        "f": "json",
        "addToDefinition": definition,
    }
    u_url = feature_layer_manager._url + "/addToDefinition"

    res = feature_layer_manager._con.post(u_url, params)
    feature_layer_manager.refresh()
    return res


def _get_version_management_server(target, feature_service):
    """Gets the url of the portal/org
    Keyword arguments:
    target - The portal/org to get the url for.
    feature_service - The url to the feature_service in the portal to retrieve the Version Manager info."""

    postdata = {'f' : 'json'}
    path = os.path.dirname(feature_service)
    path += '/VersionManagementServer'
    return target._portal.con.post(path, postdata)


def _get_org_url(target):
    """Gets the url of the portal/org
    Keyword arguments:
    target - The portal/org to get the url for."""

    org_url = target._portal.url
    properties = target.properties

    scheme = 'http'
    if 'allSSL' in properties and properties['allSSL']:
        scheme = 'https'
    if 'urlKey' in properties and 'customBaseUrl' in properties:
        org_url = "{0}://{1}.{2}/".format(scheme, properties['urlKey'], properties['customBaseUrl'])
    else:
        url = urlparse(org_url)
        org_url = org_url.replace(url.scheme, scheme)
    return org_url


def _compare_url(url1, url2):
    """Compare two URLs ignoring scheme
    Keyword arguments:
    url1 - The first url
    url2 - The second url"""

    url_parse1 = urlparse(url1)
    url_parse2 = urlparse(url2)
    return "{0}{1}".format(url_parse1.netloc.lower(), url_parse1.path.lower()) == "{0}{1}".format(url_parse2.netloc.lower(), url_parse2.path.lower())


def _find_and_replace_fields(text, field_mapping):
    """Perform a find and replace for field names in a json definition.
    Keyword arguments:
    text - The json to search and replace fields names
    field_mapping -  A dictionary containing the pairs of original field names and new field names"""

    for field in field_mapping:
        replace = field_mapping[field]

        results = set(re.findall('([{{("\[ ])({0})([}})"\] ])'.format(field), text))
        start = re.findall('(^{0})([}})"\] ])'.format(field), text)
        end = re.findall('([{{("\[ ])({0}$)'.format(field), text)
        for element in results:
            text = text.replace(''.join(element), ''.join([element[0], replace, element[2]]))

        if len(start) > 0:
            new_start = ''.join([replace, start[0][1]])
            text = new_start + text[len(new_start):]

        if len(end) > 0:
            new_end = ''.join([end[0][0], replace])
            text = text[:len(text) - len(new_end) + 1] + new_end
    return text


def _find_and_replace_fields_arcade(text, field_mapping):
    """Perform a find and replace for field names in an arcade expression.
    Keyword arguments:
    text - The arcade expression to search and replace fields names
    field_mapping -  A dictionary containing the pairs of original field names and new field names"""

    for field in field_mapping:
        replace = field_mapping[field]
        text = text.replace('$feature.{0}'.format(field), '$feature.{0}'.format(replace))
        text = text.replace('$feature["{0}"]'.format(field), '$feature["{0}"]'.format(replace))
    return text


def _update_feature_attributes(feature, field_mapping):
    """Perform a find and replace for field names in a feature attribute definition.
    Keyword arguments:
    feature - The feature to search and replace fields names
    field_mapping -  A dictionary containing the pairs of original field names and new field names"""

    if 'attributes' in feature and feature['attributes'] is not None:
        for attribute in [att for att in feature['attributes']]:
            if attribute in field_mapping:
                if field_mapping[attribute] in feature['attributes']:
                    continue
                feature['attributes'][field_mapping[attribute]] = feature['attributes'][attribute]
                del feature['attributes'][attribute]


def _update_layer_fields(layer, field_mapping):
    """Perform a find and replace for field names in a layer definition.
    Keyword arguments:
    layer - The layer to search and replace fields names
    field_mapping -  A dictionary containing the pairs of original field names and new field names"""

    if 'layerDefinition' in layer and layer['layerDefinition'] is not None:
        layer_definition = layer['layerDefinition']

        if 'definitionExpression' in layer_definition and layer_definition['definitionExpression'] is not None:
            layer_definition['definitionExpression'] = _find_and_replace_fields(layer_definition['definitionExpression'], field_mapping)

        if 'drawingInfo' in layer_definition and layer_definition['drawingInfo'] is not None:
            if 'renderer' in layer_definition['drawingInfo'] and layer_definition['drawingInfo']['renderer'] is not None:
                renderer = layer_definition['drawingInfo']['renderer']
                if renderer['type'] == 'uniqueValue':
                    i = 0
                    while 'field{0}'.format(i) in renderer:
                        if renderer['field{0}'.format(i)] in field_mapping:
                            renderer['field{0}'.format(i)] = field_mapping[renderer['field{0}'.format(i)]]
                        i += 1
                elif renderer['type'] == 'classBreaks':
                    if 'field' in renderer:
                        if renderer['field'] in field_mapping:
                            renderer['field'] = field_mapping[renderer['field']]

                value_expression = _deep_get(renderer, "valueExpression")
                if value_expression is not None:
                    renderer['valueExpression'] = _find_and_replace_fields_arcade(str(value_expression), field_mapping)

            labeling_infos = _deep_get(layer_definition['drawingInfo'], 'labelingInfo')
            if labeling_infos is not None:
                for label_info in labeling_infos:
                    label_expression = _deep_get(label_info, 'labelExpression')
                    if label_expression is not None:
                        results = re.findall("\[(.*?)\]", label_expression)
                        for result in results:
                            if result in field_mapping:
                                label_info['labelExpression'] = str(label_expression).replace("[{0}]".format(result), "[{0}]".format(field_mapping[result]))

                    value = _deep_get(label_info, 'labelExpressionInfo', 'value')
                    if value is not None:
                        results = re.findall("{(.*?)}", value)
                        for result in results:
                            if result in field_mapping:
                                label_info['labelExpressionInfo']['value'] = str(value).replace("{{{0}}}".format(result), "{{{0}}}".format(field_mapping[result]))

                    expression = _deep_get(label_info, 'labelExpressionInfo', 'expression')
                    if expression is not None:
                        label_info['labelExpressionInfo']['expression'] = _find_and_replace_fields_arcade(str(expression), field_mapping)

    if 'popupInfo' in layer and layer['popupInfo'] is not None:
        if 'title' in layer['popupInfo'] and layer['popupInfo']['title'] is not None:
            results = re.findall("{(.*?)}", layer['popupInfo']['title'])
            for result in results:
                if result in field_mapping:
                    layer['popupInfo']['title'] = str(layer['popupInfo']['title']).replace("{{{0}}}".format(result), "{{{0}}}".format(field_mapping[result]))

        if 'description' in layer['popupInfo'] and layer['popupInfo']['description'] is not None:
            results = re.findall("{(.*?)}", layer['popupInfo']['description'])
            for result in results:
                if result in field_mapping:
                    layer['popupInfo']['description'] = str(layer['popupInfo']['description']).replace("{{{0}}}".format(result), "{{{0}}}".format(field_mapping[result]))

        if 'fieldInfos' in layer['popupInfo'] and layer['popupInfo']['fieldInfos'] is not None:
            for field in layer['popupInfo']['fieldInfos']:
                if field['fieldName'] in field_mapping:
                    field['fieldName'] = field_mapping[field['fieldName']]

        if 'expressionInfos' in layer['popupInfo'] and layer['popupInfo']['expressionInfos'] is not None:
            for expression_info in layer['popupInfo']['expressionInfos']:
                if 'expression' in expression_info and expression_info['expression'] is not None:
                    expression_info['expression'] = _find_and_replace_fields_arcade(str(expression_info['expression']), field_mapping)

        if 'mediaInfos' in layer['popupInfo'] and layer['popupInfo']['mediaInfos'] is not None:
            for media_info in layer['popupInfo']['mediaInfos']:
                if 'title' in media_info and media_info['title'] is not None:
                    results = re.findall("{(.*?)}", media_info['title'])
                    for result in results:
                        if result in field_mapping:
                            media_info['title'] = str(media_info['title']).replace("{{{0}}}".format(result), "{{{0}}}".format(field_mapping[result]))
                if 'caption' in media_info and media_info['caption'] is not None:
                    results = re.findall("{(.*?)}", media_info['caption'])
                    for result in results:
                        if result in field_mapping:
                            media_info['caption'] = str(media_info['caption']).replace("{{{0}}}".format(result), "{{{0}}}".format(field_mapping[result]))
                if 'normalizeField' in media_info and media_info['normalizeField'] is not None:
                    if media_info['normalizeField'] in field_mapping:
                        media_info['normalizeField'] = field_mapping[media_info['normalizeField']]
                if 'fields' in media_info and media_info['fields'] is not None:
                    for field in media_info['fields']:
                        fields = []
                        if field in field_mapping:
                            fields.append(field_mapping[field])
                        else:
                            fields.append(field)
                    media_info['fields'] = fields

    if 'definitionEditor' in layer and layer['definitionEditor'] is not None:
        if 'inputs' in layer['definitionEditor'] and layer['definitionEditor']['inputs'] is not None:
            for definition_input in layer['definitionEditor']['inputs']:
                if 'parameters' in definition_input and definition_input['parameters'] is not None:
                    for param in definition_input['parameters']:
                        if 'fieldName' in param and param['fieldName'] is not None:
                            if param['fieldName'] in field_mapping:
                                param['fieldName'] = field_mapping[param['fieldName']]
        if 'parameterizedExpression' in layer['definitionEditor'] and layer['definitionEditor']['parameterizedExpression'] is not None:
            layer['definitionEditor']['parameterizedExpression'] = _find_and_replace_fields(layer['definitionEditor']['parameterizedExpression'], field_mapping)


def _update_layer_related_fields(layer, relationship_field_mapping):
    """Perform a find and replace for field names in a layer definition.
    Keyword arguments:
    layer - The layer to search and replace fields names
    field_mapping -  A dictionary containing the pairs of original field names and new field names"""

    for id, field_mapping in relationship_field_mapping.items():
        field_prefix = "relationships/{0}/".format(id)

        if 'popupInfo' in layer and layer['popupInfo'] is not None:
            if 'title' in layer['popupInfo'] and layer['popupInfo']['title'] is not None:
                results = re.findall("{{{0}(.*?)}}".format(field_prefix), layer['popupInfo']['title'])
                for result in results:
                    if result in field_mapping:
                        layer['popupInfo']['title'] = str(layer['popupInfo']['title']).replace("{{{0}{1}}}".format(field_prefix, result), "{{{0}{1}}}".format(field_prefix, field_mapping[result]))

            if 'description' in layer['popupInfo'] and layer['popupInfo']['description'] is not None:
                results = re.findall("{{{0}(.*?)}}".format(field_prefix), layer['popupInfo']['description'])
                for result in results:
                    if result in field_mapping:
                        layer['popupInfo']['description'] = str(layer['popupInfo']['description']).replace("{{{0}{1}}}".format(field_prefix, result), "{{{0}{1}}}".format(field_prefix, field_mapping[result]))

            if 'fieldInfos' in layer['popupInfo'] and layer['popupInfo']['fieldInfos'] is not None:
                for field in layer['popupInfo']['fieldInfos']:
                    if field['fieldName'].startswith(field_prefix) and field['fieldName'][len(field_prefix):] in field_mapping:
                        field['fieldName'] = "{0}{1}".format(field_prefix, field_mapping[field['fieldName'][len(field_prefix):]])

            if 'mediaInfos' in layer['popupInfo'] and layer['popupInfo']['mediaInfos'] is not None:
                for media_info in layer['popupInfo']['mediaInfos']:
                    if 'title' in media_info and media_info['title'] is not None:
                        results = re.findall("{{{0}(.*?)}}".format(field_prefix), media_info['title'])
                        for result in results:
                            if result in field_mapping:
                                media_info['title'] = str(media_info['title']).replace("{{{0}{1}}}".format(field_prefix, result), "{{{0}{1}}}".format(field_prefix, field_mapping[result]))
                    if 'caption' in media_info and media_info['caption'] is not None:
                        results = re.findall("{{{0}(.*?)}}".format(field_prefix), media_info['caption'])
                        for result in results:
                            if result in field_mapping:
                                media_info['caption'] = str(media_info['caption']).replace("{{{0}{1}}}".format(field_prefix, result), "{{{0}{1}}}".format(field_prefix, field_mapping[result]))
                    if 'normalizeField' in media_info and media_info['normalizeField'] is not None:
                        if media_info['normalizeField'].startswith(field_prefix) and media_info['normalizeField'] in field_mapping:
                            media_info['normalizeField'] = "{0}{1}".format(field_prefix, field_mapping[media_info['normalizeField'][len(field_prefix):]])
                    if 'fields' in media_info and media_info['fields'] is not None:
                        for field in media_info['fields']:
                            fields = []
                            if field.startswith(field_prefix) and field[len(field_prefix):] in field_mapping:
                                fields.append("{0}{1}".format(field_prefix, field_mapping[field[len(field_prefix):]]))
                            else:
                                fields.append(field)
                        media_info['fields'] = fields


def _zip_dir(path, zip_file, include_root=True):
    """Zip a directory of files.
    Keyword arguments:
    path - The folder containing the files and subfolders to zip
    zip_file - The zip file that will store the compressed files
    include_root -  Indicates if the root folder should be included in the zip"""

    rel_path = ''
    if include_root:
        rel_path = '..'

    # Zip a directory of files
    for root, dirs, files in os.walk(path):
        for file in files:
            zip_file.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(path, rel_path)))


def _deep_get(dictionary, *keys):
    """Safely return a nested value from a dictionary. If at any point along the path the key doesn't exist the function will return None.
    Keyword arguments:
    dictionary - The dictionary to search for the value
    *keys - The keys used to fetch the desired value"""

    return reduce(lambda d, key: d.get(key) if d else None, keys, dictionary)

#endregion


