"""
Classes and objects used to manage published services.
"""
from __future__ import absolute_import
from __future__ import print_function
import os
import json
import tempfile
from .._common import BaseServer
from .parameters import Extension
from arcgis._impl.common._mixins import PropertyMap
########################################################################
class ServiceManager(BaseServer):
    """
    Helper class for managing services. This class is not created by users directly. An instance of this class,
    called 'services', is available as a property of the Server object. Users call methods on this 'services' object to
    managing services.
    """
    _currentURL = None
    _url = None
    _con = None
    _json_dict = None
    _currentFolder = None
    _folderName = None
    _folders = None
    _foldersDetail = None
    _folderDetail = None
    _webEncrypted = None
    _description = None
    _isDefault = None
    _services = None
    _json = None
    #----------------------------------------------------------------------
    def __init__(self, url, gis,
                 initialize=False,
                 sm=None):
        """Constructor
            Inputs:
               url - admin url
               gis - GIS or Server object
        """
        if sm is not None:
            self._sm = sm
        super(ServiceManager, self).__init__(gis=gis,
                                             url=url, sm=sm)
        self._con = gis
        self._url = url
        self._currentURL = url
        self._currentFolder = '/'
        if initialize:
            self._init(gis)
    #----------------------------------------------------------------------
    def _init(self, connection=None):
        """loads the properties into the class"""
        if connection is None:
            connection = self._con
        params = {"f":"json"}
        try:
            result = connection.get(path=self._currentURL,
                                    params=params)
            if isinstance(result, dict):
                self._json_dict = result
                self._properties = PropertyMap(result)
            else:
                self._json_dict = {}
                self._properties = PropertyMap({})
        except:
            self._json_dict = {}
            self._properties = PropertyMap({})
    #----------------------------------------------------------------------
    @property
    def _folder(self):
        """ returns current folder """
        return self._folderName
    #----------------------------------------------------------------------
    @_folder.setter
    def _folder(self, folder):
        """gets/set the current folder"""

        if folder == "" or\
             folder == "/" or \
             folder is None:
            self._currentURL = self._url
            self._services = None
            self._description = None
            self._folderName = None
            self._webEncrypted = None
            self._init()
            self._folderName = folder
        elif folder.lower() in [f.lower() for f in self.folders]:
            self._currentURL = self._url + "/%s" % folder
            self._services = None
            self._description = None
            self._folderName = None
            self._webEncrypted = None
            self._init()
            self._folderName = folder
    #----------------------------------------------------------------------
    @property
    def folders(self):
        """ returns a list of all folders """
        if self._folders is None:
            self._init()
            self._folders = self.properties['folders']
        if "/" not in self._folders:
            self._folders.append("/")
        return self._folders
    #----------------------------------------------------------------------
    def list(self, folder=None, refresh=True):
        """
        returns a list of services in the specified folder

        Parameters:
        :param folder: name of the folder to list services from
        :param refresh: Bool, default is False. If True, the list of services will be
        requested to the server, else the list will be returned from cache.
        """
        if folder is None:
            folder = '/'
        if folder != self._currentFolder or \
           self._services is None or refresh:
            self._currentFolder = folder
            self._folder = folder
            return self._services_list()

        return self._services_list()
    #----------------------------------------------------------------------
    #@property
    def _services_list(self):
        """ returns the services in the current folder """
        self._services = []
        params = {
            "f" : "json"
        }
        json_dict = self._con.get(path=self._currentURL,
                                  params=params)
        if "services" in json_dict.keys():
            for s in json_dict['services']:
                u_url = self._currentURL + "/%s.%s" % (s['serviceName'], s['type'])
                self._services.append(
                    Service(url=u_url,
                            gis=self._con)
                )
        return self._services
    #----------------------------------------------------------------------
    @property
    def _extensions(self):
        """
        This resource is a collection of all the custom server object
        extensions that have been uploaded and registered with the server.
        You can register new server object extensions using the register
        extension operation. When updating an existing extension, you need
        to use the update extension operation. If an extension is no longer
        required, you can use the unregister operation to remove the
        extension from the site.
        """
        url = self._url + "/types/extensions"
        params = {'f' : 'json'}
        return self._con.get(path=url,
                             params=params)
    #----------------------------------------------------------------------
    def publish_sd(self,
                   sd_file,
                   folder=None):
        """
        publishes a service definition file to arcgis server
        """
        return self._sm.publish_sd(sd_file, folder)
    #----------------------------------------------------------------------
    def _find_services(self, service_type="*"):
        """
            returns a list of a particular service type on AGS
            Input:
              service_type - Type of service to find.  The allowed types
                             are: ("GPSERVER", "GLOBESERVER", "MAPSERVER",
                             "GEOMETRYSERVER", "IMAGESERVER",
                             "SEARCHSERVER", "GEODATASERVER",
                             "GEOCODESERVER", "*").  The default is *
                             meaning find all service names.
            Output:
              returns a list of service names as <folder>/<name>.<type>
        """
        allowed_service_types = ("GPSERVER", "GLOBESERVER", "MAPSERVER",
                                 "GEOMETRYSERVER", "IMAGESERVER",
                                 "SEARCHSERVER", "GEODATASERVER",
                                 "GEOCODESERVER", "*")
        lower_types = [l.lower() for l in service_type.split(',')]
        for v in lower_types:
            if v.upper() not in allowed_service_types:
                return {"message" : "%s is not an allowed service type." % v}
        params = {
            "f" : "json"
        }
        type_services = []
        folders = self.folders
        folders.append("")
        baseURL = self._url
        for folder in folders:
            if folder == "":
                url = baseURL
            else:
                url = baseURL + "/%s" % folder
            res = self._con.get(path=url, params=params)
            if res.has_key("services"):
                for service in res['services']:
                    if service['type'].lower() in lower_types:
                        service['URL'] = url + "/%s.%s" % (service['serviceName'],
                                                           service_type)
                        type_services.append(service)
                    del service
            del res
            del folder
        return type_services
    #----------------------------------------------------------------------
    def _examine_folder(self, folder=None):
        """
        A folder is a container for GIS services. ArcGIS Server supports a
        single level hierarchy of folders.
        By grouping services within a folder, you can conveniently set
        permissions on them as a single unit. A folder inherits the
        permissions of the root folder when it is created, but you can
        change those permissions at a later time.

        Parameters:
         :folder: name of folder to exmine
        """
        params = {'f': 'json'}
        if folder:
            url = self._url + "/" + folder
        else:
            url = self._url
        return self._con.get(path=url, params=params)
    #----------------------------------------------------------------------
    def _can_create_service(self,
                           service,
                           options=None,
                           folder_name=None,
                           service_type=None):
        """
        Use canCreateService to determine whether a specific service can be
        created on the ArcGIS Server site.

        Parameters:
         :folder_name: This is an optional parameter to indicate the folder
          where canCreateService will check for the service.
         :service_type: The type of service that can be created. This is an
          optional parameter, though either theserviceType or service
          parameter must be used.
         :service: The service configuration in JSON format. For more
          information about the service configuration options, see
          createService. This is an optional parameter, though either the
          service_type or service parameter must be used.
         :options: This is an optional parameter that provides additional
          information about the service, such as whether it is a hosted
          service.
        """
        url = self._url + "/canCreateService"
        params = {"f" : "json",
                  'service' : service}
        if options:
            params['options'] = options
        if folder_name:
            params['folderName'] = folder_name
        if service_type:
            params['serviceType'] = service_type
        return self._con.post(path=url,
                              postdata=params)

    #----------------------------------------------------------------------
    def _add_folder_permission(self, principal, is_allowed=True, folder=None):
        """
           Assigns a new permission to a role (principal). The permission
           on a parent resource is automatically inherited by all child
           resources
           Input:
              principal - name of role to assign/disassign accesss
              is_allowed -  boolean which allows access
           Output:
              JSON message as dictionary
        """
        if folder is not None:
            u_url = self._url + "/%s/%s" % (folder, "/permissions/add")
        else:
            u_url = self._url + "/permissions/add"
        params = {
            "f" : "json",
            "principal" : principal,
            "isAllowed" : is_allowed
        }
        res = self._con.post(path=u_url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def _folder_permissions(self, folder_name):
        """
           Lists principals which have permissions for the folder.
           Input:
              folder_name - name of the folder to list permissions for
           Output:
              JSON Message as Dictionary
        """
        u_url = self._url + "/%s/permissions" % folder_name
        params = {
            "f" : "json",
        }
        return self._con.post(path=u_url, postdata=params)
    #----------------------------------------------------------------------
    def _clean_permissions(self, principal):
        """
           Cleans all permissions that have been assigned to a role
           (principal). This is typically used when a role is deleted.
           Input:
              principal - name of the role to clean
           Output:
              JSON Message as Dictionary
        """
        u_url = self._url + "/permissions/clean"
        params = {
            "f" : "json",
            "principal" : principal
        }
        res = self._con.post(path=u_url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def create_folder(self, folder_name, description=""):
        """
           Creates a unique folder name on AGS
           Inputs:
              folder_name - name of folder on AGS
              description - describes the folder
           Output:
              JSON message as dictionary
        """
        params = {
            "f" : "json",
            "folderName" : folder_name,
            "description" : description
        }
        u_url = self._url + "/createFolder"
        res = self._con.post(path=u_url, postdata=params)
        self._init()
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def delete_folder(self, folder_name):
        """
           deletes a folder on AGS
           Inputs:
              folder_name - name of folder to remove
           Output:
              boolean
        """
        params = {
            "f" : "json"
        }
        if folder_name in self.folders:
            u_url = self._url + "/%s/deleteFolder" % folder_name
            res = self._con.post(path=u_url, postdata=params)
            self._init()
            if 'status' in res:
                return res['status'] == 'success'
            return res
        else:
            return False
    #----------------------------------------------------------------------
    def _delete_service(self, name, service_type, folder=None):
        """
           deletes a service from AGS
           Inputs:
              name - name of the service
              service_type - type of the service
              folder - name of the folder the service resides, leave None
                       for root.
           Output:
              boolean
        """
        if folder is None:
            u_url = self._url + "/%s.%s/delete" % (name,
                                                   service_type)
        else:
            u_url = self._url + "/%s/%s.%s/delete" % (folder,
                                                      name,
                                                      service_type)
        params = {
            "f" : "json"
        }
        res = self._con.post(path=u_url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def _service_report(self, folder=None):
        """
           provides a report on all items in a given folder
           Inputs:
              folder - folder to report on given services. None means root
        """
        items = ["description", "status",
                 "instances", "iteminfo",
                 "properties"]
        if folder is None:
            u_url = self._url + "/report"
        else:
            u_url = self._url + "/%s/report" % folder
        params = {
            "f" : "json",
            "parameters" : items
        }
        return self._con.get(path=u_url, params=params)
    #----------------------------------------------------------------------
    @property
    def _types(self):
        """ returns the allowed services types """
        params = {
            "f" : "json"
        }
        u_url = self._url + "/types"
        return self._con.get(path=u_url,
                             params=params)
    #----------------------------------------------------------------------
    def _federate(self):
        """
        This operation is used when federating ArcGIS Server with Portal
        for ArcGIS. It imports any services that you have previously
        published to your ArcGIS Server site and makes them available as
        items with Portal for ArcGIS. Beginning at 10.3, services are
        imported automatically as part of the federate process.
        If the automatic import of services fails as part of the federation
        process, the following severe-level message will appear in the
        server logs:
           Failed to import GIS services as items within portal.
        If this occurs, you can manually re-run the operation to import
        your services as items in the portal. Before you do this, obtain a
        portal token and then validate ArcGIS Server is federated with
        your portal using the portal website. This is done in
        My Organization > Edit Settings > Servers.
        After you run the Federate operation, specify sharing properties to
        determine which users and groups will be able to access each service.
        """
        params = {'f' : 'json'}
        url = self._url + "/federate"
        return self._con.post(path=url,
                              postdata=params)
    #----------------------------------------------------------------------
    def _unfederate(self):
        """
        This operation is used when unfederating ArcGIS Server with Portal
        for ArcGIS. It removes any items from the portal that represent
        services running on your federated ArcGIS Server. You typically run
        this operation in preparation for a full unfederate action. For
        example, this can be performed using
               My Organization > Edit Settings > Servers
        in the portal website or the Unregister Server operation in the
        ArcGIS REST API.
        Beginning at 10.3, services are removed automatically as part of
        the unfederate process. If the automatic removal of service items
        fails as part of the unfederate process, you can manually re-run
        the operation to remove the items from the portal.
        """
        params = {'f' : 'json'}
        url = self._url + "/unfederate"
        res = self._con.post(path=url,
                             postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def _unregister_extension(self, extension_filename):
        """
        Unregisters all the extensions from a previously registered server
        object extension (.SOE) file.

        Parameters:
         :extension_filename: name of the previously registered .SOE file
        """
        params = {
            "f" : "json",
            "extensionFilename" : extension_filename
        }
        url = self._url + "/types/extensions/unregister"
        res = self._con.post(path=url,
                             postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def _update_extension(self, item_id):
        """
        Updates extensions that have been previously registered with the
        server. All extensions in the new .SOE file must match with
        extensions from a previously registered .SOE file.
        Use this operation to update your implementations or extension
        configuration properties.

        Parameters:
         :item_id: id of the uploaded .SOE file
        """
        params = {'f':'json',
                  'id': item_id}
        url = self._url + "/types/extensions/update"
        res = self._con.post(path=url,
                             postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def _rename_service(self, name, service_type,
                        new_name, folder=None):
        """
           Renames a published AGS Service
           Inputs:
              name - old service name
              service_type - type of service
              new_name - new service name
              folder - location of where the service lives, none means
                       root folder.
           Output:
              JSON message as dictionary
        """
        params = {
            "f" : "json",
            "serviceName" : name,
            "serviceType" : service_type,
            "serviceNewName" : new_name
        }
        if folder is None:
            u_url = self._url + "/renameService"
        else:
            u_url = self._url + "/%s/renameService" % folder
        res = self._con.post(path=u_url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        self._init()
        return res
    #----------------------------------------------------------------------
    def create_service(self, service):
        """
        Creates a new GIS service in the folder. A service is created by
        submitting a JSON representation of the service to this operation.

        The JSON representation of a service contains the following four
        sections:
         - Service Description Properties-Common properties that are shared
          by all service types. Typically, they identify a specific service.
         - Service Framework Properties-Properties targeted towards the
          framework that hosts the GIS service. They define the life cycle
          and load balancing of the service.
         - Service Type Properties -Properties targeted towards the core
          service type as seen by the server administrator. Since these
          properties are associated with a server object, they vary across
          the service types. The Service Types section in the Help
          describes the supported properties for each service.
         - Extension Properties-Represent the extensions that are enabled
          on the service. The Extension Types section in the Help describes
          the supported out-of-the-box extensions for each service type.
        Output:
         dictionary status message
        """
        url = self._url + "/createService"
        params = {
            "f" : "json"
        }
        if isinstance(service, str):
            params['service'] = service
        elif isinstance(service, dict):
            params['service'] = json.dumps(service)
        return self._con.post(path=url,
                              postdata=params)
    #----------------------------------------------------------------------
    def _stop_services(self, services):
        """
        Stops serveral services on a single server
        Inputs:
           services - is a list of dictionary objects. Each dictionary
                      object is defined as:
                        folder_name - The name of the folder containing the
                        service, for example, "Planning". If the service
                        resides in the root folder, leave the folder
                        property blank ("folder_name": "").
                        serviceName - The name of the service, for example,
                        "FireHydrants".
                        type - The service type, for example, "MapServer".
                     Example:
                        [{
                          "folder_name" : "",
                          "serviceName" : "SampleWorldCities",
                          "type" : "MapServer"
                        }]
        """
        url = self._url + "/stopServices"
        if isinstance(services, dict):
            services = [services]
        elif isinstance(services, (list, tuple)):
            services = list(services)
        else:
            Exception("Invalid input for parameter services")
        params = {
            "f" : "json",
            "services" : {
                "services":services
            }
        }
        res = self._con.post(path=url,
                             postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def _start_services(self, services):
        """
        starts serveral services on a single server
        Inputs:
           services - is a list of dictionary objects. Each dictionary
                      object is defined as:
                        folder_name - The name of the folder containing the
                        service, for example, "Planning". If the service
                        resides in the root folder, leave the folder
                        property blank ("folder_name": "").
                        serviceName - The name of the service, for example,
                        "FireHydrants".
                        type - The service type, for example, "MapServer".
                     Example:
                        [{
                          "folderName" : "",
                          "serviceName" : "SampleWorldCities",
                          "type" : "MapServer"
                        }]
        """
        url = self._url + "/startServices"
        if isinstance(services, dict):
            services = [services]
        elif isinstance(services, (list, tuple)):
            services = list(services)
        else:
            Exception("Invalid input for parameter services")
        params = {
            "f" : "json",
            "services" : {
                "services":services
            }
        }
        res = self._con.post(path=url,
                             postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def _edit_folder(self, description, web_encrypted=False):
        """
        This operation allows you to change the description of an existing
        folder or change the web encrypted property.
        The web encrypted property indicates if all the services contained
        in the folder are only accessible over a secure channel (SSL). When
        setting this property to true, you also need to enable the virtual
        directory security in the security configuration.

        Inputs:
           description - a description of the folder
           web_encrypted - boolean to indicate if the services are
            accessible over SSL only.
        """
        url = self._url + "/editFolder"
        params = {
            "f" : "json",
            "webEncrypted" : web_encrypted,
            "description" : "%s" % description
        }
        res = self._con.post(path=url,
                             postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def exists(self, folder_name, name=None, service_type=None):
        """
        This operation allows you to check whether a folder or a service
        exists. To test if a folder exists, supply only a folder_name. To
        test if a service exists in a root folder, supply both serviceName
        and service_type with folder_name=None. To test if a service exists
        in a folder, supply all three parameters.

        Inputs:
           folder_name - a folder name
           name - a service name
           service_type - a service type. Allowed values:
                GeometryServer | ImageServer | MapServer | GeocodeServer |
                GeoDataServer | GPServer | GlobeServer | SearchServer
        """
        if folder_name and \
           name is None and \
           service_type is None:
            for folder in self.folders:
                if folder.lower() == folder_name.lower():
                    return True
                del folder
            return False
        url = self._url + "/exists"
        params = {
            "f" : "json",
            "folderName" : folder_name,
            "serviceName" : name,
            "type" : service_type
        }
        res = self._con.post(path=url,
                             postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        elif 'exists' in res:
            return res['exists']
        return res
########################################################################
class Service(BaseServer):
    """
    Represents a GIS administrative service

    **(This should not be created by a user)**

    """
    _con = None
    _frameworkProperties = None
    _recycleInterval = None
    _instancesPerContainer = None
    _maxWaitTime = None
    _minInstancesPerNode = None
    _maxIdleTime = None
    _maxUsageTime = None
    _allowedUploadFileTypes = None
    _datasets = None
    _properties = None
    _recycleStartTime = None
    _clusterName = None
    _description = None
    _isDefault = None
    _type = None
    _serviceName = None
    _isolationLevel = None
    _capabilities = None
    _loadBalancing = None
    _configuredState = None
    _maxStartupTime = None
    _private = None
    _maxUploadFileSize = None
    _keepAliveInterval = None
    _maxInstancesPerNode = None
    _json = None
    _json_dict = None
    _interceptor = None
    _provider = None
    _portalProperties = None
    _jsonProperties = None
    _url = None
    _extensions = None
    #----------------------------------------------------------------------
    def __init__(self,
                 url,
                 gis,
                 initialize=False,
                 **kwargs):
        """Constructor
            Inputs:
               url - admin url
               gis - GIS or Server object
               initialize - fills all the properties at object creation is
                            true
        """
        super(Service, self).__init__(gis=gis,
                                      url=url)
        self._service_manager = kwargs.pop('service_manager', None)
        self._url = url
        self._currentURL = url
        self._con = gis
        if initialize:
            self._init(gis)
    #----------------------------------------------------------------------
    def _init(self, connection=None):
        """ populates server admin information """
        from .parameters import Extension
        params = {
            "f" : "json"
        }
        if connection:
            json_dict = connection.get(path=self._url,
                                       params=params)
        else:
            json_dict = self._con.get(path=self._currentURL,
                                      params=params)
        self._json = json.dumps(json_dict)
        self._json_dict = json_dict
        attributes = [attr for attr in dir(self)
                      if not attr.startswith('__') and \
                      not attr.startswith('_')]
        self._properties = PropertyMap(json_dict)
        for k, v in json_dict.items():
            if k.lower() == "extensions":
                self._extensions = []
                for ext in v:
                    self._extensions.append(Extension.fromJSON(ext))
                    del ext
            #elif k in attributes:
            #    setattr(self, "_"+ k, json_dict[k])
            #else:
            #    setattr(self, k, v)
            del k
            del v
    #----------------------------------------------------------------------
    def __str__(self):
        return '<%s at %s>' % (type(self).__name__, self._url)
    #----------------------------------------------------------------------
    def __repr__(self):
        return '<%s at %s>' % (type(self).__name__, self._url)
    #----------------------------------------------------------------------
    def _refresh(self):
        """refreshes the object's values by re-querying the service"""
        self._init()
    #----------------------------------------------------------------------
    def _json_properties(self):
        """returns the jsonProperties"""
        if self._jsonProperties is None:
            self._init()
        return self._jsonProperties
    #----------------------------------------------------------------------
    @property
    def extensions(self):
        """lists the extensions on a service"""
        if self._extensions is None:
            self._init()
        return self._extensions
    #----------------------------------------------------------------------
    def _modify_extensions(self,
                          extension_objects=None):
        """
        enables/disables a service extension type based on the name
        """
        if extension_objects is None:
            extension_objects = []
        if len(extension_objects) > 0 and \
           isinstance(extension_objects[0], Extension):
            self._extensions = extension_objects
            self._json_dict['extensions'] = [x.value for x in extension_objects]
            res = self.edit(str(self))
            self._json = None
            self._init()
            return res
        return False
    #----------------------------------------------------------------------
    def _has_child_permissions_conflict(self, principal, permission):
        """
        You can invoke this operation on the resource (folder or service)
        to determine if this resource has a child resource with opposing
        permissions. This operation is typically invoked before adding a
        new permission to determine if the new addition will overwrite
        existing permissions on the child resources.
        For more information, see the section on the Continuous Inheritance
        Model.
        Since this operation basically checks if the permission to be added
        will cause a conflict with permissions on a child resource, this
        operation takes the same parameters as the Add Permission operation.

        Parameters:
         :principal: name of the role for whom the permission is being
          assigned
         :permission: The permission JSON object. The format is described
          below.
          Format:
           {
           "isAllowed": <true|false>,
           "constraint": ""
           }
        """
        params = {
            "f" : "json",
            "principal" : principal,
            "permission" : permission
        }
        url = self._url + "/permissions/hasChildPermissionsConflict"
        return self._con.post(path=url,
                              postdata=params)
    #----------------------------------------------------------------------
    def start(self):
        """ starts the specific service """
        params = {
            "f" : "json"
        }
        u_url = self._url + "/start"
        res = self._con.post(path=u_url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def stop(self):
        """ stops the current service """
        params = {
            "f" : "json"
        }
        u_url = self._url + "/stop"
        res = self._con.post(path=u_url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def restart(self):
        """ restarts the current service """
        self.stop()
        self.start()
        return True

    def rename(self, new_name):
        """Renames this service to the new name"""
        params = {
            "f": "json",
            "serviceName": self.properties.serviceName,
            "serviceType": self.properties.type,
            "serviceNewName": new_name
        }

        u_url = self._url[:self._url.rfind('/')] + "/renameService"

        res = self._service._con.post(path=u_url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def delete(self):
        """deletes a service from arcgis server"""
        params = {
            "f" : "json",
        }
        u_url = self._url + "/delete"
        res = self._con.post(path=u_url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    @property
    def status(self):
        """ returns the status of the service """
        params = {
            "f" : "json",
        }
        u_url = self._url + "/status"
        return self._con.get(path=u_url, params=params)
    #----------------------------------------------------------------------
    @property
    def statistics(self):
        """ returns the stats for the service """
        params = {
            "f" : "json"
        }
        u_url = self._url + "/statistics"
        return self._con.get(path=u_url, params=params)
    #----------------------------------------------------------------------
    @property
    def _permissions(self):
        """ returns the permissions for the service """
        params = {
            "f" : "json"
        }
        u_url = self._url + "/permissions"
        return self._con.get(path=u_url, param_dict=params)
    #----------------------------------------------------------------------
    @property
    def _iteminfo(self):
        """ returns the item information """
        params = {
            "f" : "json"
        }
        u_url = self._url + "/iteminfo"
        return self._con.get(path=u_url, params=params)
    #----------------------------------------------------------------------
    def _register_extension(self, item_id):
        """
        Registers a new server object extension file with the server.
        Before you register the file, you need to upload the .SOE file to
        the server using the Upload Data Item operation. The item_id
        returned by the upload operation must be passed to the register
        operation.
        This operation registers all the server object extensions defined
        in the .SOE file.

        Parameters:
         :item_id: The item_id of the uploaded .SOE file.
        """
        params = {
            "id" : item_id,
            "f" : "json"
        }
        url = self._url + "/types/extensions/register"
        return self._con.post(path=url,
                              postdata=params)

    #----------------------------------------------------------------------
    def _delete_item_info(self):
        """
        Deletes the item information.
        """
        params = {
            "f" : "json"
        }
        u_url = self._url + "/iteminfo/delete"
        return self._con.get(path=u_url, params=params)
    #----------------------------------------------------------------------
    def _upload_item_info(self, folder, path):
        """
        Allows for the upload of new itemInfo files such as metadata.xml
        Inputs:
           folder - folder on ArcGIS Server
           filePath - full path of the file to upload
        Output:
           json as dictionary
        """
        files = {}
        url = self._url + "/iteminfo/upload"
        params = {
            "f" : "json",
            "folder" : folder
        }
        files['file'] = path
        return self._con.post(path=url,
                              postdata=params,
                              files=files)
    #----------------------------------------------------------------------
    def _edit_item_info(self, json_dict):
        """
        Allows for the direct edit of the service's item's information.
        To get the current item information, pull the data by calling
        iteminfo property.  This will return the default template then pass
        this object back into the editItemInfo() as a dictionary.

        Inputs:
           json_dict - iteminfo dictionary.
        Output:
           json as dictionary
        """
        url = self._url + "/iteminfo/edit"
        params = {
            "f" : "json",
            "serviceItemInfo" : json.dumps(json_dict)
        }
        return self._con.post(path=url,
                              postdata=params)
    #----------------------------------------------------------------------
    def _service_manifest(self, file_type="json"):
        """
        The service manifest resource documents the data and other
        resources that define the service origins and power the service.
        This resource will tell you underlying databases and their location
        along with other supplementary files that make up the service.

        Inputs:
           file_type - this can be json or xml.  json return the
            manifest.json file.  xml returns the manifest.xml file.


        """

        url = self._url + "/iteminfo/manifest/manifest.%s" % file_type
        params = {
        }
        f = self._con.get(path=url,
                          params=params,
                          out_folder=tempfile.gettempdir(),
                          file_name=os.path.basename(url))
        return open(f, 'r').read()
    #----------------------------------------------------------------------
    def _add_permission(self, principal, is_allowed=True):
        """
           Assigns a new permission to a role (principal). The permission
           on a parent resource is automatically inherited by all child
           resources.
           Inputs:
              principal - role to be assigned
              is_allowed - access of resource by boolean
           Output:
              JSON message as dictionary
        """
        u_url = self._url + "/permissions/add"
        params = {
            "f" : "json",
            "principal" : principal,
            "isAllowed" : is_allowed
        }
        res = self._con.post(path=u_url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
    #----------------------------------------------------------------------
    def edit(self, service):
        """
        To edit a service, you need to submit the complete JSON
        representation of the service, which includes the updates to the
        service properties. Editing a service causes the service to be
        restarted with updated properties.
        """
        url = self._url + "/edit"
        params = {
            "f" : "json"
        }
        if isinstance(service, str):
            params['service'] = service
        elif isinstance(service, dict):
            params['service'] = json.dumps(service)
        res = self._con.post(path=url, postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return res
