# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import unittest
import datetime
import doctest
from trytond.tests.test_tryton import doctest_teardown

import trytond.tests.test_tryton

from trytond.pool import Pool
from trytond.modules.coog_core import test_framework, utils
from trytond.exceptions import UserError


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_insurance_document_request'

    @classmethod
    def fetch_models_for(cls):
        return ['offered_insurance', 'contract_insurance',
            'contract']

    @classmethod
    def get_models(cls):
        return {
            'Attachment': 'ir.attachment',
            'DocumentDesc': 'document.description',
            'DocumentRule': 'document.rule',
            'RuleContext': 'rule_engine.context',
            'RuleEngine': 'rule_engine',
            'RuleToDocDescRelation': 'document.rule-document.description',
            'DocumentRequestLine': 'document.request.line',
            }

    def test0001_CreateDocumentDescs(self):
        pool = Pool()
        DocumentDesc = pool.get('document.description')
        ExtraData = pool.get('extra_data')
        Template = pool.get('report.template')
        Lang = pool.get('ir.lang')
        Model = pool.get('ir.model')

        lang_en, = Lang.search([('code', '=', 'en')])
        document_request_line_model, = Model.search(
            [('model', '=', 'document.request.line')])

        document_data_1 = ExtraData()
        document_data_1.name = 'document_data_1'
        document_data_1.string = 'Document Data'
        document_data_1.type_ = 'integer'
        document_data_1.kind = 'document_request'
        document_data_1.save()

        document_data_2 = ExtraData()
        document_data_2.name = 'document_data_2'
        document_data_2.string = 'Document Data'
        document_data_2.type_ = 'integer'
        document_data_2.kind = 'document_request'
        document_data_2.save()

        document_desc_1 = DocumentDesc(name='Document 1',
            code='document_desc_1')
        document_desc_1.extra_data_def = [document_data_1, document_data_2]
        document_desc_1.save()

        document_desc_2 = DocumentDesc(name='Document 2',
            code='document_desc_2')
        document_desc_2.save()

        document_desc_3 = DocumentDesc(name='Document 3',
            code='document_desc_3')
        document_desc_3.save()

        document_desc_4 = DocumentDesc(name='Document 4',
            code='document_desc_4')
        document_desc_4.save()

        template_1 = Template()
        template_1.name = 'Test Template 1'
        template_1.code = 'test_template_1'
        template_1.input_kind = 'flat_document'
        template_1.process_method = 'flat_document'
        template_1.document_desc = document_desc_1
        template_1.on_model = document_request_line_model
        template_1.format_for_internal_edm = 'original'
        template_1.versions = [{
                'language': lang_en,
                'start_date': utils.today(),
                'name': 'Test Template 1',
                'data': b'test template 1',
                }]
        template_1.save()

        template_2 = Template()
        template_2.name = 'Test Template 2'
        template_2.code = 'test_template_2'
        template_2.input_kind = 'flat_document'
        template_2.process_method = 'flat_document'
        template_2.document_desc = document_desc_2
        template_2.on_model = document_request_line_model
        template_2.format_for_internal_edm = 'original'
        template_2.versions = [{
                'language': lang_en,
                'start_date': utils.today(),
                'name': 'Test Template 2',
                'data': b'test template 2',
                }]
        template_2.save()

        document_desc_1.template = template_1
        document_desc_1.save()
        document_desc_2.template = template_2
        document_desc_2.save()

    @test_framework.prepare_test(
        'contract_insurance_document_request.test0001_CreateDocumentDescs',
        'offered_insurance.test0010Coverage_creation',
        'contract.test0005_PrepareProductForSubscription',
        'contract.test0002_testCountryCreation',
        )
    def test0002_PrepareProductForSubscription(self):
        pool = Pool()
        Product = pool.get('offered.product')
        Coverage = pool.get('offered.option.description')
        DocumentDesc = pool.get('document.description')
        DocumentRule = pool.get('document.rule')
        DocumentRuleLine = pool.get('document.rule-document.description')

        product_a, = Product.search([('code', '=', 'AAA')])
        document_desc_1, = DocumentDesc.search(
            [('code', '=', 'document_desc_1')])
        document_desc_2, = DocumentDesc.search(
            [('code', '=', 'document_desc_2')])
        document_desc_3, = DocumentDesc.search(
            [('code', '=', 'document_desc_3')])
        document_desc_4, = DocumentDesc.search(
            [('code', '=', 'document_desc_4')])

        product_a.document_rules = [
            DocumentRule(
                documents=[
                    DocumentRuleLine(
                        document=document_desc_1, blocking=True),
                    DocumentRuleLine(
                        document=document_desc_2, blocking=False),
                    DocumentRuleLine(
                        document=document_desc_3, blocking=True),
                    ],
                ),
            ]
        product_a.save()

        coverage_a, = Coverage.search([('code', '=', 'ALP')])
        coverage_a.document_rules = [
            DocumentRule(
                documents=[
                    DocumentRuleLine(
                        document=document_desc_4, blocking=True),
                    ],
                ),
            ]
        coverage_a.save()

    @test_framework.prepare_test('contract.test0010_testContractCreation')
    def test0010_init_document_request(self):
        # Add document rule to product
        product, = self.Product.search([('code', '=', 'AAA')])
        document_desc1 = self.DocumentDesc(name='Document 1', code='document1')
        document_desc1.save()
        document_desc2 = self.DocumentDesc(name='Document 2', code='document2')
        document_desc2.save()
        document_desc3 = self.DocumentDesc(name='Document 3', code='document3')
        document_desc3.save()
        rule_engine = self.RuleEngine()
        rule_engine.name = 'Document Rule'
        rule_engine.short_name = 'doc_rule'
        rule_engine.algorithm = "return {'document3': {}, 'document2': {}}"
        rule_engine.status = 'validated'
        rule_engine.context, = self.RuleContext.search([], limit=1)
        rule_engine.type_ = 'doc_request'
        rule_engine.save()
        rule = self.DocumentRule()
        rule.documents = [self.RuleToDocDescRelation(
                document=document_desc1),
            self.RuleToDocDescRelation(document=document_desc2,
                blocking=True)]
        rule.product = product
        rule.rule = rule_engine
        rule.save()

        contract, = self.Contract.search([])
        contract.status = 'quote'
        contract.init_subscription_document_request()
        self.assertEqual(set([(d.document_desc.code, d.blocking)
                    for d in contract.document_request_lines]),
            set([('document1', False), ('document2', True),
                ('document3', False)]))
        self.assertRaises(UserError, contract.check_required_documents)

        doc2_request_line, = [x for x in contract.document_request_lines if
            x.document_desc == document_desc2]
        doc2_request_line.received = True
        self.assertRaises(UserError, contract.check_required_documents)
        contract.check_required_documents(only_blocking=True)

    @test_framework.prepare_test(
        'contract_insurance_document_request.'
        'test0002_PrepareProductForSubscription',
        )
    def test0040_TestContractDocumentRequest(self):
        pool = Pool()
        Contract = pool.get('contract')
        ContractAPI = pool.get('api.contract')

        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Father',
                    'birth_date': '1980-01-20',
                    'gender': 'male',
                    'addresses': [
                        {
                            'street': 'Somewhere along the street',
                            'zip': '75002',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        ],
                    },
                {
                    'ref': '2',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Buenaventura',
                    'birth_date': '1988-01-20',
                    'gender': 'male',
                    'addresses': [
                        {
                            'street': 'Somewhere along the street',
                            'zip': '75002',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        ],
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'coverages': [
                        {
                            'coverage': {'code': 'DEL'},
                            },
                        ],
                    'covereds': [
                        {
                            'item_descriptor': {'code': 'person'},
                            'party': {'ref': '1'},
                            'coverages': [
                                {'coverage':
                                    {'code': x}} for x in ('ALP', 'BET')
                                ]
                            },
                        {
                            'item_descriptor': {'code': 'person'},
                            'party': {'ref': '2'},
                            'coverages': [
                                {'coverage':
                                    {'code': x}} for x in ('ALP', 'BET')
                                ]
                            },
                        ]
                    },
                ],
            'options': {
                'activate': True,
                },
            }

        # Must fail, there are blocking document requests
        data_dict = copy.deepcopy(data_ref)
        error = ContractAPI.subscribe_contracts(data_dict, {})

        # Ideally, we should have a more reliant check
        self.assertEqual(error.data['message'],
            'Some required documents are missing.')

        del data_ref['options']

        data_dict = copy.deepcopy(data_ref)
        contract = Contract(
            ContractAPI.subscribe_contracts(
                data_dict, {'_debug_server': True})['contracts'][0]['id'])

        contract.init_subscription_document_request()
        covered_element_0 = contract.covered_elements[0]
        covered_element_1 = contract.covered_elements[1]

        documents = {
            (x.document_desc.code, x.for_object):
            x for x in contract.document_request_lines}

        self.assertEqual(len(contract.document_request_lines), 5)

        self.assertEqual(
            documents[('document_desc_1', contract)].blocking, True)
        self.assertEqual(
            documents[('document_desc_2', contract)].blocking, False)
        self.assertEqual(
            documents[('document_desc_3', contract)].blocking, True)

        self.assertEqual(
            documents[('document_desc_1', contract)].reception_date, None)
        self.assertEqual(
            documents[('document_desc_2', contract)].reception_date,
            utils.today())
        self.assertEqual(
            documents[('document_desc_3', contract)].reception_date, None)

        self.assertEqual(
            documents[('document_desc_1', contract)].received, False)
        self.assertEqual(
            documents[('document_desc_2', contract)].received, True)
        self.assertEqual(
            documents[('document_desc_3', contract)].received, False)
        self.assertEqual(
            documents[('document_desc_4', covered_element_0)].received, False)
        self.assertEqual(
            documents[('document_desc_4', covered_element_1)].received, False)

        self.assertEqual(
            documents[('document_desc_1', contract)].contract, contract)
        self.assertEqual(
            documents[('document_desc_2', contract)].contract, contract)
        self.assertEqual(
            documents[('document_desc_3', contract)].contract, contract)
        self.assertEqual(
            documents[('document_desc_4', covered_element_0)].contract,
            contract)
        self.assertEqual(
            documents[('document_desc_4', covered_element_1)].contract,
            contract)

        self.assertEqual(
            documents[('document_desc_1', contract)].data_status, 'waiting')
        self.assertEqual(
            documents[('document_desc_2', contract)].data_status, 'done')
        self.assertEqual(
            documents[('document_desc_3', contract)].data_status, 'done')
        self.assertEqual(
            documents[('document_desc_3', contract)].data_status, 'done')

        self.assertEqual(
            bool(documents[('document_desc_1', contract)].attachment), False)
        self.assertEqual(
            bool(documents[('document_desc_2', contract)].attachment), True)
        self.assertEqual(
            bool(documents[('document_desc_3', contract)].attachment), False)

        self.assertFalse(contract.doc_received)

        documents[('document_desc_1', contract)].extra_data = {
            'document_data_1': 10,
            'document_data_2': 20,
            }
        documents[('document_desc_1', contract)].save()
        documents[('document_desc_1', contract)].confirm_attachment(
            [documents[('document_desc_1', contract)]])

        self.assertEqual(
            documents[('document_desc_1', contract)].reception_date,
            utils.today())
        self.assertEqual(
            documents[('document_desc_1', contract)].data_status, 'done')
        self.assertEqual(
            documents[('document_desc_1', contract)].received, True)
        self.assertEqual(
            bool(documents[('document_desc_1', contract)].attachment), True)
        self.assertFalse(contract.doc_received)

        # remove one , and check update init_subscription_document_request
        # will recreate it

        def test_reinit():
            contract.init_subscription_document_request()
            documents = {
                (x.document_desc.code, x.for_object):
                x for x in contract.document_request_lines}
            self.assertEqual(len(contract.document_request_lines), 5)
            self.assertEqual(
                documents[('document_desc_1', contract)].contract, contract)
            self.assertEqual(
                documents[('document_desc_2', contract)].contract, contract)
            self.assertEqual(
                documents[('document_desc_3', contract)].contract, contract)
            self.assertEqual(
                documents[('document_desc_4', covered_element_0)].contract,
                contract)
            self.assertEqual(
                documents[('document_desc_4', covered_element_1)].contract,
                contract)

        self.DocumentRequestLine.delete([documents[
                ('document_desc_4', covered_element_0)]])
        self.assertEqual(len(contract.document_request_lines), 4)
        test_reinit()

        # manually add one that is not configured, without send_date,
        #  and check update removes it
        document_desc_4, = self.DocumentDesc.search(
            [('code', '=', 'document_desc_4')])
        outer = self.DocumentRequestLine(for_object=str(contract),
            document_desc=document_desc_4, data_status='waiting',
            added_manually=False)
        outer.save()
        self.assertEqual(len(contract.document_request_lines), 6)
        test_reinit()

        # manually add one that is not configured, WITH send_date,
        #  and check update does not remove it
        document_desc_4, = self.DocumentDesc.search(
            [('code', '=', 'document_desc_4')])
        outer = self.DocumentRequestLine(for_object=str(contract),
            document_desc=document_desc_4, data_status='waiting',
            send_date=datetime.date.today(), added_manually=False)
        outer.save()
        self.assertEqual(len(contract.document_request_lines), 6)
        contract.init_subscription_document_request()
        self.assertEqual(len(contract.document_request_lines), 6)

    @test_framework.prepare_test(
        'contract_insurance_document_request.'
        'test0040_TestContractDocumentRequest',
        )
    def test0050_TestContractDocumentRequestManual(self):
        contract = self.Contract.search([])[0]
        self.assertEqual(len(contract.document_request_lines), 5)

        document_desc_6 = self.DocumentDesc(name='Document 6', code='document6')
        document_desc_6.save()

        # we add a document with a description not requested
        outer = self.DocumentRequestLine(for_object=str(contract),
            document_desc=document_desc_6, data_status='waiting',
            added_manually=False)
        outer.save()
        self.assertEqual(len(contract.document_request_lines), 6)
        contract.init_subscription_document_request()

        # the document is deleted
        self.assertEqual(len(contract.document_request_lines), 5)

        # we MANUALLY add a document with a description not requested
        outer = self.DocumentRequestLine(for_object=str(contract),
            document_desc=document_desc_6, data_status='waiting',
            added_manually=True)
        outer.save()

        self.assertEqual(len(contract.document_request_lines), 6)
        contract.init_subscription_document_request()

        # the document is not deleted
        self.assertEqual(len(contract.document_request_lines), 6)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_document_api.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
