#-*- coding:utf-8 -*-
from datetime import date
from decimal import Decimal
import unittest

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'loan'

    @classmethod
    def depending_modules(cls):
        return ['offered_insurance', 'contract_insurance',
            'billing_individual', 'contract_insurance_process',
            'contract_life_process']

    @classmethod
    def get_test_cases_to_run(cls):
        return ['fiscal_year_test_case']

    @classmethod
    def get_models(cls):
        return {
            'Loan': 'loan',
            'Currency': 'currency.currency',
            'Date': 'ir.date',
            'Account': 'account.account',
            'AccountKind': 'account.account.type',
            'Sequence': 'ir.sequence',
            'SequenceType': 'ir.sequence.type',
            'ItemDescription': 'offered.item.description',
            'ContractProcessLauncher': 'contract.subscribe',
            'DistNetwork': 'distribution.network',
            'CommercialProduct': 'distribution.commercial_product',
            'OfferedPaymentMethod': 'offered.product-billing.payment.method',
            }

    def test0010loan_basic_data(self):
        currency, = self.Currency.create([{
                    'name': 'Euro',
                    'code': 'EUR',
                    'symbol': u'€',
                    }])

    def assert_payment(self, loan, at_date, number, begin_balance, amount,
            principal, interest, end_balance):
        payment = loan.get_payment(at_date)
        self.assert_(payment)
        self.assert_(payment.number == number)
        self.assert_(loan.currency.is_zero(
                payment.begin_balance - begin_balance))
        self.assert_(loan.currency.is_zero(payment.amount - amount))
        self.assert_(loan.currency.is_zero(payment.principal - principal))
        self.assert_(loan.currency.is_zero(payment.interest - interest))
        self.assert_(loan.currency.is_zero(
                payment.end_balance - end_balance))

    @test_framework.prepare_test('loan.test0010loan_basic_data')
    def test0020loan_creation(self):
        '''
        Test basic loan
        '''
        currency, = self.Currency.search([], limit=1)
        loan = self.Loan()
        loan.kind = 'fixed_rate'
        loan.rate = Decimal('0.04')
        loan.funds_release_date = date(2012, 7, 1)
        loan.first_payment_date = date(2012, 7, 15)
        loan.payment_frequency = 'month'
        loan.amount = 100000
        loan.number_of_payments = 180
        loan.currency = currency
        loan.payment_amount = loan.on_change_with_payment_amount()
        self.assert_(
            currency.is_zero(loan.payment_amount - Decimal(739.69)))
        loan.defferal = 'partially'
        loan.defferal_duration = 12
        loan.calculate_increments()
        self.assert_(len(loan.increments) == 2)
        increment_1 = loan.get_increment(loan.first_payment_date)
        self.assert_(increment_1)
        self.assert_(increment_1.defferal == 'partially')
        self.assert_(increment_1.number_of_payments == 12)
        self.assert_(
            currency.is_zero(increment_1.payment_amount - Decimal(333.33)))
        increment_2 = loan.get_increment(date(2013, 7, 15))
        self.assert_(increment_2)
        self.assert_(
            currency.is_zero(increment_2.payment_amount - Decimal(778.35)))

        loan.early_payments = []
        loan.payments = loan.calculate_payments()
        self.assert_(len(loan.payments) == loan.number_of_payments)

        self.assert_payment(loan, date(2013, 7, 14), 12, loan.amount,
            Decimal(333.33), Decimal(0.0), Decimal(333.33), loan.amount)

        self.assert_payment(loan, date(2013, 7, 15), 13, loan.amount,
            Decimal(778.35), Decimal(445.02), Decimal(333.33),
            Decimal(99554.98))

        self.assert_payment(loan, date(2021, 1, 15), 103,
            Decimal(53381.95), Decimal(778.35), Decimal(600.41),
            Decimal(177.94), Decimal(52781.54))

        self.assert_payment(loan, date(2027, 6, 15), 180,
            Decimal(774.70), Decimal(777.28), Decimal(774.70),
            Decimal(2.58), Decimal(0.0))

        loan.save()

    @test_framework.prepare_test('company_cog.test0001_testCompanyCreation')
    def test0025_CreateAccountKind(self):
        product_account_kind = self.AccountKind()
        product_account_kind.name = 'Product Account Kind'
        product_account_kind.company = self.Company.search([
                ('party.name', '=', 'Coop')])[0]
        product_account_kind.save()

    @test_framework.prepare_test('loan.test0025_CreateAccountKind')
    def test0026_CreateAccounts(self):
        product_account_kind = self.AccountKind.search([
                ('name', '=', 'Product Account Kind')])[0]
        company, = self.Company.search([('party.name', '=', 'Coop')])
        loan_account = self.Account()
        loan_account.name = 'Loan Product Account'
        loan_account.code = loan_account.name
        loan_account.kind = 'revenue'
        loan_account.type = product_account_kind
        loan_account.company = company
        loan_account.save()
        death_account = self.Account()
        death_account.name = 'Death Option Account'
        death_account.code = death_account.name
        death_account.kind = 'revenue'
        death_account.type = product_account_kind
        death_account.company = company
        death_account.save()
        disability_account = self.Account()
        disability_account.name = 'Disability Option Account'
        disability_account.code = disability_account.name
        disability_account.kind = 'revenue'
        disability_account.type = product_account_kind
        disability_account.company = company
        disability_account.save()

    def test0028_CreatPersonItemDesc(self):
        item_desc = self.ItemDescription()
        item_desc.code = 'person_item_desc'
        item_desc.name = 'Person Item Description'
        item_desc.kind = 'person'
        item_desc.save()

    @test_framework.prepare_test('loan.test0026_CreateAccounts',
        'loan.test0028_CreatPersonItemDesc',
        'billing_individual.test0016_PaymentMethod')
    def test0030_LoanCoverageCreation(self):
        today = self.Date.today()
        company, = self.Company.search([('party.name', '=', 'Coop')])
        item_desc, = self.ItemDescription.search([
                ('code', '=', 'person_item_desc')])
        death = self.OptionDescription()
        death.name = 'Death'
        death.code = 'DH'
        death.family = 'loan'
        death.start_date = today
        death.company = company
        death.account_for_billing = self.Account.search([
                ('name', '=', 'Death Option Account')])[0]
        death.item_desc = item_desc
        death.kind = 'insurance'
        death.save()
        disability = self.OptionDescription()
        disability.name = 'Disability'
        disability.code = 'DY'
        disability.family = 'loan'
        disability.start_date = today
        disability.company = company
        disability.account_for_billing = self.Account.search([
                ('name', '=', 'Disability Option Account')])[0]
        disability.item_desc = item_desc
        disability.kind = 'insurance'
        disability.save()
        loan_contract_sequence_code = self.SequenceType()
        loan_contract_sequence_code.name = 'Product sequence'
        loan_contract_sequence_code.code = 'product_sequence'
        loan_contract_sequence_code.save()
        loan_contract_sequence = self.Sequence()
        loan_contract_sequence.name = 'Contract sequence'
        loan_contract_sequence.code = loan_contract_sequence_code.code
        loan_contract_sequence.save()
        loan_payment_method = self.OfferedPaymentMethod()
        loan_payment_method.order = 1
        loan_payment_method.payment_method = self.PaymentMethod.search([
                ('code', '=', 'test_payment_method')])[0]
        loan = self.Product()
        loan.name = 'Loan Product'
        loan.code = 'LOAN'
        loan.start_date = today
        loan.company = company
        loan.kind = 'insurance'
        loan.contract_generator = loan_contract_sequence
        loan.account_for_billing = self.Account.search([
                ('name', '=', 'Loan Product Account')])[0]
        loan.coverages = [death, disability]
        loan.item_descriptors = [item_desc]
        loan.payment_methods = [loan_payment_method]
        loan.save()

    def test0031_LoanDistNetwork(self):
        dist_network = self.DistNetwork()
        dist_network.name = 'Test Dist Network'
        dist_network.left = 1
        dist_network.right = 2
        dist_network.save()

    @test_framework.prepare_test('loan.test0030_LoanCoverageCreation',
        'loan.test0031_LoanDistNetwork')
    def test0032_LoanCommercialProduct(self):
        commercial_product = self.CommercialProduct()
        commercial_product.name = 'Loan Commercial Product'
        commercial_product.code = 'loan_commercial_product'
        commercial_product.start_date = self.Date.today()
        commercial_product.description = 'Test Description'
        commercial_product.product = self.Product.search([
                ('code', '=', 'LOAN')])[0]
        commercial_product.dist_networks = self.DistNetwork.search([])
        commercial_product.save()

    @test_framework.prepare_test(
        'loan.test0020loan_creation',
        'contract_insurance.test0001_testPersonCreation',
        'loan.test0032_LoanCommercialProduct',
        'billing_individual.test0010_payment_term_first_following_month')
    def test0040_LoanContractSubscription(self):
        company, = self.Company.search([('party.name', '=', 'Coop')])
        commercial_product = self.CommercialProduct.search([])
        self.assertEqual(len(commercial_product), 1)
        commercial_product = commercial_product[0]
        self.assertEqual(commercial_product.code, 'loan_commercial_product')
        today = self.Date.today()

        contract = self.Contract()
        contract.init_from_offered(commercial_product.product, today)
        contract.company = company
        contract.save()
        contract.subscriber, = self.Party.search([('name', '=', 'DOE')])
        contract.save()
        contract.check_product_not_null()
        contract.check_subscriber_not_null()
        contract.check_start_date_valid()
        contract.check_product_eligibility()
        self.assertEqual(len(contract.covered_elements), 0)
        contract.set_subscriber_as_covered_element()
        self.assertEqual(len(contract.covered_elements), 1)
        contract.save()
        contract.loans = self.Loan.search([])
        self.assertEqual(len(contract.loans), 1)
        contract.set_contract_end_date_from_loans()
        self.assertEqual(contract.end_date, date(2027, 7, 14))
        contract.save()
        contract.init_options()
        contract.init_covered_elements()
        contract.init_extra_data()
        contract.save()
        self.assertEqual(len(contract.covered_elements[0].covered_data), 2)
        contract.check_options_eligibility()
        contract.check_at_least_one_covered()
        contract.check_sub_elem_eligibility()
        contract.check_option_dates()
        contract.update_coverage_amounts_if_needed()
        contract.check_covered_amounts()
        contract.update_agreements()
        contract.calculate_prices()
        contract.save()
        self.assertEqual(contract.billing_datas[0].payment_method,
            self.PaymentMethod.search([
                    ('code', '=', 'test_payment_method')])[0])
        contract.check_billing_data()
        contract.activate_contract()
        contract.finalize_contract()
        contract.save()
        self.assertEqual(contract.status, 'active')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
