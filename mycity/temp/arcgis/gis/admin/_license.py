"""
Entry point to working with licensing on Portal or ArcGIS Online
"""
from ..._impl.connection import _ArcGISConnection
from ..._impl.common._mixins import PropertyMap
from ...gis import GIS
from ._base import BasePortalAdmin
########################################################################
class LicenseManager(BasePortalAdmin):
    """
    Provides tools to work and manage licenses in ArcGIS Online and
    ArcGIS Enterprise (Portal)

    ===============     ====================================================
    **Argument**        **Description**
    ---------------     ----------------------------------------------------
    url                 required string, the web address of the site to
                        manage licenses.
                        example:
                        https://<org url>/<wa>/sharing/rest/portals/self/purchases
    ---------------     ----------------------------------------------------
    gis                 required GIS, the gis connection object
    ===============     ====================================================

    :returns:
       LicenseManager Object
    """
    _con = None
    _url = None
    _json_dict = None
    _json = None
    _properties = None
    def __init__(self, url, gis=None, initialize=True, **kwargs):
        """class initializer"""
        super(LicenseManager, self).__init__(url=url, gis=gis)
        self._url = url
        if isinstance(gis, _ArcGISConnection):
            self._con = gis
        elif isinstance(gis, GIS):
            self._gis = gis
            self._con = gis._con
        else:
            raise ValueError(
                "connection must be of type GIS or _ArcGISConnection")
        if initialize:
            self._init(connection=self._con)
    #----------------------------------------------------------------------
    def get(self, name):
        """
        retrieves a license by it's name (title)
        ===============     ====================================================
        **Argument**        **Description**
        ---------------     ----------------------------------------------------
        name                required string, name of the entitlement to locate
                            on the organization.
                            example:
                            name="arcgis pro"
        ===============     ====================================================

        :returns:
           License Object
        """
        licenses = self.all()
        for l in licenses:
            if 'listing' in l.properties and \
               'title' in l.properties['listing'] and \
                l.properties['listing']['title'].lower() == name.lower():
                return l
            del l
        del licenses
        return None
    #----------------------------------------------------------------------
    def all(self):
        """
        Returns all Licenses registered with an organization

        :returns:
           list of Licnese objects
        """
        licenses = []
        if self._properties is None:
            self._init()
        if 'purchases' in self.properties:
            purchases = self.properties['purchases']
            for purchase in purchases:
                licenses.append(License(gis=self._gis, info=purchase))
        return licenses
########################################################################
class License(object):
    """
    Represents a single entitlement for a given organization.


    ===============     ====================================================
    **Argument**        **Description**
    ---------------     ----------------------------------------------------
    gis                 required GIS, the gis connection object
    ---------------     ----------------------------------------------------
    info                required dictionary, the information provided by
                        the organization's site containing the provision
                        and listing information.
    ===============     ====================================================

    :returns:
       License Object
    """
    _properties = None
    _gis = None
    _con = None
    #----------------------------------------------------------------------
    def __init__(self, gis, info):
        """Constructor"""
        self._gis = gis
        self._con = gis._con
        self._properties = PropertyMap(info)
    #----------------------------------------------------------------------
    def __str__(self):
        try:
            return '<%s %s at %s>' % (self.properties['listing']['title'],type(self).__name__, self._gis._portal.resturl)
        except:
            return '<%s at %s>' % (type(self).__name__, self._gis._portal.resturl)
    #----------------------------------------------------------------------
    def __repr__(self):
        try:
            return '<%s %s at %s>' % (self.properties['listing']['title'],type(self).__name__, self._gis._portal.resturl)
        except:
            return '<%s at %s>' % (type(self).__name__, self._gis._portal.resturl)
    #----------------------------------------------------------------------
    @property
    def properties(self):
        return self._properties
    #----------------------------------------------------------------------
    @property
    def report(self):
        """
        returns a Panda's Dataframe of the licensing count.
        """
        import pandas as pd
        data = []
        columns = ['Entitlement', 'Total', 'Assigned', 'Remaining']
        if 'provision' in self.properties:
            for k,v in self.properties['provision']['orgEntitlements']['entitlements'].items():
                counter = 0
                for u in self.all():
                    if k in u['entitlements']:
                        counter += 1
                row = [k, v['num'], counter, v['num'] - counter]
                data.append(row)
                del k, v
        return pd.DataFrame(data=data, columns=columns)
    #----------------------------------------------------------------------
    def plot(self):
        """returns a simple bar chart of assigned and remaining entitlements"""
        report = self.report
        return report.plot(x=report["Entitlement"],
                           y=['Assigned', 'Remaining'],
                           kind='bar',stacked=True)
    #----------------------------------------------------------------------
    def all(self):
        """
        returns a list of all usernames and their entitlements for this license
        """
        item_id = self.properties['listing']['itemId']
        url = "%scontent/listings/%s/userEntitlements" % (self._gis._portal.resturl, item_id)
        start = 1
        num = 100
        params = {
            'start' : start,
            'num' : num
        }
        user_entitlements = []
        res = self._con.get(url, params)
        user_entitlements += res['userEntitlements']
        if 'nextStart' in res:
            while res['nextStart'] > 0:
                start += num
                params = {
                    'start' : start,
                    'num' : num
                }
                res = self._con.get(url, params)
                user_entitlements += res['userEntitlements']
        return user_entitlements
    #----------------------------------------------------------------------
    def user_entitlement(self, username):
        """
        checks if a user has the entitlement assigned to them

        ===============     ====================================================
        **Argument**        **Description**
        ---------------     ----------------------------------------------------
        username            required string, the name of the user you want to
                            examine the entitlements for.
        ===============     ====================================================

        :returns:
           dictionary
        """
        item_id = self.properties['listing']['itemId']
        url = "%scontent/listings/%s/userEntitlements" % (
            self._gis._portal.resturl,
            item_id)
        start = 1
        num = 100
        params = {
            'start' : start,
            'num' : num
        }
        user_entitlements = []
        res = self._con.get(url, params)
        for u in res['userEntitlements']:
            if u['username'].lower() == username.lower():
                return u
        if 'nextStart' in res:
            while res['nextStart'] > 0:
                start += num
                params = {
                    'start' : start,
                    'num' : num
                }
                res = self._con.get(url, params)
                for u in res['userEntitlements']:
                    if u['username'].lower() == username.lower():
                        return u
        return {}
    #----------------------------------------------------------------------
    def assign(self, username, entitlements, suppress_email=True):
        """
        grants a user an entitlement.
        ===============     ====================================================
        **Argument**        **Description**
        ---------------     ----------------------------------------------------
        username            required string, the name of the user you wish to
                            assign an entitlement to.
        ---------------     ----------------------------------------------------
        entitlments         required list, a list of entitlements values
        ---------------     ----------------------------------------------------
        suppress_email       optional boolean, if True, the org will not notify
                            a user that their entitlements has changed (default)
                            If False, the org will send an email notifying a
                            user that their entitlements have changed.
        ===============     ====================================================

        :returns:
           boolean
        """
        item_id = self.properties['listing']['itemId']
        params = {
            "f" : "json",
            "userEntitlements" : {"users":[username],
                                  "entitlements":entitlements},

        }
        if suppress_email:
            params["suppressCustomerEmail"] = True
        url = "%scontent/listings/%s/provisionUserEntitlements" % (self._gis._portal.resturl, item_id)
        res = self._con.post(url, params)
        if 'success' in res:
            return res['success'] == True
        return res
    #----------------------------------------------------------------------
    def revoke(self, username, entitlements, supress_email=True):
        """
        removes a specific license from a given entitlement

        ===============     ====================================================
        **Argument**        **Description**
        ---------------     ----------------------------------------------------
        username            required string, the name of the user you wish to
                            assign an entitlement to.
        ---------------     ----------------------------------------------------
        entitlments         required list, a list of entitlements values,
                            if * is given, all entitlements will be revoked
        ---------------     ----------------------------------------------------
        supress_email       optional boolean, if True, the org will not notify
                            a user that their entitlements has changed (default)
                            If False, the org will send an email notifying a
                            user that their entitlements have changed.
        ===============     ====================================================

        :returns:
           boolean
        """
        if entitlements == "*":
            return self.assign(username=username,
                                  entitlements=[],
                                  supress_email=supress_email)
        elif isinstance(entitlements, list):
            es = self.user_entitlement(username=username)

            if 'entitlements' in es:
                lookup = {e.lower() : e for e in es['entitlements']}
                es = [e.lower() for e in es['entitlements']]
                if isinstance(entitlements, str):
                    entitlements = [entitlements]
                entitlements = list(set(es) - set([e.lower() for e in entitlements]))
                es2 = []
                for e in entitlements:
                    es2.append(lookup[e])
                return self.assign(username=username,
                                   entitlements=es2,
                                   supress_email=supress_email)
        return False
