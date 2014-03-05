import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def depending_modules(cls):
        return ['clause_life', 'loan']

    @classmethod
    def get_models(cls):
        return {
            'ClauseRule': 'clause.rule',
            }

    @classmethod
    def get_module_name(cls):
        return 'contract_loan_clause'

    @classmethod
    def get_test_cases_to_run(cls):
        return ['fiscal_year_test_case', 'extra_premium_kind_test_case',
            'configure_accounting_test_case']

    @test_framework.prepare_test(
        'loan.test0030_LoanCoverageCreation',
        'clause_life.test0001_testBeneficiaryClauseCreation')
    def test0001_addBeneficiaryClauseToProduct(self):
        death_coverage, = self.OptionDescription.search([
                ('code', '=', 'DH')])

        death_clause_rule = self.ClauseRule()
        death_clause_rule.start_date = death_coverage.start_date
        death_clause_rule.clauses = self.Clause.search([
                ('code', '=', 'test_beneficiary_clause')])
        death_coverage.clause_rules = [death_clause_rule]
        death_coverage.save()

    @test_framework.prepare_test(
        'contract_loan_clause.test0001_addBeneficiaryClauseToProduct',
        'loan.test0040_LoanContractSubscription',
        )
    def test0005_checkContractBeneficiaryClauseCreation(self):
        contract, = self.Contract.search([
                ('start_date', '=', datetime.date(2014, 2, 25)),
                ('subscriber.name', '=', 'DOE'),
                ('offered.code', '=', 'LOAN'),
                ])
        covered_element, = contract.covered_elements
        for covered_data in covered_element.covered_data:
            if covered_data.option.offered.code == 'DH':
                break
        self.assertEqual(covered_data.option.offered.code, 'DH')
        self.assertEqual(len(covered_data.beneficiary_clauses), 1)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
