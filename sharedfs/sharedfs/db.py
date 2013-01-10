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

import sqlalchemy
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

import nova
from nova import log as logging
from nova.openstack.common import cfg
from nova.db.sqlalchemy import models


CONF = cfg.CONF
LOG = logging.getLogger("nova.plugin.%s" % __name__)

opts = [
    cfg.StrOpt('sharedfs_sqlite_db',
               default='novasharedfs.sqlite',
               help='sharedfs file name for sqlite'),
    cfg.StrOpt('sharedfs_sql_connection',
               default='sqlite:///$state_path/$sharedfs_sqlite_db',
               help='connection string for sharedfs sql database'),
]

CONF.register_opts(opts)

_ENGINE = None
_MAKER = None


class FileSystem(models.BASE, models.NovaBase):
    """Represents a filesystem associated with a project."""
    __tablename__ = 'filesystems'
    name = sqlalchemy.Column(String(255), primary_key=True)
    scope = sqlalchemy.Column(String(255))
    project_id = sqlalchemy.Column(String(255))


def get_maker(engine, autocommit=True, expire_on_commit=False):
    """Return a SQLAlchemy sessionmaker using the given engine."""
    return sqlalchemy.orm.sessionmaker(bind=engine,
                                       autocommit=autocommit,
                                       expire_on_commit=expire_on_commit)


def get_session(autocommit=True, expire_on_commit=False):
    """Return a SQLAlchemy session."""
    global _MAKER

    if _MAKER is None:
        engine = get_engine()
        _MAKER = get_maker(engine, autocommit, expire_on_commit)

    session = _MAKER()
    session.query = nova.exception.wrap_db_error(session.query)
    session.flush = nova.exception.wrap_db_error(session.flush)
    return session


def create_table(engine):
    meta = sqlalchemy.MetaData()
    meta.bind = engine

    filesystems = sqlalchemy.Table('filesystems', meta,
            Column('created_at', DateTime(timezone=False)),
            Column('updated_at', DateTime(timezone=False)),
            Column('deleted_at', DateTime(timezone=False)),
            Column('deleted', Boolean(create_constraint=True, name=None)),
            Column('name',
                   String(length=255, convert_unicode=False,
                          assert_unicode=None,
                          unicode_error=None, _warn_on_bytestring=False),
                   primary_key=True, nullable=False),
            Column('scope',
                   String(length=255, convert_unicode=False,
                          assert_unicode=None,
                          unicode_error=None, _warn_on_bytestring=False)),
            Column('project_id',
            String(length=255, convert_unicode=False,
                          assert_unicode=None,
                          unicode_error=None, _warn_on_bytestring=False)),
            )
    # create filesystems table
    try:
        filesystems.create(engine, checkfirst=True)
    except Exception:
        LOG.error(_("Table |%s| not created!"), repr(filesystems))
        raise


def get_engine():
    global _ENGINE
    if _ENGINE:
        return _ENGINE
    models = [FileSystem]
    engine = sqlalchemy.create_engine(CONF.sharedfs_sql_connection,
                                      echo=False)
    for model in models:
        model.metadata.create_all(engine)
    _ENGINE = engine
    create_table(_ENGINE)
    return _ENGINE


def filesystem_list(context):
    session = get_session()
    records = session.query(FileSystem).all()
    fs_names = []
    for record in records:
        fs_names.append(record.name)

    return fs_names


def filesystem_get(context, fs_name):
    session = get_session()
    with session.begin():
        return session.query(FileSystem).filter_by(name=fs_name).first()


def filesystem_add(context, fs_name, scope, project_id):
    session = get_session()
    fs_ref = FileSystem()
    fs_ref.update({'name': fs_name,
                   'scope': scope,
                   'project_id': project_id})
    fs_ref.save(session=session)
    return fs_ref


def filesystem_delete(context, fs_name):
    session = get_session()
    with session.begin():
        session.query(FileSystem).filter_by(name=fs_name).delete()
