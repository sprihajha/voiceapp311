"""
Modifies a local portal's system settings.
"""
from ..._impl.connection import _ArcGISConnection
from .. import GIS
from ._base import BasePortalAdmin
from ..._impl.common._mixins import PropertyMap
########################################################################
class System(BasePortalAdmin):
    """
    This resource is an umbrella for a collection of system-wide resources
    for your portal. This resource provides access to the ArcGIS Web
    Adaptor configuration, portal directories, database management server,
    indexing capabilities, license information, and the properties of your
    portal.
    """
    _gis = None
    _con = None
    _url = None
    #----------------------------------------------------------------------
    def __init__(self, url, gis=None, **kwargs):
        """Constructor"""
        super(System, self).__init__(url=url,
                                     gis=gis,
                                     **kwargs)
        initialize = kwargs.pop("initialize", False)
        if isinstance(gis, _ArcGISConnection):
            self._con = gis
        elif isinstance(gis, GIS):
            self._gis = gis
            self._con = gis._con
        else:
            raise ValueError(
                    "connection must be of type GIS or _ArcGISConnection")
        if initialize:
            self._init(self._gis)
    #----------------------------------------------------------------------
    @property
    def properties(self):
        """
        Gets/Sets the system properties that have been modified to control
        the portal's environment. The list of available properties are:
         - privatePortalURL-Informs the portal that it has a front end
           load-balancer/proxy reachable at the URL. This property is
           typically used to set up a highly available portal configuration
         - portalLocalhostName-Informs the portal back-end to advertise the
           value of this property as the local portal machine. This is
           typically used during federation and when the portal machine has
           one or more public host names.
         - httpProxyHost-Specifies the HTTP hostname of the proxy server
         - httpProxyPort-Specifies the HTTP port number of the proxy server
         - httpProxyUser-Specifies the HTTP proxy server username.
         - httpProxyPassword-Specifies the HTTP proxy server password.
         - isHttpProxyPasswordEncrypted-Set this property to false when you
           are configuring the HTTP proxy server password in plain text.
           After configuration, the password will be encrypted and this
           property will be set to true
         - httpsProxyHost-Specifies the HTTPS hostname of the proxy server
         - httpsProxyPort-Specifies the HTTPS port number of the proxy
           server
         - httpsProxyUser-Specifies the HTTPS proxy server username
         - httpsProxyPassword-Specifies the HTTPS proxy server password
         - isHttpsProxyPasswordEncrypted-Set this property to false when
           you are configuring the HTTPS proxy server password in plain
           text. After configuration, the password will be encrypted and
           this property will be set to true.
         - nonProxyHosts-If you want to federate ArcGIS Server and the site
           does not require use of the forward proxy, list the server
           machine or site in the nonProxyHosts property. Machine and
           domain items are separated using a pipe (|).
         - WebContextURL-If you are using a reverse proxy, set this
           property to reverse proxy URL.

        """
        url = "%s/properties" % self._url
        params = {"f" : "json"}
        return self._con.get(path=url, params=params)
    #----------------------------------------------------------------------
    @properties.setter
    def properties(self, properties):
        """
        Gets/Sets the system properties that have been modified to control
        the portal's environment. The list of available properties are:
         - privatePortalURL-Informs the portal that it has a front end
           load-balancer/proxy reachable at the URL. This property is
           typically used to set up a highly available portal configuration
         - portalLocalhostName-Informs the portal back-end to advertise the
           value of this property as the local portal machine. This is
           typically used during federation and when the portal machine has
           one or more public host names.
         - httpProxyHost-Specifies the HTTP hostname of the proxy server
         - httpProxyPort-Specifies the HTTP port number of the proxy server
         - httpProxyUser-Specifies the HTTP proxy server username.
         - httpProxyPassword-Specifies the HTTP proxy server password.
         - isHttpProxyPasswordEncrypted-Set this property to false when you
           are configuring the HTTP proxy server password in plain text.
           After configuration, the password will be encrypted and this
           property will be set to true
         - httpsProxyHost-Specifies the HTTPS hostname of the proxy server
         - httpsProxyPort-Specifies the HTTPS port number of the proxy
           server
         - httpsProxyUser-Specifies the HTTPS proxy server username
         - httpsProxyPassword-Specifies the HTTPS proxy server password
         - isHttpsProxyPasswordEncrypted-Set this property to false when
           you are configuring the HTTPS proxy server password in plain
           text. After configuration, the password will be encrypted and
           this property will be set to true.
         - nonProxyHosts-If you want to federate ArcGIS Server and the site
           does not require use of the forward proxy, list the server
           machine or site in the nonProxyHosts property. Machine and
           domain items are separated using a pipe (|).
         - WebContextURL-If you are using a reverse proxy, set this
           property to reverse proxy URL.
        """
        url = "%s/properties/update" % self._url
        params = {"f" : "json",
                  "properties" : properties}
        self._con.get(path=url, params=params)
    #----------------------------------------------------------------------
    @property
    def web_adaptors(self):
        """
        The Web Adaptors resource lists the ArcGIS Web Adaptor configured
        with your portal. You can configure the Web Adaptor by using its
        configuration web page or the command line utility provided with
        the installation.
        """
        url = "%s/webadaptors" % self._url
        return WebAdaptors(url=url, gis=self._con)
    #----------------------------------------------------------------------
    @property
    def directories(self):
        """
        The directories resource is a collection of directories that are
        used by the portal to store and manage content. Beginning at
        10.2.1, Portal for ArcGIS supports five types of directories:
         - Content directory-The content directory contains the data
           associated with every item in the portal.
         - Database directory-The built-in security store and sharing
           rules are stored in a Database server that places files in the
           database directory.
         - Temporary directory - The temporary directory is used as a
           scratch workspace for all the portal's runtime components.
         - Index directory-The index directory contains all the indexes
           associated with the content in the portal. The indexes are used
           for quick retrieval of information and for querying purposes.
         - Logs directory-Errors and warnings are written to text files in
           the log file directory. Each day, if new errors or warnings are
           encountered, a new log file is created.
        If you would like to change the path for a directory, you can use
        the Edit Directory operation.
        """
        res = []
        surl = "%s/directories" % self._url
        params = {'f' : "json"}
        for d in self._con.get(path=surl, params=params)['directories']:
            url = "%s/directories/%s" % (self._url, d['name'])
            res.append(Directory(url=url, gis=self._con))
        return res
    #----------------------------------------------------------------------
    @property
    def licenses(self):
        """
        Portal for ArcGIS requires a valid license to function correctly.
        This resource returns the current status of the license.
        Starting at 10.2.1, Portal for ArcGIS enforces the license by
        checking the number of registered members and comparing it with the
        maximum number of members authorized by the license. Contact Esri
        Customer Service if you have questions about license levels or
        expiration properties.
        """
        url = "%s/licenses" % self._url
        return Licenses(url=url, gis=self._con)
    #----------------------------------------------------------------------
    @property
    def database(self):
        """
        The database resource represents the database management system
        (DBMS) that contains all of the portal's configuration and
        relationship rules. This resource also returns the name and version
        of the database server currently running in the portal.
        You can use the properety to update database accounts
        """
        url = "%s/database" % self._url
        params = {"f" : "json"}
        return self._con.get(path=url, params=params)
    #----------------------------------------------------------------------
    @database.setter
    def database(self, value):
        """
        The database resource represents the database management system
        (DBMS) that contains all of the portal's configuration and
        relationship rules. This resource also returns the name and version
        of the database server currently running in the portal.
        You can use the properety to update database accounts
        """
        url = "%s/database" % self._url
        params = {"f" : "json"}
        for k,v in value.items():
            params[k] = v
        self._con.post(path=url, postdata=params)
    #----------------------------------------------------------------------
    @property
    def index_status(self):
        """
        The status resource allows you to view the status of the indexing
        service. You can view the number of users, groups, and search items
        in both the database (store) and the index.
        If the database and index do not match, indexing is either in
        progress or there is a problem with the index. It is recommended
        that you reindex to correct any issues. If indexing is in progress,
        you can monitor the status by refreshing the page.
        """
        url = "%s/indexer/status" % self._url
        params = {'f' : 'json'}
        return self._con.get(path=url, params=params)
    #----------------------------------------------------------------------
    def reindex(self, mode='FULL', includes=None):
        """
        This operation allows you to generate or update the indexes for
        content; such as users, groups, and items stored in the database
        (store). During the process of upgrading an earlier version of
        Portal for ArcGIS, you are required to update the indexes by
        running this operation. You can check the status of your indexes
        using the status resource.

        Parameters:
         :mode:  mode in which the indexer should run.
          Values: USER_MODE | GROUP_MODE | SEARCH_MODE | FULL
         :includes: An optional comma separated list of elements to include
          in the index. This is useful if you want to only index certain
          items or user accounts.
        """
        url = "%s/indexer/reindex" % self._url
        if mode.lower() == 'full':
            mode = "FULL_MODE"
        params = {
            "f" : "json",
            "mode" : mode
        }
        if includes:
            params['includes'] = includes
        res = self._con.post(path=url,
                             postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return False
    #----------------------------------------------------------------------
    @property
    def languages(self):
        """
        This resource gets/sets which languages will appear in portal
        content search results. Use the Update languages operation to
        modify which language'content will be available.
        """
        url = "%s/languages" % self._url
        params = {"f" : "json"}
        return self._con.get(path=url,
                             params=params)
    #----------------------------------------------------------------------
    @languages.setter
    def languages(self, value):
        """
        This resource gets/sets which languages will appear in portal
        content search results. Use the Update languages operation to
        modify which language'content will be available.
        """
        url = "%s/languages/update" % self._url
        params = {"f" : "json",
                  'languages' : value}
        self._con.post(path=url,
                       postdata=params)
########################################################################
class WebAdaptors(BasePortalAdmin):
    """
    The Web Adaptors resource lists the ArcGIS Web Adaptor configured with
    your portal. You can configure the Web Adaptor by using its
    configuration web page or the command line utility provided with the
    installation.
    """
    _gis = None
    _con = None
    _url = None
    #----------------------------------------------------------------------
    def __init__(self, url, gis=None, **kwargs):
        """Constructor"""
        super(WebAdaptors, self).__init__(url=url,
                                        gis=gis,
                                        **kwargs)
        initialize = kwargs.pop("initialize", False)
        if isinstance(gis, _ArcGISConnection):
            self._con = gis
        elif isinstance(gis, GIS):
            self._gis = gis
            self._con = gis._con
        else:
            raise ValueError(
                    "connection must be of type GIS or _ArcGISConnection")
        if initialize:
            self._init(self._gis)
    #----------------------------------------------------------------------
    def list(self):
        """returns all instances of WebAdaptors"""
        res = []
        if 'webAdaptors' in self.properties:
            for wa in self.properties.webAdaptors:
                url = "%s/%s" % (self._url, wa['id'])
                res.append(WebAdaptor(url=url, gis=self._con))
        return res
    #----------------------------------------------------------------------
    @property
    def configuration(self):
        """
        Gets/Sets the common properties and configuration of the ArcGIS Web
        Adaptor configured with the portal.
        """
        url = "%s/config" % self._url
        params = {"f" : "json"}
        return self._con.get(path=url, params=params)
    #----------------------------------------------------------------------
    @configuration.setter
    def configuration(self, shared_key):
        """
        Gets/Sets the common properties and configuration of the ArcGIS Web
        Adaptor configured with the portal.

        Parameters:
         :shared_key: This property represents credentials that are shared
          with the Web Adaptor. The Web Adaptor uses these credentials to
          communicate with the portal
        """
        url = "%s/config/update" % self._url
        if isinstance(shared_key, str):
            params = {
                "webAdaptorsConfig": {'sharedkey' : shared_key},
                "f" : "json"}
        elif isinstance(shared_key, dict) and \
             'sharedKey' in shared_key:
            params = {"webAdaptorsConfig": shared_key,
                      "f" : "json"}
        return self._con.post(path=url, postdata=params)
########################################################################
class WebAdaptor(BasePortalAdmin):
    """
    The ArcGIS Web Adaptor is a web application that runs in a front-end
    web server. One of the Web Adaptor's primary responsibilities is to
    forward HTTP requests from end users to Portal for ArcGIS. The Web
    Adaptor acts a reverse proxy, providing the end users with an entry
    point to the system, hiding the back-end servers, and providing some
    degree of immunity from back-end failures.
    The front-end web server can authenticate incoming requests against
    your enterprise identity stores and provide specific authentication
    schemes such as Integrated Windows Authentication (IWA), HTTP Basic, or
    Digest.
    Most importantly, a Web Adaptor provides your end users with a well
    defined entry point to your system without exposing the internal
    details of your portal. Portal for ArcGIS will trust requests being
    forwarded by the Web Adaptor and will not challenge the user for any
    credentials. However, the authorization of the request (by looking up
    roles and permissions) is still enforced by the portal's sharing rules.
    """
    _gis = None
    _con = None
    _url = None
    #----------------------------------------------------------------------
    def __init__(self, url, gis=None, **kwargs):
        """Constructor"""
        super(WebAdaptor, self).__init__(url=url,
                                        gis=gis,
                                        **kwargs)
        initialize = kwargs.pop("initialize", False)
        if isinstance(gis, _ArcGISConnection):
            self._con = gis
        elif isinstance(gis, GIS):
            self._gis = gis
            self._con = gis._con
        else:
            raise ValueError(
                    "connection must be of type GIS or _ArcGISConnection")
        if initialize:
            self._init(self._gis)
    #----------------------------------------------------------------------
    def unregister(self):
        """
        You can use this operation to unregister the ArcGIS Web Adaptor
        from your portal. Once a Web Adaptor has been unregistered, your
        portal will no longer trust the Web Adaptor and will not accept any
        credentials from it. This operation is typically used when you want
        to register a new Web Adaptor or when your old Web Adaptor needs to
        be updated.
        """
        url = "%s/unregister" % self._url
        params = {"f" : "json"}
        return self._con.post(path=url, postdata=params)
########################################################################
class Directory(BasePortalAdmin):
    """
    A directory is a file system-based folder that contains a specific type
    of content for the portal. The physicalPath property of a directory
    locates the actual path of the folder on the file system. Beginning at
    10.2.1, Portal for ArcGIS supports local directories and network shares
    as valid locations.
    During the Portal for ArcGIS installation, the setup program asks you
    for the root portal directory (that will contain all the portal's sub
    directories). However, you can change each registered directory through
    this API.
    """
    _gis = None
    _con = None
    _url = None
    #----------------------------------------------------------------------
    def __init__(self, url, gis=None, **kwargs):
        """Constructor"""
        super(Directory, self).__init__(url=url,
                                        gis=gis,
                                        **kwargs)
        initialize = kwargs.pop("initialize", False)
        if isinstance(gis, _ArcGISConnection):
            self._con = gis
        elif isinstance(gis, GIS):
            self._gis = gis
            self._con = gis._con
        else:
            raise ValueError(
                    "connection must be of type GIS or _ArcGISConnection")
        if initialize:
            self._init(self._gis)
    #----------------------------------------------------------------------
    @property
    def properties(self):
        """
        The properties operation on a directory can be used to change the
        physical path and description properties of the directory. This is
        useful when changing the location of a directory from a local path
        to a network share. However, the API does not copy your content and
        data from the old path to the new path. This has to be done
        independently by the system administrator.
        """
        return PropertyMap(self._json_dict)
    #----------------------------------------------------------------------
    @properties.setter
    def properties(self, value):
        """
        The properties operation on a directory can be used to change the
        physical path and description properties of the directory. This is
        useful when changing the location of a directory from a local path
        to a network share. However, the API does not copy your content and
        data from the old path to the new path. This has to be done
        independently by the system administrator.
        """
        url = "%s/edit" % self._url
        params = {
            "f" : "json"
        }
        if isinstance(value, PropertyMap):
            value = dict(value)
        for k,v in value.items():
            params[k] = v
        return self._con.post(path=url, postdata=params)


########################################################################
class Licenses(BasePortalAdmin):
    """
    Portal for ArcGIS requires a valid license to function correctly. This
    resource returns the current status of the license.
    As of 10.2.1, Portal for ArcGIS enforces the license by checking the
    number of registered members and comparing it with the maximum number
    of members authorized by the license. Contact Esri Customer Service if
    you have questions about license levels or expiration properties.
    Starting at 10.5, Portal for ArcGIS enforces two levels of membership
    for licensing to define sets of privileges for registered members and
    their assigned roles.
    """
    _gis = None
    _con = None
    _url = None
    #----------------------------------------------------------------------
    def __init__(self, url, gis=None, **kwargs):
        """Constructor"""
        super(Licenses, self).__init__(url=url,
                                     gis=gis,
                                     **kwargs)
        initialize = kwargs.pop("initialize", False)
        if isinstance(gis, _ArcGISConnection):
            self._con = gis
        elif isinstance(gis, GIS):
            self._gis = gis
            self._con = gis._con
        else:
            raise ValueError(
                    "connection must be of type GIS or _ArcGISConnection")
        if initialize:
            self._init(self._gis)
    #----------------------------------------------------------------------
    def entitlements(self, app="arcgisprodesktop"):
        """
        This operation returns the currently queued entitlements for a
        product, such as ArcGIS Pro or Navigator for ArcGIS, and applies
        them when their start dates become effective. It's possible that
        all entitlements imported using the Import Entitlements operation
        are effective immediately and no entitlements are added to the
        queue. In this case, the operation returns an empty result.

        Parameters:
         :app: application lookup
        """
        allowed = ["appstudioweb", "arcgisprodesktop",
                   "busanalystonline_2", "drone2map",
                   "geoplanner", "arcgisInsights",
                   "LRReporter", "navigator",
                   "RoadwayReporter"]
        params = {
            "f" : "json",
            "appId" : app
        }
        if app not in allowed:
            raise ValueError("The app value must be: %s" % ",".join(allowed))
        url = "%s/getEntitlements" % self._url
        return self._con.get(path=url, params=params)
    #----------------------------------------------------------------------
    def remove_entitlement(self, app="arcgisprodesktop"):
        """
        deletes an entitlement from a site
        """
        allowed = ["appstudioweb", "arcgisprodesktop",
                   "busanalystonline_2", "drone2map",
                   "geoplanner", "arcgisInsights",
                   "LRReporter", "navigator",
                   "RoadwayReporter"]
        params = {
                "f" : "json",
                "appId" : app
            }
        if app not in allowed:
            raise ValueError("The app value must be: %s" % ",".join(allowed))
        url = "%s/removeAllEntitlements" % self._url
        return self._con.get(path=url, params=params)
    #----------------------------------------------------------------------
    def update_license_manager(self, info):
        """
        ArcGIS License Server Administrator works with your portal and
        enforces licenses for ArcGIS Pro. This operation allows you to
        change the license server connection information for your portal.
        When you import entitlements into portal using the Import
        Entitlements operation, a license server is automatically
        configured for you. If your license server changes after the
        entitlements have been imported, you only need to change the
        license server connection information.
        You can register a backup license manager for high availability of
        your licensing portal. When configuring a backup license manager,
        you need to make sure that the backup license manager has been
        authorized with the same organizational entitlements. After
        configuring the backup license manager, Portal for ArcGIS is
        restarted automatically. When the restart completes, the portal is
        configured with the backup license server you specified.
        Parameter:
         :info: JSON representation of the license server connection
          information.
        """
        params = {
            "f" : "json",
            "licenseManagerInfo" : info
        }
        url = "%s/updateLicenseManager" % self._url
        return self._con.post(path=url, postdata=params)
    #----------------------------------------------------------------------
    def import_entitlements(self, file, application):
        """
        This operation allows you to import entitlements for ArcGIS Pro and
        additional products such as Navigator for ArcGIS into your
        licensing portal. Once the entitlements have been imported, you can
        assign licenses to users within your portal. The operation requires
        an entitlements file that has been exported out of your ArcGIS
        License Server Administrator or out of My Esri, depending on the
        product.
        A typical entitlements file will have multiple parts, each
        representing a set of entitlements that are effective at a specific
        date. The parts that are effective immediately will be configured
        to be the current entitlements. Other parts will be added to a
        queue. The portal framework will automatically apply the parts when
        they become effective. You can use the Get Entitlements operation
        to see the parts that are in the queue.
        Each time this operation is invoked, it overwrites all existing
        entitlements, even the ones that are in the queue.

        Parmeters:
         :file: entitlement file
         :application: application identifier to be imported
        Returns:
         JSON response
        """
        url = "%s/importEntitlements" % self._url
        params = {
            "f" : "json",
            "appId" : application
        }
        files = {'file' : file}
        return self._con.post(path=url,
                              postdata=params,
                              files=files)
    #----------------------------------------------------------------------
    def remove_all(self, application):
        """
        This operation removes all entitlements from the portal for ArcGIS
        Pro or additional products such as Navigator for ArcGIS and revokes
        all entitlements assigned to users for the specified product. The
        portal is no longer a licensing portal for that product.
        License assignments are retained on disk. Therefore, if you decide
        to configure this portal as a licensing portal for the product
        again in the future, all licensing assignments will be available in
        the website.
        """
        params = {"f" : "json",
                  "appId" : application}
        url = "%s/removeAllEntitlements" % self._url
        return self._con.get(path=url, params=params)
    #----------------------------------------------------------------------
    def release_license(self, username):
        """
        If a user checks out an ArcGIS Pro license for offline or
        disconnected use, this operation releases the license for the
        specified account. A license can only be used with a single device
        running ArcGIS Pro. To check in the license, a valid access token
        and refresh token is required. If the refresh token for the device
        is lost, damaged, corrupted, or formatted, the user will not be
        able to check in the license. This prevents the user from logging
        in to ArcGIS Pro from any other device. As an administrator, you
        can release the license. This frees the outstanding license and
        allows the user to check out a new license or use ArcGIS Pro in a
        connected environment.
        """
        params = {"f" : "json",
                  "username" : username
                  }
        url = "%s/releaseLicense" % self._url
        return self._con.get(path=url, params=params)

