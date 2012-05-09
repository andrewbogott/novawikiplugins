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
#    under the License

import urllib

import webob

from nova.api.openstack import extensions
from nova.api.openstack import wsgi
from nova.api.openstack import xmlutil
from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import utils

FLAGS = flags.FLAGS

LOG = logging.getLogger(__name__)
authorize = extensions.extension_authorizer('volume', 'shared_fs')


def make_client_entry(elem):
    elem.set('id')


def make_fs_entry(elem):
    elem.set('name')
    elem.set('size')
    elem.set('scope')
    elem.set('project')


class SharedFSTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('fs_entry',
                                       selector='fs_entry')
        make_fs_entry(root)
        return xmlutil.MasterTemplate(root, 1)


class SharedFSsTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('fs_entries')
        elem = xmlutil.SubTemplateElement(root, 'fs_entry',
                                          selector='fs_entries')
        make_fs_entry(elem)
        return xmlutil.MasterTemplate(root, 1)


class InstanceTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('instance_entry',
                                       selector='instance_entry')
        make_fs_entry(root)
        return xmlutil.MasterTemplate(root, 1)


class InstancesTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('instance_entries')
        elem = xmlutil.SubTemplateElement(root, 'instance_entry',
                                          selector='instance_entries')
        make_fs_entry(elem)
        return xmlutil.MasterTemplate(root, 1)


def _translate_instance_view(instance_id):
    result = {'id': instance_id}
    return {'instance_entry': result}


def _translate_instances_view(instance_id_list):
    return {'instance_entries':
                [_translate_instance_view(entry)['instance_entry']
                            for entry in instance_id_list]}


def _translate_fs_entry_view(fs_entry):
    result = {'name': fs_entry.get('name'),
              'size': fs_entry.get('size'),
              'scope': fs_entry.get('scope'),
              'project': fs_entry.get('project')}
    return {'fs_entry': result}


def _translate_fs_entries_view(domain_entries):
    return {'fs_entries':
            [_translate_fs_entry_view(entry)['fs_entry']
                             for entry in domain_entries]}


def _has_db_support():
    # If we're using this extension on a pre-folsom
    # version of Nova then we might not have db support.
    # If that's true we need to disable certain features.
    return hasattr(db, 'filesystem_list')


class SharedFSController(object):
    """Shared FileSystem controller for OpenStack API."""

    def __init__(self):
        self.fs_driver = utils.import_object(FLAGS.sharedfs_driver)
        self.fs_driver.do_setup()
        self.fs_driver.check_for_setup_error()
        self.has_db_support = _has_db_support()
        if not self.has_db_support:
            LOG.warn(_("The Shared Filesystem database extensions are not "
                     "present.  Automatic management of instance attachment "
                     "will not be supported."))

    @wsgi.serializers(xml=SharedFSsTemplate)
    def index(self, req):
        """Return a list of existing file shares."""
        filesystems = self.fs_driver.list_fs()

        # Only return filesystems in the db.
        context = req.environ['nova.context']

        if self.has_db_support:
            db_list = db.filesystem_list(context)

            fs_list = []
            for fs in filesystems:
                name = fs.get('name')
                if name in db_list:
                    db_entry = db.filesystem_get(context, name)
                    fs_list.append({'name': fs.get('name'),
                                    'size': fs.get('size'),
                                    'scope': db_entry.get('scope'),
                                    'project': db_entry.get('project_id')})
                    db_list.remove(name)
                else:
                    LOG.warn(_("Found filesystem %s that is not recored "
                             "in the database.  Ignoring.") % name)

            if db_list:
                LOG.warn(_("Possible database integrity issue.  The following "
                         "filesystems are recorded in the database but cannot "
                         "be located: %s") % db_list)
        else:
            fs_list = [{'name': fs.get('name'), 'size': fs.get('size'),
                        'scope': 'unknown', 'project': 'unknown'}
                       for fs in filesystems]

        return _translate_fs_entries_view(fs_list)

    @wsgi.serializers(xml=SharedFSTemplate)
    def update(self, req, id, body):
        """Add new filesystem."""
        name = id
        try:
            entry = body['fs_entry']
            size = entry['size']
            scope = entry['scope']
        except (TypeError, KeyError):
            raise webob.exc.HTTPUnprocessableEntity()
        if scope not in ['project', 'instance', 'global']:
            LOG.error(_("scope must be one of project, instance, or global"))
            raise webob.exc.HTTPUnprocessableEntity()

        context = req.environ['nova.context']
        project = context.project_id

        try:
            if self.has_db_support:
                db.filesystem_add(context, name, scope, project)

            self.fs_driver.create_fs(name, project, size)
        except exception.NotAuthorized:
            msg = _("Filesystem creation requires admin permissions.")
            raise webob.exc.HTTPForbidden(msg)

        if self.has_db_support:
            # Attach global or project-wide shares immediately.
            instance_list = []
            if scope == 'global':
                instance_list = db.instance_get_all(context)
            elif scope == 'project':
                instance_list = db.instance_get_all_by_project(context,
                                                               project)

            for instance in instance_list:
                try:
                    fixed_ips = db.fixed_ip_get_by_instance(context,
                                                            instance.id)
                    for ip in fixed_ips:
                        LOG.debug(_("attaching %(ip)s to filesystem %(fs)s.")
                                  % {'ip': ip['address'], 'fs': name})
                        try:
                            self.fs_driver.attach(name, ip['address'])
                        except exception.NotAuthorized:
                            LOG.warning(_("Insufficient permissions to attach"
                                       " %(instance)s to filesystem %(fs)s.") %
                                       {'instance': instance.name, 'fs': name})
                except exception.FixedIpNotFound:
                    LOG.warning(_("Unable to get IP address for %s.")
                              % instance.id)

        return _translate_fs_entry_view({'name': name,
                                         'size': size,
                                         'scope': scope,
                                         'project': project})

    def delete(self, req, id):
        """Delete the filesystem identified by id."""
        name = id

        if self.has_db_support:
            # Unattach global or project-wide shares immediately.
            context = req.environ['nova.context']
            fs_entry = db.filesystem_get(context, name)
            if not fs_entry:
                msg = _("Filesystem %s not found.") % name
                raise webob.exc.HTTPNotFound(msg)
            scope = fs_entry.scope
            project = fs_entry.project_id
            instance_list = []
            if scope == 'global':
                instance_list = db.instance_get_all(context)
            elif scope == 'project':
                instance_list = db.instance_get_all_by_project(context,
                                                               project)

            for instance in instance_list:
                try:
                    fixed_ips = db.fixed_ip_get_by_instance(context,
                                                            instance.id)
                    for ip in fixed_ips:
                        LOG.debug(_("unattaching %(ip)s from fs %(fs)s.") %
                                  {'ip': ip['address'], 'fs': name})
                        try:
                            self.fs_driver.unattach(name, ip['address'])
                        except exception.NotAuthorized:
                            LOG.warning(_("Insufficient permission to unattach"
                                     " %(instance)s from filesystem %(fs)s.") %
                                          {'instance': instance.name,
                                           'fs': name})
                except exception.FixedIpNotFound:
                    LOG.warning(_("Unable to get IP address for %s.")
                              % instance.id)

            db.filesystem_delete(context, name)

        try:
            self.fs_driver.delete_fs(name, project)
        except exception.NotAuthorized:
            msg = _("Filesystem deletion requires admin permissions.")
            raise webob.exc.HTTPForbidden(msg)
        except exception.NotFound:
            msg = _("Filesystem %s does not exist.") % name
            raise webob.exc.HTTPNotFound(msg)

        return webob.Response(status_int=202)


class SharedFSAttachmentController(object):
    """Shared FileSystem instance attachment controller for OpenStack API."""
    def __init__(self):
        self.fs_driver = utils.import_object(FLAGS.sharedfs_driver)
        self.has_db_support = _has_db_support()
        if not self.has_db_support:
            LOG.warn(_("The Shared Filesystem database extensions are not "
                     "present.  Automatic management of instance attachment "
                     "will not be supported."))

    @wsgi.serializers(xml=InstancesTemplate)
    def index(self, req, filesystem_id):
        """Return a list of attachments to the specified file share."""
        fs_name = filesystem_id

        context = req.environ['nova.context']
        try:
            ips = self.fs_driver.list_attachments(fs_name)
        except KeyError:
            msg = _("Filesystem %s does not exist.") % fs_name
            raise webob.exc.HTTPNotFound(msg)

        if 'localhost' in ips:
            ips.remove('localhost')

        instances = []
        for ip in ips:
            try:
                fixed_ip = db.fixed_ip_get_by_address(context, ip)
                instance_id = fixed_ip.instance_id
                instance = db.instance_get(context, instance_id)
                instances.append(instance.uuid)
            except exception.InstanceNotFound:
                LOG.warning(_("Attached to a most-likely defunct "
                            "instance with IP address %s") % ip)

        return _translate_instances_view(instances)

    @wsgi.serializers(xml=InstanceTemplate)
    def update(self, req, filesystem_id, id, body):
        """Attach an instance to a filesystem."""
        fs_name = filesystem_id
        instance_uuid = id

        if body:
            LOG.warning(_("Unexpected body: %s") % body)
            raise webob.exc.HTTPUnprocessableEntity()

        context = req.environ['nova.context']

        instance = db.instance_get_by_uuid(context, instance_uuid)
        if not instance:
            msg = (_("Unable to find instance %s.") % instance_uuid)
            raise webob.exc.HTTPNotFound(msg)

        instance_id = instance.id

        try:
            fixed_ips = db.fixed_ip_get_by_instance(context, instance_id)
        except exception.FixedIpNotFound:
            msg = (_("Unable to get IP address for instance_id %s.") %
                     instance_id)
            raise webob.exc.HTTPNotFound(msg)

        for ip in fixed_ips:
            LOG.debug(_("attaching ip %(ip)s to filesystem %(fs)s.") %
                      {'ip': ip['address'], 'fs': fs_name})
            try:
                self.fs_driver.attach(fs_name, ip['address'])
            except exception.NotAuthorized:
                msg = _("Filesystem attachment not permitted.")
                raise webob.exc.HTTPForbidden(msg)

        return _translate_instance_view(instance_uuid)

    def delete(self, req, filesystem_id, id):
        """Detach an instance from a filesystem."""
        fs_name = filesystem_id
        instance_uuid = id

        context = req.environ['nova.context']

        instance = db.instance_get_by_uuid(context, instance_uuid)
        if not instance:
            msg = (_("Unable to find instance %s.") % instance_uuid)
            raise webob.exc.HTTPNotFound(msg)

        instance_id = instance.id

        try:
            ips = db.fixed_ip_get_by_instance(context, instance_id)
        except exception.FixedIpNotFound:
            msg = (_("Unable to get IP address for instance_id %s.") %
                     instance_id)
            raise webob.exc.HTTPNotFound(msg)

        for ip in ips:
            LOG.debug(_("unattaching ip %(ip)s from filesystem %(fs)s.") %
                      {'ip': ip, 'fs': fs_name})
            try:
                self.fs_driver.unattach(fs_name, ip['address'])
            except exception.NotAuthorized:
                msg = _("Filesystem detachment not permitted.")
                raise webob.exc.HTTPForbidden(msg)

        return webob.Response(status_int=202)


class Shared_fs(extensions.ExtensionDescriptor):
    """Shared Filesystem support."""

    name = "Shared_fs"
    alias = "os-shared-filesystem"
    namespace = "http://docs.openstack.org/ext/shared_filesystem/api/v1.1"
    updated = "2012-03-01T00:00:00+00:00"

    def get_resources(self):
        resources = []

        res = extensions.ResourceExtension('os-shared-filesystem',
                         SharedFSController())
        resources.append(res)

        res = extensions.ResourceExtension('attachments',
                         SharedFSAttachmentController(),
                         parent={'member_name': 'filesystem',
                                 'collection_name': 'os-shared-filesystem'})
        resources.append(res)

        return resources
