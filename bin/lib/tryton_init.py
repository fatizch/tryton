import os
import logging

from trytond.config import config
from trytond.pool import Pool
from trytond.transaction import Transaction


def load_conf_file():
    config_file = os.environ.get('TRYTOND_CONFIG', None)
    assert config_file, 'TRYTOND_CONFIG variable should be set'
    config.update_etc(config_file)


load_conf_file()
log_level = os.environ.get('LOG_LEVEL')
assert log_level, 'LOG_LEVEL variable should be set'
logging.basicConfig(
    format='%(asctime)s %(levelname)s:%(name)s: %(message)s',
    levelname=os.environ.get('LOG_LEVEL'),
    datefmt='%H:%M:%S')


def database(db_name=None):
    if not config.get('env', 'testing'):
        database = db_name or os.environ.get('DB_NAME', None)
        assert database, 'Could not resolve database name, you must set'
        ' the DB_NAME variable'
        with Transaction().start(database, 0, readonly=True):
            Pool(database).init()
    return database
