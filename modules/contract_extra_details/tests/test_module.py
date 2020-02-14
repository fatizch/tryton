import datetime
from decimal import Decimal
import unittest

from trytond.pool import Pool
from trytond.transaction import Transaction

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'contract_extra_details'

    @classmethod
    def fetch_models_for(cls):
        return ['contract']

    @test_framework.prepare_test(
        'offered.test0010_testProductCreation',
        )
    def test0010_create_product_extra_details_rule(self):
        pool = Pool()
        Context = pool.get('rule_engine.context')
        Details = pool.get('offered.product.extra_details_rule')
        Product = pool.get('offered.product')
        Rule = pool.get('rule_engine')
        product, = Product.search([('code', '=', 'AAA')])

        ct = Context(1)

        rule = Rule()
        rule.context = ct
        rule.name = 'Test Details Rule'
        rule.short_name = 'test_details_rule'
        rule.type_ = 'contract_extra_detail'
        rule.algorithm = '\n'.join([
                'if date_de_calcul().year == 2077:',
                '    return {\'2077\': 2.1, \'2078\': 2.2}',
                'return {\'2019\': 1.1, \'2020\': 1.2}',
                ])
        rule.status = 'validated'
        rule.save()

        details = Details()
        details.product = product.id
        details.rule = rule.id
        details.save()

    @test_framework.prepare_test(
        'contract_extra_details.test0010_create_product_extra_details_rule',
        'contract.test0010_testContractCreation'
        )
    def test0020_contract_extra_details(self):
        pool = Pool()
        Product = pool.get('offered.product')
        Contract = pool.get('contract')
        ExtraData = pool.get('contract.extra_data')
        product, = Product.search([
                ('code', '=', 'AAA'),
                ])
        start_date = product.start_date + datetime.timedelta(weeks=4)
        contract = Contract(
            product=product.id,
            company=product.company.id,
            start_date=start_date,
            appliable_conditions_date=start_date,
            extra_datas=[ExtraData()]
            )
        contract.save()

        self.assertEqual(contract.current_extra_details, {
                '2019': Decimal('1.1'),
                '2020': Decimal('1.2'),
                })

        contract.activate_contract()

        self.assertEqual(contract.extra_datas[-1].extra_details, {
                '2019': Decimal('1.1'),
                '2020': Decimal('1.2'),
                })

        with Transaction().set_context(
                client_defined_date=datetime.date(2077, 1, 1)):
            contract.calculate()
            self.assertEqual(contract.extra_datas[-1].extra_details, {
                    '2077': Decimal('2.1'),
                    '2078': Decimal('2.2'),
                    })


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
