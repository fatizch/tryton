import unittest

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    @classmethod
    def get_models(cls):
        return {
            'Clause': 'clause',
            }

    @classmethod
    def get_module_name(cls):
        return 'clause'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
