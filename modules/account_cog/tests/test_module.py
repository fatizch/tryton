# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'account_cog'

    @classmethod
    def get_models(cls):
        return {
            'Currency': 'currency.currency',
            }

    @test_framework.prepare_test(
        'company_cog.test0001_testCompanyCreation')
    def test0001_create_fiscal_year(self):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        FiscalYear = pool.get('account.fiscalyear')
        Company = pool.get('company.company')
        company = Company.search([('rec_name', '=', 'World Company')])[0]
        today = datetime.date.today()
        sequence = Sequence(
            name='%s' % today.year,
            code='account.move',
            company=company.id,
            )
        sequence.save()
        fiscalyear, = FiscalYear.create([{
            'name': '%s' % today.year,
            'start_date': today.replace(month=1, day=1),
            'end_date': today.replace(month=12, day=31),
            'company': company.id,
            'post_move_sequence': sequence,
            }])
        fiscalyear.save()

    @test_framework.prepare_test(
        'account_cog.test0001_create_fiscal_year',
    )
    def test0001_create_period(self):
        FiscalYear = Pool().get('account.fiscalyear')
        FiscalYear.create_period(FiscalYear.search([]))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
