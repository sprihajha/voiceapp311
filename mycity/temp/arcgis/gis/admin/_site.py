"""
Module contains a class to manage site level functions on a local GIS
"""
from ._base import BasePortalAdmin
########################################################################
class Site(BasePortalAdmin):
    """
    Site is the root resources used after a local GIS is installed. Here
    administrators can create, export, import, and join sites.
    """
    _url = None
    _con = None
    _pa = None
    _gis = None
    _properties = None
    _json = None
    _json_dict = None
    #----------------------------------------------------------------------
    def __init__(self, url, portaladmin, **kwargs):
        """Constructor"""
        super(Site, self).__init__(url=url, gis=portaladmin._gis)
        initialize = kwargs.pop('initialize', False)
        self._url = url
        self._pa = portaladmin
        self._gis = portaladmin._gis
        self._con = portaladmin._con
        if initialize:
            self._init()
    #----------------------------------------------------------------------
    @staticmethod
    def create(url,
               username,
               password,
               full_name,
               email,
               content_store,
               description="",
               question_idx=None,
               question_ans=None):
        """
        The create site operation initializes and configures Portal for
        ArcGIS for use. It must be the first operation invoked after
        installation. Creating a new site involves:
          - Creating the initial administrator account
          - Creating a new database administrator account (which is same as
            the initial administrator account)
          - Creating token shared keys
          - Registering directories
        This operation is time consuming, as the database is initialized
        and populated with default templates and content. If the database
        directory is not empty, this operation attempts to migrate the
        database to the current version while keeping its data intact. At
        the end of this operation, the web server that hosts the API is
        restarted.

        Parameters:
         :url: the portal administration url
               Ex: https://mysite.com/<web adaptor>/portaladmin
         :username: initial admin account name
         :password: password for initial admin account
         :full_name: full name of the admin account
         :email: account email address
         :content_store: JSON string including the path to the location of
          the site's content.
         :description: optional descript for the account
         :question_idx: index of the secret question to retrieve a
          forgotten password
         :question_ans: answer to the secret question
        """
        url = "%s/createNewSite" % url
        params = {"f": "json",
                  "username" : username,
                  "password" : password,
                  "fullName" : full_name,
                  "email" : email,
                  "description" : description,
                  "contentStore" : content_store}
        if question_idx and question_ans:
            params['securityQuestionIdx'] = question_idx
            params['securityQuestionAns'] = question_ans
        return self._con.post(path=url, postdata=params)
    #----------------------------------------------------------------------
    def export_site(self, location):
        """
        This operation exports the portal site configuration to a location
        you specify. The exported file includes the following information:
          Content directory - the content directory contains the data
           associated with every item in the portal
          Database dump file - a plain-text file that contains the SQL
           commands required to reconstruct the portal database
          Configuration store connection file - a JSON file that contains
           the database connection information

        Parameters:
         :location: path to the folder accessible to the portal where the
          exported site configuration will be written.
        """
        url = "%s/exportSite" % self._url
        params = {'f' : 'json',
                  'location' : location}
        return self._con.post(path=url,
                              postdata=params)
    #----------------------------------------------------------------------
    def import_site(self, location):
        """
        The importSite operation lets you restore your site from a backup
        site configuration file that you created using the exportSite
        operation. It imports the site configuration file into the
        currently running portal site.
        The importSite operation will replace all site configurations with
        information included in the backup site configuration file. See the
        export_site operation documentation for details on what the backup
        file includes. The importSite operation also updates the portal
        content index.

        Parameters:
         :location: A file path to an exported configuration.

        """
        url = "%s/importSite" % self._url
        if url.find(":7443") == -1:
            raise ValueError(
                "You must access portal not using the web adaptor (port 7443)"
            )
        params = {'f' : 'json',
                  'location' : location}
        res =  self._con.post(path=url,
                              postdata=params)
        if 'status' in res:
            return res['status'] == 'success'
        return False
    #----------------------------------------------------------------------
    def join(self, admin_url, username, password):
        """
        The joinSite operation connects a portal machine to an existing
        site. You must provide an account with administrative privileges to
        the site for the operation to be successful.
        When an attempt is made to join a site, the site validates the
        administrative credentials, then returns connection information
        about its configuration store back to the portal machine. The portal
        machine then uses the connection information to work with the
        configuration store.
        If this is the first portal machine in your site, use the Create
        Site operation instead.
        The joinSite operation:
         - Registers a machine to an existing site (active machine)
         - Creates a snapshot of the database of the active machine
         - Updates the token shared key
         - Updates Web Adaptor configurations
        Sets up replication to keep the database of both machines in sync
        The operation is time-consuming as the database is configured on
        the machine and all configurations are applied from the active
        machine. After the operation is complete, the web server that hosts
        the API will be restarted.

        Parameters:
         :admin_url: The admin URL of the existing portal site to which a
          machine will be joined
         :username: username for the initial administrator account of the
          existing portal site.
         :password:  password for the initial administrator account of the
          existing portal site.

        """
        url = "%s/joinSite" % self._url
        params = {'f' : 'json',
                  'machineAdminUrl' : admin_url,
                  'username' : username,
                  'password' : password}
        return self._con.post(path=url,
                              postdata=params)




