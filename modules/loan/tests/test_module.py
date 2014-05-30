#-*- coding:utf-8 -*-
from datetime import date
from decimal import Decimal
import unittest

from trytond.error import UserError
import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework
from trytond.transaction import Transaction


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
            'contract_insurance_process', 'contract_life_process']

    @classmethod
    def get_test_cases_to_run(cls):
        return []
        return ['fiscal_year_test_case', 'extra_premium_kind_test_case',
            'configure_accounting_test_case']

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
            'ExtraPremiumKind': 'extra_premium.kind',
            'ExtraPremium': 'contract.option.extra_premium',
            'ExtraData': 'extra_data',
            }

    @test_framework.prepare_test(
        'company_cog.test0001_testCompanyCreation')
    def test0010loan_basic_data(self):
        company, = self.Company().search([], limit=1)
        self.Sequence(name='Loan', code='loan', company=company).save()

    # def test0025_CreateAccountKind(self):
    #     company, = self.Company.search([('party.name', '=', 'Coop')])
    #     product_account_kind = self.AccountKind()
    #     product_account_kind.name = 'Product Account Kind'
    #     product_account_kind.company = company
    #     product_account_kind.save()

    # @test_framework.prepare_test('loan.test0025_CreateAccountKind')
    # def test0026_CreateAccounts(self):
    #     product_account_kind, = self.AccountKind.search([
    #             ('name', '=', 'Product Account Kind'),
    #             ])
    #     company, = self.Company.search([('party.name', '=', 'Coop')])
    #     loan_account = self.Account()
    #     loan_account.name = 'Loan Product Account'
    #     loan_account.code = loan_account.name
    #     loan_account.kind = 'revenue'
    #     loan_account.type = product_account_kind
    #     loan_account.company = company
    #     loan_account.save()
    #     death_account = self.Account()
    #     death_account.name = 'Death Option Account'
    #     death_account.code = death_account.name
    #     death_account.kind = 'revenue'
    #     death_account.type = product_account_kind
    #     death_account.company = company
    #     death_account.save()
    #     disability_account = self.Account()
    #     disability_account.name = 'Disability Option Account'
    #     disability_account.code = disability_account.name
    #     disability_account.kind = 'revenue'
    #     disability_account.type = product_account_kind
    #     disability_account.company = company
    #     disability_account.save()

    # def test0028_CreatePersonItemDesc(self):
    #     item_desc = self.ItemDescription()
    #     item_desc.code = 'person_item_desc'
    #     item_desc.name = 'Person Item Description'
    #     item_desc.kind = 'person'
    #     item_desc.save()

    # @test_framework.prepare_test('loan.test0026_CreateAccounts',
    #     'loan.test0028_CreatePersonItemDesc',
    #     'billing_individual.test0016_PaymentMethod')
    # def test0030_LoanCoverageCreation(self):
    #     main_date = date(2014, 1, 1)
    #     company, = self.Company.search([('party.name', '=', 'Coop')])
    #     item_desc, = self.ItemDescription.search([
    #             ('code', '=', 'person_item_desc'),
    #             ])

    #     # Death Coverage
    #     pricing_comp_death = self.PremiumRuleComponent()
    #     pricing_comp_death.config_kind = 'simple'
    #     pricing_comp_death.fixed_amount = 200
    #     pricing_comp_death.kind = 'base'
    #     pricing_comp_death.code = 'Main'
    #     pricing_comp_death.rated_object_kind = 'sub_item'
    #     premium_rule_death = self.Pricing()
    #     premium_rule_death.sub_item_components = [pricing_comp_death]
    #     premium_rule_death.start_date = main_date
    #     death = self.OptionDescription()
    #     death.name = 'Death'
    #     death.code = 'DH'
    #     death.family = 'loan'
    #     death.start_date = main_date
    #     death.company = company
    #     death.account_for_billing, = self.Account.search([
    #             ('name', '=', 'Death Option Account'),
    #             ])
    #     death.item_desc = item_desc
    #     death.kind = 'insurance'
    #     death.premium_rules = [premium_rule_death]
    #     death.save()

    #     # Disability Coverage
    #     pricing_comp_disability = self.PremiumRuleComponent()
    #     pricing_comp_disability.config_kind = 'simple'
    #     pricing_comp_disability.fixed_amount = 50
    #     pricing_comp_disability.kind = 'base'
    #     pricing_comp_disability.code = 'Main'
    #     pricing_comp_disability.rated_object_kind = 'sub_item'
    #     premium_rule_disability = self.Pricing()
    #     premium_rule_disability.sub_item_components = [pricing_comp_disability]
    #     premium_rule_disability.start_date = main_date
    #     disability = self.OptionDescription()
    #     disability.name = 'Disability'
    #     disability.code = 'DY'
    #     disability.family = 'loan'
    #     disability.start_date = main_date
    #     disability.company = company
    #     disability.account_for_billing, = self.Account.search([
    #             ('name', '=', 'Disability Option Account'),
    #             ])
    #     disability.item_desc = item_desc
    #     disability.kind = 'insurance'
    #     disability.premium_rules = [premium_rule_disability]
    #     disability.save()

    #     # Loan Product
    #     loan_contract_sequence_code = self.SequenceType()
    #     loan_contract_sequence_code.name = 'Product sequence'
    #     loan_contract_sequence_code.code = 'product_sequence'
    #     loan_contract_sequence_code.save()
    #     loan_contract_sequence = self.Sequence()
    #     loan_contract_sequence.name = 'Contract sequence'
    #     loan_contract_sequence.code = loan_contract_sequence_code.code
    #     loan_contract_sequence.save()
    #     loan_payment_method = self.OfferedPaymentMethod()
    #     loan_payment_method.order = 1
    #     loan_payment_method.payment_method, = self.PaymentMethod.search([
    #             ('code', '=', 'test_payment_method'),
    #             ])
    #     loan = self.Product()
    #     loan.name = 'Loan Product'
    #     loan.code = 'LOAN'
    #     loan.start_date = main_date
    #     loan.company = company
    #     loan.kind = 'insurance'
    #     loan.contract_generator = loan_contract_sequence
    #     loan.account_for_billing, = self.Account.search([
    #             ('name', '=', 'Loan Product Account'),
    #             ])
    #     loan.coverages = [death, disability]
    #     loan.item_descriptors = [item_desc]
    #     loan.payment_methods = [loan_payment_method]
    #     loan.save()

    # def test0031_LoanDistNetwork(self):
    #     dist_network = self.DistNetwork()
    #     dist_network.name = 'Test Dist Network'
    #     dist_network.left = 1
    #     dist_network.right = 2
    #     dist_network.save()

    # @test_framework.prepare_test('loan.test0030_LoanCoverageCreation',
    #     'loan.test0031_LoanDistNetwork')
    # def test0032_LoanCommercialProduct(self):
    #     commercial_product = self.CommercialProduct()
    #     commercial_product.name = 'Loan Commercial Product'
    #     commercial_product.code = 'loan_commercial_product'
    #     commercial_product.description = 'Test Description'
    #     commercial_product.product, = self.Product.search([
    #             ('code', '=', 'LOAN'),
    #             ])
    #     commercial_product.start_date = commercial_product.product.start_date
    #     commercial_product.dist_networks = self.DistNetwork.search([])
    #     commercial_product.save()

    def assert_payment(self, loan, at_date, number, begin_balance, amount,
            principal, interest, outstanding_balance):
        payment = loan.get_payment(at_date)
        self.assert_(payment)
        self.assert_(payment.number == number)
        self.assert_(payment.begin_balance == begin_balance)
        self.assert_(payment.amount == amount)
        self.assert_(payment.principal == principal)
        self.assert_(payment.interest == interest)
        self.assert_(payment.outstanding_balance == outstanding_balance)

    @test_framework.prepare_test(
        'contract_insurance.test0001_testPersonCreation',
        'loan.test0010loan_basic_data',
        )
    def test0037loan_creation(self):
        '''
        Test basic loan
        '''
        currency, = self.Currency.search([], limit=1)
        company, = self.Company().search([], limit=1)
        loan = self.Loan(
            kind='fixed_rate',
            rate=Decimal('0.04'),
            funds_release_date=date(2012, 7, 1),
            first_payment_date=date(2012, 7, 15),
            payment_frequency='month',
            amount=Decimal(100000),
            number_of_payments=180,
            currency=currency,
            company=company)
        loan.payment_amount = loan.on_change_with_payment_amount()
        loan.parties = self.Party.search([('name', '=', 'DOE')])
        self.assert_(loan.payment_amount == Decimal('739.69'))
        loan.deferal = 'partially'
        loan.deferal_duration = 12
        loan.calculate_increments()
        loan.payments = loan.calculate_payments()
        self.assert_(len(loan.increments) == 2)
        increment_1 = loan.increments[0]
        self.assert_(increment_1)
        self.assert_(increment_1.deferal == 'partially')
        self.assert_(increment_1.number_of_payments == 12)
        self.assert_(increment_1.payment_amount == Decimal('333.33'))
        self.assert_(increment_1.end_date == date(2013, 6, 15))
        increment_2 = loan.increments[-1]
        self.assert_(increment_2)
        self.assert_(increment_2.payment_amount == Decimal('778.35'))
        self.assert_(increment_2.end_date == date(2027, 6, 15))

        self.assert_(len(loan.payments) == loan.number_of_payments + 1)
        self.assert_payment(loan, date(2013, 7, 14), 12, loan.amount,
            Decimal('333.33'), Decimal(0), Decimal('333.33'), loan.amount)
        self.assert_payment(loan, date(2013, 7, 15), 13, loan.amount,
            Decimal('778.35'), Decimal('445.02'), Decimal('333.33'),
            Decimal('99554.98'))
        self.assert_payment(loan, date(2021, 1, 15), 103,
            Decimal('53381.95'), Decimal('778.35'), Decimal('600.41'),
            Decimal('177.94'), Decimal('52781.54'))
        self.assert_payment(loan, date(2027, 6, 15), 180,
            Decimal('774.70'), Decimal('777.28'), Decimal('774.70'),
            Decimal('2.58'), Decimal(0))

        loan.save()
        self.assert_(loan.end_date == date(2027, 6, 15))
        self.assert_(loan.get_outstanding_loan_balance(
                at_date=loan.funds_release_date) == loan.amount)
        self.assert_(loan.get_outstanding_loan_balance(
                at_date=date(2016, 9, 20)) == Decimal('81498.58'))
        self.assert_(loan.get_outstanding_loan_balance(
                at_date=date(2099, 9, 20)) == Decimal(0))

        loan = self.Loan(
            kind='fixed_rate',
            rate=Decimal('0.0752'),
            funds_release_date=date(2014, 3, 5),
            payment_frequency='quarter',
            currency=currency,
            company=company)

        loan.first_payment_date = loan.on_change_with_first_payment_date()
        loan.parties = self.Party.search([('name', '=', 'DOE')])
        self.assert_(loan.first_payment_date == date(2014, 6, 5))
        loan.number_of_payments = 56
        loan.amount = Decimal(134566)
        loan.deferal = 'fully'
        loan.deferal_duration = 8
        loan.payment_amount = loan.on_change_with_payment_amount()
        self.assert_(loan.payment_amount is None)
        loan.calculate_increments()
        loan.payments = loan.calculate_payments()
        self.assert_(len(loan.increments) == 2)
        increment_1 = loan.increments[0]
        self.assert_(increment_1)
        self.assert_(increment_1.deferal == 'fully')
        self.assert_(increment_1.number_of_payments == 8)
        self.assert_(increment_1.start_date == date(2014, 6, 5))
        self.assert_(increment_1.begin_balance == Decimal(134566))
        self.assert_(increment_1.end_date == date(2016, 3, 5))
        increment_2 = loan.increments[-1]
        self.assert_(increment_2)
        self.assert_(increment_2.number_of_payments == 48)
        self.assert_(increment_2.start_date == date(2016, 6, 5))
        self.assert_(increment_2.begin_balance == Decimal('156187.70'))
        self.assert_(increment_2.end_date == date(2028, 3, 5))

        self.assert_payment(loan, date(2014, 12, 5), 3, Decimal('139673.24'),
            Decimal(0), Decimal('-2625.86'), Decimal('2625.86'),
            Decimal('142299.10'))
        self.assert_payment(loan, date(2016, 6, 5), 9, Decimal('156187.70'),
            Decimal('4968.47'), Decimal('2032.14'), Decimal('2936.33'),
            Decimal('154155.56'))
        self.assert_payment(loan, date(2019, 6, 5), 21, Decimal('129115.62'),
            Decimal('4968.47'), Decimal('2541.10'), Decimal('2427.37'),
            Decimal('126574.52'))
        self.assert_payment(loan, date(2027, 12, 5), 55, Decimal('9663.48'),
            Decimal('4968.47'), Decimal('4786.80'), Decimal('181.67'),
            Decimal('4876.68'))
        self.assert_payment(loan, date(2028, 3, 5), 56, Decimal('4876.68'),
            Decimal('4968.36'), Decimal('4876.68'), Decimal('91.68'),
            Decimal('0'))
        loan.save()
        self.assert_(loan.end_date == date(2028, 3, 5))
        self.assert_(loan.get_outstanding_loan_balance(
                at_date=loan.funds_release_date) == loan.amount)
        self.assert_(loan.get_outstanding_loan_balance(
                at_date=date(2026, 10, 20)) == Decimal('27943.50'))
        self.assert_(loan.get_outstanding_loan_balance(
                at_date=date(2099, 9, 20)) == Decimal(0))

        loan = self.Loan(
            kind='balloon',
            rate=Decimal('0.0677'),
            funds_release_date=date(2014, 3, 5),
            payment_frequency='half_year',
            currency=currency,
            company=company)
        loan.first_payment_date = loan.on_change_with_first_payment_date()
        self.assert_(loan.first_payment_date == date(2014, 9, 5))
        loan.number_of_payments = 30
        loan.amount = Decimal(243455)
        loan.deferal = loan.on_change_with_deferal()
        loan.deferal_duration = loan.on_change_with_deferal_duration()
        loan.payment_amount = loan.on_change_with_payment_amount()
        self.assert_(loan.payment_amount is None)
        loan.calculate_increments()
        loan.payments = loan.calculate_payments()
        self.assert_(len(loan.increments) == 2)
        increment_1 = loan.increments[0]
        self.assert_(increment_1)
        self.assert_(increment_1.deferal == 'partially')
        self.assert_(increment_1.number_of_payments == 29)
        self.assert_(increment_1.start_date == date(2014, 9, 5))
        self.assert_(increment_1.begin_balance == loan.amount)
        increment_2 = loan.increments[-1]
        self.assert_(increment_2)
        self.assert_(increment_2.number_of_payments == 1)
        self.assert_(increment_2.start_date == date(2029, 3, 5))
        self.assert_(increment_2.begin_balance == loan.amount)

        self.assert_payment(loan, date(2022, 3, 5), 16, loan.amount,
            Decimal('8240.95'), Decimal(0), Decimal('8240.95'), loan.amount)
        self.assert_payment(loan, date(2029, 3, 5), 30, loan.amount,
            Decimal('251695.95'), loan.amount, Decimal('8240.95'),
            Decimal('0'))

    # @test_framework.prepare_test('loan.test0037loan_creation',
    #     'loan.test0032_LoanCommercialProduct')
    # def test0040_LoanContractSubscription(self):
    #     company, = self.Company.search([('party.name', '=', 'Coop')])
    #     with Transaction().set_context(user=1):
    #         commercial_product = self.CommercialProduct.search([])
    #         self.assertEqual(len(commercial_product), 1)
    #         commercial_product = commercial_product[0]
    #         self.assertEqual(commercial_product.code,
    #             'loan_commercial_product')
    #         contract = self.Contract()
    #         contract.init_from_product(commercial_product.product,
    #             date(2014, 2, 25))
    #         contract.company = company
    #         contract.subscriber, = self.Party.search([('name', '=', 'DOE')])
    #         contract.save()
    #         contract.check_product_not_null()
    #         contract.check_subscriber_not_null()
    #         contract.check_start_date_valid()
    #         contract.check_product_eligibility()
    #         self.assertEqual(len(contract.covered_elements), 0)
    #         contract.set_subscriber_as_covered_element()
    #         self.assertEqual(len(contract.covered_elements), 1)
    #         contract.save()
    #         contract.loans = self.Loan.search([])
    #         self.assertEqual(len(contract.loans), 1)
    #         contract.set_contract_end_date_from_loans()
    #         self.assertEqual(contract.end_date, date(2027, 7, 14))
    #         contract.save()
    #         contract.init_options()
    #         contract.init_covered_elements()
    #         contract.init_extra_data()
    #         contract.save()
    #         self.assertEqual(len(contract.covered_elements[0].options), 2)
    #         contract.check_contract_extra_data()
    #         contract.check_covered_element_extra_data()
    #         contract.check_option_extra_data()
    #         contract.check_options_eligibility()
    #         contract.check_at_least_one_covered()
    #         contract.check_sub_elem_eligibility()
    #         contract.check_option_dates()
    #         contract.update_coverage_amounts_if_needed()
    #         contract.check_covered_amounts()
    #         contract.update_agreements()
    #         contract.calculate_prices()
    #         contract.save()
    #         self.assertEqual(contract.billing_datas[0].payment_method,
    #             self.PaymentMethod.search([
    #                     ('code', '=', 'test_payment_method'),
    #                     ])[0])
    #         contract.check_billing_data()
    #         contract.activate_contract()
    #         contract.finalize_contract()
    #         contract.save()
    #         self.assertEqual(contract.status, 'active')

    # @test_framework.prepare_test('loan.test0040_LoanContractSubscription')
    # def test0041_TestPremiumModification(self):
    #     contract, = self.Contract.search([
    #             ('start_date', '=', date(2014, 2, 25)),
    #             ('subscriber.name', '=', 'DOE'),
    #             ('product.code', '=', 'LOAN'),
    #             ])
    #     self.assertEqual(contract.prices[6].amount, Decimal('200'))
    #     option = contract.covered_elements[0].options[0]

    #     # Create Extra Premium
    #     extra_premium = self.ExtraPremium()
    #     extra_premium.option = option
    #     extra_premium.motive, = self.ExtraPremiumKind.search([
    #             ('code', '=', 'medical_risk'),
    #             ])
    #     extra_premium.start_date = date(2014, 2, 25)
    #     extra_premium.end_date = date(2015, 2, 24)
    #     extra_premium.calculation_kind = 'flat'
    #     extra_premium.flat_amount = 10000
    #     extra_premium.save()

    #     # Check calculation result
    #     contract.calculate_prices()
    #     self.assertEqual(contract.prices[6].amount, Decimal('10200'))
    #     line = contract.prices[6].all_lines[0]
    #     self.assertEqual(line.on_object, option)
    #     self.assertEqual(len(line.all_lines), 1)
    #     self.assertEqual(line.all_lines[0].on_object.__name__, 'loan.share')
    #     self.assertEqual(len(line.all_lines[0].all_lines), 2)
    #     self.assertEqual(line.all_lines[0].all_lines[-1].on_object,
    #         extra_premium.motive)
    #     self.assertEqual(line.all_lines[0].all_lines[-1].amount,
    #         Decimal('10000'))

    #     # Check end of calculation
    #     self.assertEqual(contract.prices[26].amount, Decimal('200'))
    #     self.assertEqual(contract.prices[26].start_date,
    #         date(2015, 2, 25))

    #     # Check rate extra_premium
    #     extra_premium.calculation_kind = 'rate'
    #     extra_premium.rate = Decimal('0.4')
    #     extra_premium.save()
    #     contract.calculate_prices()
    #     self.assertEqual(contract.prices[6].amount, Decimal('280'))

    #     # Check rate extra_premium
    #     extra_premium.calculation_kind = 'capital_per_mil'
    #     extra_premium.capital_per_mil_rate = Decimal('0.005')
    #     extra_premium.save()
    #     contract.calculate_prices()
    #     self.assertEqual(contract.prices[6].amount, Decimal('700'))

    # @test_framework.prepare_test('loan.test0040_LoanContractSubscription')
    # def test0042_TestCheckExtraData(self):
    #     contract, = self.Contract.search([
    #             ('start_date', '=', date(2014, 2, 25)),
    #             ('subscriber.name', '=', 'DOE'),
    #             ('product.code', '=', 'LOAN'),
    #             ])
    #     product = contract.product
    #     covered_element = contract.covered_elements[0]
    #     test_extra_data = self.ExtraData()
    #     test_extra_data.name = 'test_extra_data'
    #     test_extra_data.start_date = product.start_date
    #     test_extra_data.string = 'Test Extra Data'
    #     test_extra_data.type_ = 'selection'
    #     test_extra_data.kind = 'sub_elem'
    #     test_extra_data.selection = 'test_key: test_value'
    #     test_extra_data.save()
    #     product.extra_data_def = [test_extra_data]
    #     product.save()
    #     contract.check_contract_extra_data()
    #     self.assertRaises(UserError,
    #         contract.check_covered_element_extra_data)
    #     covered_element.extra_data = {'test_extra_data': ''}
    #     covered_element.save()
    #     self.assertEqual(False, contract.check_covered_element_extra_data()[0])
    #     covered_element.extra_data['test_extra_data'] = 'foo'
    #     covered_element.save()
    #     self.assertEqual(False, contract.check_covered_element_extra_data()[0])
    #     covered_element.extra_data['test_extra_data'] = 'test_key'
    #     covered_element.save()
    #     contract.check_covered_element_extra_data()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
