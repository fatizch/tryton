import unittest
import datetime

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
            }

    @test_framework.prepare_test(
        'offered.test0030_testProductCoverageRelation',
        )
    def test0010_testContractCreation(self):
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
            option.contract.end_date = contract_end_date
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
        test_option(automatic_end_date=auto_date, expected=auto_date,
            to_set=test_date, should_set=True)

        # option with manual date
        test_option(automatic_end_date=auto_date, manual_end_date=manual_date,
            expected=manual_date, to_set=test_date, should_set=True)

        # option with no end date at all
        test_option(expected=contract_end_date, to_set=test_date,
            should_set=True)

        # try setting setting end date anterior to start date
        test_option(expected=contract_end_date, to_set=early_date,
            should_raise=True)

        # try setting setting end date posterior to contract end date
        test_option(expected=contract_end_date, to_set=late_date,
            should_raise=True)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
