import unittest
#  import doctest
import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework
#  from trytond.tests.test_tryton import doctest_setup, doctest_teardown


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'endorsement_life'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))

    # Remove test scenario since proteus fails at handling the nested on
    # changes of the Manage Beneficiaries state view :
    # https://bugs.tryton.org/issue5367

    #  suite.addTests(doctest.DocFileSuite(
    #          'scenario_endorsement_change_beneficiaries.rst',
    #          setUp=doctest_setup, tearDown=doctest_teardown,
    #          encoding='utf-8',
    #          optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
