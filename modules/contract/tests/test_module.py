import unittest
import datetime
from dateutil.relativedelta import relativedelta

import trytond.tests.test_tryton

from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.pool import Pool

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'contract'

    @classmethod
    def depending_modules(cls):
        return ['offered']

    @classmethod
    def get_models(cls):
        return {
            'Address': 'party.address',
            'Country': 'country.country',
            'Contact': 'contract.contact',
            'ZipCode': 'country.zipcode',
            'Party': 'party.party',
            'Contract': 'contract',
            'Option': 'contract.option',
            'ActivationHistory': 'contract.activation_history',
            'ContractChangeStartDate': 'contract.change_start_date',
            'Coverage': 'offered.option.description',
            'ContractExtraData': 'contract.extra_data',
            'SubStatus': 'contract.sub_status',
            }

    def createContactTypes(self):
        ContactType = Pool().get('contract.contact.type')
        to_create = []
        for code in ('subscriber', 'covered_party'):
            to_create.append(ContactType(code=code, name='dummy'))
        ContactType.save(to_create)

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
        self.assert_(party.id)

    @test_framework.prepare_test(
        'contract.test0001_testPersonCreation',
        'offered.test0030_testProductCoverageRelation',
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
        contract.finalize_contract()
        self.assertEqual(contract.status, 'active')
        self.assert_(contract.contract_number)
        self.assertEqual(contract.start_date, start_date)

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        )
    def test0011_testContractTermination(self):
        contract, = self.Contract.search([])
        self.Contract.do_terminate([contract])
        self.assertEqual(contract.status, 'terminated')
        self.assertEqual(contract.sub_status, self.SubStatus.search(
                [('code', '=', 'reached_end_date')])[0])

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        'contract.createContactTypes',
        )
    def test0012_testContractContactsList(self):
        contract = self.Contract()
        party = self.Party.search([('is_person', '=', True)])[0]
        contract.subscriber = party
        contract.covered_elements = []
        for _count in range(2):  # don't add contact if it already exists
            contract.update_contacts()
            self.assertEqual(len(contract.contacts), 1)
        contract.subscriber = None
        for _count in range(2):
            contract.update_contacts()
            self.assertEqual(len(contract.contacts), 0)

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
        coverage, = self.Coverage.search([])
        start_date = contract.start_date

        def set_test_case(new_date, ant_date, post_date):
            if contract.options:
                for option in contract.options:
                    self.Option.delete([option])
            option_ant = self.Option()
            option_ant.manual_start_date = ant_date
            option_ant.coverage = coverage.id
            option_ant.save()
            option_post = self.Option()
            option_post.manual_start_date = post_date
            option_post.coverage = coverage.id
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
                automatic_end_date=automatic_end_date,
                manual_end_date=manual_end_date,
                contract=contract,
                )
            option.parent_contract = option.contract
            option.contract.end_date = contract_end_date
            self.assertEqual(option.get_end_date('end_date'), expected)
            option.contract.options = [option]
            option.manual_end_date = to_set
            option.save()

            # test check
            if should_raise:
                self.assertRaises(UserError,
                    self.Contract.check_option_end_dates, [option.contract])
            else:
                self.Contract.check_option_end_dates([option.contract])

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
        coverage, = self.Coverage.search([])
        end_option1 = current_end - datetime.timedelta(weeks=2)
        end_option2 = current_end - datetime.timedelta(weeks=4)

        def get_options(option_end_dates):
            options = []
            for end_date in option_end_dates:
                option = self.Option(
                        start_date=contract.start_date,
                        automatic_end_date=end_date,
                        manual_end_date=end_date,
                        end_date=end_date,
                        contract=contract,
                        parent_contract=contract,
                        coverage=coverage,
                        )
                options.append(option)
            return options

        # If the end dates of every options are below the contract
        # end date, the maximum end_date is the latest option end date.
        contract.options = get_options([end_option1, end_option2])
        contract.calculate_activation_dates()
        contract.save()
        self.assertEqual(contract.end_date, end_option1)

    @test_framework.prepare_test(
        'contract.test0010_testContractCreation',
        )
    def test0050_searcher_start_date(self):
        contract, = self.Contract.search([])
        coverage, = self.Coverage.search([])

        def make_option(manual_offset=None):
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


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
