import unittest
import datetime

import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework
from trytond.transaction import Transaction
from trytond.exceptions import UserError


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'contract'

    @classmethod
    def depending_modules(cls):
        return ['offered']

    @classmethod
    def get_models(cls):
        return {
            'Contract': 'contract',
            'Option': 'contract.option',
            'ActivationHistory': 'contract.activation_history',
            'ContractChangeStartDate': 'contract.change_start_date',
            'Coverage': 'offered.option.description',
            'ContractExtraData': 'contract.extra_data',
            'SubStatus': 'contract.sub_status',
            }

    @test_framework.prepare_test(
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
        contract.set_and_propagate_end_date(end_date)
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
            option_ant.start_date = ant_date
            option_ant.coverage = coverage.id
            option_ant.save()
            option_post = self.Option()
            option_post.start_date = post_date
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

        # case 1 : new date posterior to start_date
        new_date = start_date + datetime.timedelta(weeks=2)
        ant_date = new_date - datetime.timedelta(weeks=1)
        post_date = new_date + datetime.timedelta(weeks=1)

        set_test_case(new_date, ant_date, post_date)

        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(contract.options[0].start_date, new_date)
        self.assertEqual(contract.options[1].start_date, post_date)

        # case 2 : new date anterior to start_date
        contract.set_start_date(start_date)
        contract.save()
        new_date = start_date - datetime.timedelta(weeks=2)
        ant_date = new_date - datetime.timedelta(weeks=1)
        post_date = new_date + datetime.timedelta(weeks=1)

        set_test_case(new_date, ant_date, post_date)

        self.assertEqual(new_date, contract.start_date)
        self.assertEqual(new_date, contract.appliable_conditions_date)
        self.assertEqual(contract.options[0].start_date, new_date)
        self.assertEqual(contract.options[1].start_date, post_date)

    def test0030_testOptionEndDate(self):
        start_date = datetime.date(2012, 2, 15)
        auto_date = start_date + datetime.timedelta(weeks=50)
        manual_date = start_date + datetime.timedelta(weeks=60)
        test_date = start_date + datetime.timedelta(weeks=30)
        contract_end_date = start_date + datetime.timedelta(weeks=70)
        early_date = start_date - datetime.timedelta(weeks=1)
        late_date = contract_end_date + datetime.timedelta(weeks=1)

        def test_option(automatic_end_date=None, manual_end_date=None,
                start_date=start_date, expected=None, should_raise=False,
                to_set=None, should_set=True):
            option = self.Option(
                start_date=start_date,
                automatic_end_date=automatic_end_date,
                manual_end_date=manual_end_date,
                contract=self.Contract(end_date=contract_end_date),
                )
            option.parent_contract = option.contract
            option.contract.end_date = contract_end_date
            self.assertEqual(option.get_end_date('end_date'), expected)
            option.contract.options = [option]
            option.manual_end_date = to_set

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
    def test_maximum_end_date(self):
        contract, = self.Contract.search([])
        current_end = contract.end_date
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
                        parent_contract=contract,
                        )
                options.append(option)
            return options

        # If the end dates of every options are below the contract
        # end date, the maximum end_date is the latest option end date.
        contract.options = get_options([end_option1, end_option2])
        contract.calculate_activation_dates()
        self.assertEqual(contract.end_date, end_option1)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
