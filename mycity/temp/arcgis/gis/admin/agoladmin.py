"""
Entry point to working with local enterprise GIS functions
"""
from ..._impl.connection import _ArcGISConnection
from ...gis import GIS
from ._resources import PortalResourceManager
from ._base import BasePortalAdmin
########################################################################
class AGOLAdminManager(object):
    """
    This is the root resource for administering your online GIS. Starting from
    this root, all of the GIS's environment is organized into a
    hierarchy of resources and operations.

    Parameter:
    :param gis: GIS object containing Administrative credentials
    :param ux: the UX object (optional)
    :param metadata: the metadata manager object (optional)
    :param collaborations: the CollaborationManager object (optional)
    """
    _gis = None
    _ux = None
    _idp = None
    _pp = None
    _credits = None
    _metadata = None
    _collaborations = None
    _ur = None
    _sp = None
    _license = None
    _usage = None
    _category_schema = None
    #----------------------------------------------------------------------
    def __init__(self,
                 gis,
                 ux=None,
                 metadata=None,
                 collaborations=None):
        """initializer"""
        self._gis = gis
        self._ux = ux
        self._collaborations = collaborations
        self._metadata = metadata
        self.resources = PortalResourceManager(gis=self._gis)
    #----------------------------------------------------------------------
    def __str__(self):
        return '<%s at %s>' % (type(self).__name__, self._gis._portal.resturl)
    #----------------------------------------------------------------------
    def __repr__(self):
        return '<%s at %s>' % (type(self).__name__, self._gis._portal.resturl)
    #----------------------------------------------------------------------
    @property
    def ux(self):
        """returns a UX/UI manager"""
        if self._ux is None:
            from ._ux import UX
            self._ux = UX(gis=self._gis)
        return self._ux
    #----------------------------------------------------------------------
    @property
    def collaborations(self):
        """
        The collaborations resource lists all collaborations in which a
        portal participates
        """
        if self._collaborations is None:
            from ._collaboration import CollaborationManager
            self._collaborations = CollaborationManager(gis=self._gis)
        return self._collaborations
    #----------------------------------------------------------------------
    @property
    def category_schema(self):
        """
        This resource allows for the setting and manipulating of catagory
        schemas.
        """
        if self._category_schema is None:
            from ._catagoryschema import CategoryManager
            self._category_schema = CategoryManager(gis=self._gis)
        return self._category_schema
    #----------------------------------------------------------------------
    @property
    def idp(self):
        """
        This resource allows for the setting and configuration of the identity provider
        """
        if self._idp is None:
            from ._idp import IdentityProviderManager
            self._idp = IdentityProviderManager(gis=self._gis)
        return self._idp
    #----------------------------------------------------------------------
    @property
    def social_providers(self):
        """
        This resource allows for the setting and configuration of the social providers
        for a GIS.
        """
        if self._sp is None:
            from ._socialproviders import SocialProviders
            self._sp = SocialProviders(gis=self._gis)
        return self._sp
    #----------------------------------------------------------------------
    @property
    def credits(self):
        """
        manages the credits on a ArcGIS Online
        """
        if self._credits is None:
            from ._creditmanagement import CreditManager
            self._credits = CreditManager(gis=self._gis)
        return self._credits
    #----------------------------------------------------------------------
    @property
    def metadata(self):
        """
        resources to work with metadata on GIS
        """
        if self._metadata is None:
            from ._metadata import MetadataManager
            self._metadata = MetadataManager(gis=self._gis)
        return self._metadata
    #----------------------------------------------------------------------
    @property
    def password_policy(self):
        """tools to manage a Site's password policy"""
        if self._pp is None:
            from ._security import PasswordPolicy
            url = "%s/portals/self/securityPolicy" % (self._gis._portal.resturl)
            self._pp = PasswordPolicy(url=url,
                                      gis=self._gis)
        return self._pp
    #----------------------------------------------------------------------
    @property
    def usage_reports(self):
        """
        provides access to the usage reports of the AGOL organization
        """
        if self._ur is None:
            from ._usage import AGOLUsageReports
            url = "%sportals/%s/usage" % (self._gis._portal.resturl,
                                          self._gis.properties.id)
            self._ur = AGOLUsageReports(url=url, gis=self._gis)
        return self._ur
    #----------------------------------------------------------------------
    @property
    def license(self):
        """
        provides a set of tools to access and manage user licenses and
        entitlements.
        """
        if self._license is None:
            from ._license import LicenseManager
            url = self._gis._portal.resturl + "portals/self/purchases"
            self._license = LicenseManager(url=url, gis=self._gis)
        return self._license
    #----------------------------------------------------------------------
    @property
    def urls(self):
        """
        returns the URLs to the Hosting and Tile Server for ArcGIS Online
        """
        res = self._gis._con.get(path="%s/portals/%s/urls" % (self._gis._portal.resturl,
                                                              self._gis.properties.id),
                                      params={'f': 'json'})
        return res

