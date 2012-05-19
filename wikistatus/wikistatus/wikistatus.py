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

sys.path.append("/home/andrew/mwclient/")
import mwclient

from keystoneclient.v2_0 import client as keystoneclient

from nova import db
from nova import exception
from nova import flags
from nova import image
from nova import log as logging
from nova.openstack.common import cfg
from nova import utils
from nova.plugin import plugin

LOG = logging.getLogger('nova.plugin.%s' % __name__)

wiki_opts = [
    cfg.StrOpt('wiki_host',
               default='deployment.wikimedia.beta.wmflabs.org',
               help='Mediawiki host to receive updates.'),
    cfg.StrOpt('wiki_page_prefix',
               default='InstanceStatus_',
               help='Created pages will have form <prefix>_<instancename>.'),
    cfg.StrOpt('wiki_login',
                default='andrewbogott',
                help='Account used to edit wiki pages.'),
    cfg.StrOpt('wiki_password',
               default='bananaphone',
               help='Password for wiki_login.'),
    cfg.BoolOpt('wiki_use_keystone',
                default=True,
                help='Indicates whether or not keystone is in use.'),
    cfg.StrOpt('wiki_keystone_auth_url',
                default='http://127.0.0.1:35357/v2.0',
                help='keystone auth url'),
    cfg.StrOpt('wiki_keystone_login',
                default='admin',
                help='keystone admin login'),
    cfg.StrOpt('wiki_keystone_password',
               default='devstack',
               help='keystone admin password'),
    cfg.MultiStrOpt('wiki_eventtype_whitelist',
               default=['compute.instance.delete.start',
                        'compute.instance.delete.end',
                        'compute.instance.create.start',
                        'compute.instance.create.end',
                        'compute.instance.rebuild.start',
                        'compute.instance.rebuild.end',
                        'compute.instance.resize.start',
                        'compute.instance.resize.end',
                        'compute.instance.suspend',
                        'compute.instance.resume',
                        'compute.instance.exists',
                       ],
               help='Event types to always handle.'),
    cfg.MultiStrOpt('wiki_eventtype_blacklist',
               default=[],
               help='Event types to always ignore.'
                'In the event of a conflict, this overrides the whitelist.'),
    ]


FLAGS = flags.FLAGS
FLAGS.register_opts(wiki_opts)


class WikiStatus(object):
    """Notifier class which posts instance info to a wiki page.

    Activate with something like this:

    --notification_driver = nova.notifier.list_notifier
    --list_notifier_drivers = nova.wikistatus.WikiStatus

    Or inject via the plugin, below.
    """

    RawTemplateFields = [
                         'created_at',
                         'disk_gb',
                         'display_name',
                         'instance_id',
                         'instance_type',
                         'launched_at',
                         'memory_mb',
                         'state',
                         'state_description',
                        ]

    def __init__(self):
        self.host = FLAGS.wiki_host
        self.site = None
        self.kclient = None
        self.nclient = None
        self._wiki_logged_in = False
        self._image_service = image.get_default_image_service()

    def _wiki_login(self):
        if not self._wiki_logged_in:
            if not self.site:
                self.site = mwclient.Site(self.host,
                                          retry_timeout=5,
                                          max_retries=2)
            if self.site:
                self.site.login(FLAGS.wiki_login, FLAGS.wiki_password)
                self._wiki_logged_in = True
            else:
                LOG.warning("Unable to reach %s.  We'll keep trying, "
                            "but pages will be out of sync in the meantime.")

    def _keystone_login(self, tenant_id):
        if not self.kclient:
            self.kclient = keystoneclient.Client(token='devstack',
                                       username=FLAGS.wiki_keystone_login,
                                       password=FLAGS.wiki_keystone_password,
                                       tenant_id=tenant_id,
                                       endpoint=FLAGS.wiki_keystone_auth_url)

            self.tenant_manager = self.kclient.tenants
            self.user_manager = self.kclient.users
            self.token = self.kclient.tokens.authenticate(
                       username=FLAGS.wiki_keystone_login,
                       password=FLAGS.wiki_keystone_password).id

        return self.kclient

    def notify(self, ctxt, message):
        event_type = message.get('event_type')
        if event_type in FLAGS.wiki_eventtype_blacklist:
            return
        if event_type not in FLAGS.wiki_eventtype_whitelist:
            LOG.debug("Ignoring message type %s" % event_type)
            return

        payload = message['payload']
        instance = payload['instance_id']
        instance_name = payload['display_name']

        pagename = "%s%s" % (FLAGS.wiki_page_prefix, instance_name)
        LOG.debug("wikistatus:  Writing instance info"
                  " to page http://%s/wiki/%s" %
                  (self.host, pagename))

        if event_type == 'compute.instance.delete.end':
            page_string = _("This instance has been deleted.")
        else:
            template_param_dict = {}
            for field in self.RawTemplateFields:
                template_param_dict[field] = payload[field]

            if (FLAGS.wiki_use_keystone and
                self._keystone_login(payload['tenant_id'])):
                tenant_obj = self.tenant_manager.get(payload['tenant_id'])
                user_obj = self.user_manager.get(payload['user_id'])
                tenant_name = tenant_obj.name
                user_name = user_obj.name
            else:
                project = db.project_get(None, payload['tenant_id'])
                tenant_name = project.name

                user = db.user_get(None, payload['user_id'])
                user_name = user.name

            template_param_dict['tenant'] = tenant_name
            template_param_dict['username'] = user_name

            inst = db.instance_get_by_uuid(ctxt, payload['instance_id'])

            simple_id = inst.id
            template_param_dict['cpu_count'] = inst.vcpus
            template_param_dict['disk_gb_current'] = inst.ephemeral_gb
            template_param_dict['host'] = inst.host
            template_param_dict['reservation_id'] = inst.reservation_id
            template_param_dict['availability_zone'] = inst.availability_zone
            template_param_dict['original_host'] = inst.launched_on
            template_param_dict['public_ip'] = inst.access_ip_v4

            try:
                fixed_ips = db.fixed_ip_get_by_instance(ctxt, simple_id)
            except exception.FixedIpNotFoundForInstance:
                fixed_ips = []
            ips = [ip.address for ip in fixed_ips]
            template_param_dict['private_ip'] = ','.join(ips)

            sec_groups = db.security_group_get_by_instance(ctxt, simple_id)
            grps = [grp.name for grp in sec_groups]
            template_param_dict['security_group'] = ','.join(grps)

            image = self._image_service.show(ctxt, inst.image_ref)
            image_name = image.get('name', inst.image_ref)
            template_param_dict['image_name'] = image_name

            fields_string = ""
            for key in template_param_dict:
                fields_string += "\n|%s=%s" % (key, template_param_dict[key])

            page_string = "{{InstanceStatus%s}}" % fields_string

        self._wiki_login()
        page = self.site.Pages[pagename]
        try:
            page.edit()
            page.save(page_string, "Auto update of instance info.")
        except (mwclient.errors.InsufficientPermission,
                mwclient.errors.LoginError):
            LOG.debug("Failed to update wiki page..."
                      " trying to re-login next time.")
            self._wiki_logged_in = False


class StatusPlugin(plugin.Plugin):

    def __init__(self):
        super(StatusPlugin, self).__init__()
        statusNotifier = WikiStatus()
        self.add_notifier(statusNotifier)

    def on_service_load(self, service_class):
        pass
