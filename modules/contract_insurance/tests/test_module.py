# -*- coding:utf-8 -*-
import datetime
import unittest
from decimal import Decimal

import trytond.tests.test_tryton
import mock

from trytond.modules.cog_utils import test_framework
from trytond.transaction import Transaction
from trytond.exceptions import UserError


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'contract_insurance'

    @classmethod
    def depending_modules(cls):
        return ['offered_insurance']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'ExtraPremium': 'contract.option.extra_premium',
            'Contract': 'contract',
            'Option': 'contract.option',
            'ContractChangeStartDate': 'contract.change_start_date',
            'Coverage': 'offered.option.description',
            'CoveredElement': 'contract.covered_element',
            'RuleEngineRuntime': 'rule_engine.runtime',
            }

    def test0001_testPersonCreation(self):
        party = self.Party()
        party.is_person = True
        party.name = 'DOE'
        party.first_name = 'John'
        party.birth_date = datetime.date(1980, 5, 30)
        party.gender = 'male'
        party.save()

        party, = self.Party.search([('name', '=', 'DOE')])
        self.assert_(party.id)

    @test_framework.prepare_test(
        'offered_insurance.test0100_testExtraPremiumKindCreation',
    )
    def test0010_testExtraPremiumRateCalculate(self):
        extra_premium = self.ExtraPremium()
        extra_premium.calculation_kind = 'rate'
        extra_premium.rate = Decimal('-0.05')
        extra_premium_kind, = self.ExtraPremiumKind.search([
            ('code', '=', 'reduc_no_limit'), ])
        extra_premium.motive = extra_premium_kind

        result = extra_premium.calculate_premium_amount(None, base=100)
        self.assertEqual(result, Decimal('-5.0'))

    @test_framework.prepare_test(
        'offered_insurance.test0100_testExtraPremiumKindCreation',
    )
    def test0011_testExtraPremiumAmountCalculate(self):
        extra_premium = self.ExtraPremium()
        extra_premium.calculation_kind = 'flat'
        extra_premium.flat_amount = Decimal('100')
        extra_premium_kind, = self.ExtraPremiumKind.search([
            ('code', '=', 'reduc_no_limit'), ])
        extra_premium.motive = extra_premium_kind

        result = extra_premium.calculate_premium_amount(None, base=100)
        self.assertEqual(result, Decimal('100'))

    @test_framework.prepare_test(
        'offered_insurance.test0010Coverage_creation',
        'contract_insurance.test0001_testPersonCreation',
        )
    def test0012_testContractCreation(self):
        product, = self.Product.search([
                ('code', '=', 'AAA'),
                ])
        start_date = product.start_date + datetime.timedelta(weeks=4)
        end_date = start_date + datetime.timedelta(weeks=52)
        contract = self.Contract(
            start_date=start_date,
            product=product.id,
            company=product.company.id,
            appliable_conditions_date=start_date,
            )
        contract.save()
        self.assertEqual(contract.status, 'quote')
        self.assertEqual(contract.start_date, start_date)
        contract.set_end_date(end_date)
        contract.save()
        self.assertEqual(contract.end_date, end_date)
        self.assertEqual(contract.start_date, start_date)
        self.assertEqual(len(contract.activation_history), 1)
        self.assertEqual(contract.activation_history[0].end_date, end_date)

        contract.finalize_contract()
        contract.activate_contract()
        contract.save()
        self.assertEqual(contract.status, 'active')
        self.assert_(contract.contract_number)
        self.assertEqual(contract.start_date, start_date)

    @test_framework.prepare_test(
        'contract_insurance.test0012_testContractCreation',
        'contract_insurance.test0001_testPersonCreation',
        )
    def test0013_testChangeStartDateWizardOptions(self):
        coverage = self.Coverage.search([])[0]
        contract, = self.Contract.search([])
        start_date = contract.start_date

        def set_test_case(new_date, ant_date, post_date):
            if (contract.covered_elements and
                    contract.covered_elements[0].options):
                for option in contract.covered_elements[0].options:
                    self.Option.delete([option])
            option_cov_ant = self.Option()
            option_cov_ant.coverage = coverage.id
            option_cov_ant.start_date = ant_date
            option_cov_ant.save()

            option_cov_post = self.Option()
            option_cov_post.coverage = coverage.id
            option_cov_post.start_date = post_date
            option_cov_post.save()

            covered_element = self.CoveredElement()
            covered_element.options = [option_cov_ant.id, option_cov_post.id]
            covered_element.item_desc = coverage.item_desc
            covered_element.contract = contract
            covered_element.product = covered_element.on_change_with_product()
            party = self.Party.search([('is_person', '=', True)])[0]
            covered_element.party = party
            covered_element.save()
            contract.covered_elements = [covered_element.id]
            contract.save()

            with Transaction().set_context(active_id=contract.id):
                wizard_id, _, _ = self.ContractChangeStartDate.create()
                wizard = self.ContractChangeStartDate(wizard_id)
                wizard._execute('change_date')
                wizard.change_date.new_start_date = new_date
                wizard.change_date.on_change_new_start_date()
                wizard._execute('apply')

        # case 1 : new date posterior to start_date
        new_date = start_date + datetime.timedelta(weeks=2)
        ant_date = new_date - datetime.timedelta(weeks=1)
        post_date = new_date + datetime.timedelta(weeks=1)

        set_test_case(new_date, ant_date, post_date)

        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(
                contract.covered_elements[0].options[0].start_date, new_date)
        self.assertEqual(
                contract.covered_elements[0].options[1].start_date, post_date)

        # case 2 : new date anterior to start_date
        contract.set_start_date(start_date)
        contract.save()
        new_date = start_date - datetime.timedelta(weeks=2)
        ant_date = new_date - datetime.timedelta(weeks=1)
        post_date = new_date + datetime.timedelta(weeks=1)

        set_test_case(new_date, ant_date, post_date)

        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(
                contract.covered_elements[0].options[0].start_date, new_date)
        self.assertEqual(
                contract.covered_elements[0].options[1].start_date, post_date)

    @test_framework.prepare_test(
        'contract_insurance.test0012_testContractCreation',
        'contract_insurance.test0001_testPersonCreation',
        'offered_insurance.test0100_testExtraPremiumKindCreation',
    )
    def test0014_testChangeStartDateWizardOptionsPremiums(self):
        coverage = self.Coverage.search([])[0]
        contract, = self.Contract.search([])
        start_date = contract.start_date

        def set_test_case(new_date, ant_date, post_date):

            if (contract.covered_elements and
                    contract.covered_elements[0].options):
                for option in contract.covered_elements[0].options:
                    self.Option.delete([option])

            if contract.options:
                for option in contract.options:
                    self.Option.delete([option])

            option_cov = self.Option()
            option_cov.coverage = coverage.id
            option_cov.start_date = ant_date
            extra_premium_ant = self.ExtraPremium()
            extra_premium_ant.calculation_kind = 'rate'
            extra_premium_ant.rate = Decimal('-0.05')
            extra_premium_kind, = self.ExtraPremiumKind.search([
                ('code', '=', 'reduc_no_limit'), ])
            extra_premium_ant.motive = extra_premium_kind
            extra_premium_ant.option = option_cov
            extra_premium_ant.start_date = ant_date
            extra_premium_ant.save()

            extra_premium_post = self.ExtraPremium()
            extra_premium_post.calculation_kind = 'rate'
            extra_premium_post.rate = Decimal('-0.05')
            extra_premium_post.motive = extra_premium_kind
            extra_premium_post.option = option_cov
            extra_premium_post.start_date = post_date
            extra_premium_post.save()

            option_cov.extra_premiums = [
                    extra_premium_ant.id, extra_premium_post.id
                    ]
            option_cov.save()

            covered_element = self.CoveredElement()
            covered_element.options = [option_cov.id]
            covered_element.item_desc = coverage.item_desc
            covered_element.contract = contract
            covered_element.product = covered_element.on_change_with_product()
            party = self.Party.search([('is_person', '=', True)])[0]
            covered_element.party = party
            covered_element.save()

            contract.covered_elements = [covered_element.id]

            option_contract = self.Option()
            option_contract.coverage = coverage.id
            option_contract.start_date = ant_date
            extra_premium_contract_ant = self.ExtraPremium()
            extra_premium_contract_ant.calculation_kind = 'rate'
            extra_premium_contract_ant.rate = Decimal('-0.05')
            extra_premium_contract_kind, = self.ExtraPremiumKind.search([
                ('code', '=', 'reduc_no_limit'), ])
            extra_premium_contract_ant.motive = extra_premium_kind
            extra_premium_contract_ant.option = option_cov
            extra_premium_contract_ant.start_date = ant_date
            extra_premium_contract_ant.save()

            extra_premium_contract_post = self.ExtraPremium()
            extra_premium_contract_post.calculation_kind = 'rate'
            extra_premium_contract_post.rate = Decimal('-0.05')
            extra_premium_contract_post.motive = extra_premium_kind
            extra_premium_contract_post.option = option_cov
            extra_premium_contract_post.start_date = post_date
            extra_premium_contract_post.save()

            option_contract.extra_premiums = [
                    extra_premium_contract_ant.id,
                    extra_premium_contract_post.id,
                    ]
            option_contract.save()
            contract.options = [option_contract.id]

            contract.save()

            with Transaction().set_context(active_id=contract.id):
                wizard_id, _, _ = self.ContractChangeStartDate.create()
                wizard = self.ContractChangeStartDate(wizard_id)
                wizard._execute('change_date')
                wizard.change_date.new_start_date = new_date
                wizard.change_date.on_change_new_start_date()
                wizard._execute('apply')

        # test case 1 : new_date posterior to start_date
        new_date = start_date + datetime.timedelta(weeks=2)
        ant_date = new_date - datetime.timedelta(weeks=1)
        post_date = new_date + datetime.timedelta(weeks=1)

        set_test_case(new_date, ant_date, post_date)

        contract_cov_opt = contract.covered_elements[0].options[0]
        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(
                contract_cov_opt.start_date, new_date)
        self.assertEqual(
                contract_cov_opt.extra_premiums[0].start_date, new_date)
        self.assertEqual(
                contract_cov_opt.extra_premiums[1].start_date, post_date)
        self.assertEqual(
                contract.options[0].extra_premiums[0].start_date, new_date)
        self.assertEqual(
                contract.options[0].extra_premiums[1].start_date, post_date)

        # test case 2 : new_date posterior to start_date
        contract.set_start_date(start_date)
        contract.save()
        new_date = start_date - datetime.timedelta(weeks=2)
        ant_date = new_date - datetime.timedelta(weeks=1)
        post_date = new_date + datetime.timedelta(weeks=1)

        set_test_case(new_date, ant_date, post_date)

        contract_cov_opt = contract.covered_elements[0].options[0]
        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(
                contract_cov_opt.start_date, new_date)
        self.assertEqual(
                contract_cov_opt.extra_premiums[0].start_date, new_date)
        self.assertEqual(
                contract_cov_opt.extra_premiums[1].start_date, post_date)
        self.assertEqual(
                contract.options[0].extra_premiums[0].start_date, new_date)
        self.assertEqual(
                contract.options[0].extra_premiums[1].start_date, post_date)

    def test0015_testOptionEndDate(self):
        start_date = datetime.date(2012, 2, 15)
        date1 = start_date + datetime.timedelta(weeks=30)
        date2 = start_date + datetime.timedelta(weeks=50)
        date3 = start_date + datetime.timedelta(weeks=60)
        contract_end_date = start_date + datetime.timedelta(weeks=70)
        early_date = start_date - datetime.timedelta(weeks=1)
        late_date = contract_end_date + datetime.timedelta(weeks=1)

        def test_option(automatic_end_date=None, manual_end_date=None,
                        start_date=start_date, expected=None,
                        should_raise=False,
                        to_set=None, should_set=True):
            option = self.Option(
                start_date=start_date,
                automatic_end_date=automatic_end_date,
                manual_end_date=manual_end_date,
                parent_contract=self.Contract(end_date=contract_end_date),
                covered_element=self.CoveredElement(),
                )
            self.assertEqual(option.get_end_date('end_date'), expected)

            # test setter
            with mock.patch.object(self.Option, 'write') as write:
                if should_raise:
                    self.assertRaises(UserError, self.Option.set_end_date,
                        [option], 'end_date', to_set)
                else:
                    self.Option.set_end_date([option], 'end_date', to_set)
                    if should_set:
                        write.assert_called_with([option],
                            {'manual_end_date': to_set})
                    else:
                        write.assert_called_with([],
                            {'manual_end_date': to_set})

        # option with auto date
        test_option(automatic_end_date=date2, expected=date2,
            to_set=date1, should_set=True)

        # option with manual date
        test_option(automatic_end_date=date2, manual_end_date=date3,
            expected=min(date3, date2), to_set=date1,
            should_set=True)

        # option with no end date at all
        test_option(expected=contract_end_date, to_set=date1,
            should_set=True)

        # try setting setting end date anterior to start date
        test_option(expected=contract_end_date, to_set=early_date,
            should_raise=True)

        # try setting setting end date posterior to contract end date
        test_option(expected=contract_end_date, to_set=late_date,
            should_raise=True)

        test_option(automatic_end_date=date2, expected=date2, to_set=date1,
            should_set=True)

        # try setting setting end date posterior to option automatic end date
        test_option(automatic_end_date=date2, expected=date2, to_set=date3,
            should_raise=True)

    @test_framework.prepare_test(
        'contract_insurance.test0012_testContractCreation',
        'contract_insurance.test0001_testPersonCreation',
    )
    def test_0020_testLastOptionEndsContract(self):
        # The ending date of a contract should be capped by
        # the max ending date of covered elements options
        contract, = self.Contract.search([])
        current_end = contract.end_date
        end_option1 = current_end - datetime.timedelta(weeks=2)
        end_option2 = current_end - datetime.timedelta(weeks=4)

        def add_covered_element_with_options(option_end_dates):
            covered_element = self.CoveredElement()
            options = []
            for end_date in option_end_dates:
                option = self.Option(
                        start_date=contract.start_date,
                        end_date=end_date,
                        parent_contract=contract,
                        covered_element=covered_element
                        )
                options.append(option)
            covered_element.options = options
            return covered_element

        def build_contract_covered_elements(end_date1, end_date2):
            contract.covered_elements = [add_covered_element_with_options(
                    [end_date1, end_date2]),
                add_covered_element_with_options(
                    [end_date2, end_date2])]

        contract.options = []
        build_contract_covered_elements(end_option1, end_option2)
        contract.calculate_end_date()
        self.assertEqual(contract.end_date, max(end_option1, end_option2))

        # Of course, this cap should not be effective
        # if the options ends after the contract
        contract, = self.Contract.search([])
        end_option1 = current_end + datetime.timedelta(weeks=2)
        end_option2 = current_end + datetime.timedelta(weeks=4)
        build_contract_covered_elements(end_option1, end_option2)
        contract.calculate_end_date()
        self.assertEqual(contract.end_date, max(end_option1, end_option2))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
