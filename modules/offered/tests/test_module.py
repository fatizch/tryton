# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Offered Module
    '''
    module = 'offered'

    @classmethod
    def depending_modules(cls):
        return ['company_cog']

    @classmethod
    def get_models(cls):
        return {
            'Product': 'offered.product',
            'Sequence': 'ir.sequence',
            'OptionDescription': 'offered.option.description',
             }

    def test0001_testNumberGeneratorCreation(self):
        ng = self.Sequence()
        ng.name = 'Contract Sequence'
        ng.code = 'contract'
        ng.prefix = 'Ctr'
        ng.suffix = 'Y${year}'
        ng.save()
        self.assert_(ng.id)

    @test_framework.prepare_test(
        'offered.test0001_testNumberGeneratorCreation',
        'company_cog.test0001_testCompanyCreation',
        )
    def test0010_testProductCreation(self):
        company, = self.Company.search([('party.name', '=', 'World Company')])
        ng = self.Sequence.search([
                ('code', '=', 'contract')])[0]
        product_a = self.Product()
        product_a.code = 'AAA'
        product_a.name = 'Awesome Alternative Allowance'
        product_a.start_date = datetime.date.today()
        product_a.contract_generator = ng
        product_a.company = company
        product_a.currency = company.currency
        product_a.start_date = datetime.date(2010, 1, 1)
        product_a.save()

        self.assert_(product_a.id)

    @test_framework.prepare_test(
        'company_cog.test0001_testCompanyCreation',
        )
    def test0020_testCoverageCreation(self):
        company, = self.Company.search([('party.name', '=', 'World Company')])
        coverage_a = self.OptionDescription()
        coverage_a.code = 'ALP'
        coverage_a.name = 'Alpha Coverage'
        coverage_a.start_date = datetime.date.today()
        coverage_a.company = company
        coverage_a.currency = company.currency
        coverage_a.start_date = datetime.date(2010, 1, 1)
        coverage_a.save()

        self.assert_(coverage_a.id)

    @test_framework.prepare_test(
        'offered.test0010_testProductCreation',
        'offered.test0020_testCoverageCreation',
        )
    def test0030_testProductCoverageRelation(self):
        product_a, = self.Product.search([
                ('code', '=', 'AAA'),
                ], limit=1)
        coverage_a, = self.OptionDescription.search([
                ('code', '=', 'ALP'),
                ], limit=1)
        product_a.coverages = [coverage_a]
        product_a.save()
        self.assertEqual([x.coverage for x in product_a.ordered_coverages],
            [coverage_a])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
