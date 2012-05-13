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

from nova import logging
from nova.plugin import plugin
import sharedfs_notifier
import sharedfs_api

LOG = logging.getLogger('nova.plugin.%s' % __name__)

class SharedFSPlugin(plugin.Plugin):

    def __init__(self):
        LOG.debug("Sharedfs activate init!")
        super(SharedFSPlugin, self).__init__([sharedfs_api.Shared_fs],
                                        [sharedfs_notifier.SharedFSNotifier])
