# Copyright 2012 Andrew Bogott for the Wikimedia Foundation
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

import time

from nova import exception
from nova import flags
from nova import log as logging
from nova.openstack.common import cfg
from nova import utils

FLAGS = flags.FLAGS
LOG = logging.getLogger("nova.plugin.%s" % __name__)


class SharedFSDriver(object):
    """Defines the Shared Filesystem driver interface.

    Does nothing.
    """

    def do_setup(self):
        LOG.debug(_("Setting up the empty shared_fs driver.  "
                    "If you plan to use the shared_fs functionality, "
                    "redefine --sharedfs_driver."))

    def check_for_setup_error(self):
        pass

    def create_fs(self, fs_name, tenant, size_in_g):
        pass

    def delete_fs(self, fs_name, tenant):
        pass

    def list_fs(self):
        return []

    def attach(self, fs_name, ip_list):
        pass

    def unattach(self, fs_name, ip_list):
        pass

    def list_attachments(self, fs_name):
        return []
