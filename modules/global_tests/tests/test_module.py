import doctest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import doctest_setup, doctest_teardown


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(doctest.DocFileSuite('scenario_global.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
