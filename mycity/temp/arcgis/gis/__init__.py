"""
The **gis** module provides an information model for GIS hosted
within ArcGIS Online or ArcGIS Enterprise.
This module provides functionality to manage
(create, read, update and delete) GIS users, groups and content. This module
is the most important and provides the entry point into the GIS.
"""
from __future__ import absolute_import

import base64
import json
import locale
import logging
import os
import re
import tempfile
import zipfile
import configparser
from contextlib import contextmanager
import functools
from datetime import datetime

import arcgis._impl.portalpy as portalpy
import arcgis.env
from arcgis._impl.common._mixins import PropertyMap
from arcgis._impl.common._utils import _DisableLogger
from arcgis._impl.connection import _is_http_url
from six.moves.urllib.error import HTTPError
_log = logging.getLogger(__name__)

class Error(Exception): pass

@contextmanager
def _tempinput(data):
    temp = tempfile.NamedTemporaryFile(delete=False)
    temp.write((bytes(data, 'UTF-8')))
    temp.close()
    yield temp.name
    os.unlink(temp.name)

def _lazy_property(fn):
    '''Decorator that makes a property lazy-evaluated.
    '''
    # http://stevenloria.com/lazy-evaluated-properties-in-python/
    attr_name = '_lazy_' + fn.__name__

    @property
    @functools.wraps(fn)
    def _lazy_property(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazy_property

class GIS(object):
    """
    .. _gis:

    A GIS is representative of a single ArcGIS Online organization or an ArcGIS Enterprise deployment. The GIS object
    provides helper objects to manage (search, create, retrieve) GIS resources such as content, users, and groups.

    Additionally, the GIS object has properties to query its state, which is accessible using the properties attribute.

    The GIS provides a mapping widget that can be used in the Jupyter Notebook environment for visualizing GIS content
    as well as the results of your analysis. To create a new map, call the map() method.

    The constructor constructs a GIS object given a url and user credentials to ArcGIS Online
    or an ArcGIS Enterprise Portal. User credentials can be passed in using username/password
    pair, or key_file/cert_file pair (in case of PKI). Supports built-in users, LDAP, PKI, Integrated Windows Authentication
    (using NTLM and Kerberos) and Anonymous access.

    If no url is provided, ArcGIS Online is used. If username/password
    or key/cert files are not provided, the currently logged-in user's credentials (IWA) or anonymous access is used.

    Persisted profiles for the GIS can be created by giving the GIS authorization credentials and
    specifying a profile name. The profile stores all of the authorization credentials (except the password) in the
    user's home directory in an unencrypted config file named .arcgisprofile. The profile securely stores the password
    in an O.S. specific password manager through the `keyring <https://pypi.python.org/pypi/keyring>`_ python module.
    (Note: Linux systems may need additional software installed and configured for proper security) Once a profile has
    been saved, passing the profile parameter by itself uses the authorization credentials saved in the configuration
    file/password manager by that profile name. Multiple profiles can be created and used in parallel.

    See https://developers.arcgis.com/python/guide/working-with-different-authentication-schemes/ for examples.


    ================    ===============================================================
    **Argument**        **Description**
    ----------------    ---------------------------------------------------------------
    url                 Optional string. If URL is None, then the URL will be ArcGIS
                        Online.  This should be a web address to either a local Portal
                        or to ArcGIS Online in the form:
                        <scheme>://<fully_qualified_domain_name>/<web_adaptor> (Portal Example)
                        https://gis.example.com/portal
    ----------------    ---------------------------------------------------------------
    username            Optional string. The login user name (case-sensitive).
    ----------------    ---------------------------------------------------------------
    password            Optional string. If a username is provided, a password is
                        expected.  This is case-sensitive. If the password is not
                        provided, the user is prompted in the interactive dialog.
    ----------------    ---------------------------------------------------------------
    key_file            Optional string. The file path to a user's key certificate for PKI
                        authentication
    ----------------    ---------------------------------------------------------------
    cert_file           Optional string. The file path to a user's certificate file for PKI
                        authentication
    ----------------    ---------------------------------------------------------------
    verify_cert         Optional boolean. If a site has an invalid SSL certificate or is
                        being accessed via the IP or hostname instead of the name on the
                        certificate, set this value to False.  This will ensure that all
                        SSL certificate issues are ignored.
                        The default is True.
                        **Warning** Setting the value to False can be a security risk.
    ----------------    ---------------------------------------------------------------
    set_active          Optional boolean. The default is True.  If True, the GIS object
                        will be used as the default GIS object throughout the whole
                        scripting session.
    ----------------    ---------------------------------------------------------------
    client_id           Optional string. Used for OAuth athentication.  This is the
                        client ID value.
    ----------------    ---------------------------------------------------------------
    profile             Optional string. the name of the profile that the user wishes to use
                        to authenticate, if set, the identified profile will be used to login
                        to the specified GIS.
    ================    ===============================================================

    In addition to explicitly named parameters, the GIS object supports optional key word
    arguments:

    ================    ===============================================================
    **kwargs**          **Description**
    ----------------    ---------------------------------------------------------------
    proxy_host          Optional string. The host name of the proxy server used to allow HTTP/S
                        access in the network where the script is run.
    ----------------    ---------------------------------------------------------------
    proxy_port          Optional integer. The proxy host port.  The default is 80.
    ----------------    ---------------------------------------------------------------
    token               Optional string. This is the Enterprise token for built-in
                        logins. This parameter is only honored if the username/password
                        is None and the security for the site uses BUILT-IN security.
    ================    ===============================================================




    .. code-block:: python

        # Usage Example 1: Anonymous Login to ArcGIS Online

        gis = GIS()

    .. code-block:: python

        # Usage Example 2: Built-in Login to ArcGIS Online

        gis = GIS(username="someuser", password="secret1234")

    .. code-block:: python

        # Usage Example 3: Built-in Login to ArcGIS Enterprise

        gis = GIS(url="http://pythonplayground.esri.com/portal",
              username="user1", password="password1")

    .. code-block:: python

        # Usage Example 4: Built-in Login to ArcGIS Enterprise, ignoring SSL errors

        gis = GIS(url="http://pythonplayground.esri.com/portal", username="user1",
                  password="password1", verify_cert=False)


    .. code-block:: python
        USAGE EXAMPLE 5: Anonymous ArcGIS Online Login with Proxy

    gis = GIS(proxy_host='127.0.0.1', proxy_port=8888)


    """
    _server_list = None
    # admin = None
    # oauth = None
    def __init__(self, url=None, username=None, password=None, key_file=None, cert_file=None,
                 verify_cert=True, set_active=True, client_id=None, profile=None, **kwargs):
        """
        Constructs a GIS object given a url and user credentials to ArcGIS Online
        or an ArcGIS Portal. User credentials can be passed in using username/password
        pair, or key_file/cert_file pair (in case of PKI). Supports built-in users, LDAP,
        PKI, Integrated Windows Authentication (using NTLM and Kerberos) and Anonymous access.

        If no url is provided, ArcGIS Online is used. If username/password
        or key/cert files are not provided, logged in user credentials (IWA) or anonymous access is used.

        Persisted profiles for the GIS can be created by giving the GIS authorization credentials and
        specifying a profile name. The profile stores all of the authorization credentials (except the password) in the
        user's home directory in an unencrypted config file named .arcgisprofile. The profile securely stores the password
        in an O.S. specific password manager through the `keyring <https://pypi.python.org/pypi/keyring>`_ python module.
        (Note: Linux systems may need additional software installed and configured for proper security) Once a profile has
        been saved, passing the profile parameter by itself uses the authorization credentials saved in the configuration
        file/password manager by that profile name. Multiple profiles can be created and used in parallel.

        If the GIS uses a secure (https) url, certificate verification is performed. If you are using self signed certificates
        in a testing environment and wish to disable certificate verification, you may specify verify_cert=False to disable
        certificate verification in the Python process. However, this should not be done in production environments and is
        strongly discouraged.
        """
        self._proxy_host = kwargs.pop('proxy_host', None)
        self._proxy_port = kwargs.pop('proxy_port', 80)

        from arcgis._impl.tools import _Tools

        if profile is not None:
            # Load config
            cfg_file_path = os.path.expanduser("~") + '/.arcgisprofile'
            config = configparser.ConfigParser()
            if os.path.isfile(cfg_file_path):
                config.read(cfg_file_path)

            # Update config to >v1.3 format if it's old
            if self._config_is_in_old_format(config):
                self._update_config_to_new_format(config)

            # Add any __init__() args to config/keyring store
            if profile not in config.keys():
                _log.info("Adding new profile {} to config...".format(profile))
                config.add_section(profile)
                self._add_timestamp_to_profile_data_in_config(config, profile)
            self._update_profile_data_in_config(config, profile, url, username,
                                                key_file, cert_file, client_id)
            if password is not None:
                self._securely_store_password(profile, password)
            self._write_any_config_changes_to_file(config, cfg_file_path)

            # Update __init__() args with data from config file/keyring store
            if config.has_option(profile,   "url"):
                url =       config[profile]["url"]
            if config.has_option(profile,   "username"):
                username =  config[profile]["username"]
            if config.has_option(profile,   "key_file"):
                key_file =  config[profile]["key_file"]
            if config.has_option(profile,   "cert_file"):
                cert_file = config[profile]["cert_file"]
            if config.has_option(profile,   "client_id"):
                client_id = config[profile]["client_id"]
            password = self._securely_get_password(profile)

        if url is None:
            url = "https://www.arcgis.com"
        if self._uri_validator(url) == False and str(url).lower() != 'pro':
            raise Exception("Malformed url provided: %s" % url)
        if username is not None and password is None:
            from getpass import getpass
            password = getpass('Enter password: ')

        self._url = url
        self._username = username
        self._password = password
        self._key_file = key_file
        self._cert_file = cert_file
        self._portal = None
        self._con = None
        self._verify_cert = verify_cert
        self._client_id = client_id
        self._datastores_list = None
        utoken = kwargs.pop('token', None)

        try:
            self._portal = portalpy.Portal(self._url, self._username,
                                           self._password, self._key_file,
                                           self._cert_file,
                                           proxy_host=self._proxy_host,
                                           proxy_port=self._proxy_port,
                                           verify_cert=self._verify_cert,
                                           client_id=self._client_id)
            if not (utoken is None):
                self._portal.con._token = utoken
                self._portal.con._auth = "BUILTIN"

        except Exception as e:
            if len(e.args) > 0 and str(type(e.args[0])) == "<class 'ssl.SSLError'>":
                raise RuntimeError("An untrusted SSL error occurred when attempting to connect to the provided GIS.\n"
                                   "If you trust this server and want to proceed, add 'verify_cert=False' as an "
                                   "argument when connecting to the GIS.")
            else:
                raise
        try:
            if url.lower().find("arcgis.com") > -1 and \
               self._portal.is_logged_in:
                from six.moves.urllib_parse import urlparse
                props = self._portal.get_properties(force=False)
                url = "%s://%s.%s" % (urlparse(self._url).scheme,
                                      props['urlKey'],
                                      props['customBaseUrl'])
                self._url = url
                pp =  portalpy.Portal(url,
                                      self._username,
                                      self._password,
                                      self._key_file,
                                      self._cert_file,
                                      verify_cert=self._verify_cert,
                                      client_id=self._client_id,
                                      proxy_port=self._proxy_port,
                                      proxy_host=self._proxy_host)
                self._portal = pp
        except: pass
        self._lazy_properties = PropertyMap(self._portal.get_properties(force=False))

        if self._url.lower() == "pro":
            self._url = self._portal.url

        self._con = self._portal.con

        if self._con._auth.lower() != 'anon' and \
           self._con._auth is not None and \
           hasattr(self.users.me, 'role') and \
           self.users.me.role == "org_admin":
            try:
                if self.properties.isPortal == True:
                    from .admin.portaladmin import PortalAdminManager
                    self.admin = PortalAdminManager(url="%s/portaladmin" % self._portal.url,
                                                    gis=self)
                else:
                    from .admin.agoladmin import AGOLAdminManager
                    self.admin = AGOLAdminManager(gis=self)
            except:
                pass
        elif self._con._auth.lower() != 'anon' and \
             self._con._auth is not None and\
             hasattr(self.users.me, 'role') and \
             self.users.me.role == 'org_publisher' and \
             self._portal.is_arcgisonline == False:
            try:
                from .admin.portaladmin import PortalAdminManager
                self.admin = PortalAdminManager(url="%s/portaladmin" % self._portal.url,
                                                gis=self, is_admin=False)
            except:
                pass
        elif self._con._auth.lower() != 'anon' and \
             self._con._auth is not None and\
             hasattr(self.users.me, 'privileges') and \
             self._portal.is_arcgisonline == False:
            privs = ['portal:publisher:publishFeatures',
                     'portal:publisher:publishScenes',
                     'portal:publisher:publishServerGPServices',
                     'portal:publisher:publishServerServices',
                     'portal:publisher:publishTiles']
            for priv in privs:
                if priv in self.users.me.privileges:
                    can_publish = True
                    break
                else:
                    can_publish = False
            if can_publish:
                try:
                    from .admin.portaladmin import PortalAdminManager
                    self.admin = PortalAdminManager(url="%s/portaladmin" % self._portal.url,
                                                    gis=self, is_admin=False)
                except:
                    pass
        if self._con._auth.lower() != 'anon' and \
           self._con._auth is not None and\
           hasattr(self.users.me, 'role') and \
           self.users.me.role == 'org_publisher' and \
           self._portal.is_arcgisonline == False:
            try:
                from .admin.portaladmin import PortalAdminManager
                self.admin = PortalAdminManager(url="%s/portaladmin" % self._portal.url,
                                                gis=self, is_admin=False)
            except:
                pass
        self._tools = _Tools(self)
        if set_active:
            arcgis.env.active_gis = self

    def _config_is_in_old_format(self, config):
        """ Any version <= 1.3 of the API used a different config file
        formatting that, among other things, did not store the last time
        a profile was modified. Thus, if 'date_modified' is not found in any
        profile, it is the old format
        """
        for profile in config.keys():
            if config[profile].name == "DEFAULT":
                #ignore the default profile (it's not user defined)
                continue
            if "date_modified" not in config[profile]:
                return True
        return False

    def _update_config_to_new_format(self, config):
        """ The new config file does not store the password at all, instead
        storing it through the keyring module (see below functions). The new
        config file also has a 'date_modified' field, and does not store the
        other fields in a rot13 character shifted fashion anymore.

        This function goes through all profiles in the .arcgisprofile file
        and makes it compatible with the new format. Note: this function just
        updates 'config' obj passed in; changes are written to file elsewhere
        """
        _log.info("Doing one time update of .arcgisprofile to new format...")
        attributes_to_rewrite_to_config = [ 'url', 'username', 'key_file',
                                            'cert_file', 'client_id' ]
        attributes_to_write_to_keyring = [ 'password' ]

        for profile in config.keys():
            for attr_key in config[profile].keys():
                unscrambled_attr_value = rot13(config[profile][attr_key],
                                               of=True)
                if attr_key in attributes_to_rewrite_to_config:
                    config[profile][attr_key] =  unscrambled_attr_value
                if attr_key in attributes_to_write_to_keyring:
                    self._securely_store_password(profile,
                                                  unscrambled_attr_value)
                    config.remove_option(profile, attr_key)
                self._add_timestamp_to_profile_data_in_config(config, profile)

    def _update_profile_data_in_config(self, config, profile, url = None,
                                       username = None, key_file = None,
                                       cert_file = None, client_id = None):
        """Updates the specific profile in the config object to include
        any of the user defined arguments. This will overwrite old values.
        ***USE THIS FUNCTION INSTEAD OF MANUALLY MODIFYING PROFILE DATA***
        """
        if url is not None:
            config[profile]["url"] = url
            self._add_timestamp_to_profile_data_in_config(config, profile)
        if username is not None:
            config[profile]["username"] = username
            self._add_timestamp_to_profile_data_in_config(config, profile)
        if key_file is not None:
            config[profile]["key_file"] = key_file
            self._add_timestamp_to_profile_data_in_config(config, profile)
        if cert_file is not None:
            config[profile]["cert_file"] = cert_file
            self._add_timestamp_to_profile_data_in_config(config, profile)
        if client_id is not None:
            config[profile]["client_id"] = client_id
            self._add_timestamp_to_profile_data_in_config(config, profile)

    def _add_timestamp_to_profile_data_in_config(self, config, profile):
        """Sets the 'date_modified' field to this moment's datetime"""
        config[profile]["date_modified"] = str(datetime.now())

    def _write_any_config_changes_to_file(self, config, cfg_file_path):
        """write the config object to the .arcgisprofile file"""
        config.write(open(cfg_file_path, "w"))

    def _securely_store_password(self, profile, password):
        """Securely stores the password in an O.S. specific store via the
        keyring package. Can be retrieved later with just the profile name.

        If keyring is not properly set up system-wide, raise a RuntimeError
        """
        import keyring
        if self._current_keyring_is_recommended():
            return keyring.set_password("arcgis_python_api_profile_passwords",
                                        profile,
                                        password)
        else:
            raise RuntimeError(self._get_keyring_failure_message())

    def _securely_get_password(self, profile):
        """Securely gets the profile specific password stored via keyring

        If keyring is not properly set up system-wide OR if a password is not
        found through keyring, log the respective warning and return 'None'
        """
        import keyring
        if self._current_keyring_is_recommended():
            # password will be None if no password is found for the profile
            password = keyring.get_password(
                "arcgis_python_api_profile_passwords",
                                         profile)
        else:
            password = None
            _log.warn(self._get_keyring_failure_message())

        if password is None:
            _log.warn("Profile {0} does not have a password on file through "\
                      "keyring. If you are expecting this behavior (PKI or "\
                      "IWA authentication, entering password through "\
                      "run-time prompt, etc.), please ignore this message. "\
                      "If you would like to store your password in the {0} "\
                      "profile, run GIS(profile = '{0}', password = ...). "\
                      "See the API doc for more details. "\
                      "(http://bit.ly/2CK2wG8)".format(profile))
        return password

    def _securely_delete_password(self, profile):
        """Securely deletes the profile specific password via keyring

        If keyring is not properly set up system-wide, log a warning
        """
        import keyring
        if self._current_keyring_is_recommended():
            return keyring.delete_password(
                "arcgis_python_api_profile_passwords",
                                         profile)
        else:
            _log.warn(self._get_keyring_failure_message())
            return False

    def _current_keyring_is_recommended(self):
        """The keyring project recommends 4 secure keyring backends. The
        defaults on Windows/OSX should be the recommended backends, but Linux
        needs some system-wide software installed and configured to securely
        function. Return if the current keyring is a supported, properly
        configured backend
        """
        import keyring
        supported_keyrings = [ keyring.backends.OS_X.Keyring,
                               keyring.backends.SecretService.Keyring,
                               keyring.backends.Windows.WinVaultKeyring,
                               keyring.backends.kwallet.DBusKeyring ]
        current_keyring = type(keyring.get_keyring())
        return current_keyring in supported_keyrings

    def _get_keyring_failure_message(self):
        """An informative failure msg about the backend keyring being used"""
        import keyring
        return "Keyring backend being used ({}) either failed to install "\
               "or is not recommended by the keyring project (i.e. it is "\
               "not secure). This means you can not use stored passwords "\
               "through GIS's persistent profiles. Note that extra system-"\
               "wide steps must be taken on a Linux machine to use the python "\
               "keyring module securely. Read more about this at the "\
               "keyring API doc (http://bit.ly/2EWDP7B) and the ArcGIS API "\
               "for Python doc (http://bit.ly/2CK2wG8)."\
               "".format(keyring.get_keyring())

    def _uri_validator(self, x):
        from urllib.parse import urlparse
        if x is None:
            return False
        try:
            result = urlparse(x)
            return result.scheme != "" and result.netloc != ""
        except:
            return False

    @_lazy_property
    def users(self):
        """
        The resource manager for GIS users.
        """
        return UserManager(self)

    @_lazy_property
    def groups(self):
        """
        The resource manager for GIS groups.
        """
        return GroupManager(self)

    @_lazy_property
    def content(self):
        """
        The resource manager for GIS content.
        """
        return ContentManager(self)

    # @_lazy_property
    # def ux(self):
    #     return UX(self)

    @_lazy_property
    def _datastores(self):
        """
        The list of datastores resource managers for sites federated with the GIS.
        """
        if self._datastores_list is not None:
            return self._datastores_list

        self._datastores_list = []
        try:
            res = self._portal.con.post("portals/self/servers", {"f": "json"})

            servers = res['servers']
            admin_url = None
            for server in servers:
                admin_url = server['adminUrl'] + '/admin'
                self._datastores_list.append(DatastoreManager(self, admin_url, server))
        except:
            pass
        return self._datastores_list

    @_lazy_property
    def properties(self):
        """
        The properties of the GIS.
        """
        return PropertyMap(self._get_properties(force=True))

    def update_properties(self, properties_dict):
        """Updates the GIS's properties from those in properties_dict.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        properties_dict     Required dictionary. A dictionary of just those properties and
                            values that are to be updated.
        ===============     ====================================================================


        :return:
           The item if successfully added, None if unsuccessful.
        """
        postdata = self._portal._postdata()
        postdata.update(properties_dict)

        resp = self._portal.con.post('portals/self/update', postdata)
        if resp:
            self._lazy_properties = PropertyMap(self._portal.get_properties(force=True))
            # delattr(self, '_lazy_properties') # force refresh of properties when queried next
            return resp.get('success')

    def __str__(self):
        return 'GIS @ ' + self._url

    def _repr_html_(self):
        """
        HTML Representation for IPython Notebook
        """
        return 'GIS @ <a href="' + self._url + '">' + self._url + '</a>'

    def _get_properties(self, force=False):
        """ Returns the portal properties (using cache unless force=True). """
        return self._portal.get_properties(force)

    def map(self, location=None, zoomlevel=None):
        """
        Creates a map widget centered at the declared location with the specified
        zoom level. If an address is provided, it is geocoded
        using the GIS's configured geocoders and if a match is found, the geographic
        extent of the matched address is used as the map extent. If a zoomlevel is also
        provided, the map is centered at the matched address instead and the map is zoomed
        to the specified zoomlevel.

        Note: The map widget is only supported within Jupyter Notebook.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        location               Optional string. The address or lat-long tuple of where the map is to be centered.
        ------------------     --------------------------------------------------------------------
        zoomlevel              Optional integer. The desired zoom level.
        ==================     ====================================================================


        :return:
          The map widget (displayed in Jupyter Notebook when queried).
        """
        try:
            from arcgis.widgets import MapView
            from arcgis.geocoding import get_geocoders, geocode
        except Error as err:
            _log.error("ipywidgets packages is required for the map widget.")
            _log.error("Please install it:\n\tconda install ipywidgets")

        if isinstance(location, Item) and location.type == 'Web Map':
            mapwidget = MapView(gis=self, item=location)
        else:
            mapwidget = MapView(gis=self)

            # Geocode the location
            if isinstance(location, str):
                for geocoder in get_geocoders(self):
                    locations = geocode(location, out_sr=4326, max_locations=1, geocoder=geocoder)
                    if len(locations) > 0:
                        if zoomlevel is not None:
                            loc = locations[0]['location']
                            mapwidget.center = loc['y'], loc['x']
                            mapwidget.zoom = zoomlevel
                        else:
                            mapwidget.extent = locations[0]['extent']
                        break

            # Center the map at the location
            elif isinstance(location, (tuple, list)):
                if all(isinstance(el, list) for el in location):
                    extent = {
                        'xmin': location[0][0],
                        'ymin': location[0][1],
                        'xmax': location[1][0],
                        'ymax': location[1][1]
                    }
                    mapwidget.extent = extent
                else:
                    mapwidget.center = location

            elif isinstance(location, dict): # geocode result
                if 'extent' in location and zoomlevel is None:
                    mapwidget.extent = location['extent']
                elif 'location' in location:
                    mapwidget.center = location['location']['y'], location['location']['x']
                    if zoomlevel is not None:
                        mapwidget.zoom = zoomlevel

            elif location is not None:
                print("location must be an address(string) or (lat, long) pair as a tuple")

        if zoomlevel is not None:
            mapwidget.zoom = zoomlevel

        return mapwidget

###########################################################################
class Datastore(dict):
    """
    Represents a datastore (folder, database or bigdata fileshare) within the GIS's data store.
    """
    def __init__(self, datastore, path):
        dict.__init__(self)
        self._datastore = datastore
        self._portal = datastore._portal
        self._admin_url = datastore._admin_url

        self.datapath = path


        params = { "f" : "json" }
        path = self._admin_url + "/data/items" + self.datapath

        datadict = self._portal.con.post(path, params, verify_cert=False)

        if datadict:
            self.__dict__.update(datadict)
            super(Datastore, self).update(datadict)

    def __getattr__(self, name): # support group attributes as group.access, group.owner, group.phone etc
        try:
            return dict.__getitem__(self, name)
        except:
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))

    def __getitem__(self, k): # support group attributes as dictionary keys on this object, eg. group['owner']
        try:
            return dict.__getitem__(self, k)
        except KeyError:
            params = { "f" : "json" }
            path = self._admin_url + "/data/items" + self.datapath

            datadict = self._portal.con.post(path, params, verify_cert=False)
            super(Datastore, self).update(datadict)
            self.__dict__.update(datadict)
            return dict.__getitem__(self, k)

    def __str__(self):
        return self.__repr__()
        # state = ["   %s=%r" % (attribute, value) for (attribute, value) in self.__dict__.items()]
        # return '\n'.join(state)

    def __repr__(self):
        return '<%s title:"%s" type:"%s">' % (type(self).__name__, self.path, self.type)

    @property
    def manifest(self):
        """
        Gets or sets the manifest resource for bigdata fileshares, as a dictionary.
        """
        data_item_manifest_url = self._admin_url + '/data/items' + self.datapath + "/manifest"

        params = {
            'f': 'json',
        }
        res = self._portal.con.post(data_item_manifest_url, params, verify_cert=False)
        return res

    @manifest.setter
    def manifest(self, value):
        """
        Updates the manifest resource for bigdata file shares.
        """
        manifest_upload_url =  self._admin_url + '/data/items' + self.datapath + '/manifest/update'

        with _tempinput(json.dumps(value)) as tempfilename:
            # Build the files list (tuples)
            files = []
            files.append(('manifest', tempfilename, os.path.basename(tempfilename)))

            postdata = {
                'f' : 'pjson'
            }

            resp = self._portal.con.post(manifest_upload_url, postdata, files, verify_cert=False)

            if resp['status'] == 'success':
                return True
            else:
                print(str(resp))
                return False

    @property
    def ref_count(self):
        """
        Gets the total number of references to this data item that exists on the server. You can use this
        property to determine if this data item can be safely deleted or taken down for maintenance.
        """
        data_item_manifest_url = self._admin_url + '/data/computeTotalRefCount'

        params = {
            'f': 'json',
            'itemPath': self.datapath
        }
        res = self._portal.con.post(data_item_manifest_url, params, verify_cert=False)
        return res["totalRefCount"]

    def delete(self):
        """
        Unregisters this data item from the data store.

        :return:
           A boolean indicating success (True) or failure (False).

        """
        params = {
            "f" : "json" ,
            "itempath" : self.datapath,
            "force": True
        }
        path = self._admin_url + "/data/unregisterItem"

        resp = self._portal.con.post(path, params, verify_cert=False)
        if resp:
            return resp.get('success')
        else:
            return False

    def update(self, item):
        """
        Edits this data item to update its connection information.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        item                Required dictionary. The representation of the updated item.
        ===============     ====================================================================


        :return:
           A boolean indicating success (True) or failure (False).
        """
        params = {
            "f" : "json" ,
            "item" : item
        }
        path = self._admin_url +  "/data/items" + self.datapath +  "/edit"

        resp = self._portal.con.post(path, params, verify_cert=False)
        if resp ['status'] == 'success':
            return True
        else:
            return False

    def validate(self):
        """
        Validates that this data item's path (for file shares) or connection string (for databases)
        is accessible to every server node in the site.

        :return:
           A boolean indicating success (True) or failure (False).
        """
        params = { "f" : "json" }
        path = self._admin_url + "/data/items" + self.datapath

        datadict = self._portal.con.post(path, params, verify_cert=False)

        params = {
            "f" : "json",
            "item": datadict
        }
        path = self._admin_url + "/data/validateDataItem"

        res = self._portal.con.post(path, params, verify_cert=False)
        return res['status'] == 'success'

    @property
    def datasets(self):
        """
        Gets the datasets in the data store, as a dictionary (currently implemented for big data file shares).
        """
        data_item_manifest_url = self._admin_url + '/data/items' + self.datapath + "/manifest"

        params = {
            'f': 'json',
        }
        res = self._portal.con.post(data_item_manifest_url, params, verify_cert=False)

        return res['datasets']

class DatastoreManager(object):
    """
    Helper class for managing the GIS data stores in on-premises ArcGIS Portals.
    This class is not created by users directly.
    Instances of this class are returned from arcgis.geoanalytics.get_datastores() and
    arcgis.raster.analytics.get_datastores() functions to get the corresponding datastores.
    Users call methods on this 'datastores' object to manage the datastores in a site
    federated with the portal.
    """
    def __init__(self, gis, admin_url, server):
        self._gis = gis
        self._portal = gis._portal
        self._admin_url = admin_url
        self._server = server

    def __str__(self):
        return '<%s for %s>' % (type(self).__name__, self._admin_url)

    def __repr__(self):
        return '<%s for %s>' % (type(self).__name__, self._admin_url)

    @property
    def config(self):
        """
        Gets or sets the data store configuration properties, which affect the behavior of the data holdings of the server. The properties include:
        blockDataCopy. When this property is False, or not set at all, copying data to the site when publishing services from a client application is allowed. This is the default behavior.
        When this property is True, the client application is not allowed to copy data to the site when publishing. Rather, the publisher is required to register data items through which the service being published can reference data. Values: True | False
        Note:
        If you specify the property as True, users will not be able to publish geoprocessing services and geocode services from composite locators. These service types require data to be copied to the server. As a workaround, you can temporarily set the property to False, publish the service, and then set the property back to True.
        """
        params = {"f" : "json"}
        path = self._admin_url + "/data/config"
        res = self._portal.con.post(path, params, verify_cert=False)
        return res

    @config.setter
    def config(self, value):
        """
        The data store configuration properties affect the behavior of the data holdings of the server. The properties include:
        blockDataCopy—When this property is False, or not set at all, copying data to the site when publishing services from a client application is allowed. This is the default behavior.
        When this property is True, the client application is not allowed to copy data to the site when publishing. Rather, the publisher is required to register data items through which the service being published can reference data. Values: True | False
        Note:
        If you specify the property as True, users will not be able to publish geoprocessing services and geocode services from composite locators. These service types require data to be copied to the server. As a workaround, you can temporarily set the property to False, publish the service, and then set the property back to True.
        """
        params = {"f" : "json"}
        params['datastoreConfig'] = value
        path = self._admin_url + "/data/config/update"
        res = self._portal.con.post(path, params)
        return res

    def add_folder(self,
                   name,
                   server_path,
                   client_path=None):

        """
        Registers a folder with the data store.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        name                Required string. The unique fileshare name on the server.
        ---------------     --------------------------------------------------------------------
        server_path         Required string. The path to the folder from the server (and client, if shared path).
        ---------------     --------------------------------------------------------------------
        client_path         Optional string. If folder is replicated, the path to the folder from the client.
        ===============     ====================================================================


        :return:
           The folder if registered successfully, None otherwise.
        """
        conn_type = "shared"
        if client_path is not None:
            conn_type = "replicated"

        item = {
            "type" : "folder",
            "path" : "/fileShares/" + name,
            "info" : {
                "path" : server_path,
                "dataStoreConnectionType" : conn_type
            }
        }

        if client_path is not None:
            item['clientPath'] = client_path

        params = {
            "f" : "json",
            "item" : item
        }
        if self._validate_item(item=params['item']) == False:
            raise Exception("Could not register the folder.")
        path = self._admin_url + "/data/registerItem"
        res = self._portal.con.post(path, params, verify_cert=False)
        if res['status'] == 'success' or res['status'] == 'exists':
            return Datastore(self, "/fileShares/" + name)
        else:
            print(str(res))
            return None

    def add_bigdata(self,
                    name,
                    server_path=None):
        """
        Registers a bigdata fileshare with the data store.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        name                Required string. The unique bigdata fileshare name on the server.
        ---------------     --------------------------------------------------------------------
        server_path         Optional string. The path to the folder from the server.
        ===============     ====================================================================


        :return:
           The big data fileshare if registered successfully, None otherwise.
        """
        output = None
        path = self._admin_url + "/data/registerItem"

        pattern = r'\\\\[a-zA-Z]+'
        if re.match(pattern, server_path) is not None:  # starts with double backslash, double the backslashes
            server_path = server_path.replace('\\', '\\\\')

        path_str = '{"path":"' + server_path + '"}'
        params = {
            'f': 'json',
            'item' : json.dumps({
                "path": "/bigDataFileShares/" + name,
                "type": "bigDataFileShare",

                "info": {
                    "connectionString": path_str,
                    "connectionType": "fileShare"
                }
            })
        }
        if self._validate_item(item=params['item']) == False:
            raise Exception("Could not register the path.")
        res = self._portal.con.post(path, params, verify_cert=False)

        if res['status'] == 'success' or res['status'] == 'exists':
            output = Datastore(self, "/bigDataFileShares/" + name)

        if res['success']:
            print("Created Big Data file share for " + name)
        elif res['success'] == False and res['status'] != 'exists':
            raise Exception("Could not create Big Data file share: %s" % name)
        elif res['status'] == 'exists':
            print("Big Data file share exists for " + name)

        return output

    def add_database(self,
                     name,
                     conn_str,
                     client_conn_str=None,
                     conn_type="shared"):
        """
        Registers a database with the data store.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        name                Required string. The unique database name on the server.
        ---------------     --------------------------------------------------------------------
        conn_str            Required string. the path to the folder from the server (and client, if shared or serverOnly database).
        ---------------     --------------------------------------------------------------------
        client_conn_str     Optional string. The connection string for client to connect to replicated enterprise database.
        ---------------     --------------------------------------------------------------------
        conn_type           Optional string. Choice of "<shared|replicated|serverOnly>", shared is the default.
        ===============     ====================================================================


        :return:
           The database if registered successfully, None otherwise.
        """

        item = {
            "type" : "egdb",
            "path" : "/enterpriseDatabases/" + name,
            "info" : {
                "connectionString" : conn_str,
                "dataStoreConnectionType" : conn_type
            }
        }

        if client_conn_str is not None:
            item['info']['clientConnectionString'] = client_conn_str

        is_managed = False
        if conn_type == "serverOnly":
            is_managed = True

        item['info']['isManaged'] = is_managed

        params = {
            "f" : "json",
            "item" : item
        }
        if self._validate_item(params['item']) == False:
            raise Exception("Invalid item.")
        path = self._admin_url + "/data/registerItem"
        res = self._portal.con.post(path, params, verify_cert=False)
        if res['status'] == 'success' or res['status'] == 'exists':
            return Datastore(self, "/enterpriseDatabases/" + name)
        else:
            print(str(res))
            return None

    def add(self,
            name,
            item):
        """
        Registers a new data item with the data store.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        name                Required string. The name of the item to be added on the server.
        ---------------     --------------------------------------------------------------------
        item                Required dictionary. The dictionary representing the data item.  See http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r3000001s9000000
        ===============     ====================================================================


        :return:
           The new data item if registered successfully, None otherwise.
        """
        params = {
            "f" : "json"
        }

        params['item'] = item
        if self._validate_item(params['item']) == False:
            raise Exception("Invalid item.")
        path = self._admin_url + "/data/registerItem"
        res = self._portal.con.post(path, params, verify_cert=False)
        if res['status'] == 'success' or res['status'] == 'exists':
            return Datastore(self, "/enterpriseDatabases/" + name)
        else:
            print(str(res))
            return None

    def get(self, path):
        """
        Returns the data item object at the given path.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        path                Required string. The path for the data item.
        ===============     ====================================================================


        :return:
           The data item object if found, None otherwise.
        """
        params = { "f" : "json" }
        urlpath = self._admin_url + "/data/items" + path

        datadict = self._portal.con.post(urlpath, params, verify_cert=False)
        if 'status' not in datadict:
            return Datastore(self, path)
        else:
            print(datadict['messages'])
            return None

    def search(self, parent_path=None, ancestor_path=None,
               types=None, id=None):
        """
           You can use this operation to search through the various data
           items registered in the server's data store. Searching without
           specifying the parent path and other parameters returns a list
           of all registered data items.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        parentPath          Optional string. The path of the parent under which to find items.
                            Pass '/' to get the root data items.
        ---------------     --------------------------------------------------------------------
        ancestorPath        Optional string. The path of the ancestor under which to find items.
        ---------------     --------------------------------------------------------------------
        types               Optional string. A comma separated filter for the type of the items.
                            Types include folder, egdb, bigDataFileShare, datadir.
        ---------------     --------------------------------------------------------------------
        id                  Optional string. A filter to search by the ID of the item.
        ===============     ====================================================================


        :return:
           A list of data items matching the specified query.
        """
        params = {
            "f" : "json",
        }
        if parent_path is None and ancestor_path is None and types is None and id is None:
            ancestor_path = '/'
        if parent_path is not None:
            params['parentPath'] = parent_path
        if ancestor_path is not None:
            params['ancestorPath'] = ancestor_path
        if types is not None:
            params['types'] = types
        if id is not None:
            params['id'] = id


        path = self._admin_url + "/data/findItems"


        dataitems = []

        res = self._portal.con.post(path, params, verify_cert=False)
        for item in res['items']:
            dataitems.append(Datastore(self, item['path']))
        return dataitems

    def _validate_item(self, item):
        """validates a BDS connection"""
        url = self._admin_url + "/data/validateDataItem"
        params = {
            'f' : 'json',
            'item' : item
        }
        res = self._portal.con.post(url, params, verify_cert=False)
        try:
            return res['status'] == 'success'
        except:
            return False

    def validate(self):
        """
        Validates all items in the datastore. In order for a data item to be registered and
        used successfully within the GIS's data store, you need to make sure that the path
        (for file shares) or connection string (for databases) is accessible to every server
        node in the site. To validate all registered data items all
        at once, you can invoke this operation.

        :return:
           True if the data store items were validated, False if not.
        """
        params = {"f" : "json"}
        path = self._admin_url + "/data/validateAllDataItems"
        res = self._portal.con.post(path, params, verify_cert=False)
        return res['status'] == 'success'
###########################################################################
class UserManager(object):
    """
    Helper class for managing GIS users. This class is not created by users directly.
    An instance of this class, called 'users', is available as a property of the Gis object.
    Users call methods on this 'users' object to manipulate (create, get, search, etc) users.
    """
    def __init__(self, gis):
        self._gis = gis
        self._portal = gis._portal

    def create(self, username, password, firstname, lastname, email, description=None, role='org_user',
               provider='arcgis', idp_username=None, level=2, thumbnail=None):
        """
        This operation is used to pre-create built-in or enterprise accounts within the portal,
        or built-in users in an ArcGIS Online organization account. Only an administrator
        can call this method.

        To create a viewer account, choose role='org_viewer' and level=1

        .. note:
            When Portal for ArcGIS is connected to an enterprise identity store, enterprise users sign
            into portal using their enterprise credentials. By default, new installations of Portal for
            ArcGIS do not allow accounts from an enterprise identity store to be registered to the portal
            automatically. Only users with accounts that have been pre-created can sign in to the portal.
            Alternatively, you can configure the portal to register enterprise accounts the first time
            the user connects to the website.

        ================  ===============================================================================
        **Argument**      **Description**
        ----------------  -------------------------------------------------------------------------------
        username          Required string. The user name, which must be unique in the Portal, and
                          6-24 characters long.
        ----------------  -------------------------------------------------------------------------------
        password          Required string. The password for the user.  It must be at least 8 characters.
                          This is a required parameter only if
                          the provider is arcgis; otherwise, the password parameter is ignored.
                          If creating an account in an ArcGIS Online org, it can be set as None to let
                          the user set their password by clicking on a link that is emailed to him/her.
        ----------------  -------------------------------------------------------------------------------
        firstname         Required string. The first name for the user
        ----------------  -------------------------------------------------------------------------------
        lastname          Required string. The last name for the user
        ----------------  -------------------------------------------------------------------------------
        email             Required string. The email address for the user. This is important to have correct.
        ----------------  -------------------------------------------------------------------------------
        description       Optional string. The description of the user account.
        ----------------  -------------------------------------------------------------------------------
        thumbnail         Optional string. The URL to user's image.
        ----------------  -------------------------------------------------------------------------------
        role              Optional string. The role for the user account. The default value is org_user.
                          Other possible values are org_publisher, org_admin, org_viewer.
        ----------------  -------------------------------------------------------------------------------
        provider          Optional string. The provider for the account. The default value is arcgis.
                          The other possible value is enterprise.
        ----------------  -------------------------------------------------------------------------------
        idp_username      Optional string. The name of the user as stored by the enterprise user store.
                          This parameter is only required if the provider parameter is enterprise.
        ----------------  -------------------------------------------------------------------------------
        level             Optional string. The account level.
                          See http://server.arcgis.com/en/portal/latest/administer/linux/roles.htm
        ================  ===============================================================================

        :return:
            The user if successfully created, None if unsuccessful.

        """
        #map role parameter of a viewer to the internal value for org viewer.
        if role == 'org_viewer':
            role = 'iAAAAAAAAAAAAAAA'

        if self._gis._portal.is_arcgisonline:
            email_text = '''<html><body><p>''' + self._gis.properties.user.fullName + \
                ''' has invited you to join an ArcGIS Online Organization, ''' + self._gis.properties.name + \
                         '''</p>
<p>Please click this link to finish setting up your account and establish your password: <a href="https://www.arcgis.com/home/newuser.html?invitation=@@invitation.id@@">https://www.arcgis.com/home/newuser.html?invitation=@@invitation.id@@</a></p>
<p>Note that your account has already been created for you with the username, <strong>@@touser.username@@</strong>.  </p>
<p>If you have difficulty signing in, please contact ''' + self._gis.properties.user.fullName + \
                                                         '(' + self._gis.properties.user.email + '''). Be sure to include a description of the problem, the error message, and a screenshot.</p>
<p>For your reference, you can access the home page of the organization here: <br>''' + self._gis.properties.user.fullName + '''</p>
<p>This link will expire in two weeks.</p>
<p style="color:gray;">This is an automated email. Please do not reply.</p>
</body></html>'''
            params = {
                'f': 'json',
                'invitationList' : {'invitations' : [ {
                    'username': username,
                    'firstname': firstname,
                    'lastname': lastname,
                    'fullname': firstname + ' ' + lastname,
                    'email': email,
                    'role': role,
                    'level': level
                    } ] },
                'subject' : 'An invitation to join an ArcGIS Online organization, ' + self._gis.properties.name,
                'html' : email_text
            }
            if idp_username is not None:
                if provider is None:
                    provider = 'enterprise'
                params['invitationList']['invitations'][0]['targetUserProvider'] = provider
                params['invitationList']['invitations'][0]['idpUsername'] = idp_username
            if password is not None:
                params['invitationList']['invitations'][0]['password'] = password

            resp = self._portal.con.post('portals/self/invite', params, ssl=True)
            if resp and resp.get('success'):
                if username in resp['notInvited']:
                    print('Unable to create ' + username)
                    _log.error('Unable to create ' + username)
                    return None
                else:
                    return self.get(username)
        else:
            createuser_url = self._portal.url + "/portaladmin/security/users/createUser"
            #print(createuser_url)
            params = {
                'f': 'json',
                'username' : username,
                'password' : password,
                'firstname' : firstname,
                'lastname' : lastname,
                'email' : email,
                'description' : description,
                'role' : role,
                'provider' : provider,
                'idpUsername' : idp_username,
                'level' : level
            }
            self._portal.con.post(createuser_url, params)
            user = self.get(username)
            if thumbnail is not None:
                ret = user.update(thumbnail=thumbnail)
                if not ret:
                    _log.error('Unable to update the thumbnail for  ' + username)
            return user

    def signup(self, username, password, fullname, email):
        """
        Signs up a user to an instance of Portal for ArcGIS.

        .. note:
            This method only applies to Portal and not ArcGIS
            Online.  This method can be called anonymously, but
            keep in mind that self-signup can also be disabled
            in a Portal.  It also only creates built-in
            accounts, it does not work with enterprise
            accounts coming from ActiveDirectory or your
            LDAP.

        ================  ========================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------
        username          Required string. The desired username, which must be unique in the Portal,
                          and at least 4 characters.
        ----------------  --------------------------------------------------------
        password          Required string. The passowrd, which must be at least 8 characters.
        ----------------  --------------------------------------------------------
        fullname          Required string. The full name of the user.
        ----------------  --------------------------------------------------------
        email             Required string. The email address for the user. This is important to have correct.
        ================  ========================================================

        :return:
            The user if successfully created, None if unsuccessful.

        """
        success = self._portal.signup(username, password, fullname, email)
        if success:
            return User(self._gis, username)
        else:
            return None

    def get(self, username):
        """
        Returns the user object for the specified username.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        username               Required string. The user to get as an object.
        ==================     ====================================================================


        :return:
            The user object if successfully found, None if unsuccessful.
        """
        try:
            with _DisableLogger():
                user = self._portal.get_user(username)
        except RuntimeError as re:
            if re.args[0].__contains__("User does not exist or is inaccessible"):
                return None
            else:
                raise re

        if user is not None:
            return User(self._gis, user['username'], user)
        return None

    def search(self, query=None, sort_field='username', sort_order='asc', max_users=100, outside_org=False):
        """
        Searches portal users.

        Returns a list of users matching the specified query

        .. note::
            A few things that will be helpful to know.

            1. The query syntax has quite a few features that can't
               be adequately described here.  The query syntax is
               available in ArcGIS help.  A short version of that URL
               is http://bitly.com/1fJ8q31.

            2. Searching without specifying a query parameter returns
               a list of all users in your organization.

            3. Most of the time when searching users you want to
               search within your organization in ArcGIS Online
               or within your Portal.  As a convenience, the method
               automatically appends your organization id to the query by
               default.  If you don't want the API to append to your query
               set outside_org to True.  If you use this feature with an
               OR clause such as field=x or field=y you should put this
               into parenthesis when using outside_org.

        ================  ========================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------
        query             Optional string. The query string.  See notes above. Pass None
                          to get list of all users in the organization.
        ----------------  --------------------------------------------------------
        sort_field        Optional string. Valid values can be username (the default) or created.
        ----------------  --------------------------------------------------------
        sort_order        Optional string. Valid values are asc (the default) or desc.
        ----------------  --------------------------------------------------------
        max_users         Optional integer. The maximum number of users to be returned. The default is 100.
        ----------------  --------------------------------------------------------
        outside_org       Optional boolean. This controls whether to search outside
                          your organization. The default is False (search only
                          within your organization).
        ================  ========================================================

        :return:
            A list of users.
        """
        if query is None:
            users = self._portal.get_org_users(max_users)
            return [User(self._gis, u['username'], u) for u in users]
        else:
            userlist = []

            users = self._portal.search_users(query, sort_field, sort_order, max_users, outside_org)
            for user in users:
                userlist.append(User(self._gis, user['username'], user))
            return userlist

        #TODO: remove org users, invite users

    @property
    def me(self):
        """ Gets the logged in user.
        """
        meuser = self._portal.logged_in_user()
        if meuser is not None:
            return User(self._gis, meuser['username'], meuser)
        else:
            return None

    @property
    def roles(self):
        """Helper object to manage custom roles for users"""
        return RoleManager(self._gis)


class RoleManager(object):
    """Helper class to manage custom roles for users in a GIS."""

    def __init__(self, gis):
        """Creates helper object to manage custom roles in the GIS"""
        self._gis = gis
        self._portal = gis._portal


    def create(self, name, description, privileges=None):
        """Creates a custom role with the specified parameters.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        name                   Required string. The custom role's name.
        ------------------     --------------------------------------------------------------------
        description            Required string. The custom role's description.
        ------------------     --------------------------------------------------------------------
        privileges             Optional string. An array of strings with predefined permissions within
                               each privilege.  For supported privileges see
                               http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#/Privileges/02r3000002wq000000/
        ==================     ====================================================================


        :return:
           The custom role if successfully created, None if unsuccessful.
        """
        if self.exists(role_name=name) == False:
            role_id = self._portal.create_role(name, description)
            if role_id is not None:
                role_data = {
                    "id": role_id,
                  "name": name,
                  "description": description
                }
                role = Role(self._gis, role_id, role_data)
                role.privileges = privileges
                return role
            else:
                return None
        else:
            n = str(name.lower())
            roles = [r for r in self.all() \
                     if r.name.lower() == n]
            return roles[0]
        return None

    def exists(self, role_name):
        """
        Checks to see if a role exists given the declared role name.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        role_name              Required string. The name of the role to determine if it exists or not.
        ==================     ====================================================================

        :return:
           True if the role exists, and False if it does not.
        """
        for role in self.all():
            if role.name.lower() == role_name.lower():
                return True
        return False

    def all(self, max_roles=1000):
        """
        Provides the list of all roles in the GIS.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        max_roles              Required integer. The maximum number of roles to be returned, defaults to 1000.
        ==================     ====================================================================

        :return:
           The list of all roles in the GIS.
        """
        roles = self._portal.get_org_roles(max_roles)
        return [Role(self._gis, role['id'], role) for role in roles]


    def get_role(self, role_id):
        """
        Retrieves the role with the specified role ID.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        role_id                Required string. The role ID of the role to get. Set to None to get all roles
        ==================     ====================================================================

        :return:
           The role associated with the specified role ID, or a list of all roles if role_id was set to None.
        """
        role = self._portal.con.post('portals/self/roles/' + role_id, self._portal._postdata())
        return Role(self._gis, role['id'], role)


class Role(object):
    """A custom role in the GIS."""
    def __init__(self, gis, role_id, role):
        """Create a custom role"""
        self._gis = gis
        self._portal = gis._portal
        self.role_id = role_id
        if role is not None:
            self._name = role['name']
            self._description = role['description']

    def __repr__(self):
        return '<Role name: ' + self.name + ', description: ' + self.description + '>'

    def ___str___(self):
        return 'Custom Role name: ' + self.name + ', description: ' + self.description

    @property
    def name(self):
        """Gets and sets the name of the custom role."""
        return self._name

    @name.setter
    def name(self, value):
        """Name of the custom role"""
        self._name = value
        self._update_role()

    @property
    def description(self):
        """Gets and sets the description of the custom role."""
        return self._description

    @description.setter
    def description(self, value):
        """Description of the custom role"""
        self._description = value
        self._update_role()

    def _update_role(self):
        """Updates the name or description of this role"""
        postdata = self._portal._postdata()
        postdata['name'] = self._name
        postdata['description'] = self._description

        resp = self._portal.con.post('portals/self/roles/' + self.role_id + '/update', postdata)
        if resp:
            return resp.get('success')

    @property
    def privileges(self):
        """
        Get or sets the privileges for the custom role as a list of strings.

        Supported privileges with predefined permissions are:

        *Administrative Privileges:*

        Members

        - portal:admin:viewUsers: grants the ability to view full member account information within organization.
        - portal:admin:updateUsers: grants the ability to update member account information within organization.
        - portal:admin:deleteUsers: grants the ability to delete member accounts within organization.
        - portal:admin:inviteUsers: grants the ability to invite members to organization. (This privilege is only applicable to ArcGIS Online.)
        - portal:admin:disableUsers: grants the ability to enable and disable member accounts within organization.
        - portal:admin:changeUserRoles: grants the ability to change the role a member is assigned within organization; however, it does not grant the ability to promote a member to, or demote a member from, the Administrator role. That privilege is reserved for the Administrator role alone.
        - portal:admin:manageLicenses: grants the ability to assign licenses to members of organization.
        - portal:admin:reassignUsers: grants the ability to assign all groups and content of a member to another within organization.

        Groups

        - portal:admin:viewGroups: grants the ability to view all groups within organization.
        - portal:admin:updateGroups: grants the ability to update groups within organization.
        - portal:admin:deleteGroups: grants the ability to delete groups within organization.
        - portal:admin:reassignGroups: grants the ability to reassign groups to other members within organization.
        - portal:admin:assignToGroups: grants the ability to assign members to, and remove members from, groups within organization.
        - portal:admin:manageEnterpriseGroups: grants the ability to link group membership to an enterprise group. (This privilege is only applicable to Portal for ArcGIS.)

        Content

        - portal:admin:viewItems: grants the ability to view all content within organization.
        - portal:admin:updateItems: grants the ability to update content within organization.
        - portal:admin:deleteItems: grants the ability to delete content within organization.
        - portal:admin:reassignItems: grants the ability to reassign content to other members within organization.
        - portal:admin:shareToGroup: grants the ability to share other member's content to groups the user belongs to.
        - portal:admin:shareToOrg: grants the ability to share other member's content to organization.
        - portal:admin:shareToPublic: grants the ability to share other member's content to all users of the portal.

        ArcGIS Marketplace Subscriptions

        - marketplace:admin:purchase: grants the ability to request purchase information about apps and data in ArcGIS Marketplace. (This privilege is only applicable to ArcGIS Online.)
        - marketplace:admin:startTrial: grants the ability to start trial subscriptions in ArcGIS Marketplace. (This privilege is only applicable to ArcGIS Online.)
        - marketplace:admin:manage: grants the ability to create listings, list items and manage subscriptions in ArcGIS Marketplace. (This privilege is only applicable to ArcGIS Online.)

        *Publisher Privileges:*

        Content

        - portal:publisher:publishFeatures: grants the ability to publish hosted feature layers from shapefiles, CSVs, etc.
        - portal:publisher:publishTiles: grants the ability to publish hosted tile layers from tile packages, features, etc.
        - portal:publisher:publishScenes: grants the ability to publish hosted scene layers.

        *User Privileges:*

        Groups

        - portal:user:createGroup: grants the ability for a member to create, edit, and delete their own groups.
        - portal:user:joinGroup: grants the ability to join groups within organization.
        - portal:user:joinNonOrgGroup: grants the ability to join groups external to the organization. (This privilege is only applicable to ArcGIS Online.)

        Content

        - portal:user:createItem: grants the ability for a member to create, edit, and delete their own content.

        Sharing

        - portal:user:shareToGroup: grants the ability to share content to groups.
        - portal:user:shareToOrg: grants the ability to share content to organization.
        - portal:user:shareToPublic: grants the ability to share content to all users of portal.
        - portal:user:shareGroupToOrg: grants the ability to make groups discoverable by the organization.
        - portal:user:shareGroupToPublic: grants the ability to make groups discoverable by all users of portal.

        Premium Content

        - premium:user:geocode: grants the ability to perform large-volume geocoding tasks with the Esri World Geocoder such as publishing a CSV of addresses as hosted feature layer.
        - premium:user:networkanalysis: grants the ability to perform network analysis tasks such as routing and drive-time areas.
        - premium:user:geoenrichment: grants the ability to geoenrich features.
        - premium:user:demographics: grants the ability to make use of premium demographic data.
        - premium:user:spatialanalysis: grants the ability to perform spatial analysis tasks.
        - premium:user:elevation: grants the ability to perform analytical tasks on elevation data.

        Features

        - features:user:edit: grants the ability to edit features in editable layers, according to the edit options enabled on the layer.
        - features:user:fullEdit: grants the ability to add, delete, and update features in a hosted feature layer regardless of the editing options enabled on the layer.

        Open Data

        - opendata:user:openDataAdmin: grants the ability to manage Open Data Sites for the organization. (This privilege is only applicable to ArcGIS Online.)
        - opendata:user:designateGroup: grants the ability to designate groups within organization as being available for use in Open Data. (This privilege is only applicable to ArcGIS Online.)

        """
        resp = self._portal.con.post('portals/self/roles/' + self.role_id + '/privileges', self._portal._postdata())
        if resp:
            return resp.get('privileges')
        else:
            return None

    @privileges.setter
    def privileges(self, value):
        """Privileges for the custom role as a list of strings"""
        postdata = self._portal._postdata()
        postdata['privileges'] = { 'privileges' : value }

        resp = self._portal.con.post('portals/self/roles/' + self.role_id + '/setPrivileges', postdata)
        if resp:
            return resp.get('success')

    def delete(self):
        """Deletes this role.

        :return:
           A boolean indicating success (True) or failure (False).
        """
        resp = self._portal.con.post('portals/self/roles/' + self.role_id + '/delete', self._portal._postdata())
        if resp:
            return resp.get('success')


class GroupManager(object):
    """
    Helper class for managing GIS groups. This class is not created by users directly.
    An instance of this class, called 'groups', is available as a property of the Gis object.
    Users call methods on this 'groups' object to manipulate (create, get, search, etc) users.
    """
    def __init__(self, gis):
        self._gis = gis
        self._portal = gis._portal

    def create(self, title, tags, description=None,
               snippet=None, access='public', thumbnail=None,
               is_invitation_only=False, sort_field='avgRating',
               sort_order='desc', is_view_only=False, auto_join=False,
               provider_group_name=None, provider=None,
               max_file_size=None, users_update_items=False):
        """
        Creates a group with the values for any particular arguments that are specified.
        Only title and tags are required.


        ====================  =========================================================
        **Argument**          **Description**
        --------------------  ---------------------------------------------------------
        title                 Required string. The name of the group.
        --------------------  ---------------------------------------------------------
        tags                  Required string. A comma-delimited list of tags, or
                              list of tags as strings.
        --------------------  ---------------------------------------------------------
        description           Optional string. A detailed description of the group.
        --------------------  ---------------------------------------------------------
        snippet               Optional string.  A short snippet (<250 characters)
                              that summarizes the group.
        --------------------  ---------------------------------------------------------
        access                Optional string. Choices are private, public, or org.
        --------------------  ---------------------------------------------------------
        thumbnail             Optional string. URL or file location to a group image.
        --------------------  ---------------------------------------------------------
        is_invitation_only    Optional boolean. Defines whether users can join by
                              request. Default is False meaning users can ask to join
                              by request or join by invitation.
        --------------------  ---------------------------------------------------------
        sort_field            Optional string. Specifies how shared items with
                              the group are sorted.
        --------------------  ---------------------------------------------------------
        sort_order            Optional string.  Choices are asc or desc for ascending
                              or descending, respectively.
        --------------------  ---------------------------------------------------------
        is_view_only          Optional boolean. Defines whether the group is searchable.
                              Default is False meaning the group is searchable.
        --------------------  ---------------------------------------------------------
        auto_join             Optional boolean. Only applies to org accounts. If True,
                              this group will allow joining without requesting
                              membership approval. Default is False.

        --------------------  ---------------------------------------------------------
        provider_group_name   Optional string. The name of the domain group.
        --------------------  ---------------------------------------------------------
        provider              Optional string. Name of the provider.
        --------------------  ---------------------------------------------------------
        max_file_size         Optional integer.  This is the maximum file size allowed
                              be uploaded/shared to a group. Default value is: 1024000
        --------------------  ---------------------------------------------------------
        users_update_items    Optional boolean.  Members can update all items in this
                              group.  Updates to an item can include changes to the
                              item's description, tags, metadata, as well as content.
                              This option can't be disabled once the group has
                              been created. Default is False.
        ====================  =========================================================

        :return:
            The group if successfully created, None if unsuccessful.
        """
        if max_file_size is None:
            max_file_size = 1024000
        if users_update_items is None:
            users_update_items = False

        if type(tags) is list:
            tags = ",".join(tags)
        params = {
            'title' : title, 'tags' : tags, 'description' : description,
            'snippet' : snippet, 'access' : access, 'sortField' : sort_field,
            'sortOrder' : sort_order, 'isViewOnly' : is_view_only,
            'isinvitationOnly' : is_invitation_only,
            'autoJoin': auto_join}
        if provider_group_name:
            params['provider'] = provider
            params['providerGroupName'] = provider_group_name
        if users_update_items == True:
            params['capabilities'] = "updateitemcontrol"
        else:
            params['capabilities'] = ""
        params['MAX_FILE_SIZE'] = max_file_size

        group = self._portal.create_group_from_dict(params, thumbnail)

        if group is not None:
            return Group(self._gis, group['id'], group)
        else:
            return None

    def create_from_dict(self, dict):
        """
        Creates a group via a dictionary with the values for any particular arguments that are specified.
        Only title and tags are required.


        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        dict                   Required dictionary. A dictionary of entries to create/define the
                               group.  See help of the create() method for parameters.
        ==================     ====================================================================


        :return:
            The group if successfully created, None if unsuccessful.
        """
        thumbnail = dict.pop("thumbnail", None)

        if 'tags' in dict:
            if type(dict['tags']) is list:
                dict['tags'] = ",".join(dict['tags'])

        group = self._portal.create_group_from_dict(dict, thumbnail)
        if group is not None:
            return Group(self._gis, group['id'], group)
        else:
            return None

    def get(self, groupid):
        """
        Returns the group object for the specified groupid.


        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        groupid                Required string. The group identifier.
        ==================     ====================================================================


        :return:
           The group object if the group is found, None if it is not found.
        """
        try:
            group = self._portal.get_group(groupid)
        except RuntimeError as re:
            if re.args[0].__contains__("Group does not exist or is inaccessible"):
                return None
            else:
                raise re

        if group is not None:
            return Group(self._gis, groupid, group)
        return None

    def search(self, query='', sort_field='title', sort_order='asc',
               max_groups=1000, outside_org=False, categories=None):
        """
        Searches for portal groups.

        .. note::
            A few things that will be helpful to know.

            1. The query syntax has many features that can't
                be adequately described here.  The query syntax is
               available in ArcGIS Help.  A short version of that URL
                is http://bitly.com/1fJ8q31.

            2. Searching without specifying a query parameter returns
               a list of all groups in your organization.

            3. Most of the time when searching for groups, you'll want to
                search within your organization in ArcGIS Online
                or within your Portal.  As a convenience, the method
                automatically appends your organization id to the query by
                default.  If you don't want the API to append to your query
                set outside_org to True.

        ================  ========================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------
        query             Optional string on Portal, or required string for ArcGIS Online.
                          If not specified, all groups will be searched. See notes above.
        ----------------  --------------------------------------------------------
        sort_field        Optional string. Valid values can be title, owner,
                          created.
        ----------------  --------------------------------------------------------
        sort_order        Optional string. Valid values are asc or desc.
        ----------------  --------------------------------------------------------
        max_groups        Optional integer. Maximum number of groups returned, default is 1,000.
        ----------------  --------------------------------------------------------
        outside_org       Optional boolean. Controls whether to search outside
                          your org. Default is False, do not search ourside your org.
        ----------------  --------------------------------------------------------
        categories        Optional string or list. A string of category values.
        ================  ========================================================


        :return:
           A list of groups matching the specified query.
        """
        grouplist = []
        groups = self._portal.search_groups(query, sort_field, sort_order, max_groups, outside_org, categories)
        for group in groups:
            grouplist.append(Group(self._gis, group['id'], group))
        return grouplist


def _is_shapefile(data):
    try:
        if zipfile.is_zipfile(data):
            zf = zipfile.ZipFile(data, 'r')
            namelist = zf.namelist()
            for name in namelist:
                if name.endswith('.shp') or name.endswith('.SHP'):
                    return True
        return False
    except:
        return False


class ContentManager(object):
    """
    Helper class for managing content in ArcGIS Online or ArcGIS Enterprise.
    This class is not created by users directly. An instance of this class,
    called 'content', is available as a property of the GIS object. Users
    call methods on this 'content' object to manipulate (create, get, search,
    etc) items.
    """
    def __init__(self, gis):
        self._gis = gis
        self._portal = gis._portal

    def add(self, item_properties, data=None, thumbnail=None, metadata=None, owner=None, folder=None):
        """ Adds content to the GIS by creating an item.

        .. note::
            Content can be a file (such as a service definition, shapefile,
            CSV, layer package, file geodatabase, geoprocessing package,
            map package) or it can be a URL (to an ArcGIS Server service,
            WMS service, or an application).

            If you are uploading a package or other file, provide a path or
            URL to the file in the data argument.

            From a technical perspective, none of the item_properties (see
            table below *Key:Value Dictionary Options for Argument
            item_properties*) are required.  However, it is strongly
            recommended that arguments title, type, typeKeywords, tags,
            snippet, and description be provided.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        item_properties     Required dictionary. See table below for the keys and values.
        ---------------     --------------------------------------------------------------------
        data                Optional string. Either a path or URL to the data.
        ---------------     --------------------------------------------------------------------
        thumbnail           Optional string. Either a path or URL to a thumbnail image.
        ---------------     --------------------------------------------------------------------
        metadata            Optional string. Either a path or URL to the metadata.
        ---------------     --------------------------------------------------------------------
        owner               Optional string. Defaults to the logged in user.
        ---------------     --------------------------------------------------------------------
        folder              Optional string. Name of the folder where placing item.
        ===============     ====================================================================


        *Key:Value Dictionary Options for Argument item_properties*


        =================  =====================================================================
        **Key**            **Value**
        -----------------  ---------------------------------------------------------------------
        type               Optional string. Indicates type of item, see URL 1 below for valid values.
        -----------------  ---------------------------------------------------------------------
        typeKeywords       Optional string. Provide a lists all sub-types, see URL 1 below for valid values.
        -----------------  ---------------------------------------------------------------------
        description        Optional string. Description of the item.
        -----------------  ---------------------------------------------------------------------
        title              Optional string. Name label of the item.
        -----------------  ---------------------------------------------------------------------
        url                Optional string. URL to item that are based on URLs.
        -----------------  ---------------------------------------------------------------------
        text               Optional string. For text based items such as Feature Collections & WebMaps
        -----------------  ---------------------------------------------------------------------
        tags               Optional string. Tags listed as comma-separated values, or a list of strings.
                           Used for searches on items.
        -----------------  ---------------------------------------------------------------------
        snippet            Optional string. Provide a short summary (limit to max 250 characters) of the what the item is.
        -----------------  ---------------------------------------------------------------------
        extent             Optional string. Provide comma-separated values for min x, min y, max x, max y.
        -----------------  ---------------------------------------------------------------------
        spatialReference   Optional string. Coordinate system that the item is in.
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
           The item if successfully added, None if unsuccessful.
            """

        if data is not None:
            title = os.path.splitext(os.path.basename(data))[0]
            extn = os.path.splitext(os.path.basename(data))[1].upper()

            filetype = None
            if (extn == '.CSV'):
                filetype = 'CSV'
            elif (extn == '.SD'):
                filetype = 'Service Definition'
            elif title.upper().endswith('.GDB'):
                filetype = 'File Geodatabase'
            elif (extn in ('.SLPK', '.SPK')):
                filetype = 'Scene Package'
            elif (extn in ('.LPK', '.LPKX')):
                filetype = 'Layer Package'
            elif (extn in ('.GPK', '.GPKX')):
                filetype = 'Geoprocessing Package'
            elif (extn == '.GCPK'):
                filetype = 'Locator Package'
            elif (extn == '.TPK'):
                filetype = 'Tile Package'
            elif (extn in ('.MPK', '.MPKX')):
                filetype = 'Map Package'
            elif (extn == '.MMPK'):
                filetype = 'Mobile Map Package'
            elif (extn == '.APTX'):
                filetype = 'Project Template'
            elif (extn == '.VTPK'):
                filetype = 'Vector Tile Package'
            elif (extn == '.PPKX'):
                filetype = 'Project Package'
            elif (extn == '.RPK'):
                filetype = 'Rule Package'
            elif (extn == '.MAPX'):
                filetype = 'Pro Map'

            if _is_shapefile(data):
                filetype = 'Shapefile'

            if not 'type' in item_properties:
                if filetype is not None:
                    item_properties['type'] = filetype
                else:
                    raise RuntimeError('Specify type in item_properties')
            if not 'title' in item_properties:
                item_properties['title'] = title

        owner_name = owner
        if isinstance(owner, User):
            owner_name = owner.username

        if 'tags' in item_properties:
            if type(item_properties['tags']) is list:
                item_properties['tags'] = ",".join(item_properties['tags'])

        itemid = self._portal.add_item(item_properties, data, thumbnail, metadata, owner_name, folder)

        if itemid is not None:
            return Item(self._gis, itemid)
        else:
            return None

    #----------------------------------------------------------------------
    def analyze(self,
                url=None,
                item=None,
                file_path=None,
                text=None,
                file_type=None,
                source_locale='en',
                geocoding_service=None,
                location_type=None,
                source_country='world',
                country_hint=None
                ):
        """
        The Analyze call helps a client analyze a CSV or Excel file (.xlsx, .xls) prior to publishing or generating features using the Publish or Generate operation, respectively.

        Analyze returns information about the file including the fields present as well as sample records. Analyze attempts to detect the presence of location fields that may be present as either X,Y fields or address fields.

        Analyze packages its result so that publishParameters within the JSON response contains information that can be passed back to the server in a subsequent call to Publish or Generate. The publishParameters subobject contains properties that describe the resulting layer after publishing, including its fields, the desired renderer, and so on. Analyze will suggest defaults for the renderer.

        In a typical workflow, the client will present portions of the Analyze results to the user for editing before making the call to Publish or Generate.

        If the file to be analyzed currently exists in the portal as an item, callers can pass in its itemId. Callers can also directly post the file. In this case, the request must be a multipart post request pursuant to IETF RFC1867. The third option for text files is to pass the text in as the value of the text parameter.

        =======================    =============================================================
        **Argument**               **Description**
        -----------------------    -------------------------------------------------------------
        url                        optional string. The URL of the csv file.
        -----------------------    -------------------------------------------------------------
        item                       optional string/Item. The ID or Item of the item to be
                                   analyzed.
        -----------------------    -------------------------------------------------------------
        file_path                  optional string. The file to be analyzed.
        -----------------------    -------------------------------------------------------------
        text                       optional string. The text in the file to be analyzed.
        -----------------------    -------------------------------------------------------------
        file_type                  optional string. The type of the input file: shapefile, csv or excel
        -----------------------    -------------------------------------------------------------
        source_locale              optional string. The locale used for the geocoding service source.
        -----------------------    -------------------------------------------------------------
        geocoding_service          optional string/geocoder. The URL of the service.
        -----------------------    -------------------------------------------------------------
        location_type              optional string. Indicates the type of spatial information stored in the dataset.

                                   Values for CSV: coordinates | address | lookup | none
                                   Values for Excel: coordinates | address | none
        -----------------------    -------------------------------------------------------------
        source_country             optional string. The two character country code associated with the geocoding service, default is "world".
        -----------------------    -------------------------------------------------------------
        country_hint               optional string. If first time analyzing, the hint is used. If source country is already specified than sourcecountry is used.
        =======================    =============================================================

        :returns: dictionary

        """
        surl = "%s/sharing/rest/content/features/analyze" % self._gis._url
        params = {
            'f' : 'json',
            'analyzeParameters' : {}
        }
        files = None
        if not (text or file_path or item or url):
            return Exception("Must provide an itemid, file_path or text to analyze data.")
        if item:
            if isinstance(item, str):
                parms['itemid'] = item
            elif isinstance(item, Item):
                params['itemid'] = item.itemid
        elif file_path and os.path.isfile(file_path):
            files = {'file' : file_path}
        elif text:
            params['text'] = text
        elif url:
            params['sourceUrl'] = url

        params['analyzeParameters']['sourcelocale'] = source_locale
        if geocoding_service:
            from arcgis.geocoding._functions import Geocoder
            if isinstance(geocoding_service, Geocoder):
                params['analyzeParameters']['geocodeServiceUrl'] = geocoding_service.url
            else:
                params['analyzeParameters']['geocodeServiceUrl'] = geocoding_service
        if location_type:
            params['analyzeParameters']['locationType'] = location_type

        if file_type is None and \
           (url or file_path):
            d = url or file_path
            if d:
                if str(d).lower().endswith('.csv'):
                    params['fileType'] = 'csv'
                elif str(d).lower().endswith('.xls') or \
                     str(d).lower().endswith('.xlsx'):
                    params['fileType'] = 'excel'
        if source_country:
            params['analyzeParameters']['sourceCountry'] = source_country
        if country_hint:
            params['analyzeParameters']['sourcecountryhint'] = country_hint

        gis = self._gis
        params['analyzeParameters'] = json.dumps(params['analyzeParameters'])
        return gis._con.post(path=surl, postdata=params, files=files)


    def create_service(self, name,
                       service_description="",
                       has_static_data=False,
                       max_record_count = 1000,
                       supported_query_formats = "JSON",
                       capabilities = None,
                       description = "",
                       copyright_text = "",
                       wkid=102100,
                       create_params=None,
                       service_type="featureService",
                       owner=None, folder=None, item_properties=None, is_view=False):
        """ Creates a service in the Portal.


        =======================    =============================================================
        **Argument**               **Description**
        -----------------------    -------------------------------------------------------------
        name                       Required string. The unique name of the service.
        -----------------------    -------------------------------------------------------------
        service_description        Optional string. Description of the service.
        -----------------------    -------------------------------------------------------------
        has_static_data            Optional boolean. Indicating whether the data can change.  Default is True, data is not allowed to change.
        -----------------------    -------------------------------------------------------------
        max_record_count           Optional integer. Maximum number of records in query operations.
        -----------------------    -------------------------------------------------------------
        supported_query_formats    Optional string. Formats in which query results are returned.
        -----------------------    -------------------------------------------------------------
        capabilities               Optional string. Specify service capabilities.
                                   If left unspecified, 'Image,Catalog,Metadata,Download,Pixels'
                                   are used for image services, and 'Query'
                                   is used for feature services, and 'Query' otherwise
        -----------------------    -------------------------------------------------------------
        description                Optional string. A user-friendly description for the published dataset.
        -----------------------    -------------------------------------------------------------
        copyright_text             Optional string. The copyright information associated with the dataset.
        -----------------------    -------------------------------------------------------------
        wkid                       Optional integer. The well known id (WKID) of the spatial reference for the service.
                                   All layers added to a hosted feature service need to have the same spatial
                                   reference defined for the feature service. When creating a new
                                   empty service without specifying its spatial reference, the spatial
                                   reference of the hosted feature service is set to the first layer added to that feature service.
        -----------------------    -------------------------------------------------------------
        create_params              Optional dictionary. Add all create_service parameters into a dictionary. If this parameter is used,
                                   all the parameters above are ignored.
        -----------------------    -------------------------------------------------------------
        service_type               Optional string. The type of service to be created.  Currently the options are imageService or featureService.
        -----------------------    -------------------------------------------------------------
        owner                      Optional string. The username of the owner of the service being created.
        -----------------------    -------------------------------------------------------------
        folder                     Optional string. The name of folder in which to create the service.
        -----------------------    -------------------------------------------------------------
        item_properties            Optional dictionary. See below for the keys and values
        -----------------------    -------------------------------------------------------------
        is_view                    Optional boolean. Indicating if the service is a hosted feature layer view
        =======================    =============================================================


        *Key:Value Dictionary Options for Argument item_properties*


        =================  =====================================================================
        **Key**            **Value**
        -----------------  ---------------------------------------------------------------------
        type               Optional string. Indicates type of item, see URL 1 below for valid values.
        -----------------  ---------------------------------------------------------------------
        typeKeywords       Optional string. Provide a lists all sub-types, see URL 1 below for valid values.
        -----------------  ---------------------------------------------------------------------
        description        Optional string. Description of the item.
        -----------------  ---------------------------------------------------------------------
        title              Optional string. Name label of the item.
        -----------------  ---------------------------------------------------------------------
        url                Optional string. URL to item that are based on URLs.
        -----------------  ---------------------------------------------------------------------
        tags               Optional string. Tags listed as comma-separated values, or a list of strings.
                           Used for searches on items.
        -----------------  ---------------------------------------------------------------------
        snippet            Optional string. Provide a short summary (limit to max 250 characters) of the what the item is.
        -----------------  ---------------------------------------------------------------------
        extent             Optional string. Provide comma-separated values for min x, min y, max x, max y.
        -----------------  ---------------------------------------------------------------------
        spatialReference   Optional string. Coordinate system that the item is in.
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

        :return:
             The item for the service if successfully created, None if unsuccessful.
        """
        if capabilities is None:
            if service_type == 'imageService':
                capabilities = 'Image,Catalog,Metadata,Download,Pixels'
            elif service_type == 'featureService':
                capabilities = 'Query'
            else:
                capabilities = 'Query'

        itemid = self._portal.create_service(name,
                                             service_description,
                                             has_static_data,
                                             max_record_count,
                                             supported_query_formats,
                                             capabilities,
                                             description,
                                             copyright_text,
                                             wkid,
                                             service_type,
                                             create_params,
                                             owner, folder, item_properties, is_view)
        if itemid is not None:
            return Item(self._gis, itemid)
        else:
            return None

    def get(self, itemid):
        """ Returns the item object for the specified itemid.


        =======================    =============================================================
        **Argument**               **Description**
        -----------------------    -------------------------------------------------------------
        itemid                     Required string. The item identifier.
        =======================    =============================================================

        :return:
            The item object if the item is found, None if the item is not found.
        """
        try:
            item = self._portal.get_item(itemid)
        except RuntimeError as re:
            if re.args[0].__contains__("Item does not exist or is inaccessible"):
                return None
            else:
                raise re

        if item is not None:
            return Item(self._gis, itemid, item)
        return None

    def search(self,
               query, item_type=None,
               sort_field='avgRating', sort_order='desc',
               max_items=10, outside_org=False,
               categories=None):
        """ Searches for portal items.

        .. note::
            A few things that will be helpful to know...

            1. The query syntax has many features that can't be adequately
               described here.  The query syntax is available in ArcGIS Help.
               A short version of that URL is http://bitly.com/1fJ8q31.

            2. Most of the time when searching for items, you'll want to
               search within your organization in ArcGIS Online
               or within your Portal.  As a convenience, the method
               automatically appends your organization id to the query by
               default.  If you want content from outside your organization
               set outside_org to True.

        ================  ==========================================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------------------------
        query             Required string. A query string.  See notes above.
        ----------------  --------------------------------------------------------------------------
        item_type         Optional string. Set type of item to search.
                          http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#//02r3000000ms000000
        ----------------  --------------------------------------------------------------------------
        sort_field        Optional string. Valid values can be title, uploaded, type, owner, modified,
                          avgRating, numRatings, numComments, and numViews.
        ----------------  --------------------------------------------------------------------------
        sort_order        Optional string. Valid values are asc or desc.
        ----------------  --------------------------------------------------------------------------
        max_items         Optional integer. Maximum number of items returned, default is 10.
        ----------------  --------------------------------------------------------------------------
        outside_org       Optional boolean. Controls whether to search outside your org (default is False, do not search ourside your org).
        ----------------  --------------------------------------------------------------------------
        categories        Optional string or list. A string of category values.
        ================  ==========================================================================

        :return:
            A list of items matching the specified query.
        """
        itemlist = []
        if query is not None and query != '' and item_type is not None:
            query += ' AND '

        if item_type is not None:
            item_type = item_type.lower()
            if item_type == "web map":
                query += ' (type:"web map" NOT type:"web mapping application")'
            elif item_type == "web scene":
                query += ' (type:"web scene" NOT type:"CityEngine Web Scene")'
            elif item_type == "feature layer":
                query += ' (type:"feature service")'
            elif item_type == "geoprocessing tool":
                query += ' (type:"geoprocessing service")'
            elif item_type == "geoprocessing toolbox":
                query += ' (type:"geoprocessing service")'
            elif item_type == "feature layer collection":
                query += ' (type:"feature service")'
            elif item_type == "image layer":
                query += ' (type:"image service")'
            elif item_type == "imagery layer":
                query += ' (type:"image service")'
            elif item_type == "map image layer":
                query += ' (type:"map service")'
            elif item_type == "vector tile layer":
                query += ' (type:"vector tile service")'
            elif item_type == "scene layer":
                query += ' (type:"scene service")'
            elif item_type == "layer":
                query += ' (type:"layer" NOT type:"layer package" NOT type:"Explorer Layer")'
            elif item_type == "feature collection":
                query += ' (type:"feature collection" NOT type:"feature collection template")'
            elif item_type == "desktop application":
                query += ' (type:"desktop application" NOT type:"desktop application template")'
            else:
                query += ' (type:"' + item_type +'")'
        if isinstance(categories, list):
            categories = ",".join(categories)
        items = self._portal.search(query, sort_field=sort_field, sort_order=sort_order, max_results=max_items, outside_org=outside_org, categories=categories)
        for item in items:
            itemlist.append(Item(self._gis, item['id'], item))
        return itemlist
    # q: (type:"web map" NOT type:"web mapping applications") AND accountid:0123456789ABCDEF

    def create_folder(self, folder, owner=None):
        """
        Creates a folder with the given folder name, for the given owner. Does
        nothing if the folder already exists. If owner is not specified, owner
        is set as the logged in user.


        ================  ==========================================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------------------------
        folder            Required string. The name of the folder to create for the owner.
        ----------------  --------------------------------------------------------------------------
        owner             Optional string. User, folder owner, None for logged in user.
        ================  ==========================================================================

        :return:
            A json object like the following if the folder was created:
            {"username" : "portaladmin","id" : "bff13218991c4485a62c81db3512396f","title" : "testcreate"}; None otherwise.
        """
        if folder != '/': # we don't create root folder
            if owner is None:
                owner = self._portal.logged_in_user()['username']
                owner_name = owner
            elif isinstance(owner, User):
                owner_name = owner.username
            else:
                owner_name = owner
            if self._portal.get_folder_id(owner_name, folder) is None:
                return self._portal.create_folder(owner_name, folder)
            else:
                print('Folder already exists.')
        return None

    def delete_items(self, items):
        """
        Deletes a collection of items from a users content.

        ================  ==========================================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------------------------
        items             list of Item or Item Ids.  This is an array of items to be deleted from
                          the current user's content
        ================  ==========================================================================

        Returns: boolean. True on
        """
        if self._gis._portal.con.baseurl.endswith("/"):
            url = "%s/%s/%s/deleteItems" % (self._gis._portal.con.baseurl[:-1],
                                            "content/users",
                                            self._gis.users.me.username)
        else:
            url = "%s/%s/%s/deleteItems" % (self._gis._portal.con.baseurl,
                                            "content/users",
                                            self._gis.users.me.username)
        params = {
        'f' : 'json',
        'items' : ""
        }
        ditems = []
        for item in items:
            if isinstance(item, str):
                ditems.append(item)
            elif isinstance(item, Item):
                ditems.append(item.id)
            del item
        if len(ditems) > 0:
            params['items'] = ",".join(ditems)
            res = self._gis._con.post(path=url, postdata=params)
            return all([r['success'] for r in res['results']])
        return False


    def delete_folder(self, folder, owner=None):
        """
        Deletes a folder for the given owner (logged in user by default) with
        the given folder name.


        ================  ==========================================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------------------------
        folder            Required string. The name of the folder to delete.
        ----------------  --------------------------------------------------------------------------
        owner             Optional string. User, folder owner, None for logged in user is the default.
        ================  ==========================================================================

        :return:
            True if folder deletion succeeded, False if folder deletion failed.
        """
        if folder != '/':
            if owner is None:
                owner = self._portal.logged_in_user()['username']
                owner_name = owner
            elif isinstance(owner, User):
                owner_name = owner.username
            else:
                owner_name = owner
            return self._portal.delete_folder(owner_name, folder)

    def import_data(self, df, address_fields=None, **kwargs):
        """
        Imports a Pandas data frame (that has an address column), or an arcgis
        spatial dataframe into the GIS.

        Spatial dataframes are imported into the GIS and published as feature
        layers. Pandas dataframes that have an address column are imported as
        an in-memory feature collection.
        Note: By default, there is a limit of 1,000 rows/features for Pandas
        dataframes. This limit isn't there for spatial dataframes.

        ================  ==========================================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------------------------
        df                Required string. Pandas dataframe or arcgis.SpatialDataFrame
        ----------------  --------------------------------------------------------------------------
        address_fields    Optional dictionary. Dictionary containing mapping of df columns to address fields, eg: { "CountryCode" : "Country"} or { "Address" : "Address" }.
        ----------------  --------------------------------------------------------------------------
        title             Optional string. Title of the item. This is used for spatial dataframe objects.
        ----------------  --------------------------------------------------------------------------
        tags              Optional string. Tags listed as comma-separated values, or a list of strings. Provide tags when publishing a spatial dataframe to the the GIS.
        ================  ==========================================================================

        In addition to the parameters aboce, you can specify additional information to help publish CSV
        data.

        =====================  ==========================================================================
        **Optional Argument**  **Description**
        ---------------------  --------------------------------------------------------------------------
        location_type          Optional string. Indicates the type of spatial information stored in the
                               dataset.

                               Values for CSV:

                                  + coordinates
                                  + address (default)
                                  + lookup
                                  + none

                               Values for Excel:

                                  + coordinates
                                  + address (default)
                                  + none

                               When location_type = coordinates, the CSV or Excel data contains x,y
                               information.
                               When location_type = address, the CSV or Excel data contains address
                               fields that will be geocoded to a single point.
                               When location_type = lookup, the CSV or Excel data contains fields that
                               can be mapped to well-known sets of geographies.
                               When location_type = none, the CSV or Excel data contains no spatial
                               content and data will be loaded and subsequently queried as tabular data.

                               Based on this parameter, additional parameters will be required, for
                               example, when specifying location_type = coordinates, the latitude and
                               longitude field names must be specified.
        ---------------------  --------------------------------------------------------------------------
        latitude_field         Optional string. If location_type = coordinates, the name of the field that
                               contains the y coordinate.
        ---------------------  --------------------------------------------------------------------------
        longitude_field        Optional string. If location_type = coordinates, the name of the field that
                               contains the x coordinate.
        ---------------------  --------------------------------------------------------------------------
        coordinate_field_type  Optional string. Specify the type of coordinates that contain location
                               information. Values: LatitudeAndLongitude (default), MGRS, USNG
        ---------------------  --------------------------------------------------------------------------
        coordinate_field_name  Optional string. The name of the field that contains the coordinates
                               specified in coordinate_field_type
        ---------------------  --------------------------------------------------------------------------
        lookup_type            Optional string. The type of place to look up.
        ---------------------  --------------------------------------------------------------------------
        lookup_fields          Optional string. A JSON object with name value pairs that define the
                               fields used to look up the location.
        ---------------------  --------------------------------------------------------------------------
        geocode_url            Optional string. The URL of the geocoding service that supports batch
                               geocoding.
        ---------------------  --------------------------------------------------------------------------
        source_locale          Optional string. The locale used for the geocoding service source.
        ---------------------  --------------------------------------------------------------------------
        source_country         Optional string. The two character country code associated with the
                               geocoding service, default is 'world'.
        ---------------------  --------------------------------------------------------------------------
        country_hint           Optional string. If first time analyzing, the hint is used. If source
                               country is already specified than source_country is used.
        =====================  ==========================================================================


        When publishing a Spatial Dataframe, additional options can be given:

        =====================  ==========================================================================
        **Optional Argument**  **Description**
        ---------------------  --------------------------------------------------------------------------
        target_sr              optional integer.  WKID of the output data.  This is used when publishing
                               Spatial Dataframes to Hosted Feature Layers. The default is: 102100
        ---------------------  --------------------------------------------------------------------------
        title                  optional string. Name of the layer. The default is a random string.
        ---------------------  --------------------------------------------------------------------------
        tags                   optional string. Comma seperated strings that provide metadata for the
                               items. The default is FGDB.
        ---------------------  --------------------------------------------------------------------------
        capabilities           optional string. specifies the operations that can be performed on the
                               feature layer service. The default is Query.
        =====================  ==========================================================================


        :return:
           A feature collection or feature layer that can be used for analysis,
           visualization, or published to the GIS as an item.
        """
        from arcgis.features import FeatureCollection, SpatialDataFrame, FeatureSet

        from arcgis._impl.common._utils import zipws

        import shutil
        from uuid import uuid4
        import pandas as pd
        try:
            import arcpy
            has_arcpy = True
        except ImportError:
            has_arcpy = False
        try:
            import shapefile
            has_pyshp = True
        except ImportError:
            has_pyshp = False
        if isinstance(df, FeatureSet):
            df = df.df
        if has_arcpy == False and \
           has_pyshp == False and \
           isinstance(df, SpatialDataFrame):
            raise Exception("SpatialDataFrame's must have either pyshp or" + \
                            " arcpy available to use import_data")
        elif isinstance(df, SpatialDataFrame):
            import random
            import string
            temp_dir = os.path.join(tempfile.gettempdir(), "a" + uuid4().hex[:7])
            title = kwargs.pop("title", uuid4().hex)
            tags = kwargs.pop('tags', 'FGDB')
            target_sr = kwargs.pop('target_sr', 102100)
            capabilities = kwargs.pop('capabilities', "Query")
            os.makedirs(temp_dir)
            temp_zip = os.path.join(temp_dir, "%s.zip" % ("a" + uuid4().hex[:5]))
            if has_arcpy:
                name = "%s%s.gdb" % (random.choice(string.ascii_lowercase),
                                     uuid4().hex[:5])
                fgdb = arcpy.CreateFileGDB_management(out_folder_path=temp_dir,
                                                      out_name=name)[0]
                ds = df.to_featureclass(out_location=fgdb,
                                        out_name=os.path.basename(temp_dir))
                zip_fgdb = zipws(path=fgdb, outfile=temp_zip, keep=True)
                item = self.add(
                    item_properties={
                        "title" : title,
                        "type" : "File Geodatabase",
                        "tags" : tags},
                    data=zip_fgdb)
                shutil.rmtree(temp_dir,
                              ignore_errors=True)
                publish_parameters =  {"hasStaticData":True, "name": os.path.splitext(item['name'])[0],
                                       "maxRecordCount":2000, "layerInfo":{"capabilities":capabilities}}
                if target_sr is not None:
                    publish_parameters['targetSR'] = { 'wkid' : target_sr }
                return item.publish(publish_parameters=publish_parameters)
            elif has_pyshp:
                import random
                import string
                name = "%s%s.shp" % (random.choice(string.ascii_lowercase),
                                     uuid4().hex[:5])
                ds = df.to_featureclass(out_location=temp_dir,
                                        out_name=name)
                zip_shp = zipws(path=temp_dir, outfile=temp_zip, keep=False)
                item = self.add(
                    item_properties={
                        "title":title,
                        "tags":tags},
                    data=zip_shp)
                shutil.rmtree(temp_dir,
                              ignore_errors=True)
                publish_parameters =  {"hasStaticData":True, "name": os.path.splitext(item['name'])[0],
                                       "maxRecordCount":2000, "layerInfo":{"capabilities":capabilities}}
                if target_sr is not None:
                    publish_parameters['targetSR'] = { 'wkid' : target_sr }
                return item.publish(publish_parameters=publish_parameters)
            return
        elif isinstance(df, pd.DataFrame) and \
             'location_type' not in kwargs:
            # CSV WORKFLOW
            path = "content/features/analyze"

            postdata = {
                "f": "pjson",
                "text" : df.to_csv(),
                "filetype" : "csv",

                "analyzeParameters" : {
                    "enableGlobalGeocoding": "true",
                    "sourceLocale":"en-us",
                    #"locationType":"address",
                    "sourceCountry":"",
                    "sourceCountryHint":"",
                    "geocodeServiceUrl":self._gis.properties.helperServices.geocode[0]['url']
                }
            }

            if address_fields is not None:
                postdata['analyzeParameters']['locationType'] = 'address'

            res = self._portal.con.post(path, postdata)
            #import json
            #json.dumps(res)
            if address_fields is not None:
                res['publishParameters'].update({"addressFields":address_fields})

            path = "content/features/generate"
            postdata = {
                "f": "pjson",
                "text" : df.to_csv(),
                "filetype" : "csv",
                "publishParameters" : json.dumps(res['publishParameters'])
            }

            res = self._portal.con.post(path, postdata)#, use_ordered_dict=True) - OrderedDict >36< PropertyMap

            fc = FeatureCollection(res['featureCollection']['layers'][0])
            return fc
        elif isinstance(df, pd.DataFrame) and \
             'location_type' in kwargs:
            path = "content/features/analyze"

            postdata = {
                "f": "pjson",
                "text" : df.to_csv(),
                "filetype" : "csv",

                "analyzeParameters" : {
                    "enableGlobalGeocoding": "true",
                    "sourceLocale":kwargs.pop("source_locale", "us-en"),

                    "sourceCountry": kwargs.pop("source_country", ""),
                    "sourceCountryHint": kwargs.pop("country_hint", ""),
                    "geocodeServiceUrl": kwargs.pop("geocode_url",
                                                    self._gis.properties.helperServices.geocode[0]['url']),
                    #"locationType": kwargs.pop('location_type', None),
                    #"latitudeFieldName" : kwargs.pop("latitude_field", None),
                    #"longitudeFieldName" : kwargs.pop("longitude_field", None),
                    #"coordinateFieldName" : kwargs.pop("coordinate_field_name", None),

                    #"coordinateFieldType" : kwargs.pop("coordinate_field_type", None)

                }
            }
            update_dict = {}
            update_dict["locationType"] = kwargs.pop('location_type', "")
            update_dict["latitudeFieldName"] = kwargs.pop("latitude_field", "")
            update_dict["longitudeFieldName"] = kwargs.pop("longitude_field", "")
            update_dict["coordinateFieldName"] = kwargs.pop("coordinate_field_name", "")
            update_dict["coordinateFieldType"] = kwargs.pop("coordinate_field_type", "")
            rk = []
            for k,v in update_dict.items():
                if v == "":
                    rk.append(k)
            for k in rk:
                del update_dict[k]

            res = self._portal.con.post(path, postdata)
            res['publishParameters'].update(update_dict)
            path = "content/features/generate"
            postdata = {
                "f": "pjson",
                "text" : df.to_csv(),
                "filetype" : "csv",
                "publishParameters" : json.dumps(res['publishParameters'])
            }
            res = self._portal.con.post(path, postdata)#, use_ordered_dict=True) - OrderedDict >36< PropertyMap

            fc = FeatureCollection(res['featureCollection']['layers'][0])
            return fc
            #return
        return None

    def is_service_name_available(self, service_name, service_type):
        """ For a desired service name, determines if that service name is
            available for use or not.

            ================  ======================================================================
            **Argument**      **Description**
            ----------------  ----------------------------------------------------------------------
            service_name      Required string. A desired service name.
            ----------------  ----------------------------------------------------------------------
            service_type      Required string. The type of service to be created.  Currently the options are imageService or featureService.
            ================  ======================================================================

            :return:
                 True if the specified service_name is available for the
               specified service_type, False if the service_name is unavailable.

        """
        path = "portals/self/isServiceNameAvailable"

        postdata = {
            "f": "pjson",
            "name" : service_name,
            "type" : service_type
        }

        res = self._portal.con.post(path, postdata)
        return res['available']

    def clone_items(self, items, folder=None, item_extent=None, use_org_basemap=False, copy_data=True, search_existing_items=True, item_mapping=None, group_mapping=None):
        """ Clone content to the GIS by creating new items.

        .. note::
        Cloning an item will create a copy of the item and for certain
        item types a copy of the item dependencies in the GIS.

        For example a web application created using Web AppBuilder
        or a Configurable App Template which is built from a web map
        that references one or more hosted feature layers. This function
        will clone all of these items to the GIS and swizzle the paths
        in the web map and web application to point to the new layers.

        This creates an exact copy of the application, map, and layers
        in the GIS.

        =====================     ====================================================================
        **Argument**              **Description**
        ---------------------     --------------------------------------------------------------------
        items                     Required list. Collection of Items to clone.
        ---------------------     --------------------------------------------------------------------
        folder                    Optional string. Name of the folder where placing item.
        ---------------------     --------------------------------------------------------------------
        item_extent               Optional Envelope. Extent set for any cloned items. Default is None,
                                  extent will remain unchanged. Spatial reference of the envelope will be
                                  used for any cloned feature layers.
        ---------------------     --------------------------------------------------------------------
        use_org_basemap           Optional boolean. Indicating whether the basemap in any cloned web maps
                                  should be updated to the organizations default basemap. Default is False,
                                  basemap will not change.
        ---------------------     --------------------------------------------------------------------
        copy_data                 Optional boolean. Indicating whether the data should be copied with any
                                  feature layer or feature collections. Default is True, data will be copied.
        ---------------------     --------------------------------------------------------------------
        search_existing_items     Optional boolean. Indicating whether items that have already been cloned
                                  should be searched for in the GIS and reused rather than cloned again.
        ---------------------     --------------------------------------------------------------------
        item_mapping              Optional dictionary. Can be used to associate an item id in the source
                                  GIS (key) to an item id in the target GIS (value). The target item will
                                  be used rather than cloning the source item.
        ---------------------     --------------------------------------------------------------------
        group_mapping             Optional dictionary. Can be used to associate a group id in the source
                                  GIS (key) to a group id in the target GIS (value). The target group will
                                  be used rather than cloning the source group.
        =====================     ====================================================================

        :return:
           A list of items created during the clone.

        """

        import arcgis._impl.common._clone as clone
        wgs84_extent = None
        if item_extent:
            wgs84_extent = clone._wgs84_envelope(item_extent)
        deep_cloner = clone._DeepCloner(self._gis, items, folder, wgs84_extent, use_org_basemap, copy_data, search_existing_items, item_mapping, group_mapping)
        return deep_cloner.clone()

    def _bulk_update(self, itemids, properties):
        """
        Updates a collection of items' properties.

        Example:

        >>> itemsids = gis.content.search("owner: TestUser12399")
        >>> properties = {'categories' : ["clothes","formal_wear/socks"]}
        >>> gis.content._bulk_update(itemids, properties)
        [{'results' : [{'itemid' : 'id', 'success' : "True/False" }]}]

        .. :Note: bulk_update only works with content categories at this time.

        ================  ======================================================================
        **Argument**      **Description**
        ----------------  ----------------------------------------------------------------------
        itemids           Required list of string or Item. The collection of Items to update.
        ----------------  ----------------------------------------------------------------------
        properties        Required dictionary. The Item's properties to update.
        ================  ======================================================================

        :returns: list of results

        """
        path = "content/updateItems"
        params = {'f' : 'json',
                  'items' : []}
        updates = []
        results = []
        for item in itemids:
            if isinstance(item, Item):
                updates.append({
                    item.itemid : properties
                })
            elif isinstance(item, str):
                updates.append({
                    item : properties
                })
            else:
                raise ValueError("Invalid Item or ItemID, must be string or Item")
        def _chunks(l, n):
            for i in range(0, len(l), n):
                yield l[i:i+n]
        for i in _chunks(l=updates, n=100):
            params['items'] = i

            res = self._gis._con.post(path=path, postdata=params)
            results.append(res)
            del i
        return results

class ResourceManager(object):
    """
    Helper class for managing resource files of an item. This class is not created by users directly.
    An instance of this class, called 'resources', is available as a property of the Item object.
    Users call methods on this 'resources' object to manage (add, remove, update, list, get) item resources.
    """

    def __init__(self, item, gis):
        self._gis = gis
        self._portal = gis._portal
        self._item = item

    def add(self, file=None, folder_name=None, file_name=None, text=None, archive=False):
        """The add resources operation adds new file resources to an existing item. For example, an image that is
        used as custom logo for Report Template. All the files are added to 'resources' folder of the item. File
        resources use storage space from your quota and are scanned for viruses. The item size is updated to
        include the size of added resource files. Each file added should be no more than 25 Mb.

        Supported item types that allow adding file resources are: Vector Tile Service, Vector Tile Package,
        Style, Code Attachment, Report Template, Web Mapping Application, Feature Service, Web Map,
        Statistical Data Collection, Scene Service, and Web Scene.

        Supported file formats are: JSON, XML, TXT, PNG, JPEG, GIF, BMP, PDF, MP3, MP4, and ZIP.
        This operation is only available to the item owner and the organization administrator.

        ================  ===============================================================
        **Argument**      **Description**
        ----------------  ---------------------------------------------------------------
        file              Optional string. The path to the file that needs to be added.
        ----------------  ---------------------------------------------------------------
        folder_name       Optional string. Provide a folder name if the file has to be
                          added to a folder under resources.
        ----------------  ---------------------------------------------------------------
        file_name         Optional string. The file name used to rename an existing file
                          resource uploaded, or to be used together with text as file name for it.
        ----------------  ---------------------------------------------------------------
        text              Optional string. Text input to be added as a file resource,
                          used together with file_name. If this resource is used, then
                          file_name becomes required.
        ----------------  ---------------------------------------------------------------
        archive           Optional boolean. Default is False.  If True, file resources
                          added are extracted and files are uploaded to respective folders.
        ================  ===============================================================

        :return:
            Python dictionary like the following if it succeeded:
            {
                "success": True,
                "itemId": "<item id>",
                "owner": "<owner username>",
                "folder": "<folder id>"}

            else like the following if it failed:
            {"error": {
                        "code": 400,
                        "messageCode": "CONT_0093",
                        "message": "File type not allowed for addResources",
                        "details": []
                        }}
        """
        if not file and (not text or not file_name):
            raise ValueError("Please provide a valid file or text/file_name.")
        query_url = 'content/users/'+ self._item.owner +\
            '/items/' + self._item.itemid + '/addResources'

        files = [] #create a list of named tuples to hold list of files
        if file and os.path.isfile(os.path.abspath(file)):
            files.append(('file',file, os.path.basename(file)))
        elif file and os.path.isfile(os.path.abspath(file)) == False:
            raise RuntimeError("File(" + file + ") not found.")

        params = {}
        params['f'] = 'json'

        if folder_name is not None:
            params['resourcesPrefix'] = folder_name
        if file_name is not None:
            params['fileName'] = file_name
        if text is not None:
            params['text'] = text
        params['archive'] = 'true' if archive else 'false'

        resp = self._portal.con.post(query_url, params,
                                     files=files, compress=False)
        return resp

    def update(self, file, folder_name=None, file_name=None, text=None):
        """The update resources operation allows you to update existing file resources of an item.
        File resources use storage space from your quota and are scanned for viruses. The item size
        is updated to include the size of updated resource files.

        Supported file formats are: JSON, XML, TXT, PNG, JPEG, GIF, BMP, PDF, and ZIP.
        This operation is only available to the item owner and the organization administrator.

        ================  ===============================================================
        **Argument**      **Description**
        ----------------  ---------------------------------------------------------------
        file              Required string. The path to the file on disk to be used for
                          overwriting an existing file resource.
        ----------------  ---------------------------------------------------------------
        folder_name       Optional string. Provide a folder name if the file resource
                          being updated resides in a folder.
        ----------------  ---------------------------------------------------------------
        file_name         Optional string. The destination name for the file used to update
                          an existing resource, or to be used together with the text parameter
                          as file name for it.

                          For example, you can use fileName=banner.png to update an existing
                          resource banner.png with a file called billboard.png without
                          renaming the file locally.
        ----------------  ---------------------------------------------------------------
        text              Optional string. Text input to be added as a file resource,
                          used together with file_name.
        ================  ===============================================================

        :return:
            Python dictionary like the following if it succeeded:
            {
                "success": True,
                "itemId": "<item id>",
                "owner": "<owner username>",
                "folder": "<folder id>" }

            else like the following if it failed:
            {"error": {
                        "code": 404,
                        "message": "Resource does not exist or is inaccessible.",
                        "details": []
                        } }
        """

        query_url = 'content/users/' + self._item.owner + \
            '/items/' + self._item.itemid + '/updateResources'

        files = []  # create a list of named tuples to hold list of files
        if not os.path.isfile(os.path.abspath(file)):
            raise RuntimeError("File(" + file + ") not found.")
        files.append(('file', file, os.path.basename(file)))

        params = {}
        params['f'] = 'json'

        if folder_name is not None:
            params['resourcesPrefix'] = folder_name
        if file_name is not None:
            params['fileName'] = file_name
        if text is not None:
            params['text'] = text

        resp = self._portal.con.post(query_url, params, files=files)
        return resp

    def list(self):
        """
        Provides a lists all file resources of an existing item. This resource is only available to
        the item owner and the organization administrator.

        :return:
            A Python list of dictionaries of the form:
            [
                {
                  "resource": "<resource1>"
                },
                {
                  "resource": "<resource2>"
                },
                {
                  "resource": "<resource3>"
                }
            ]
        """
        query_url = 'content/items/' + self._item.itemid + '/resources'
        params = {'f':'json',
                  'num': 1000}
        resp = self._portal.con.get(query_url, params)
        resp_resources = resp.get('resources')
        count = int(resp.get('num'))
        next_start = int(resp.get('nextStart'))

        # loop through pages
        while next_start > 0:
            params2 = {'f':'json',
                       'num':1000,
                       'start':next_start + 1}

            resp2 = self._portal.con.get(query_url, params2)
            resp_resources.extend(resp2.get('resources'))
            count += int(resp2.get('num'))
            next_start = int(resp2.get('nextStart'))

        return resp_resources

    def get(self, file, try_json = True, out_folder = None, out_file_name = None):
        """
        Gets a specific file resource of an existing item.  This operation is only
        available to the item owner and the organization administrator.

        ================  ===============================================================
        **Argument**      **Description**
        ----------------  ---------------------------------------------------------------
        file              Required string. The path to the file to be downloaded.
                          For files in the root, just specify the file name. For files in
                          folders (prefixes), specify using the format
                          <foldername>/<foldername>./../<filename>
        ----------------  ---------------------------------------------------------------
        try_json          Optional boolean. If True, will attempt to convert JSON files to
                          Python dictionary objects. Default is True.
        ----------------  ---------------------------------------------------------------
        out_folder        Optional string. Specify the folder into which the file has to
                          be saved. Default is user's temporary directory.
        ----------------  ---------------------------------------------------------------
        out_file_name     Optional string. Specify the name to use when downloading the
                          file. Default is the resource file's name.
        ================  ===============================================================


        :return:
           Path to the downloaded file if getting a binary file (like a jpeg or png file) or if
           try_jon = False when getting a JSON file.

           If file is a JSON, returns as a Python dictionary.
        """

        safe_file_format = file.replace(r'\\','/')
        safe_file_format = safe_file_format.replace('//', '/')

        query_url = 'content/items/' + self._item.itemid + '/resources/' + safe_file_format

        return self._portal.con.get(query_url, try_json = try_json, out_folder=out_folder,
                                    file_name = out_file_name)

    def remove(self, file = None):
        """
        Removes a single resource file or all resources. The item size is updated once
        resource files are deleted. This operation is only available to the item owner
        and the organization administrator.

        ================  ===============================================================
        **Argument**      **Description**
        ----------------  ---------------------------------------------------------------
        file              Optional string. The path to the file to be removed.
                          For files in the root, just specify the file name. For files in
                          folders (prefixes), specify using the format
                          <foldername>/<foldername>./../<filename>

                          If not specified, all resource files will be removed.
        ================  ===============================================================


        :return:
            If succeeded a boolean of True will be returned,

            else a dictionary with error info
            {"error": {"code": 404,
                        "message": "Resource does not exist or is inaccessible.",
                        "details": []
                      }
            }
        """
        safe_file_format = ""
        delete_all = 'false'
        if file:
            safe_file_format = file.replace(r'\\','/')
            safe_file_format = safe_file_format.replace('//', '/')
        else:
            delete_all = 'true'

        query_url = 'content/users/'+ self._item.owner +\
            '/items/' + self._item.itemid + '/removeResources'
        params = {'f':'json',
                  'resource': safe_file_format if safe_file_format else "",
                  'deleteAll':delete_all}
        res = self._portal.con.post(query_url, postdata=params)
        if 'success' in res:
            return res['success']
        return res

class Group(dict):
    """
    Represents a group within the GIS (ArcGIS Online or Portal for ArcGIS).
    """
    def __init__(self, gis, groupid, groupdict=None):
        dict.__init__(self)
        self._gis = gis
        self._portal = gis._portal
        self.groupid = groupid
        self.thumbnail = None
        self._workdir = tempfile.gettempdir()
        # groupdict = self._portal.get_group(self.groupid)
        self._hydrated = False
        if groupdict:
            self.__dict__.update(groupdict)
            super(Group, self).update(groupdict)

    def _hydrate(self):
        groupdict = self._portal.get_group(self.groupid)
        self._hydrated = True
        super(Group, self).update(groupdict)
        self.__dict__.update(groupdict)

    def __getattr__(self, name): # support group attributes as group.access, group.owner, group.phone etc
        if not self._hydrated and not name.startswith('_'):
            self._hydrate()
        try:
            return dict.__getitem__(self, name)
        except:
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))



    def __getitem__(self, k): # support group attributes as dictionary keys on this object, eg. group['owner']
        try:
            return dict.__getitem__(self, k)
        except KeyError:
            if not self._hydrated and not k.startswith('_'):
                self._hydrate()
            return dict.__getitem__(self, k)

    def __str__(self):
        return self.__repr__()
        # state = ["   %s=%r" % (attribute, value) for (attribute, value) in self.__dict__.items()]
        # return '\n'.join(state)

    def __repr__(self):
        return '<%s title:"%s" owner:%s>' % (type(self).__name__, self.title, self.owner)

    def get_thumbnail_link(self):
        """ URL to the thumbnail image """
        thumbnail_file = self.thumbnail
        if thumbnail_file is None:
            return self._portal.url + '/home/images/group-no-image.png'
        else:
            thumbnail_url_path = self._portal.con.baseurl + 'community/groups/' + self.groupid + '/info/' + thumbnail_file
            return thumbnail_url_path

    def _repr_html_(self):
        thumbnail = self.thumbnail
        if self.thumbnail is None or not self._portal.is_logged_in:
            thumbnail = self.get_thumbnail_link()
        else:
            b64 = base64.b64encode(self.get_thumbnail())
            thumbnail = "data:image/png;base64," + str(b64,"utf-8") + "' "

        title = 'Not Provided'
        snippet = 'Not Provided'
        description = 'Not Provided'
        owner = 'Not Provided'
        try:
            title = self.title
        except:
            title = 'Not Provided'

        try:
            description = self.description
        except:
            description = 'Not Provided'

        try:
            snippet = self.snippet
        except:
            snippet = 'Not Provided'

        try:
            owner = self.owner
        except:
            owner = 'Not available'

        url = self._portal.url  + "/home/group.html?id=" + self.groupid
        return """<div class="9item_container" style="height: auto; overflow: hidden; border: 1px solid #cfcfcf; border-radius: 2px; background: #f6fafa; line-height: 1.21429em; padding: 10px;">
                    <div class="item_left" style="width: 210px; float: left;">
                       <a href='""" + str(url) + """' target='_blank'>
                        <img src='""" + str(thumbnail) + """' class="itemThumbnail">
                       </a>
                    </div>

                    <div class="item_right" style="float: none; width: auto; overflow: hidden;">
                        <a href='""" + str(url) + """' target='_blank'><b>""" + str(title) + """</b>
                        </a>
                        <br/>
                        <br/><b>Summary</b>: """ + str(snippet) + """
                        <br/><b>Description</b>: """ + str(description)  + """
                        <br/><b>Owner</b>: """ + str(owner)  + """
                        <br/><b>Created</b>: """ + str(datetime.fromtimestamp(self.created/1000).strftime("%B %d, %Y")) + """

                    </div>
                </div>
                """

    def content(self, max_items=1000):
        """
        Gets the list of items shared with this group.


        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        max_items              Required integer. The maximum number of items to be returned, defaults to 1000.
        ==================     ====================================================================


        :return:
           The list of items that are shared.

        """
        itemlist = []
        items = self._portal.search('group:' + self.groupid, max_results=max_items, outside_org=True)
        for item in items:
            itemlist.append(Item(self._gis, item['id'], item))
        return itemlist

    def delete(self):
        """
        Deletes this group.

        :return:
           A boolean indicating success (True) or failure (False).

        """
        return self._portal.delete_group(self.groupid)

    def get_thumbnail(self):
        """
        Gets the bytes that make up the thumbnail for this group.


        :return:
            Bytes that represent the image.

        Example

        .. code-block:: python

            response = group.get_thumbnail()
            f = open(filename, 'wb')
            f.write(response)
        """
        return self._portal.get_group_thumbnail(self.groupid)

    def download_thumbnail(self, save_folder=None):
        """
        Downloads the group thumbnail for this group.


        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        save_folder            Optional string. The file path to where the group thumbnail will be downloaded.
        ==================     ====================================================================


        :return:
           The file path to which the group thumbnail is downloaded.
        """
        if self.thumbnail is None:
            self._hydrate()
        thumbnail_file = self.thumbnail
        # Only proceed if a thumbnail exists
        if thumbnail_file:
            thumbnail_url_path = 'community/groups/' + self.groupid + '/info/' + thumbnail_file
            if thumbnail_url_path:
                if not save_folder:
                    save_folder = self._workdir
                file_name = os.path.split(thumbnail_file)[1]
                if len(file_name) > 50: #If > 50 chars, truncate to last 30 chars
                    file_name = file_name[-30:]

                file_path = os.path.join(save_folder, file_name)
                self._portal.con.get(path=thumbnail_url_path, try_json=False,
                                     out_folder=save_folder,
                                            file_name=file_name)
                return file_path

        else:
            return None

    def add_users(self, usernames):
        """ Adds users to this group.

        .. note::
            This method will only work if the user for the
            Portal object is either an administrator for the entire
            Portal or the owner of the group.

        ============  ======================================
        **Argument**  **Description**
        ------------  --------------------------------------
        usernames     Required list of strings or single string.
                      The list of usernames or single username to be added.
        ============  ======================================

        :return:
           A dictionary which contains the users that were not added to the group.
        """
        users = []
        if isinstance(usernames, (list, tuple)) == False:
            usernames = [usernames]
        for u in usernames:
            if isinstance(u, str):
                users.append(u)
            elif isinstance(u, User):
                users.append(u.username)
        return self._portal.add_group_users(users, self.groupid)

    def remove_users(self, usernames):
        """
        Remove users from this group.

        ================  ========================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------
        usernames         Required string.  A comma-separated list of users to be removed.
        ================  ========================================================

        :return:
            A dictionary with a key notRemoved that is a list of users not removed.
        """
        users = []
        for u in usernames:
            if isinstance(u, str):
                users.append(u)
            elif isinstance(u, User):
                users.append(u.username)

        return self._portal.remove_group_users(users, self.groupid)

    def invite_users(self, usernames, role='group_member', expiration=10080):
        """
        Invites users to this group. The user executing this command must be the group owner.

        .. note::
            A user who is invited to this group will see a list of invitations
            in the "Groups" tab of Portal listing invitations.  The user
            can either accept or reject the invitation.

        ================  ========================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------
        usernames         Required string. The users to invite as a list.
        ----------------  --------------------------------------------------------
        role              Optional string. Either group_member (the default) or group_admin.
        ----------------  --------------------------------------------------------
        expiration        Optional integer. Specifies how long the invitation is
                          valid for in minutes.  Default is 10,080 minutes (7 days).
        ================  ========================================================

        :return:
           A boolean indicating success (True) or failure (False).
        """
        return self._portal.invite_group_users(usernames, self.groupid, role, expiration)

    def reassign_to(self, target_owner):
        """
        Reassigns this group to another owner.

        ================  ========================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------
        target_owner      Required string.  The username of the new group owner.
        ================  ========================================================

        :return:
            A boolean indicating success (True) or failure (False).
        """
        return self._portal.reassign_group(self.groupid, target_owner)

    def get_members(self):
        """
        Gets the members of this group.


        *Key:Value Dictionary Return Values*

            ================  ========================================================
            **Key**           **Value**
            ----------------  --------------------------------------------------------
            owner             The group's owner (string).
            ----------------  --------------------------------------------------------
            admins            The group's admins (list of strings). Typically this is the same as the owner.
            ----------------  --------------------------------------------------------
            users             The members of the group (list of strings).
            ================  ========================================================


        :return:
            A dictionary with keys: owner, admins, and users.


        .. code-block:: python

            # Usage Example: To print users in a group

            response = group.get_members()
            for user in response['users'] :
                print(user)

        """
        return self._portal.get_group_members(self.groupid)

    def update(self, title=None, tags=None, description=None, snippet=None, access=None,
               is_invitation_only=None, sort_field=None, sort_order=None, is_view_only=None,
               thumbnail=None, max_file_size=None, users_update_items=False):
        """
        Updates this group with only values supplied for particular arguments.


        ==================  =========================================================
        **Argument**        **Description**
        ------------------  ---------------------------------------------------------
        title               Optional string. The new name of the group.
        ------------------  ---------------------------------------------------------
        tags                Optional string. A comma-delimited list of new tags, or
                            a list of tags as strings.
        ------------------  ---------------------------------------------------------
        description         Optional string. The new description for the group.
        ------------------  ---------------------------------------------------------
        snippet             Optional string. A new short snippet (<250 characters)
                            that summarizes the group.
        ------------------  ---------------------------------------------------------
        access              Optional string. Choices are private, public, or org.
        ------------------  ---------------------------------------------------------
        is_invitation_only  Optional boolean. Defines whether users can join by
                            request. True means an invitation is required.
        ------------------  ---------------------------------------------------------
        sort_field          Optional string. Specifies how shared items with the
                            group are sorted.
        ------------------  ---------------------------------------------------------
        sort_order          Optional string. Choices are asc or desc for ascending
                            or descending, respectively.
        ------------------  ---------------------------------------------------------
        is_view_only        Optional boolean. Defines whether the group is searchable.
                            True means the group is searchable.
        ------------------  ---------------------------------------------------------
        thumbnail           Optional string. URL or file location to a new group image.
        ------------------  ---------------------------------------------------------
        max_file_size       Optional integer.  This is the maximum file size allowed
                            be uploaded/shared to a group. Default value is: 1024000
        ------------------  ---------------------------------------------------------
        users_update_items  Optional boolean.  Members can update all items in this
                            group.  Updates to an item can include changes to the
                            item's description, tags, metadata, as well as content.
                            This option can't be disabled once the group has
                            been created. Default is False.
        ==================  =========================================================


        :return:
            A boolean indicating success (True) or failure (False).
        """
        if max_file_size is None:
            max_file_size = 1024000
        if users_update_items is None:
            users_update_items = False
        if tags is not None:
            if type(tags) is list:
                tags = ",".join(tags)
        isinstance(self._portal, portalpy.Portal)
        resp = self._portal.update_group(self.groupid, title, tags,
                                         description, snippet, access,
                                         is_invitation_only, sort_field,
                                         sort_order, is_view_only, thumbnail,
                                         max_file_size, users_update_items)
        if resp:
            self._hydrate()
        return resp

    def leave(self):
        """
        Removes the logged in user from this group.  It is required
        that the user be logged in.


        :return:
           A boolean indicating success (True) or failure (False).
        """
        return self._portal.leave_group(self.groupid)

    def join(self):
        """
        Users apply to join a group using the Join Group operation. This
        creates a new group application, which the group administrators
        accept or decline. This operation also creates a notification for
        the user indicating that they have applied to join this group.
        Available only to authenticated users.
        Users can only apply to join groups to which they have access. If
        the group is private, users will not be able to find it to ask to
        join it.
        Information pertaining to the applying user, such as their full
        name and username, can be sent as part of the group application.

        :return:
             A boolean indicating success (True) or failure (False).
        """
        url = "community/groups/%s/join" % (self.groupid)
        params = {"f" : "json"}
        res = self._portal.con.post(url, params)
        if 'success' in res:
            return res['success'] == True
        return res
    #----------------------------------------------------------------------
    @property
    def applications(self):
        """
        Gets the group applications for the given group as a list. Available to
        administrators of the group or administrators of an organization if
        the group is part of one.
        """
        apps = []
        try:
            path = "%scommunity/groups/%s/applications" % (self._portal.resturl, self.groupid)
            params = {"f" : "json"}
            res = self._portal.con.post(path, params)
            if 'applications' in res:
                for app in res['applications']:
                    url = "%s/%s" % (path, app['username'])
                    apps.append(GroupApplication(url=url, gis=self._gis))
        except:
            print()
        return apps

class GroupApplication(object):
    """
    Represents a single group application on the GIS (ArcGIS Online or
    Portal for ArcGIS).
    """
    _con = None
    _portal =  None
    _gis = None
    _url = None
    _properties = None
    def __init__(self, url, gis, **kwargs):
        initialize = kwargs.pop('initialize', False)
        self._url = url
        self._gis = gis
        self._portal = gis._portal
        self._con = self._portal.con
        if initialize:
            self._init()

    def _init(self):
        """Loads the properties."""
        try:
            res = self._con.get(self._url, {'f':'json'})
            self._properties = PropertyMap(res)
            self._json_dict = res
        except:
            self._properties = PropertyMap({})
            self._json_dict = {}

    @property
    def properties(self):
        """Gets the properties of the Group application."""
        if self._properties is None:
            self._init()
        return self._properties

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '<%s for %s>' % (type(self).__name__, self.properties.username)

    def accept(self):
        """
        When a user applies to join a group, a group application is
        created. Group administrators choose to accept this application
        using the Accept Group Application operation. This operation adds
        the applying user to the group then deletes the application. This
        operation also creates a notification for the user indicating that
        the user's group application was accepted. Available only to group
        owners and admins.

        :return:
           A boolean indicating success (True) or failure (False).
        """
        url = "%s/accept" % self._url
        params = {"f" : "json"}
        res = self._con.post(url, params)
        if 'success' in res:
            return res['success'] == True
        return res

    def decline(self):
        """
        When a user applies to join a group, a group application is
        created. Group administrators can decline this application using
        this method. This method
        deletes the application and creates a notification for the user
        indicating that the user's group application was declined. The
        applying user will not be added to the group. Available only to
        group owners and admins.

        :return:
           A boolean indicating success (True) or failure (False).
        """
        url = "%s/decline" % self._url
        params = {"f" : "json"}
        res = self._con.post(url, params)
        if 'success' in res:
            return res['success'] == True
        return res

class User(dict):
    """
    Represents a registered user of the GIS (ArcGIS Online, or Portal for ArcGIS).
    """
    def __init__(self, gis, username, userdict=None):
        dict.__init__(self)
        self._gis = gis
        self._portal = gis._portal
        self.username = username
        self.thumbnail = None
        self._workdir = tempfile.gettempdir()
        # userdict = self._portal.get_user(self.username)
        self._hydrated = False
        if userdict:
            if 'groups' in userdict and len(userdict['groups']) == 0: # groups aren't set unless hydrated
                del userdict['groups']
            self.__dict__.update(userdict)
            super(User, self).update(userdict)

    # Using http://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/?in=user-97991

    def _hydrate(self):
        userdict = self._portal.get_user(self.username)
        self._hydrated = True
        super(User, self).update(userdict)
        self.__dict__.update(userdict)

    def __getattr__(self, name): # support user attributes as user.access, user.email, user.role etc
        if not self._hydrated and not name.startswith('_'):
            self._hydrate()
        try:
            return dict.__getitem__(self, name)
        except:
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))


    def __getitem__(self, k): # support user attributes as dictionary keys on this object, eg. user['role']
        try:
            return dict.__getitem__(self, k)
        except KeyError:
            if not self._hydrated and not k.startswith('_'):
                self._hydrate()
            return dict.__getitem__(self, k)

    def __str__(self):
        return self.__repr__()
        # state = ["   %s=%r" % (attribute, value) for (attribute, value) in self.__dict__.items()]
        # return '\n'.join(state)


    def __repr__(self):
        return '<%s username:%s>' % (type(self).__name__, self.username)

    def get_thumbnail_link(self):
        """ Retrieves the URL to the thumbnail image.

        :return:
           The thumbnail's URL.
        """
        thumbnail_file = self.thumbnail
        if thumbnail_file is None:
            return self._portal.url + '/home/js/arcgisonline/css/images/no-user-thumb.jpg'
        else:
            thumbnail_url_path = self._portal.con.baseurl + '/community/users/' + self.username + '/info/' + thumbnail_file
            return thumbnail_url_path

    def _repr_html_(self):
        thumbnail = self.thumbnail
        if self.thumbnail is None or not self._portal.is_logged_in:
            thumbnail = self.get_thumbnail_link()
        else:
            b64 = base64.b64encode(self.get_thumbnail())
            thumbnail = "data:image/png;base64," + str(b64,"utf-8") + "' width='200' height='133"

        firstName = 'Not Provided'
        lastName = 'Not Provided'
        fullName = 'Not Provided'
        description = "This user has not provided any personal information."

        try:
            firstName = self.firstName
        except:
            firstName = 'Not Provided'

        try:
            lastName = self.lastName
        except:
            firstName = 'Not Provided'

        try:
            fullName = self.fullName
        except:
            fullName = 'Not Provided'

        try:
            description = self.description
        except:
            description = "This user has not provided any personal information."

        url = self._portal.url  + "/home/user.html?user=" + self.username

        return """<div class="9item_container" style="height: auto; overflow: hidden; border: 1px solid #cfcfcf; border-radius: 2px; background: #f6fafa; line-height: 1.21429em; padding: 10px;">
                    <div class="item_left" style="width: 210px; float: left;">
                       <a href='""" + str(url) + """' target='_blank'>
                        <img src='""" + str(thumbnail) + """' class="itemThumbnail">
                       </a>
                    </div>

                    <div class="item_right" style="float: none; width: auto; overflow: hidden;">
                        <a href='""" + str(url) + """' target='_blank'><b>""" + str(fullName) + """</b>
                        </a>
                        <br/><br/><b>Bio</b>: """ + str(description) + """
                        <br/><b>First Name</b>: """ + str(firstName) + """
                        <br/><b>Last Name</b>: """ + str(lastName)  + """
                        <br/><b>Username</b>: """ + str(self.username)  + """
                        <br/><b>Joined</b>: """ + str(datetime.fromtimestamp(self.created/1000).strftime("%B %d, %Y")) + """

                    </div>
                </div>
                """
    @property
    def groups(self):
        """Gets a list of Group objects the current user belongs to."""
        return [Group(self._gis, group['id']) for group in self['groups']]
    #----------------------------------------------------------------------
    def update_level(self, level):
        """
        Allows only administrators
        of an organization to update the level of a user. Administrators can
        leverage two levels of membership when assigning roles and
        privileges to members. Membership levels allow organizations to
        control access to some ArcGIS capabilities for some members while
        granting more complete access to other members. Level 1 membership
        is designed for members who need privileges to view and interact
        with existing content, while Level 2 membership is for those who
        contribute, create, and share content and groups, in addition to
        other tasks.

        Maximum user quota of an organization at the given level is checked
        before allowing the update.

        Built-in roles including organization administrator, publisher, and
        user are assigned as Level 2, members with custom roles can be
        assigned as Level 1 or Level 2.

        Level 1 membership allows for limited capabilities given through a
        maximum of 8 privileges: `portal:user:joinGroup,
        portal:user:viewOrgGroups, portal:user:viewOrgItems,
        portal:user:viewOrgUsers, premium:user:geocode,
        premium:user:networkanalysis, premium:user:demographics, and
        premium:user:elevation`. If updating the role of a Level 1 user with
        a custom role that has more privileges than the eight, additional
        privileges will be disabled for the user to ensure restriction.

        Level 1 users are not allowed to own any content or group which can
        be reassigned to other users through the Reassign Item and Reassign
        Group operations before downgrading them. The operation will also
        fail if the user being updated has got licenses assigned to premium
        apps that are not allowed at the targeting level.

        =====================  =========================================================
        **Argument**           **Description**
        ---------------------  ---------------------------------------------------------
        level                  Required integer. The values of 1 or 2. This is the user
                               level for the given user.
        =====================  =========================================================

        :returns:
           A boolean indicating success (True) or failure (False).
        """
        if 'roleId' in self and \
           self['roleId'] != 'iAAAAAAAAAAAAAAA':
            self.update_role('iAAAAAAAAAAAAAAA')
            self._hydrated = False
            self._hydrate()
        elif not ('roleId' in self) and level == 1:
            self.update_role('iAAAAAAAAAAAAAAA')
            self._hydrated = False
            self._hydrate()


        if not isinstance(level, int):
            raise ValueError("level must be an integer with values 1 or 2")

        if level < 1 or level > 2:
            raise ValueError("level is an integers with values: 1 or 2")

        url = "%s/portals/self/updateUserLevel" % self._portal.resturl
        params = {
            'user' : self.username,
            'level' : level,
            'f' : 'json'
        }
        res = self._gis._con.post(url, params)
        if 'success' in res:
            return res['success']
        return res

    def reset(self, password, new_password=None, new_security_question=None, new_security_answer=None):
        """ Resets a user's password, security question, and/or security answer.

        .. note::
            This function does not apply to those using enterprise accounts
            that come from an enterprise such as ActiveDirectory, LDAP, or SAML.
            It only has an effect on built-in users.

            If a new security question is specified, a new security answer should
            be provided.

        =====================  =========================================================
        **Argument**           **Description**
        ---------------------  ---------------------------------------------------------
        password               Required string. The current password.
        ---------------------  ---------------------------------------------------------
        new_password           Optional string. The new password if resetting password.
        ---------------------  ---------------------------------------------------------
        new_security_question  Optional string. The new security question if desired.
        ---------------------  ---------------------------------------------------------
        new_security_answer    Optional string. The new security question answer if desired.
        =====================  =========================================================

        :return:
            A boolean indicating success (True) or failure (False).

        """
        return self._portal.reset_user(self.username, password, new_password,
                                       new_security_question, new_security_answer)

    def update(self, access=None, preferred_view=None, description=None, tags=None,
               thumbnail=None, fullname=None, email=None, culture=None, region=None,
               first_name=None, last_name=None, security_question=None, security_answer=None):
        """ Updates this user's properties.

        .. note::
            Only pass in arguments for properties you want to update.
            All other properties will be left as they are.  If you
            want to update the description, then only provide
            the description argument.

        .. note::
            When updating the security question, you must provide a
            security_answer as well.

        ==================  ==========================================================
        **Argument**        **Description**
        ------------------  ----------------------------------------------------------
        access              Optional string. The access level for the user, values
                            allowed are private, org, public.
        ------------------  ----------------------------------------------------------
        preferred_view      Optional string. The preferred view for the user, values allowed are Web, GIS, null.
        ------------------  ----------------------------------------------------------
        description         Optional string. A description of the user.
        ------------------  ----------------------------------------------------------
        tags                Optional string. Tags listed as comma-separated values, or a list of strings.
        ------------------  ----------------------------------------------------------
        thumbnail           Optional string. The path or url to a file of type PNG, GIF,
                            or JPEG. Maximum allowed size is 1 MB.
        ------------------  ----------------------------------------------------------
        fullname            Optional string. The full name of this user, only for built-in users.
        ------------------  ----------------------------------------------------------
        email               Optional string. The e-mail address of this user, only for built-in users.
        ------------------  ----------------------------------------------------------
        culture             Optional string. The two-letter language code, fr for example.
        ------------------  ----------------------------------------------------------
        region              Optional string. The two-letter country code, FR for example.
        ------------------  ----------------------------------------------------------
        first_name          Optional string. User's first name.
        ------------------  ----------------------------------------------------------
        last_name           Optional string. User's first name.
        ------------------  ----------------------------------------------------------
        security_question   Optional integer.  The is a number from 1-14.  The
                            questions are as follows:

                            1. What city were you born in?
                            2. What was your high school mascot?
                            3. What is your mother's maden name?
                            4. What was the make of your first car?
                            5. What high school did you got to?
                            6. What is the last name of your best friend?
                            7. What is the middle name of your youngest sibling?
                            8. What is the name of the street on which your grew up?
                            9. What is the name of your favorite fictional character?
                            10. What is the name of your favorite pet?
                            11. What is the name of your favorite restaurant?
                            12. What is the title of your facorite book?
                            13. What is your dream job?
                            14. Where did you go on your first date?

                            Usage Example:

                            security_question=13
        ------------------  ----------------------------------------------------------
        security_answer     Optional string.  This is the answer to security querstion.
                            If you are changing a user's question, an answer must be
                            provided.

                            Usage example:

                            security_answer="Working on the Python API"
        ==================  ==========================================================

        :return:
           A boolean indicating success (True) or failure (False).

        """
        user_type = None
        if tags is not None and \
           isinstance(tags, list):
            tags = ",".join(tags)
        import copy
        params = {"f" : "json",
                  'access' : access,
                  'preferredView' : preferred_view,
                  'description' : description,
                  'tags' : tags,
                  'password' : None,
                  'fullname' : fullname,
                  'email' : email,
                  'securityQuestionIdx' : None,
                  'securityAnswer' : None,
                  'culture' : culture,
                  'region' : region,
                  'firstName' : first_name,
                  'lastName' : last_name
                  }
        if security_answer and security_question:
            params['securityQuestionIdx'] = security_question
            params['securityAnswer'] = security_answer
        for k,v in copy.copy(params).items():
            if v is None:
                del params[k]

        if thumbnail:
            files = {'thumbnail' : thumbnail}
        else:
            files = None
        url = "%s/sharing/rest/community/users/%s/update" % (self._gis._url,
                                                             self.username)
        ret = self._gis._con.post(path=url,
                                  postdata=params,
                                  files=files)
        if ret['success'] == True:
            self._hydrate()
        return ret['success']
    #----------------------------------------------------------------------
    def disable(self):
        """
        Disables login access for the
        user. It is only available to the administrator of the organization.

        :return:
           A boolean indicating success (True) or failure (False).

        """
        params = {"f" : "json"}
        url = "%s/sharing/rest/community/users/%s/disable" % (self._gis._url, self.username)
        res = self._gis._con.post(url, params)
        if 'status' in res:
            self._hydrate()
            return res['status'] == 'success'
        elif 'success' in res:
            self._hydrate()
            return res['success']
        return False
    #----------------------------------------------------------------------
    def enable(self):
        """
        Enables login access for the user.
        It is only available to the administrator of the organization.
        """
        params = {"f" : "json"}
        url = "%s/sharing/rest/community/users/%s/enable" % (self._gis._url, self.username)
        res = self._gis._con.post(url, params)
        if 'status' in res:
            self._hydrate()
            return res['status'] == 'success'
        elif 'success' in res:
            self._hydrate()
            return res['success']
        return False
    #----------------------------------------------------------------------
    @property
    def esri_access(self):
        """
        Enable or disable 'Esri access'. Administrator privileges required.
        A member whose account has Esri access enabled can use My Esri and
        Community and Forums (GeoNet), access e-Learning on the Training
        website, and manage email communications from Esri. The member
        cannot enable or disable their own access to these Esri resources.

        Please see: http://doc.arcgis.com/en/arcgis-online/administer/manage-members.htm#ESRI_SECTION1_7CE845E428034AE8A40EF8C1085E2A23
        for more information.


        """
        if self._portal.is_arcgisonline:
            self._hydrate()
            return self['userType']
        else:
            return False
    #----------------------------------------------------------------------
    @esri_access.setter
    def esri_access(self, value):
        """

        Enable or disable 'Esri access'. Administrator privileges required.
        A member whose account has Esri access enabled can use My Esri and
        Community and Forums (GeoNet), access e-Learning on the Training
        website, and manage email communications from Esri. The member
        cannot enable or disable their own access to these Esri resources.

        Please see: http://doc.arcgis.com/en/arcgis-online/administer/manage-members.htm#ESRI_SECTION1_7CE845E428034AE8A40EF8C1085E2A23
        for more information.


        ================  ==========================================================
        **Argument**      **Description**
        ----------------  ----------------------------------------------------------
        value             Required boolean. The current user will be allowed to use
                          the username for other Esri/ArcGIS logins when the value
                          is set to True. If false, the account can only be used to
                          access a given individual's organization.
        ================  ==========================================================
        """
        if self._portal.is_arcgisonline:
            if value == True:
                ret = self._portal.update_user(self.username,
                                               user_type="both")
            else:
                ret = self._portal.update_user(self.username,
                                               user_type="arcgisonly")
            self._hydrate()
    #----------------------------------------------------------------------
    @property
    def linked_accounts(self):
        """returns all linked account for the current user as User objects"""
        url = "%s/sharing/rest/community/users/%s/linkedUsers" % (self._gis._url,
                                                                  self.username)
        start = 1
        params = {
            'f' : 'json',
            'num' : 10,
            'start' : start
        }
        users = []
        res = self._gis._con.get(url, params)
        users = res["linkedUsers"]
        if len(users) == 0:
            return users
        else:
            while (res["nextStart"] > -1):
                start += 10
                params['start'] = start
                res = self._gis._con.get(url, params)
                users += res['linkedUsers']
        users = [self._gis.users.get(user['username']) for user in users]
        return users
    #----------------------------------------------------------------------
    def link_account(self, username, user_gis):
        """
        If you use multiple accounts for ArcGIS Online and Esri websites,
        you can link them so you can switch between accounts and share your
        Esri customer information with My Esri, e-Learning, and GeoNet. You
        can link your organizational, public, enterprise, and social login
        accounts. Your content and privileges are unique to each account.
        From Esri websites, only Esri access-enabled accounts appear in
        your list of linked accounts.

        See: http://doc.arcgis.com/en/arcgis-online/reference/sign-in.htm for
        addtional information.

        ================  ==========================================================
        **Argument**      **Description**
        ----------------  ----------------------------------------------------------
        username          required string/User. This is the username or User object
                          that a user wants to link to.
        ----------------  ----------------------------------------------------------
        user_gis          required GIS.  This is the GIS object for the username.
                          In order to link an account, a user must be able to login
                          to that account.  The GIS object is the entry into that
                          account.
        ================  ==========================================================

        returns: Boolean. True for success, False for failure.

        """
        userToken = user_gis._con.token
        if isinstance(username, User):
            username = username.username
        params = {
            'f' : 'json',
            'user' : username,
            'userToken' : userToken
        }
        url = "%s/sharing/rest/community/users/%s/linkUser" % (self._gis._url, self.username)
        res = self._gis._con.post(url, params)
        if 'success' in res:
            return res['success']
        return False
    #----------------------------------------------------------------------
    def unlink_account(self, username):
        """
        When a user wishes to no longer have a linked account, the unlink method
        allows for the removal if linked accounts.

        See: http://doc.arcgis.com/en/arcgis-online/reference/sign-in.htm for
        addtional information.

        ================  ==========================================================
        **Argument**      **Description**
        ----------------  ----------------------------------------------------------
        username          required string/User. This is the username or User object
                          that a user wants to unlink.
        ================  ==========================================================

        returns: boolean.
        """
        if isinstance(username, User):
            username = username.username
        params = {
            'f' : 'json',
            'user' : username
        }
        url = "%s/sharing/rest/community/users/%s/unlinkUser" % (self._gis._url, self.username)
        res = self._gis._con.post(url, params)
        if 'success' in res:
            return res['success']
        return False
    #----------------------------------------------------------------------
    def update_role(self, role):
        """
        Updates this user's role to org_user, org_publisher, org_admin, or a custom role.

        .. note::
            There are four types of roles in Portal - user, publisher, administrator and custom roles.
            A user can share items, create maps, create groups, etc.  A publisher can
            do everything a user can do and additionally create hosted services.  An administrator can
            do everything that is possible in Portal. A custom roles privileges can be customized.

        ================  ========================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------
        role              Required string. Value must be either org_user,
                          org_publisher, org_admin,
                          or a custom role object (from gis.users.roles).
        ================  ========================================================

        :return:
            A boolean indicating success (True) or failure (False).

        """
        if isinstance(role, Role):
            role = role.role_id
        passed = self._portal.update_user_role(self.username, role)
        if passed:
            self._hydrate()
            self.role = role
        return passed

    def delete(self, reassign_to=None):
        """
        Deletes this user from the portal, optionally deleting or reassigning groups and items.

        .. note::
            You can not delete a user in Portal if that user owns groups or items.  If you
            specify someone in the reassign_to argument, then items and groups will be
            transferred to that user.  If that argument is not set then the method
            will fail if the user has items or groups that need to be reassigned.

        ================  ========================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------
        reassign_to       Optional string. The new owner of the items and groups
                          that belong to the user being deleted.
        ================  ========================================================

        :return:
            A boolean indicating success (True) or failure (False).

        """
        if isinstance(reassign_to, User):
            reassign_to = reassign_to.username
        return self._portal.delete_user(self.username, reassign_to)

    def reassign_to(self, target_username):
        """
        Reassigns all of this user's items and groups to another user.

        Items are transferred to the target user into a folder named
        <user>_<folder> where user corresponds to the user whose items were
        moved and folder corresponds to the folder that was moved.

        .. note::
            This method must be executed as an administrator.  This method also
            can not be undone.  The changes are immediately made and permanent.

        ================  ===========================================================
        **Argument**      **Description**
        ----------------  -----------------------------------------------------------
        target_username   Required string. The user who will be the new owner of the
                          items and groups from which these are being reassigned from.
        ================  ===========================================================

        :return:
            A boolean indicating success (True) or failure (False).

        """
        if isinstance(target_username, User):
            target_username = target_username.username
        return self._portal.reassign_user(self.username, target_username)

    def get_thumbnail(self):
        """
        Returns the bytes that make up the thumbnail for this user.

        :return:
            Bytes that represent the image.

        .. code-block:: python

            Usage Example:

            response = user.get_thumbnail()
            f = open(filename, 'wb')
            f.write(response)

        """
        thumbnail_file = self.thumbnail
        if thumbnail_file:
            thumbnail_url_path = 'community/users/' + self.username + '/info/' + thumbnail_file
            if thumbnail_url_path:
                return self._portal.con.get(thumbnail_url_path, try_json=False, force_bytes=True)

    def download_thumbnail(self, save_folder=None):
        """
        Downloads the item thumbnail for this user.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        save_folder            Optional string. The desired folder name to download the thumbnail to.
        ==================     ====================================================================


        :return:
           The file path of the downloaded thumbnail.
        """
        thumbnail_file = self.thumbnail

        # Only proceed if a thumbnail exists
        if thumbnail_file:
            thumbnail_url_path = 'community/users/' + self.username + '/info/' + thumbnail_file
            if thumbnail_url_path:
                if not save_folder:
                    save_folder = self._workdir
                file_name = os.path.split(thumbnail_file)[1]
                if len(file_name) > 50: #If > 50 chars, truncate to last 30 chars
                    file_name = file_name[-30:]

                file_path = os.path.join(save_folder, file_name)
                return self._portal.con.get(path=thumbnail_url_path, try_json=False,
                                            out_folder=save_folder,
                                     file_name=file_name)
        else:
            return None

    @property
    def folders(self):
        """Gets the list of the user's folders"""
        return self._portal.user_folders(self.username)

    def items(self, folder=None, max_items=100):
        """
        Provides a list of items in the specified folder. For content in the root folder, use
        the default value of None for the folder argument. For other folders, pass in the folder
        name as a string, or as a dictionary containing
        the folder ID, such as the dictionary obtained from the folders property.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        folder                 Optional string. The specifc folder (as a string or dictionary)
                               to get a list of items in.
        ------------------     --------------------------------------------------------------------
        max_items              Optional integer. The maximum number of items to be returned. The default is 100.
        ==================     ====================================================================

        :return:
           The list of items in the specified folder.
        """
        items = []
        folder_id = None
        if folder is not None:
            if isinstance(folder, str):
                folder_id = self._portal.get_folder_id(self.username, folder)
                if folder_id is None:
                    msg = "Could not locate the folder: %s" % folder
                    raise ValueError("%s. Please verify that this folder exists and try again." % msg)
            elif isinstance(folder, dict):
                folder_id = folder['id']
            else:
                print("folder should be folder name as a string"
                      "or a dict containing the folder 'id'")

        resp = self._portal.user_items(self.username, folder_id, max_items)
        for item in resp:
            items.append(Item(self._gis, item['id'], item))

        return items
    #----------------------------------------------------------------------
    @property
    def notifications(self):
        """
        Gets the list of notifications available for the given user.
        """
        from .._impl.notification import Notification
        result = []
        url = "%s/community/users/%s/notifications" % (self._portal.resturl, self.username)
        params = {"f" : "json"}
        ns = self._portal.con.get(url, params)
        if "notifications" in ns:
            for n in ns["notifications"]:
                result.append(Notification(url="%s/%s" % (url, n['id']),
                                           user=self,
                                           data=n,
                                           initialize=False)
                              )
                del n
            return result
        return result

class Item(dict):
    """
    An item (a unit of content) in the GIS. Each item has a unique identifier and a well
    known URL that is independent of the user owning the item.
    An item can have associated binary or textual data that's available via the item data resource.
    For example, an item of type Map Package returns the actual bits corresponding to the
    map package via the item data resource.

    Items that have layers (eg FeatureLayerCollection items and ImageryLayer items) and tables have
    the dynamic `layers` and `tables` properties to get to the individual layers/tables in this item.
    """

    def __init__(self, gis, itemid, itemdict=None):
        dict.__init__(self)
        self._portal = gis._portal
        self._gis = gis
        self.itemid = itemid
        self.thumbnail = None
        self._workdir = tempfile.gettempdir()
        self._hydrated = False
        self.resources = ResourceManager(self, self._gis)

        if itemdict:
            if 'size' in itemdict and itemdict['size'] == -1:
                del itemdict['size'] # remove nonsensical size
            self.__dict__.update(itemdict)
            super(Item, self).update(itemdict)

        if self._has_layers():
            self.layers = None
            self.tables = None
            self['layers'] = None
            self['tables'] = None

    def _has_layers(self):
        return self.type ==  'Feature Collection' or \
               self.type == 'Feature Service' or \
            self.type == 'Big Data File Share' or \
            self.type == 'Image Service' or \
            self.type == 'Map Service' or \
            self.type == 'Globe Service' or \
            self.type == 'Scene Service' or \
            self.type == 'Network Analysis Service' or \
            self.type == 'Vector Tile Service'

    def _populate_layers(self):
        from arcgis.features import FeatureLayer, FeatureCollection, FeatureLayerCollection, Table
        from arcgis.mapping import VectorTileLayer, MapImageLayer
        from arcgis.network import NetworkDataset
        from arcgis.raster import ImageryLayer

        if self._has_layers():
            layers = []
            tables = []

            params = {"f" : "json"}

            if self.type == 'Image Service': # service that is itself a layer
                layers.append(ImageryLayer(self.url, self._gis))

            elif self.type == 'Feature Collection':
                lyrs = self.get_data()['layers']
                for layer in lyrs:
                    layers.append(FeatureCollection(layer))

            elif self.type == 'Big Data File Share':
                serviceinfo = self._portal.con.post(self.url, params)
                for lyr in serviceinfo['children']:
                    lyrurl = self.url + '/' + lyr['name']
                    layers.append(Layer(lyrurl, self._gis))


            elif self.type == 'Vector Tile Service':
                layers.append(VectorTileLayer(self.url, self._gis))

            elif self.type == 'Network Analysis Service':
                svc = NetworkDataset.fromitem(self)

                # route laters, service area layers, closest facility layers
                for lyr in svc.route_layers:
                    layers.append(lyr)
                for lyr in svc.service_area_layers:
                    layers.append(lyr)
                for lyr in svc.closest_facility_layers:
                    layers.append(lyr)

            elif self.type == 'Feature Service':
                m = re.search(r'\d+$', self.url)
                if m is not None:  # ends in digit - it's a single layer from a Feature Service
                    layers.append(FeatureLayer(self.url, self._gis))
                else:
                    svc = FeatureLayerCollection.fromitem(self)
                    for lyr in svc.layers:
                        layers.append(lyr)
                    for tbl in svc.tables:
                        tables.append(tbl)

            elif self.type == 'Map Service':
                svc = MapImageLayer.fromitem(self)
                for lyr in svc.layers:
                    layers.append(lyr)
            else:
                m = re.search(r'\d+$', self.url)
                if m is not None: # ends in digit
                    layers.append(FeatureLayer(self.url, self._gis))
                else:
                    svc = _GISResource(self.url, self._gis)
                    for lyr in svc.properties.layers:
                        if self.type == 'Scene Service':
                            lyr_url = svc.url + '/layers/' + str(lyr.id)
                        else:
                            lyr_url = svc.url+'/'+str(lyr.id)
                        lyr = Layer(lyr_url, self._gis)
                        layers.append(lyr)
                    try:
                        for lyr in svc.properties.tables:
                            lyr = Table(svc.url+'/'+str(lyr.id), self._gis)
                            tables.append(lyr)
                    except:
                        pass

            self.layers = layers
            self.tables = tables
            self['layers'] = layers
            self['tables'] = tables

    def _hydrate(self):
        itemdict = self._portal.get_item(self.itemid)
        self._hydrated = True
        super(Item, self).update(itemdict)
        self.__dict__.update(itemdict)
        try:
            with _DisableLogger():
                self._populate_layers()
        except:
            pass

    def __getattribute__ (self, name):
        if name == 'layers':
            if self['layers'] == None or self['layers'] == []:
                try:
                    with _DisableLogger():
                        self._populate_layers()
                except:
                    pass
                return self['layers']
        elif name == 'tables':
            if self['tables'] == None or self['tables'] == []:
                try:
                    with _DisableLogger():
                        self._populate_layers()
                except:
                    pass
                return self['tables']
        return super(Item, self).__getattribute__(name)

    def __getattr__(self, name): # support item attributes
        if not self._hydrated and not name.startswith('_'):
            self._hydrate()
        try:
            return dict.__getitem__(self, name)
        except:
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))

    def __getitem__(self, k): # support item attributes as dictionary keys on this object
        try:
            return dict.__getitem__(self, k)
        except KeyError:
            if not self._hydrated and not k.startswith('_'):
                self._hydrate()
            return dict.__getitem__(self, k)
    #----------------------------------------------------------------------
    @property
    def content_status(self):
        """
        The content_status property states if an Item is authoritative or deprecated.  This
        givens owners and administrators of Item the ability to warn users that they
        should be either this information or not.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        value                  Optional string or None.  Defines if an Item is deprecated or
                               authoritative.
                               If a value of None is given, then the value will be reset.

                               Allowsed Values: authoritative, deprecated, or None
        ==================     ====================================================================
        """
        try:
            return self.contentStatus
        except:
            return ""

    #----------------------------------------------------------------------
    @content_status.setter
    def content_status(self, value):
        """
        The content_status property states if an Item is authoritative or deprecated.  This
        givens owners and administrators of Item the ability to warn users that they
        should be either this information or not.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        value                  Optional string or None.  Defines if an Item is deprecated or
                               authoritative.
                               If a value of None is given, then the value will be reset.

                               Allowsed Values: authoritative, deprecated, or None
        ==================     ====================================================================
        """
        status_values = ['authoritative',
                         'org_authoritative',
                         'deprecated']

        if value is None:
            pass
        elif str(value).lower() not in status_values:
            raise ValueError("%s is not valid value of: authoritative or deprecated" % value)

        if str(value).lower() == 'authoritative':
            value = 'org_authoritative'

        params = {
            'f' : 'json',
            'status' : value
        }
        url = 'content/items/' + self.itemid + '/setContentStatus'

        if value is None:
            value = ""
            params['status'] = ""
            params['clearEmptyFields'] = True
        else:
            params['clearEmptyFields'] = False
        res = self._portal.con.get(url,
                                   params)
        if 'success' in res:
            self.contentStatus = value
            self._hydrate()

    @property
    def homepage(self):
        """Gets the URL to the HTML page for the item."""
        itemid = self.itemid
        return "%s/home/item.html?id=%s" % (self._portal.resturl.replace("/sharing/rest/", ""), itemid)

    def copy_feature_layer_collection(self, service_name, layers=None, tables=None, folder=None,
                                      description=None, snippet=None, owner=None):
        """
        This operation allows users to copy existing Feature Layer Collections and select the
        layers/tables that the user wants in the service.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        service_name           Required string. It is the name of the service.
        ------------------     --------------------------------------------------------------------
        layers                 Optional list/string.  This is a either a list of integers or a comma
                               seperated list of integers as a string.  Each index value represents
                               a layer in the feature layer collection.
        ------------------     --------------------------------------------------------------------
        tables                 Optional list/string. This is a either a list of integers or a comma
                               seperated list of integers as a string.  Each index value represents
                               a table in the feature layer collection.
        ------------------     --------------------------------------------------------------------
        folder                 Optional string. This is the name of the folder to place in.  The
                               default is None, which means the root folder.
        ------------------     --------------------------------------------------------------------
        description            Optional string. This is the Item description of the service.
        ------------------     --------------------------------------------------------------------
        snippet                Optional string. This is the Item's snippet of the service. It is
                               no longer than 250 characters.
        ------------------     --------------------------------------------------------------------
        owner                  Optional string/User. The default is the current user, but if you
                               want the service to be owned by another user, pass in this value.
        ==================     ====================================================================


        :return:
           Item on success. None on failure

        """
        from ..features import FeatureLayerCollection
        if self.type != "Feature Service" and \
           self.type != "Feature Layer Collection":
            return
        if layers is None and tables is None:
            raise ValueError("An index of layers or tables must be provided")
        content = self._gis.content
        if isinstance(owner, User):
            owner = owner.username
        idx_layers = []
        idx_tables = []
        params = {}
        allowed = ['description', 'allowGeometryUpdates', 'units', 'syncEnabled',
                   'serviceDescription', 'capabilities', 'serviceItemId',
                   'supportsDisconnectedEditing', 'maxRecordCount',
                   'supportsApplyEditsWithGlobalIds', 'name', 'supportedQueryFormats',
                   'xssPreventionInfo', 'copyrightText', 'currentVersion',
                   'syncCapabilities', '_ssl', 'hasStaticData', 'hasVersionedData',
                   'editorTrackingInfo', 'name']
        parent = None
        if description is None:
            description = self.description
        if snippet is None:
            snippet = self.snippet
        i = 1
        is_free = content.is_service_name_available(service_name=service_name,
                                                    service_type="Feature Service")
        if is_free == False:
            while is_free == False:
                i += 1
                s = service_name + "_%s" % i
                is_free = content.is_service_name_available(service_name=s,
                                                            service_type="Feature Service")
                if is_free:
                    service_name = s
                    break
        if len(self.tables) > 0 or len(self.layers) > 0:
            parent = FeatureLayerCollection(url=self.url, gis=self._gis)
        else:
            raise Exception("No tables or layers found in service, cannot copy it.")
        if layers is not None:
            if isinstance(layers, (list, tuple)):
                for idx in layers:
                    idx_layers.append(self.layers[idx])
                    del idx
            elif isinstance(layers, (str)):
                for idx in layers.split(','):
                    idx_layers.append(self.layers[idx])
                    del idx
            else:
                raise ValueError("layers must be a comma seperated list of integers or a list")
        if tables is not None:
            if isinstance(tables, (list, tuple)):
                for idx in tables:
                    idx_tables.append(self.tables[idx])
                    del idx
            elif isinstance(tables, (str)):
                for idx in tables.split(','):
                    idx_tables.append(self.tables[idx])
                    del idx
            else:
                raise ValueError("tables must be a comma seperated list of integers or a list")
        for k, v in dict(parent.properties).items():
            if k in allowed:
                if k.lower() == 'name':
                    params[k] = service_name
                if k.lower() == '_ssl':
                    params['_ssl'] = False
                params[k] = v
            del k, v
        if 'name' not in params.keys():
            params['name'] = service_name
        params['_ssl'] = False
        copied_item = content.create_service(name=service_name,
                                             create_params=params,
                                             folder=folder,
                                             owner=owner,
                                             item_properties={'description':description,
                                                              'snippet': snippet,
                                                              'tags' : self.tags,
                                                              'title' : service_name
                                                              })

        fs = FeatureLayerCollection(url=copied_item.url, gis=self._gis)
        fs_manager = fs.manager
        add_defs = {'layers' : [], 'tables' : []}
        for l in idx_layers:
            v = dict(l.manager.properties)
            if 'indexes' in v:
                del v['indexes']
            if 'adminLayerInfo' in v:
                del v['adminLayerInfo']
            add_defs['layers'].append(v)
            del l
        for l in idx_tables:
            v = dict(l.manager.properties)
            if 'indexes' in v:
                del v['indexes']
            if 'adminLayerInfo' in v:
                del v['adminLayerInfo']
            add_defs['tables'].append(v)
            del l
        res = fs_manager.add_to_definition(json_dict=add_defs)
        if res['success'] ==  True:
            return copied_item
        else:
            try:
                copied_item.delete()
            except: pass
        return None

    def download(self, save_path=None):
        """
        Downloads the data to the specified folder or a temporary folder if a folder is not provided.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        save_path           Optional string. Folder location to download the file to.
        ===============     ====================================================================


        :return:
           The download path if data was available, otherwise None.
        """
        data_path = 'content/items/' + self.itemid + '/data'
        if not save_path:
            save_path = self._workdir
        if data_path:
            download_path = self._portal.con.get(path=data_path, file_name=self.name or self.title,
                                                 out_folder=save_path, try_json=False, force_bytes=False)
            if download_path == '':
                return None
            else:
                return download_path

    def export(self, title, export_format, parameters=None, wait=True):
        """
        Exports a service item to the specified export format.
        Available only to users with an organizational subscription.
        Invokable only by the service item owner or an administrator.
        This is useful for long running exports that could hold up a script.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        title               Required string. The desired name of the exported service item.
        ---------------     --------------------------------------------------------------------
        export_format       Required string. The format to export the data to. Allowed types: 'Shapefile',
                            'CSV', 'File Geodatabase', 'Feature Collection', 'GeoJson', 'Scene Package', 'KML'
        ---------------     --------------------------------------------------------------------
        parameters          Optional string. A JSON object describing the layers to be exported
                            and the export parameters for each layer.  See http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#/Export_Item/02r30000008s000000/
                            for guidance.
        ---------------     --------------------------------------------------------------------
        wait                Optional boolean. Default is True, which forces a wait for the
                            export to complete; use False for when it is okay to proceed while
                            the export continues to completion.
        ===============     ====================================================================


        :return:
           Item or dictionary.  Item is returned when wait=True. A dictionary describing the status of
           the item is returned when wait=False.
        """
        import time
        formats = ['Shapefile',
                   'CSV',
                   'File Geodatabase',
                   'Feature Collection',
                   'GeoJson',
                   'Scene Package',
                   'KML']
        data_path = 'content/users/%s/export' % self._gis.users.me.username
        params = {
            "f" : "json",
            "itemId" : self.itemid,
            "exportFormat" : export_format,
            "title" : title,
        }
        res = self._portal.con.post(data_path, params)
        export_item = Item(gis=self._gis, itemid=res['exportItemId'])
        if wait == True:
            status = "partial"
            while status != "completed":
                status = export_item.status(job_id=res['jobId'],
                                            job_type="export")
                if status['status'] == 'failed':
                    raise Exception("Could not export item: %s" % self.itemid)
                elif status['status'].lower() == "completed":
                    return export_item
                time.sleep(2)
        return res
    #----------------------------------------------------------------------
    def status(self, job_id=None, job_type=None):
        """
        Provides the status when publishing an item, adding an item in
        async mode, or adding with a multipart upload. "Partial" is
        available for Add Item Multipart, when only a part is uploaded
        and the item is not committed.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        job_id              Optional string. The job ID returned during publish, generateFeatures,
                            export, and createService calls.
        ---------------     --------------------------------------------------------------------
        job_type            Optional string. The type of asynchronous job for which the status
                            has to be checked. Default is none, which checks the item's status.
                            This parameter is optional unless used with the operations listed
                            below. Values: `publish`, generateFeatures, export, and createService
        ===============     ====================================================================


        :return:
           The status of a publishing item.
        """
        params = {
            "f" : "json"
        }
        data_path = 'content/users/%s/items/%s/status' % (self._gis.users.me.username, self.itemid)
        if job_type is not None:
            params['jobType'] = job_type
        if job_id is not None:
            params["jobId"] = job_id
        return self._portal.con.get(data_path,
                                    params)
    #----------------------------------------------------------------------
    def get_thumbnail(self):
        """
        Retrieves the bytes that make up the thumbnail for this item.

        :return:
           Bytes that represent the item.

        Example

        .. code-block:: python

            response = item.get_thumbnail()
            f = open(filename, 'wb')
            f.write(response)

        """
        thumbnail_file = self.thumbnail
        if thumbnail_file:
            thumbnail_url_path = 'content/items/' + self.itemid + '/info/' + thumbnail_file
            if thumbnail_url_path:
                return self._portal.con.get(thumbnail_url_path, try_json=False, force_bytes=True)

    def download_thumbnail(self, save_folder=None):
        """
        Downloads the thumbnail for this item.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        save_folder          Optional string. Folder location to download the item's thumbnail to.
        ===============     ====================================================================


        :return:
           For a successful download of the thumbnail, a file path. None if the item does not have a thumbnail.
        """
        if self.thumbnail is None:
            self._hydrate()
        thumbnail_file = self.thumbnail

        # Only proceed if a thumbnail exists
        if thumbnail_file:
            thumbnail_url_path = 'content/items/' + self.itemid  + '/info/' + thumbnail_file
            if thumbnail_url_path:
                if not save_folder:
                    save_folder = self._workdir
                file_name = os.path.split(thumbnail_file)[1]
                if len(file_name) > 50: #If > 50 chars, truncate to last 30 chars
                    file_name = file_name[-30:]

                file_path = os.path.join(save_folder, file_name)
                self._portal.con.get(path=thumbnail_url_path, try_json=False,
                                     out_folder=save_folder,
                                     file_name=file_name)
                return file_path
        else:
            return None

    def get_thumbnail_link(self):
        """ URL to the thumbnail image. """
        thumbnail_file = self.thumbnail
        if thumbnail_file is None:
            if self._gis.properties.portalName == 'ArcGIS Online':
                return 'http://static.arcgis.com/images/desktopapp.png'
            else:
                return self._portal.url + '/portalimages/desktopapp.png'
        else:
            thumbnail_url_path = self._portal.con.baseurl + '/content/items/' + self.itemid + '/info/' + thumbnail_file
            return thumbnail_url_path

    @property
    def metadata(self):
        """ Gets and sets the item metadata for the specified item.
            Returns None if the item does not have metadata.
            Items with metadata have 'Metadata' in their typeKeywords.
        """
        metadataurlpath = 'content/items/' + self.itemid  + '/info/metadata/metadata.xml'
        try:
            return self._portal.con.get(metadataurlpath, try_json=False)

        # If the get operation returns a 400 HTTP Error then the metadata simply
        # doesn't exist, let's just return None in this case
        except HTTPError as e:
            if e.code == 400 or e.code == 500:
                return None
            else:
                raise e

    #----------------------------------------------------------------------
    @metadata.setter
    def metadata(self, value):
        """
        For metadata enabled site, users can get/set metadata from a file
        or XML text.
        """
        import shutil
        from six import string_types
        xml_file = os.path.join(tempfile.gettempdir(), 'metadata.xml')
        if os.path.isfile(xml_file) == True:
            os.remove(xml_file)
        if os.path.isfile(value) == True and \
           str(value).lower().endswith('.xml'):
            if os.path.basename(value).lower() != 'metadata.xml':
                shutil.copy(value, xml_file)
            else:
                xml_file = value
        elif isinstance(value, string_types):
            with open(xml_file, mode='w') as writer:
                writer.write(value)
                writer.close()
        else:
            raise ValueError("Input must be XML path file or XML Text")
        return self.update(metadata=xml_file)

    def download_metadata(self, save_folder=None):
        """
        Downloads the item metadata for the specified item id. Items with metadata have 'Metadata'
        in their typeKeywords.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        save_folder          Optional string. Folder location to download the item's metadata to.
        ===============     ====================================================================


        :return:
           For a successful download of metadata, a file path. None if the item does not have metadata.
        """
        metadataurlpath = 'content/items/' + self.itemid + '/info/metadata/metadata.xml'
        if not save_folder:
            save_folder = self._workdir
        try:
            file_name="metadata.xml"
            file_path = os.path.join(save_folder, file_name)
            self._portal.con.get(path=metadataurlpath,
                                 out_folder=save_folder,
                                     file_name=file_name, try_json=False)
            return file_path

        # If the get operation returns a 400 HTTP/IO Error then the metadata
        # simply doesn't exist, let's just return None in this case
        except HTTPError as e:
            if e.code == 400 or e.code == 500:
                return None
            else:
                raise e

    def _get_icon(self):
        icon = "layers16.png"
        if self.type.lower() == "web map":
            icon = "maps16.png"
        elif self.type.lower() == "web scene":
            icon = "websceneglobal16.png"
        elif self.type.lower() == "cityengine web scene":
            icon = "websceneglobal16.png"
        elif self.type.lower() == "pro map":
            icon = "mapsgray16.png"
        elif self.type.lower() == "feature service":
            icon = "featureshosted16.png"
        elif self.type.lower() == "map service":
            icon = "mapimages16.png"
        elif self.type.lower() == "image service":
            icon = "imagery16.png"
        elif self.type.lower() == "kml":
            icon = "features16.png"
        elif self.type.lower() == "wms":
            icon = "mapimages16.png"
        elif self.type.lower() == "feature collection":
            icon = "features16.png"
        elif self.type.lower() == "feature collection template":
            icon = "maps16.png"
        elif self.type.lower() == "geodata service":
            icon = "layers16.png"
        elif self.type.lower() == "globe service":
            icon = "layers16.png"
        elif self.type.lower() == "shapefile":
            icon = "datafiles16.png"
        elif self.type.lower() == "web map application":
            icon = "apps16.png"
        elif self.type.lower() == "map package":
            icon = "mapsgray16.png"
        elif self.type.lower() == "feature layer":
            icon = "featureshosted16.png"
        elif self.type.lower() == "map service":
            icon = "maptiles16.png"
        elif self.type.lower() == "map document":
            icon = "mapsgray16.png"
        else:
            icon = "layers16.png"

        icon = self._portal.url + '/home/js/jsapi/esri/css/images/item_type_icons/' + icon
        return icon

    def _ux_item_type(self):
        item_type= self.type
        if self.type == 'Geoprocessing Service':
            item_type = 'Geoprocessing Toolbox'
        elif self.type.lower() == 'feature service':
            item_type = 'Feature Layer Collection'
        elif self.type.lower() == 'map service':
            item_type = 'Map Image Layer'
        elif self.type.lower() == 'image service':
            item_type = 'Imagery Layer'
        elif self.type.lower().endswith('service'):
            item_type = self.type.replace('Service', 'Layer')
        return item_type

    def _repr_html_(self):
        thumbnail = self.thumbnail
        if self.thumbnail is None or not self._portal.is_logged_in:
            thumbnail = self.get_thumbnail_link()
        else:
            try:
                b64 = base64.b64encode(self.get_thumbnail())
                thumbnail = "data:image/png;base64," + str(b64,"utf-8") + "' width='200' height='133"
            except:
                if self._gis.properties.portalName == 'ArcGIS Online':
                    thumbnail = 'http://static.arcgis.com/images/desktopapp.png'
                else:
                    thumbnail = self._portal.url + '/portalimages/desktopapp.png'

        snippet = self.snippet
        if snippet is None:
            snippet = ""

        portalurl = self._portal.url  + "/home/item.html?id=" + self.itemid

        locale.setlocale(locale.LC_ALL, '')
        numViews = locale.format("%d", self.numViews, grouping=True)
        return """<div class="item_container" style="height: auto; overflow: hidden; border: 1px solid #cfcfcf; border-radius: 2px; background: #f6fafa; line-height: 1.21429em; padding: 10px;">
                    <div class="item_left" style="width: 210px; float: left;">
                       <a href='""" + portalurl + """' target='_blank'>
                        <img src='""" + thumbnail + """' class="itemThumbnail">
                       </a>
                    </div>

                    <div class="item_right"     style="float: none; width: auto; overflow: hidden;">
                        <a href='""" + portalurl + """' target='_blank'><b>""" + self.title + """</b>
                        </a>
                        <br/>""" + snippet + """<img src='""" + self._get_icon() +"""' style="vertical-align:middle;">""" + self._ux_item_type() + """ by """ + self.owner + """
                        <br/>Last Modified: """ + datetime.fromtimestamp(self.modified/1000).strftime("%B %d, %Y") + """
                        <br/>""" + str(self.numComments) + """ comments, """ +  str(numViews) + """ views
                    </div>
                </div>
                """

    def __str__(self):
        return self.__repr__()
        # state = ["   %s=%r" % (attribute, value) for (attribute, value) in self.__dict__.items()]
        # return '\n'.join(state)

    def __repr__(self):
        return '<%s title:"%s" type:%s owner:%s>' % (type(self).__name__, self.title, self._ux_item_type(), self.owner)

    def reassign_to(self, target_owner, target_folder=None):
        """
        Allows the administrator to reassign a single item from one user to another.

        .. note::
            If you wish to move all of a user's items (and groups) to another user then use the
            user.reassign_to() method.  This method only moves one item at a time.

        ================  ========================================================
        **Argument**      **Description**
        ----------------  --------------------------------------------------------
        item_id           Required string. The unique identifier for the item.
        ----------------  --------------------------------------------------------
        target_owner      Required string. The new desired owner of the item.
        ----------------  --------------------------------------------------------
        target_folder     Optional string. The folder to move the item to.
        ================  ========================================================

        :return:
            A boolean indicating success (True) with the ID of the reassigned item, or failure (False).

        """
        try:
            current_folder = self.ownerFolder
        except:
            current_folder = None
        resp = self._portal.reassign_item(self.itemid, self.owner, target_owner, current_folder, target_folder)
        if resp is True:
            self._hydrate() # refresh
            return resp

    def share(self, everyone=False, org=False, groups=None, allow_members_to_edit=False):
        """
        Shares an item with the specified list of groups.

        ======================  ========================================================
        **Argument**            **Description**
        ----------------------  --------------------------------------------------------
        everyone                Optional boolean. Default is False, don't share with
                                everyone.
        ----------------------  --------------------------------------------------------
        org                     Optional boolean. Default is False, don't share with
                                the organization.
        ----------------------  --------------------------------------------------------
        groups                  Optional list of group names as strings, or a list of
                                arcgis.gis.Group objects, or a comma-separated list of
                                group IDs.
        ----------------------  --------------------------------------------------------
        allow_members_to_edit   Optional boolean. Default is False, to allow item to be
                                shared with groups that allow shared update
        ======================  ========================================================

        :return:
            A dictionary with key "notSharedWith" containing array of groups with which the item could not be shared.

        """
        try:
            folder = self.ownerFolder
        except:
            folder = None

        #get list of group IDs
        group_ids = ''
        if isinstance(groups, list):
            for group in groups:
                if isinstance(group, Group):
                    group_ids = group_ids + "," + group.id

                elif isinstance(group, str):
                    #search for group using title
                    search_result = self._gis.groups.search(query='title:' + group, max_groups=1)
                    if len(search_result) >0:
                        group_ids = group_ids + "," + search_result[0].id
                    else:
                        raise Exception("Cannot find: " + group)
                else:
                    raise Exception("Invalid group(s)")

        elif isinstance(groups, str):
            #old API - groups sent as comma separated group ids
            group_ids = groups

        if self.access == 'public' and not everyone and not org:
            return self._portal.share_item_as_group_admin(self.itemid, group_ids, allow_members_to_edit)
        else:
            return self._portal.share_item(self.itemid, self.owner, folder, everyone, org, group_ids, allow_members_to_edit)

    def unshare(self, groups):
        """
        Stops sharing of the item with the specified list of groups.


        ================  =========================================================================================
        **Argument**      **Description**
        ----------------  -----------------------------------------------------------------------------------------
        groups            Optional list of group names as strings, or a list of arcgis.gis.Group objects,
                          or a comma-separated list of group IDs.
        ================  =========================================================================================


        :return:
            Dictionary with key "notUnsharedFrom" containing array of groups from which the item could not be unshared.
        """
        try:
            folder = self.ownerFolder
        except:
            folder = None

        # get list of group IDs
        group_ids = ''
        if isinstance(groups, list):
            for group in groups:
                if isinstance(group, Group):
                    group_ids = group_ids + "," + group.id

                elif isinstance(group, str):
                    # search for group using title
                    search_result = self._gis.groups.search(query='title:' + group, max_groups=1)
                    if len(search_result) > 0:
                        group_ids = group_ids + "," + search_result[0].id
                    else:
                        raise Exception("Cannot find: " + group)
                else:
                    raise Exception("Invalid group(s)")

        elif isinstance(groups, str):
            # old API - groups sent as comma separated group ids
            group_ids = groups

        if self.access == 'public':
            return self._portal.unshare_item_as_group_admin(self.itemid, group_ids)
        else:
            return self._portal.unshare_item(self.itemid, self.owner, folder, group_ids)

    def delete(self):
        """ Deletes an item.

        :return:
            A boolean indicating success (True) or failure (False).

        """
        try:
            folder = self.ownerFolder
        except:
            folder = None
        return self._portal.delete_item(self.itemid, self.owner, folder)

    def update(self, item_properties=None, data=None, thumbnail=None, metadata=None):
        """ Updates an item in a Portal.


        .. note::
            Content can be a file (such as a layer package, geoprocessing package,
            map package) or a URL (to an ArcGIS Server service, WMS service,
            or an application).

            To upload a package or other file, provide a path or URL
            to the file in the data argument.

            For item_properties, pass in arguments for only the properties you want to be updated.
            All other properties will be untouched.  For example, if you want to update only the
            item's description, then only provide the description argument in item_properties.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        item_properties     Required dictionary. See table below for the keys and values.
        ---------------     --------------------------------------------------------------------
        data                Optional string. Either a path or URL to the data.
        ---------------     --------------------------------------------------------------------
        thumbnail           Optional string. Either a path or URL to a thumbnail image.
        ---------------     --------------------------------------------------------------------
        metadata            Optional string. Either a path or URL to the metadata.
        ===============     ====================================================================


        *Key:Value Dictionary Options for Argument item_properties*


        =================  =====================================================================
        **Key**            **Value**
        -----------------  ---------------------------------------------------------------------
        type               Optional string. Indicates type of item, see URL 1 below for valid values.
        -----------------  ---------------------------------------------------------------------
        typeKeywords       Optional string. Provide a lists all sub-types, see URL 1 below for valid values.
        -----------------  ---------------------------------------------------------------------
        description        Optional string. Description of the item.
        -----------------  ---------------------------------------------------------------------
        title              Optional string. Name label of the item.
        -----------------  ---------------------------------------------------------------------
        url                Optional string. URL to item that are based on URLs.
        -----------------  ---------------------------------------------------------------------
        tags               Optional string. Tags listed as comma-separated values, or a list of strings.
                           Used for searches on items.
        -----------------  ---------------------------------------------------------------------
        snippet            Optional string. Provide a short summary (limit to max 250 characters) of the what the item is.
        -----------------  ---------------------------------------------------------------------
        extent             Optional string. Provide comma-separated values for min x, min y, max x, max y.
        -----------------  ---------------------------------------------------------------------
        spatialReference   Optional string. Coordinate system that the item is in.
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
        """
        try:
            folder = self.ownerFolder
        except:
            folder = None

        if item_properties:
            large_thumbnail = item_properties.pop("largeThumbnail", None)
        else:
            large_thumbnail = None

        if item_properties is not None:
            if 'tags' in item_properties:
                if type(item_properties['tags']) is list:
                    item_properties['tags'] = ",".join(item_properties['tags'])

        ret = self._portal.update_item(self.itemid, item_properties, data,
                                       thumbnail, metadata, self.owner, folder,
                                       large_thumbnail)
        if ret:
            self._hydrate()
        return ret

    def get_data(self, try_json=True):
        """
        Retrieves the data component of an item and returns the data associated with an item.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        try_json            Optional string. Default is True. For JSON/text files, if try_json
                            is True, the method tries to convert the data to a Python dictionary
                            (use json.dumps(data) to convert the dictionary to a string),
                            otherwise the data is returned as a string.
        ===============     ====================================================================


        :return:
           Dependent on the content type of the data.
           For non-JSON/text data, binary files are returned and the path to the downloaded file.
           For JSON/text files, a Python dictionary or a string.  All others will be a byte array,
           that can be converted to string using data.decode('utf-8'). Zero byte files will return None.
        """
        item_data = self._portal.get_item_data(self.itemid, try_json)

        if item_data == '':
            return None
        elif type(item_data) == bytes:
            try:
                item_data_str = item_data.decode('utf-8')
                if item_data_str == '':
                    return None
                else:
                    return item_data
            except:
                return item_data
        else:
            return item_data

    def dependent_upon(self):
        """ Returns items, urls, etc that this item is dependent on.  """
        return self._portal.get_item_dependencies(self.itemid)

    def dependent_to(self):
        """ Returns items, urls, etc that are dependent to this item. """
        return self._portal.get_item_dependents_to(self.itemid)

    _RELATIONSHIP_TYPES = frozenset(['Map2Service', 'WMA2Code',
                                     'Map2FeatureCollection', 'MobileApp2Code', 'Service2Data',
                                     'Service2Service', 'Survey2Service', 'Map2Area', 'Area2Package'])

    _RELATIONSHIP_DIRECTIONS = frozenset(['forward', 'reverse'])

    def related_items(self, rel_type, direction="forward"):
        """
        Retrieves the items related to this item. Relationships can be added and deleted using
        item.add_relationship() and item.delete_relationship(), respectively.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        rel_type            Required string.  The type of the related item; is one of
                            ['Map2Service', 'WMA2Code', 'Map2FeatureCollection', 'MobileApp2Code',
                            'Service2Data', 'Service2Service']. See Relationship types in
                            REST API help for more information on this parameter.
        ---------------     --------------------------------------------------------------------
        direction           Required string. One of ['forward', 'reverse']
        ===============     ====================================================================


        :return:
           The list of related items.
        """

        if rel_type not in self._RELATIONSHIP_TYPES:
            raise Error('Unsupported relationship type: ' + rel_type)
        if not direction in self._RELATIONSHIP_DIRECTIONS:
            raise Error('Unsupported direction: ' + direction)

        related_items = []

        postdata = { 'f' : 'json' }
        postdata['relationshipType'] = rel_type
        postdata['direction'] = direction
        resp = self._portal.con.post('content/items/' + self.itemid + '/relatedItems', postdata)
        for related_item in resp['relatedItems']:
            related_items.append(Item(self._gis, related_item['id'], related_item))
        return related_items

    def add_relationship(self, rel_item, rel_type):
        """ Adds a relationship from this item to rel_item.

        .. note::
            Relationships are not tied to an item. They are directional links from an origin item
            to a destination item and have a type. The type defines the valid origin and destination
            item types as well as some rules. See Relationship types in REST API help for more information.
            Users don't have to own the items they relate unless so defined by the rules of the relationship
            type.

            Users can only delete relationships they create.

            Relationships are deleted automatically if one of the two items is deleted.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        rel_item            Required Item object corresponding to the related item.
        ---------------     --------------------------------------------------------------------
        rel_type            Required string.  The type of the related item; is one of
                            ['Map2Service', 'WMA2Code', 'Map2FeatureCollection', 'MobileApp2Code',
                            'Service2Data', 'Service2Service']. See Relationship types in
                            REST API help for more information on this parameter.
        ===============     ====================================================================


        :return:
           Returns True if the relationship was added, False if the add failed.
        """
        if not rel_type in self._RELATIONSHIP_TYPES:
            raise Error('Unsupported relationship type: ' + rel_type)

        postdata = { 'f' : 'json' }
        postdata['originItemId'] = self.itemid
        postdata['destinationItemId'] = rel_item.itemid
        postdata['relationshipType'] = rel_type
        path = 'content/users/' + self.owner

        path += '/addRelationship'

        resp = self._portal.con.post(path, postdata)
        if resp:
            return resp.get('success')

    def delete_relationship(self, rel_item, rel_type):
        """
        Deletes a relationship between this item and the rel_item.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        rel_item            Required Item object corresponding to the related item.
        ---------------     --------------------------------------------------------------------
        rel_type            Required string.  The type of the related item; is one of
                            ['Map2Service', 'WMA2Code', 'Map2FeatureCollection', 'MobileApp2Code',
                            'Service2Data', 'Service2Service']. See Relationship types in
                            REST API help for more information on this parameter.
        ===============     ====================================================================


        :return:
           Returns True if the relationship was deleted, False if the deletion failed.
        """
        if not rel_type in self._RELATIONSHIP_TYPES:
            raise Error('Unsupported relationship type: ' + rel_type)
        postdata = { 'f' : 'json' }
        postdata['originItemId'] =  self.itemid
        postdata['destinationItemId'] = rel_item.itemid
        postdata['relationshipType'] = rel_type
        path = 'content/users/' + self.owner


        path += '/deleteRelationship'
        resp = self._portal.con.post(path, postdata)
        if resp:
            return resp.get('success')

    def publish(self, publish_parameters=None, address_fields=None, output_type=None, overwrite=False,
                file_type=None, build_initial_cache=False):
        """
        Publishes a hosted service based on an existing source item (this item).
        Publishers can create feature, tiled map, vector tile and scene services.

        Feature services can be created using input files of type csv, shapefile, serviceDefinition, featureCollection, and fileGeodatabase.
        CSV files that contain location fields (i.e. address fields or XY fields) are spatially enabled during the process of publishing.
        Shapefiles and file geodatabases should be packaged as *.zip files.

        Tiled map services can be created from service definition (*.sd) files, tile packages, and existing feature services.

        Vector tile services can be created from vector tile package (*.vtpk) files.

        Scene services can be created from scene layer package (*.spk, *.slpk) files.

        Service definitions are authored in ArcGIS for Desktop and contain both the cartographic definition for a map
        as well as its packaged data together with the definition of the geo-service to be created.

        .. note::
            ArcGIS does not permit overwriting if you published multiple hosted feature layers from the same data item.


        ===================    ===============================================================
        **Argument**           **Description**
        -------------------    ---------------------------------------------------------------
        publish_parameters     Optional dictionary. containing publish instructions and customizations.
                               Cannot be combined with overwrite.  See http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#/Publish_Item/02r300000080000000/ for details.
        -------------------    ---------------------------------------------------------------
        address_fields         Optional dictionary. containing mapping of df columns to address fields,
                               eg: { "CountryCode" : "Country"} or { "Address" : "Address" }
        -------------------    ---------------------------------------------------------------
        output_type            Optional string.  Only used when a feature service is published as a tile service.
                               eg: output_type='Tiles'
        -------------------    ---------------------------------------------------------------
        overwrite              Optional boolean.   If True, the hosted feature service is overwritten.
                               Only available in ArcGIS Online and Portal for ArcGIS 10.5 or later.
        -------------------    ---------------------------------------------------------------
        file_type              Optional string.  Some formats are not automatically detected, when this occurs, the
                               file_type can be specified: serviceDefinition,shapefile,csv,
                               tilePackage, featureService, featureCollection, fileGeodatabase,
                               geojson, scenepackage, vectortilepackage, imageCollection,
                               mapService, and sqliteGeodatabase are valid entries. This is an
                               optional parameter.
        -------------------    ---------------------------------------------------------------
        build_initial_cache    Optional boolean.  The boolean value (default False), if true
                               and applicable for the file_type, the value will built cache
                               for the service.
        ===================    ===============================================================


        :return:
            An arcgis.gis.Item object corresponding to the published web layer.

        For publish_parameters, see http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#/Publish_Item/02r300000080000000/
        """

        import time
        params = {
            "f" : "json"
        }
        buildInitialCache = build_initial_cache
        if file_type is None:
            if self['type'] == 'Service Definition':
                fileType = 'serviceDefinition'
            elif self['type'] == 'Feature Collection':
                fileType = 'featureCollection'
            elif self['type'] == 'CSV':
                fileType = 'CSV'
            elif self['type'] == 'Shapefile':
                fileType = 'shapefile'
            elif self['type'] == 'File Geodatabase':
                fileType = 'fileGeodatabase'
            elif self['type'] == 'Vector Tile Package':
                fileType = 'vectortilepackage'
            elif self['type'] == 'Scene Package':
                fileType = 'scenePackage'
            elif self['type'] == 'Tile Package':
                fileType = 'tilePackage'
            elif self['type'] == 'SQLite Geodatabase':
                fileType = 'sqliteGeodatabase'
            elif self['type'] == 'GeoJson':
                fileType = 'geojson'
            elif self['type'] == 'Feature Service' and \
                 'Spatiotemporal' in self['typeKeywords']:
                fileType = 'featureService'
            else:
                raise ValueError("A file_type must be provide, data format not recognized")
        else:
            fileType = file_type
        try:
            folder = self.ownerFolder
        except:
            folder = None

        if publish_parameters is None:
            if fileType == 'shapefile' and not overwrite:
                publish_parameters =  {"hasStaticData":True, "name":os.path.splitext(self['name'])[0],
                                       "maxRecordCount":2000, "layerInfo":{"capabilities":"Query"} }

            elif fileType == 'CSV' and not overwrite:
                path = "content/features/analyze"

                postdata = {
                    "f": "pjson",
                    "itemid" : self.itemid,
                    "filetype" : "csv",

                    "analyzeParameters" : {
                        "enableGlobalGeocoding": "true",
                        "sourceLocale":"en-us",
                        #"locationType":"address",
                        "sourceCountry":"",
                        "sourceCountryHint":""
                    }
                }

                if address_fields is not None:
                    postdata['analyzeParameters']['locationType'] = 'address'

                res = self._portal.con.post(path, postdata)
                publish_parameters =  res['publishParameters']
                if address_fields is not None:
                    publish_parameters.update({"addressFields":address_fields})

                # use csv title for service name, after replacing non-alphanumeric characters with _
                service_name = re.sub(r'[\W_]+', '_', self['title'])
                publish_parameters.update({"name": service_name})

            elif fileType in ['CSV', 'shapefile', 'fileGeodatabase'] and overwrite: #need to construct full publishParameters
                #find items with relationship 'Service2Data' in reverse direction - all feature services published using this data item
                related_items = self.related_items('Service2Data', 'reverse')

                return_item_list = []
                if len (related_items) == 1: #simple 1:1 relationship between data and service items
                    r_item = related_items[0]
                    #construct a FLC manager
                    from arcgis.features import FeatureLayerCollection
                    flc = FeatureLayerCollection.fromitem(r_item)
                    flc_mgr = flc.manager

                    #get the publish parameters from FLC manager
                    publish_parameters = flc_mgr._gen_overwrite_publishParameters(r_item)

                elif len(related_items) == 0:
                    # the CSV item was never published. Hence overwrite should work like first time publishing - analyze csv
                    path = "content/features/analyze"
                    postdata = {
                        "f": "pjson",
                        "itemid" : self.itemid,
                        "filetype" : "csv",

                        "analyzeParameters" : {
                            "enableGlobalGeocoding": "true",
                            "sourceLocale":"en-us",
                            #"locationType":"address",
                            "sourceCountry":"",
                            "sourceCountryHint":""
                        }
                    }

                    if address_fields is not None:
                        postdata['analyzeParameters']['locationType'] = 'address'

                    res = self._portal.con.post(path, postdata)
                    publish_parameters =  res['publishParameters']
                    if address_fields is not None:
                        publish_parameters.update({"addressFields":address_fields})

                    # use csv title for service name, after replacing non-alphanumeric characters with _
                    service_name = re.sub(r'[\W_]+', '_', self['title'])
                    publish_parameters.update({"name": service_name})

                elif len(related_items) > 1:
                    # length greater than 1, then 1:many relationship
                    raise RuntimeError("User cant overwrite this service, using this data, as this data is already referring to another service.")

            elif fileType == 'vectortilepackage':
                name = re.sub(r'[\W_]+', '_', self['title'])
                publish_parameters = {'name': name, 'maxRecordCount':2000}
                output_type = 'VectorTiles'
                buildInitialCache = True

            elif fileType == 'scenePackage':
                name = re.sub(r'[\W_]+', '_', self['title'])
                publish_parameters = {'name': name, 'maxRecordCount':2000}
                output_type = 'sceneService'
            elif fileType == 'featureService':
                name = re.sub(r'[\W_]+', '_', self['title'])
                c = self._gis.content
                is_avail = c.is_service_name_available(name, 'featureService')
                i = 1
                while is_avail == False:
                    sname = name + "_%s" % i
                    is_avail = c.is_service_name_available(sname, 'featureService')
                    if is_avail:
                        name = sname
                        break
                    i += 1
                ms = self.layers[0].container.manager
                publish_parameters = ms._generate_mapservice_definition()
                output_type = "bdsMapService"
                buildInitialCache = True
                if 'serviceName' in publish_parameters:
                    publish_parameters['serviceName'] = name

            elif fileType == 'tilePackage':
                name = re.sub(r'[\W_]+', '_', self['title'])
                publish_parameters = {'name': name, 'maxRecordCount':2000}
                buildInitialCache = True
            elif fileType == 'sqliteGeodatabase':
                name = re.sub(r'[\W_]+', '_', self['title'])
                publish_parameters = {"name":name,
                                      'maxRecordCount':2000,
                                      "capabilities":"Query, Sync"}
            else: #sd files
                name = re.sub(r'[\W_]+', '_', self['title'])
                publish_parameters =  {"hasStaticData":True, "name": name, "maxRecordCount":2000, "layerInfo":{"capabilities":"Query"} }

        elif fileType == 'CSV': # merge users passed-in publish parameters with analyze results
            publish_parameters_orig = publish_parameters
            path = "content/features/analyze"

            postdata = {
                "f": "pjson",
                "itemid" : self.itemid,
                "filetype" : "csv",

                "analyzeParameters" : {
                    "enableGlobalGeocoding": "true",
                    "sourceLocale":"en-us",
                    #"locationType":"address",
                    "sourceCountry":"",
                    "sourceCountryHint":""
                }
            }

            if address_fields is not None:
                postdata['analyzeParameters']['locationType'] = 'address'

            res = self._portal.con.post(path, postdata)
            publish_parameters =  res['publishParameters']
            publish_parameters.update(publish_parameters_orig)
        #params['overwrite'] = json.dumps(overwrite)
        ret = self._portal.publish_item(self.itemid, None,
                                        None, fileType,
                                        publish_parameters, output_type,
                                        overwrite, self.owner,
                                        folder, buildInitialCache)

        #Check publishing job status

        if buildInitialCache and \
           self._gis._portal.is_arcgisonline and \
           fileType.lower() == 'tilepackage':
            from ..mapping._types import MapImageLayer
            if len(ret) > 0 and \
               'success' in ret[0] and \
               ret[0]['success'] == False:
                raise Exception(ret[0]['error'])
            ms_url = self._gis.content.get(ret[0]['serviceItemId']).url
            ms = MapImageLayer(url=ms_url, gis=self._gis)
            serviceitem_id = ret[0]['serviceItemId']
            try:
                ret = ms.manager.update_tiles()
            except: pass
        else:
            serviceitem_id = self._check_publish_status(ret, folder)
        return Item(self._gis, serviceitem_id)

    def move(self, folder, owner=None):
        """
        Moves this item to the folder with the given name.

        ================  ===============================================================
        **Argument**      **Description**
        ----------------  ---------------------------------------------------------------
        folder            Required string. The name of the folder to move the item to.
                          Use '/' for the root folder. For other folders, pass in the
                          folder name as a string, or a dictionary containing the folder ID,
                          such as the dictionary obtained from the folders property.
        ----------------  ---------------------------------------------------------------
        owner             Optional string or Owner object.  The name of the user to
                          move to.
        ================  ===============================================================

        :return:
            A json object like the following:
            {"success": true | false,
               "itemId": "<item id>",
               "owner": "<owner username>",
               "folder": "<folder id>"}

        """
        if isinstance(owner, User):
            owner_name = owner.username
        elif isinstance(owner, str):
            user = self._gis.users.get(owner)
            if user is None:
                owner_name = self._portal.logged_in_user()['username']
            else:
                owner_name = user.username
        else:
            owner_name = self._portal.logged_in_user()['username']

        folder_id = None
        if folder is not None:
            if isinstance(folder, str):
                if folder == '/':
                    folder_id = '/'
                else:
                    folder_id = self._portal.get_folder_id(owner_name, folder)
            elif isinstance(folder, dict):
                folder_id = folder['id']
            else:
                print("folder should be folder name as a string, or dict with id")

        if folder_id is not None:
            ret = self._portal.move_item(self.itemid, owner_name, self.ownerFolder, folder_id)
            self._hydrate()
            return ret
        else:
            print('Folder not found for given owner')
            return None

    #----------------------------------------------------------------------
    def create_tile_service(self,
                            title,
                             min_scale,
                             max_scale,
                             cache_info=None,
                             build_cache=False):
        """
        Allows publishers and administrators to publish hosted feature
        layers and hosted feature layer views as a tile service.

        ================  ===============================================================
        **Argument**      **Description**
        ----------------  ---------------------------------------------------------------
        title             Required string. The name of the new service.
                          Example: "SeasideHeightsNJTiles"
        ----------------  ---------------------------------------------------------------
        min_scale         Required float. The smallest scale at which to view data.
                          Example: 577790.0
        ----------------  ---------------------------------------------------------------
        max_scale         Required float. The largest scale at which to view data.
                          Example: 80000.0
        ----------------  ---------------------------------------------------------------
        cache_info        Optional dictionary. If not none, administrator provides the
                          tile cache info for the service. The default is the AGOL scheme.
        ----------------  ---------------------------------------------------------------
        build_cache       Optional boolean. Default is False; if True, the cache will be
                          built at publishing time.  This will increase the time it takes
                          to publish the service.
        ================  ===============================================================

        :return:
           The item if successfully added, None if unsuccessful.

        """

        if self.type.lower() == 'Feature Service'.lower():
            p = self.layers[0].container
            if cache_info is None:
                cache_info = {'spatialReference': {'latestWkid': 3857, 'wkid': 102100},
                              'rows': 256, 'preciseDpi': 96, 'cols': 256, 'dpi': 96,
                              'origin': {'y': 20037508.342787, 'x': -20037508.342787},
                              'lods': [{'level': 0, 'scale': 591657527.591555, 'resolution': 156543.033928},
                                       {'level': 1, 'scale': 295828763.795777, 'resolution': 78271.5169639999},
                                       {'level': 2, 'scale': 147914381.897889, 'resolution': 39135.7584820001},
                                       {'level': 3, 'scale': 73957190.948944, 'resolution': 19567.8792409999},
                                       {'level': 4, 'scale': 36978595.474472, 'resolution': 9783.93962049996},
                                       {'level': 5, 'scale': 18489297.737236, 'resolution': 4891.96981024998},
                                       {'level': 6, 'scale': 9244648.868618, 'resolution': 2445.98490512499},
                                       {'level': 7, 'scale': 4622324.434309, 'resolution': 1222.99245256249},
                                       {'level': 8, 'scale': 2311162.217155, 'resolution': 611.49622628138},
                                       {'level': 9, 'scale': 1155581.108577, 'resolution': 305.748113140558},
                                       {'level': 10, 'scale': 577790.554289, 'resolution': 152.874056570411},
                                       {'level': 11, 'scale': 288895.277144, 'resolution': 76.4370282850732},
                                       {'level': 12, 'scale': 144447.638572, 'resolution': 38.2185141425366},
                                       {'level': 13, 'scale': 72223.819286, 'resolution': 19.1092570712683},
                                       {'level': 14, 'scale': 36111.909643, 'resolution': 9.55462853563415},
                                       {'level': 15, 'scale': 18055.954822, 'resolution': 4.77731426794937},
                                       {'level': 16, 'scale': 9027.977411, 'resolution': 2.38865713397468},
                                       {'level': 17, 'scale': 4513.988705, 'resolution': 1.19432856685505},
                                       {'level': 18, 'scale': 2256.994353, 'resolution': 0.597164283559817},
                                       {'level': 19, 'scale': 1128.497176, 'resolution': 0.298582141647617},
                                       {'level': 20, 'scale': 564.248588, 'resolution': 0.14929107082380833},
                                       {'level': 21, 'scale': 282.124294, 'resolution': 0.07464553541190416},
                                       {'level': 22, 'scale': 141.062147, 'resolution': 0.03732276770595208}]
                              }
            pp = {"minScale":min_scale,"maxScale":max_scale,"name":title,
                  "tilingSchema":{"tileCacheInfo": cache_info,
                                  "tileImageInfo":{"format":"PNG32","compressionQuality":0,"antialiasing":True},
                  "cacheStorageInfo":{"storageFormat":"esriMapCacheStorageModeExploded",
                                      "packetSize":128}},"cacheOnDemand":True,
                  "cacheOnDemandMinScale":144448,
                  "capabilities":"Map,ChangeTracking"}
            params = {
                "f" : "json",
                "outputType" : "tiles",
                "buildInitialCache" : build_cache,
                "itemid" : self.itemid,
                "filetype" : "featureService",
                "publishParameters" : json.dumps(pp)
            }
            url = "%s/content/users/%s/publish" % (self._portal.resturl,
                                                   self._gis.users.me.username)
            res = self._gis._con.post(url, params)
            serviceitem_id = self._check_publish_status(res['services'], folder=None)
            if self._gis._portal.is_arcgisonline:
                from ..mapping._types import MapImageLayer
                ms_url = self._gis.content.get(serviceitem_id).url
                ms = MapImageLayer(url=ms_url, gis=self._gis)
                extent = ",".join([str(ms.properties['fullExtent']['xmin']),
                                   str(ms.properties['fullExtent']['ymin']),
                                   str(ms.properties['fullExtent']['xmax']),
                                   str(ms.properties['fullExtent']['ymax'])])
                lods = []
                for lod in cache_info['lods']:
                    if lod['scale'] <= min_scale and \
                       lod['scale'] >= max_scale:
                        lods.append(str(lod['level']))
                ms.manager.update_tiles(levels=",".join(lods), extent=extent)
            return self._gis.content.get(serviceitem_id)
        else:
            raise ValueError("Input must of type FeatureService")
        return

    def protect(self, enable=True):
        """
        Enables or disables delete protection on this item.

        ================  ===============================================================
        **Argument**      **Description**
        ----------------  ---------------------------------------------------------------
        enable            Optional boolean. Default is True which enables delete
                          protection, False to disable delete protection.
        ================  ===============================================================

        :return:
            A json object like the following:
            {"success": true | false}

        """

        try:
            folder = self.ownerFolder
        except:
            folder = None
        return self._portal.protect_item(self.itemid, self.owner, folder, enable)

    def _check_publish_status(self, ret, folder):
        """ Internal method to check the status of a publishing job.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        ret                 Required dictionary. Represents the result of a publish REST call.
                            This dict should contain the `serviceItemId` and `jobId` of the publishing job.
        ---------------     --------------------------------------------------------------------
        folder              Required string. Obtained from self.ownerFolder
        ===============     ====================================================================


        :return:
           The status.
        """

        import time
        try:
            serviceitem_id = ret[0]['serviceItemId']
        except KeyError as ke:
            raise RuntimeError(ret[0]['error']['message'])

        if 'jobId' in ret[0]:
            job_id = ret[0]['jobId']
            path = 'content/users/' + self.owner
            if folder is not None:
                path = path + '/' + folder + '/'

            path = path + '/items/' + serviceitem_id + '/status'
            params = {
                "f" : "json",
                "jobid" : job_id
            }
            job_response = self._portal.con.post(path, params)

            # Query and report the Analysis job status.
            #
            num_messages = 0
            #print(str(job_response))
            if "status" in job_response:
                while not job_response.get("status") == "completed":
                    time.sleep(5)

                    job_response = self._portal.con.post(path, params)

                    #print(str(job_response))
                    if job_response.get("status") in ("esriJobFailed","failed"):
                        raise Exception("Job failed.")
                    elif job_response.get("status") == "esriJobCancelled":
                        raise Exception("Job cancelled.")
                    elif job_response.get("status") == "esriJobTimedOut":
                        raise Exception("Job timed out.")

            else:
                raise Exception("No job results.")
        else:
            raise Exception("No job id")

        return serviceitem_id
    #----------------------------------------------------------------------
    @property
    def comments(self):
        """
        Gets a list of comments for a given item.
        """
        from .._impl.comments import Comment
        cs = []
        start = 1
        num = 100
        nextStart = 0
        url = "%s/content/items/%s/comments" % (self._portal.url, self.id)
        while nextStart != -1:
            params = {
                "f" : "json",
                "start" : start,
                "num" : num
            }
            res = self._portal.con.post(url, params)
            for c in res['comments']:
                cs.append(Comment(url="%s/%s" % (url, c['id']),
                                  item=self, initialize=False))
            start += num
            nextStart = res['nextStart']
        return cs
    #----------------------------------------------------------------------
    def add_comment(self, comment):
        """
        Adds a comment to an item. Available only to authenticated users
        who have access to the item.


        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        comment             Required string. Text to be added as a comment to a specific item.
        ===============     ====================================================================


        :return:
           Comment ID if successful, None on failure.
        """
        params = {
            "f" : "json",
            "comment" : comment
        }
        url = "%s/content/items/%s/addComment" % (self._portal.url, self.id)
        res = self._portal.con.post(url, params)
        if 'commentId' in res:
            return res['commentId']
        return None
    #----------------------------------------------------------------------
    @property
    def rating(self):
        """
        Gets or sets the rating given by the current user to the item.
        """
        url = "%s/content/items/%s/rating" % (self._portal.url, self.id)
        params = {"f" : "json"}
        res = self._portal.con.get(url, params)
        if 'rating' in res:
            return res['rating']
        return None
    #----------------------------------------------------------------------
    @rating.setter
    def rating(self, value):
        """
        Adds a rating to an item to which you have access. Only one rating
        can be given to an item per user. If this call is made on a
        currently rated item, the new rating will overwrite the existing
        rating. A user cannot rate their own item. Available only to
        authenticated users.

        ===============     ====================================================================
        **Argument**        **Description**
        ---------------     --------------------------------------------------------------------
        value               Required float. The rating to be applied for the item. The value
                            must be a floating point number between 1.0 and 5.0.
        ===============     ====================================================================


        """
        url = "%s/content/items/%s/addRating" % (self._portal.url,
                                                 self.id)
        params = {"f" : "json",
                  'rating' : float(value)}
        self._portal.con.post(url, params)
    #----------------------------------------------------------------------
    def delete_rating(self):
        """
        Removes the rating the calling user added for the specified item.
        """
        url = "%s/content/items/%s/deleteRating" % (self._portal.url,
                                                    self.id)
        params = {"f" : "json"}
        res = self._portal.con.post(url, params)
        if 'success' in res:
            return res['success']
        return res
    #----------------------------------------------------------------------
    @property
    def proxies(self):
        """
        Gets the ArcGIS Online hosted proxy services set on a registered app
        item with the Registered App type keyword. This resource is only
        available to the item owner and the organization administrator.
        """
        url = "%s/content/users/%s/items/%s/proxies" % (self._portal.url,
                                                        self.owner,
                                                        self.id)
        params = {"f" : "json"}
        ps = []
        try:
            res = self._portal.con.get(url, params)
            if 'appProxies' in res:
                for p in res['appProxies']:
                    ps.append(p)
        except:
            return []
        return ps


def rot13(s, b64=False, of=False):
    if s is None:
        return None
    result = ""

    # If b64 is True, then first convert back to a string
    if b64:
        try:
            s = base64.b64decode(s).decode()
        except:
            raise RuntimeError('Reading value from profile is not correctly formatted. ' + \
                               'Update by creating a new connection using the profile option.')

    # Loop over characters.
    for v in s:
        # Convert to number with ord.
        c = ord(v)

        # Shift number back or forward.
        if c >= ord('a') and c <= ord('z'):
            if c > ord('m'):
                c -= 13
            else:
                c += 13
        elif c >= ord('A') and c <= ord('Z'):
            if c > ord('M'):
                c -= 13
            else:
                c += 13

        # Append to result.
        result += chr(c)

    # Return transformation.
    if of:
        return result
    if not b64:
        # if not base64 to start, need to convert to base64 for saving to file
        return (base64.b64encode(result.encode())).decode()
    else:
        return result


class _GISResource(object):
    """ a GIS service
    """
    def __init__(self, url, gis=None):

        from .server._common import ServerConnection
        from .._impl.connection import _ArcGISConnection
        self._hydrated = False
        self.url = url
        self._url = url

        if gis is None:
            gis = GIS(set_active=False)
            self._gis = gis
            self._con = gis._con
        #elif isinstance(gis, (ServerConnection, _ArcGISConnection)):
            #self._gis = GIS(set_active=False)
            #self._con = gis
        else:
            self._gis = gis
            if isinstance(gis, (ServerConnection, _ArcGISConnection)):
                self._con = gis
            else:
                self._con = gis._con

    @classmethod
    def fromitem(cls, item):
        if not item.type.lower().endswith('service'):
            raise TypeError("item must be a type of service, not " + item.type)
        return cls(item.url, item._gis)

    def _refresh(self):
        params = {"f": "json"}

        if type(self).__name__ == 'VectorTileLayer': # VectorTileLayer is GET only
            dictdata = self._con.get(self.url, params, token=self._lazy_token)
        else:
            dictdata = self._con.post(self.url, params, token=self._lazy_token)

        self._lazy_properties = PropertyMap(dictdata)

    @property
    def properties(self):
        """The properties of this object"""
        if self._hydrated:
            return self._lazy_properties
        else:
            self._hydrate()
            return self._lazy_properties

    @properties.setter
    def properties(self, value):
        self._lazy_properties = value

    def _hydrate(self):
        """Fetches properties and deduces token while doing so"""
        self._lazy_token = None
        err = None

        with _DisableLogger():
            try:
                # try as a federated server
                if self._con._token is None:
                    self._lazy_token = None
                else:
                    if isinstance(self._con, arcgis._impl._ArcGISConnection):
                        self._lazy_token = self._con.generate_portal_server_token(self._url)
                    else:
                        self._lazy_token = self._con.token

                self._refresh()

            except HTTPError as httperror:  # service maybe down
                _log.error(httperror)
                err = httperror
            except RuntimeError as e:
                try:
                    # try as a public server
                    self._lazy_token = None
                    self._refresh()

                except HTTPError as httperror:
                    _log.error(httperror)
                    err = httperror
                except RuntimeError as e:
                    if 'Token Required' in e.args[0]:
                        # try token in the provided gis
                        self._lazy_token = self._con.token
                        self._refresh()

        if err is not None:
            raise RuntimeError('HTTPError: this service url encountered an HTTP Error: ' + self.url)

        self._hydrated = True

    @property
    def _token(self):
        if self._hydrated:
            return self._lazy_token
        else:
            self._hydrate()
            return self._lazy_token


    def __str__(self):
        return '<%s url:"%s">' % (type(self).__name__, self.url)

    def __repr__(self):
        return '<%s url:"%s">' % (type(self).__name__, self.url)

    def _invoke(self, method, **kwargs):
        """Invokes the specified method on this service passing in parameters from the kwargs name-value pairs"""
        url = self._url + "/" + method
        params = { "f" : "json"}
        if len(kwargs) > 0:
            for k,v in kwargs.items():
                params[k] = v
                del k,v
        return self._con.post(path=url, postdata=params, token=self._token)


class Layer(_GISResource):
    """
    The layer is a primary concept for working with data in a GIS.

    Users create, import, export, analyze, edit, and visualize layers.

    Layers can be added to and visualized using maps. They act as inputs to and outputs from analysis tools.

    Layers are created by publishing data to a GIS, and are exposed as a broader resource (Item) in the
    GIS. Layer objects can be obtained through the layers attribute on layer Items in the GIS.
    """

    def __init__(self, url, gis=None):
        super(Layer, self).__init__(url, gis)
        self.filter = None

    @classmethod
    def fromitem(cls, item, index=0):
        """
        Returns the layer at the specified index from a layer item.

        ==================     ====================================================================
        **Argument**           **Description**
        ------------------     --------------------------------------------------------------------
        item                   Required string. An item ID representing a layer.
        ------------------     --------------------------------------------------------------------
        index                  Optional int. The index of the layer amongst the item's layers
        ==================     ====================================================================

        :return:
           The layer at the specified index.
        """
        return item.layers[index]

    @property
    def _lyr_dict(self):
        url = self.url

        lyr_dict =  { 'type' : type(self).__name__, 'url' : url }
        if self._token is not None:
            lyr_dict['serviceToken'] = self._token

        if self.filter is not None:
            lyr_dict['filter'] = self.filter

        return lyr_dict

    @property
    def _lyr_json(self):
        url = self.url
        if self._token is not None:  # causing geoanalytics Invalid URL error
            url += '?token=' + self._token

        lyr_dict = {'type': type(self).__name__, 'url': url}

        return lyr_dict

    @property
    def _lyr_domains(self):
        """
        returns the domain information for any fields in the layer with domains
        """
        domains = []
        for field in [field for field in self.properties.fields if field['domain'] != None]:
            field_domain = dict(field.domain)
            field_domain['fieldName'] = field.name
            domains.append({field.name:field_domain})
        return domains
