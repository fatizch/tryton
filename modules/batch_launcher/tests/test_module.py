# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

from trytond.pool import Pool
from trytond.modules.coog_core import BatchRoot


class BatchLauncherTestCase(ModuleTestCase):
    'Batch Launcher Test Case'
    '''
    Test Coog batch launcher.
    '''
    module = 'batch_launcher'

    @with_transaction()
    def test_check_required_params(self):
        class TestClassNoRequiredParams(BatchRoot):
            def execute(cls, objects, ids, crash=None):
                return

        class TestClassRequiredParams(BatchRoot):
            def execute(cls, objects, ids, treatment_date, test_param,
                    default_param=False):
                return

        pool = Pool()
        BatchLauncher = pool.get('batch.launcher.select_batchs')
        excluded_params = ['cls', 'objects', 'ids']
        self.assertEqual(BatchLauncher.get_used_params(
            TestClassNoRequiredParams, excluded_params, only_required=False),
            set(['crash']))
        self.assertEqual(BatchLauncher.get_used_params(
            TestClassNoRequiredParams, excluded_params, only_required=True),
            set([]))
        self.assertEqual(BatchLauncher.get_used_params(
            TestClassRequiredParams, excluded_params, only_required=False),
            set(['treatment_date', 'test_param', 'default_param']))
        self.assertEqual(BatchLauncher.get_used_params(
            TestClassRequiredParams, excluded_params, only_required=True),
            set(['treatment_date', 'test_param']))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        BatchLauncherTestCase))
    return suite
