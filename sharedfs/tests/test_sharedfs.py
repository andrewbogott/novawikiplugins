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

import UserDict

import webob

from ..drivers import sharedfs_driver
from nova import context
from nova import db
from nova import test
from .. import sharedfs_api
from .. import sharedfs_notifier
from nova.tests.api.openstack import fakes
from .. import sharedfs_db

instance_fs_name = "instancefs"
project_fs_name = "projectfs"
global_fs_name = "globalfs"

project1_id = 'project1'
project2_id = 'project2'

instance1_id = 'instance1'
instance2_id = 'instance2'

instance1_ip = '10.10.10.43'
instance2_ip = '10.10.10.44'


def driver_list_fs(self):
    return [{'name': instance_fs_name,
             'size': 1},
            {'name': project_fs_name,
             'size': 2},
            {'name': 'bogus',
             'size': 0},
            {'name': global_fs_name,
             'size': 3}]


def db_filesystem_list(context):
    return [instance_fs_name, project_fs_name, global_fs_name, 'nonsense']


class fake_fs_model(UserDict.UserDict):
    def __init__(self, name, project_id, size, scope):
        self.name = name
        self.project_id = project_id
        self.size = size
        self.scope = scope
        self.data = {'name': name,
                     'project_id': project_id,
                     'size': size,
                     'scope': scope}


def db_filesystem_get(context, name):
    if name == instance_fs_name:
        scope = 'instance'
        size = 1
    elif name == project_fs_name:
        scope = 'project'
        size = 2
    elif name == global_fs_name:
        scope = 'global'
        size = 3
    else:
        return None

    return fake_fs_model(name, project1_id, size, scope)


class fake_instance(object):
    def __init__(self, id, project):
        self.id = id
        self.project = project
        self.uuid = id


def db_instance_get_all(context):
    return [fake_instance(instance1_id, project1_id),
            fake_instance(instance2_id, project2_id),
            fake_instance('bogus', 'noproject')]


def db_instance_get(context, instance_id):
    return fake_instance(instance_id, 'bogus project')


def db_instance_get_all_by_project(context, project_id):
    return [fake_instance(instance2_id, project2_id)]


def db_instance_get_by_uuid(context, instance_id):
    if instance_id == instance1_id:
        return fake_instance(instance1_id, project1_id)
    elif instance_id == instance2_id:
        return fake_instance(instance2_id, project2_id)
    else:
        return None


def db_filesystem_delete(context, name):
    pass


class fake_fixed_ip(UserDict.UserDict):
    def __init__(self, ip, instance_id):
        self.address = ip
        self.instance_id = instance_id
        self.data = {'address': ip, 'instance_id': instance_id}


def db_fixed_ip_get_by_instance(context, instanceid):
    if instanceid == instance1_id:
        ip = instance1_ip
    elif instanceid == instance2_id:
        ip = instance2_ip
    else:
        ip = '0.0.0.0'

    return [fake_fixed_ip(ip, instanceid)]


def db_fixed_ip_get_by_address(context, ip):
    if ip == instance1_ip:
        return fake_fixed_ip(ip, instance1_id)
    elif ip == instance2_ip:
        return fake_fixed_ip(ip, instance2_id)
    else:
        return fake_fixed_ip(ip, 'bogus')


class SharedFSTest(test.TestCase):
    def setUp(self):
        super(SharedFSTest, self).setUp()
        self.fs_controller = sharedfs_api.SharedFSController()

        def db_filesystem_add(context, name, scope, project):
            pass

        self.stubs.Set(sharedfs_db,
                       'filesystem_add',
                       db_filesystem_add)

        def driver_fs_create(slf, name, project_name, size):
            pass

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'create_fs',
                       driver_fs_create)

        self.stubs.Set(sharedfs_db,
                       'filesystem_delete',
                       db_filesystem_delete)

        def driver_fs_delete(slf, name, tenant):
            pass

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'delete_fs',
                       driver_fs_delete)

    def test_fs_list(self):
        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'list_fs',
                       driver_list_fs)
        self.stubs.Set(sharedfs_db,
                       'filesystem_list',
                       db_filesystem_list)
        self.stubs.Set(sharedfs_db,
                       'filesystem_get',
                       db_filesystem_get)

        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem')
        res_dict = self.fs_controller.index(req)
        fs_entries = res_dict.get('fs_entries')

        self.assertEqual(len(fs_entries), 3)
        self.assertEqual(fs_entries[0].get('name'), 'instancefs')
        self.assertEqual(fs_entries[1].get('name'), 'projectfs')
        self.assertEqual(fs_entries[2].get('name'), 'globalfs')
        self.assertEqual(fs_entries[0].get('size'), 1)
        self.assertEqual(fs_entries[2].get('scope'), 'global')

    def test_fs_create_and_attach_global(self):
        self.stubs.Set(db,
                       'instance_get_all',
                       db_instance_get_all)

        self.stubs.Set(db,
                       'fixed_ip_get_by_instance',
                       db_fixed_ip_get_by_instance)

        attachments = []

        def driver_attach(slf, name, ip):
            attachments.append({'name': name, 'ip': ip})

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'attach',
                       driver_attach)

        body = {'fs_entry': {'size': 11, 'scope': 'global'}}
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s' %
                                      global_fs_name)
        res_dict = self.fs_controller.update(req, global_fs_name, body)

        res_entry = res_dict.get('fs_entry')
        self.assertEqual(res_entry.get('name'), global_fs_name)
        self.assertEqual(res_entry.get('size'), 11)
        self.assertEqual(res_entry.get('scope'), 'global')
        self.assertEqual(len(attachments), 3)
        self.assertEqual(attachments[0].get('name'), global_fs_name)
        self.assertEqual(attachments[1].get('name'), global_fs_name)
        self.assertEqual(attachments[0].get('ip'), instance1_ip)
        self.assertEqual(attachments[1].get('ip'), instance2_ip)

    def test_fs_create_and_attach_project(self):
        self.stubs.Set(db,
                       'instance_get_all_by_project',
                       db_instance_get_all_by_project)

        self.stubs.Set(db,
                       'fixed_ip_get_by_instance',
                       db_fixed_ip_get_by_instance)

        attachments = []

        def driver_attach(slf, name, ip):
            attachments.append({'name': name, 'ip': ip})

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'attach',
                       driver_attach)

        body = {'fs_entry': {'size': 11, 'scope': 'project'}}
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s'
                                      % project_fs_name)
        res_dict = self.fs_controller.update(req, project_fs_name, body)

        res_entry = res_dict.get('fs_entry')
        self.assertEqual(res_entry.get('name'), project_fs_name)
        self.assertEqual(res_entry.get('size'), 11)
        self.assertEqual(res_entry.get('scope'), 'project')
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get('name'), project_fs_name)
        self.assertEqual(attachments[0].get('ip'), instance2_ip)

    def test_fs_delete_and_detach_project(self):
        self.stubs.Set(db,
                       'instance_get_all_by_project',
                       db_instance_get_all_by_project)

        self.stubs.Set(db,
                       'fixed_ip_get_by_instance',
                       db_fixed_ip_get_by_instance)

        self.stubs.Set(sharedfs_db,
                       'filesystem_get',
                       db_filesystem_get)

        detachments = []

        def driver_unattach(slf, name, ip):
            detachments.append({'name': name, 'ip': ip})

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'unattach',
                       driver_unattach)

        bogus_name = "bogus_project_name"
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s' %
                                      bogus_name)
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.fs_controller.delete,
                          req,
                          bogus_name)

        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s' %
                                      project_fs_name)
        res_dict = self.fs_controller.delete(req, project_fs_name)

        self.assertEqual(len(detachments), 1)
        self.assertEqual(detachments[0].get('name'), project_fs_name)
        self.assertEqual(detachments[0].get('ip'), instance2_ip)

    def test_fs_delete_and_detach_global(self):
        self.stubs.Set(db,
                       'instance_get_all',
                       db_instance_get_all)

        self.stubs.Set(db,
                       'fixed_ip_get_by_instance',
                       db_fixed_ip_get_by_instance)

        self.stubs.Set(sharedfs_db,
                       'filesystem_get',
                       db_filesystem_get)

        detachments = []

        def driver_unattach(slf, name, ip):
            detachments.append({'name': name, 'ip': ip})

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'unattach',
                       driver_unattach)

        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s' %
                                      global_fs_name)
        res_dict = self.fs_controller.delete(req, global_fs_name)

        self.assertEqual(len(detachments), 3)
        self.assertEqual(detachments[0].get('name'), global_fs_name)
        self.assertEqual(detachments[0].get('ip'), instance1_ip)
        self.assertEqual(detachments[1].get('name'), global_fs_name)
        self.assertEqual(detachments[1].get('ip'), instance2_ip)


def driver_list_attachments(self, fs_name):
    return ['localhost', instance1_ip, instance2_ip]


class SharedAttachTest(test.TestCase):
    def setUp(self):
        super(SharedAttachTest, self).setUp()
        self.attachment_controller = sharedfs_api.SharedFSAttachmentController()

    def test_list_attachments(self):
        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'list_attachments',
                       driver_list_attachments)

        self.stubs.Set(db,
                       'fixed_ip_get_by_address',
                       db_fixed_ip_get_by_address)

        self.stubs.Set(db,
                       'instance_get',
                       db_instance_get)

        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s/attachments' %
                                      global_fs_name)
        res_dict = self.attachment_controller.index(req, global_fs_name)
        instance_entries = res_dict.get('instance_entries')
        self.assertEqual(len(instance_entries), 2)
        self.assertEqual(instance_entries[0]['id'], instance1_id)
        self.assertEqual(instance_entries[1]['id'], instance2_id)

    def test_attach(self):
        self.stubs.Set(db,
                       'instance_get_by_uuid',
                       db_instance_get_by_uuid)

        self.stubs.Set(db,
                       'fixed_ip_get_by_instance',
                       db_fixed_ip_get_by_instance)

        attachments = []

        def driver_attach(slf, name, ip):
            attachments.append({'name': name, 'ip': ip})

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'attach',
                       driver_attach)

        fake_instance_name = 'fakefake'
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s/attachments/%s'
                                      % (global_fs_name, fake_instance_name))
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.attachment_controller.update,
                          req,
                          global_fs_name,
                          fake_instance_name, None)

        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s/attachments/%s'
                                      % (global_fs_name, instance1_id))
        res_dict = self.attachment_controller.update(req, global_fs_name,
                                          instance1_id, None)
        entry = res_dict.get('instance_entry')
        self.assertEqual(entry['id'], instance1_id)

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get('name'), global_fs_name)
        self.assertEqual(attachments[0].get('ip'), instance1_ip)

    def test_unattach(self):
        self.stubs.Set(db,
                       'instance_get_by_uuid',
                       db_instance_get_by_uuid)

        self.stubs.Set(db,
                       'fixed_ip_get_by_instance',
                       db_fixed_ip_get_by_instance)

        unattachments = []

        def driver_unattach(slf, name, ip):
            unattachments.append({'name': name, 'ip': ip})

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'unattach',
                       driver_unattach)

        fake_instance_name = 'fakefake'
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s/attachments/%s'
                                      % (global_fs_name, fake_instance_name))
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.attachment_controller.delete,
                          req,
                          global_fs_name,
                          fake_instance_name)

        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s/attachments/%s'
                                      % (global_fs_name, instance1_id))
        self.attachment_controller.delete(req, global_fs_name, instance1_id)

        self.assertEqual(len(unattachments), 1)
        self.assertEqual(unattachments[0].get('name'), global_fs_name)
        self.assertEqual(unattachments[0].get('ip'), instance1_ip)


class TestNotificationResponse(test.TestCase):
    def setUp(self):
        super(TestNotificationResponse, self).setUp()
        self.notifier = sharedfs_notifier.SharedFSNotifier()

    def testInstanceCreationNotice(self):
        self.stubs.Set(sharedfs_db,
                       'filesystem_list',
                       db_filesystem_list)
        self.stubs.Set(sharedfs_db,
                       'filesystem_get',
                       db_filesystem_get)
        self.stubs.Set(db,
                       'instance_get_by_uuid',
                       db_instance_get_by_uuid)
        self.stubs.Set(db,
                       'fixed_ip_get_by_instance',
                       db_fixed_ip_get_by_instance)

        attachments = []

        def driver_attach(slf, name, ip):
            attachments.append({'name': name, 'ip': ip})

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'attach',
                       driver_attach)

        # This one should result in attachments to
        #  the project and global filesystem.
        message = {'event_type': 'compute.instance.create.end',
                   'payload': {'instance_id': instance1_id,
                               'tenant_id': project1_id,
                               'user_id': 'testuser'}}
        self.notifier.notify(message)
        self.assertEqual(len(attachments), 2)
        self.assertEqual(attachments[0].get('name'), project_fs_name)
        self.assertEqual(attachments[1].get('name'), global_fs_name)
        self.assertEqual(attachments[0].get('ip'), instance1_ip)
        self.assertEqual(attachments[1].get('ip'), instance1_ip)

        # This one should result in attachments to
        #  just the global filesystem.
        attachments = []
        message = {'event_type': 'compute.instance.create.end',
                   'payload': {'instance_id': instance2_id,
                               'tenant_id': project2_id,
                               'user_id': 'testuser'}}
        self.notifier.notify(message)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get('name'), global_fs_name)
        self.assertEqual(attachments[0].get('ip'), instance2_ip)

    def testInstanceDeletionNotice(self):
        self.stubs.Set(sharedfs_db,
                       'filesystem_list',
                       db_filesystem_list)
        self.stubs.Set(sharedfs_db,
                       'filesystem_get',
                       db_filesystem_get)
        self.stubs.Set(db,
                       'instance_get_by_uuid',
                       db_instance_get_by_uuid)
        self.stubs.Set(db,
                       'fixed_ip_get_by_instance',
                       db_fixed_ip_get_by_instance)

        detachments = []

        def driver_unattach(slf, name, ip):
            detachments.append({'name': name, 'ip': ip})

        self.stubs.Set(sharedfs_driver.SharedFSDriver,
                       'unattach',
                       driver_unattach)

        # This one should result in attachments to
        #  the project and global filesystem.
        message = {'event_type': 'compute.instance.delete.start',
                   'payload': {'instance_id': instance1_id,
                               'tenant_id': project1_id,
                               'user_id': 'testuser'}}
        self.notifier.notify(message)
        self.assertEqual(len(detachments), 2)
        self.assertEqual(detachments[0].get('name'), project_fs_name)
        self.assertEqual(detachments[1].get('name'), global_fs_name)
        self.assertEqual(detachments[0].get('ip'), instance1_ip)
        self.assertEqual(detachments[1].get('ip'), instance1_ip)

        # This one should result in attachments to
        #  just the global filesystem.
        detachments = []
        message = {'event_type': 'compute.instance.delete.start',
                   'payload': {'instance_id': instance2_id,
                               'tenant_id': project2_id,
                               'user_id': 'testuser'}}
        self.notifier.notify(message)
        self.assertEqual(len(detachments), 1)
        self.assertEqual(detachments[0].get('name'), global_fs_name)
        self.assertEqual(detachments[0].get('ip'), instance2_ip)
