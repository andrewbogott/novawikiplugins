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

from .. import sharedfs_api
from nova import context
from nova import db
from nova import flags
from ..drivers import sharedfs_gluster_driver
from nova import test
from . import test_sharedfs
from nova.tests.api.openstack import fakes
from nova import utils
from .. import sharedfs_db

FLAGS = flags.FLAGS


class GlusterDriverTest(test.TestCase):
    def setUp(self):
        super(GlusterDriverTest, self).setUp()

        def gl_refresh_volume_info(self):
            self.volume_info = {test_sharedfs.instance_fs_name:
                                   {'features.limit-usage':
                                    'size:9'},
                                test_sharedfs.project_fs_name:
                                   {'features.limit-usage':
                                    'size:8',
                                    'auth.allow': 'a,b'},
                                'bogus':
                                    {'features.limit-usage':
                                     'size:7g'}}

        self.stubs.Set(sharedfs_gluster_driver.GlusterDriver,
                       '_refresh_volume_info',
                       gl_refresh_volume_info)

        self.executed = []

        def utils_execute(*cmd, **kwargs):
            self.executed = cmd

        self.stubs.Set(utils,
                       'execute',
                       utils_execute)

        def gl_make_bricks(self, fs_name, tenant):
            return []
        self.stubs.Set(sharedfs_gluster_driver.GlusterDriver,
                       '_make_bricks',
                       gl_make_bricks)

        def gl_cleanup_bricks(self, fs_name, tenant):
            pass
        self.stubs.Set(sharedfs_gluster_driver.GlusterDriver,
                       '_cleanup_bricks',
                       gl_cleanup_bricks)

        self.stubs.Set(sharedfs_db,
                       'filesystem_list',
                       test_sharedfs.db_filesystem_list)
        self.stubs.Set(sharedfs_db,
                       'filesystem_get',
                       test_sharedfs.db_filesystem_get)
        self.stubs.Set(db,
                       'instance_get_all_by_project',
                       test_sharedfs.db_instance_get_all_by_project)
        self.stubs.Set(db,
                       'instance_get_by_uuid',
                       test_sharedfs.db_instance_get_by_uuid)
        self.stubs.Set(db,
                       'fixed_ip_get_by_instance',
                       test_sharedfs.db_fixed_ip_get_by_instance)
        self.stubs.Set(sharedfs_db,
                       'filesystem_delete',
                       test_sharedfs.db_filesystem_delete)

        self.old_FLAGS_sharedfs_driver = FLAGS.sharedfs_driver
        self.old_FLAGS_gluster_bricks = FLAGS.gluster_bricks

        FLAGS.sharedfs_driver = (
            "sharedfs.drivers.sharedfs_gluster_driver.GlusterDriver")
        FLAGS.gluster_bricks = ['fake:fake', 'example:example']
        self.fs_controller = sharedfs_api.SharedFSController()
        self.attachment_controller = sharedfs_api.SharedFSAttachmentController()

    def tearDown(self):
        FLAGS.sharedfs_driver = self.old_FLAGS_sharedfs_driver
        FLAGS.gluster_bricks = self.old_FLAGS_gluster_bricks
        super(GlusterDriverTest, self).tearDown()

    def test_gluster_list(self):
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem')
        res_dict = self.fs_controller.index(req)
        fs_entries = res_dict.get('fs_entries')

        self.assertEqual(len(fs_entries), 2)
        self.assertEqual(fs_entries[0].get('name'), 'projectfs')
        self.assertEqual(fs_entries[1].get('name'), 'instancefs')
        self.assertEqual(fs_entries[0].get('size'), '8')
        self.assertEqual(fs_entries[1].get('scope'), 'instance')

    def test_gluster_create(self):
        body = {'fs_entry': {'size': 11, 'scope': 'project'}}
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s'
                                        % test_sharedfs.project_fs_name,
                                      use_admin_context=True)
        res_dict = self.fs_controller.update(req,
                                             test_sharedfs.project_fs_name,
                                             body)
        self.assertEqual(len(self.executed), 7)
        self.assertEqual(self.executed[0], 'gluster')

    def test_gluster_delete(self):
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s' %
                                      test_sharedfs.project_fs_name)
        res_dict = self.fs_controller.delete(req,
                                             test_sharedfs.project_fs_name)
        self.assertEqual(len(self.executed), 5)
        self.assertEqual(self.executed[0], 'gluster')

    def test_gluster_attach(self):
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s/attachments/%s'
                                      % (test_sharedfs.project_fs_name,
                                         test_sharedfs.instance1_id))
        res_dict = self.attachment_controller.update(req,
                                          test_sharedfs.project_fs_name,
                                          test_sharedfs.instance1_id, None)
        self.assertEqual(len(res_dict), 1)
        self.assertEqual(res_dict['instance_entry']['id'],
                         test_sharedfs.instance1_id)
        self.assertEqual(self.executed[5], 'auth.allow')

    def test_gluster_unattach(self):
        req = fakes.HTTPRequest.blank('/vw/123/os-filesystem/%s/attachments/%s'
                                      % (test_sharedfs.project_fs_name,
                                         test_sharedfs.instance1_id))
        self.attachment_controller.delete(req, test_sharedfs.project_fs_name,
                                          test_sharedfs.instance1_id)
        self.assertEqual(self.executed[5], 'auth.allow')
