# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
import copy
import datetime
import unittest
from decimal import Decimal

import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.exceptions import UserError
from trytond.server_context import ServerContext

from trytond.modules.coog_core import test_framework
from trytond.modules.rule_engine.tests.test_module import test_tree_element


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract_insurance'

    @classmethod
    def fetch_models_for(cls):
        return ['offered_insurance', 'contract']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'ExtraPremium': 'contract.option.extra_premium',
            'Contract': 'contract',
            'Option': 'contract.option',
            'ContractChangeStartDate': 'contract.change_start_date',
            'OptionSubscription': 'contract.wizard.option_subscription',
            'Coverage': 'offered.option.description',
            'CoveredElement': 'contract.covered_element',
            'CoveredElementVersion': 'contract.covered_element.version',
            'RuleEngineRuntime': 'rule_engine.runtime',
            'SubStatus': 'contract.sub_status',
            'EndReason': 'covered_element.end_reason',
            'EndReasonItemDescription':
            'offered.item.description-covered_element.end_reason',
            'SelectCoveredPackageView':
            'contract.wizard.option_subscription.select_package_per_covered',
            'Package': 'offered.package',
            }

    def test0001_testPersonCreation(self):
        party = self.Party()
        party.is_person = True
        party.name = 'DOE'
        party.first_name = 'John'
        party.birth_date = datetime.date(1980, 5, 30)
        party.gender = 'male'
        party.save()

        party = self.Party()
        party.is_person = True
        party.name = 'Antoine'
        party.first_name = 'Jeff'
        party.birth_date = datetime.date(1988, 7, 30)
        party.gender = 'male'
        party.save()

        party, = self.Party.search([('name', '=', 'DOE')])
        self.assertTrue(party.id)

    def test0002_quote_sequence_creation(self):
        qg = self.Sequence()
        qg.name = 'Quote Sequence'
        qg.code = 'quote'
        qg.prefix = 'Quo'
        qg.suffix = 'Y${year}'
        qg.save()

    @test_framework.prepare_test(
        'offered_insurance.test0010Coverage_creation',
        )
    def test0005_PrepareProductForSubscription(self):
        quote_sequence, = self.Sequence.search([('code', '=', 'quote')])

        product_a, = self.Product.search([('code', '=', 'AAA')])
        product_a.quote_number_sequence = quote_sequence
        product_a.save()

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
        self.assertTrue(contract.contract_number)
        self.assertEqual(contract.start_date, start_date)

    @test_framework.prepare_test(
        'contract_insurance.test0012_testContractCreation',
        'contract_insurance.test0001_testPersonCreation',
        )
    def test0013_testChangeStartDateWizardOptions(self):
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        contract, = self.Contract.search([])
        start_date = contract.start_date

        def set_test_case(new_date, ant_date, post_date, party):
            if (contract.covered_elements and
                    contract.covered_elements[0].options):
                for option in contract.covered_elements[0].options:
                    self.Option.delete([option])
            covered_element = self.CoveredElement()
            covered_element.item_desc = coverage_a.item_desc
            covered_element.contract = contract
            covered_element.product = covered_element.on_change_with_product()
            covered_element.party = party
            covered_element.save()

            option_cov_ant = self.Option()
            option_cov_ant.coverage = coverage_a.id
            option_cov_ant.manual_start_date = ant_date
            option_cov_ant.covered_element = covered_element
            option_cov_ant.save()

            option_cov_post = self.Option()
            option_cov_post.coverage = coverage_b.id
            option_cov_post.manual_start_date = post_date
            option_cov_post.covered_element = covered_element
            option_cov_post.save()

            # covered_element.options = [option_cov_ant.id, option_cov_post.id]
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
        party = self.Party.search([('is_person', '=', True)])[0]

        set_test_case(new_date, ant_date, post_date, party)

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
        party1 = self.Party.search([('is_person', '=', True)])[1]

        set_test_case(new_date, ant_date, post_date, party1)

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

        def set_test_case(new_date, fixed_date, party):

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
        party = self.Party.search([('is_person', '=', True)])[0]

        set_test_case(new_date, fixed_date, party)

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
        party1 = self.Party.search([('is_person', '=', True)])[1]

        set_test_case(new_date, fixed_date, party1)

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
        self.Option.delete(contract.covered_elements[0].options
            + contract.options)
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
                    option.parent_contract.check_options_dates)
            else:
                option.parent_contract.check_options_dates()
            self.Option.delete([option])

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

        # try setting manual start date anterior to contract initial start date
        test_option(automatic_end_date=date2, expected=date2, to_set=date1,
            start_date=early_date, should_raise=True)

        # try setting manual start date anterior to covered manual start date
        date4 = start_date + datetime.timedelta(weeks=1)
        covered_element.manual_start_date = start_date + datetime.timedelta(
            weeks=2)
        covered_element.save()

        self.assertRaises(UserError,
            test_option, automatic_end_date=date2, expected=date2, to_set=date1,
            start_date=date4, should_raise=True)

    @test_framework.prepare_test(
        'contract_insurance.test0012_testContractCreation',
        'contract_insurance.test0001_testPersonCreation',
    )
    def test_0020_testLastOptionEndsContract(self):
        # The ending date of a contract should be capped by
        # the max ending date of covered elements options
        contract, = self.Contract.search([])
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        current_end = contract.end_date
        end_option1 = current_end - datetime.timedelta(weeks=2)
        end_option2 = current_end - datetime.timedelta(weeks=4)

        def add_covered_element_with_options(parameters, party):
            covered_element = self.CoveredElement()
            covered_element.item_desc = coverage_a.item_desc
            covered_element.contract = contract
            covered_element.product = covered_element.on_change_with_product()
            covered_element.party = party
            covered_element.save()
            options = []
            for coverage, end_date in parameters:
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
            party = self.Party.search([('is_person', '=', True)])[0]
            party1 = self.Party.search([('is_person', '=', True)])[1]

            contract.covered_elements = [add_covered_element_with_options(
                    [(coverage_a, end_date1), (coverage_b, end_date2)], party),
                add_covered_element_with_options(
                    [(coverage_a, end_date1), (coverage_b, end_date2)], party1)
                ]

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
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        coverage_c, = self.Coverage.search([('code', '=', 'GAM')])

        covered_element = self.CoveredElement()
        covered_element.item_desc = coverage_a.item_desc
        covered_element.contract = contract
        covered_element.product = covered_element.on_change_with_product()
        party = self.Party.search([('is_person', '=', True)])[0]
        covered_element.party = party
        covered_element.save()
        contract.covered_element = [covered_element]
        contract.save()

        def make_option(coverage, manual_offset=None):
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

        option_no_offset = make_option(coverage_a)
        option_one_week = make_option(coverage_b, manual_offset=1)
        option_three_weeks = make_option(coverage_c, manual_offset=3)

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
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        contract, = self.Contract.search([])
        sub_status = self.SubStatus.search([('code', '=',
                    'reached_end_date')])[0]
        covered_element = self.CoveredElement()
        covered_element.contract = contract
        covered_element.item_desc = coverage_a.item_desc
        covered_element.product = covered_element.on_change_with_product()
        party = self.Party.search([('is_person', '=', True)])[0]
        covered_element.party = party
        covered_element.save()
        contract.covered_elements = [covered_element.id]
        contract.covered_elements[0].options = [
            self.Option(status='active', coverage=coverage_a),
            self.Option(status='active', coverage=coverage_b),
            ]
        contract.activation_history[0].termination_reason = sub_status
        contract.activation_history = list(contract.activation_history)
        contract.save()
        self.assertEqual(len(contract.covered_elements[0].options), 2)
        self.Contract.do_terminate([contract])
        contract = self.Contract(contract.id)
        for option in contract.covered_elements[0].options:
            self.assertEqual(option.status, 'terminated')
            self.assertEqual(option.sub_status, sub_status)

    @test_framework.prepare_test(
        'contract_insurance.test0012_testContractCreation'
        )
    def test0050_testOveralppingCoveredElements(self):

        def _test_prepare_data():
            """
                Factory method to prepare required data and
                 its dependencies for this test

            """
            party = self.Party(
                is_person=True,
                name='Von Neumann',
                first_name='John',
                birth_date=datetime.date(1980, 5, 30),
                gender='male'
                )
            party.save()

            party1 = self.Party(
                is_person=True,
                name='Alain',
                first_name='Turing',
                birth_date=datetime.date(1920, 5, 30),
                gender='male'
                )
            party1.save()

            party2 = self.Party(
                is_person=True,
                name='Leslie',
                first_name='Lamport',
                birth_date=datetime.date(1945, 5, 30),
                gender='male'
                )
            party2.save()

            party3 = self.Party(
                is_person=True,
                name='Edsger',
                first_name='Dijkstra',
                birth_date=datetime.date(1945, 5, 30),
                gender='male'
                )
            party3.save()

            contract, = self.Contract.search([])

            coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
            item_desc = coverage_a.item_desc

            end_reason = self.EndReason(code='contract_transfer',
                                        name='Contract Transfer')
            end_reason.item_descs = [item_desc]
            end_reason.save()

            return party, party1, party2, party3,\
                   contract, coverage_a, end_reason

        party, party1, party2, party3,\
             contract, coverage_a, end_reason = _test_prepare_data()

        def test_method_raises_an_error(func):
            """
                When we create a covered element
                this decorator will verify that if a User Error raises
                its message will be the message below
            """
            MSG = "You are trying to create a covered element " \
                  "that overlaps with an old covered element"

            def wrapper(*args, **kwargs):
                try:
                    value = func(*args, **kwargs)
                    return value
                except UserError as e:
                    self.assertEqual(e.message, MSG)
            return wrapper

        @test_method_raises_an_error
        def _make_covered_element(party, contract, coverage_a,
             has_parent=False, ended=False, **kwargs):

            """
                Create a covered element with a parent or without parent
            :param party:
            :param contract:
            :param coverage_a:
            :param has_parent: True if it has parent
            :param kwargs: the different attributes
            :return: covered element
            """

            covered_element = self.CoveredElement()
            covered_element.contract = contract
            covered_element.item_desc = coverage_a.item_desc
            covered_element.product = covered_element.on_change_with_product()
            if ended:
                covered_element.end_reason = kwargs["end_reason"]
                covered_element.manual_end_date = kwargs["manual_end_date"]
            if has_parent:
                covered_element.parent = kwargs["parent"]
                covered_element.manual_start_date = kwargs["manual_start_date"]
            covered_element.party = party
            covered_element.save()
            if has_parent is False:
                contract.covered_elements = [covered_element.id]
            contract.save()
            return covered_element

        covered_element = _make_covered_element(party, contract, coverage_a)
        sub_covered_1 = _make_covered_element(party1, contract, coverage_a,
                         has_parent=True,
                         parent=covered_element,
                         manual_start_date=datetime.date(2018, 5, 5),
                         manual_end_date=datetime.date(2018, 6, 6),
                         ended=True,
                         end_reason=end_reason)
        sub_covered_2 = _make_covered_element(party2, contract,
                         coverage_a, has_parent=True,
                         parent=covered_element,
                         manual_start_date=datetime.date(2018, 1, 1),
                         manual_end_date=datetime.date(2018, 2, 2),
                         end_reason=end_reason, ended=True)

        sub_covered_3 = _make_covered_element(party3, contract, coverage_a,
                        has_parent=True,
                        parent=covered_element,
                        manual_start_date=datetime.date(2016, 5, 5),
                        manual_end_date=None, ended=False)

        # """
        #     Tree Structure Professor and his students
        #     [+] Professor Von Neumann
        #         [-] Student 1 : Turing
        #         [-] Student 2 : Lamport
        #         [-] Student 3 : Dijkstra
        #
        # """

        result = [cov.party.first_name
                  for cov in covered_element.sub_covered_elements]
        expected_result = [sub_covered_1.party.first_name,
                           sub_covered_2.party.first_name,
                           sub_covered_3.party.first_name]
        self.assertEqual(result, expected_result)

        # Sub_covered_4 has party1 as party and it overlapps with sub_covered_1
        sub_covered_4 = _make_covered_element(party1, contract, coverage_a,
                        has_parent=True,
                        parent=covered_element,
                        manual_start_date=datetime.date(2018, 5, 15),
                        manual_end_date=None, end_reason=end_reason)

        self.assertEqual(sub_covered_4, None)

        # Sub_covered_5 does not overlap sub_covered_2
        sub_covered_12 = _make_covered_element(party2, contract, coverage_a,
                        has_parent=True, parent=covered_element,
                        manual_start_date=datetime.date(2018, 2, 3),
                        ended=True, manual_end_date=datetime.date(2018, 6, 18),
                        end_reason=end_reason)
        self.assertNotEqual(sub_covered_12, None)

    @test_framework.prepare_test(
        'contract_insurance.test0012_testContractCreation'
        )
    def test0051_void_contract_options(self):
        """
        Tests coherence between contract status and its options status
        when voiding a contract
        """
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        contract, = self.Contract.search([])
        covered_element = self.CoveredElement()
        covered_element.contract = contract
        covered_element.item_desc = coverage_a.item_desc
        party = self.Party.search([('is_person', '=', True)])[0]
        covered_element.party = party
        covered_element.save()
        first_option = self.Option(
            manual_start_date=contract.start_date,
            covered_element=covered_element,
            parent_contract=contract,
            coverage=coverage_a,
            )
        first_option.save()
        second_option = self.Option(
            manual_start_date=contract.start_date,
            covered_element=covered_element,
            parent_contract=contract,
            coverage=coverage_b,
            )
        second_option.save()
        # before void
        options_status = [option.status
            for covered_element in contract.covered_elements
            for option in covered_element.options
            ]
        self.assertEqual(options_status, ['active', 'active'])
        self.assertEqual(contract.status, 'active')
        void_reason, = self.SubStatus.search([('code', '=', 'error')])
        self.Contract.void([contract], void_reason)
        # after void
        options_status = [option.status
            for covered_element in contract.covered_elements
            for option in covered_element.options
            ]
        self.assertEqual(options_status, ['void', 'void'])
        self.assertEqual(contract.status, 'void')

    @test_framework.prepare_test(
        'contract_insurance.test0001_testPersonCreation',
        'contract_insurance.test0005_PrepareProductForSubscription',
        'contract.test0002_testCountryCreation',
        )
    def test0060_subscribe_contract_API(self):
        baby, = self.Party.search([('name', '=', 'Antoine'),
                ('first_name', '=', 'Jeff')])
        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Mother',
                    'birth_date': '1978-01-14',
                    'gender': 'female',
                    'addresses': [
                        {
                            'street': 'Somewhere along the street',
                            'zip': '75002',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        ],
                    'relations': [
                        {
                            'ref': '1',
                            'type': 'parent',
                            'to': {'id': baby.id},
                            },
                        ],
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'extra_data': {},
                    'covereds': [
                        {
                            'party': {'ref': '1'},
                            'item_descriptor': {'code': 'person'},
                            'coverages': [
                                {
                                    'coverage': {'code': 'ALP'},
                                    'extra_data': {},
                                    },
                                {
                                    'coverage': {'code': 'BET'},
                                    'extra_data': {},
                                    },
                                {
                                    'coverage': {'code': 'GAM'},
                                    'extra_data': {},
                                    },
                                ],
                            },
                        {
                            'party': {'id': baby.id},
                            'item_descriptor': {'code': 'person'},
                            'coverages': [
                                {
                                    'coverage': {'code': 'ALP'},
                                    'extra_data': {},
                                    },
                                {
                                    'coverage': {'code': 'BET'},
                                    'extra_data': {},
                                    },
                                ],
                            },
                        ],
                    'coverages': [
                        {
                            'coverage': {'code': 'DEL'},
                            'extra_data': {},
                            },
                        ],
                    },
                ],
            'options': {
                'activate': True,
                },
            }

        def check_result(data, result):
            mother, = self.Party.search([('name', '=', 'Doe'),
                    ('first_name', '=', 'Mother')])
            self.assertEqual(len(mother.relations), 1)
            self.assertEqual(mother.relations[0].to, baby)

            contract, = self.Contract.browse(
                [x['id'] for x in result['contracts']])

            self.assertEqual(len(contract.options), 1)
            self.assertEqual(contract.options[0].coverage.code, 'DEL')
            self.assertEqual(len(contract.covered_elements), 2)
            self.assertEqual(len(contract.covered_elements[0].options), 3)
            self.assertEqual(contract.covered_elements[0].party.id,
                result['parties'][0]['id'])

            self.assertEqual(len(contract.covered_elements[1].options), 2)
            self.assertEqual(contract.covered_elements[1].party.id, baby.id)

        data_dict = copy.deepcopy(data_ref)
        result = self.ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})
        check_result(data_dict, result)

        data_dict = copy.deepcopy(data_ref)
        data_dict['parties'][0]['name'] = 'Aunt'
        data_dict['parties'][0]['is_person'] = False
        del data_dict['parties'][0]['birth_date']
        del data_dict['parties'][0]['first_name']
        del data_dict['parties'][0]['gender']
        error = self.ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'bad_constraint',
                    'data': {
                        'field': 'covered.party',
                        'comment': 'Should be a person'},
                    }])

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['covereds'][0]['party']['ref'] = '12345'
        error = self.ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data[0], {
                    'type': 'bad_reference',
                    'data': {
                        'model': 'party.party',
                        'ref': '12345'},
                    })

        bad_item_desc = self.ItemDesc()
        bad_item_desc.kind = 'party'
        bad_item_desc.code = 'bad'
        bad_item_desc.name = 'Bad'
        bad_item_desc.save()

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['covereds'][0]['item_descriptor']['code'] = \
            'bad'
        error = self.ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data[0], {
                'type': 'invalid_item_desc_for_product',
                'data': {
                    'product': 'AAA',
                    'item_desc': 'bad',
                    'expected': ['person'],
                    },
                })

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['coverages'].append({
                'coverage': {'code': 'GAM'},
                'extra_data': {},
                })
        error = self.ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'invalid_coverage_for_product',
                    'data': {
                        'product': 'AAA',
                        'coverages': ['DEL', 'GAM'],
                        },
                    }])

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['covereds'][0]['coverages'].append({
                'coverage': {'code': 'DEL'},
                'extra_data': {},
                })
        error = self.ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data[0], {
                'type': 'invalid_coverage_for_covered',
                'data': {
                    'item_desc': 'person',
                    'coverages': ['ALP', 'BET', 'DEL', 'GAM'],
                    },
                })

        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['covereds'][1]['coverages'] = \
            data_dict['contracts'][0]['covereds'][1]['coverages'][:1]
        error = self.ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data[0], {
                'type': 'missing_mandatory_coverage',
                'data': {
                    'item_desc': 'person',
                    'coverages': ['ALP'],
                    'mandatory_coverages': ['ALP', 'BET'],
                    },
                })

    @test_framework.prepare_test(
        # Check that basic subscription still works
        'contract.test0100_subscribe_contract_API',
        )
    def test0070_subscribe_simple_contract_API(self):
        pass

    @test_framework.prepare_test(
        'contract_insurance.test0001_testPersonCreation',
        'offered_insurance.test0010Package_creation'
        )
    def test0080_subscription_by_package(self):
        product, = self.Product.search([
                ('code', '=', 'AAA'),
                ], limit=1)
        # create contract
        start_date = product.start_date + datetime.timedelta(weeks=4)
        contract = self.Contract(
            start_date=start_date,
            product=product.id,
            company=product.company.id,
            appliable_conditions_date=start_date,
            )
        contract.init_extra_data()
        contract.save()
        # create covered element
        party1, party2 = self.Party.search([('is_person', '=', True)])
        covered_element1 = self.CoveredElement()
        covered_element1.contract = contract
        covered_element1.item_desc = product.coverages[0].item_desc
        covered_element1.product = covered_element1.on_change_with_product()
        covered_element1.party = party1
        covered_element1_version = self.CoveredElementVersion()
        covered_element1_version.extra_data = {'extra_data_covered': None}
        covered_element1.versions = [covered_element1_version]
        covered_element1.save()
        covered_element2 = self.CoveredElement()
        covered_element2.contract = contract
        covered_element2.item_desc = product.coverages[0].item_desc
        covered_element2.product = covered_element2.on_change_with_product()
        covered_element2.party = party2
        covered_element2_version = self.CoveredElementVersion()
        covered_element2_version.extra_data = {'extra_data_covered': None}
        covered_element2.versions = [covered_element2_version]
        covered_element2.save()
        contract.covered_elements = [covered_element1, covered_element2]
        contract.save()
        self.assertTrue(len(contract.covered_elements) == 2)

        def apply_package(packages, contract):
            # packages could be a list in case of package per covered
            with Transaction().set_context(active_id=contract.id,
                    active_model='contract'):
                wizard_id, _, _ = self.OptionSubscription.create()
                wizard = self.OptionSubscription(wizard_id)
                wizard._execute('select_package')
                if len(packages) > 1:
                    views = []
                    wizard.select_package.covereds_package = []
                    for rank, selected in enumerate(packages):
                        view = self.SelectCoveredPackageView()
                        view.covered = contract.covered_elements[rank]
                        view.package = selected
                        views.append(view)
                    wizard.select_package.covereds_package = views
                else:
                    wizard.select_package.package = packages[0]
                wizard._execute('set_package')
        # apply package 1
        apply_package([product.packages[0]], contract)
        self.assertTrue(
            [a.coverage.code for c in contract.covered_elements
                for a in c.options] == ['ALP', 'BET', 'ALP', 'BET'])
        self.assertTrue([c.options[0].current_version.extra_data
                for c in contract.covered_elements] == [
                {'extra_data_coverage_alpha': 'option2'},
                {'extra_data_coverage_alpha': 'option2'}])
        # apply package 2
        apply_package([product.packages[1]], contract)
        self.assertEqual({a.coverage.code for a in contract.options},
            {'CONT', 'DEL'})
        self.assertEqual([a.current_version.extra_data
                for a in contract.options], [{}, {}])
        self.assertEqual(
            [a.coverage.code for c in contract.covered_elements
                for a in c.options], ['ALP', 'GAM', 'ALP', 'GAM'])
        self.assertEqual([c.options[0].current_version.extra_data
                for c in contract.covered_elements], [
                {'extra_data_coverage_alpha': 'option3'},
                {'extra_data_coverage_alpha': 'option3'}])
        self.assertEqual(contract.extra_datas[0].extra_data_values, {
                'extra_data_contract': 'formula2'})
        # apply package 3
        apply_package([product.packages[2]], contract)
        self.assertEqual(contract.extra_datas[0].extra_data_values, {
                'extra_data_contract': 'formula3'})
        self.assertEqual(len(contract.options), 1)
        self.assertEqual(
            [a.coverage.code for c in contract.covered_elements
                for a in c.options], ['GAM', 'GAM'])
        self.assertEqual([c.options[0].current_version.extra_data
                for c in contract.covered_elements], [{}, {}])

        # test package per covered
        packages = self.Package.search([('code', 'in', ('P1', 'P4'))])
        product.packages_defined_per_covered = True
        product.packages = packages
        product.save()

        # apply package 1 to covered1 and package 2 to covered2
        apply_package([product.packages[0], product.packages[1]], contract)
        self.assertEqual(len(contract.options), 1)
        self.assertEqual(
            [a.coverage.code for c in contract.covered_elements
                for a in c.options], ['ALP', 'BET', 'ALP', 'GAM'])
        self.assertEqual([c.options[0].current_version.extra_data
                for c in contract.covered_elements], [
                {'extra_data_coverage_alpha': 'option2'},
                {'extra_data_coverage_alpha': 'option1'}])
        self.assertEqual([c.versions[0].extra_data
                for c in contract.covered_elements], [
                {'extra_data_covered': None},
                {'extra_data_covered': 'covered3'}])
        # apply package 1 to covered1 and package 2 to covered2
        apply_package([product.packages[1], product.packages[0]], contract)
        self.assertEqual(
            [a.coverage.code for c in contract.covered_elements
                for a in c.options], ['ALP', 'GAM', 'ALP', 'BET'])
        self.assertEqual([c.versions[0].extra_data
                for c in contract.covered_elements], [
                {'extra_data_covered': 'covered3'},
                {'extra_data_covered': 'covered3'}])

    def test0200_test_api_rule_tree_elements(self):
        APIRuleRuntime = Pool().get('api.rule_runtime')
        with ServerContext().set_context(_test_api_tree_elements=True):
            with ServerContext().set_context(
                    api_rule_context=APIRuleRuntime.get_runtime()):
                self.assertEqual(test_tree_element(
                        'rule_engine.runtime',
                        '_re_get_subscriber_birthdate',
                        {
                            'api.parties': [{
                                    'ref': '1',
                                    'birth_date': datetime.date(2000, 1, 1),
                                    }],
                            'api.contract': {'subscriber': {'ref': '1'}}}
                        ).result,
                    datetime.date(2000, 1, 1))

                self.assertEqual(test_tree_element(
                        'rule_engine.runtime',
                        '_re_get_option_initial_start_date',
                        {
                            'api.contract': {
                                'start_date': datetime.date(2000, 1, 1)},
                            'api.option': {'coverage': {'code': 'my_coverage'}},
                            }
                        ).result,
                    datetime.date(2000, 1, 1))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
