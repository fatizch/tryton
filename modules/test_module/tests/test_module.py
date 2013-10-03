import sys
import os
import unittest
DIR = os.path.abspath(os.path.normpath(os.path.join(
    __file__, '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import trytond.tests.test_tryton

MODULE_NAME = os.path.basename(
    os.path.abspath(
        os.path.join(os.path.normpath(__file__), '..', '..')))


def doctest_dropdb(test):
    from trytond import backend
    SQLiteDatabase = backend.get('Database')
    database = SQLiteDatabase().connect()
    cursor = database.cursor(autocommit=True)
    try:
        database.drop(cursor, ':memory:')
        cursor.commit()
    finally:
        cursor.close()


def suite():
    import doctest
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(doctest.DocFileSuite('test_contract_subscription.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb,
            encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
