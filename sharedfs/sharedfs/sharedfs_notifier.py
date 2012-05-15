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

from nova import context
from nova import db
from nova import flags
from nova import log as logging
from nova.openstack.common import cfg
from nova.openstack.common import importutils
import sharedfs_db

LOG = logging.getLogger("nova.plugin.%s" % __name__)

FLAGS = flags.FLAGS

NOTIFICATIONS = []


class SharedFSNotifier(object):
    """Notifier class for shared filesystem integration.

    This notifier detects instance creation and deletion,
    and automatically attaches or detaches instances
    from file shares as appropriate.

    To activate this feature, add to the notifier list
    like this:

    --notification_driver = nova.notifier.list_notifier
    --list_notifier_drivers = \
       nova.sharedfs.sharedfs_notifier.SharedFSNotifier
    """

    def __init__(self):
        self.fs_driver = importutils.import_object(FLAGS.sharedfs_driver)

    def notify(self, message):
        event_type = message.get('event_type')
        if event_type not in ['compute.instance.delete.start',
                              'compute.instance.create.end']:
            return

        payload = message['payload']

        instance = payload['instance_id']
        tenant = payload['tenant_id']
        user = payload['user_id']
        ctxt = context.RequestContext(user, tenant)

        # Find all global scope filesystems
        #  and all project-scope systems that are
        #  associated with this project.
        fs_list = []
        db_fs_list = sharedfs_db.filesystem_list(ctxt)
        for fs_name in db_fs_list:
            fs = sharedfs_db.filesystem_get(ctxt, fs_name)
            if not fs:
                LOG.debug(_("Database inconsistency:  no record for FS %s") %
                          fs_name)
                continue
            if fs.scope == 'global':
                fs_list.append(fs_name)
            elif fs.scope == 'project' and fs.project_id == tenant:
                fs_list.append(fs_name)

        for fs_name in fs_list:
            if event_type == 'compute.instance.delete.start':
                self.unattach(ctxt, instance, fs_name)
            elif event_type == 'compute.instance.create.end':
                self.attach(ctxt, instance, fs_name)

    def attach(self, ctxt, instance_uuid, fs_name):
        LOG.debug(_("attaching instance %(instance)s to filesystem %(fs)s.") %
                  {'instance': instance_uuid, 'fs': fs_name})

        instance = db.instance_get_by_uuid(ctxt, instance_uuid)
        instance_id = instance.id

        fixed_ips = db.fixed_ip_get_by_instance(ctxt, instance_id)
        for ip in fixed_ips:
            LOG.debug(_("auto-attaching ip %(ip)s to filesystem %(fs)s.") %
                      {'ip': ip['address'], 'fs': fs_name})
            self.fs_driver.attach(fs_name, ip['address'])

    def unattach(self, ctxt, instance_uuid, fs_name):
        LOG.debug(_("unattaching %(instance)s from filesystem %(fs)s.") %
                  {'instance': instance_uuid, 'fs': fs_name})

        instance = db.instance_get_by_uuid(ctxt, instance_uuid)
        instance_id = instance.id

        fixed_ips = db.fixed_ip_get_by_instance(ctxt, instance_id)
        for ip in fixed_ips:
            LOG.debug(_("auto unattaching %(ip)s from filesystem %(fs)s.") %
                      {'ip': ip['address'], 'fs': fs_name})
            self.fs_driver.unattach(fs_name, ip['address'])
