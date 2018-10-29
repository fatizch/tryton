# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import logging
import shutil
import time
import json
from trytond.modules.coog_core import batch
from trytond.modules.migrator import tools


__all__ = [
    'CreateStaging',
    ]


class CreateStaging(batch.BatchRootNoSelect):
    '''Create Staging Files'''

    __name__ = 'staging.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(CreateStaging, cls).__setup__()
        cls._default_config_items.update({'job_size': 1})

    @classmethod
    def get_tablename_from_filename(cls, filename):
        return (os.path.splitext(filename)[0])

    @classmethod
    def select_ids(cls, **kwargs):
        dirpath = kwargs.get('directory')
        if not dirpath or not os.path.isdir(dirpath):
            raise Exception("A directory must be specified")
        paths = []
        for file_ in os.listdir(dirpath):
            if file_.endswith('.csv'):
                path = os.path.join(dirpath, file_)
                paths.append((path,))
        return paths

    @classmethod
    def execute(cls, objects, ids, **kwargs):
        if not ids:
            raise Exception('No files to stage.')
        path = ids[0]
        dirpath = kwargs.get('directory')
        encoding = kwargs.get('encoding')
        delim = kwargs.get('delimiter')
        tablename = cls.get_tablename_from_filename(
            os.path.basename(path).lower())
        with tools.connect_to_source() as conn:
            try:
                cls.logger.info('Importing file %s into staging' % tablename)
                CreateStaging.create_table(conn, tablename, dirpath)
                rowcount = cls.copy_from_file(conn, path, tablename, encoding,
                    delim)
                CreateStaging.rename_move_file(path, tablename)
            except Exception as e:
                conn.rollback()
                raise e
            else:
                conn.commit()
                return 'rows: %d' % rowcount

    @classmethod
    def create_table(cls, conn, tablename, dirpath):
        cursor = conn.cursor()
        filecolumns = cls.get_table_columns(tablename, dirpath)
        if filecolumns:
            if CreateStaging.table_exists(cursor, tablename) is False:
                fields = ', '.join(['%s varchar' % c for c in filecolumns])
                cursor.execute("CREATE TABLE {} ({})".format(tablename, fields))
        else:
            raise Exception('No definition for %s', tablename)

    @classmethod
    def table_exists(cls, cursor, tablename):
        cursor.execute(
            "SELECT EXISTS("
            "SELECT * FROM information_schema.tables "
            "WHERE table_name = '{}')".format(tablename))
        return bool(cursor.fetchone()['exists'])

    @classmethod
    def get_table_columns(cls, tablename, dirpath):
        columns = []
        if os.path.isdir(os.path.join(dirpath, 'tables_definition')):
            if os.path.exists(os.path.join(dirpath, 'tables_definition/',
                        'columns_definition.json')):
                columns_file = os.path.join(dirpath, 'tables_definition/',
                    'columns_definition.json')
                with open(columns_file, 'r') as f:
                    table_description = json.loads(f.read())
                if tablename in table_description.keys():
                    columns = table_description[tablename]
                return columns
            else:
                raise Exception('No table definition file')
        else:
            raise Exception('The directory tables definitions does not exist')

    @classmethod
    def copy_from_file(cls, conn, path, tablename, encoding,
            delim=';'):
        cursor = conn.cursor()
        op = "COPY {} FROM STDIN WITH CSV ENCODING '{}' DELIMITER '{}'".format(
            tablename, encoding, delim)
        with open(path, 'rb') as csvfile:
            cursor.copy_expert(op, csvfile)
        return cursor.rowcount

    @classmethod
    def rename_move_file(cls, path, tablename):
        archive_dir = os.path.join(os.path.dirname(path), 'archive')
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
        exectime = time.strftime("%Y_%m_%d")
        new_file_name = os.path.splitext(tablename)[0] + '_' + exectime + '.csv'
        os.rename(path, (os.path.join(os.path.dirname(path), new_file_name)))
        src = os.path.join(os.path.dirname(path), new_file_name)
        shutil.move(src, archive_dir)
