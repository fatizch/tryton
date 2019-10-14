# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework
from trytond.modules.api import APIInputError, api_input_error_manager


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Offered Module
    '''
    module = 'offered'
    extras = ['web_configuration']

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

    def test0005_testExtraDataCreation(self):
        contract_extra_1 = self.ExtraData()
        contract_extra_1.name = 'contract_1'
        contract_extra_1.string = 'Contract 1'
        contract_extra_1.kind = 'contract'
        contract_extra_1.type_ = 'numeric'
        contract_extra_1.digits = 2
        contract_extra_1.save()

        contract_extra_2 = self.ExtraData()
        contract_extra_2.name = 'contract_2'
        contract_extra_2.string = 'Contract 2'
        contract_extra_2.kind = 'contract'
        contract_extra_2.type_ = 'boolean'
        contract_extra_2.save()

        contract_extra_3 = self.ExtraData()
        contract_extra_3.name = 'contract_3'
        contract_extra_3.string = 'Contract 3'
        contract_extra_3.kind = 'contract'
        contract_extra_3.type_ = 'selection'
        contract_extra_3.selection = '1:1\n2:2\n3:3'
        contract_extra_3.save()

        option_extra_1 = self.ExtraData()
        option_extra_1.name = 'option_1'
        option_extra_1.string = 'Option 1'
        option_extra_1.kind = 'option'
        option_extra_1.type_ = 'numeric'
        option_extra_1.digits = 2
        option_extra_1.save()

        option_extra_2 = self.ExtraData()
        option_extra_2.name = 'option_2'
        option_extra_2.string = 'Option 2'
        option_extra_2.kind = 'option'
        option_extra_2.type_ = 'boolean'
        option_extra_2.save()

        option_extra_3 = self.ExtraData()
        option_extra_3.name = 'option_3'
        option_extra_3.string = 'Option 3'
        option_extra_3.kind = 'option'
        option_extra_3.type_ = 'selection'
        option_extra_3.selection = '1:1\n2:2\n3:3'
        option_extra_3.save()

    @test_framework.prepare_test(
        'offered.test0005_testExtraDataCreation',
        'offered.test0001_testNumberGeneratorCreation',
        'company_cog.test0001_testCompanyCreation',
        )
    def test0010_testProductCreation(self):
        company, = self.Company.search([('party.name', '=', 'World Company')])
        ng, = self.Sequence.search([('code', '=', 'contract')])
        product_a = self.Product()
        product_a.code = 'AAA'
        product_a.name = 'Awesome Alternative Allowance'
        product_a.start_date = datetime.date.today()
        product_a.contract_generator = ng
        product_a.company = company
        product_a.currency = company.currency
        product_a.start_date = datetime.date(2010, 1, 1)
        product_a.extra_data_def = self.ExtraData.search(
            [('kind', '=', 'contract')])
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
        coverage_a.extra_data_def = self.ExtraData.search(
            [('kind', '=', 'option')])
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

    @test_framework.prepare_test(
        'offered.test0030_testProductCoverageRelation',
        )
    def test0035_testProductPackages(self):
        pool = Pool()
        Product = pool.get('offered.product')
        Coverage = pool.get('offered.option.description')
        Package = pool.get('offered.package')
        PackageCoverageRelation = pool.get('offered.package-option.description')

        product_a, = Product.search([('code', '=', 'AAA')])
        coverage_a, = Coverage.search([('code', '=', 'ALP')])
        coverage_b, = Coverage.search([('code', '=', 'BET')])

        package_a = Package()
        package_a.name = 'Package A'
        package_a.code = 'package_a'
        package_a.option_relations = [
            PackageCoverageRelation(option=coverage_a, extra_data={
                    'option_3': '2'}),
            PackageCoverageRelation(option=coverage_b),
            ]
        package_a.extra_data = {
            'contract_1': '16.10',
            }
        package_a.save()

        package_b = Package()
        package_b.name = 'Package B'
        package_b.code = 'package_b'
        package_b.option_relations = [
            PackageCoverageRelation(option=coverage_a, extra_data={
                    'option_3': '1'}),
            ]
        package_b.save()

        product_a.packages = [package_a, package_b]

        # This is ignored unless offered_insurance is installed, but this
        # allows for a simple useful test in contract_insurance (test0070)
        product_a.packages_defined_per_covered = False

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
                    'code': 'test_numeric', 'conditions': [
                        {'code': 'test_selection', 'operator': '=',
                            'value': '2'}],
                    'digits': 4,
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
                    'digits': 4,
                    'name': 'Test Numeric 2',
                    'sequence': 5,
                    'type': 'numeric'},
                ],
            )

    @test_framework.prepare_test(
        'offered.test0005_testExtraDataCreation',
        )
    def test0061_extraDataParsing(self):
        contract_extra_1, = self.ExtraData().search(
            [('name', '=', 'contract_1')])
        contract_extra_1.type_ = 'numeric'
        contract_extra_1.digits = 2

        contract_extra_2, = self.ExtraData().search(
            [('name', '=', 'contract_2')])
        contract_extra_2.type_ = 'boolean'

        contract_extra_3, = self.ExtraData().search(
            [('name', '=', 'contract_3')])
        contract_extra_3.type_ = 'selection'

        contract_extra_4 = self.ExtraData()
        contract_extra_4.name = 'contract_4'
        contract_extra_4.string = 'Contract 4'
        contract_extra_4.kind = 'contract'
        contract_extra_4.type_ = 'integer'
        contract_extra_4.save()

        contract_extra_5 = self.ExtraData()
        contract_extra_5.name = 'contract_5'
        contract_extra_5.string = 'Contract 5'
        contract_extra_5.kind = 'contract'
        contract_extra_5.type_ = 'date'
        contract_extra_5.save()

        def test_error(extra_data, errors):
            try:
                with api_input_error_manager():
                    self.APICore._extra_data_convert(extra_data)
                raise Exception('Not Raised')
            except APIInputError as e:
                self.assertEqual(e.data, errors)

        test_error({'inexisting': '1'}, [{
                    'type': 'unknown_extra_data',
                    'data': {'code': 'inexisting'},
                    }])

        test_error({'contract_4': 'foo'}, [{
                    'type': 'extra_data_type',
                    'data': {
                        'extra_data': 'contract_4',
                        'expected_type': 'integer',
                        'given_type': str(str),
                        },
                    }])

        test_error({'contract_1': 123.0}, [{
                    'type': 'extra_data_type',
                    'data': {
                        'extra_data': 'contract_1',
                        'expected_type': 'string',
                        'given_type': str(float),
                        },
                    }])

        test_error({'contract_1': False}, [{
                    'type': 'extra_data_type',
                    'data': {
                        'extra_data': 'contract_1',
                        'expected_type': 'string',
                        'given_type': str(bool),
                        },
                    }])

        test_error({'contract_1': '123.456'}, [{
                    'type': 'extra_data_conversion',
                    'data': {
                        'extra_data': 'contract_1',
                        'expected_format': '1111.11',
                        'given_value': '123.456',
                        },
                    }])

        test_error({'contract_1': '123-123az'}, [{
                    'type': 'extra_data_conversion',
                    'data': {
                        'extra_data': 'contract_1',
                        'expected_format': '1111.11',
                        'given_value': '123-123az',
                        },
                    }])

        self.assertEqual(self.APICore._extra_data_convert(
                {'contract_1': '123.45'}),
            {'contract_1': Decimal('123.45')})

        test_error({'contract_2': None}, [{
                    'type': 'extra_data_type',
                    'data': {
                        'extra_data': 'contract_2',
                        'expected_type': 'boolean',
                        'given_type': str(type(None)),
                        },
                    }])

        test_error({'contract_2': 0}, [{
                    'type': 'extra_data_type',
                    'data': {
                        'extra_data': 'contract_2',
                        'expected_type': 'boolean',
                        'given_type': str(int),
                        },
                    }])

        test_error({'contract_2': 'True'}, [{
                    'type': 'extra_data_type',
                    'data': {
                        'extra_data': 'contract_2',
                        'expected_type': 'boolean',
                        'given_type': str(str),
                        },
                    }])

        test_error({'contract_3': 12}, [{
                    'type': 'extra_data_type',
                    'data': {
                        'extra_data': 'contract_3',
                        'expected_type': 'string',
                        'given_type': str(int),
                        },
                    }])

        test_error({'contract_3': '12'}, [{
                    'type': 'extra_data_conversion',
                    'data': {
                        'extra_data': 'contract_3',
                        'expected_format': ['1', '2', '3'],
                        'given_value': '12',
                        },
                    }])

        test_error({'contract_5': None}, [{
                    'type': 'extra_data_type',
                    'data': {
                        'extra_data': 'contract_5',
                        'expected_type': 'string',
                        'given_type': str(type(None)),
                        },
                    }])

        test_error({'contract_5': '123-45-40-1'}, [{
                    'type': 'extra_data_conversion',
                    'data': {
                        'extra_data': 'contract_5',
                        'expected_format': 'YYYY-MM-DD',
                        'given_value': '123-45-40-1',
                        },
                    }])

        self.assertEqual(self.APICore._extra_data_convert(
                {'contract_5': '2000-05-01'}),
            {'contract_5': datetime.date(2000, 5, 1)})

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
            with api_input_error_manager():
                self.APIModel.instantiate_code_object('offered.product',
                    {'code': 'does not exists'})
        except APIInputError as e:
            self.assertEqual(e, APIInputError([{
                    'type': 'configuration_not_found',
                    'data': {
                        'model': 'offered.product',
                        'code': 'does not exists',
                        },
                    }]),
                )

    @test_framework.prepare_test(
        'offered.test0035_testProductPackages',
        )
    def test0070_productDescription(self):
        pool = Pool()

        Product = pool.get('offered.product')
        Coverage = pool.get('offered.option.description')
        Package = pool.get('offered.package')
        extra_data = self.ExtraData()
        WebUIResourceKey = pool.get('web.ui.resource.key')

        helper_resource, = WebUIResourceKey.search([('code', '=', 'helper')])
        title_resource, = WebUIResourceKey.search([('code', '=', 'title')])

        extra_data.name = 'analyse_forcee'
        extra_data.string = 'Analyse forcée'
        extra_data.kind = 'contract'
        extra_data.type_ = 'selection'
        extra_data.save()

        product_a, = Product.search([('code', '=', 'AAA')])
        coverage_a, = Coverage.search([('code', '=', 'ALP')])
        coverage_b, = Coverage.search([('code', '=', 'BET')])
        package_a, = Package.search([('code', '=', 'package_a')])
        package_b, = Package.search([('code', '=', 'package_b')])

        # Add some API resources on extra_data
        contract_1, = pool.get('extra_data').search(
            [('name', '=', 'contract_1')])
        contract_1.web_ui_resources = [
            {
                'key': helper_resource,
                'value': '"some value"',
                'origin_resource': extra_data,
                },
            {
                'key': title_resource,
                'value': '1234',
                'origin_resource': extra_data,
                },
            ]
        contract_1.save()

        self.assertEqual(
            pool.get('api.product').describe_products(
                {}, {'_debug_server': True}),
            [
                {
                    'id': product_a.id,
                    'code': 'AAA',
                    'name': 'Awesome Alternative Allowance',
                    'description': '',
                    'extra_data': [
                        {
                            'code': 'contract_1',
                            'name': 'Contract 1',
                            'type': 'numeric',
                            'sequence': 1,
                            'digits': 2,
                            'custom_resources': {
                                'title': '1234',
                                'helper': '"some value"',
                                },
                            },
                        {
                            'code': 'contract_2',
                            'name':
                            'Contract 2',
                            'type': 'boolean',
                            'sequence': 2,
                            },
                        {
                            'code': 'contract_3',
                            'name': 'Contract 3',
                            'type': 'selection',
                            'sequence': 3,
                            'selection': [
                                {'value': '1', 'name': '1',
                                    'sequence': 0},
                                {'value': '2', 'name': '2',
                                    'sequence': 1},
                                {'value': '3', 'name': '3',
                                    'sequence': 2},
                                ],
                            },
                        ],
                    'coverages': [
                        {
                            'id': coverage_a.id,
                            'name': 'Alpha Coverage',
                            'code': 'ALP',
                            'description': '',
                            'extra_data': [
                                {
                                    'code': 'option_1',
                                    'name': 'Option 1',
                                    'type': 'numeric',
                                    'sequence': 4,
                                    'digits': 2,
                                    },
                                {
                                    'code': 'option_2',
                                    'name':
                                    'Option 2',
                                    'type': 'boolean',
                                    'sequence': 5,
                                    },
                                {
                                    'code': 'option_3',
                                    'name': 'Option 3',
                                    'type': 'selection',
                                    'sequence': 6,
                                    'selection': [
                                        {'value': '1', 'name': '1',
                                            'sequence': 0},
                                        {'value': '2', 'name': '2',
                                            'sequence': 1},
                                        {'value': '3', 'name': '3',
                                            'sequence': 2},
                                        ],
                                    },
                                ],
                            'mandatory': True,
                            },
                        {
                            'id': coverage_b.id,
                            'name': 'Beta Coverage',
                            'code': 'BET',
                            'description': '',
                            'extra_data': [],
                            'mandatory': True,
                            },
                        ],
                    'packages': [
                        {
                            'id': package_a.id,
                            'code': 'package_a',
                            'name': 'Package A',
                            'coverages': [
                                {
                                    'id': coverage_a.id,
                                    'code': 'ALP',
                                    'package_extra_data': {
                                        'option_3': '2',
                                        },
                                    },
                                {
                                    'id': coverage_b.id,
                                    'code': 'BET',
                                    'package_extra_data': {},
                                    },
                                ],
                            'extra_data': {
                                'contract_1': '16.10',
                                },
                            },
                        {
                            'id': package_b.id,
                            'code': 'package_b',
                            'name': 'Package B',
                            'coverages': [
                                {
                                    'id': coverage_a.id,
                                    'code': 'ALP',
                                    'package_extra_data': {
                                        'option_3': '1',
                                        },
                                    },
                                ],
                            'extra_data': {},
                            },
                        ],
                    'subscriber': {
                        'model': 'party',
                        'required': ['name', 'first_name', 'birth_date',
                            'email', 'addresses'],
                        'fields': ['name', 'first_name', 'birth_date',
                            'email', 'phone_number', 'is_person', 'addresses'],
                        },
                    },
                ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
