# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
import datetime
import unittest
from decimal import Decimal

import trytond.tests.test_tryton

from trytond.modules.coog_core import test_framework
from trytond.transaction import Transaction
from trytond.exceptions import UserError


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_insurance'

    @classmethod
    def fetch_models_for(cls):
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
            'SubStatus': 'contract.sub_status',
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
        contract.end_date = end_date
        contract.save()
        self.assertEqual(contract.end_date, end_date)
        self.assertEqual(contract.start_date, start_date)
        self.assertEqual(len(contract.activation_history), 1)
        self.assertEqual(contract.activation_history[0].end_date, end_date)

        contract.activate_contract()
        self.assertEqual(contract.status, 'active')
        contract.end_date = end_date
        contract.save()
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
            option_cov_ant.manual_start_date = ant_date
            option_cov_ant.save()

            option_cov_post = self.Option()
            option_cov_post.coverage = coverage.id
            option_cov_post.manual_start_date = post_date
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
        contract.start_date = start_date
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
        """
        When we postpone the contract start date, the extra_premiums
        with manually set start_dates should stay where they were,
        except when they would be anterior to new contract start_date.
        """

        def set_test_case(new_date, fixed_date):

            if (contract.covered_elements and
                    contract.covered_elements[0].options):
                for option in contract.covered_elements[0].options:
                    self.Option.delete([option])

            if contract.options:
                for option in contract.options:
                    self.Option.delete([option])

            covered_element = self.CoveredElement()
            covered_element.contract = contract
            covered_element.item_desc = coverage.item_desc
            covered_element.product = covered_element.on_change_with_product()
            party = self.Party.search([('is_person', '=', True)])[0]
            covered_element.party = party
            covered_element.save()
            contract.covered_elements = [covered_element.id]

            option_cov = self.Option()
            option_cov.coverage = coverage.id
            option_cov.covered_element = covered_element
            option_cov.save()
            contract.save()

            extra_premium = self.ExtraPremium()
            extra_premium.calculation_kind = 'rate'
            extra_premium.rate = Decimal('-0.05')
            extra_premium_kind, = self.ExtraPremiumKind.search([
                ('code', '=', 'reduc_no_limit'), ])
            extra_premium.motive = extra_premium_kind
            extra_premium.option = option_cov
            extra_premium.duration_unit = 'month'
            extra_premium.duration = 6
            extra_premium.save()

            extra_premium_manual = self.ExtraPremium()
            extra_premium_manual.calculation_kind = 'rate'
            extra_premium_manual.rate = Decimal('-0.05')
            extra_premium_manual.motive = extra_premium_kind
            extra_premium_manual.option = option_cov
            extra_premium_manual.manual_start_date = fixed_date
            extra_premium_manual.duration_unit = 'month'
            extra_premium_manual.duration = 6
            extra_premium_manual.save()

            option_cov.extra_premiums = [
                    extra_premium.id, extra_premium_manual.id
                    ]
            option_cov.save()

            option_contract = self.Option()
            option_contract.coverage = coverage.id
            option_contract.contract = contract
            extra_premium_contract = self.ExtraPremium()
            extra_premium_contract.calculation_kind = 'rate'
            extra_premium_contract.rate = Decimal('-0.05')
            extra_premium_contract_kind, = self.ExtraPremiumKind.search([
                ('code', '=', 'reduc_no_limit'), ])
            extra_premium_contract.motive = extra_premium_kind
            extra_premium_contract.option = option_cov
            extra_premium_contract.duration_unit = 'month'
            extra_premium_contract.duration = 6
            extra_premium_contract.save()

            extra_premium_contract_manual = self.ExtraPremium()
            extra_premium_contract_manual.calculation_kind = 'rate'
            extra_premium_contract_manual.rate = Decimal('-0.05')
            extra_premium_contract_manual.motive = extra_premium_kind
            extra_premium_contract_manual.option = option_cov
            extra_premium_contract_manual.manual_start_date = fixed_date
            extra_premium_contract_manual.duration_unit = 'month'
            extra_premium_contract_manual.duration = 6
            extra_premium_contract_manual.save()

            option_contract.extra_premiums = [
                    extra_premium_contract.id,
                    extra_premium_contract_manual.id,
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

        # test case 1 : We will change the contract start date
        # to a posterior date. ExtraPremium start dates should stick
        # to new start date if not manually set
        new_date = start_date + datetime.timedelta(weeks=2)
        fixed_date = start_date + datetime.timedelta(weeks=1)

        set_test_case(new_date, fixed_date)

        contract_cov_opt = contract.covered_elements[0].options[0]
        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(
                contract_cov_opt.start_date, new_date)
        self.assertEqual(
                contract_cov_opt.extra_premiums[0].start_date, new_date)
        self.assertEqual(
                contract_cov_opt.extra_premiums[1].start_date, fixed_date)
        self.assertEqual(
                contract.options[0].extra_premiums[0].start_date, new_date)
        self.assertEqual(
                contract.options[0].extra_premiums[1].start_date, fixed_date)

        # test end_dates
        self.assertEqual(
                contract_cov_opt.extra_premiums[0].end_date, new_date +
                relativedelta(months=6, days=-1))
        self.assertEqual(
                contract_cov_opt.extra_premiums[1].end_date, fixed_date +
                relativedelta(months=6, days=-1))
        self.assertEqual(
                contract.options[0].extra_premiums[0].end_date, new_date +
                relativedelta(months=6, days=-1))
        self.assertEqual(
                contract.options[0].extra_premiums[1].end_date, fixed_date +
                relativedelta(months=6, days=-1))

        # test case 2 : we will change the contract start date
        # to an anterior date. ExtraPremium start dates should stick
        # to new start date if not manually set
        contract.start_date = start_date
        contract.save()
        new_date = start_date - datetime.timedelta(weeks=2)
        fixed_date = start_date + datetime.timedelta(weeks=1)

        set_test_case(new_date, fixed_date)

        contract_cov_opt = contract.covered_elements[0].options[0]
        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(
                contract_cov_opt.start_date, new_date)
        self.assertEqual(
                contract_cov_opt.extra_premiums[0].start_date, new_date)
        self.assertEqual(
                contract_cov_opt.extra_premiums[1].start_date, fixed_date)
        self.assertEqual(
                contract.options[0].extra_premiums[0].start_date, new_date)
        self.assertEqual(
                contract.options[0].extra_premiums[1].start_date, fixed_date)

        # test end_dates
        self.assertEqual(
                contract_cov_opt.extra_premiums[0].end_date, new_date +
                relativedelta(months=6, days=-1))
        self.assertEqual(
                contract_cov_opt.extra_premiums[1].end_date, fixed_date +
                relativedelta(months=6, days=-1))
        self.assertEqual(
                contract.options[0].extra_premiums[0].end_date, new_date +
                relativedelta(months=6, days=-1))
        self.assertEqual(
                contract.options[0].extra_premiums[1].end_date, fixed_date +
                relativedelta(months=6, days=-1))

    @test_framework.prepare_test(
        'contract_insurance.test0014_testChangeStartDateWizardOptionsPremiums',
    )
    def test0015_testOptionEndDate(self):
        contract = self.Contract.search([])[0]
        coverage = self.Coverage.search([])[0]
        covered_element = self.CoveredElement.search([])[0]
        covered_element.contract = contract
        covered_element.save()
        start_date = contract.start_date
        date1 = start_date + datetime.timedelta(weeks=30)
        date2 = start_date + datetime.timedelta(weeks=50)
        date3 = start_date + datetime.timedelta(weeks=60)
        contract_end_date = start_date + datetime.timedelta(weeks=70)
        early_date = start_date - datetime.timedelta(weeks=1)
        late_date = contract_end_date + datetime.timedelta(weeks=1)
        contract.options = []
        contract.covered_elements[0].options = []
        contract.end_date = contract_end_date
        contract.save()

        def test_option(automatic_end_date=None, manual_end_date=None,
                        start_date=start_date, expected=None,
                        should_raise=False,
                        to_set=None, should_set=True):
            option = self.Option(
                manual_start_date=start_date,
                automatic_end_date=automatic_end_date,
                manual_end_date=manual_end_date,
                covered_element=covered_element,
                coverage=coverage,
                )
            option.sub_status = \
                option.on_change_with_sub_status()
            option.save()
            self.assertEqual(option.end_date, expected)
            option.parent_contract.options = [option]
            option.parent_contract.covered_element_options = [option]
            option.manual_end_date = to_set

            # test check
            if should_raise:
                self.assertRaises(UserError,
                    self.Contract.check_option_end_dates,
                    [option.parent_contract])
            else:
                self.Contract.check_option_end_dates([option.parent_contract])

        # option with auto end date
        test_option(automatic_end_date=date2, expected=date2,
            to_set=date1, should_set=True)

        # option with manual end date
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
        coverage = self.Coverage.search([])[0]
        current_end = contract.end_date
        end_option1 = current_end - datetime.timedelta(weeks=2)
        end_option2 = current_end - datetime.timedelta(weeks=4)

        def add_covered_element_with_options(option_end_dates):
            covered_element = self.CoveredElement()
            covered_element.item_desc = coverage.item_desc
            covered_element.contract = contract
            covered_element.product = covered_element.on_change_with_product()
            party = self.Party.search([('is_person', '=', True)])[0]
            covered_element.party = party
            covered_element.save()
            options = []
            for end_date in option_end_dates:
                option = self.Option(
                        start_date=contract.start_date,
                        manual_end_date=end_date,
                        automatic_end_date=None,
                        covered_element=covered_element,
                        coverage=coverage,
                        parent_contract=contract,
                        )
                option.sub_status = \
                    option.on_change_with_sub_status()
                option.save()
                options.append(option)
            covered_element.options = options
            covered_element.save()
            return covered_element

        def build_contract_covered_elements(end_date1, end_date2):
            self.CoveredElement.delete(contract.covered_elements)
            contract.covered_elements = [add_covered_element_with_options(
                    [end_date1, end_date2]),
                add_covered_element_with_options(
                    [end_date2, end_date2])]

        contract.options = []
        build_contract_covered_elements(end_option1, end_option2)
        self.Contract.calculate_activation_dates([contract])
        contract.save()
        self.assertEqual(contract.end_date, max(end_option1, end_option2))

        # Of course, this cap should not be effective
        # if the options ends after the contract
        end_option1 = current_end + datetime.timedelta(weeks=2)
        end_option2 = current_end + datetime.timedelta(weeks=4)
        build_contract_covered_elements(end_option1, end_option2)
        self.Contract.calculate_activation_dates([contract])
        contract.save()
        self.assertEqual(contract.end_date, max(end_option1, end_option2))

    @test_framework.prepare_test(
        'contract_insurance.test0012_testContractCreation',
        'contract_insurance.test0001_testPersonCreation',
    )
    def test_0030_search_start_date(self):
        contract, = self.Contract.search([])
        coverage = self.Coverage.search([])[0]

        covered_element = self.CoveredElement()
        covered_element.item_desc = coverage.item_desc
        covered_element.contract = contract
        covered_element.product = covered_element.on_change_with_product()
        party = self.Party.search([('is_person', '=', True)])[0]
        covered_element.party = party
        covered_element.save()
        contract.covered_element = [covered_element]
        contract.save()

        def make_option(manual_offset=None):
            if manual_offset:
                my_offset = relativedelta(weeks=manual_offset)
                option = self.Option(
                        manual_start_date=contract.start_date + my_offset,
                        covered_element=covered_element,
                        parent_contract=contract,
                        coverage=coverage,
                        )
                option.save()
            else:
                option = self.Option(
                        covered_element=covered_element,
                        parent_contract=contract,
                        coverage=coverage,
                        )
                option.save()
            return option

        option_no_offset = make_option()
        option_one_week = make_option(manual_offset=1)
        option_three_weeks = make_option(manual_offset=3)

        res = self.Option.search([('start_date', '=', contract.start_date)])
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], option_no_offset)

        res = self.Option.search([('start_date', '=', contract.start_date +
                    relativedelta(weeks=1))])
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], option_one_week)

        res = self.Option.search([('start_date', '>=', contract.start_date)])
        self.assertEqual(len(res), 3)

        res = self.Option.search([('start_date', '>=', contract.start_date +
                    relativedelta(weeks=1))])
        self.assertEqual(len(res), 2)
        self.assertEqual(set(res), set([option_one_week, option_three_weeks]))

        res = self.Option.search([('start_date', '>', contract.start_date +
                    relativedelta(weeks=1))])
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], option_three_weeks)

        res = self.Option.search([('start_date', '<', contract.start_date +
                    relativedelta(weeks=4))])
        self.assertEqual(len(res), 3)

    @test_framework.prepare_test(
        'contract_insurance.test0012_testContractCreation',
        'contract_insurance.test0001_testPersonCreation',
        )
    def test0040_testContractTermination(self):
        coverage = self.Coverage.search([])[0]
        contract, = self.Contract.search([])
        sub_status = self.SubStatus.search([('code', '=',
                    'reached_end_date')])[0]
        covered_element = self.CoveredElement()
        covered_element.contract = contract
        covered_element.item_desc = coverage.item_desc
        covered_element.product = covered_element.on_change_with_product()
        party = self.Party.search([('is_person', '=', True)])[0]
        covered_element.party = party
        covered_element.save()
        contract.covered_elements = [covered_element.id]
        contract.covered_elements[0].options = [self.Option(status='active',
                coverage=coverage) for x in range(2)]
        contract.activation_history[0].termination_reason = sub_status
        contract.activation_history = list(contract.activation_history)
        contract.save()
        self.assertEqual(len(contract.covered_elements[0].options), 2)
        self.Contract.do_terminate([contract])
        for option in contract.covered_elements[0].options:
            self.assertEqual(option.status, 'terminated')
            self.assertEqual(option.sub_status, sub_status)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
