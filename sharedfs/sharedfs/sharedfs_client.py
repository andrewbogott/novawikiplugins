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

from cliff import lister
from cliff import show

import logging
import urllib

from novaclient import base
from openstackclient.common import command


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


class FS_Create(command.OpenStackCommand):
    "Create a shared file system."

    api = 'compute'
    log = logging.getLogger("nova.plugin.%s" % __name__)

    def get_parser(self, prog_name):
        parser = super(Show_Server, self).get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<name>',
            help='Name of new filesystem')
        parser.add_argument(
            'size',
            metavar='<size>',
            help='Size of filesystem in Gb')
        parser.add_argument(
            'scope',
            metavar='<scope>',
            help='FS scope (instance, project, global)')
        return parser

    def run(self, parsed_args):
        self.log.info('FS_Create.run(%s)' % parsed_args)
        r = shared_filesystem.create(args.name, args.size, args.scope)
        self.log.info(r)


class List_Filesystems(command.OpenStackCommand, lister.Lister):
    "Show filesystem command."

    api = 'compute'
    log = logging.getLogger("nova.plugin.%s" % __name__)

    def get_parser(self, prog_name):
        parser = super(List_Filesystems, self).get_parser(prog_name)
        parser.add_argument(
           '--long',
            action='store_true',
            default=False,
            help='Additional fields are listed in output')
        return parser

    def get_data(self, parsed_args):
        self.log.debug('v2.Show_Filesystem.run(%s)' % parsed_args)
        if parsed_args.long:
            columns = ('ID', 'Name', 'Size', 'Scope')
        else:
            columns = ('ID', 'Name')

        nova_client = self.app.client_manager.compute
        fsmanager = SharedFileSystemManager(nova_client)
        data = fsmanager.fs_list()

        return (columns,
                (utils.get_item_properties(
                    s, columns,
                    formatters={},
                    ) for s in data),
                )


class Create_Filesystem(command.OpenStackCommand):
    """Create filesystem command"""

    api = 'compute'
    log = logging.getLogger("nova.plugin.%s" % __name__)

    def get_parser(self, prog_name):
        parser = super(Create_Filesystem, self).get_parser(prog_name)
        parser.add_argument(
            'filesystem_name',
            metavar='<filesystem-name>',
            help='New filesystem name')
        parser.add_argument(
            'filesystem_size',
            metavar='<filesystem-size>',
            help='New filesystem size in Gb')
        parser.add_argument(
            'filesystem_scope',
            metavar='<filesystem-scope>',
            help='New filesystem scope (project, global, or instance)')
        return parser


    def run(self, parsed_args):
        self.log.debug('v2.Create_Filesystem.get_data(%s)' % parsed_args)
        nova_client = self.app.client_manager.compute
        fsmanager = SharedFileSystemManager(nova_client)
        fs = fsmanager.create(parsed_args.filesystem_name,
                           parsed_args.filesystem_size,
                           parsed_args.filesystem_scope)

        return {'name': fs.name,
                'size': fs.size,
                'project': fs.project,
                'scope': fs.scope}
