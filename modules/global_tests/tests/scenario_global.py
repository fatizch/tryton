import os

os.environ['GEN_CREATE_NEW_DB'] = 'FALSE'
os.environ['GEN_RESTORE_DB'] = 'FALSE'
os.environ['GEN_TESTING'] = 'TRUE'
os.environ['GEN_BASIC_INIT'] = 'TRUE'
os.environ['GEN_LOAD_ZIP_CODES'] = 'TRUE'
os.environ['GEN_LOAD_BANKS'] = 'TRUE'
os.environ['GEN_LOAD_ACCOUNTING'] = 'TRUE'
os.environ['GEN_CREATE_PROCESSES'] = 'TRUE'
os.environ['GEN_CREATE_ACTORS'] = 'TRUE'
os.environ['GEN_CREATE_PRODUCTS'] = 'TRUE'
os.environ['GEN_CREATE_COMMISSION_CONFIG'] = 'TRUE'
os.environ['GEN_CREATE_CONTRACTS'] = 'TRUE'
os.environ['GEN_BILL_CONTRACTS'] = 'TRUE'
os.environ['GEN_CREATE_CLAIMS'] = 'TRUE'

import trytond.modules.global_tests.tests.new_db  # NOQA
