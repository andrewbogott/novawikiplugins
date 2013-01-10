# Copyright 2012 Andrew Bogott for the Wikimedia Foundation
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
import sys

from nova.openstack.common import log as logging
from nova.openstack.common.plugin import plugin
from sharedfs import notifier
from sharedfs import api

LOG = logging.getLogger('nova.plugin.%s' % __name__)

class SharedFSPlugin(plugin.Plugin):

    def __init__(self, service_name):
        super(SharedFSPlugin, self).__init__(service_name)
        self._add_notifier(notifier.SharedFSNotifier)
        self._add_api_extension_descriptor(api.Shared_fs)
