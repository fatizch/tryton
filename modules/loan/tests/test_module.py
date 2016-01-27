# -*- coding:utf-8 -*-
from decimal import Decimal
import unittest
import doctest
import datetime

import trytond.tests.test_tryton
from trytond.tests.test_tryton import doctest_setup, doctest_teardown

from trytond.modules.cog_utils import test_framework, coop_date
from trytond.transaction import Transaction


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'loan'

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
            'LoanIncrement': 'loan.increment',
            'Currency': 'currency.currency',
            'Date': 'ir.date',
            'Account': 'account.account',
            'AccountKind': 'account.account.type',
            'Sequence': 'ir.sequence',
            'SequenceType': 'ir.sequence.type',
            'ItemDescription': 'offered.item.description',
            'ContractProcessLauncher': 'contract.subscribe',
            'ExtraPremiumKind': 'extra_premium.kind',
            'ExtraPremium': 'contract.option.extra_premium',
            'ExtraData': 'extra_data',
            'Contract': 'contract',
            'Coverage': 'offered.option.description',
            'LoanShare': 'loan.share',
            'CoveredElement': 'contract.covered_element',
            'Option': 'contract.option',
            'Party': 'party.party',
            'Insurer': 'insurer',
            'InsuredOutstandingLoanBalance':
                'party.display_insured_outstanding_loan_balance',
            'InsuredOutstandingLoanBalanceView':
                'party.display_insured_outstanding_loan_balance.view',
            'InsuredOutstandingLoanBalanceLineView':
                'party.display_insured_outstanding_loan_balance.line_view',
            'InsuredOutstandingLoanBalanceSelectDate':
                'party.display_insured_outstanding_loan_balance.select_date',
            }

    @test_framework.prepare_test(
        'company_cog.test0001_testCompanyCreation')
    def test0010loan_basic_data(self):
        company, = self.Company().search([], limit=1)
        self.Sequence(name='Loan', code='loan', company=company).save()

    def assert_payment(self, loan, at_date, number=None,
            begin_balance=None, amount=None, principal=None, interest=None,
            outstanding_balance=None):
        payment = loan.get_payment(at_date)
        self.assert_(payment)
        if number:
            self.assertEqual(payment.number, number)
        if begin_balance:
            self.assertEqual(payment.begin_balance, Decimal(begin_balance))
        if amount:
            self.assertEqual(payment.amount, Decimal(amount))
        if principal:
            self.assertEqual(payment.principal, Decimal(principal))
        if interest:
            self.assertEqual(payment.interest, Decimal(interest))
        if outstanding_balance:
            self.assertEqual(payment.outstanding_balance,
                Decimal(outstanding_balance))

    @test_framework.prepare_test(
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
            funds_release_date=datetime.date(2012, 7, 1),
            first_payment_date=datetime.date(2012, 7, 15),
            payment_frequency='month',
            amount=Decimal(100000),
            duration=180,
            duration_unit='month',
            currency=currency,
            company=company)
        loan.deferral = 'partially'
        loan.deferral_duration = 12
        loan.calculate()
        loan.save()
        self.assertEqual(loan.get_payment_amount(loan.first_payment_date),
            Decimal('333.33'))
        self.assertEqual(loan.get_payment_amount(datetime.date(2013, 7, 15)),
            Decimal('778.35'))
        self.assertEqual(len(loan.increments), 2)
        increment_1 = loan.increments[0]
        self.assert_(increment_1)
        self.assertEqual(increment_1.deferral, 'partially')
        self.assertEqual(increment_1.number_of_payments, 12)
        self.assertEqual(increment_1.payment_amount, Decimal('333.33'))
        increment_2 = loan.increments[-1]
        self.assert_(increment_2)
        self.assertEqual(increment_2.payment_amount, Decimal('778.35'))

        self.assertEqual(len(loan.payments), loan.duration + 1)
        self.assertEqual(loan.get_payment(datetime.date(2012, 6, 30)), None)
        self.assert_payment(loan, datetime.date(2013, 7, 14), 12, loan.amount,
            Decimal('333.33'), Decimal(0), Decimal('333.33'), loan.amount)
        self.assert_payment(loan, datetime.date(2013, 7, 15), 13, loan.amount,
            Decimal('778.35'), Decimal('445.02'), Decimal('333.33'),
            Decimal('99554.98'))
        self.assert_payment(loan, datetime.date(2021, 1, 15), 103,
            Decimal('53381.95'), Decimal('778.35'), Decimal('600.41'),
            Decimal('177.94'), Decimal('52781.54'))
        self.assert_payment(loan, datetime.date(2027, 6, 15), 180,
            Decimal('774.70'), Decimal('777.28'), Decimal('774.70'),
            Decimal('2.58'), Decimal(0))

        loan.save()
        self.assertEqual(loan.increments[0].end_date,
            datetime.date(2013, 6, 15))
        self.assertEqual(loan.increments[-1].end_date,
            datetime.date(2027, 6, 15))
        self.assertEqual(loan.end_date, datetime.date(2027, 6, 15))
        self.assertEqual(loan.get_outstanding_loan_balance(
                at_date=loan.funds_release_date), loan.amount)
        self.assertEqual(loan.get_outstanding_loan_balance(
                at_date=datetime.date(2016, 9, 20)), Decimal('81498.58'))
        self.assertEqual(loan.get_outstanding_loan_balance(
                at_date=datetime.date(2099, 9, 20)), Decimal(0))

        # Test loan modification
        loan.rate = Decimal('0.0752')
        loan.funds_release_date = datetime.date(2014, 3, 5)
        loan.payment_frequency = 'quarter'
        loan.first_payment_date = coop_date.add_duration(
            loan.funds_release_date, loan.payment_frequency,
            stick_to_end_of_month=True)
        self.assertEqual(loan.first_payment_date, datetime.date(2014, 6, 5))
        loan.duration = 14
        loan.duration_unit = 'year'
        loan.amount = Decimal(134566)
        loan.deferral = 'fully'
        loan.deferral_duration = 8
        loan.calculate()
        loan.save()
        self.assertEqual(loan.duration, 168)
        self.assertEqual(loan.get_payment_amount(loan.first_payment_date),
            Decimal(0))
        self.assertEqual(len(loan.increments), 2)
        increment_1 = loan.increments[0]
        self.assert_(increment_1)
        self.assertEqual(increment_1.deferral, 'fully')
        self.assertEqual(increment_1.number_of_payments, 8)
        self.assertEqual(increment_1.start_date, datetime.date(2014, 6, 5))
        self.assertEqual(increment_1.begin_balance, Decimal(134566))
        increment_2 = loan.increments[-1]
        self.assert_(increment_2)
        self.assertEqual(increment_2.number_of_payments, 48)
        self.assertEqual(increment_2.start_date, datetime.date(2016, 6, 5))
        self.assertEqual(increment_2.begin_balance, Decimal('156187.70'))

        self.assert_payment(loan, datetime.date(2014, 12, 5), 3,
            Decimal('139673.24'), Decimal(0), Decimal('-2625.86'),
            Decimal('2625.86'), Decimal('142299.10'))
        self.assert_payment(loan, datetime.date(2016, 6, 5), 9,
            Decimal('156187.70'), Decimal('4968.47'), Decimal('2032.14'),
            Decimal('2936.33'), Decimal('154155.56'))
        self.assert_payment(loan, datetime.date(2019, 6, 5), 21,
            Decimal('129115.62'), Decimal('4968.47'), Decimal('2541.10'),
            Decimal('2427.37'), Decimal('126574.52'))
        self.assert_payment(loan, datetime.date(2027, 12, 5), 55,
            Decimal('9663.48'), Decimal('4968.47'), Decimal('4786.80'),
            Decimal('181.67'), Decimal('4876.68'))
        self.assert_payment(loan, datetime.date(2028, 3, 5), 56,
            Decimal('4876.68'), Decimal('4968.36'), Decimal('4876.68'),
            Decimal('91.68'), Decimal('0'))
        loan.save()
        self.assert_(loan.end_date == datetime.date(2028, 3, 5))
        self.assertEqual(loan.get_outstanding_loan_balance(
                at_date=loan.funds_release_date), loan.amount)
        self.assertEqual(loan.get_outstanding_loan_balance(
                at_date=datetime.date(2026, 10, 20)), Decimal('27943.50'))
        self.assertEqual(loan.get_outstanding_loan_balance(
                at_date=datetime.date(2099, 9, 20)), Decimal(0))

        loan = self.Loan(
            kind='balloon',
            rate=Decimal('0.0677'),
            funds_release_date=datetime.date(2014, 3, 5),
            payment_frequency='half_year',
            currency=currency,
            company=company)
        loan.first_payment_date = loan.on_change_with_first_payment_date()
        self.assertEqual(loan.first_payment_date, datetime.date(2014, 9, 5))
        loan.duration = 30
        loan.duration_unit = 'half_year'
        loan.amount = Decimal(243455)
        loan.calculate()
        loan.save()
        self.assertEqual(loan.get_payment_amount(loan.first_payment_date),
            Decimal('8240.95'))
        self.assertEqual(len(loan.increments), 2)
        increment_1 = loan.increments[0]
        self.assert_(increment_1)
        self.assertEqual(increment_1.deferral, 'partially')
        self.assertEqual(increment_1.number_of_payments, 29)
        self.assertEqual(increment_1.start_date, datetime.date(2014, 9, 5))
        self.assertEqual(increment_1.begin_balance, loan.amount)
        increment_2 = loan.increments[-1]
        self.assert_(increment_2)
        self.assertEqual(increment_2.number_of_payments, 1)
        self.assertEqual(increment_2.start_date, datetime.date(2029, 3, 5))
        self.assertEqual(increment_2.begin_balance, loan.amount)

        self.assert_payment(loan, datetime.date(2022, 3, 5), 16, loan.amount,
            Decimal('8240.95'), Decimal(0), Decimal('8240.95'), loan.amount)
        self.assert_payment(loan, datetime.date(2029, 3, 5), 30, loan.amount,
            Decimal('251695.95'), loan.amount, Decimal('8240.95'),
            Decimal('0'))

        loan = self.Loan(
            kind='interest_free',
            funds_release_date=datetime.date(2016, 1, 31),
            rate=None,
            amount=Decimal(100000),
            duration=120,
            duration_unit='month',
            payment_frequency='month',
            currency=currency,
            company=company)
        loan.first_payment_date = loan.on_change_with_first_payment_date()
        self.assertEqual(loan.first_payment_date, datetime.date(2016, 2, 29))
        loan.calculate()
        self.assertEqual(loan.payments[1].start_date,
            datetime.date(2016, 2, 29))
        self.assertEqual(loan.payments[2].start_date,
            datetime.date(2016, 3, 31))
        self.assertEqual(loan.payments[13].start_date,
            datetime.date(2017, 2, 28))
        self.assertEqual(loan.payments[-1].start_date,
            datetime.date(2026, 1, 31))

        loan.first_payment_date = datetime.date(2016, 2, 27)
        loan.calculate()
        self.assertEqual(loan.payments[2].start_date,
            datetime.date(2016, 3, 27))

        # Test Loan Modification at current date
        loan = self.Loan(
            kind='fixed_rate',
            rate=Decimal('0.033'),
            funds_release_date=datetime.date(2013, 4, 15),
            first_payment_date=datetime.date(2013, 5, 15),
            payment_frequency='month',
            amount=Decimal('171848.22'),
            duration=Decimal('252'),
            duration_unit='month',
            currency=currency,
            company=company)
        loan.deferral = 'partially'
        loan.deferral_duration = 12
        loan.calculate()
        self.assert_payment(loan, datetime.date(2034, 3, 15), 251,
            begin_balance='1950.18', amount='979.08',
            principal='973.72', interest='5.36',
            outstanding_balance='976.46')
        loan.save()

        # Add manual increment at effective date
        increment = self.LoanIncrement(
            start_date=datetime.date(2015, 7, 15),
            begin_balance=Decimal('166199.5'),
            number_of_payments=229,
            rate=Decimal('0.024'),
            payment_frequency='month',
            currency=loan.currency,
            loan=loan,
            deferral='',
            manual=True)
        increment.payment_amount = increment.calculate_payment_amount()
        loan.increments = list(loan.increments) + [increment]
        loan.save()
        loan.calculate()
        loan.save()
        self.assertEqual(list(loan.increments)[1].number_of_payments, 14)
        self.assertEqual(loan.duration, 255)
        self.assert_payment(loan, datetime.date(2034, 5, 15), 253,
            begin_balance='2704.24', amount='905.32',
            principal='899.91', interest='5.41',
            outstanding_balance='1804.33')

        # Test synchronized date
        increment = self.LoanIncrement(
            start_date=datetime.date(2015, 6, 5),
            begin_balance=Decimal('166199.5'),
            number_of_payments=225,
            rate=Decimal('0.024'),
            payment_frequency='month',
            loan=loan,
            currency=loan.currency,
            deferral=None,
            manual=True)
        increment.payment_amount = increment.calculate_payment_amount()
        loan.increments = list(loan.increments) + [increment]
        loan.calculate()
        loan.save()
        increment_2 = list(loan.increments)[1]
        increment_3 = list(loan.increments)[2]
        self.assertEqual(increment_2.number_of_payments, 13)
        self.assertEqual(increment_2.end_date, datetime.date(2015, 5, 15))
        self.assertEqual(increment_3.start_date, datetime.date(2015, 6, 5))
        self.assertEqual(increment_3.end_date, datetime.date(2034, 2, 5))

        # Test manual increment with graduated loan
        loan = self.Loan(
            kind='graduated',
            rate=Decimal('0.038'),
            funds_release_date=datetime.date(2013, 4, 15),
            first_payment_date=datetime.date(2013, 5, 15),
            payment_frequency='month',
            amount=Decimal('65087'),
            duration=Decimal('312'),
            duration_unit='month',
            currency=currency,
            company=company)
        loan.increments = [
            self.LoanIncrement(
                number_of_payments=12,
                deferral='partially',
                rate=loan.rate,
                payment_amount=Decimal('206.12'),
                payment_frequency=loan.payment_frequency,
                ),
            self.LoanIncrement(
                number_of_payments=240,
                rate=loan.rate,
                payment_amount=Decimal('207.12'),
                payment_frequency=loan.payment_frequency,
                ),
            self.LoanIncrement(
                number_of_payments=60,
                begin_balance=Decimal('64724.40'),
                rate=loan.rate,
                payment_amount=Decimal('1186.20'),
                payment_frequency=loan.payment_frequency,
                ),
            ]
        loan.calculate()
        loan.save()

        loan.state = 'draft'
        loan.increments = list(loan.increments) + [
            self.LoanIncrement(
                start_date=datetime.date(2015, 7, 15),
                begin_balance=Decimal('65074.66'),
                number_of_payments=228,
                rate=Decimal('0.024'),
                payment_amount=Decimal('300'),
                payment_frequency='month',
                loan=loan,
                manual=True,
                ),
            self.LoanIncrement(
                number_of_payments=12,
                rate=Decimal('0.024'),
                payment_frequency='month',
                payment_amount=Decimal('1356.64'),
                loan=loan,
                )]
        loan.save()
        loan.calculate()
        loan.save()
        self.assertEqual(loan.increments[2].number_of_payments, 228)
        self.assertEqual(loan.increments[3].begin_balance, Decimal('16070.03'))
        self.assertEqual(loan.increments[3].start_date,
            datetime.date(2034, 7, 15))
        self.assertEqual(loan.duration, 266)
        self.assert_payment(loan, datetime.date(2034, 6, 15), 254,
            begin_balance='16337.36', amount='300',
            principal='267.33', interest='32.67',
            outstanding_balance='16070.03')
        self.assert_payment(loan, datetime.date(2035, 6, 15), 266,
            begin_balance='1353.97', amount='1356.68',
            principal='1353.97', interest='2.71',
            outstanding_balance='0')

    @test_framework.prepare_test(
        'loan.test0010loan_basic_data',
        )
    def test0038loan_payment_dates(self):
        '''
        Test basic loan
        '''
        currency, = self.Currency.search([], limit=1)
        company, = self.Company().search([], limit=1)
        loan = self.Loan(
            kind='fixed_rate',
            rate=Decimal('0.04'),
            funds_release_date=datetime.date(2013, 12, 31),
            first_payment_date=datetime.date(2014, 1, 31),
            payment_frequency='month',
            amount=Decimal(100000),
            duration=12,
            duration_unit='month',
            currency=currency,
            company=company)
        loan.calculate()
        loan.save()

        self.assertEqual(loan.payments[1].start_date,
            datetime.date(2014, 1, 31))
        self.assertEqual(loan.payments[2].start_date,
            datetime.date(2014, 2, 28))
        self.assertEqual(loan.payments[3].start_date,
            datetime.date(2014, 3, 31))
        self.assertEqual(loan.payments[4].start_date,
            datetime.date(2014, 4, 30))
        self.assertEqual(loan.payments[11].start_date,
            datetime.date(2014, 11, 30))

    @test_framework.prepare_test(
        'loan.test0010loan_basic_data',
        )
    def test0039intermediate_loan_last_payment(self):
        '''
        Test intermediate loan
        '''
        currency, = self.Currency.search([], limit=1)
        company, = self.Company().search([], limit=1)

        loan = self.Loan(
            kind='graduated',
            funds_release_date=datetime.date(2013, 3, 22),
            first_payment_date=datetime.date(2015, 04, 22),
            rate=Decimal('0.0395'),
            amount=Decimal(101948),
            duration=360,
            duration_unit='month',
            payment_frequency='month',
            currency=currency,
            company=company)
        increment_1 = self.LoanIncrement(
            number=1,
            number_of_payments=180,
            payment_amount=Decimal('435.00'),
            payment_frequency='month',
            rate=Decimal('0.0395'))
        increment_2 = self.LoanIncrement(
            number=2,
            number_of_payments=96,
            payment_amount=Decimal('536.86'),
            payment_frequency='month',
            rate=Decimal('0.0395'))
        increment_3 = self.LoanIncrement(
            number=3,
            number_of_payments=84,
            payment_amount=Decimal('625.82'),
            payment_frequency='month',
            rate=Decimal('0.0395'))
        loan.increments = [increment_1, increment_2, increment_3]
        loan.calculate()
        loan.save()
        self.assert_payment(loan, datetime.date(2045, 3, 22), 360,
            Decimal('623.72'), Decimal('625.77'), Decimal('623.72'),
            Decimal('2.05'), Decimal('0.00'))

    @test_framework.prepare_test(
        'loan.test0010loan_basic_data',
        'contract_insurance.test0001_testPersonCreation',
        )
    def test0048_insured_outstanding_loan_balance_wizard(self):
        'Test outstanding amount wizard'

        company, = self.Company().search([], limit=1)
        currency, = self.Currency.search([], limit=1)

        item_desc = self.ItemDescription(name='Test Item Desc', kind='person',
            code='test_item_desc')
        item_desc.save()

        def create_insurer(name):
            party = self.Party(name=name)
            party.save()
            insurer = self.Insurer(party=party)
            insurer.save()
            return insurer

        def create_account():
            product_account_kind = self.AccountKind(
                    name='Product Account Kind',
                    company=company)
            product_account_kind.save()
            account = self.Account(
                name='Loan Product Account',
                code='Loan Product Account',
                kind='revenue',
                type=product_account_kind,
                company=company)
            account.save()
            return account

        def create_coverage(name, code, family, insurance_kind,
                account, insurer, start_date):
            coverage = self.Coverage(
                code=code,
                name=name,
                company=company,
                item_desc=item_desc,
                start_date=start_date,
                account_for_billing=account,
                insurer=insurer,
                family='loan',
                insurance_kind=insurance_kind)
            coverage.save()
            return coverage

        def create_loan(amount, base_date):
            loan = self.Loan(
                kind='fixed_rate',
                rate=Decimal('0.04'),
                funds_release_date=base_date + datetime.timedelta(weeks=20),
                first_payment_date=base_date + datetime.timedelta(weeks=30),
                payment_frequency='month',
                amount=Decimal(amount),
                duration=120,
                duration_unit='month',
                currency=currency,
                company=company)
            loan.calculate()
            loan.save()
            return loan

        def create_product(base_date, account):
            self.Sequence(name='Contract',
                    code='contract', company=company).save()
            ng = self.Sequence.search([
                    ('code', '=', 'contract')])[0]
            product = self.Product(
                code='AAA',
                name='Awesome Alternative Allowance',
                contract_generator=ng,
                company=company,
                start_date=base_date)
            product.save()
            return product

        def create_contract(account, product, subscriber):
            start_date = product.start_date + datetime.timedelta(weeks=10)
            contract = self.Contract(
                product=product.id,
                company=product.company.id,
                appliable_conditions_date=start_date,
                start_date=start_date,
                )
            contract.save()
            contract.account_for_billing = account
            contract.subscriber = subscriber
            return contract

        def create_option(coverage, covered_element, base_date):
            option = self.Option(
                start_date=base_date + datetime.timedelta(weeks=10),
                coverage=coverage.id,
                covered_element=covered_element.id,
                status='active')
            option.save()
            return option

        def create_loan_share(share, option, loan):
            loan_share = self.LoanShare(
                option=option,
                loan=loan,
                share=Decimal(share))
            loan_share.save()

        base_date = datetime.date(2014, 01, 15)
        john = self.Party.search([('name', '=', 'DOE')])[0]

        account_product = create_account()
        product = create_product(base_date, account_product)

        insurer1 = create_insurer("INSURER1")
        insurer2 = create_insurer("INSURER2")

        account_ins1 = create_account()
        account_ins2 = create_account()
        death_ins1 = create_coverage("DeathInsurer1", "death_ins1",
                "insurance", "death", account_ins1, insurer1,
                base_date)
        dis_ins1 = create_coverage("DisInsurer1", "dis_ins1",
                "insurance", "partial_disability", account_ins1, insurer1,
                base_date)
        temp_dis_ins2 = create_coverage("TempInsurer2", "tem_ins2",
                "insurance", "temporary_disability",
                account_ins2, insurer2,
                base_date)
        loan1 = create_loan(100000, base_date)
        loan2 = create_loan(200000, base_date)
        product.coverages = [death_ins1, dis_ins1, temp_dis_ins2]
        product.save()

        account_contract = create_account()
        contract1 = create_contract(account_contract, product, john)
        contract2 = create_contract(account_contract, product, john)

        covered_element1 = self.CoveredElement()
        covered_element1.contract = contract1
        covered_element1.item_desc = item_desc
        covered_element1.party = john
        covered_element1.save()
        covered_element2 = self.CoveredElement()
        covered_element2.contract = contract2
        covered_element2.item_desc = item_desc
        covered_element2.party = john
        covered_element2.save()

        # on contract 1
        option_death_ins1 = create_option(death_ins1,
                covered_element1, base_date)
        option_dis_ins1 = create_option(dis_ins1,
                covered_element1, base_date)
        option_temp_dis_ins2 = create_option(temp_dis_ins2,
                covered_element1, base_date)

        create_loan_share('0.8', option_death_ins1, loan1)
        create_loan_share('0.8', option_death_ins1, loan2)
        create_loan_share('0.3333', option_dis_ins1, loan1)
        create_loan_share('0.3333', option_temp_dis_ins2, loan1)
        contract1.loans = [loan1, loan2]
        contract1.save()

        # on contract 2
        option_temp_dis_ins2_2 = create_option(temp_dis_ins2,
                covered_element2, base_date)
        create_loan_share('0.8', option_temp_dis_ins2_2, loan2)
        contract2.loans = [loan2]
        contract2.save()

        for contract in (contract1, contract2):
            contract.activate_contract()
            contract.save()
            self.assertEqual(contract.status, 'active')

        self.assertEqual(contract1.end_date, max([x.end_date
                    for x in (loan1, loan2)]))
        self.assertEqual(contract2.end_date, loan2.end_date)

        def run_wizard(at_date, currency):
            with Transaction().set_context(active_id=john.id,
                    company=company.id):
                wizard_id, _, _ = self.InsuredOutstandingLoanBalance.create()
                wizard = self.InsuredOutstandingLoanBalance(wizard_id)
                wizard._execute('select_date')
                wizard.select_date.date = at_date
                wizard.select_date.party = john
                wizard.select_date.currency = currency
                wizard._execute('insured_outstanding_loan_balance_view')
                lines = wizard.get_insured_outstanding_loan_balances(
                    john, at_date, currency)
                return lines

        test_date = base_date - datetime.timedelta(weeks=20)
        res = run_wizard(test_date, currency)
        insurers = set([x['name'] for x in res])
        self.assertEqual(insurers, set(['Total']))
        self.assertEqual(res[0]['amount'], Decimal('0'))

        test_date = base_date + datetime.timedelta(days=227)
        res = run_wizard(test_date, currency)
        insurers = set([x['name'] for x in res])
        self.assertEqual(insurers, set(['Total', insurer1.rec_name,
                    insurer2.rec_name]))
        for line in res:
            if line['name'] == insurer1.rec_name:
                self.assertEqual(line['amount'], Decimal('238370.12'))
                coverages = set(x['name'] for x in line['childs'])
                self.assertTrue(
                        coverages == set(['Death', 'Partial Disability']))
                for child in line['childs']:
                    if child['name'] == 'Death':
                        self.assertEqual(child['amount'], Decimal('238370.12'))
                    if child['name'] == 'Partial Disability':
                        self.assertEqual(child['amount'], Decimal('33103.65'))
            elif line['name'] == insurer2.rec_name:
                self.assertEqual(line['amount'], Decimal('192017.07'))
                coverages = set(x['name'] for x in line['childs'])
                self.assertTrue(coverages == set(['Temporary Disability']))
                self.assertEqual(line['childs'][0]['amount'],
                    Decimal('192017.07'))
            elif line['name'] == 'Total':
                self.assertEqual(line['amount'], Decimal('192017.07') +
                    Decimal('238370.12'))

        test_date = base_date + datetime.timedelta(days=2662)
        res = run_wizard(test_date, currency)
        insurers = set([x['name'] for x in res])
        self.assertEqual(insurers, set(['Total', insurer1.rec_name,
                    insurer2.rec_name]))
        for line in res:
            if line['name'] == insurer1.rec_name:
                self.assertEqual(line['amount'], Decimal('88726.16'))
                coverages = set(x['name'] for x in line['childs'])
                self.assertTrue(
                        coverages == set(['Death', 'Partial Disability']))
                for child in line['childs']:
                    if child['name'] == 'Death':
                        self.assertEqual(child['amount'], Decimal('88726.16'))
                    if child['name'] == 'Partial Disability':
                        self.assertEqual(child['amount'], Decimal('12321.84'))
            elif line['name'] == insurer2.rec_name:
                self.assertEqual(line['amount'], Decimal('71472.62'))
                coverages = set(x['name'] for x in line['childs'])
                self.assertTrue(coverages == set(['Temporary Disability']))
                for child in line['childs']:
                    if child['name'] == 'Temporary Disability':
                        self.assertEqual(child['amount'], Decimal('71472.62'))
            elif line['name'] == 'Total':
                self.assertEqual(line['amount'], Decimal('88726.16') +
                    Decimal('71472.62'))

        test_date = contract.end_date + datetime.timedelta(days=1)
        res = run_wizard(test_date, currency)
        insurers = set([x['name'] for x in res])
        self.assertEqual(insurers, set(['Total']))
        self.assertEqual(res[0]['amount'], Decimal('0'))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_contract_loan.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
