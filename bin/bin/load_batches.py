#!/usr/bin/env python
import os
from trytond.pool import Pool
from trytond.modules.coog_core import batch
from trytond.transaction import Transaction

database = os.environ.get('DB_NAME', None)
with Transaction().start(database, 0, readonly=True):
    pool = Pool(database_name=database)
    #  pool.init()
    for name, kls in pool.iterobject():
        if issubclass(kls, batch.BatchRoot):
            print name
