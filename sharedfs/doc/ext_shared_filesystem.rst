The Shared Filesystem Extension
=================================================================
About this Extension
--------------------
The Shared Filesystem extension provides an interface for creating or deleting file-level storage volumes.  It also supports per-instance or per-project access control.

Filesystems with a scope of 'global' will be accessible to all instances.  Filesystems with scope 'project' are automatically made visible to all instances in a given project/tenant.  In both cases, a filesystem's access list is dynamically adjusted as instances are created and deleted.

Filesystems with a scope of 'instance' must be explicitly attached to instances in order to be visible.

To obtain current information about the extensions available to you, issue an EXTENSION query on the OpenStack system where it is installed, such as http://example.com/v1.1/tenant/extension.

Extension Overview
~~~~~~~~~~~~~~~~~~

Name
        Shared Filesystems

Namespace
        http://docs.openstack.org/ext/shared_filesystem/api/v1.1

Alias
        os-shared-filesystem

Contact
        Andrew Bogott <abogott@wikimedia.org>

Status
        Alpha

Extension Version
        v1.0 (2012-4-11)

Dependencies
        Compute API v1.1

Doc Link (PDF)
        http://

Doc Link (WADL)
        http://

Short Description
        This extension creates and manages shared filesystem volumes for Nova.

Sample Query Responses
~~~~~~~~~~~~~~~~~~~~~~

As shown below, responses to an EXTENSION query in XML or JSON provide basic information about the extension.

Extension Query Response: XML::

        None

Extension Query Response: JSON::

        {'extensions':
        [{'updated': '2012-04-11T00:00:00+00:00',
        'name': 'Shared_fs',
        'links': [],
        'namespace': 'http://docs.openstack.org/ext/shared_filesystem/api/v1.1',
        'alias': 'os-shared-filesystem',
        'description': 'Shared filesystem support'}]}

Document Change History
~~~~~~~~~~~~~~~~~~~~~~~

============= =====================================
Revision Date Summary of Changes
2012-04-11    Initial draft
============= =====================================


Summary of Changes
------------------
This extension to the Compute API enables management of shared filesystems that may be accessed by nova instances.  Filesystems may be shared globally, locally, or project-wide.

Support is provided by the addition of new resources.

New Actions
~~~~~~~~~~~
None

New Faults
~~~~~~~~~~
None

New Headers
~~~~~~~~~~~
None

New Resources
~~~~~~~~~~~~~
Create a file system::

    PUT /v1.1/<tenant_id>/os-filesystem/homeforproject1

    # Sample body (project-wide):
    {'fs_entry' :
        {'size': '4Gb',
         'scope': 'project',
         'project' : 'project1'}
    }

    # Sample response (project-wide):
    {'fs_entry' :
        {'name': 'homeforproject1',
         'size': '4Gb',
         'scope': 'project',
         'project' : 'project1'}
    }

    PUT /v1.1/<tenant_id>/os-filesystem/instance2storage

    # Sample body (instance):
    {'fs_entry' :
        {'size': '80Gb',
         'scope': 'instance'}
    }

    # Sample response (instance):
    {'fs_entry' :
        {'name': 'instance2storage',
         'size': '80Gb',
         'scope': 'instance
        }
    }


Get list of available file systems::

    GET /v1.1/<tenant_id>/os-filesystem

    # Sample response:
    {'fs_entries':
        {'name': 'instance2storage',
         'size': '80Gb',
         'scope': 'instance
        }
        {'name': 'homeforproject1'
         'size': '4Gb',
         'scope': 'project',
         'project' : 'project1'
        }
    }


Delete a file system::

    DELETE /v1.1/<tenant_id>/os-filesystem/instance2storage

    Normal Response Code: 202
    Failure Response Code: 404 (FS to be deleted not found.)
    Failure Response Code: 403 (Insufficient permissions to delete.)


List instances connected to a file system::

    GET /v1.1/<tenant_id>/os-filesystem/homeforproject1/instances

    # Sample response:
    {'instance_entries':
        {'id': 'instance00001'}
        {'id': 'instance00002'}
        {'id': 'instance00002'}
    }


Connect an instance to a file system::

    PUT /v1.1/<tenant_id>/os-filesystem/instance2storage/instances/<instance_id>

    # Sample response:
    {'instance_entry':
        {'id': <instance_id>}


Remove an instance from a file system::

    DELETE /v1.1/<tenant_id>/os-filesystem/instance2storage/instances/<instance_id>

    Normal Response Code: 202
    Failure Response Code: 404 (Instance or FS not found.)
    Failure Response Code: 403 (Insufficient permission)


New States
~~~~~~~~~~
None

Changes to the Cloud Servers Specification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
None
