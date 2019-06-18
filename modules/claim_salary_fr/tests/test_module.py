# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime

from dateutil.relativedelta import relativedelta

import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'claim_salary_fr'

    @classmethod
    def get_models(cls):
        return {
            'Table': 'table',
            'Cell': 'table.cell',
            }

    def test0000_checkTableAreUpToDate(self):
        '''
            This test will make sure that AGIRC / ARCO / PMSS tables are up to
            date by failing if no values are found for the new year 1 month
            before the end of the previous year.

            If for some reasons the data is not yet available, setting the
            delta to two weeks may be done, but deployments to clients will
            have to be quick.
        '''
        tables = self.Table.search([('xml_id', 'in', (
                        'claim_salary_fr.table_agirc',
                        'claim_salary_fr.table_arrco',
                        'claim_salary_fr.table_pmss',
                        ))])
        self.assertEqual(len(tables), 3)

        # Changing this is not the solution, the table.xml file should be
        # updated with the new values
        target_date = datetime.date.today() + relativedelta(months=1)
        for table in tables:
            self.assertTrue(self.Cell.get(table, target_date) is not None)
            self.assertTrue(
                self.Cell.get(table, datetime.date.today()) is not None)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModuleTestCase))
    return suite
