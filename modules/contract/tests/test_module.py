# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
import copy
from decimal import Decimal
from dateutil.relativedelta import relativedelta

import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.pool import Pool
from trytond.server_context import ServerContext

from trytond.modules.coog_core import test_framework
from trytond.modules.rule_engine.tests.test_module import test_tree_element


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'contract'

    @classmethod
    def fetch_models_for(cls):
        return ['offered']

    @classmethod
    def get_models(cls):
        return {
            'Address': 'party.address',
            'Country': 'country.country',
            'Contact': 'contract.contact',
            'ZipCode': 'country.zip',
            'Party': 'party.party',
            'Contract': 'contract',
            'Option': 'contract.option',
            'ActivationHistory': 'contract.activation_history',
            'ContractChangeStartDate': 'contract.change_start_date',
            'Coverage': 'offered.option.description',
            'ContractExtraData': 'contract.extra_data',
            'SubStatus': 'contract.sub_status',
            'ContactType': 'contract.contact.type',
            'ContractAPI': 'api.contract',
            'RuleEngine': 'rule_engine',
            }

    def createContactTypes(self):
        to_create = []
        for code in ('subscriber', 'covered_party'):
            to_create.append(self.ContactType(code=code, name='dummy'))
        self.ContactType.save(to_create)

    def test0001_testPersonCreation(self):
        party = self.Party()
        party.is_person = True
        party.name = 'DOE'
        party.first_name = 'John'
        party.birth_date = datetime.date(1980, 5, 30)
        party.gender = 'male'
        party.save()

        country = self.Country(name="Oz", code='OZ')
        country.save()
        address = self.Address(party=party, zip="1", country=country,
            city="Emerald")
        address.save()
        party.addresses = [address.id]
        party.save()

        party, = self.Party.search([('name', '=', 'DOE')])
        self.assertTrue(party.id)

    def test0002_testCountryCreation(self):
        self.Country(
            code='FR',
            code3='FRA',
            name='France',
            ).save()

    def test0005_PrepareProductForSubscription(self):
        quote_sequence = self.Sequence.search([('code', '=', 'quote')])
        if quote_sequence:
            quote_sequence = quote_sequence[0]
        else:
            quote_sequence = self.Sequence()
            quote_sequence.name = 'Quote Sequence'
            quote_sequence.code = 'quote'
            quote_sequence.prefix = 'Quo'
            quote_sequence.suffix = 'Y${year}'
            quote_sequence.save()

        for product in self.Product.search([]):
            product.quote_number_sequence = quote_sequence
            product.save()

    @test_framework.prepare_test('contract.test0001_testPersonCreation',
        'offered.test0030_testProductCoverageRelation',
        'contract.test0005_PrepareProductForSubscription'
        )
    def test0010_testContractCreation(self):
        sub_status, = self.SubStatus.search([
                ('code', '=', 'reached_end_date')])
        product, = self.Product.search([
                ('code', '=', 'AAA'),
                ])
        start_date = product.start_date + datetime.timedelta(weeks=4)
        end_date = start_date + datetime.timedelta(weeks=52)
        contract = self.Contract(
            product=product.id,
            company=product.company.id,
            start_date=start_date,
            appliable_conditions_date=start_date,
            )
        contract.save()
        self.assertEqual(contract.status, 'quote')
        self.assertEqual(len(contract.activation_history), 1)
        self.assertEqual(contract.activation_history[0].start_date, start_date)
        self.assertEqual(contract.start_date, start_date)
        contract.end_date = end_date
        contract.save()
        self.assertEqual(contract.end_date, end_date)
        self.assertEqual(contract.start_date, start_date)
        self.assertEqual(len(contract.activation_history), 1)
        self.assertEqual(contract.activation_history[0].end_date, end_date)
        contract.activation_history[0].termination_reason = sub_status
        contract.activation_history = list(contract.activation_history)
        contract.save()
        self.assertEqual(contract.termination_reason, sub_status)
        contract.activate_contract()
        contract.end_date = end_date
        contract.save()
        self.assertEqual(contract.status, 'active')
        self.assertTrue(contract.contract_number)
        self.assertEqual(contract.start_date, start_date)
        self.assertEqual(contract.end_date, end_date)

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        )
    def test0011_testContractTermination(self):
        contract, = self.Contract.search([])
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        contract.options = [
            self.Option(status='active', coverage=coverage_a),
            self.Option(status='active', coverage=coverage_a),
            ]
        self.assertRaises(UserError, contract.save)
        contract.options[1].coverage = coverage_b
        contract.save()

        sub_status = self.SubStatus.search([('code', '=',
                    'reached_end_date')])[0]
        self.Contract.do_terminate([contract])
        self.assertEqual(contract.status, 'terminated')
        self.assertEqual(contract.sub_status, sub_status)
        self.assertEqual(len(contract.options), 2)
        for option in contract.options:
            self.assertEqual(option.status, 'terminated')
            self.assertEqual(option.sub_status, sub_status)

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        )
    def test0015_testRevertToProject(self):
        contract, = self.Contract.search([])
        start_date = contract.start_date
        self.assertEqual(contract.status, 'active')
        contract.extra_datas = [
            self.ContractExtraData(start=None),
            self.ContractExtraData(
                start=start_date + datetime.timedelta(weeks=10)),
            ]
        contract.save()
        good_extra_id = contract.extra_datas[-1].id
        self.Contract.revert_to_project([contract])
        self.assertEqual(contract.status, 'quote')
        self.assertEqual(len(contract.extra_datas), 1)
        self.assertEqual(contract.extra_datas[0].id, good_extra_id)

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        )
    def test0020_testChangeStartDateWizard(self):
        contract, = self.Contract.search([])
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        start_date = contract.start_date

        def set_test_case(new_date, ant_date, post_date):
            if contract.options:
                for option in contract.options:
                    self.Option.delete([option])
            option_ant = self.Option()
            option_ant.manual_start_date = ant_date
            option_ant.coverage = coverage_a.id
            option_ant.save()
            option_post = self.Option()
            option_post.manual_start_date = post_date
            option_post.coverage = coverage_b.id
            option_post.save()
            contract.options = [option_ant.id, option_post.id]
            contract.save()
            with Transaction().set_context(active_id=contract.id):
                wizard_id, _, _ = self.ContractChangeStartDate.create()
                wizard = self.ContractChangeStartDate(wizard_id)
                wizard._execute('change_date')
                wizard.change_date.new_start_date = new_date
                wizard.change_date.on_change_new_start_date()
                wizard._execute('apply')
            return [option_ant, option_post]

        # case 1 : new date posterior to start_date
        new_date = start_date + datetime.timedelta(weeks=2)
        ant_date = new_date - datetime.timedelta(weeks=1)
        post_date = new_date + datetime.timedelta(weeks=1)

        option_ant, option_post = set_test_case(new_date, ant_date, post_date)

        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(option_ant.start_date, new_date)
        self.assertEqual(option_post.start_date, post_date)

        # case 2 : new date anterior to start_date
        contract.start_date = start_date
        contract.save()
        new_date = start_date - datetime.timedelta(weeks=2)
        ant_date = new_date - datetime.timedelta(weeks=1)
        post_date = new_date + datetime.timedelta(weeks=1)

        option_ant, option_post = set_test_case(new_date, ant_date, post_date)

        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(option_ant.start_date, new_date)
        self.assertEqual(option_post.start_date, post_date)

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        )
    def test0030_testOptionEndDate(self):
        start_date = datetime.date(2012, 2, 15)
        auto_date = start_date + datetime.timedelta(weeks=50)
        manual_date = start_date + datetime.timedelta(weeks=60)
        test_date = start_date + datetime.timedelta(weeks=30)
        contract_end_date = start_date + datetime.timedelta(weeks=70)
        early_date = start_date - datetime.timedelta(weeks=1)
        late_date = contract_end_date + datetime.timedelta(weeks=1)

        coverage, = self.Coverage.search([('code', '=', 'ALP')])

        contract = self.Contract(
                    product=self.Contract.search([])[0].product,
                    company=self.Contract.search([])[0].company,
                    start_date=start_date)
        contract.save()
        contract.end_date = contract_end_date
        contract.save()

        def test_option(automatic_end_date=None, manual_end_date=None,
                expected=None, should_raise=False,
                to_set=None, should_set=True):
            option = self.Option(
                status='active',
                automatic_end_date=automatic_end_date,
                manual_end_date=manual_end_date,
                contract=contract,
                coverage=coverage,
                )
            option.parent_contract = option.contract
            option.contract.end_date = contract_end_date
            self.assertEqual(option.loader_end_date('end_date'), expected)
            option.contract.options = [option]
            option.manual_end_date = to_set
            option.sub_status = \
                option.on_change_with_sub_status()
            option.save()

            if option.manual_end_date:
                self.assertEqual(option.sub_status.code, 'terminated')
            else:
                self.assertIsNone(option.sub_status)

            # test check
            if should_raise:
                self.assertRaises(UserError,
                    option.contract.check_options_dates)
            else:
                option.contract.check_options_dates()

            self.Option.delete([option])

        # option with auto date
        test_option(automatic_end_date=auto_date, expected=auto_date,
            to_set=test_date, should_set=True)

        # option with manual date
        test_option(automatic_end_date=auto_date, manual_end_date=manual_date,
            expected=min(manual_date, auto_date), to_set=test_date,
            should_set=True)

        # option with no end date at all
        test_option(expected=contract_end_date, to_set=test_date,
            should_set=True)

        # try setting setting end date anterior to start date
        test_option(expected=contract_end_date, to_set=early_date,
            should_raise=True)

        # try setting setting end date posterior to contract end date
        test_option(expected=contract_end_date, to_set=late_date,
            should_raise=True)

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        )
    def test0040_maximum_end_date(self):
        contract, = self.Contract.search([])
        current_end = contract.end_date
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        end_option1 = current_end - datetime.timedelta(weeks=2)
        end_option2 = current_end - datetime.timedelta(weeks=4)

        def get_options(parameters):
            options = []
            for coverage, end_date in parameters:
                option = self.Option(
                        start_date=contract.start_date,
                        automatic_end_date=end_date,
                        manual_end_date=end_date,
                        end_date=end_date,
                        contract=contract,
                        parent_contract=contract,
                        coverage=coverage,
                        )
                option.sub_status = \
                    option.on_change_with_sub_status()
                options.append(option)
            return options

        # If the end dates of every options are below the contract
        # end date, the maximum end_date is the latest option end date.
        contract.options = get_options(
            [(coverage_a, end_option1), (coverage_b, end_option2)])
        self.Contract.calculate_activation_dates([contract])
        contract.save()
        self.assertEqual(contract.end_date, end_option1)

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        )
    def test0050_searcher_start_date(self):
        contract, = self.Contract.search([])
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        coverage_c, = self.Coverage.search([('code', '=', 'GAM')])

        def make_option(coverage, manual_offset=None):
            if manual_offset:
                my_offset = relativedelta(weeks=manual_offset)
                option = self.Option(
                        manual_start_date=contract.start_date + my_offset,
                        contract=contract,
                        parent_contract=contract,
                        coverage=coverage,
                        )
                option.save()
            else:
                option = self.Option(
                        contract=contract,
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
        'contract.test0010_testContractCreation',
        )
    def test0060_activation_history_getters_and_searcher(self):
        years = (2010, 2011, 2012, 2013)
        contract, = self.Contract.search([])
        contract.activation_history = [self.ActivationHistory(start_date=x,
                end_date=x + relativedelta(years=1, days=-1)) for x in
            (datetime.date(y, 1, 1) for y in years)]
        sub_status, = self.SubStatus.search([
                ('code', '=', 'reached_end_date')])
        contract.activation_history[-1].termination_reason = sub_status
        contract.save()
        self.assertEqual(len(contract.activation_history), 4)

        # test consultation in middle of periods
        for i, y in enumerate(years):
            self.assertEqual(contract.activation_history[i].start_date,
                datetime.date(y, 1, 1))
            self.assertEqual(contract.activation_history[i].end_date,
                datetime.date(y, 12, 31))
            with Transaction().set_context(client_defined_date=datetime.date(
                        y, 6, 1)):
                contract = self.Contract(contract.id)
                self.assertEqual(contract.start_date, datetime.date(y, 1, 1))
                self.assertEqual(contract.end_date, datetime.date(y, 12, 31))
                self.assertEqual(contract.termination_reason,
                    sub_status)

        # test consultation on last day of periods
        for y in years:
            with Transaction().set_context(client_defined_date=datetime.date(
                        y, 12, 31)):
                contract = self.Contract(contract.id)
                self.assertEqual(contract.start_date, datetime.date(y, 1, 1))
                self.assertEqual(contract.end_date, datetime.date(y, 12, 31))
                contracts = contract.__class__.search([
                        ('start_date', '=', datetime.date(y, 1, 1)),
                        ('end_date', '=', datetime.date(y, 12, 31)),
                        ])
                self.assertEqual(contracts[0], contract)

        # test consultation on first day of periods
        for y in years:
            with Transaction().set_context(client_defined_date=datetime.date(
                        y, 1, 1)):
                contract = self.Contract(contract.id)
                self.assertEqual(contract.start_date, datetime.date(y, 1, 1))
                self.assertEqual(contract.end_date, datetime.date(y, 12, 31))
                contracts = contract.__class__.search([
                        ('start_date', '=', datetime.date(y, 1, 1)),
                        ('end_date', '=', datetime.date(y, 12, 31)),
                        ])
                self.assertEqual(contracts[0], contract)

        # test consultation before first periods
        with Transaction().set_context(client_defined_date=datetime.date(
                    2009, 6, 1)):
            contract = self.Contract(contract.id)
            self.assertEqual(contract.start_date, datetime.date(2010, 1, 1))
            self.assertEqual(contract.end_date, datetime.date(2010, 12, 31))
            contracts = contract.__class__.search([
                    ('start_date', '=', datetime.date(2010, 1, 1)),
                    ('end_date', '=', datetime.date(2010, 12, 31)),
                    ])
            self.assertEqual(contracts[0], contract)

        # test consultation after last period
        with Transaction().set_context(client_defined_date=datetime.date(
                    2014, 6, 1)):
            contract = self.Contract(contract.id)
            self.assertEqual(contract.start_date, datetime.date(2013, 1, 1))
            self.assertEqual(contract.end_date, datetime.date(2013, 12, 31))
            contracts = contract.__class__.search([
                    ('start_date', '=', datetime.date(2013, 1, 1)),
                    ('end_date', '=', datetime.date(2013, 12, 31)),
                    ])
            self.assertEqual(contracts[0], contract)

        # test consultation on last day of periods
        for y in years:
            with Transaction().set_context(client_defined_date=datetime.date(
                        y, 12, 31)):
                contract = self.Contract(contract.id)
                contracts = contract.__class__.search([
                        ('initial_start_date', '=', datetime.date(2010, 1, 1)),
                        ])
                self.assertEqual(contracts[0], contract)

    @test_framework.prepare_test('contract.test0001_testPersonCreation')
    def test0060_get_contacts(self):
        party, = self.Party.search([('name', '=', 'DOE')])
        subscriber_type, = self.ContactType.search(
            [('code', '=', 'subscriber')])
        covered_party_type = self.ContactType(
            code='covered_party',
            name='Covered Party')
        covered_party_type.save()
        today = datetime.date.today()
        contract = self.Contract(subscriber=party)
        contact1 = self.Contact(
            party=party,
            address=None,
            date=None,
            end_date=today + relativedelta(days=-30),
            type=subscriber_type)
        contact1.type_code = contact1.on_change_with_type_code()
        contact2 = self.Contact(
            party=party,
            address=None,
            date=today + relativedelta(days=-29),
            end_date=today + relativedelta(days=-5),
            type=subscriber_type)
        contact2.type_code = contact2.on_change_with_type_code()
        contact3 = self.Contact(
            party=party,
            address=None,
            date=None,
            end_date=None,
            type=covered_party_type.id)
        contact3.type_code = contact3.on_change_with_type_code()
        contract.contacts = (contact1, contact2, contact3)
        contacts = contract.get_contacts(type_='subscriber',
            date=today + relativedelta(days=-100))
        self.assertEqual(contacts, [contact1])
        contacts = contract.get_contacts(type_='subscriber',
            date=today + relativedelta(days=-25))
        self.assertEqual(contacts, [contact2])
        contacts = contract.get_contacts(type_='covered_party')
        self.assertEqual(contacts, [contact3])
        contacts = contract.get_contacts(type_='subscriber')
        self.assertEqual(contacts[0].party, party)
        contact4 = self.Contact(
            party=party,
            address=None,
            date=today,
            end_date=None,
            type=subscriber_type)
        contact4.type_code = contact4.on_change_with_type_code()
        contract.contacts = (contact1, contact2, contact3, contact4)
        contacts = contract.get_contacts(type_='subscriber')
        self.assertEqual(contacts, [contact4])

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        )
    def test0070_void_option_dates(self):
        contract, = self.Contract.search([])
        coverage, = self.Coverage.search([('code', '=', 'ALP')])
        sub_status, = self.SubStatus.search([('code', '=', 'error')])
        option = self.Option(status='void', contract=contract,
            manual_start_date=datetime.date(1999, 9, 1),
            manual_end_date=datetime.date(2001, 9, 1),
            coverage=coverage, sub_status=sub_status)
        option.save()
        self.assertEqual(option.end_date, None)
        self.assertEqual(option.start_date, None)

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation'
        )
    def test0080_void_contract_options(self):
        """
            Tests coherence between contract status and its options status
             when voiding a contract
        """
        contract, = self.Contract.search([])
        coverage, = self.Coverage.search([('code', '=', 'ALP')])
        option = self.Option(
            manual_start_date=contract.start_date,
            contract=contract,
            parent_contract=contract,
            coverage=coverage,
            status='quote',
            )
        option.save()
        self.assertEqual(option.status, 'quote')
        contracts = [contract]
        void_reason, = self.SubStatus.search([('code', '=', 'error')])
        self.Contract.void(contracts, void_reason)
        self.assertEqual(option.status, 'void')

    @test_framework.prepare_test(
        'contract.test0001_testPersonCreation',
        'offered.test0030_testProductCoverageRelation',
        )
    def test0090_testSubscriptionBehavior(self):
        product, = self.Product.search([
                ('code', '=', 'AAA'),
                ])
        coverage_a, = self.Coverage.search([('code', '=', 'ALP')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        rule, = self.RuleEngine.search([
                ('short_name', '=', 'default_subscription_rule')])
        coverage_a.subscription_rule = rule
        coverage_a.subscription_rule_extra_data = {
            'subscription_behaviour': 'mandatory',
            'required_options': '',
            'excluded_options': '',
            }
        coverage_a.save()
        coverage_b.subscription_rule = rule
        coverage_b.subscription_rule_extra_data = {
            'subscription_behaviour': 'defaulted',
            'required_options': 'ALP',
            'excluded_options': '',
            }
        coverage_b.save()
        start_date = product.start_date + datetime.timedelta(weeks=4)
        contract = self.Contract(
            product=product.id,
            company=product.company.id,
            start_date=start_date,
            appliable_conditions_date=start_date,
            quote_number='1111111',
            )
        contract.save()
        contract.init_from_product(product)
        self.assertEqual([o.coverage.code for o in contract.options],
            ['ALP', 'BET'])

        coverage_b.subscription_rule = rule
        coverage_b.subscription_rule_extra_data = {
            'subscription_behaviour': 'optional',
            'required_options': 'ALP',
            'excluded_options': '',
            }
        coverage_b.save()

        contract = self.Contract(
            product=product.id,
            company=product.company.id,
            start_date=start_date,
            appliable_conditions_date=start_date,
            quote_number='1111112',
            )
        contract.save()
        contract.init_from_product(product)
        self.assertEqual([o.coverage.code for o in contract.options], ['ALP'])

    @test_framework.prepare_test(
        'contract.test0090_testSubscriptionBehavior',
        'contract.test0002_testCountryCreation',
        'contract.test0005_PrepareProductForSubscription',
        )
    def test0095_testAutomaticCleanOptions(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')

        rule, = self.RuleEngine.search([
                ('short_name', '=', 'default_subscription_rule')])
        coverage_b, = self.Coverage.search([('code', '=', 'BET')])
        coverage_b.subscription_rule = rule
        coverage_b.subscription_rule_extra_data = {
            'subscription_behaviour': 'not_subscriptable',
            'required_options': '',
            'excluded_options': '',
            }
        coverage_b.save()

        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Richard',
                    'birth_date': '1980-01-20',
                    'gender': 'male',
                    'addresses': [
                        {
                            'street': 'Somewhere along the street',
                            'zip': '75002',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        ],
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'extra_data': {
                        'contract_1': '16.10',
                        'contract_2': False,
                        'contract_3': '2',
                        },
                    'coverages': [
                        {
                            'coverage': {'code': 'ALP'},
                            'extra_data': {
                                'option_1': '6.10',
                                'option_2': True,
                                'option_3': '2',
                                },
                            },
                        {
                            'coverage': {'code': 'BET'},
                            'extra_data': {},
                            },
                        ],
                    },
                ],
            'options': {
                'auto_remove_not_subscriptable': True,
                },
            }

        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})

        contract, = self.Contract.browse(
            [x['id'] for x in result['contracts']])
        self.assertEqual(contract.product.code, 'AAA')
        self.assertEqual(len(contract.options), 1)
        self.assertEqual(contract.options[0].coverage.code, 'ALP')

        coverage_b.subscription_rule = rule
        coverage_b.subscription_rule_extra_data = {
            'subscription_behaviour': 'defaulted',
            'required_options': 'ALP,GAM',
            'excluded_options': '',
            }
        coverage_b.save()
        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})
        contract, = self.Contract.browse(
            [x['id'] for x in result['contracts']])
        self.assertEqual(len(contract.options), 1)
        self.assertEqual(contract.options[0].coverage.code, 'ALP')

        coverage_b.subscription_rule = rule
        coverage_b.subscription_rule_extra_data = {
            'subscription_behaviour': 'defaulted',
            'required_options': '',
            'excluded_options': 'ALP',
            }
        coverage_b.save()
        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})
        contract, = self.Contract.browse(
            [x['id'] for x in result['contracts']])
        self.assertEqual(len(contract.options), 1)
        self.assertEqual(contract.options[0].coverage.code, 'ALP')

        coverage_b.subscription_rule_extra_data = {
            'subscription_behaviour': 'optionnal',
            'required_options': '',
            'excluded_options': '',
            }
        coverage_b.save()
        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})
        contract, = self.Contract.browse(
            [x['id'] for x in result['contracts']])
        self.assertEqual(len(contract.options), 2)
        self.assertEqual({x.coverage.code for x in contract.options},
            {'ALP', 'BET'})

    @test_framework.prepare_test(
        'offered.test0030_testProductCoverageRelation',
        'contract.test0002_testCountryCreation',
        'contract.test0005_PrepareProductForSubscription',
        )
    def test0100_subscribe_contract_API(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')

        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Father',
                    'birth_date': '1980-01-20',
                    'gender': 'male',
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
                            'ref': '3',
                            'type': 'child',
                            'to': {'ref': '3'},
                            },
                        ],
                    },
                {
                    'ref': '2',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Baby',
                    'birth_date': '2010-02-12',
                    'gender': 'female',
                    },
                {
                    'ref': '3',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Grand-Pa',
                    'birth_date': '1920-04-08',
                    'gender': 'male',
                    },
                ],
            'relations': [
                {
                    'ref': '1',
                    'type': 'child',
                    'from': {'ref': '2'},
                    'to': {'ref': '1'},
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'extra_data': {
                        'contract_1': '16.10',
                        'contract_2': False,
                        'contract_3': '2',
                        },
                    'coverages': [
                        {
                            'coverage': {'code': 'ALP'},
                            'extra_data': {
                                'option_1': '6.10',
                                'option_2': True,
                                'option_3': '2',
                                },
                            },
                        {
                            'coverage': {'code': 'BET'},
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
            party_1 = self.Party([
                    x for x in result['parties'] if x['ref'] == '1'][0]['id'])
            party_data_1 = [x for x in data['parties'] if x['ref'] == '1'][0]
            self.assertEqual(party_1.is_person, party_data_1['is_person'])
            self.assertEqual(party_1.name, party_data_1['name'])
            self.assertEqual(party_1.first_name, party_data_1['first_name'])
            self.assertEqual(party_1.birth_date, party_data_1['birth_date'])
            self.assertEqual(party_1.gender, party_data_1['gender'])
            self.assertIsNotNone(party_1.id)
            self.assertIsNotNone(party_1.code)
            self.assertEqual(len(party_1.addresses), 1)
            self.assertEqual(party_1.addresses[0].full_address,
                'Somewhere along the street\n75002 Paris\nFRANCE')

            party_2 = self.Party([
                    x for x in result['parties'] if x['ref'] == '2'][0]['id'])
            party_data_2 = [x for x in data['parties'] if x['ref'] == '2'][0]
            self.assertEqual(party_2.is_person, party_data_2['is_person'])
            self.assertEqual(party_2.name, party_data_2['name'])
            self.assertEqual(party_2.first_name, party_data_2['first_name'])
            self.assertEqual(party_2.birth_date, party_data_2['birth_date'])
            self.assertEqual(party_2.gender, party_data_2['gender'])
            self.assertIsNotNone(party_2.id)
            self.assertIsNotNone(party_2.code)

            party_3 = self.Party([
                    x for x in result['parties'] if x['ref'] == '3'][0]['id'])

            relation, = party_2.relations
            self.assertEqual(relation.type.code, 'child')
            self.assertEqual(relation.to.id, party_1.id)
            self.assertEqual(relation.from_.id, party_2.id)

            relation = party_1.relations[1]
            self.assertEqual(relation.type.code, 'child')
            self.assertEqual(relation.to.id, party_3.id)
            self.assertEqual(relation.from_.id, party_1.id)

            contract, = self.Contract.browse(
                [x['id'] for x in result['contracts']])

            self.assertEqual(contract.product.code, 'AAA')
            self.assertEqual(contract.subscriber.id, party_1.id)
            self.assertEqual(len(contract.extra_datas), 1)
            self.assertEqual(contract.extra_datas[0].extra_data_values,
                {
                    'contract_1': Decimal('16.10'),
                    'contract_2': False,
                    'contract_3': '2',
                    })

            self.assertEqual(len(contract.options), 2)
            self.assertEqual(contract.options[0].coverage.code, 'ALP')
            self.assertEqual(len(contract.options[0].versions), 1)
            self.assertEqual(contract.options[0].versions[0].extra_data,
                {
                    'option_1': Decimal('6.10'),
                    'option_2': True,
                    'option_3': '2',
                    },
                )
            self.assertEqual(contract.options[1].coverage.code, 'BET')
            self.assertEqual(len(contract.options[1].versions), 1)
            self.assertEqual(contract.options[1].versions[0].extra_data, {})

        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})
        check_result(data_dict, result)

        # Check Bad Reference to subscriber
        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['subscriber']['ref'] = '10'
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'bad_reference',
                    'data': {
                        'model': 'party.party',
                        'ref': '10',
                        },
                    }])

        # Check inexisting product
        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['product']['code'] = 'foo'
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data[0], {
                'type': 'configuration_not_found',
                'data': {
                    'code': 'foo',
                    'model': 'offered.product',
                    },
                })

        # Check missing extra_data
        data_dict = copy.deepcopy(data_ref)
        del data_dict['contracts'][0]['extra_data']['contract_1']
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'invalid_extra_data_for_product',
                    'data': {
                        'product': 'AAA',
                        'extra_data': ['contract_2', 'contract_3'],
                        'expected_keys': ['contract_1', 'contract_2',
                            'contract_3'],
                        },
                    }])

        # Check extra extra_data
        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['extra_data']['option_1'] = '1.21'
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'extra_data_business_kind',
                    'data': {
                        'extra_data': 'option_1',
                        'expected_business_kinds': ['contract'],
                        },
                    },
                    {
                    'type': 'invalid_extra_data_for_product',
                    'data': {
                        'product': 'AAA',
                        'extra_data': ['contract_1', 'contract_2', 'contract_3',
                            'option_1'],
                        'expected_keys': ['contract_1', 'contract_2',
                            'contract_3'],
                        },
                    }])

        # Check missing mandatory coverage
        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['coverages'].pop()
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'missing_mandatory_coverage',
                    'data': {
                        'product': 'AAA',
                        'coverages': ['ALP'],
                        'mandatory_coverages': ['ALP', 'BET'],
                        },
                    }])

        # Check missing coverage extra_data
        data_dict = copy.deepcopy(data_ref)
        del data_dict['contracts'][0]['coverages'][0]['extra_data']['option_1']
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'invalid_extra_data_for_coverage',
                    'data': {
                        'coverage': 'ALP',
                        'extra_data': ['option_2', 'option_3'],
                        'expected_keys': ['option_1', 'option_2',
                            'option_3'],
                        },
                    }])

        # Check extra coverage extra_data
        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['coverages'][0]['extra_data']['contract_1'] \
            = '13.21'
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'extra_data_business_kind',
                    'data': {
                        'extra_data': 'contract_1',
                        'expected_business_kinds': ['option'],
                        },
                    },
                    {
                    'type': 'invalid_extra_data_for_coverage',
                    'data': {
                        'coverage': 'ALP',
                        'extra_data': ['contract_1', 'option_1', 'option_2',
                            'option_3'],
                        'expected_keys': ['option_1', 'option_2',
                            'option_3'],
                        },
                    }])

    @test_framework.prepare_test(
        'contract.test0002_testCountryCreation',
        'offered.test0035_testProductPackages',
        'contract.test0005_PrepareProductForSubscription',
        )
    def test0105_subscribe_package_contract_API(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')

        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Father',
                    'birth_date': '1980-01-20',
                    'gender': 'male',
                    'addresses': [
                        {
                            'street': 'Somewhere along the street',
                            'zip': '75002',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        ],
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'extra_data': {
                        'contract_2': False,
                        'contract_3': '2',
                        },
                    'package': {'code': 'package_a'},
                    'coverages': [
                        {
                            'coverage': {'code': 'ALP'},
                            'extra_data': {
                                'option_1': '6.10',
                                'option_2': True,
                                },
                            },
                        ],
                    },
                ],
            }

        def check_result(data, result):
            contract = self.Contract(result['contracts'][0]['id'])

            self.assertEqual(len(contract.extra_datas), 1)
            self.assertEqual(contract.extra_datas[0].extra_data_values,
                {
                    'contract_1': Decimal('16.10'),
                    'contract_2': False,
                    'contract_3': '2',
                    })

            self.assertEqual(len(contract.options), 2)
            self.assertEqual(contract.options[0].coverage.code, 'ALP')
            self.assertEqual(len(contract.options[0].versions), 1)
            self.assertEqual(contract.options[0].versions[0].extra_data,
                {
                    'option_1': Decimal('6.10'),
                    'option_2': True,
                    'option_3': '2',
                    },
                )
            self.assertEqual(contract.options[1].coverage.code, 'BET')
            self.assertEqual(len(contract.options[1].versions), 1)
            self.assertEqual(contract.options[1].versions[0].extra_data, {})

        data_dict = copy.deepcopy(data_ref)
        result = ContractAPI.subscribe_contracts(data_dict,
            {'_debug_server': True})
        check_result(data_dict, result)

        # Check package extra data conflict
        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['extra_data']['contract_1'] = '1.20'
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'manual_package_extra_data',
                    'data': {
                        'product': 'AAA',
                        'package': 'package_a',
                        'extra_data': ['contract_1'],
                        },
                    }])
        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['coverages'][0]['extra_data'][
            'option_3'] = '1'
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'manual_package_extra_data',
                    'data': {
                        'coverage': 'ALP',
                        'package': 'package_a',
                        'extra_data': ['option_3'],
                        },
                    }])

        # Check manual extra coverage conflict
        data_dict = copy.deepcopy(data_ref)
        data_dict['contracts'][0]['coverages'].append({
                'coverage': {'code': 'GAM'},
                })
        error = ContractAPI.subscribe_contracts(data_dict, {})
        self.assertEqual(error.data, [{
                    'type': 'package_with_manual_coverages',
                    'data': {
                        'package': 'package_a',
                        'package_contents': ['ALP', 'BET'],
                        'manual_coverage': 'GAM',
                        },
                    }])

        # Now, test multiselection extra data

        Product = pool.get('offered.product')
        Coverage = pool.get('offered.option.description')
        aaa, = Product.search([('code', '=', 'AAA')])
        alpha, = Coverage.search([('code', '=', 'ALP')])

        option_multi_extra = self.ExtraData()
        option_multi_extra.name = 'my_choices'
        option_multi_extra.string = 'Contract 2'
        option_multi_extra.kind = 'option'
        option_multi_extra.type_ = 'multiselection'
        option_multi_extra.selection = 'a: A\nb:B\nc:C'
        option_multi_extra.save()

        alpha.extra_data_def = [option_multi_extra]
        alpha.save()

        aaa.coverages = [alpha]
        aaa.save()

        multi_selection_data = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Father',
                    'birth_date': '1980-01-20',
                    'gender': 'male',
                    'addresses': [
                        {
                            'street': 'Somewhere along the street',
                            'zip': '75002',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        ],
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'extra_data': {
                        'contract_1': '16.10',
                        'contract_2': False,
                        'contract_3': '2',
                        },
                    'coverages': [
                        {
                            'coverage': {'code': 'ALP'},
                            'extra_data': {
                                'my_choices': ['a', 'b'],
                                },
                            },
                        ],
                    },
                ],
            'options': {
                'activate': True,
                },
            }

        input_ = copy.deepcopy(multi_selection_data)
        result = ContractAPI.subscribe_contracts(input_,
            {'_debug_server': True})
        Contract = pool.get('contract')
        res_contract = Contract(result['contracts'][0]['id'])
        self.assertEqual(res_contract.options[0].current_extra_data,
            {'my_choices': ['a', 'b']})

    @test_framework.prepare_test(
        'offered.test0030_testProductCoverageRelation',
        'contract.test0002_testCountryCreation',
        'contract.test0005_PrepareProductForSubscription',
        )
    def test9910_test_simulate_API(self):
        pool = Pool()
        ContractAPI = pool.get('api.contract')
        data_ref = {
            'parties': [
                {
                    'ref': '1',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Father',
                    'birth_date': '1980-01-20',
                    'gender': 'male',
                    'addresses': [
                        {
                            'street': 'Somewhere along the street',
                            'zip': '75002',
                            'city': 'Paris',
                            'country': 'fr',
                            },
                        ],
                    },
                ],
            'contracts': [
                {
                    'ref': '1',
                    'product': {'code': 'AAA'},
                    'subscriber': {'ref': '1'},
                    'extra_data': {
                        'contract_1': '16.10',
                        'contract_2': False,
                        'contract_3': '2',
                        },
                    'coverages': [
                        {
                            'coverage': {'code': 'ALP'},
                            'extra_data': {
                                'option_1': '6.10',
                                'option_2': True,
                                'option_3': '2',
                                },
                            },
                        {
                            'coverage': {'code': 'BET'},
                            'extra_data': {},
                            },
                        ],
                    },
                ],
            'options': {
                'activate': True,
                },
            }

        # We have to commit here because simulate is executed in a new
        # transaction, which cannot have access to the contents of the testing
        # transaction
        Transaction().commit()

        data_dict = copy.deepcopy(data_ref)
        simulation = ContractAPI.simulate(data_dict, {'_debug_server': True})

        self.assertEqual(len(simulation), 1)
        self.assertEqual(simulation[0]['ref'], '1')
        self.assertEqual(simulation[0]['product']['code'], 'AAA')
        self.assertEqual(len(simulation[0]['coverages']), 2)

    # CAREFUL: The test above has commited transactions
    # The test addeded below this one will have all the configuration
    # (coverages, product, etc) already in DB

    def test0200_test_api_rule_tree_elements(self):
        APIRuleRuntime = Pool().get('api.rule_runtime')
        with ServerContext().set_context(_test_api_tree_elements=True):
            with ServerContext().set_context(
                    api_rule_context=APIRuleRuntime.get_runtime()):
                self.assertEqual(test_tree_element(
                        'rule_engine.runtime',
                        '_re_get_contract_initial_start_date',
                        {'api.contract':
                            {'start_date': datetime.date(2020, 1, 1)}}
                        ).result,
                    datetime.date(2020, 1, 1))

                self.assertEqual(test_tree_element(
                        'rule_engine.runtime',
                        '_re_contract_signature_date',
                        {'api.contract':
                            {'signature_date': datetime.date(2020, 1, 1)}}
                        ).result,
                    datetime.date(2020, 1, 1))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModuleTestCase))
    return suite
