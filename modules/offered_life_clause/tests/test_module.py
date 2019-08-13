# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

import trytond.tests.test_tryton
from trytond.pool import Pool

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    module = 'offered_life_clause'

    @classmethod
    def fetch_models_for(cls):
        return ['offered_clause']

    @test_framework.prepare_test(
        'offered_clause.test0020_addClausesToProduct',
        )
    def test0020_addBeneficiaryClauses(self):
        pool = Pool()
        Coverage = pool.get('offered.option.description')
        Clause = pool.get('clause')

        coverage_a, = Coverage.search([('code', '=', 'ALP')])

        clause_benef_1 = Clause()
        clause_benef_1.code = 'clause_benef_1'
        clause_benef_1.name = 'Clause 1'
        clause_benef_1.content = 'Clause 1 contents'
        clause_benef_1.customizable = False
        clause_benef_1.kind = 'beneficiary'
        clause_benef_1.save()

        clause_benef_2 = Clause()
        clause_benef_2.code = 'clause_benef_2'
        clause_benef_2.name = 'Clause 2'
        clause_benef_2.content = 'Clause 2 contents (customizable <HERE>)'
        clause_benef_2.customizable = True
        clause_benef_2.kind = 'beneficiary'
        clause_benef_2.save()

        clause_benef_3 = Clause()
        clause_benef_3.code = 'clause_benef_3'
        clause_benef_3.name = 'Clause 3'
        clause_benef_3.content = 'Clause 3 contents'
        clause_benef_3.customizable = False
        clause_benef_3.kind = 'beneficiary'
        clause_benef_3.save()

        coverage_a.beneficiaries_clauses = [clause_benef_1, clause_benef_2]
        coverage_a.default_beneficiary_clause = clause_benef_2
        coverage_a.save()

    @test_framework.prepare_test(
        'offered_life_clause.test0020_addBeneficiaryClauses',
        )
    def test0070_productDescription(self):
        pool = Pool()
        Clause = pool.get('clause')

        clause_1, = Clause.search([('code', '=', 'clause_benef_1')])
        clause_2, = Clause.search([('code', '=', 'clause_benef_2')])

        self.max_diff = None
        self.assertEqual(
            self.APIProduct.describe_products({}, {'_debug_server': True}
                )[0]['coverages'][-1]['beneficiaries_clauses'],
            [
                {
                    'code': 'clause_benef_1',
                    'content': 'Clause 1 contents',
                    'customizable': False,
                    'id': clause_1.id,
                    'name': 'Clause 1',
                    'default': False,
                    },
                {
                    'code': 'clause_benef_2',
                    'content': 'Clause 2 contents (customizable <HERE>)',
                    'customizable': True,
                    'id': clause_2.id,
                    'name': 'Clause 2',
                    'default': True,
                    },
                ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
