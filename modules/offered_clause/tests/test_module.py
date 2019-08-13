# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    module = 'offered_clause'

    @classmethod
    def fetch_models_for(cls):
        return ['offered']

    @test_framework.prepare_test(
        'offered.test0030_testProductCoverageRelation',
        )
    def test0020_addClausesToProduct(self):
        pool = Pool()
        Product = pool.get('offered.product')
        Clause = pool.get('clause')

        product_a, = Product.search([('code', '=', 'AAA')])

        clause_1 = Clause()
        clause_1.code = 'clause_1'
        clause_1.name = 'Clause 1'
        clause_1.content = 'Clause 1 contents'
        clause_1.customizable = False
        clause_1.save()

        clause_2 = Clause()
        clause_2.code = 'clause_2'
        clause_2.name = 'Clause 2'
        clause_2.content = 'Clause 2 contents (customizable <HERE>)'
        clause_2.customizable = True
        clause_2.save()

        clause_3 = Clause()
        clause_3.code = 'clause_3'
        clause_3.name = 'Clause 3'
        clause_3.content = 'Clause 3 contents'
        clause_3.customizable = False
        clause_3.save()

        product_a.clauses = [clause_1, clause_2]
        product_a.save()

    @test_framework.prepare_test(
        'offered_clause.test0020_addClausesToProduct',
        )
    def test0070_productDescription(self):
        pool = Pool()
        Clause = pool.get('clause')

        clause_1, = Clause.search([('code', '=', 'clause_1')])
        clause_2, = Clause.search([('code', '=', 'clause_2')])

        self.max_diff = None
        self.assertEqual(
            self.APIProduct.describe_products({}, {'_debug_server': True}
                )[0]['clauses'],
            [
                {
                    'code': 'clause_1',
                    'content': 'Clause 1 contents',
                    'customizable': False,
                    'id': clause_1.id,
                    'name': 'Clause 1',
                    },
                {
                    'code': 'clause_2',
                    'content': 'Clause 2 contents (customizable <HERE>)',
                    'customizable': True,
                    'id': clause_2.id,
                    'name': 'Clause 2',
                    },
                ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
