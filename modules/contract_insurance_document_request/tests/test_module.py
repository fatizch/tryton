# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.exceptions import UserError


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_insurance_document_request'

    @classmethod
    def fetch_models_for(cls):
        return ['contract']

    @classmethod
    def get_models(cls):
        return {
            'Attachment': 'ir.attachment',
            'DocumentDesc': 'document.description',
            'DocumentRule': 'document.rule',
            'RuleContext': 'rule_engine.context',
            'RuleEngine': 'rule_engine',
            'RuleToDocDescRelation': 'document.rule-document.description',
            }

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


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite