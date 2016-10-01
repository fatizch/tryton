# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework


def doctest_dropdb(test):
    from trytond import backend
    SQLiteDatabase = backend.get('Database')
    database = SQLiteDatabase().connect()
    cursor = database.cursor(autocommit=True)
    try:
        database.drop(cursor, ':memory:')
        cursor.commit()
    except:
        pass
    finally:
        cursor.close()


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'test_module'

    def test9999_launch_test_cases(self):
        pass


def suite():
    suite = trytond.tests.test_tryton.suite()
    # suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
    #     ModuleTestCase))
    return suite
