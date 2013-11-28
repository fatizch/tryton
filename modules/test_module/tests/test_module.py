import unittest

import trytond.tests.test_tryton

from trytond.modules.coop_utils import test_framework


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


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'test_module'


def suite():
    import doctest
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite('test_contract_subscription.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb,
            encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
