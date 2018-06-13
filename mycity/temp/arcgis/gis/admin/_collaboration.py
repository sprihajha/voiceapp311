"""
Classes to manage a GIS Collaboration
"""
from .. import GIS, Group
import functools

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

class CollaborationManager(object):
    _gis = None
    _basepath = None
    _pid = None
    def __init__(self, gis,portal_id=None):
        self._gis = gis
        self._portal = gis._portal
        self._pid = portal_id
        if portal_id is None:
            res = self._portal.con.get("portals/self")
            if 'id' in res:
                self._pid = res['id']
            else:
                raise Exception("Could not find the portal's ID")
        self._basepath = "portals/%s" % self._pid

    #----------------------------------------------------------------------
    def create(self,
               name,
               description,
               workspace_name,
               workspace_description,
               portal_group_id,
               host_contact_first_name,
               host_contact_last_name,
               host_contact_email_address,
               access_mode="sendAndReceive"):
        """
        The create method creates a collaboration. The host
        of the collaboration is the portal where it is created. The initial
        workspace for the collaboration is also created. A portal group in
        the host portal is linked to the workspace. The access mode for the
        host portal is set. The contact information associated with the
        host can be specified; otherwise, the contact information for the
        administrator user performing the operation will be used.

        :Inputs:
         :name: name of the collaboration
         :description: A description of the collaboration that all
          participants will see.
         :workspace_name: The name of the initial workspace.
         :workspace_description: The description of the initial workspace.
         :portal_group_id: ID of group in the portal that will be linked
          with the workspace.
         :host_contact_first_name: The first name of the contact person for
          the collaboration host portal.
         :host_contact_last_name: The last name of the contact person for
          the collaboration host portal.
         :host_contact_email_address: The email address of the contact
          person for the collaboration host portal.
         :access_mode:The organization's access mode to the workspace.
           Values: send | receive | sendAndReceive
        Output:
              the data item is registered successfully, None otherwise

        """
        if access_mode not in ['send', 'receive', 'sendAndReceive']:
            raise Exception("Invalid access_mode. Must be of value: send, " + \
                            "receive or sendAndReceive.")
        params = {
            "f" : "json",
            "name" : name,
            "description" : description,
            "workspaceName" : workspace_name,
            "workspaceDescription" : workspace_description,
            "portalGroupId" : portal_group_id,
            "hostContactFirstname" : host_contact_first_name,
            "hostContactLastname" : host_contact_last_name,
            "hostContactEmailAddress" : host_contact_email_address,
            "accessMode" : access_mode,
            "config" : {}
        }
        data_path = "%s/createCollaboration" % self._basepath
        res = self._portal.con.post(data_path, params)
        if 'collaboration' in res and \
           'id' in res['collaboration']:
            return Collaboration(collab_manager=self,
                                 collab_id=res['collaboration']['id'],
                                 portal_id=self._pid)
    #----------------------------------------------------------------------
    def accept_invitation(self,
                          first_name,
                          last_name,
                          email,
                          invitation_file=None,
                          invitation_JSON=None,
                          webauth_username=None,
                          webauth_password=None,
                          webauth_cert_file=None,
                          webauth_cert_password=None
                          ):
        """
        The accept_invitation operation allows a portal to accept a
        collaboration invitation. The invitation file received securely
        from the collaboration host portal must be provided. Once a guest
        accepts an invitation to a collaboration, it must link workspace(s)
        associated with the collaboration to local portal group(s). The
        guest must export a collaboration invitation response file and send
        it to the host. Once the host processes the response, content can
        be shared between the host and guest(s).

        Inputs:
         :first_name:The first name of the contact person for the guest
          portal.
         :last_name:last name of the contact person
         :email: email of the contact person
         :invitation_file: A multipart form parameter—file upload. Use
          either this parameter or invitation_JSON.
         :invitation_JSON: the same contents as the invitationFile
          parameter but passed as a string. Use either this parameter or
          invitationFile.
         :webauth_username: If the collaboration host requires web-tier
          authentication, optionally use this parameter to provide the
          host's web-tier authentication user name.
         :webauth_password: If the collaboration host requires web-tier
          authentication, optionally use this parameter to provide the
          host's web-tier authentication password.
         :webauth_cert_file:If the collaboration host requires web-tier
          authentication, optionally use this parameter to provide the
          host's web-tier authentication certificate file.
         :webauth_cert_password:If the collaboration host requires web-tier
          authentication, optionally use this parameter to provide the
          host's web-tier authentication certificate password.
        Output:
         dictionary
        """
        data_path = "%s/acceptCollaborationInvitation" % self._basepath
        params = {
            'f' : 'json',
            'guestContactFirstname' : first_name,
            'guestContactLastname' : last_name,
            'guestContactEmailAddress' : email
        }
        files =  None
        if invitation_file is None and \
           invitation_JSON is None:
            raise ValueError("invitation_file or invitation_JSON must be provided")
        if invitation_file:
            files = {}
            files['invitationFile'] = invitation_file
        if invitation_JSON:
            params['invitationJSON'] = invitation_JSON
        if webauth_cert_file:
            if files is None:
                files = {}
            files['hostWebauthCertificateFile'] = webauth_cert_file
        if webauth_cert_password:
            params['hostWebauthCertPassword'] = webauth_cert_password
        if webauth_password and webauth_username:
            params['hostWebauthUsername'] = webauth_username
            params['hostWebauthPassword'] = webauth_password
        con = self._portal.con
        return con.post(path=data_path,
                        postdata=params,
                        files=files)
    #----------------------------------------------------------------------
    def list(self):
        """gets all collaborations for a portal"""
        data_path = "%s/collaborations" % self._basepath
        params = {"f" : "json",
                  "num":100,
                  'start' : 1}
        res = self._portal.con.get(data_path, params)
        collabs = []
        while len(res['collaborations']) > 0:
            for collab in res['collaborations']:
                collabs.append(Collaboration(collab_manager=self,
                                             collab_id=collab['id']))
            res = self._portal.con.get(data_path, params)
            params['start'] = res['nextStart']
            if res['nextStart'] == -1:
                return collabs
        return collabs
    #----------------------------------------------------------------------
    def validate_invitation(self,
                            first_name,
                            last_name,
                            email,
                            invitation_file=None,
                            invitation_JSON=None,
                            webauth_username=None,
                            webauth_password=None,
                            webauth_cert_file=None,
                            webauth_cert_password=None):
        """
        The validate_invitation method allows a portal to
        validate a collaboration invitation. The invitation file received
        securely from the collaboration host portal must be provided.
        Validation checks include checking that the invitation is for the
        intended recipient.

        Inputs:
         :first_name:The first name of the contact person for the guest
          portal.
         :last_name:last name of the contact person
         :email: email of the contact person
         :invitation_file: A multipart form parameter—file upload. Use
          either this parameter or invitation_JSON.
         :invitation_JSON: the same contents as the invitationFile
          parameter but passed as a string. Use either this parameter or
          invitationFile.
         :webauth_username: If the collaboration host requires web-tier
          authentication, optionally use this parameter to provide the
          host's web-tier authentication user name.
         :webauth_password: If the collaboration host requires web-tier
          authentication, optionally use this parameter to provide the
          host's web-tier authentication password.
         :webauth_cert_file:If the collaboration host requires web-tier
          authentication, optionally use this parameter to provide the
          host's web-tier authentication certificate file.
         :webauth_cert_password:If the collaboration host requires web-tier
          authentication, optionally use this parameter to provide the
          host's web-tier authentication certificate password.
        Output:
         dictionary
        """
        data_path = "%s/validateCollaborationInvitation" % self._basepath
        params = {
            'f' : 'json',
            'guestContactFirstname' : first_name,
            'guestContactLastname' : last_name,
            'guestContactEmailAddress' : email
        }
        files =  None
        if invitation_file is None and \
           invitation_JSON is None:
            raise ValueError("invitation_file or invitation_JSON must be provided")
        if invitation_file:
            files = {}
            files['invitationFile'] = invitation_file
        if invitation_JSON:
            params['invitationJSON'] = invitation_JSON
        if webauth_cert_file:
            if files is None:
                files = {}
            files['hostWebauthCertificateFile'] = webauth_cert_file
        if webauth_cert_password:
            params['hostWebauthCertPassword'] = webauth_cert_password
        if webauth_password and webauth_username:
            params['hostWebauthUsername'] = webauth_username
            params['hostWebauthPassword'] = webauth_password
        con = self._portal.con
        return con.post(path=data_path,
                        postdata=params,
                        files=files)

    # ----------------------------------------------------------------------
    def collaborate_with(self, guest_gis, collaboration_name, collaboration_description):
        """
        A high level method to quickly establish a collaboration between two GIS. This method uses defaults
        wherever applicable and internally calls the `create`, `accept_invitation` and `invite_participant` methods.
        This method will create a new group and a new workspace in both the host and guest GIS for this collaboration.
        Invitation and response files created during the collaborations will be downloaded to the current working
        directory.
        
        Use the other methods if you need fine-grained control over how the collaboration is set up.
        :param guest_gis: GIS object of the guest org or Enterprise 
        :param collaboration_name: A generic name for the collaboration. This name is used with prefixes such as 
        wksp_<your_collab_name>, grp_<your_collab_name> to create the collaboration workspace and groups.
        :param collaboration_description: A generic description for the collaboration.
        :return: returns True / False
        """

        # create a group in the host
        host_group = self._gis.groups.create(title="grp_" + collaboration_name, tags='collaboration',
                                             description='Group for ' + collaboration_description)

        #create a collaboration in the host
        host_first_name = ""
        host_last_name = ""
        host_email = ""
        if hasattr(self._gis.users.me, 'firstName'):
            host_first_name = self._gis.users.me.firstName
            host_last_name = self._gis.users.me.lastName
        elif hasattr(self._gis.users.me, 'fullName'):
            sp = self._gis.users.me.fullName.split()
            host_first_name = sp[0]
            if len(sp) > 1:
                host_last_name = sp[1]
            else:
                host_last_name=host_first_name
        if hasattr(self._gis.users.me, 'email'):
            host_email = self._gis.users.me.email

        host_collab = self.create(name='collab_' + collaboration_name, description=collaboration_description,
                                  workspace_name='wksp_' + collaboration_name,
                                  workspace_description='Workspace for ' + collaboration_description,
                                  portal_group_id=host_group.id,
                                  host_contact_first_name=host_first_name,
                                  host_contact_last_name=host_last_name,
                                  host_contact_email_address=host_email)

        #Invite guest GIS as participant
        config = [{host_collab.workspaces[0]['id']:"sendAndReceive"}]
        invite_file = host_collab.invite_participant(config, guest_gis=guest_gis)

        #Create a group in guest GIS
        guest_group = guest_gis.groups.create(title='grp_' + collaboration_name, tags='collaboration',
                                              description='Group for ' + collaboration_description)

        #Accept invitation in guest GIS
        guest_first_name = ""
        guest_last_name = ""
        guest_email = ""
        if hasattr(guest_gis.users.me, 'firstName'):
            guest_first_name = guest_gis.users.me.firstName
            guest_last_name = guest_gis.users.me.lastName
        elif hasattr(guest_gis.users.me, 'fullName'):
            sp = self._gis.users.me.fullName.split()
            guest_first_name = sp[0]
            if len(sp) > 1:
                guest_last_name = sp[1]
            else:
                guest_last_name = guest_first_name
        if hasattr(guest_gis.users.me, 'email'):
            guest_email = guest_gis.users.me.email
        response = guest_gis.admin.collaborations.accept_invitation(first_name=guest_first_name,
                                                                    last_name=guest_last_name,
                                                                    email=guest_email,
                                                                    invitation_file=invite_file)

        #Export response from guest GIS
        guest_collab = None
        response_file = None
        if response['success']:
            guest_collab = Collaboration(guest_gis.admin.collaborations, host_collab.id)
            response_file = guest_collab.export_invitation('./')
        else:
            raise Exception("Unable to accept collaboration in the guest GIS")

        #Add guest group to guest collab
        group_add_result = guest_collab.add_group_to_workspace(guest_group, guest_collab.workspaces[0])

        #Accept response back in the host GIS
        host_collab.import_invitation_response(response_file)

        return True

###########################################################################
class Collaboration(dict):
    """
    The collaboration resource returns information about the collaboration
    with a specified ID.
    """
    _id = None
    _cm = None # CollaborationManager
    _baseurl = None
    _portal = None
    def __init__(self, collab_manager, collab_id, portal_id=None):
        dict.__init__(self)
        self._id = collab_id
        self._cm = collab_manager
        self._portal = collab_manager._gis._portal
        if portal_id is None:
            res = self._portal.con.get("portals/self")
            if 'id' in res:
                portal_id = res['id']
            else:
                raise Exception("Could not find the portal's ID")
        self._basepath = "portals/%s/collaborations/%s" % (portal_id,collab_id)
        params = {"f" : "json"}
        datadict = self._portal.con.post(self._basepath, params, verify_cert=False)

        if datadict:
            self.__dict__.update(datadict)
            super(Collaboration, self).update(datadict)
    #----------------------------------------------------------------------
    def __getattr__(self, name): # support group attributes as group.access, group.owner, group.phone etc
        try:
            return dict.__getitem__(self, name)
        except:
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))
    #----------------------------------------------------------------------
    def __getitem__(self, k): # support group attributes as dictionary keys on this object, eg. group['owner']
        try:
            return dict.__getitem__(self, k)
        except KeyError:
            params = { "f" : "json" }
            datadict = self._portal.con.post(self._basepath, params,
                                             verify_cert=False)
            super(Collaboration, self).update(datadict)
            self.__dict__.update(datadict)
            return dict.__getitem__(self, k)
    #----------------------------------------------------------------------
    def add_workspace(self, name, description, config, portal_group_id):
        """
        The add_workspace resource adds a new workspace to a
        portal-to-portal collaboration. Only collaboration hosts can create
        new workspaces.

        Inputs:
         :name: The name of the new workspace.
         :description: The description of the new workspace.
         :config: The configuration details of the new workspace.
         :portal_group_id: The ID of the portal group linked with the
          workspace.
        Output:
         dictionary with status and ID or workspace and collaboration
        """
        params = {
            "f": "json",
            "collaborationWorkspaceName" : name,
            "collaborationWorkspaceDescription" : description,
            "config" : config,
            "portalGroupId" : portal_group_id
        }
        path = "%s/%s" % (self._basepath, "addWorkspace")
        return self._portal.con.post(path, params, verify_cert=False)
    #----------------------------------------------------------------------
    def get_invitation(self, invitation_id):
        """
        The get_invitation operation returns the information about an
        invitation to participate in a portal-to-portal collaboration for a
        particular invitation with the specified ID.
        """
        params = {
            "f": "json"
        }
        path = "%s/%s/%s" % (self._basepath,
                             "invitations",
                             invitation_id)
        return self._portal.con.get(path, params)
    #----------------------------------------------------------------------
    def get_workspace(self, workspace_id):
        """
        The workspace resource provides information about the collaboration
        workspace with a specified ID.
        """
        params = {
            "f": "json"
        }
        path = "%s/%s/%s" % (self._basepath,
                             "workspaces",
                             workspace_id)
        return self._portal.con.get(path, params)
    #----------------------------------------------------------------------
    @property
    def invitations(self):
        """The invitations operation returns the invitation information for
        all the invitations generated by a portal-to-portal collaboration
        host.
        """
        params = {
            "f": "json",
            'start' : 1,
            'nun' : 100
        }
        invs = []
        path = "%s/%s" % (self._basepath, "invitations")
        res = self._portal.con.get(path, params)
        while len(res['collaborationInvitations']) > 0:
            invs += res['collaborationInvitations']
            params['start'] = res['nextStart']
            if res['nextStart'] == -1:
                return invs
            res = self._portal.con.get(path, params)
        return invs
    #----------------------------------------------------------------------
    def delete(self):
        """
        The delete operation deletes a portal-to-portal collaboration from
        the host portal. This stops any sharing set up from the
        collaboration. The collaboration will be removed on guest portals
        on the next refresh of their content based on the collaboration
        sharing schedule. Guests cannot delete collaborations, but they can
        discontinue participation in a collaboration via the
        removeParticipation endpoint.
        """
        params = {'f' : "json"}
        data_path = "%s/delete" % self._basepath
        resp = self._portal.con.post(data_path, params)
        if 'success' in resp:
            return resp['success']
        return resp
    #----------------------------------------------------------------------
    def remove_workspace(self, workspace_id):
        """
        The delete operation deletes a collaboration workspace. This
        immediately disables further replication of data to and from the
        portal and the collaboration participants.

        Inputs:
         : workspace_id: uid of the workspace to remove from the
          collaboration.

        """
        params = {"f" : "json"}
        data_path = "%s/workpaces/%s/delete" % (self._basepath, workspace_id)
        return self._portal.con.post(data_path, params)
    #----------------------------------------------------------------------
    @_lazy_property
    def workspaces(self):
        """
        The workspaces resource lists all the workspaces in a given
        collaboration. A workspace is a virtual space in the collaboration
        to which each participating portal is either sending or receiving
        content. Workspaces can only be created by the collaboration owner.
        """
        data_path = "%s/workspaces" % self._basepath
        params = {'f' : 'json',
                  "num":100,
                  'start' : 1}
        res = self._portal.con.get(data_path, params)
        workspaces = []
        while len(res['workspaces']) > 0:
            workspaces += res['workspaces']
            params['start'] = res['nextStart']
            if res['nextStart'] == -1:
                return workspaces
            res = self._portal.con.get(data_path, params)
        return workspaces
    #----------------------------------------------------------------------
    def export_invitation(self, out_folder):
        """
        The exportInvitationResponse operation exports a collaboration
        invitation response file from a collaboration guest portal. The
        exported response file must be sent via email or through other
        communication channels that are established in your organization to
        the inviting portal's administrator. The inviting portal's
        administrator will then import your response file to complete the
        establishment of trust between your portals.
        It is important that the contents of this response file are not
        intercepted and tampered with by any unknown entity.

        inputs:
         :out_folder: location to save the file to
        Output:
         file path
        """
        params = {"f" : "json"}
        data_path = "%s/exportInvitationResponse" % self._basepath
        return self._portal.con.post(data_path, params, out_folder=out_folder, verify_cert=False)
        # return self._portal.con.get(data_path, params, out_folder=out_folder)
    #----------------------------------------------------------------------
    def import_invitation_response(self,
                                   response_file,
                                   webauth_username=None,
                                   webauth_password=None,
                                   webauth_cert_file=None,
                                   webauth_cert_password=None):
        """
        The importInvitationResponse operation imports an invitation
        response file from a portal collaboration guest. The operation is
        performed on the portal that serves as the collaboration host. Once
        an invitation response is imported, trust between the host and the
        guest is established. Sharing of content between participants can
        proceed from this point.

        Inputs:
         :response_file: A multipart form parameter—file upload.
         :webauth_username: If the collaboration guest requires web-tier
          authentication, optionally use this parameter to provide the
          guest's web-tier authentication user name.
         :webauth_password: password for the webauth_username
         :webauth_cert_file: If the collaboration guest requires web-tier
          authentication, optionally use this parameter to provide the
          guest's web-tier authentication certificate file.
         :webauth_cert_password: If the collaboration guest requires
          web-tier authentication, optionally use this parameter to provide
          the guest's web-tier authentication certificate password.
        Output:
         JSON dictionary
        """
        params = {"f" : "json"}
        data_path = "%s/importInvitationResponse" % self._basepath
        files = {'invitationResponseFile' : response_file}
        if webauth_cert_file:
            files['guestWebauthCertificateFile'] = webauth_cert_file
        if webauth_cert_password:
            params['guestWebauthCertPassword'] = webauth_cert_password
        if webauth_username and webauth_password:
            params['guestWebauthUsername'] = webauth_username
            params['guestWebauthPassword'] = webauth_password
        con = self._portal.con
        return con.post(path=data_path,
                        postdata=params,
                        files=files,
                        verify_cert=False)
    #----------------------------------------------------------------------
    def invalidate(self, invitation_id):
        """
        The invalidate operation invalidates a previously generated
        portal-to-portal collaboration invitation. If a guest accepts this
        invitation and sends an invitation response for it, the response
        will not import successfully on the collaboration host.
        """
        params = {"f" : "json"}
        data_path = "%s/invitations/%s/invalidate" % (self._basepath, invitation_id)
        con = self._portal.con
        return con.post(data_path,
                       params, verify_cert=False)
    #----------------------------------------------------------------------
    def invite_participant(self,
                           config_json,
                           expiration=24,
                           guest_portal_url=None,
                           guest_gis=None,
                           save_path=None):
        """
        As a collaboration host, once you have set up a new collaboration,
        you are ready to invite other portals as participants in your
        collaboration. The inviteParticipant operation allows you to invite
        other portals to your collaboration by creating an invitation file.
        You need to send this invitation file to the administrator of the
        portal you are inviting to your collaboration. This can be done via
        email or through other communication channels that are established
        in your organization. It is important that the contents of this
        invitation file are not intercepted and tampered with by any
        unknown entity. The invitation file is in the format
        collaboration-<guestHostDomain>.invite.
        The administrator of the participant will accept the invitation by
        importing the invitation file into their portal. Their acceptance
        is returned to you as another file that you must import into your
        portal using the import_invitation_response operation. This will
        establish trust between your portal and that of your participant.

        Inputs:
         :config_json: A JSON object containing a map of access modes for
          the participant in each of the collaboration workspaces.
          Defined as: send | receive | sendAndReceive
          :Example:
          config_json = [
                {"workspace_id" : "send"},
                {"workspace_id2" : "receive"},
                {"workspace_id3" : "sendAndReceive"}
          ]
         :expiration: The time in UTC when the invitation to collaborate
          should expire.
         :guest_portal_url: The URL of the participating org or Enterprise that you want
          to invite to the collaboration.
         :guest_gis: GIS object to the guest collaboration site (optional)
         :save_path: Path to download the invitation file to.
        Output:
         contents of a file that contains the invitation information
        """
        if guest_gis is None and \
           guest_portal_url is None:
            raise ValueError("A GIS object or URL is required")
        if guest_portal_url is None and \
           guest_gis:
            guest_portal_url = guest_gis._portal.url
        data_path = "%s/inviteParticipant" % self._basepath
        params = {
            "f" : "json",
            "guestPortalUrl" : guest_portal_url,
            "collaborationWorkspacesParticipantConfigJSON" : config_json,
            "expiration" : expiration
        }
        con = self._portal.con
        return con.post(path=data_path,
                       postdata=params,
                       verify_cert=False,
                        out_folder = save_path)
    #----------------------------------------------------------------------
    def get_participant(self, portal_id):
        """
        The participant operation provides information about the
        collaboration participant with a specified ID.
        """
        data_path = "%s/participants/%s" % (self._basepath, portal_id)
        params = {"f" : "json"}
        con = self._portal.con
        return con.get(data_path,
                       params)
    #----------------------------------------------------------------------
    def participants(self):
        """
        The participants resource provides information about all of the
        participants in a portal-to-portal collaboration.
        """
        data_path = "%s/participants" % self._basepath
        params = {"f" : "json"}
        con = self._portal.con
        return con.get(data_path,
                       params)
    #----------------------------------------------------------------------
    def add_group_to_workspace(self, portal_group, workspace):
        """
        This operation adds a group to a workspace that participates in a portal-to-portal collaboration. Content shared
         to the portal group is shared to other participants in the collaboration.
        :param portal_group: arcgis.gis.Group object or group id string
        :return:
        """
        group_id = None
        if isinstance(portal_group, Group):
            group_id = portal_group.groupid
        elif isinstance(portal_group, str):
            group_id = portal_group

        data_path = "{}/workspaces/{}/updatePortalGroupLink".format(self._basepath, workspace['id'])
        params = {'f':'json',
                  'portalGroupId':group_id,
                  'enableRealtimeSync':True,
                  'copyFeatureServiceData': False}
        con = self._portal.con
        result = con.post(path=data_path, postdata=params, verify_cert=False)
        return result

    # ----------------------------------------------------------------------
    def _force_sync(self, workspace):
        """
        Undocumented. This operation will force sync the collaboration and its workspaces
        :param workspace:
        :return:
        """
        config_sync_data_path = "{}/configSync".format(self._basepath)
        config_sync_status = self._portal.con.get(config_sync_data_path, {"f":"json"})

        if config_sync_status['success']:
            #proceed to workspace sync
            workspace_sync_data_path = "{}/workspaces/{}/sync".format(self._basepath, workspace['id'])
            wksp_sync_status = self._portal.con.post(workspace_sync_data_path, postdata={'f':'json'}, verify_cert=False)
            return wksp_sync_status
        else:
            raise RuntimeError("Error force syncing")
    # ----------------------------------------------------------------------
    def refresh(self, invitation_id):
        """
        The refresh operation refreshes a previously generated
        portal-to-portal collaboration invitation. The new invitation file
        is provided via a multipart POST response. The expiration for the
        invitation is extended an additional 72 hours from the current
        time.

        Inputs:
         :invitation_id: ID of the invitation to refresh
        Output:
         dictionary
        """
        params = {"f" : "json"}
        data_path = "%s/invitations/%s/refresh" % (self._basepath, invitation_id)
        con = self._portal.con
        return con.post(path=data_path,
                        postdata=params,
                       verify_cert=False)
    #----------------------------------------------------------------------
    def remove_participation(self):
        """
        The removeParticipation operation removes collaboration
        participation by a guest from a collaboration, allowing a guest to
        exit a collaboration. This immediately disables further
        replication of data to and from the portal and the other
        collaboration participants.
        """
        data_path = "%s/removeParticipation" % self._basepath
        params = {"f" : "json"}
        con = self._portal.con
        return con.post(path=data_path,
                       postdata=params,
                       verify_cert=False)
    #----------------------------------------------------------------------
    def remove_participant(self, portal_id):
        """
        The remove operation allows a collaboration host to remove a
        participant from a portal-to-portal collaboration.
        """
        params = {'f' : 'json'}
        data_path = "%s/participants/%s/remove" % (self._basepath, portal_id)
        con = self._portal.con
        return con.post(path=data_path, postdata=params)
    #----------------------------------------------------------------------
    def remove_portal_group_link(self, workspace_id):
        """
        The remove_portal_group_link operation removes the link between a
        collaboration workspace and a portal group. Replication of content
        discontinues when the link is removed.

        Input:
         :workspace_id: workspace in.
        Output:
         dictionary
        """
        params = {'f' : 'json'}
        data_path = "%s/workspaces/%s/removePortalGroupLink" % (self._basepath, workspace_id)
        con = self._portal.con
        return con.post(path=data_path, postdata=params)
    #----------------------------------------------------------------------
    def update_collaboration(self, name=None,
                             description=None, config=None):
        """
        The updateInfo operation updates certain properties of a
        collaboration, primarily its name, description, and configuration
        properties. The updates are propagated to guests when the next
        scheduled refresh of content occurs.

        Inputs:
         :name: name of the collaboration
         :description: description of the collaboration
         :config: configuration properties of the collaboration
        Output:
         dictionary
        """
        data_path = "%s/updateInfo" % self._basepath
        params = {"f" : "json"}
        if name:
            params['name'] = name
        if description:
            params['description'] = description
        if config:
            params['config'] = config
        con = self._portal.con
        return con.post(path=data_path, postdata=params)
    #----------------------------------------------------------------------
    def update_workspace(self,
                         workspace_id, name=None,
                         description=None, config=None):
        """
        The updateInfo operation updates certain collaboration workspace
        properties.

        Inputs:
         :workspace_id: UID of the workspace
         :name: name of new workspace
         :description: description of new workspace
         :config: configuration details of the new workspace
        Output:
         dictionary
        """
        data_path = "%s/workspaces/%s/updateInfo" % (self._basepath, workspace_id)
        params = {"f" : 'json'}
        if name:
            params['collaborationWorkspaceName'] = name
        if description:
            params['collaborationWorkspaceDescription'] = description
        if config:
            params['config'] = config
        con = self._portal.con
        return con.post(path=data_path, postdata=params)
    #----------------------------------------------------------------------
    def update_access_modes(self,
                            portal_id,
                            workspace_access_json):
        """
        The update_access_modes operation updates the access mode for a
        specific participant in a portal-to-portal collaboration.

        Inputs:
         :portal_id: ID of the portal
         :workspace_access_json: JSON describing the participant's access
          mode.
        Output:
         dictionary
        """
        data_path = "/participants/%s/updateParticipantAccessModes" % portal_id
        params = {'f': 'json'}
        params['collaborationWorkspacesAccessJSON'] = workspace_access_json
        con = self._portal.con
        return con.post(path=data_path, postdata=params)
    #----------------------------------------------------------------------
    def update_portal_group_link(self, workspace_id,
                                 portal_id,
                                 enable_realtime_sync=True,
                                 interval_hours=1):
        """
        The updatePortalGroupLink operation updates the group linked with a
        workspace for a participant in a portal-to-portal collaboration.
        Content shared to the portal group is shared to other participants
        in the collaboration.

        Inputs:
         :workspace_id: workspace ID to update the group link
         :portal_id: the ID of the portal group link with the workspace
         :enable_realtime_sync: Determines whether the content shared with
          the group is shared to other collaboration participants in real
          time, updating whenever changes are made, or whether the content
          is shared based on a schedule set by the collaboration host.
          Values: true or false.
         :interval_hours: sets the sharing schedule for the group
        Output:
         dictionary with success status as boolean
        """
        data_path = "/workspaces/%s/updatePortalGroupLink" % workspace_id
        params = {
            'f': 'json',
            'portalGroupId' : portal_id,
            'enableRealtimeSync' : enable_realtime_sync,
            'syncIntervalHours' : interval_hours
        }

        con = self._portal.con
        return con.post(path=data_path, postdata=params)
    #----------------------------------------------------------------------
    def validate_invitation_response(self, response_file):
        """
        Prior to importing a collaboration invitation response, the
        invitation response file can be validated by using the
        validate_invitation_response operation to check for the existence
        of the collaboration and validity of the invitation response file.

        Inputs:
         :response_file: file upload
        Output:
         dictionary
        """
        files = {'invitationResponseFile' : response_file}
        params = {'f':'json'}
        data_path = "%s/validatInvitationResponse" % self._basepath
        con = self._portal.con
        return con.post(path=data_path, postdata=params)