# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest
from decimal import Decimal

import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework
from trytond.modules.api import APIInputError


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Offered Module
    '''
    module = 'offered'

    @classmethod
    def fetch_models_for(cls):
        return ['company_cog']

    @classmethod
    def get_models(cls):
        return {
            'Product': 'offered.product',
            'Sequence': 'ir.sequence',
            'OptionDescription': 'offered.option.description',
            'ExtraData': 'extra_data',
            'SubData': 'extra_data-sub_extra_data',
            'APIModel': 'api',
            'APICore': 'api.core',
            'APIProduct': 'api.product',
             }

    def test0001_testNumberGeneratorCreation(self):
        ng = self.Sequence()
        ng.name = 'Contract Sequence'
        ng.code = 'contract'
        ng.prefix = 'Ctr'
        ng.suffix = 'Y${year}'
        ng.save()
        self.assertTrue(ng.id)

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

        self.assertTrue(product_a.id)

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

        coverage_b = self.OptionDescription()
        coverage_b.code = 'BET'
        coverage_b.name = 'Beta Coverage'
        coverage_b.start_date = datetime.date.today()
        coverage_b.company = company
        coverage_b.currency = company.currency
        coverage_b.start_date = datetime.date(2010, 1, 1)
        coverage_b.save()

        coverage_c = self.OptionDescription()
        coverage_c.code = 'GAM'
        coverage_c.name = 'Gamma Coverage'
        coverage_c.start_date = datetime.date.today()
        coverage_c.company = company
        coverage_c.currency = company.currency
        coverage_c.start_date = datetime.date(2010, 1, 1)
        coverage_c.save()

        self.assertTrue(coverage_a.id)

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
        coverage_b, = self.OptionDescription.search([
                ('code', '=', 'BET'),
                ], limit=1)
        product_a.coverages = [coverage_a, coverage_b]
        product_a.save()

    def test0040_testExtraDataStructure(self):
        # Basic structure
        test_selection = self.ExtraData()
        test_selection.type_ = 'selection'
        test_selection.name = 'test_selection'
        test_selection.string = 'Test Selection'
        test_selection.kind = 'contract'
        test_selection.selection = '1:1\n2:2\n3:3'
        test_selection.has_default_value = True
        test_selection.default_value = '2'
        test_selection.sequence_order = 1
        test_selection.save()

        self.assertEqual(test_selection._get_structure(),
            {'code': 'test_selection', 'name': 'Test Selection',
                'technical_kind': 'selection',
                'business_kind': 'contract',
                'sequence': 1,
                'sorted': True,
                'default': '2',
                'selection': [('1', '1'), ('2', '2'), ('3', '3')],
                })

        test_numeric = self.ExtraData()
        test_numeric.type_ = 'numeric'
        test_numeric.name = 'test_numeric'
        test_numeric.string = 'Test Numeric'
        test_numeric.kind = 'contract'
        test_numeric.digits = 4
        test_numeric.sequence_order = 2
        test_numeric.save()

        self.assertEqual(test_numeric._get_structure(),
            {'code': 'test_numeric', 'name': 'Test Numeric',
                'technical_kind': 'numeric',
                'business_kind': 'contract',
                'sequence': 2,
                'digits': (16, 4)})

        # Sub data
        test_selection.sub_datas = [self.SubData(
                select_value='2', child=test_numeric)]
        test_selection.save()

        self.assertEqual(test_selection._get_structure(),
            {'code': 'test_selection', 'name': 'Test Selection',
                'technical_kind': 'selection',
                'business_kind': 'contract',
                'sorted': True,
                'sequence': 1,
                'default': '2',
                'selection': [('1', '1'), ('2', '2'), ('3', '3')],
                'sub_data': [
                    ('=', '2', test_numeric._get_structure())],
                })

        # Nested sub data
        test_selection_2 = self.ExtraData()
        test_selection_2.type_ = 'selection'
        test_selection_2.name = 'test_selection_2'
        test_selection_2.string = 'Test Selection 2'
        test_selection_2.kind = 'contract'
        test_selection_2.selection = '1:1\n2:2\n3:3'
        test_selection_2.has_default_value = False
        test_selection_2.sequence_order = 4
        test_selection_2.save()

        test_numeric_2 = self.ExtraData()
        test_numeric_2.type_ = 'numeric'
        test_numeric_2.name = 'test_numeric_2'
        test_numeric_2.string = 'Test Numeric 2'
        test_numeric_2.kind = 'contract'
        test_numeric_2.digits = 4
        test_numeric_2.sequence_order = 5
        test_numeric_2.save()

        test_selection_2.sub_datas = [self.SubData(
                select_value='3', child=test_numeric_2)]
        test_selection_2.save()
        test_selection.sub_datas = list(test_selection.sub_datas) + [
            self.SubData(select_value='1', child=test_selection_2)]
        test_selection.save()

        self.maxDiff = None
        self.assertEqual(test_selection._get_structure(),
            {'code': 'test_selection', 'name': 'Test Selection',
                'technical_kind': 'selection',
                'business_kind': 'contract',
                'sorted': True,
                'default': '2',
                'sequence': 1,
                'selection': [('1', '1'), ('2', '2'), ('3', '3')],
                'sub_data': [
                    ('=', '2', test_numeric._get_structure()),
                    ('=', '1', test_selection_2._get_structure()),
                    ],
                })

    @test_framework.prepare_test(
        'offered.test0040_testExtraDataStructure',
        )
    def test0050_extraDataRefreshing(self):
        # _refresh_extra_data(base_data, structure)
        test_selection, = self.ExtraData.search(
            [('name', '=', 'test_selection')])

        test_alpha = self.ExtraData()
        test_alpha.type_ = 'char'
        test_alpha.name = 'test_alpha'
        test_alpha.string = 'Test Numeric 2'
        test_alpha.kind = 'contract'
        test_alpha.digits = 4
        test_alpha.save()

        test_structure = {
            'test_selection': test_selection._get_structure(),
            'test_alpha': test_alpha._get_structure(),
            }

        self.assertEqual(self.ExtraData._refresh_extra_data(
                {'test_alpha': 'test',
                    'test_selection': '3'},
                test_structure),
            {'test_alpha': 'test',
                'test_selection': '3'})
        self.assertEqual(self.ExtraData._refresh_extra_data(
                {'test_alpha': 'test',
                    'test_selection': '3',
                    'test_numeric': Decimal('15')},
                test_structure),
            {'test_alpha': 'test',
                'test_selection': '3'})
        self.assertEqual(self.ExtraData._refresh_extra_data(
                {'test_alpha': 'test',
                    'test_selection': '2'},
                test_structure),
            {'test_alpha': 'test',
                'test_selection': '2',
                'test_numeric': None})
        self.assertEqual(self.ExtraData._refresh_extra_data(
                {'test_alpha': 'test',
                    'test_selection': '2',
                    'test_numeric': Decimal('15')},
                test_structure),
            {'test_alpha': 'test',
                'test_selection': '2',
                'test_numeric': Decimal('15')})
        self.assertEqual(self.ExtraData._refresh_extra_data(
                {'test_alpha': 'test',
                    'test_selection': '2',
                    'test_numeric': Decimal('15'),
                    'test_numeric_2': Decimal('11')},
                test_structure),
            {'test_alpha': 'test',
                'test_selection': '2',
                'test_numeric': Decimal('15')})
        self.assertEqual(self.ExtraData._refresh_extra_data(
                {'test_alpha': 'test',
                    'test_selection': '1',
                    'test_numeric': Decimal('15'),
                    },
                test_structure),
            {'test_alpha': 'test',
                'test_selection': '1',
                'test_selection_2': None})

        # Test nested default matching
        test_selection_2, = self.ExtraData.search(
            [('name', '=', 'test_selection_2')])
        test_selection_2.has_default_value = True
        test_selection_2.default_value = '3'
        test_selection_2.save()

        # Do not forget to refresh the structure!
        test_structure = {
            'test_selection': test_selection._get_structure(),
            'test_alpha': test_alpha._get_structure(),
            }

        self.assertEqual(self.ExtraData._refresh_extra_data(
                {'test_alpha': 'test',
                    'test_selection': '1',
                    'test_numeric': Decimal('15'),
                    },
                test_structure),
            {'test_alpha': 'test',
                'test_selection': '1',
                'test_selection_2': '3',
                'test_numeric_2': None})
        self.assertEqual(self.ExtraData._refresh_extra_data(
                {'test_alpha': 'test',
                    'test_selection': '2',
                    'test_selection_2': '3',
                    'test_numeric_2': Decimal('11'),
                    },
                test_structure),
            {'test_alpha': 'test',
                'test_selection': '2',
                'test_numeric': None})

    @test_framework.prepare_test(
        'offered.test0040_testExtraDataStructure',
        )
    def test0060_extraDataApiStructure(self):
        test_selection, = self.ExtraData.search(
            [('name', '=', 'test_selection')])

        self.maxDiff = None
        self.assertEqual(
            self.APICore._extra_data_structure([test_selection]),
            [
                {
                    'code': 'test_selection',
                    'name': 'Test Selection',
                    'type': 'selection',
                    'default': '2',
                    'sequence': 1,
                    'selection': [
                        {'value': '1', 'name': '1', 'sequence': 0},
                        {'value': '2', 'name': '2', 'sequence': 1},
                        {'value': '3', 'name': '3', 'sequence': 2},
                        ],
                    },
                {
                    'code': 'test_numeric',
                    'conditions': [
                        {'code': 'test_selection', 'operator': '=',
                            'value': '2'}],
                    'digits': (16, 4),
                    'name': 'Test Numeric',
                    'sequence': 2,
                    'type': 'numeric'},
                {'code': 'test_selection_2',
                    'conditions': [{'code': 'test_selection', 'operator': '=',
                            'value': '1'}],
                    'name': 'Test Selection 2',
                    'selection': [
                        {'name': '1', 'sequence': 0, 'value': '1'},
                        {'name': '2', 'sequence': 1, 'value': '2'},
                        {'name': '3', 'sequence': 2, 'value': '3'}],
                    'sequence': 4,
                    'type': 'selection'},
                {'code': 'test_numeric_2',
                    'conditions': [{'code': 'test_selection_2',
                            'operator': '=', 'value': '3'}],
                    'digits': (16, 4),
                    'name': 'Test Numeric 2',
                    'sequence': 5,
                    'type': 'numeric'},
                ],
            )

    @test_framework.prepare_test(
        'offered.test0030_testProductCoverageRelation',
        )
    def test0065_instantiateCodeObject(self):
        product_a, = self.Product.search([
                ('code', '=', 'AAA'),
                ], limit=1)
        self.assertEqual(
            self.APIModel.instantiate_code_object('offered.product',
                {'code': 'AAA'}).id,
            product_a.id)
        self.assertEqual(
            self.APIModel.instantiate_code_object('offered.product',
                {'id': product_a.id}).id,
            product_a.id)
        try:
            self.APIModel.instantiate_code_object('offered.product',
                {'code': 'does not exists'})
        except APIInputError as e:
            self.assertEqual(e, APIInputError([{
                    'type': 'invalid_code',
                    'data': {
                        'model': 'offered.product',
                        'key': {'code': 'does not exists'},
                        },
                    }]),
                )

    @test_framework.prepare_test(
        'offered.test0030_testProductCoverageRelation',
        )
    def test0070_productDescription(self):
        product_a, = self.Product.search([
                ('code', '=', 'AAA'),
                ], limit=1)
        self.maxDiff = None
        self.assertEqual(
            self.APIProduct.describe_products({}, {}),
            [
                {
                    'id': product_a.id,
                    'code': 'AAA',
                    'name': 'Awesome Alternative Allowance',
                    'description': '',
                    'coverages': [{
                            'code': 'ALP',
                            'description': '',
                            'extra_data': [],
                            'id': product_a.coverages[0].id,
                            'name': 'Alpha Coverage',
                            },
                        {
                            'code': 'BET',
                            'description': '',
                            'extra_data': [],
                            'id': product_a.coverages[1].id,
                            'name': 'Beta Coverage'},
                        ],
                    'extra_data': [],
                    'packages': [],
                    'subscriber': {
                        'model': 'party',
                        'required': ['name', 'first_name', 'birth_date',
                            'email', 'address'],
                        'fields': ['name', 'first_name', 'birth_date',
                            'email', 'phone_number', 'is_person', 'address'],
                        },
                    },
                ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
