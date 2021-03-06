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

from cliff import command
from cliff import lister
from cliff import show

from openstackclient.common import command
from openstackclient.common import utils

from sharedfs import client


class List_Filesystem(command.OpenStackCommand, lister.Lister):
    "Show filesystem command."

    api = 'compute'
    log = logging.getLogger("nova.plugin.%s" % __name__)

    def get_parser(self, prog_name):
        parser = super(List_Filesystem, self).get_parser(prog_name)
        parser.add_argument(
           '--long',
            action='store_true',
            default=False,
            help='Additional fields are listed in output')
        return parser

    def get_data(self, parsed_args):
        self.log.debug('v2.List_Filesystem.run(%s)' % parsed_args)
        if parsed_args.long:
            columns = ('Name', 'Size', 'Scope', 'Project')
        else:
            columns = (['Name'])

        nova_client = self.app.client_manager.compute
        fsmanager = client.SharedFileSystemManager(nova_client)
        data = fsmanager.fs_list()

        return (columns,
                (utils.get_item_properties(
                    s, columns,
                    formatters={},
                    ) for s in data),
                )


class Create_Filesystem(command.OpenStackCommand, show.ShowOne):
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

    def get_data(self, parsed_args):
        self.log.debug('v2.Create_Filesystem.get_data(%s)' % parsed_args)
        nova_client = self.app.client_manager.compute
        fsmanager = client.SharedFileSystemManager(nova_client)
        fs = fsmanager.create(parsed_args.filesystem_name,
                           parsed_args.filesystem_size,
                           parsed_args.filesystem_scope)

        columns = ('Name', 'Size', 'Scope', 'Project')
        return (columns,
                utils.get_item_properties(
                    fs, columns,
                    formatters={})
                )


class Delete_Filesystem(command.OpenStackCommand, command.Command):
    "Command to delete a shared FileSystem"

    api = 'compute'
    log = logging.getLogger("nova.plugin.%s" % __name__)

    def get_parser(self, prog_name):
        parser = super(Delete_Filesystem, self).get_parser(prog_name)
        parser.add_argument(
            'filesystem_name',
            metavar='<filesystem-name>',
            help='Filesystem name')
        return parser

    def run(self, parsed_args):
        self.log.debug('v2.Delete_Filesystem.run(%s)' % parsed_args)

        nova_client = self.app.client_manager.compute
        fsmanager = client.SharedFileSystemManager(nova_client)
        fs = fsmanager.delete(parsed_args.filesystem_name)


class Attachments_Filesystem(command.OpenStackCommand, lister.Lister):
    "Command to list attachments to a given FS"

    api = 'compute'
    log = logging.getLogger("nova.plugin.%s" % __name__)

    def get_parser(self, prog_name):
        parser = super(Attachments_Filesystem, self).get_parser(prog_name)
        parser.add_argument(
            'filesystem_name',
            metavar='<filesystem-name>',
            help='Filesystem name')
        return parser

    def get_data(self, parsed_args):
        self.log.debug('v2.List_Attachment.run(%s)' % parsed_args)
        columns = (['id'])

        nova_client = self.app.client_manager.compute
        fsmanager = client.SharedFSAttachmentManager(nova_client)
        data = fsmanager.attachments(parsed_args.filesystem_name)

        return (columns,
                (utils.get_item_properties(
                    s, columns,
                    formatters={},
                    ) for s in data),
                )


class Attach_Filesystem(command.OpenStackCommand, show.ShowOne):
    "Command to list attachments to a given FS"

    api = 'compute'
    log = logging.getLogger("nova.plugin.%s" % __name__)

    def get_parser(self, prog_name):
        parser = super(Attach_Filesystem, self).get_parser(prog_name)
        parser.add_argument(
            'filesystem_name',
            metavar='<filesystem-name>',
            help='Filesystem name')
        parser.add_argument(
            'instance_id',
            metavar='<instance-id>',
            help='Instance ID')
        return parser

    def get_data(self, parsed_args):
        self.log.debug('v2.Attach_Filesystem.run(%s)' % parsed_args)

        nova_client = self.app.client_manager.compute
        fsmanager = client.SharedFSAttachmentManager(nova_client)
        data = fsmanager.attach(parsed_args.filesystem_name,
                                parsed_args.instance_id)

        columns = (['id'])
        return (columns,
                utils.get_item_properties(
                    data, columns,
                    formatters={})
                )


class Detach_Filesystem(command.OpenStackCommand, command.Command):
    "Command to list attachments to a given FS"

    api = 'compute'
    log = logging.getLogger("nova.plugin.%s" % __name__)

    def get_parser(self, prog_name):
        parser = super(Detach_Filesystem, self).get_parser(prog_name)
        parser.add_argument(
            'filesystem_name',
            metavar='<filesystem-name>',
            help='Filesystem name')
        parser.add_argument(
            'instance_id',
            metavar='<instance-id>',
            help='Instance ID')
        return parser

    def run(self, parsed_args):
        self.log.debug('v2.Detach_Filesystem.run(%s)' % parsed_args)

        nova_client = self.app.client_manager.compute
        fsmanager = client.SharedFSAttachmentManager(nova_client)
        fsmanager.unattach(parsed_args.filesystem_name,
                           parsed_args.instance_id)
