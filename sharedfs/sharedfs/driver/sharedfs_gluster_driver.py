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

import os
import time
from xml.etree import ElementTree

import paramiko

from nova import exception
from nova import flags
from nova.openstack.common import cfg
from nova.openstack.common import log as logging
from . import sharedfs_driver
from nova import utils
from nova.volume import iscsi
from nova.volume import volume_types


FLAGS = flags.FLAGS
LOG = logging.getLogger("nova.plugin.%s" % __name__)

gluster_opts = [
    cfg.StrOpt('gluster_mode',
               default='replicated',
               help="Distribution mode for gluster volumes.  Should be "
                    "'normal', 'replicated' or 'striped'."),
    cfg.StrOpt('gluster_transport',
               default='tcp',
               help="Transport method for gluster.  Should be "
                    "'tcp' or 'rdma'."),
    cfg.IntOpt('gluster_count',
               default=1,
               help="Determines the number of replications or the stripe "
                    "count, depending on gluster_mode.  If mode is "
                    "'normal' then this setting has no effect."),
    cfg.MultiStrOpt('gluster_bricks',
               default=[],
               help='Each entry should be in the form hostname:location. '
                    'For example, server1:/exp1')]


FLAGS.register_opts(gluster_opts)


class GlusterDriver(sharedfs_driver.SharedFSDriver):
    """Implements the Shared Filesystem driver for GlusterFS."""

    def do_setup(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def check_for_setup_error(self):
        """Raises an error if prerequisites aren't met."""

        if FLAGS.gluster_mode not in ['normal', 'replicated', 'striped']:
            raise exception.Error(_("Gluster mode must be 'normal', "
                                    "'replicated', or 'striped'."))
        if (FLAGS.gluster_transport and
            FLAGS.gluster_transport not in ['tcp', 'rdma']):
            raise exception.Error(_("Gluster transport must be 'tcp' "
                                    "or 'rdma'."))
        if not len(FLAGS.gluster_bricks):
            raise exception.Error(_("At least one gluster brick is "
                                    "required."))
        if (FLAGS.gluster_mode == 'replicated' or
            FLAGS.gluster_mode == 'striped'):
            if len(FLAGS.gluster_bricks) < FLAGS.gluster_count:
                raise exception.Error(_("gluster_count cannot exceed "
                                        "the number of bricks."))
            if len(FLAGS.gluster_bricks) % FLAGS.gluster_count != 0:
                LOG.warn(_("If the number of gluster bricks is not "
                           "a multiple of gluster_count then  "
                           "some storage space may be wasted."))
        try:
            self._refresh_volume_info()
        except exception.ProcessExecutionError:
            raise exception.Error(_("Glusterfs is not working."))

    def _glustersizestr(self, size_in_g):
        if int(size_in_g) == 0:
            return '100MB'
        return '%sGB' % size_in_g

    def _refresh_volume_info(self):
        (out, err) = utils.execute('gluster', 'volume', 'info',
                                   run_as_root=True)
        if err:
            raise exception.Error(_("Glusterfs failure: %s") % out)

        self.volume_info = {}
        volname = "unknown"

        for line in out.split("\n"):
            part = line.partition(':')
            if not part[1]:
                continue
            if part[0] == 'Volume Name':
                volname = part[2].strip()
                self.volume_info[volname] = {}
            else:
                self.volume_info[volname][part[0].strip()] = part[2].strip()

    def _make_bricks(self, fs_name, tenant):
        """Create dirs for each brick and prepare a brick list for gluster."""

        bricklist = []
        for brick in FLAGS.gluster_bricks:
            parts = brick.partition(':')
            host = parts[0]
            dir = '%s/%s/%s' % (parts[2], tenant, fs_name)
            self.ssh.connect(host)
            stdin, stdout, stderr = self.ssh.exec_command("mkdir -p '%s'" %
                                                          dir)
            out = stdout.readlines()
            err = stderr.readlines()
            if err:
                LOG.warn("Failed to mkdir %s on %s. "
                         "That brick will be excluded from filesystem %s."
                         "\nstdout:  %s"
                         "\nstderr:  %s"
                         % (dir, host, fs_name, out, err))
            else:
                brickdef = '%s:%s' % (host, dir)
                LOG.debug("Created brick; adding %s" % brickdef)
                bricklist.append(brickdef)

        if not bricklist:
            raise exception.Error(_("Glusterfs failure."
                                    "Could not mkdir on a single brick."))

        return bricklist

    def _cleanup_bricks(self, fs_name, tenant):
        """Delete dirs for each brick."""

        for brick in FLAGS.gluster_bricks:
            parts = brick.partition(':')
            host = parts[0]
            dir = '%s/%s/%s' % (parts[2], tenant, fs_name)
            self.ssh.connect(host)
            stdin, stdout, stderr = self.ssh.exec_command("rmdir '%s'" %
                                                          dir)
            out = stdout.readlines()
            err = stderr.readlines()
            if err:
                LOG.warn("Failed to rmdir %s on %s. "
                         "We leaked a directory."
                         "\nstdout:  %s"
                         "\nstderr:  %s"
                         % (dir, host, out, err))

            projdir = '%s/%s' % (parts[2], tenant)

            # This will fail quietly if there are still subdirs.
            stdin, stdout, stderr = self.ssh.exec_command("rmdir '%s'" %
                                                          projdir)

    def create_fs(self, fs_name, tenant, size_in_g):
        bricklist = self._make_bricks(fs_name, tenant)

        if FLAGS.gluster_mode != 'normal':
            utils.execute('gluster', '--mode=script', 'volume', 'create',
                          fs_name, FLAGS.gluster_mode, FLAGS.gluster_count,
                          'transport', FLAGS.gluster_transport,
                          ' '.join(bricklist), run_as_root=True)
        else:
            utils.execute('gluster', '--mode=script', 'volume', 'create',
                          fs_name, 'transport', FLAGS.gluster_transport,
                          ' '.join(bricklist), run_as_root=True)

        utils.execute('gluster', '--mode=script', 'volume', 'quota',
                      fs_name, 'enable', run_as_root=True)
        utils.execute('gluster', '--mode=script', 'volume', 'quota',
                      fs_name, 'limit-usage', '/data',
                      self._glustersizestr(size_in_g), run_as_root=True)
        utils.execute('gluster', '--mode=script', 'volume', 'start',
                      fs_name, run_as_root=True)
        utils.execute('gluster', '--mode=script', 'volume', 'set', fs_name,
                      'allow', 'localhost', run_as_root=True)

    def delete_fs(self, fs_name, tenant):
        utils.execute('gluster', '--mode=script', 'volume', 'stop',
                      fs_name, run_as_root=True)

        utils.execute('gluster', '--mode=script', 'volume', 'delete',
                      fs_name, run_as_root=True)

        bricklist = self._cleanup_bricks(fs_name, tenant)

    def _get_size(self, volname):
        rawsize = self.volume_info[volname].get('features.limit-usage',
                                                "unknown:unknown")
        return rawsize.partition(':')[2]

    def list_fs(self):
        self._refresh_volume_info()
        return [{'name': key,
                 'size': self._get_size(key)}
                for key in self.volume_info.keys()]

    def attach(self, fs_name, ip_list):
        attachlist = self.list_attachments(fs_name)
        if isinstance(ip_list, list):
            for ip in ip_list:
                if ip not in attachlist:
                    attachlist.append(ip)
        else:
            if ip_list not in attachlist:
                attachlist.append(ip_list)
        newlist = ','.join(attachlist)
        LOG.debug('attachlist: %s' % attachlist)
        utils.execute('gluster', '--mode=script', 'volume', 'set',
                      fs_name, 'auth.allow', newlist, run_as_root=True)

    def unattach(self, fs_name, ip_list):
        attachlist = self.list_attachments(fs_name)
        if isinstance(ip_list, list):
            for item in ip_list:
                if item in attachlist:
                    attachlist.remove(item)
        else:
            if ip_list in attachlist:
                attachlist.remove(ip_list)
        newlist = ','.join(attachlist)
        utils.execute('gluster', '--mode=script', 'volume', 'set', fs_name,
                      'auth.allow', newlist, run_as_root=True)

    def list_attachments(self, fs_name):
        self._refresh_volume_info()
        l = self.volume_info[fs_name].get('auth.allow')
        if l:
            return l.split(',')
        else:
            return []
