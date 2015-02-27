# -*- coding:utf-8 -*-
from decimal import Decimal
import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework, coop_date
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

    def assert_payment(self, loan, at_date, number, begin_balance, amount,
            principal, interest, outstanding_balance):
        payment = loan.get_payment(at_date)
        self.assert_(payment)
        self.assertEqual(payment.number, number)
        self.assertEqual(payment.begin_balance, begin_balance)
        self.assertEqual(payment.amount, amount)
        self.assertEqual(payment.principal, principal)
        self.assertEqual(payment.interest, interest)
        self.assertEqual(payment.outstanding_balance, outstanding_balance)

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
            funds_release_date=datetime.date(2012, 7, 1),
            first_payment_date=datetime.date(2012, 7, 15),
            payment_frequency='month',
            amount=Decimal(100000),
            number_of_payments=180,
            currency=currency,
            company=company)
        loan.deferal = 'partially'
        loan.deferal_duration = 12
        loan.calculate()
        loan.save()
        self.assertEqual(loan.get_payment_amount(loan.first_payment_date),
            Decimal('333.33'))
        self.assertEqual(loan.get_payment_amount(datetime.date(2013, 7, 15)),
            Decimal('778.35'))
        self.assertEqual(len(loan.increments), 2)
        increment_1 = loan.increments[0]
        self.assert_(increment_1)
        self.assertEqual(increment_1.deferal, 'partially')
        self.assertEqual(increment_1.number_of_payments, 12)
        self.assertEqual(increment_1.payment_amount, Decimal('333.33'))
        increment_2 = loan.increments[-1]
        self.assert_(increment_2)
        self.assertEqual(increment_2.payment_amount, Decimal('778.35'))

        self.assertEqual(len(loan.payments), loan.number_of_payments + 1)
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
        loan.number_of_payments = loan.on_change_with_number_of_payments()
        self.assertEqual(loan.number_of_payments, 56)
        loan.amount = Decimal(134566)
        loan.deferal = 'fully'
        loan.deferal_duration = 8
        loan.calculate()
        loan.save()
        self.assertEqual(loan.get_payment_amount(loan.first_payment_date),
            Decimal(0))
        self.assertEqual(len(loan.increments), 2)
        increment_1 = loan.increments[0]
        self.assert_(increment_1)
        self.assertEqual(increment_1.deferal, 'fully')
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
        loan.number_of_payments = 30
        loan.amount = Decimal(243455)
        loan.calculate()
        loan.save()
        self.assertEqual(loan.get_payment_amount(loan.first_payment_date),
            Decimal('8240.95'))
        self.assertEqual(len(loan.increments), 2)
        increment_1 = loan.increments[0]
        self.assert_(increment_1)
        self.assertEqual(increment_1.deferal, 'partially')
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
            number_of_payments=120,
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

    @test_framework.prepare_test(
        'contract_insurance.test0001_testPersonCreation',
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
            number_of_payments=12,
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
        'loan.test0037loan_creation',
        'contract_insurance.test0001_testPersonCreation',
        )
    def test0048_insured_outstanding_loan_balance_wizard(self):
        'Test outstanding amount wizard'

        company, = self.Company().search([], limit=1)
        currency, = self.Currency.search([], limit=1)

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
                start_date=start_date,
                account_for_billing=account,
                insurer=insurer,
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
                number_of_payments=120,
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
                start_date=base_date,
                account_for_billing=account)
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
            contract.activation_history[0].end_date = start_date + \
                datetime.timedelta(weeks=3000)
            contract.activation_history[0].save()
            contract.account_for_billing = account
            contract.subscriber = subscriber
            contract.activate_contract()
            contract.finalize_contract()
            self.assertEqual(contract.status, 'active')
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

        account_contract = create_account()
        contract1 = create_contract(account_contract, product, john)
        contract2 = create_contract(account_contract, product, john)
        covered_element1 = self.CoveredElement()
        covered_element1.contract = contract1
        covered_element1.party = john
        covered_element1.save()
        covered_element2 = self.CoveredElement()
        covered_element2.contract = contract2
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

        # on contract 2
        option_temp_dis_ins2_2 = create_option(temp_dis_ins2,
                covered_element2, base_date)
        create_loan_share('0.8', option_temp_dis_ins2_2, loan2)

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

        test_date = base_date + datetime.timedelta(weeks=2000)
        res = run_wizard(test_date, currency)
        insurers = set([x['name'] for x in res])
        self.assertEqual(insurers, set(['Total', insurer1.rec_name,
                    insurer2.rec_name]))
        for line in res:
            self.assertEqual(line['amount'], 0)

        test_date = base_date + datetime.timedelta(weeks=3200)
        res = run_wizard(test_date, currency)
        insurers = set([x['name'] for x in res])
        self.assertEqual(insurers, set(['Total']))
        self.assertEqual(res[0]['amount'], Decimal('0'))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
