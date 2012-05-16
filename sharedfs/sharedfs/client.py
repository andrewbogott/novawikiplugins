# Copyright 2012 Andrew Bogott for The Wikimedia Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging
import urllib

from novaclient import base


class SharedFilesystem(base.Resource):
    HUMAN_ID = True

    def delete(self):
        self.manager.delete(self.name)

    def create(self):
        return self.manager.create_public(self.name, self.size, self.scope)

    def get(self):
        entries = self.manager.fs_list()
        for entry in entries:
            if entry.get('name') == self.name:
                return entry

        return None


class SharedFileSystemManager(base.ManagerWithFind):
    resource_class = SharedFilesystem

    def fs_list(self):
        """Return the list of existing filesystems."""
        return self._list("/os-shared-filesystem", "fs_entries")

    def create(self, name, size, scope):
        """Create a shareable filesystem."""
        body = {'fs_entry':
                 {'size': size,
                  'scope': scope}}

        fs = self._update('/os-shared-filesystem/%s' % name,
                           body)
        return self.resource_class(self, fs['fs_entry'])

    def delete(self, name):
        """Delete an existing filesystem."""
        self._delete("/os-shared-filesystem/%s" % name)


class SharedFSAttachment(base.Resource):
    HUMAN_ID = True

    def attach(self, fs_name):
        self.manager.attach(fs_name, self.id)

    def unattach(self, fs_name):
        self.manager.create_public(fs_name, self.id)


class SharedFSAttachmentManager(base.ManagerWithFind):
    resource_class = SharedFSAttachment

    def attachments(self, fs_name):
        """List the instance IDs attached to a given Filesystem."""
        return self._list("/os-shared-filesystem/%s/attachments" % fs_name,
                          "instance_entries")

    def attach(self, fs_name, instance_id):
        """Attach a filesystem to an instance."""
        entry = self._update("/os-shared-filesystem/%s/attachments/%s" %
                             (fs_name, instance_id), None)
        return self.resource_class(self, entry['instance_entry'])

    def unattach(self, fs_name, instance_id):
        """Detach a filesystem from an instance."""
        self._delete("/os-shared-filesystem/%s/attachments/%s" %
                     (fs_name, instance_id))
